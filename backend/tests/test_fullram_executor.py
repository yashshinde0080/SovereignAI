"""FullRAM engine lifecycle test on a tiny synthesized model (@slow).

Synthesizes a 2-layer tiny Llama + word-level tokenizer offline, then drives
FullRAMEngine end to end: load → generate → generate_stream → unload.  Guards
regressions in the primary inference path (the one that loads via
AutoModelForCausalLM) that has zero test coverage today.
"""
from pathlib import Path
from unittest.mock import patch

import psutil
import pytest
from tokenizers import Tokenizer, models, pre_tokenizers
from transformers import AutoModelForCausalLM, LlamaConfig, PreTrainedTokenizerFast

from app.engines.fullram.executor import FullRAMEngine

PROMPT = "the quick brown fox jumps over the lazy dog"


def _make_tiny_model(source_dir: Path) -> None:
    """A 2-layer tiny Llama + word-level tokenizer, saved offline."""
    words = [
        "<unk>", "<s>", "</s>", "<pad>", "the", "quick", "brown", "fox",
        "jumps", "over", "lazy", "dog", "hello", "world", "sovereign",
        "engine", "stream", "test", ".", ",", "!", "a", "and", "of", "to",
    ]
    vocab = {w: i for i, w in enumerate(words)}
    tok = Tokenizer(models.WordLevel(vocab=vocab, unk_token="<unk>"))
    tok.pre_tokenizer = pre_tokenizers.Whitespace()
    fast = PreTrainedTokenizerFast(
        tokenizer_object=tok, unk_token="<unk>", bos_token="<s>",
        eos_token="</s>", pad_token="<pad>",
    )
    fast.save_pretrained(source_dir)

    config = LlamaConfig(
        vocab_size=len(vocab), hidden_size=32, intermediate_size=64,
        num_hidden_layers=2, num_attention_heads=4, num_key_value_heads=2,
        max_position_embeddings=128, rope_theta=10000.0,
    )
    AutoModelForCausalLM.from_config(config).save_pretrained(
        source_dir, safe_serialization=True,
    )


@pytest.mark.slow
async def test_fullram_load_generate_unload(tmp_path: Path):
    """Load → generate → generate_stream → unload lifecycle."""
    source = tmp_path / "tiny"
    source.mkdir()
    _make_tiny_model(source)

    engine = FullRAMEngine(str(source), {}, None)
    await engine.load()
    try:
        assert engine.loaded
        assert engine.tokenizer is not None
        assert engine.model is not None

        # Non-streaming generate — random model may produce empty output
        # (all special tokens stripped), but the engine must complete cleanly
        result = await engine.generate(input_data=PROMPT, max_tokens=8, temperature=0.0)
        assert "output" in result
        assert result.get("finish_reason") in ("stop", "length")
        assert int(result["metadata"]["tokens_generated"]) >= 0

        # Streaming generate — tokens or finish_reason must arrive
        got_finish = False
        async for chunk in engine.generate_stream(
            input_data=PROMPT, max_tokens=8, temperature=0.0,
        ):
            if chunk.get("finish_reason"):
                got_finish = True
                break
        assert got_finish, "stream never sent finish_reason"

        # Memory tracking
        usage = engine.get_memory_usage()
        assert "ram_used_gb" in usage
        assert usage["ram_used_gb"] >= 0
    finally:
        await engine.unload()

    # After unload: state is clean
    assert not engine.loaded
    assert engine.model is None
    assert engine.tokenizer is None
    with pytest.raises(RuntimeError):
        await engine.generate(input_data=PROMPT)


@pytest.mark.slow
async def test_fullram_oom_during_generate(tmp_path: Path):
    """OOM during generate propagates — no silent swallow.

    The real OOM→LayerStream fallback lives in ModelManager, not the engine.
    This test verifies the engine doesn't silently eat MemoryError.
    """
    source = tmp_path / "tiny"
    source.mkdir()
    _make_tiny_model(source)

    engine = FullRAMEngine(str(source), {}, None)
    await engine.load()
    try:
        original_generate = engine.model.generate

        def _oom_generate(*args, **kwargs):
            raise MemoryError("CUDA out of memory")

        engine.model.generate = _oom_generate
        with pytest.raises(MemoryError, match="out of memory"):
            await engine.generate(input_data=PROMPT, max_tokens=8)
    finally:
        # Restore before unload so del doesn't fail
        engine.model.generate = original_generate
        await engine.unload()

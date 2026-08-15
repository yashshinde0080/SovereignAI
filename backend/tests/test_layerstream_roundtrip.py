"""Full LayerStream executor round-trip on a freshly-split tiny model (@slow).

Synthesizes a 2-layer tiny Llama + word-level tokenizer entirely offline, then
drives LayerStreamEngine end to end: load() (fresh-split path — the splitter
copies the tokenizer), generate_stream() through the real executor (embed /
layer / norm / lm_head forwards, RoPE, KV cache, sampler), and unload().

This is the layer the loader-only tests can't reach, and it guards two real
regressions: split dirs whose tokenizer was never copied (degenerate
vocab-size-1 tokenizer -> zero tokens) and the meta rotary_emb crash in
execute_forward (rotary buffers from init_empty_weights are meta, and .to()
on a meta tensor raises).
"""
from pathlib import Path

import pytest
import torch
from tokenizers import Tokenizer, models, pre_tokenizers
from transformers import AutoModelForCausalLM, LlamaConfig, PreTrainedTokenizerFast

from app.core.memory_manager import MemoryManager
from app.engines.layerstream.executor import LayerStreamEngine

PROMPT = "the quick brown fox jumps over the lazy dog"


def _make_tiny_model(source_dir: Path) -> None:
    """A 2-layer tiny Llama + word-level tokenizer, saved offline (no download)."""
    words = ["<unk>", "<s>", "</s>", "<pad>", "the", "quick", "brown", "fox",
             "jumps", "over", "lazy", "dog", "hello", "world", "sovereign",
             "engine", "stream", "test", ".", ",", "!", "a", "and", "of", "to"]
    vocab = {w: i for i, w in enumerate(words)}
    tok = Tokenizer(models.WordLevel(vocab=vocab, unk_token="<unk>"))
    tok.pre_tokenizer = pre_tokenizers.Whitespace()
    fast = PreTrainedTokenizerFast(
        tokenizer_object=tok, unk_token="<unk>", bos_token="<s>",
        eos_token="</s>", pad_token="<pad>")
    fast.save_pretrained(source_dir)

    config = LlamaConfig(
        vocab_size=len(vocab), hidden_size=32, intermediate_size=64,
        num_hidden_layers=2, num_attention_heads=4, num_key_value_heads=2,
        max_position_embeddings=128, rope_theta=10000.0,
        tie_word_embeddings=False,  # splitter saves lm_head separately
    )
    AutoModelForCausalLM.from_config(config).save_pretrained(
        source_dir, safe_serialization=True)


@pytest.mark.slow
async def test_layerstream_executor_roundtrip(tmp_path: Path, monkeypatch):
    source = tmp_path / "tiny"
    source.mkdir()
    _make_tiny_model(source)

    # Keep the engine's runtime storage (offload_cache) inside the tmp dir.
    from app.config import settings
    monkeypatch.setattr(settings, "workspace_dir", tmp_path)

    engine = LayerStreamEngine(str(source), {}, MemoryManager())
    await engine.load()
    try:
        assert engine.loaded
        assert engine.layer_executor.num_layers == 2

        # The fresh split must carry the tokenizer — otherwise transformers
        # silently builds a vocab-size-1 tokenizer and nothing gets generated.
        weights_dir = Path(engine.weights_dir)
        assert weights_dir.is_dir()
        assert (weights_dir / "tokenizer.json").exists()
        assert (weights_dir / "tokenizer_config.json").exists()

        tokens, finishes, layers_seen = [], [], set()
        async for chunk in engine.generate_stream(
            input_data=PROMPT, max_tokens=8, temperature=0.0  # greedy, deterministic
        ):
            if chunk.get("token"):
                tokens.append(chunk["token"])
            if chunk.get("finish_reason"):
                finishes.append(chunk["finish_reason"])
            if chunk.get("layers_loaded"):
                layers_seen.add(chunk["layers_loaded"])

        # Real tokens flowed through the executor (not the degenerate empty
        # output), across all 2 layers, and generation terminated cleanly.
        assert any(t.strip() for t in tokens), f"no tokens emitted: {tokens!r}"
        assert layers_seen == {2}
        assert finishes and finishes[-1] in ("stop", "length")

        # Non-streaming path shares the executor; TaskResolver defaults are safe.
        result = await engine.generate(input_data=PROMPT, max_tokens=4, temperature=0.0)
        assert result["output"].strip()
        assert int(result["metadata"]["tokens_generated"]) >= 1

        assert engine.get_memory_usage()["ram_used_gb"] >= 0
    finally:
        await engine.unload()

    assert not engine.loaded
    assert engine.layer_executor is None
    with pytest.raises(RuntimeError):
        await engine.generate(input_data=PROMPT)

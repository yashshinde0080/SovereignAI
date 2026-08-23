"""Text generation loop with KV-cache.

Two-phase generation:
1. Prefill: process all prompt tokens at once (fills KV-cache)
2. Decode: generate one token at a time using cached k/v
"""

from __future__ import annotations

import numpy as np

from .model import TransformerModel
from .tokenizer import Tokenizer
from .kv_cache import KVCache
from .utils import sample_token, get_peak_rss_mb, GenerationResult, Timer


def generate(
    model: TransformerModel,
    tokenizer: Tokenizer,
    prompt: str,
    max_tokens: int = 128,
    temperature: float = 0.7,
    top_p: float = 0.9,
    top_k: int = 0,
) -> GenerationResult:
    """Generate text from a prompt.

    Uses KV-cache for efficient autoregressive generation:
    - Prefill phase: run all prompt tokens through model (fills cache)
    - Decode phase: generate one token at a time, reusing cached k/v
    """
    config = model.config

    # Cap prompt at context length
    ids = tokenizer.encode(prompt)
    max_ctx = config.max_position_embeddings - max_tokens
    if len(ids) > max_ctx:
        ids = ids[:max_ctx]
    n_prompt = len(ids)

    # Initialize KV-cache
    kv_cache = KVCache(
        n_layers=config.n_layers,
        n_heads=config.n_kv_heads,
        head_dim=config.head_dim,
        max_seq_len=config.max_position_embeddings,
    )

    generated: list[int] = []

    with Timer() as timer:
        # ── Prefill phase ───────────────────────────────────────────
        if ids:
            input_ids = np.array(ids, dtype=np.int64)
            logits = model.forward(input_ids, kv_cache)
            next_logits = logits[-1]  # logits for last prompt position
        else:
            # Empty prompt: use BOS token as starting point
            bos = tokenizer.bos_token_id if tokenizer.bos_token_id else 0
            input_ids = np.array([bos], dtype=np.int64)
            logits = model.forward(input_ids, kv_cache)
            next_logits = logits[-1]

        next_token = sample_token(next_logits, temperature, top_p, top_k)

        if next_token != tokenizer.eos_token_id:
            generated.append(next_token)

        # ── Decode phase ────────────────────────────────────────────
        for _ in range(max_tokens - 1):
            if next_token == tokenizer.eos_token_id:
                break

            input_ids = np.array([next_token], dtype=np.int64)
            logits = model.forward(input_ids, kv_cache)
            next_logits = logits[-1]
            next_token = sample_token(next_logits, temperature, top_p, top_k)

            if next_token != tokenizer.eos_token_id:
                generated.append(next_token)

    text = tokenizer.decode(generated)
    return GenerationResult(
        text=text,
        token_ids=generated,
        n_prompt_tokens=n_prompt,
        n_generated_tokens=len(generated),
        elapsed_s=timer.elapsed,
        tokens_per_second=len(generated) / timer.elapsed if timer.elapsed > 0 else 0,
        peak_rss_mb=get_peak_rss_mb(),
        kv_cache_mb=kv_cache.size_mb,
    )

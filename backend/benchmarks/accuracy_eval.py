"""Accuracy eval gate for the TurboQuant KV cache.

The gate that must pass before `turboquant_enabled` may be re-enabled, and the
place where the ablation-tuned QJL gain (benchmarks/qjl_ablation.py) gets
re-validated on REAL model K/V.

What it measures, for each cache configuration vs the model's native cache
(FP16/FP32 baseline):
  1. Chunked perplexity on real text (wikitext) with the cache carried across
     chunks - i.e. the actual decode-time usage, exercising the hot-buffer
     flush path (chunk_size=64).
  2. Needle-in-haystack recall: a secret sentence buried in long filler
     context, probed by P(needle-token) and greedy continuation.

Gate verdict: a configuration PASSES if perplexity degradation vs baseline is
< 2% AND needle-token probability is not more than 10x worse than baseline
(3 orders of magnitude log-prob). The QJL-on vs QJL-off comparison re-checks
the keep-vs-drop decision on real K/V.

Usage:
  python -m benchmarks.accuracy_eval --smoke          # tiny random model, wiring check
  python -m benchmarks.accuracy_eval --model Qwen/Qwen2-0.5B --tokens 2048 --context 2048

Runs on CPU; model is loaded in fp32 (native cache = fp32; TQ cache stores
fp16 scales on top of its quantized indices, i.e. strictly less memory).
"""

import argparse
import json
import math
import os
import time

import torch

from app.engines.shared.turboquant import (
    TurboQuantConfig,
    TurboQuantKVCacheManager,
    TurboQuantHFProxyCache,
)

CHUNK = 64  # matches the manager's hot-buffer flush size
NEEDLE = "The secret password is PINEAPPLE123."
PROBE = "What is the secret password? The secret password is"
GATE_PPL_DEGRADATION = 0.02   # 2% relative perplexity degradation allowed
GATE_NEEDLE_LOGPROB_FACTOR = 10.0  # needle P may drop at most 10x vs baseline


def _model_dims(model):
    cfg = model.config
    head_dim = getattr(cfg, "head_dim", None) or (cfg.hidden_size // cfg.num_attention_heads)
    return cfg.num_hidden_layers, cfg.num_attention_heads, head_dim


def make_tq_cache(tq_kwargs: dict, model) -> TurboQuantHFProxyCache:
    num_layers, num_heads, head_dim = _model_dims(model)
    config = TurboQuantConfig(**tq_kwargs)
    mgr = TurboQuantKVCacheManager(
        config, num_layers=num_layers, num_heads=num_heads, head_dim=head_dim, device="cpu"
    )
    return TurboQuantHFProxyCache(mgr)


def _get_cache(out) -> torch.nn.Module:
    """5.x returns the cache under past_key_values or cache depending on version."""
    return getattr(out, "past_key_values", None) or getattr(out, "cache", None)


@torch.no_grad()
def chunked_perplexity(model, tokenizer, text, tq_kwargs=None, chunk=CHUNK, log_every=16):
    """Next-token perplexity over `text`, feeding it in chunks with the cache
    carried (the decode-time path). `tq_kwargs=None` uses the native cache."""
    ids = tokenizer(text, return_tensors="pt").input_ids
    n = ids.shape[1]
    cache = None
    if tq_kwargs is not None:
        cache = make_tq_cache(tq_kwargs, model)
    total_nll, total_tokens, start = 0.0, 0, time.time()
    for i in range(0, n - 1, chunk):
        batch = ids[:, i : i + chunk]
        out = model(batch, past_key_values=cache, use_cache=True)
        logits = out.logits[:, :-1]  # [1, C-1, V]
        labels = batch[:, 1:]
        nll = torch.nn.functional.cross_entropy(
            logits.reshape(-1, logits.shape[-1]), labels.reshape(-1), reduction="sum"
        ).item()
        total_nll += nll
        total_tokens += labels.numel()
        cache = _get_cache(out)
        if log_every and (i // chunk) % log_every == 0:
            done = min(i + chunk, n - 1)
            print(f"    [{done}/{n-1}] ppl-so-far {math.exp(total_nll / total_tokens):.3f} "
                  f"({time.time() - start:.0f}s)")
    return math.exp(total_nll / total_tokens)


def _build_haystack(tokenizer, context_tokens: int, needle: str):
    """Filler text with the needle buried at ~40% depth."""
    filler = (
        "The quick brown fox jumps over the lazy dog near the riverbank. "
        "It is a bright sunny morning and the birds are singing in the trees. "
        "People walk along the path carrying baskets of fresh fruit and bread. "
    )
    needle_ids = tokenizer(needle, return_tensors="pt").input_ids[0]
    probe_ids = tokenizer(PROBE, return_tensors="pt").input_ids[0]
    budget = context_tokens - needle_ids.numel() - probe_ids.numel() - 16
    filler_ids = tokenizer(filler, return_tensors="pt").input_ids[0]
    repeats = (budget + filler_ids.numel() - 1) // filler_ids.numel()
    hay = filler_ids.repeat(repeats)
    insert_at = int(len(hay) * 0.4)
    hay = torch.cat([hay[:insert_at], needle_ids, hay[insert_at:]])
    return hay, probe_ids


@torch.no_grad()
def needle_recall(model, tokenizer, tq_kwargs, context_tokens=2048, generate=8):
    """P(needle-token) after the probe, plus a greedy continuation match."""
    hay, probe_ids = _build_haystack(tokenizer, context_tokens, NEEDLE)
    cache = None
    if tq_kwargs is not None:
        cache = make_tq_cache(tq_kwargs, model)

    # Feed the haystack in chunks, then the probe.
    all_ids = torch.cat([hay, probe_ids])
    for i in range(0, len(hay), CHUNK):
        out = model(hay[i : i + CHUNK].unsqueeze(0), past_key_values=cache, use_cache=True)
        cache = _get_cache(out)
    out = model(probe_ids.unsqueeze(0), past_key_values=cache, use_cache=True)
    cache = _get_cache(out)
    next_logits = out.logits[:, -1, :]  # [1, V]
    pwd_ids = tokenizer("PINEAPPLE", add_special_tokens=False, return_tensors="pt").input_ids
    # Mean log-prob over the password token(s). Approximation: all tokens are
    # scored against the final probe logits (fine for a fixed single word).
    logp = torch.log_softmax(next_logits, dim=-1)[0, pwd_ids[0]].mean().item()

    # Greedy continuation, 1 token at a time (exercises per-token update path).
    gen = []
    cur = probe_ids.unsqueeze(0)
    for _ in range(generate):
        out = model(cur, past_key_values=cache, use_cache=True)
        cache = _get_cache(out)
        nxt = out.logits[:, -1, :].argmax(-1)
        gen.append(nxt.item())
        cur = nxt.unsqueeze(0)
    text = tokenizer.decode(gen, skip_special_tokens=True)
    return logp, text, ("PINEAPPLE" in text or "Pineapple" in text)


_WIKITEXT_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "..", "..", "reviews", "eval_wikitext.txt")


def get_wikitext_slice(tokens: int) -> tuple[str, str]:
    """Fetch a slice of wikitext-2 test (datasets-server HTTP API, no pyarrow
    needed); prefer the local cache file (``reviews/eval_wikitext.txt``) for
    reproducibility and offline use. Falls back to synthetic text if both the
    cache and network fail.

    ``tokens`` is a character budget (chars ~= tokens * 4). Returns
    ``(text, source)`` where source identifies the actual source.
    """
    import json as _json
    import urllib.request as _url

    # Prefer the local cache (offline-able, reproducible).
    if os.path.exists(_WIKITEXT_CACHE):
        with open(_WIKITEXT_CACHE, encoding="utf-8") as _f:
            lines = [l.strip() for l in _f if len(l.strip()) > 80]
        if lines:
            print(f"    using cached wikitext ({_WIKITEXT_CACHE})")
            return "\n".join(lines)[: tokens * 4], "wikitext-cache"

    try:
        api = ("https://datasets-server.huggingface.co/rows?dataset=Salesforce%2Fwikitext"
               "&config=wikitext-2-raw-v1&split=test&offset=0&length=25")
        with _url.urlopen(api, timeout=30) as resp:
            data = _json.load(resp)
        lines = [r["row"]["text"].strip() for r in data["rows"] if len(r["row"]["text"].strip()) > 80]
        if lines:
            return "\n".join(lines)[: tokens * 4], "wikitext"
        raise RuntimeError("no long lines in wikitext rows")
    except Exception as e:  # pragma: no cover - network fallback
        print(f"    wikitext fetch failed ({e}); using synthetic text")
        return "The quick brown fox jumps over the lazy dog. " * (tokens // 9), "synthetic-fallback"


def run_config(model, tokenizer, label, tq_kwargs, text, context, out):
    print(f"  [{label}] perplexity...")
    t0 = time.time()
    ppl = chunked_perplexity(model, tokenizer, text, tq_kwargs)
    print(f"  [{label}] needle-in-haystack...")
    logp, gen, hit = needle_recall(model, tokenizer, tq_kwargs, context_tokens=context)
    row = {"label": label, "tq_kwargs": tq_kwargs, "perplexity": ppl,
           "needle_logp": logp, "needle_gen": gen, "needle_hit": hit,
           "seconds": time.time() - t0}
    out.append(row)
    print(f"  [{label}] ppl={ppl:.3f} needle_logp={logp:.3f} hit={hit}")
    # Windows consoles are often cp1252; never let a generated token crash the gate.
    safe = gen.encode("ascii", "replace").decode("ascii")
    print(f"             needle continuation: {safe!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen2-0.5B")
    ap.add_argument("--tokens", type=int, default=1536)
    ap.add_argument("--context", type=int, default=1536)
    ap.add_argument("--smoke", action="store_true", help="tiny random model, fast wiring check")
    ap.add_argument("--out", default=None, help="JSON results path")
    args = ap.parse_args()

    model_id = "hf-internal-testing/tiny-random-LlamaForCausalLM" if args.smoke else args.model
    from transformers import AutoModelForCausalLM, AutoTokenizer

    print(f"Loading {model_id} (fp32, CPU)...")
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(model_id, dtype=torch.float32)
    model.eval()

    text, text_source = get_wikitext_slice(args.tokens)
    # Trim to a multiple of CHUNK for clean flushes.
    ids = tokenizer(text, return_tensors="pt").input_ids[0]
    ids = ids[: (ids.numel() // CHUNK) * CHUNK]
    text = tokenizer.decode(ids)
    print(f"Eval text: {ids.numel()} tokens, source {text_source}, model {model_id}")

    configs = [
        ("baseline", None),
        # Per-channel affine (KIVI-style) re-gate. Polar configs (3.5+qjl,
        # 3.5-noqjl, 4.0+qjl -> ppl 1201/3434/3623) are recorded in
        # reviews/eval_gate_2026-08-09.json from the 2026-08-09 run.
        ("tq-affine-3.5", {"bits_per_coord": 3.5, "quant_scheme": "affine"}),
        ("tq-affine-4.0", {"bits_per_coord": 4.0, "quant_scheme": "affine"}),
        ("tq-affine-4k5v", {"bits_per_coord": 4.0, "quant_scheme": "affine", "v_bits": 5.0}),
        ("tq-affine-4k6v", {"bits_per_coord": 4.0, "quant_scheme": "affine", "v_bits": 6.0}),
    ]
    results = []
    for label, tq_kwargs in configs:
        run_config(model, tokenizer, label, tq_kwargs, text, args.context, results)
        print()

    baseline = results[0]["perplexity"]
    baseline_logp = results[0]["needle_logp"]
    print("=" * 78)
    print(f"{'config':<16}{'ppl':>9}{'deg%':>8}{'needle_logp':>13}{'hit':>6}")
    verdicts = {}
    for r in results:
        deg = (r["perplexity"] / baseline - 1) * 100 if r["label"] != "baseline" else 0.0
        print(f"{r['label']:<16}{r['perplexity']:>9.3f}{deg:>8.2f}"
              f"{r['needle_logp']:>13.3f}{str(r['needle_hit']):>6}")
        if r["label"] != "baseline":
            ppl_ok = deg < GATE_PPL_DEGRADATION * 100
            needle_ok = r["needle_logp"] > baseline_logp - math.log(GATE_NEEDLE_LOGPROB_FACTOR)
            verdicts[r["label"]] = ppl_ok and needle_ok
    print("-" * 78)
    for label, passed in verdicts.items():
        print(f"  {label}: {'PASS' if passed else 'FAIL'}")
    print("=" * 78)
    print(f"Gate: ppl degradation < {GATE_PPL_DEGRADATION*100:.0f}% AND needle logp within "
          f"{GATE_NEEDLE_LOGPROB_FACTOR:.0f}x of baseline")
    print(f"NOTE: ~{ids.numel()} scored tokens is a coarse gate (fine for catching catastrophic "
          f"failure; a release-grade gate should use 4-8k+ tokens). Text source: {text_source}")
    qjl_on = next((r for r in results if r["label"] == "tq-3.5+qjl"), None)
    qjl_off = next((r for r in results if r["label"] == "tq-3.5-noqjl"), None)
    if qjl_on is not None and qjl_off is not None:
        if qjl_on["perplexity"] < qjl_off["perplexity"]:
            print(f"QJL gain re-validation on real K/V: QJL-ON beats QJL-off "
                  f"({qjl_on['perplexity']:.3f} vs {qjl_off['perplexity']:.3f}) -> keep")
        else:
            print(f"QJL gain re-validation on real K/V: QJL-off beats QJL-ON "
                  f"({qjl_off['perplexity']:.3f} vs {qjl_on['perplexity']:.3f}) -> reconsider")
    else:
        print("QJL comparison skipped (polar configs not in this run; 2026-08-09 gate: "
              "3.5+qjl 1201 vs 3.5-noqjl 3434 on Qwen2-0.5B)")

    if args.out:
        with open(args.out, "w") as f:
            json.dump({"model": model_id, "tokens": ids.numel(),
                       "text_source": text_source, "results": results}, f, indent=2)
        print(f"Results written to {args.out}")


if __name__ == "__main__":
    main()

"""Compare the `turboquant_plus` reference PolarQuant/TurboQuant codec against
our affine/polar numbers on the SAME captured Qwen2 K/V tensors.

Answers: "is our accuracy failure codebook-side or regime-side?" If the
reference (per-vector norm extraction + Gaussian Lloyd-Max centroids + norm
correction) hits dramatically lower NMSE than our uniform-codebook polar
(0.142 K @ 3.5+qjl) and approaches affine-4bit (0.0050), the fix is a codebook
swap. If it lands at the same ~1-2% NMSE, the small-model regime is the wall.

Usage: python -m benchmarks.reference_polar_probe [--layers 4] [--tokens 128]
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# Reference implementation lives at repo-root llama-cpp-tq/turboquant
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "llama-cpp-tq"))

from turboquant.polar_quant import PolarQuant
from turboquant.turboquant import TurboQuant, TurboQuantMSE

from app.engines.shared.turboquant import (
    TurboQuantConfig,
    TurboQuantKVCacheManager,
    TurboQuantHFProxyCache,
)

MODEL = "Qwen/Qwen2-0.5B"


def nmse(a, b):
    return ((a - b) ** 2).mean().item() / ((b ** 2).mean().item() + 1e-12)


def as_vectors(t: torch.Tensor) -> np.ndarray:
    """[1, nh, seq, hd] -> (nh*seq, hd) float64 numpy rows (one vector per row)."""
    return t[0].reshape(-1, t.shape[-1]).cpu().numpy().astype(np.float64)


def ref_polar_nmse(x: np.ndarray, bits: int, with_qjl: bool, norm_correct: bool) -> float:
    """NMSE of reference codec on a (n, d) matrix of vectors."""
    d = x.shape[1]
    if with_qjl:
        tq = TurboQuant(d=d, bit_width=bits, seed=42, norm_correction=norm_correct)
        c = tq.quantize(x)
        recon = tq.dequantize(c)
    else:
        tq = TurboQuantMSE(d=d, bit_width=bits, seed=42, norm_correction=norm_correct)
        idx, norms = tq.quantize(x)
        recon = tq.dequantize(idx, norms)
    return float(((recon - x) ** 2).mean() / ((x ** 2).mean() + 1e-12))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--layers", default="4")
    ap.add_argument("--tokens", type=int, default=256)
    args = ap.parse_args()
    probe_layers = [int(s) for s in args.layers.split(",")]

    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(args.model, dtype=torch.float32)
    model.eval()
    cfg = model.config
    kv_heads = getattr(cfg, "num_key_value_heads", cfg.num_attention_heads)
    hd = getattr(cfg, "head_dim", None) or (cfg.hidden_size // cfg.num_attention_heads)
    print(f"{args.model}: kv_heads={kv_heads} head_dim={hd}", flush=True)

    captured = {}
    orig_update = TurboQuantHFProxyCache.update

    def recording(self, key_states, value_states, layer_idx, cache_kwargs=None):
        captured[layer_idx] = (key_states.detach().float(), value_states.detach().float())
        return orig_update(self, key_states, value_states, layer_idx, cache_kwargs)

    TurboQuantHFProxyCache.update = recording

    mgr_cfg = TurboQuantConfig(bits_per_coord=3.5, enable_qjl=True, device="cpu")
    proxy = TurboQuantHFProxyCache(
        TurboQuantKVCacheManager(mgr_cfg, num_layers=cfg.num_hidden_layers,
                                 num_heads=kv_heads, head_dim=hd, device="cpu")
    )
    text = "The quick brown fox jumps over the lazy dog near the riverbank. " * (args.tokens // 9)
    ids = tok(text, return_tensors="pt").input_ids
    cache = proxy
    with torch.no_grad():
        for i in range(0, ids.shape[1], 64):
            out = model(ids[:, i : i + 64], past_key_values=cache, use_cache=True)
            cache = getattr(out, "past_key_values", None) or getattr(out, "cache", None)
    print(f"captured {len(captured)} layers", flush=True)

    print(f"\n=== NMSE on same captured tensors (layer {probe_layers[0]}) ===")
    print(f"{'method':<28} {'K NMSE':>10} {'V NMSE':>10}")
    k, v = captured[probe_layers[0]]
    k, v = k[0], v[0]  # [nh, seq, hd]

    # Our current pipeline (polar 3.5 + QJL) — reference numbers from the report
    mgr = TurboQuantKVCacheManager(mgr_cfg, num_layers=1, num_heads=kv_heads,
                                   head_dim=hd, device="cpu")
    kc, vc = mgr._quantize_kv(k.unsqueeze(0), v.unsqueeze(0))
    kr, vr = mgr._dequantize_kv(kc, vc)
    print(f"{'our polar 3.5+qjl':<28} {nmse(kr, k.unsqueeze(0)):>10.5f} {nmse(vr, v.unsqueeze(0)):>10.5f}")

    k_np, v_np = as_vectors(k.unsqueeze(0)), as_vectors(v.unsqueeze(0))

    # Reference PolarQuant (MSE-only) at 2/3/4 bits, norm correction on
    for bits in (2, 3, 4):
        km = ref_polar_nmse(k_np, bits, with_qjl=False, norm_correct=True)
        vm = ref_polar_nmse(v_np, bits, with_qjl=False, norm_correct=True)
        print(f"{f'ref PolarQuant {bits}-bit (nc)':<28} {km:>10.5f} {vm:>10.5f}")

    # Reference full TurboQuant (PolarQuant b-1 bits + QJL 1 bit)
    for bits in (3, 4):
        km = ref_polar_nmse(k_np, bits, with_qjl=True, norm_correct=True)
        vm = ref_polar_nmse(v_np, bits, with_qjl=True, norm_correct=True)
        print(f"{f'ref TurboQuant {bits}-bit (b-1+1)':<28} {km:>10.5f} {vm:>10.5f}")

    # Norm correction off (isolate its contribution)
    km = ref_polar_nmse(k_np, 3, with_qjl=False, norm_correct=False)
    vm = ref_polar_nmse(v_np, 3, with_qjl=False, norm_correct=False)
    print(f"{'ref PolarQuant 3-bit (no nc)':<28} {km:>10.5f} {vm:>10.5f}")

    print(f"\nReference (report): affine 4-bit K 0.0050 / V 0.026; affine 3-bit K 0.0228 / V 0.092.")


if __name__ == "__main__":
    main()

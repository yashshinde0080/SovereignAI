"""Probe real Qwen2-0.5B K/V structure to size the per-channel affine quantizer.

Captures real K/V through the TurboQuant proxy's update() hook, then measures:
  1. Per-channel std structure (K across tokens, V across head-dim) — the
     premise of KIVI-style per-channel scales.
  2. Best-achievable NMSE for per-channel affine quantization (K: per-(nh,hd)
     max-abs scale, V: per-(nh,seq) max-abs scale) vs the current polar
     pipeline on the SAME captured tensors.

Usage:  python -m benchmarks.kv_structure_probe [--layers 0,4,8,12,16,20]
"""
import argparse

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from app.engines.shared.turboquant import (
    TurboQuantConfig,
    TurboQuantKVCacheManager,
    TurboQuantHFProxyCache,
)

MODEL = "Qwen/Qwen2-0.5B"


def nmse(a, b):
    return ((a - b) ** 2).mean().item() / ((b ** 2).mean().item() + 1e-12)


def affine_nmse(x, bits, which):
    """Uniform per-group affine quantization NMSE estimate.

    which='k': scale per (nh, hd) over the seq dim (per-channel).
    which='v': scale per (nh, seq) over the hd dim (per-token).
    """
    L = int(2 ** bits)
    half = L / 2.0
    if which == "k":
        scale = x.abs().amax(dim=1, keepdim=True).clamp(min=1e-8)  # [nh,1,hd]
    else:
        scale = x.abs().amax(dim=2, keepdim=True).clamp(min=1e-8)  # [nh,seq,1]
    q = (x / scale * half).round().clamp(-half, half - 1)
    recon = (q / half) * scale
    return nmse(recon, x)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--layers", default="0,4,8,12,16,20")
    ap.add_argument("--tokens", type=int, default=512)
    args = ap.parse_args()
    model_id = args.model
    probe_layers = [int(s) for s in args.layers.split(",")]

    tok = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(model_id, dtype=torch.float32)
    model.eval()
    cfg = model.config
    num_layers = cfg.num_hidden_layers
    kv_heads = getattr(cfg, "num_key_value_heads", cfg.num_attention_heads)
    hd = getattr(cfg, "head_dim", None) or (cfg.hidden_size // cfg.num_attention_heads)
    print(f"{model_id}: layers={num_layers} kv_heads={kv_heads} head_dim={hd}", flush=True)

    # Token-vector norms: the sharpness signal (Qwen2-0.5B keys ~215 -> logits
    # ~5800; a moderate-norm model should be ~10-40).
    with torch.no_grad():
        ids = tok("The quick brown fox jumps over the lazy dog. " * 4, return_tensors="pt").input_ids
        k_norms = {}

        def grab_k(store, layer):
            def h(m, inp, out):
                store[layer] = out.detach().float()
            return h

        for name, mod in model.named_modules():
            if name.endswith("k_proj"):
                layer = int(name.split(".")[2]) if len(name.split(".")) > 2 else 0
                mod.register_forward_hook(grab_k(k_norms, layer))
        out = model(ids)
        for lay in sorted(k_norms)[:3]:
            k = k_norms[lay].reshape(-1, k_norms[lay].shape[-1])
            print(f"  layer {lay} key norms: mean {k.norm(dim=-1).mean().item():.1f} "
                  f"max {k.norm(dim=-1).max().item():.1f}", flush=True)

    captured = {}
    orig_update = TurboQuantHFProxyCache.update

    def recording(self, key_states, value_states, layer_idx, cache_kwargs=None):
        captured[layer_idx] = (key_states.detach().float(), value_states.detach().float())
        return orig_update(self, key_states, value_states, layer_idx, cache_kwargs)

    TurboQuantHFProxyCache.update = recording

    mgr_cfg = TurboQuantConfig(bits_per_coord=3.5, enable_qjl=True, device="cpu")
    proxy = TurboQuantHFProxyCache(
        TurboQuantKVCacheManager(mgr_cfg, num_layers=num_layers, num_heads=kv_heads,
                                 head_dim=hd, device="cpu")
    )

    text = "The quick brown fox jumps over the lazy dog near the riverbank. " * (args.tokens // 9)
    ids = tok(text, return_tensors="pt").input_ids
    cache = proxy
    with torch.no_grad():
        for i in range(0, ids.shape[1], 64):
            out = model(ids[:, i : i + 64], past_key_values=cache, use_cache=True)
            cache = getattr(out, "past_key_values", None) or getattr(out, "cache", None)
    print(f"captured {len(captured)} layers", flush=True)

    print("\n=== per-channel structure (last chunk, layer per row) ===")
    print(f"{'layer':>5} | K ch std  min/max/mean | K ch cv  | V tok std min/max/mean")
    for lay in probe_layers:
        if lay not in captured:
            continue
        k, v = captured[lay]
        k = k[0]  # [nh, seq, hd]
        v = v[0]
        ks = k.std(dim=1)  # [nh, hd]
        vs = v.std(dim=2)  # [nh, seq]
        print(f"{lay:>5} | {ks.min().item():.3f}/{ks.max().item():.3f}/{ks.mean().item():.3f}"
              f" | {(ks.std() / ks.mean()).item():.3f}"
              f" | {vs.min().item():.3f}/{vs.max().item():.3f}/{vs.mean().item():.3f}")

    print("\n=== NMSE on same captured tensors (layer 4 reference) ===")
    k, v = captured[probe_layers[0]]
    k, v = k[0], v[0]
    # current pipeline (polar 3.5 + QJL)
    mgr = TurboQuantKVCacheManager(mgr_cfg, num_layers=1, num_heads=kv_heads,
                                   head_dim=hd, device="cpu")
    kc, vc = mgr._quantize_kv(k.unsqueeze(0), v.unsqueeze(0))
    kr, vr = mgr._dequantize_kv(kc, vc)
    print(f"  polar 3.5+qjl : K {nmse(kr, k.unsqueeze(0)):.5f}  V {nmse(vr, v.unsqueeze(0)):.5f}")
    for bits in (3, 4, 5, 6):
        print(f"  affine {bits}bit : K {affine_nmse(k, bits, 'k'):.5f}"
              f"  V {affine_nmse(v, bits, 'v'):.5f}")


if __name__ == "__main__":
    main()

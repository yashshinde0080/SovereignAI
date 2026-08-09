"""QJL drop-vs-fix ablation for the TurboQuant KV cache.

Decision input for: at >= 3 bits, does the 1-bit QJL residual correction earn
its storage? Compares three modes across bit rates on data resembling model
K/V activations:

  off      — PolarQuant only (no QJL)
  shipped  — QJL as shipped BEFORE tuning (frozen here for reproducibility):
             decode divides by d' after P was normalized by 1/sqrt(d') -> net
             1/d'^1.5 attenuation (undercorrects)
  fixed    — QJL with the empirically tuned decode c = 1/32 (what qjl.py now
             ships, per this ablation)

NOTE: the "shipped" decode is FROZEN in this script (`shipped_qjl_decode`)
so the tables stay reproducible after the qjl.py change. Do not bind it to
the live module function — it now IS the tuned decode.

Metrics per mode:
  kv_nmse  — reconstruction NMSE of quantized K/V vs the FP16 original
  attn_nmse— output fidelity: fresh random queries through softmax(QK^T)V
             using quantized vs FP16 KV (the direct downstream metric)
  mb       — compressed size (K+V) so same-budget comparisons are visible

Theory being tested (TurboQuant paper + community consensus): the QJL
estimator has a per-coordinate noise floor of ~1/qjl_dim, independent of the
residual. PolarQuant error at 3.5 bits is ~(2/10)^2/12 = 0.0033, BELOW the
floor (1/64 = 0.0156) — so QJL should help only at <= 2.5 bits and hurt or
do nothing at >= 3. The table below verifies this numerically.

Run:  cd backend && ./.venv/Scripts/python.exe -m benchmarks.qjl_ablation
"""

import math
import statistics
import torch

from app.engines.shared.turboquant import TurboQuantConfig, TurboQuantKVCacheManager
import app.engines.shared.turboquant.kv_cache as kvc

NH, HD, SEQ = 8, 64, 256          # qjl_dim defaults to HD
QUERY_POS = 8                     # fresh query positions for attention fidelity
BITS = [2.0, 2.5, 3.0, 3.5, 4.0]
DISTS = ["normal", "t4"]
SEEDS = [0, 1, 2]


def shipped_qjl_decode(codes: torch.Tensor, P: torch.Tensor) -> torch.Tensor:
    """The pre-tuning shipped decode: codes @ P / d' (undercorrects).

    Frozen here so the ablation record is reproducible after qjl.py changed.
    """
    return codes.to(torch.float32) @ P / P.shape[0]


def fixed_qjl_decode(codes: torch.Tensor, P: torch.Tensor) -> torch.Tensor:
    """QJL decode with the empirically-tuned scale (matches shipped qjl.py).

    c = 1/32 is the sweep optimum at BOTH hd=32 and hd=64 (the textbook
    1/sqrt(d') overcorrects; the old shipped 1/d' undercorrects). Tuned on
    synthetic K/V — re-validate on real models in the eval-gate task.
    """
    return codes.to(torch.float32) @ P / 32.0


def nmse(a: torch.Tensor, b: torch.Tensor) -> float:
    """Normalized MSE: error power relative to signal power."""
    return ((a - b) ** 2).mean().item() / ((b ** 2).mean().item() + 1e-12)


def make_data(dist: str, seed: int):
    g = torch.Generator().manual_seed(seed)
    if dist == "normal":
        k = torch.randn(1, NH, SEQ, HD, generator=g, dtype=torch.float16)
        v = torch.randn(1, NH, SEQ, HD, generator=g, dtype=torch.float16)
    else:  # t4: heavy-tailed, K/V cache values are not perfectly Gaussian
        t = torch.distributions.StudentT(df=4)
        k = t.sample((1, NH, SEQ, HD)).clamp(-8, 8).to(torch.float16)
        v = t.sample((1, NH, SEQ, HD)).clamp(-8, 8).to(torch.float16)
    q = torch.randn(1, NH, QUERY_POS, HD, generator=g)
    return k, v, q


def run_case(mgr, k, v, q):
    mgr.update(0, k, v)
    k_recon, v_recon = mgr.get(0)
    kv_nmse = (nmse(k_recon.float(), k.float()) + nmse(v_recon.float(), v.float())) / 2
    qf, kf, vf = q.float(), k.float(), v.float()
    scale = HD ** -0.5
    logits = qf @ kf.transpose(-1, -2) * scale
    logits_q = qf @ k_recon.float().transpose(-1, -2) * scale
    out = torch.softmax(logits, -1) @ vf
    out_q = torch.softmax(logits_q, -1) @ v_recon.float()
    attn_nmse = nmse(out_q, out)
    return kv_nmse, attn_nmse, mgr.get_size_mb() * 1024 * 1024


def mean(xs):
    return statistics.mean(xs)


def main():
    orig_decode = kvc.qjl_decode
    results = {}  # (dist, bits, mode) -> (kv_nmse, attn_nmse, bytes)
    for dist in DISTS:
        for bits in BITS:
            for mode in ("off", "shipped", "fixed"):
                if mode == "shipped":
                    kvc.qjl_decode = shipped_qjl_decode  # frozen historical
                elif mode == "fixed":
                    kvc.qjl_decode = fixed_qjl_decode
                kv_m, at_m, by = [], [], []
                for seed in SEEDS:
                    k, v, q = make_data(dist, seed)
                    cfg = TurboQuantConfig(
                        bits_per_coord=bits, enable_qjl=(mode != "off"), device="cpu"
                    )
                    mgr = TurboQuantKVCacheManager(
                        cfg, num_layers=1, num_heads=NH, head_dim=HD, device="cpu"
                    )
                    kv_nmse, attn_nmse, nbytes = run_case(mgr, k, v, q)
                    kv_m.append(kv_nmse)
                    at_m.append(attn_nmse)
                    by.append(nbytes)
                kvc.qjl_decode = orig_decode  # restore between modes
                results[(dist, bits, mode)] = (mean(kv_m), mean(at_m), mean(by))

    kvc.qjl_decode = orig_decode

    print(f"QJL ablation (hd={HD}, qjl_dim={HD}, {QUERY_POS} query pos, 3 seeds)")
    print(f"QJL estimator noise floor 1/d' = {1/HD:.4f}")
    print()
    for dist in DISTS:
        print(f"=== data distribution: {dist} ===")
        print(f"{'bits':>5} | {'off  kv/attn':>20} | {'shipped kv/attn':>20} | {'fixed kv/attn':>20} | {'winner':>8}")
        for bits in BITS:
            off_kv, off_at, _ = results[(dist, bits, "off")]
            sh_kv, sh_at, _ = results[(dist, bits, "shipped")]
            fx_kv, fx_at, _ = results[(dist, bits, "fixed")]
            # winner judged on attention fidelity (the metric that matters downstream)
            best = min([("off", off_at), ("shipped", sh_at), ("fixed", fx_at)], key=lambda t: t[1])[0]
            print(
                f"{bits:>5} | {off_kv:8.4f}/{off_at:8.4f} | {sh_kv:8.4f}/{sh_at:8.4f} | "
                f"{fx_kv:8.4f}/{fx_at:8.4f} | {best:>8}"
            )
        print()

    # Same-budget comparison: 3.5-bit + packed 1-bit QJL (~0.47 B/coord) vs
    # 4.0-bit PolarQuant only (~0.50 B/coord). If 4.0-off beats 3.5+QJL at
    # equal-or-smaller size, the bit is better spent on the codebook.
    print("=== same-budget comparison (normal) ===")
    sh35 = results[("normal", 3.5, "shipped")]
    off35 = results[("normal", 3.5, "off")]
    off40 = results[("normal", 4.0, "off")]
    q40 = results[("normal", 4.0, "shipped")]
    print(f"3.5 no QJL    : {off35[1]:.4f} attn NMSE @ {off35[2]:.0f} B")
    print(f"3.5+QJL(ship) : {sh35[1]:.4f} attn NMSE @ {sh35[2]:.0f} B")
    print(f"4.0 no QJL    : {off40[1]:.4f} attn NMSE @ {off40[2]:.0f} B")
    print(f"4.0+QJL(ship) : {q40[1]:.4f} attn NMSE @ {q40[2]:.0f} B")

    # Scaling sweep: is the tuned c=1/32 (16x the old shipped 1/d'^1.5 at
    # hd=64) near-optimal, or is a different c strictly better? decode = c.(codes @ P).
    print()
    print("=== QJL decode scaling sweep (3.5 bits, normal, 2 seeds) ===")
    k, v, q = make_data("normal", 0)
    for c in [1 / 2048, 1 / 1024, 1 / 512, 1 / 256, 1 / 128, 1 / 64, 1 / 32, 1 / 16, 1 / 8, 1 / 4]:
        tag = " <-- old shipped" if abs(c - 1 / 512) < 1e-12 else (" <-- tuned (shipped now)" if abs(c - 1 / 32) < 1e-12 else (" <-- textbook 1/sqrt(d')" if abs(c - 1 / 8) < 1e-12 else ""))
        acc = []
        for seed in SEEDS[:2]:
            k, v, q = make_data("normal", seed)
            kvc.qjl_decode = lambda codes, P, c=c: codes.to(torch.float32) @ P * c
            cfg = TurboQuantConfig(bits_per_coord=3.5, enable_qjl=True, device="cpu")
            mgr = TurboQuantKVCacheManager(cfg, num_layers=1, num_heads=NH, head_dim=HD, device="cpu")
            _, attn_nmse, _ = run_case(mgr, k, v, q)
            acc.append(attn_nmse)
            kvc.qjl_decode = orig_decode
        print(f"  c=1/{1 / c:>4.0f}: attn NMSE {mean(acc):.4f}{tag}")
    kvc.qjl_decode = orig_decode


if __name__ == "__main__":
    main()

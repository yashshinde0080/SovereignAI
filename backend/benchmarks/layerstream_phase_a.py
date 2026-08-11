"""Phase A benchmark: bounded LRU cache + deep prefetch on the real loader.

Simulates the LayerStream access pattern (sequential layer loads with
prefetch-ahead, exactly like ``LayerExecutor.execute_forward``) against a real
split model. Each config runs in a FRESH subprocess so RSS is not confounded
by the previous config's allocator retention.

  - cache: unlimited (pre-Phase-A behavior) vs bounded (Phase A)
  - prefetch depth: 1 (pre-Phase-A) vs 3 (Phase A)

Run:  python -m benchmarks.layerstream_phase_a [--model pythia-70m-deduped]
"""
import argparse
import gc
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil

_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))

from app.engines.layerstream.splitter import WeightSplitter

MODEL = "Qwen/Qwen2-0.5B"
CACHE_ROOT = Path(_BACKEND).parent / "workspace" / "offload_cache"

CONFIGS = [
    ("before: depth=1, unlimited", 1, None),
    ("after:  depth=3, bounded", 3, "budget"),
    ("after:  depth=3, unlimited", 3, None),
    ("after:  depth=1, bounded", 1, "budget"),
]


def _run_config(layer_paths, depth, budget_mb, passes=3):
    """Run one config IN-PROCESS and return JSON-serializable results."""
    gc.collect()
    from app.engines.layerstream.loader import LayerWeightLoader

    base_rss = psutil.Process().memory_info().rss
    loader = LayerWeightLoader(str(Path(layer_paths[0]).parent),
                               prefetch_depth=depth,
                               cache_budget_mb=budget_mb)
    times, peak = [], 0.0
    for _ in range(passes):
        t0 = time.perf_counter()
        for i, p in enumerate(layer_paths):
            for d in range(1, depth + 1):
                j = i + d
                if j < len(layer_paths):
                    loader.prefetch_async(layer_paths[j])
            loader.get_weights(p)
        times.append(time.perf_counter() - t0)
        peak = max(peak, psutil.Process().memory_info().rss)
    stats = loader.get_cache_stats()
    # Delta RSS over the baseline: what THIS loader added.
    return {
        "times": times,
        "rss_delta_mb": (peak - base_rss) / (1024 ** 2),
        "cached_mb": stats["cached_mb"],
        "budget_mb": stats["budget_mb"],
    }


def _split(out_dir: Path, model_id: str, quant: str):
    if not (out_dir / "layer_0.safetensors").exists():
        print(f"Splitting {model_id} ({quant}) -> {out_dir} (one-time)...", flush=True)
        os.makedirs(out_dir, exist_ok=True)
        import torch
        WeightSplitter(model_id, str(out_dir), quant_method=quant).split_and_save(torch.float16)


def run_suite(model_id: str, quant: str, args):
    suffix = {"int8": "-int8", "int4": "-int4"}.get(quant, "")
    out_dir = CACHE_ROOT / ("bench-" + model_id.replace("/", "-") + suffix)
    _split(out_dir, model_id, quant)

    layer_paths = sorted(
        (str(p) for p in out_dir.glob("layer_*.safetensors")),
        key=lambda s: int(s.split("layer_")[1].split(".")[0]),
    )
    n = len(layer_paths)
    largest_mb = max(os.path.getsize(p) for p in layer_paths) / (1024 ** 2)
    budget_mb = max(256.0, largest_mb * 4.5)  # reference budget

    print(f"model={model_id} quant={quant} layers={n} largest_layer={largest_mb:.1f}MB budget={budget_mb:.0f}MB",
          flush=True)

    # Each config in a fresh subprocess: clean RSS, cold-ish page cache.
    results = {}
    for label, depth, budget in CONFIGS:
        budget_arg = budget_mb if budget == "budget" else None
        code = (
            "import sys, json; sys.path.insert(0, %r); "
            "from benchmarks.layerstream_phase_a import _run_config; "
            "print(json.dumps(_run_config(%r, %r, %r)))" % (str(_BACKEND), layer_paths, depth, budget_arg)
        )
        try:
            out = subprocess.run([sys.executable, "-c", code],
                                 capture_output=True, text=True, timeout=600)
        except subprocess.TimeoutExpired:
            print(f"{label}: TIMEOUT", flush=True)
            continue
        if out.returncode != 0:
            print(f"{label}: FAILED\n{out.stderr[-800:]}", flush=True)
            continue
        results[label] = json.loads(out.stdout.strip().splitlines()[-1])
        r = results[label]
        print(f"{label:<34} pass1={r['times'][0]:6.2f}s pass3={r['times'][2]:6.2f}s "
              f"rss+{r['rss_delta_mb']:7.1f}MB cached={r['cached_mb']:7.1f}MB", flush=True)

    if args.json:
        print(json.dumps({"budget_mb": budget_mb, "results": results}, indent=2))
        return

    if "before: depth=1, unlimited" in results and "after:  depth=3, bounded" in results:
        b = results["before: depth=1, unlimited"]
        a = results["after:  depth=3, bounded"]
        print("\n=== before vs after (Phase A) ===")
        print(f"  steady-state pass3: {b['times'][2]:.2f}s -> {a['times'][2]:.2f}s")
        # cached_mb is the honest cache footprint; RSS delta is an allocator
        # high-water mark (torch/malloc don't return freed blocks to the OS).
        print(f"  loader cached: {b['cached_mb']:.0f}MB -> {a['cached_mb']:.0f}MB "
              f"({(a['cached_mb'] / max(b['cached_mb'], 0.1) - 1) * 100:+.0f}%)")
        print(f"  loader RSS delta (allocator high-water): {b['rss_delta_mb']:.0f}MB -> {a['rss_delta_mb']:.0f}MB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quant", default="none", choices=["none", "int8", "int4"])
    args = ap.parse_args()
    run_suite(args.model, args.quant, args)


if __name__ == "__main__":
    main()

"""LayerStream small-model benchmark (P1 / CEO item).

Measures real end-to-end t/s + peak RAM on an installed split model and prints
honest numbers — the first check of the "70B on 8GB" claim. Run from backend/:

    .venv/Scripts/python.exe benchmark_layerstream.py [model_dir]

Default model: workspace/offload_cache/bench-Qwen-Qwen2-0.5B-int4 (339 MB int4).
"""
import asyncio
import os
import sys
import time

from app.core.memory_manager import MemoryManager
from app.engines.layerstream.executor import LayerStreamEngine

DEFAULT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "workspace", "offload_cache", "bench-Qwen-Qwen2-0.5B-int4",
)
PROMPT = "The quick brown fox jumps over the lazy dog. "
MAX_TOKENS = 32


async def main(model_path: str) -> None:
    import psutil

    engine = LayerStreamEngine(model_path, {}, MemoryManager())
    t0 = time.perf_counter()
    await engine.load()
    load_s = time.perf_counter() - t0

    baseline_ram = psutil.Process().memory_info().rss / (1024**2)

    gen_t0 = time.perf_counter()
    tokens = 0
    async for chunk in engine.generate_stream(
        input_data=PROMPT, max_tokens=MAX_TOKENS, temperature=0.7, top_p=0.9
    ):
        if chunk.get("token"):
            tokens += 1
    gen_s = time.perf_counter() - gen_t0

    stats = engine.layer_executor.tracker.get_stats()
    peak_ram = max(stats["peak_ram_mb"], psutil.Process().memory_info().rss / (1024**2))

    print("\n=== LayerStream benchmark ===")
    print(f"model            : {os.path.basename(model_path)}")
    print(f"device           : {engine.device}")
    print(f"load time        : {load_s:.1f}s")
    print(f"generation       : {tokens} tokens in {gen_s:.2f}s")
    print(f"tokens/second    : {tokens / gen_s:.2f} tok/s")
    print(f"peak RAM         : {peak_ram / 1024:.2f} GB (baseline {baseline_ram / 1024:.2f} GB)")
    print(f"disk read time   : {stats['disk_read_time_total']:.2f}s "
          f"({stats['num_layer_loads']} layer loads, avg {stats['layer_load_time_avg']*1000:.0f} ms)")
    print(f"compute time     : {stats['compute_time']:.2f}s")
    print("note: single-user CPU box; tok/s is honest raw decode, not marketing.")

    await engine.unload()


if __name__ == "__main__":
    model = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    if not os.path.isdir(model):
        print(f"model dir not found: {model}", file=sys.stderr)
        sys.exit(1)
    asyncio.run(main(model))

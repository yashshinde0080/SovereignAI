"""FullRAM Q4 benchmark (office-hours 2026-08-16 / Approach A assignment).

Measures real end-to-end t/s + peak RAM for the FullRAM GGUF Q4 path — the
honest numbers for the "3-8B Q4 on 8GB RAM" pitch. Mirrors the LayerStream
benchmark (benchmark_layerstream.py) so the two engines are comparable:
same prompt, same 32 generated tokens.

Run from backend/:

    .venv/Scripts/python.exe benchmark_fullram.py [model_gguf] [--device cpu|cuda]

Default model: workspace/models/bench-qwen2.5-0.5b-q4/qwen2.5-0.5b-instruct-q4_k_m.gguf
Default device: cpu (the "runs in RAM" claim). Pass --device cuda for the
GPU path a user with this box's GPU would actually get.
"""
import argparse
import asyncio
import os
import sys
import threading
import time

import psutil

from app.core.memory_manager import MemoryManager
from app.engines.fullram.executor import FullRAMEngine

DEFAULT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "workspace", "models", "bench-qwen2.5-0.5b-q4", "qwen2.5-0.5b-instruct-q4_k_m.gguf",
)
PROMPT = "The quick brown fox jumps over the lazy dog. "
MAX_TOKENS = 32


async def main(model_path: str, device: str) -> None:
    engine = FullRAMEngine(model_path, {}, MemoryManager())
    if device == "cpu":
        engine.device = "cpu"  # override cuda-autodetect: this run measures the RAM claim

    # Peak-RSS sampler (Windows psutil peak_wset covers the whole process
    # history, including pre-load; sample instead so delta is honest).
    peak = {"mb": 0.0}
    stop = threading.Event()

    def _sampler():
        proc = psutil.Process()
        while not stop.is_set():
            try:
                peak["mb"] = max(peak["mb"], proc.memory_info().rss / (1024 ** 2))
            except Exception:
                pass
            time.sleep(0.05)

    baseline = psutil.Process().memory_info().rss / (1024 ** 2)
    sampler = threading.Thread(target=_sampler, daemon=True)
    sampler.start()

    t0 = time.perf_counter()
    await engine.load()
    load_s = time.perf_counter() - t0

    gen_t0 = time.perf_counter()
    tokens = 0
    async for chunk in engine.generate_stream(
        input_data=PROMPT, max_tokens=MAX_TOKENS, temperature=0.7, top_p=0.9
    ):
        if chunk.get("token"):
            tokens += 1
    gen_s = time.perf_counter() - gen_t0

    stop.set()
    sampler.join(timeout=2)
    peak_ram = max(peak["mb"], psutil.Process().memory_info().rss / (1024 ** 2))

    print("\n=== FullRAM Q4 benchmark ===")
    print(f"model            : {os.path.basename(model_path)}")
    print(f"device           : {engine.device}")
    print(f"load time        : {load_s:.1f}s")
    print(f"generation       : {tokens} tokens in {gen_s:.2f}s")
    print(f"tokens/second    : {tokens / gen_s:.2f} tok/s")
    print(f"peak RAM         : {peak_ram / 1024:.2f} GB (baseline {baseline / 1024:.2f} GB, "
          f"delta {(peak_ram - baseline) / 1024:.2f} GB)")
    note = ("cpu path: GGUF Q4 stays small on disk but transformers materializes "
            "fp32 weights in RAM, so peak RAM is ~4x the file size. "
            if engine.device == "cpu" else
            "cuda path: fp16 weights in VRAM; RAM stays low.")
    print(f"note              : {note}")
    print(f"LayerStream ref   : 0.40 tok/s (same prompt, 32 tokens, same box, Qwen3.5-0.8B)")

    await engine.unload()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("model", nargs="?", default=DEFAULT)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    args = parser.parse_args()
    if not os.path.exists(args.model):
        print(f"model not found: {args.model}", file=sys.stderr)
        sys.exit(1)
    asyncio.run(main(args.model, args.device))

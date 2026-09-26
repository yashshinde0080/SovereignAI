"""llama.cpp spike benchmark (office-hours 2026-08-16 / Approach B).

Validates the mechanism Approach B depends on: llama.cpp keeps GGUF Q4 weights
quantized in RAM (no fp32/fp16 materialization) and decodes with fused SIMD
kernels. Same prompt / token target as benchmark_fullram.py and
benchmark_layerstream.py so all three engines are comparable.

Run from backend/:

    .venv/Scripts/python.exe benchmark_llamacpp.py [model_gguf] [--gpu-layers N]

Default model: workspace/models/bench-qwen2.5-0.5b-q4/qwen2.5-0.5b-instruct-q4_k_m.gguf
"""
import argparse
import os
import sys
import threading
import time

import psutil

from llama_cpp import Llama

DEFAULT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "workspace", "models", "bench-qwen2.5-0.5b-q4", "qwen2.5-0.5b-instruct-q4_k_m.gguf",
)
PROMPT = "The quick brown fox jumps over the lazy dog. "
MAX_TOKENS = 32


def main(model_path: str, gpu_layers: int) -> None:
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
    llm = Llama(model_path=model_path, n_ctx=2048, n_gpu_layers=gpu_layers, verbose=False)
    load_s = time.perf_counter() - t0

    gen_t0 = time.perf_counter()
    res = llm(PROMPT, max_tokens=MAX_TOKENS, temperature=0.7, top_p=0.9, echo=False)
    gen_s = time.perf_counter() - gen_t0

    stop.set()
    sampler.join(timeout=2)
    peak_ram = max(peak["mb"], psutil.Process().memory_info().rss / (1024 ** 2))

    tokens = res.get("usage", {}).get("completion_tokens", 0)
    timings = res.get("timings", {})
    predicted_s = timings.get("predicted_per_second") or (tokens / gen_s if tokens else 0)

    print("\n=== llama.cpp spike benchmark ===")
    print(f"model            : {os.path.basename(model_path)}")
    print(f"n_gpu_layers     : {gpu_layers}")
    print(f"file size        : {os.path.getsize(model_path) / (1024 ** 2):.0f} MB on disk")
    print(f"load time        : {load_s:.1f}s")
    print(f"generation       : {tokens} tokens in {gen_s:.2f}s")
    print(f"tokens/second    : {tokens / gen_s:.2f} tok/s (llama.cpp reported {predicted_s:.2f})")
    print(f"peak RAM         : {peak_ram / 1024:.2f} GB (baseline {baseline / 1024:.2f} GB, "
          f"delta {(peak_ram - baseline) / 1024:.2f} GB)")
    print(f"RAM vs file size : {(peak_ram - baseline) / 1024 / (os.path.getsize(model_path) / (1024 ** 3)):.1f}x "
          f"(quantized residency: ~1x means weights stay Q4 in RAM)")
    print("FullRAM ref      : 3.84 tok/s CPU / 7.03 CUDA, 1.93 GB delta (fp32/fp16 dequant)")
    print("LayerStream ref  : 0.40 tok/s")

    del llm


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("model", nargs="?", default=DEFAULT)
    parser.add_argument("--gpu-layers", type=int, default=0)
    args = parser.parse_args()
    if not os.path.exists(args.model):
        print(f"model not found: {args.model}", file=sys.stderr)
        sys.exit(1)
    main(args.model, args.gpu_layers)

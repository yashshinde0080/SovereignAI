# FullRAM

A ==high-performance inference architecture== that loads the entire language model into VRAM or RAM for maximum tokens-per-second speed.

## Role in SovereignAI Edge

[[FullRAM]] is one of the two core execution engines in SovereignAI Edge's ==dual-engine architecture== (alongside [[LayerStream]]). It is automatically selected by the [[Hardware Profiler]] when available memory exceeds the model size by at least 20%.

## Key Characteristics

- **Speed:** Maximum throughput — all parameters in memory, no I/O wait
- **Memory:** Requires 16GB+ RAM or 8GB+ VRAM depending on model size
- **Precision:** FP16 on CUDA, FP32 on CPU
- **Pipeline:** Standard Hugging Face `transformers` `model.generate()` pipeline

## Memory Formula

$$V_{full} \\approx S_{model} + (2 \\times L_{ctx} \\times N_{layers} \\times D_{hidden} \\times B_{p})$$

Where $S_{model}$ is model size and $L_{ctx}$ is context length.

## See Also

- [[LayerStream]] — Low-memory alternative engine
- [[Engines Overview]] — FullRAM vs LayerStream deep-dive
- [[Engine Algorithms]] — Pseudocode for FullRAM execution
- [[Hardware Profiler]] — Engine selection logic

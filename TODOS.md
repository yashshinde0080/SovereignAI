# Remaining TurboQuant tasks

See [`reviews/autoplan-report-2026-08-09.md`](reviews/autoplan-report-2026-08-09.md) for the full status.

- **P3 — CLI honesty**: benchmark-turboquant still uses synthetic data only (estimated ratio is now labeled as synthetic; real model gate needed)
- **P3 — TODOS.md**: this file
- **Future**: ≥1B model gate test (TinyLlama-1.1B), per-vector codebook exploration (spherical VQ / product quantization)
- ~~Reference-codebook comparison~~ — ✅ DONE 2026-08-11 (`benchmarks/reference_polar_probe.py`): ref PolarQuant 5x better than our polar (0.028 vs 0.143 K at 3-bit) but ≈ our failing affine regime (0.0087 @ 4-bit vs affine 0.0050); codebook swap alone cannot pass the gate
- ~~llama.cpp tbq3_0/tbq4_0 evaluation~~ — ✅ done 2026-08-11, see Phase 4 section in the report
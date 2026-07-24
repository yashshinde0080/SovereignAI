---
tags: [research, literature-review, edge-ai, quantization, inference]
created: 2026-07-24
updated: 2026-07-24
---

# Literature Review: Edge AI Inference & LLM Serving

Research papers relevant to SovereignAI Edge. Published 2022-2026. High-impact venues only (MLSys, NeurIPS, ICML, SOSP, ICLR).

## Overview

| Paper | Component | Benefit |
|-------|-----------|---------|
| AWQ | FullRAM Engine | 4-bit quantization, 3× speedup |
| FlashAttention | Both Engines | Longer contexts, less memory |
| PagedAttention | KV Cache / Scheduler | Near-zero cache waste |
| Speculative Decoding | LayerStream Engine | Mask layer-load latency |
| QLoRA | Future on-device FT | Fine-tune on edge hardware |
| RAG Survey | Vector Store | Retrieval pipeline guide |

---

## 1. AWQ: Activation-aware Weight Quantization

Lin et al., MLSys 2024 (Best Paper). [arXiv:2306.00978](https://arxiv.org/abs/2306.00978)

Only ~1% weight channels need protection during quantization. AWQ identify salient channels via activation distribution (not weight magnitude). Apply equivalent scaling — no backprop, no reconstruction. TinyChat achieve 3× speedup over HF FP16 on desktop/mobile GPUs.

**Apply:** Quantize models to 4-bit for FullRAM engine. Run bigger models at same RAM budget.

---

## 2. FlashAttention: IO-Aware Exact Attention

Dao et al., NeurIPS 2022. [arXiv:2205.14135](https://arxiv.org/abs/2205.14135)

Tile attention computation to minimize GPU HBM ↔ SRAM traffic. Exact attention, 3× GPT-2 speedup at 1K seqlen. Enable 64K token contexts (Path-256).

**Apply:** Reduce per-layer memory in LayerStream. Extend context window in FullRAM. v2/v3 give further gains.

---

## 3. PagedAttention: OS-Style KV Cache Management

Kwon et al., SOSP 2023. [arXiv:2309.06180](https://arxiv.org/abs/2309.06180)

Virtual memory paging for KV cache. Near-zero waste. vLLM achieve 2-4× throughput over FasterTransformer/Orca. Native KV cache sharing for parallel sampling / beam search.

**Apply:** Adopt paging allocator in KV cache manager. Reduce fragmentation on edge RAM. Use continuous batching pattern in scheduler.

---

## 4. Speculative Decoding: Lossless 2-3× Acceleration

Leviathan et al., ICML 2023 (Oral). [arXiv:2211.17192](https://arxiv.org/abs/2211.17192)

Small draft model generate candidates. Large model verify in parallel. Identical output distribution. No retraining needed.

**Apply:** Pair with LayerStream. Draft model (1-2B quantized) speculate tokens while target model stream layers. Mask disk-load latency.

---

## 5. QLoRA: 4-bit Fine-Tuning on a Single GPU

Dettmers et al., NeurIPS 2023. [arXiv:2305.14314](https://arxiv.org/abs/2305.14314)

NF4 data type + LoRA adapters + double quantization + paged optimizers. Fine-tune 65B model on single 48GB GPU. Match full 16-bit quality. Guanaco-65B reach 99.3% ChatGPT performance in 24h single-GPU training.

**Apply:** Enable on-device personalization. NF4 as alternative quantization format for FullRAM.

---

## 6. RAG for LLMs: Comprehensive Survey

Gao et al., 2024. [arXiv:2312.10997](https://arxiv.org/abs/2312.10997)

Taxonomy: Naive RAG → Advanced RAG (iterative retrieval, rewriting) → Modular RAG (pluggable components). Cover chunking, embedding, retrieval, evaluation.

**Apply:** Guide chunker/embedding/retriever improvements in vectorstore. Modular RAG align with plugin architecture.

---

## Related

- [[Project SovereignAI Edge]]
- [[FullRAM Engine]]
- [[LayerStream Engine]]
- [[Engine Algorithms]]

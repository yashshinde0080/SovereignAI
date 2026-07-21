---
tags: [format, model, quantization, gguf]
source: "[[Docs/GGUF.md]]"
created: 2026-07-21
updated: 2026-07-21
---

# GGUF

GGUF (GPT-Generated Unified Format) is a file format for storing quantized large language model weights, developed as an evolution of GGML. It is the native model format supported by SovereignAI Edge, consumed by both inference engines.

## Role in SovereignAI Edge

All inference engines operate on `.gguf` files. The FullRAM engine memory-maps the GGUF file directly into RAM for fast inference. The LayerStream engine reads individual layers from the GGUF structure sequentially. Header parsing extracts model metadata such as size, architecture, tokenizer configuration, and quantization level.

## Key Characteristics

GGUF is self-contained, bundling tokenizer, model weights, and metadata into a single file. It is cross-platform compatible across Windows, macOS, and Linux. It supports various quantization levels including Q4_0, Q5_K_M, Q8_0, and others, enabling trade-offs between model quality and memory footprint.

## Key Points

- Native model format for all SovereignAI Edge inference
- Self-contained: weights, tokenizer, and metadata in one file
- Cross-platform portability
- Multiple quantization levels for memory/accuracy trade-offs
- FullRAM memory-maps GGUF directly into RAM; LayerStream reads layer by layer

## Related

- [[FullRAM]] — Memory-maps GGUF files into RAM for monolithic inference
- [[LayerStream]] — Reads GGUF layers sequentially for memory-bounded inference
- [[Engines Overview]] — How both engines consume GGUF model files
- [[Hugging Face]] — Source of pre-trained models converted to GGUF

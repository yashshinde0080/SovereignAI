# GGUF

A file format for storing quantized large language model weights, developed as an evolution of GGML. It stands for "GPT-Generated Unified Format."

## Role in SovereignAI Edge

[[GGUF]] is the ==native model format== supported by SovereignAI Edge. All inference engines operate on `.gguf` files:

- **FullRAM Engine:** Memory-maps the GGUF file directly into RAM for fast inference
- **LayerStream Engine:** Reads individual layers from the GGUF structure sequentially
- **Header Parsing:** Extracts model metadata (size, architecture, tokenizer) from the GGUF header

## Key Characteristics

- **Self-contained:** Includes tokenizer, model weights, and metadata in a single file
- **Portable:** Cross-platform compatible (Windows, macOS, Linux)
- **Quantization:** Supports various quantization levels (Q4_0, Q5_K_M, Q8_0, etc.)

## See Also

- [[Engines Overview]] — FullRAM and LayerStream architecture
- [[Technical Architecture]] — System component interactions
- [[Hugging Face]] — Source of pre-trained models

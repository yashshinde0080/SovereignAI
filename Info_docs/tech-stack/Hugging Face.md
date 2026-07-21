---
tags: [ml, models, huggingface, external]
source: "[[Docs/Hugging Face.md]]"
created: 2026-07-21
updated: 2026-07-21
---

# Hugging Face

Hugging Face provides the core ML infrastructure that SovereignAI Edge builds upon. The `transformers` library supplies `AutoTokenizer` for text-to-tensor conversion, `AutoModelForCausalLM` for model loading and inference (used by the FullRAM engine), and `AutoConfig` for meta-scaffolding and weight splitting (used by the LayerStream engine). `TextIteratorStreamer` enables real-time token generation for the streaming response pattern.

The Hugging Face model hub gives access to thousands of pre-trained models (Llama, Mistral, Gemma, and others), which SovereignAI Edge converts to GGUF format for optimized deployment. Both engines depend on Hugging Face components: FullRAM loads models via `from_pretrained()`, while LayerStream uses the configuration and tokenizer infrastructure to prepare models for sharded execution.

## Key Points

- `AutoTokenizer` for text-to-tensor conversion in both engines
- `AutoModelForCausalLM` for FullRAM model loading and inference
- `AutoConfig` for LayerStream meta-scaffolding and weight splitting
- `TextIteratorStreamer` for real-time streaming token generation
- Model hub provides access to Llama, Mistral, Gemma, and thousands of other models

## Related
- [[Engines Overview]]
- [[Engine Algorithms]]
- [[GGUF]]
- [[Technical Architecture]]

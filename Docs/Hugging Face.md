# Hugging Face

A leading platform and community for machine learning, providing the `transformers` library and model hub.

## Role in SovereignAI Edge

[[Hugging Face]] provides the ==core ML infrastructure== that SovereignAI Edge builds upon:

- **Transformers Library:** `AutoTokenizer`, `AutoModelForCausalLM` for model loading and inference
- **Model Architecture:** Access to thousands of pre-trained models (Llama, Mistral, Gemma)
- **Tokenizers:** `AutoTokenizer` for text-to-tensor conversion
- **Streaming:** `TextIteratorStreamer` for real-time token generation

## Usage in Engines

- **FullRAM Engine:** Loads entire model via `AutoModelForCausalLM.from_pretrained()`
- **LayerStream Engine:** Uses `AutoConfig` for meta-scaffolding and weight splitting

## See Also

- [[Engines Overview]] — FullRAM and LayerStream architecture
- [[Engine Algorithms]] — Pseudocode for both engines
- [[GGUF]] — Model format for optimized deployment

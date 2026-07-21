# Data & Execution Pipelines

## 1. Overview
Pipelines define the rigid step-by-step transformations data undergoes from the moment a user types a prompt until the generated text appears on the screen. SovereignAI Edge utilizes strict, synchronous pipelines for data safety, transitioning to asynchronous streams for client delivery.

## 2. The Comprehensive Inference Pipeline

### Phase 1: Ingestion & Validation
1. **Payload Reception:** The backend receives a JSON payload `{ "messages": [...], "model": "llama-3-8b", "temperature": 0.7 }`.
2. **Sanitization:** [[Pydantic]] models strip invalid keys and enforce bounds (e.g., temp between 0.0 and 2.0).

### Phase 2: Pre-Processing & Context Formatting
1. **Plugin Injection:** Pre-prompt plugins execute here. (e.g., If a local ==RAG== plugin is active, it queries a local vector DB and injects the context directly into the prompt transparently).
2. **Templating:** The raw messages are converted into the specific prompt-template required by the selected model (e.g., ChatML, Llama-3-Instruct formats).
3. **==Tokenization==:** Text is converted to specific integer token IDs using the embedded vocabulary.

### Phase 3: Hardware Routing & Execution
1. **Engine Check:** Model size vs available memory is evaluated.
2. **K/V Cache Setup:** The ==KV Cache== is initialized for the session to prevent recalculating past tokens.
3. **Forward Pass Loop:**
   - **==FullRAM==:** CPU/GPU blasts the input through the weights loaded in RAM.
   - **==LayerStream==:** CPU reads Layer 1 from disk, computes, unloads, reads Layer 2, computes...
4. **Logit Sampling:** The output probabilities are sampled based on ==Temperature==, Top-K, and ==Top-P== to pick the next token.

### Phase 4: Output Streaming & Post-Processing
1. **Detokenization:** The generated integer token is converted back to a string chunk.
2. **Yielding:** The string is yielded to a WebSocket or ==SSE (Server-Sent Events)== stream.
3. **Completion:** Upon reaching the End-Of-Sequence (EOS) token, metrics (tokens/sec) are calculated, saved to the database, and the stream is closed.

## 3. Pipeline Visualization
```text
  [ User Types Prompt ]
           |
           v
+------------------------+      +---------------------------+
| 1. Ingestion Endpoint  | ---> | JSON Schema Validation    |
+------------------------+      +---------------------------+
                                            |
+------------------------+      +-----------v---------------+
| 2. Pre-Processing      |      | Plugin Manager (Hooks:    |
|    Formatting          | <--- | RAG, Formatting, Safety)  |
+------------------------+      +---------------------------+
           |
+----------v-------------+      +---------------------------+
| 3. Tokenizer Module    | ---> | Checks Context Limit      |
+------------------------+      +---------------------------+
           |
+----------v-------------+
| 4. Hardware Router     | ---> [ FullRAM or LayerStream? ]
+------------------------+
           |
+----------v-------------+      +---------------------------+
| 5. Autoregressive Loop | <--- | LLM Inference Core        |
|    (Generate 1 Token)  | ---> | (Sampling: Temp, Top-P)   |
+------------------------+      +---------------------------+
           |
+----------v-------------+      +---------------------------+
| 6. Detokenizer & Post  | ---> | Websocket Stream Emission |
|    Processing          | <--- | (Client updates UI)       |
+------------------------+      +---------------------------+
           |
  [ End of Sequence (EOS) ]
```

## See Also
- [[Working Flow]] — Boot sequence and session lifecycle
- [[Engine Algorithms]] — Pseudocode for FullRAM and LayerStream
- [[Implemented Algorithms]] — 25 algorithms across the platform
- [[Schedulers]] — Task queue and worker pool management

# SovereignAI Execution Engines Architecture

This documentation provides a deep-dive, technical analysis of the execution engines utilized in the SovereignAI backend: ==FullRAM Engine== and ==LayerStream Engine==. It details their internal mechanics, class structures, memory management strategies, generation pipelines, and hardware implications.

---

## 1. FullRAM Engine (`engines/fullram`)

The **FullRAM** mechanism (`FullRAMEngine`) serves as the core monolithic inference pipeline. It represents the standard paradigm for loading and executing Large Language Models (LLMs) via the [[Hugging Face]] `transformers` ecosystem. It relies on having sufficient memory (RAM or VRAM) to hold the entire model architecture simultaneously.

### 1.1 Core Architecture

The `FullRAMEngine` class inherits from `BaseEngine` and manages the lifecycle of the model seamlessly.

**Key Components:**
- **==Tokenizer==:** `AutoTokenizer` responsible for translating text prompts into tensor representations (`input_ids`).
- **Model Framework:** `AutoModelForCausalLM` which contains the full transformer stack.
- **Hardware Mapping:** Automatically utilizes `accelerate` backend (`device_map="auto"`) to push tensors to CUDA if available, falling back to CPU matrices if not.

### 1.2 Memory Lifecycle

#### Loading Phase (`async def load`)
When the `load()` function is invoked:
1. The engine checks the hardware target. If `"cuda"` is detected, it configures model loading arguments to use `torch.float16` precision and maps layers strictly.
2. If `"cpu"` is targeted, it utilizes `torch.float32`.
3. The entirety of the `.safetensors` or `.bin` files are loaded directly into active memory.
4. **Implication:** The system experiences an immediate physical memory spike corresponding to the size of the model weights.

#### Unloading Phase (`async def unload`)
To prevent memory leaks during context switching:
1. Variables referencing the model and tokenizer are explicitly deleted (`del self.model`).
2. CUDA caches are forcefully emptied (`torch.cuda.empty_cache()`) to reclaim VRAM.

### 1.3 Inference Pipeline

The engine supports two inference modes:

**Standard Generation (`generate`):**
- Utilizes the monolithic `self.model.generate()` method.
- Because `generate()` is computationally blocking, it is wrapped in an `asyncio.to_thread(_generate)` executor. This prevents the primary Python event loop from freezing, maintaining API responsiveness.
- Returns a complete tokenized output upon full sequence completion.

**Streaming Generation (`generate_stream`):**
- Implements `TextIteratorStreamer` from the [[Hugging Face]] library.
- The generation loop is pushed to a background `Threading.Thread`.
- Tokens are yielded asynchronously to the caller the moment they are decoded from the model, providing real-time text visualization.

### 1.4 Visual Architecture: FullRAM Flow
```mermaid
graph TD
    Source[HuggingFace / Local Model] -->|Direct Load| ActiveMem["Active VRAM / RAM"]
    
    subgraph ActiveMem ["Active System Memory"]
        Embed[Embeddings Layer]
        Layers[Layers 1...N]
        Head[Norm & Head]
    end
    
    ActiveMem --> Pass[Execute Forward Pass]
    Pass --> OutMode{Select Mode}
    OutMode --> Standard[Standard Generation (Blocking)]
    OutMode --> Stream[Streaming Generation (Iterative)]
```

---

## 2. LayerStream Engine (`engines/layerstream`)

The **LayerStream** Engine (`LayerStreamEngine`) represents a true ==memory-bounded inference== architecture. It dynamically circumvents Out-of-Memory (OOM) errors by decoupling the computation pipeline, streaming layers from disk storage sequentially instead of mapping the entire graph into active RAM.

### 2.1 Core Architecture

Unlike FullRAM's monolithic design, LayerStream orchestrates a complex suite of sub-components:

- **==WeightSplitter==:** Pre-processes models by chunking monolithic weight files into discrete, layer-by-layer `.safetensors` parts mapped to physical disk.
- **==Empty Scaffolding==:** Utilizes `accelerate.init_empty_weights()` to construct the logical `AutoConfig` framework of the model without allocating memory for its weights.
- **ModelIntrospector:** Scans the empty scaffold to identify component blocks (embedding layers, attention layers, MLP blocks, final norm).
- **LayerExecutor:** Handles the heavy lifting—loading a single tensor layer into memory, passing the hidden states through it, and immediately flushing the layer from memory.

### 2.2 Memory Lifecycle and Pre-Processing

#### Setup and Splitting (`async def load`)
1. **Cache Resolution:** Determines if the requested model has been previously chunked. It maps to an `offload_cache` directory.
2. **Dynamic Splitting:** If chunks are absent, `WeightSplitter` dynamically loads the monolithic model (usually onto CPU to prevent VRAM overflow) and slices it per attention/MLP block, saving them as independent files.
3. **Scaffold Integration:** The model frame is built, and `LayerExecutor` is instantiated. Only the meta-architecture resides in RAM at this point.

#### Unloading Phase (`async def unload`)
Aggressive garbage collection is required here.
1. The `LayerExecutor`'s loader explicitly clears its LRU cache (`clear_cache()`).
2. The Key-Value Key/Value cache (`kv_manager`) is flushed to ensure past sequence states are destroyed.
3. Explicit `gc.collect()` and `torch.cuda.empty_cache()` are invoked to scrub residual tensor allocations.

### 2.3 The Two-Phase Computation Pipeline

Inference strictly bypasses HuggingFace's `generate()` method, instead building a custom computation loop driven by `execute_forward()` and a custom `Sampler`.

#### Phase 1: Context Prefill
- When a prompt is ingested, the engine must process the entire sequence to generate internal hidden states.
- It iterates through the disk cache, pulling Layer 1 into memory, passing the prompt tokens, saving the state, unloading Layer 1, loading Layer 2, etc.
- **Goal:** Establishes the initial logits and ==KV Cache== blocks.

#### Phase 2: Decoded Token Generation
- Armed with the final state of the prefill, the engine decodes the first token.
- For each subsequent required token, the engine passes the singular new token through the layers sequentially.
- Uses `Sampler.sample()` (with ==temperature== and ==top-p== tuning) to predict the next word.
- Loop terminates when `eos_token_id` is reached or `max_tokens` is hit.

### 2.4 Visual Architecture: LayerStream Flow
```mermaid
graph TD
    HF[HuggingFace / Local Model] -->|One-time| Split[WeightSplitter]
    Split -->|Discrete .safetensors| SSD[Disk Cache / SSD]
    
    subgraph RAM ["System RAM"]
        Meta[Metascaffolding / Config]
        KV[KV Manager / Cache]
        Exec[LayerExecutor Controller]
    end
    
    SSD <-->|Sequential IO Streaming| Exec
    Exec -->|Hidden States| Forward[Execute Layer Step]
    Forward -->|State State| KV
    Forward -->|Last Token| Sampler[Sampler (Logits)]
```

---

## 3. Comparative Summary & Trade-offs

| Feature | FullRAM (`FullRAMEngine`) | LayerStream (`LayerStreamEngine`) |
| :--- | :--- | :--- |
| **Primary Goal** | Maximum Inference Speed | Absolute Memory Efficiency (Run huge models on low RAM) |
| **Generation Speed** | Extremely High (All params in memory) | Moderate (Bottlenecked by PCIe/Memory Bandwidth) |
| **Memory Footprint** | Massive (Size of model + K/V bounds) | Minimal (Size of maximum single layer + RAM overhead) |
| **Pre-Processing** | None (Direct loading) | High (Requires one-time disk chunking via `WeightSplitter`) |
| **Mechanism** | Standard `transformers` generation | Custom decoupling, CPU KV state, independent `Sampler` |
| **Inference Math** | $TPS = \frac{TFLOPS}{FLOPs_{per\_token}}$ | $TPS \approx \frac{BW_{pcie}}{ModelSize}$ |
| **Best Hardware** | Multi-GPU setups, High RAM systems | Consumer GPUs, Laptops, Low VRAM systems |

---

## 4. Theoretical Performance Models

To optimize deployment, the following mathematical relationships should be used to estimate hardware requirements.

### 4.1 Memory Bound Estimations

1. **VRAM Savings Factor ($F_{vram}$)**:
   $$F_{vram} = \frac{V_{full}}{V_{layer}} \approx \frac{S_{model}}{\frac{S_{model}}{N_{layers}}} = N_{layers}$$
   *Interpretation:* On a model with 32 layers, LayerStream can effectively reduce VRAM requirements by $\approx 30\text{x}$.

2. **KV Cache Overhead**:
   As context length ($L_{ctx}$) grows, the KV Cache size increases linearly.
   $$\Delta KV \approx 4 \times L_{ctx} \times N_{layers} \times D_{hidden} \times (\text{Precision\_Bytes})$$
   In LayerStream, this growth is absorbed by System RAM ($V_{ram}$), preventing VRAM-based execution failure.

### 4.2 Throughput Limits

The generation throughput (Tokens Per Second) is bounded by different architectural bottlenecks:

* **FullRAM (Compute Bound):**
  $$TPS_{full} = \frac{TFLOPS_{gpu}}{2 \times S_{model}}$$
* **LayerStream (I/O & Bandwidth Bound):**
  $$TPS_{layer} = \frac{BW_{pcie}}{S_{model}}$$

*Example:* A 14GB model (7B) on a PCIe Gen3 x16 (16GB/s) slot:
$$TPS_{layer} \approx \frac{16\text{GB/s}}{14\text{GB}} \approx 1.14 \text{ tokens/sec}$$

---

## 5. Code Extensibility

To extend these engines, developers must implement the `BaseEngine` interface. 
- Ensure that `load()`, `unload()`, `generate()`, and `generate_stream()` are appropriately overridden.
- Engine memory footprint tracking MUST be reported via `get_memory_usage()` returning a dictionary format parsing active internal buffers (or `psutil` values).

## See Also
- [[Engine Algorithms]] — Pseudocode and math for both engines
- [[Algorithms]] — Adaptive memory and LayerStream algorithms
- [[Technical Architecture]] — System component interactions
# SovereignAI Engine Algorithms
This document breaks down the procedural and computational algorithms driving the ==FullRAM== and ==LayerStream== engines.

---

## 1. FullRAM Execution Algorithm

The FullRAM engine utilizes a straightforward, monolithic approach. It relies on the standard autoregressive generation algorithm provided natively by [[Hugging Face]] `transformers`.

### Phase 1: Initialization
```pascal
Procedure Initialize_FullRAM(model_path, device):
    // 1. Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    
    // 2. Map constraints and load entire model into memory natively
    model = AutoModelForCausalLM.from_pretrained(model_path, device_map=device)
    
    Return model, tokenizer
```

### Phase 2: Generation Loop
```pascal
Procedure Generate_FullRAM(prompt, max_tokens):
    // 1. Tokenization
    input_ids = tokenizer.encode(prompt)
    
    // 2. Monolithic Forward Pass & Sampling handled internally
    output_ids = model.generate(
        input_ids=input_ids,
        max_new_tokens=max_tokens,
        do_sample=True
    )
    
    // 3. Decode
    return tokenizer.decode(output_ids)
```

---

## 2. LayerStream Execution Algorithm

The LayerStream engine is a highly customized inference pipeline designed to execute Large Language Models on severely ==hardware-constrained== systems. It involves a four-phase algorithmic process to sequentially stream tensor data.

### Phase 0: Weight Splitting (Pre-processing)
Before inference can happen, the monolithic model must be chunked.
```pascal
Procedure Split_Weights(model_path, offload_dir):
    If offload_dir is fully populated:
        Return  // already split
        
    // 1. Load model to CPU (prevent VRAM crash)
    model = Load_Model_To_RAM(model_path)
    
    // 2. Extract and save components sequentially
    Save_To_Disk(model.embeddings, offload_dir + "/embed.safetensors")
    
    For layer_index = 0 to N_Layers:
        layer_weights = model.layers[layer_index]
        Save_To_Disk(layer_weights, offload_dir + "/layer_" + layer_index + ".safetensors")
    
    Save_To_Disk(model.norm, offload_dir + "/norm.safetensors")
    Save_To_Disk(model.lm_head, offload_dir + "/lm_head.safetensors")
    
    Clear_RAM()
```

### Phase 1: Meta-Scaffolding
Load the architecture of the model without consuming memory for its weights.
```pascal
Procedure Build_Scaffold(offload_dir):
    // 1. Initialize configuration
    config = AutoConfig.from_pretrained(offload_dir)
    
    // 2. Build empty architecture
    With Init_Empty_Weights():
        model = AutoModelForCausalLM.from_config(config)
        
    // 3. Initialize Executors
    kv_manager = Initialize_KV_Cache()
    executor = Initialize_Layer_Executor(model, offload_dir, kv_manager)
    
    Return executor
```

### Phase 2: Context Prefill
This phase processes the initial prompt block to generate the starting hidden states and compute the first token.
```pascal
Procedure Context_Prefill(input_ids, executor):
    // 1. Embedding Forward Pass
    load_weights(executor, "embed")
    hidden_states = compute_embeddings(input_ids)
    unload_weights(executor, "embed")
    
    // 2. Sequential Layer Forward Pass
    For layer_index = 0 to N_Layers:
        // Load target layer from Disk -> RAM -> VRAM
        load_weights(executor, layer_index)
        
        // Execute math
        hidden_states, layer_kv = compute_layer(hidden_states, current_weights)
        
        // Store the sequence KV states for this layer specifically
        executor.kv_manager.store(layer_index, layer_kv)
        
        // Flush memory immediately
        unload_weights(executor, layer_index)
        force_garbage_collection()
        
    // 3. Final Norm and Head processing
    load_weights(executor, "norm_and_head")
    logits = compute_logits(hidden_states)
    unload_weights(executor, "norm_and_head")
    
    // 4. Sample the very first generated token
    next_token = Sampler.sample(logits)
    Return next_token
```

### Phase 3: Token Decoding (Autoregressive Loop)
Once the prefill is established, the engine must generate tokens one by one. It streams the model layers repeatedly for each single token.
```pascal
Procedure Decode_Loop(first_token, max_tokens, executor):
    current_token = first_token
    generated_tokens = [current_token]
    
    While sequence_length < max_tokens AND current_token != EOS_TOKEN:
        
        // 1. Embed singular current_token
        load_weights(executor, "embed")
        hidden_states = compute_embeddings(current_token)
        unload_weights(executor, "embed")
        
        // 2. Sequential Layer Pass (With KV Cache)
        For layer_index = 0 to N_Layers:
            load_weights(executor, layer_index)
            
            // Retrieve past sequence data up to this point
            past_kv = executor.kv_manager.retrieve(layer_index)
            
            // Execute math using historical states
            hidden_states, new_kv = compute_layer(hidden_states, past_kv)
            
            // Update the sequence memory
            executor.kv_manager.update(layer_index, new_kv)
            
            unload_weights(executor, layer_index)
            
        // 3. Final processing and prediction
        load_weights(executor, "norm_and_head")
        logits = compute_logits(hidden_states)
        unload_weights(executor, "norm_and_head")
        
        // 4. Sample and Append
        current_token = Sampler.sample(logits)
        generated_tokens.append(current_token)
        
    Return generated_tokens
```

---

## 3. Mathematical Framework: Metrics & Constraints

To objectively evaluate engine performance, we utilize the following mathematical models to predict ==memory footprint== and latency.

### 3.1 VRAM Occupancy ($V_{vram}$)

Let:
- $S_{model}$ = Total size of model weights in bytes (e.g., 14GB for a 7B FP16 model).
- $N_{layers}$ = Number of transformer layers.
- $L_{ctx}$ = Current context length (tokens).
- $D_{hidden}$ = Hidden dimension size.
- $B_{p}$ = Bytes per parameter (2 for FP16/BF16, 4 for FP32).

#### FullRAM VRAM:
$$V_{full} \approx S_{model} + (2 \times L_{ctx} \times N_{layers} \times D_{hidden} \times B_{p})$$
*Constraint: $V_{full} < GPU_{total\_vram}$*

#### LayerStream VRAM:
$$V_{layer} \approx \frac{S_{model}}{N_{layers}} + \text{Padding\_Buffers}$$
*Note: [[KV Cache]] in LayerStream is offloaded to System RAM, keeping VRAM footprint nearly constant regardless of context length.*

### 3.2 System RAM Occupancy ($V_{ram}$)

#### FullRAM RAM:
$$V_{ram} \approx \text{OS Overhead} \text{ (Weights are already in VRAM)}$$

#### LayerStream RAM:
$$V_{ram} \approx S_{model} + (2 \times L_{ctx} \times N_{layers} \times D_{hidden} \times B_{p})$$
*The entire weights and the total KV Cache reside in system memory to minimize Disk I/O.*

### 3.3 Inference Latency ($T_{inference}$)

Total time for one token generation step:

#### FullRAM Latency:
$$T_{full} = T_{compute} \approx \frac{FLOPs_{per\_token}}{TFLOPS_{gpu}}$$

#### LayerStream Latency:
$$T_{layer} = \sum_{i=1}^{N_{layers}} (T_{move\_i} + T_{compute\_i})$$
Since weights are moved from RAM to VRAM:
$$T_{move} \approx \frac{S_{model}}{BW_{pcie}}$$
*Where $BW_{pcie}$ is the PCIe bandwidth (e.g., 15.75 GB/s for Gen3 x16).*

**Conclusion**: LayerStream is constrained by ==Memory Bandwidth== (RAM to VRAM), while FullRAM is constrained by ==Compute Power== (TFLOPS).

---

## Performance Summary: The Algorithmic Bottleneck

The fundamental difference between these two algorithms dictates their hardware dependencies:

1. **FullRAM** executes Phase 2 and 3 entirely within VRAM. The GPU performs thousands of mathematical operations per second without ever waiting.
2. **LayerStream** inserts an `I/O Wait` (Loading weights from disk to RAM, and moving them from RAM to VRAM) inside the core *For* loop of **both** Phase 2 and Phase 3. 

If a model has 32 layers, and the user requests 100 tokens, the LayerStream Algorithm must perform **3,200 separate file reads** from the disk drive during Phase 3 (if not cached). This transforms the inference bottleneck from ==Math Compute Speed== (GPU TFLOPS) into ==Storage I/O Speed== (SSD Read MB/s).

## See Also
- [[Engines Overview]] — FullRAM and LayerStream architecture deep-dive
- [[Algorithms]] — Adaptive memory allocation and engine selection
- [[Implemented Algorithms]] — 25 algorithms across SovereignAI
- [[Pipelines]] — End-to-end inference pipeline
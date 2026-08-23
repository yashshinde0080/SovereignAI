# Weight Splitting & Quantization

Weight splitting converts a full model checkpoint into per-layer `.safetensors` files for LayerStream's layer-by-layer inference.

## Split Process

`WeightSplitter.split_and_save()` (`backend/app/engines/layerstream/splitter.py`):

```
Input: model directory (config.json, model weights, tokenizer)
Output: workspace/offload_cache/{model_name}/
  ├── embed.safetensors        # Token + position embeddings
  ├── layer_0.safetensors      # Transformer block 0
  ├── layer_1.safetensors      # Transformer block 1
  ├── ...
  ├── layer_N.safetensors      # Transformer block N
  ├── norm.safetensors         # Final layer norm
  ├── lm_head.safetensors      # Language model head
  ├── quant_config.json        # Quantization metadata
  ├── config.json              # Model config (copied)
  ├── tokenizer.json           # Tokenizer (copied)
  └── tokenizer_config.json    # Tokenizer config (copied)
```

### Steps

1. **RAM preflight** — check `available_ram >= model_size * 2`
2. **Load full model** — `AutoModelForCausalLM.from_pretrained(device_map="cpu", dtype=float16)`
3. **Detect components** — `ModelIntrospector.detect_model_components(model)` → `{embed, layers, norm, lm_head}`
4. **Save components** — each `.safetensors` via `safetensors.torch.save_file()`
5. **Copy config + tokenizer** files
6. **Delete model** from RAM (`del model; gc.collect()`)

## Quantization Methods

### none (fp16 default)
Weights stored as-is (float16). No compression.

### int8 (Per-Tensor Symmetric)

```python
scale = tensor.abs().max() / 127.0
quantized = round(tensor / scale).clamp(-128, 127).to(int8)
```

Stored: `{name}.int8` (int8 tensor) + `{name}.scale` (float32 scalar, shape [1])

Dequantization on device:
```python
result = tensor.to(device, dtype) * scale.to(device, dtype)
```

### int4 (Group-wise Q4_0-style)

Group size: 32 contiguous values along the last dimension.

```python
# Reshape to groups
flat = tensor.reshape(-1, cols)
grouped = flat.reshape(rows, -1, 32)

# Per-group scale
scale = grouped.abs().amax(dim=-1) / 8.0

# Quantize to [-8, 7]
q = round(grouped / scale).clamp(-8, 7)

# Pack 2 nibbles per byte (little-endian)
lo = q[..., 0::2]  # even indices
hi = q[..., 1::2]  # odd indices
packed = (lo | (hi << 4)).to(uint8)
```

Stored: packed uint8 + `{name}.scale` [rows, num_groups] (float16)

Dequantization on device:
1. Unpack nibbles: `lo = packed & 0x0F`, `hi = (packed >> 4) & 0x0F`
2. Two's complement: values ≥ 8 become `value - 16`
3. Interleave: `q_flat = stack([lo, hi], dim=-1).reshape(rows, -1)`
4. Multiply by per-group scale
5. Reshape to target shape (strip padding)

### Minimum Quantization Threshold

Tensors with fewer than 1024 elements are left in fp — quantizing them gains nothing and would break RoPE math if their int8/uint8 form is loaded raw.

## QuantConfig

`backend/app/engines/layerstream/quant_config.py` — saved as `quant_config.json`:

```json
{
  "quant_method": "none|int8|int4",
  "bits": 16|8|4,
  "group_size": 128|32
}
```

## Why Split?

LayerStream needs one layer on the device at a time to stay within memory bounds. Without splitting, loading the full `model.safetensors` into RAM defeats the purpose. The per-layer files enable:
- `LayerWeightLoader` to fetch individual layers from disk
- `ThreadPoolExecutor` prefetch to overlap I/O with compute
- LRU cache eviction of non-critical layers
- Pinned caching of embed/norm/lm_head (used every pass)

## Related

- [[05-layer-by-layer]] — How split weights are used during inference
- [[04-engine-system]] — LayerStreamEngine load process
- [[03-model-loading]] — When splitting happens (first LayerStream load)
- [[07-model-downloading]] — Models downloaded before splitting

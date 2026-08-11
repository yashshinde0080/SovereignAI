import os
import gc
import json
import torch
from transformers import AutoModelForCausalLM
from safetensors.torch import save_file

from .introspection import ModelIntrospector
from .quant_config import QuantConfig


# Tensors smaller than this are left in fp (buffers like inv_freq, tiny
# embeddings): quantizing them gains nothing and the executor would load
# their int8/uint8 form raw, silently breaking e.g. RoPE math.
_MIN_QUANT_NUMEL = 1024


def _quantize_int8(state_dict: dict) -> dict:
    """Per-tensor symmetric INT8 quantization. Returns quantized + scale tensors."""
    quantized = {}
    for key, tensor in state_dict.items():
        if (tensor.dtype in (torch.float16, torch.float32, torch.bfloat16)
                and tensor.numel() >= _MIN_QUANT_NUMEL):
            scale = tensor.abs().max() / 127.0
            if scale < 1e-10:
                quantized[key] = tensor.to(torch.int8)
            else:
                quantized[key] = torch.clamp(
                    torch.round(tensor / scale), -128, 127
                ).to(torch.int8)
            quantized[f"{key}.scale"] = scale.view(1).to(torch.float32)
        else:
            quantized[key] = tensor
            scale_key = f"{key}.scale"
            if scale_key in state_dict:
                quantized[scale_key] = state_dict[scale_key]
    return quantized


_INT4_GROUP = 32  # Q4_0-style group size; symmetric, no zero-point

def _quantize_int4(state_dict: dict) -> dict:
    """Group-wise symmetric INT4 (Q4_0-style), packed 2 values per byte.

    Each group of ``_INT4_GROUP`` contiguous values along the LAST dim shares
    one fp16 scale (max_abs / 8). Indices are 4-bit two's complement
    ([-8, 7]), packed little-endian into uint8: byte = (hi << 4) | lo.
    Scales are stored as ``<name>.scale``; dequant happens on device.
    """
    quantized = {}
    for key, tensor in state_dict.items():
        if (tensor.dtype in (torch.float16, torch.float32, torch.bfloat16)
                and tensor.numel() >= _MIN_QUANT_NUMEL):
            t = tensor.to(torch.float32)
            orig_shape = t.shape
            flat = t.reshape(-1, orig_shape[-1])  # [rows, cols]
            cols = flat.shape[1]
            pad = 0
            if cols % _INT4_GROUP != 0:
                # Pad cols to a multiple of the group; dequant restores shape
                pad = (_INT4_GROUP - cols % _INT4_GROUP) % _INT4_GROUP
                flat = torch.nn.functional.pad(flat, (0, pad))
            grouped = flat.reshape(flat.shape[0], -1, _INT4_GROUP)  # [r, g_, g]
            scale = grouped.abs().amax(dim=-1, keepdim=True).clamp(min=1e-10) / 8.0
            q = torch.clamp(torch.round(grouped / scale), -8, 7).to(torch.int8)
            q_flat = q.reshape(flat.shape[0], -1).to(torch.uint8) & 0x0F  # two's comp nibble
            lo = q_flat[..., 0::2]
            hi = q_flat[..., 1::2]
            packed = (lo | (hi << 4)).to(torch.uint8)
            # [rows, (cols+pad)/2] -> original shape with last dim halved; the
            # dequant slices the pad back off using the target tensor's shape.
            packed = packed.reshape(*orig_shape[:-1], (cols + pad) // 2)
            s = scale.reshape(flat.shape[0], -1).to(torch.float16)
            quantized[key] = packed
            quantized[f"{key}.scale"] = s
        else:
            quantized[key] = tensor
    return quantized


class WeightSplitter:
    def __init__(self, model_id: str, output_dir: str = "layers", quant_method: str = "none"):
        self.model_id = model_id
        self.output_dir = output_dir
        self.quant_method = quant_method
        os.makedirs(output_dir, exist_ok=True)

    def split_and_save(self, dtype=torch.float16):
        """
        Loads the full model into CPU RAM precisely once and saves the core components
        into separate safetensors files.
        """
        print(f"Loading full model '{self.model_id}' to CPU for splitting...")
        # Load full model to CPU
        kwargs = {
            "device_map": "cpu",
            "dtype": dtype,
            "low_cpu_mem_usage": True,
            "trust_remote_code": True,
            "ignore_mismatched_sizes": True
        }

        
        if str(self.model_id).endswith(".gguf") or str(self.model_id).endswith(".gguf.enc"):
            model_dir = os.path.dirname(self.model_id)
            kwargs["gguf_file"] = os.path.basename(self.model_id)
            model = AutoModelForCausalLM.from_pretrained(model_dir, **kwargs)
        else:
            # torch < 2.6 refuses .bin checkpoints (CVE-2025-32434); convert to safetensors first
            from app.engines.shared.safetensors import ensure_safetensors
            ensure_safetensors(self.model_id)
            model = AutoModelForCausalLM.from_pretrained(self.model_id, **kwargs)
        
        components = ModelIntrospector.detect_model_components(model)

        quant_method = self.quant_method
        # none / int8 / int4 are implemented; others need dedicated kernels
        if quant_method not in ("none", "int8", "int4"):
            raise ValueError(
                f"quant_method '{quant_method}' not yet implemented. "
                f"Available: none, int8, int4"
            )
        bits = {"none": 16, "int8": 8, "int4": 4}[quant_method]
        quant_cfg = QuantConfig(quant_method=quant_method, bits=bits,
                                group_size=_INT4_GROUP if quant_method == "int4" else 128)
        quant_cfg.save(os.path.join(self.output_dir, "quant_config.json"))

        def _maybe_quant(sd):
            if quant_method == "int8":
                return _quantize_int8(sd)
            if quant_method == "int4":
                return _quantize_int4(sd)
            return sd

        print("Saving embed...")
        save_file(_maybe_quant(components['embed'].state_dict()), os.path.join(self.output_dir, "embed.safetensors"))
        
        print(f"Saving {len(components['layers'])} layers...")
        for i, layer in enumerate(components['layers']):
            save_file(_maybe_quant(layer.state_dict()), os.path.join(self.output_dir, f"layer_{i}.safetensors"))

        if components['norm'] is not None:
            print("Saving final norm...")
            save_file(_maybe_quant(components['norm'].state_dict()), os.path.join(self.output_dir, "norm.safetensors"))

        print("Saving lm_head...")
        save_file(_maybe_quant(components['lm_head'].state_dict()), os.path.join(self.output_dir, "lm_head.safetensors"))
        
        # Save config
        model.config.save_pretrained(self.output_dir)
        
        # Copy tokenizer if it exists in source dir
        import shutil
        tokenizer_files = [
            "tokenizer.json", "tokenizer_config.json", "vocab.json", 
            "merges.txt", "special_tokens_map.json", "added_tokens.json",
            "tokenizer.model"
        ]
        
        source_dir = self.model_id
        if os.path.isfile(source_dir):
            source_dir = os.path.dirname(source_dir)
            
        for tf in tokenizer_files:
            src = os.path.join(source_dir, tf)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(self.output_dir, tf))
        
        # Clean up full model from RAM
        del model
        gc.collect()
        print(f"Splitting complete. Files saved to {self.output_dir}/")

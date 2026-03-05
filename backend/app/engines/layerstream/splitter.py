import os
import gc
import torch
from transformers import AutoModelForCausalLM
from safetensors.torch import save_file

from .introspection import ModelIntrospector

class WeightSplitter:
    def __init__(self, model_id: str, output_dir: str = "layers"):
        self.model_id = model_id
        self.output_dir = output_dir
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
            "torch_dtype": dtype,
            "low_cpu_mem_usage": True,
            "trust_remote_code": True,
            "ignore_mismatched_sizes": True
        }

        
        if str(self.model_id).endswith(".gguf") or str(self.model_id).endswith(".gguf.enc"):
            import os
            model_dir = os.path.dirname(self.model_id)
            kwargs["gguf_file"] = os.path.basename(self.model_id)
            model = AutoModelForCausalLM.from_pretrained(model_dir, **kwargs)
        else:
            model = AutoModelForCausalLM.from_pretrained(self.model_id, **kwargs)
        
        components = ModelIntrospector.detect_model_components(model)
        
        print("Saving embed...")
        save_file(components['embed'].state_dict(), os.path.join(self.output_dir, "embed.safetensors"))
        
        print(f"Saving {len(components['layers'])} layers...")
        for i, layer in enumerate(components['layers']):
            save_file(layer.state_dict(), os.path.join(self.output_dir, f"layer_{i}.safetensors"))
            
        if components['norm'] is not None:
            print("Saving final norm...")
            save_file(components['norm'].state_dict(), os.path.join(self.output_dir, "norm.safetensors"))
            
        print("Saving lm_head...")
        save_file(components['lm_head'].state_dict(), os.path.join(self.output_dir, "lm_head.safetensors"))
        
        # Save config
        model.config.save_pretrained(self.output_dir)
        
        # Clean up full model from RAM
        del model
        gc.collect()
        print(f"Splitting complete. Files saved to {self.output_dir}/")

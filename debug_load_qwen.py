import torch
from transformers import AutoModelForCausalLM, AutoConfig
import traceback

model_id = r"D:\SovereignAI\backend\models\installed\Qwen-Qwen3.5-0.8B"

try:
    print(f"Testing load for {model_id}")
    config = AutoConfig.from_pretrained(model_id, trust_remote_code=True)
    print(f"Config loaded: {config.model_type}")
    
    kwargs = {
        "device_map": "cpu",
        "torch_dtype": torch.float16,
        "low_cpu_mem_usage": True,
        "trust_remote_code": True,
        "ignore_mismatched_sizes": True
    }
    
    model = AutoModelForCausalLM.from_pretrained(model_id, **kwargs)
    print("Model loaded successfully")
except Exception as e:
    print("Error during load:")
    traceback.print_exc()


import torch
from transformers import AutoConfig, AutoModelForMultimodalLM
import time
import os

model_path = "models/installed/Qwen-Qwen3.5-0.8B"
try:
    print(f"Loading config from {model_path}...")
    config = AutoConfig.from_pretrained(model_path, trust_remote_code=True)
    print(f"Config loaded: {config.__class__.__name__}")
    
    print("\nAttempting model load with AutoModelForMultimodalLM.from_pretrained...")
    start = time.time()
    
    # We use CPU to avoid VRAM issues during test if GTX 1650 is tight (4GB)
    # The model is 0.8B, so ~1.6GB in float16, ~3.2GB in float32.
    # GTX 1650 has 4GB, so float32 might OOM if other stuff is running.
    # We'll use low_cpu_mem_usage=True.
    
    model = AutoModelForMultimodalLM.from_pretrained(
        model_path,
        trust_remote_code=True,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        device_map="auto" if torch.cuda.is_available() else "cpu",
        low_cpu_mem_usage=True
    )
    
    print(f"Success! Load took {time.time() - start:.2f}s")
    print(f"Model class: {model.__class__.__name__}")
    
except Exception as e:
    import traceback
    print(f"\nERROR: {e}")
    traceback.print_exc()

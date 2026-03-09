
from transformers import AutoConfig, AutoModelForCausalLM
import torch
import os

model_path = "models/installed/Qwen-Qwen3.5-0.8B"
try:
    config = AutoConfig.from_pretrained(model_path)
    print(f"Config loaded! Model type: {config.model_type}")
    
    from accelerate import init_empty_weights
    with init_empty_weights():
        model = AutoModelForCausalLM.from_config(config)
    print("Model initialized successfully!")
except Exception as e:
    print(f"Error loading Qwen 3.5: {e}")


import torch
from transformers import AutoConfig, AutoModelForCausalLM
from accelerate import init_empty_weights
import os

model_path = "models/installed/Qwen-Qwen2.5-0.5B-Instruct"

config = AutoConfig.from_pretrained(model_path)
with init_empty_weights():
    model = AutoModelForCausalLM.from_config(config)

print(f"Model class: {model.__class__.__name__}")
# Try to find rotary_emb
for name, module in model.named_modules():
    if "rotary_emb" in name:
        print(f"Found rotary_emb module: {name} ({module.__class__.__name__})")
        break

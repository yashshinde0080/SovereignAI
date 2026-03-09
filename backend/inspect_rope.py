
import torch
import inspect
from transformers import AutoConfig, AutoModelForCausalLM
from accelerate import init_empty_weights

model_path = "models/installed/Qwen-Qwen2.5-0.5B-Instruct"
config = AutoConfig.from_pretrained(model_path)
with init_empty_weights():
    model = AutoModelForCausalLM.from_config(config)

rotary_emb = None
for name, module in model.named_modules():
    if "rotary_emb" in name:
        rotary_emb = module
        break

print(f"Rotary module: {rotary_emb}")
sig = inspect.signature(rotary_emb.forward)
print(f"Forward signature: {sig}")

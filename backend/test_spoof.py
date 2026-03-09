
import json
from transformers import AutoConfig, AutoModelForCausalLM
import torch

model_path = "models/installed/Qwen-Qwen3.5-0.8B"

with open(f"{model_path}/config.json", "r") as f:
    config_dict = json.load(f)

print(f"Original model_type: {config_dict.get('model_type')}")
config_dict["model_type"] = "qwen2"

try:
    # Use the dict to create a config object
    config = AutoConfig.from_dict(config_dict)
    print("Spoofed config created successfully.")
    
    from accelerate import init_empty_weights
    with init_empty_weights():
        model = AutoModelForCausalLM.from_config(config)
    print("Model initialized from spoofed config!")
    
except Exception as e:
    print(f"Activation failed: {e}")

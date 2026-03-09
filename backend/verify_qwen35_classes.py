
import torch
from transformers import AutoConfig, AutoModel, AutoModelForCausalLM, AutoModelForSeq2SeqLM
from accelerate import init_empty_weights
import os

model_path = "models/installed/Qwen-Qwen3.5-0.8B"
try:
    config = AutoConfig.from_pretrained(model_path)
    print(f"Config loaded: {config.__class__.__name__}")
    print(f"Architectures: {config.architectures}")
    
    with init_empty_weights():
        print("Trying AutoModelForMultimodalLM...")
        try:
            from transformers import AutoModelForMultimodalLM
            model = AutoModelForMultimodalLM.from_config(config)
            print("AutoModelForMultimodalLM success!")
        except Exception as e:
            print(f"AutoModelForMultimodalLM failed: {e}")
            
        print("Trying AutoModel...")
        try:
            model = AutoModel.from_config(config)
            print("AutoModel success!")
        except Exception as e:
            print(f"AutoModel failed: {e}")
            
except Exception as e:
    print(f"Error: {e}")

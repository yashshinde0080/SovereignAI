import torch
from safetensors.torch import load_file
layer0 = load_file(r'd:\SovereignAI\backend\offload_cache\Qwen-Qwen2.5-0.5B-Instruct\layer_0.safetensors')
print(list(layer0.keys()))

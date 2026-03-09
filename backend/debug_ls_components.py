from transformers import AutoConfig, AutoModelForCausalLM
from accelerate import init_empty_weights
from app.engines.layerstream.introspection import ModelIntrospector
import inspect

# Check Qwen 2.5 components
c = AutoConfig.from_pretrained("offload_cache/Qwen-Qwen2.5-0.5B-Instruct")
c._attn_implementation = "eager"
print("Config:", c.architectures, c.model_type)

with init_empty_weights():
    m = AutoModelForCausalLM.from_config(c)

comps = ModelIntrospector.detect_model_components(m)
print("embed:", comps["embed"].__class__.__name__)
print("layers:", len(comps["layers"]), comps["layers"][0].__class__.__name__)
print("norm:", comps["norm"].__class__.__name__ if comps["norm"] else None)
print("lm_head:", comps["lm_head"].__class__.__name__)
print("rotary:", comps["rotary_emb"].__class__.__name__ if comps["rotary_emb"] else None)

# Check forward signature of first layer
layer = comps["layers"][0]
sig = inspect.signature(layer.forward)
print("\nLayer forward params:", list(sig.parameters.keys()))

# Check if KV cache is being used - does layer have self_attn?
print("\nLayer children:")
for name, child in layer.named_children():
    print(f"  {name}: {child.__class__.__name__}")

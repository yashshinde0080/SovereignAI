import torch
from app.engines.layerstream.introspection import ModelIntrospector
from transformers import AutoModelForCausalLM
import gc

def debug_embed():
    model_id = r"D:\SovereignAI\models\installed\Qwen-Qwen2.5-0.5B-Instruct"
    model = AutoModelForCausalLM.from_pretrained(model_id, device_map="cpu", torch_dtype=torch.float16, low_cpu_mem_usage=True)
    embed = model.model.embed_tokens
    input_ids = torch.tensor([[1, 2, 3, 4, 5]])
    hidden_states = embed(input_ids)
    print("Reference embed sum:", hidden_states.sum().item(), "min:", hidden_states.min().item(), "max:", hidden_states.max().item())

    from app.engines.layerstream.executor import LayerStreamEngine
    import asyncio
    engine = LayerStreamEngine(model_id, {"device": "cuda"}, None)

    async def main():
        await engine.load()
        embed_path = engine.layer_executor.embed_path
        engine.layer_executor.assign_weights(engine.components['embed'], engine.layer_executor.loader.get_weights(embed_path))
        hs = engine.components['embed'](input_ids.to(engine.device))
        print("LayerStream embed sum:", hs.sum().item(), "min:", hs.min().item(), "max:", hs.max().item())

    asyncio.run(main())

debug_embed()

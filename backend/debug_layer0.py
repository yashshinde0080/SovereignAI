import torch
from app.engines.layerstream.introspection import ModelIntrospector
from transformers import AutoModelForCausalLM
import gc

def debug_layer0():
    model_id = r"D:\SovereignAI\models\installed\Qwen-Qwen2.5-0.5B-Instruct"
    model = AutoModelForCausalLM.from_pretrained(model_id, device_map="cpu", torch_dtype=torch.float16, low_cpu_mem_usage=True)
    embed = model.model.embed_tokens
    layer0 = model.model.layers[0]

    input_ids = torch.tensor([[1, 2, 3, 4, 5]])
    hidden_states = embed(input_ids)
    
    # We need to construct position_ids & attention_mask manually for a fair test
    position_ids = torch.arange(0, 5, dtype=torch.long).unsqueeze(0)
    attention_mask = torch.tril(torch.ones((5, 5))).unsqueeze(0).unsqueeze(0)
    attention_mask = torch.where(attention_mask == 1.0, 0.0, torch.finfo(torch.float16).min)
    
    ref_out = layer0(hidden_states, position_ids=position_ids, attention_mask=attention_mask, use_cache=False)
    hs_ref = ref_out[0]

    print("Reference layer0 sum:", hs_ref.sum().item(), "min:", hs_ref.min().item(), "max:", hs_ref.max().item())

    from app.engines.layerstream.executor import LayerStreamEngine
    import asyncio
    engine = LayerStreamEngine(model_id, {"device": "cuda"}, None)

    async def main():
        await engine.load()
        engine.layer_executor.assign_weights(engine.components['embed'], engine.layer_executor.loader.get_weights(engine.layer_executor.embed_path))
        hs_ls = engine.components['embed'](input_ids.to(engine.device))
        
        # Now assign layer0
        l0 = engine.components['layers'][0]
        engine.layer_executor.assign_weights(l0, engine.layer_executor.loader.get_weights(engine.layer_executor.layer_paths[0]))
        
        # Test just layer_0
        ls_out = l0(
            hs_ls, 
            position_ids=position_ids.to(engine.device), 
            attention_mask=attention_mask.to(engine.device), 
            use_cache=False
        )
        hs_ls_eval = ls_out[0]
        print(f"Reference Layer 0 Sum: {hs_ref.sum().item()} | LS Layer 0 Sum: {hs_ls_eval.sum().item()}")
        diff = torch.abs(hs_ref.cpu() - hs_ls_eval.cpu()).max().item()
        print("Max diff:", diff)
        
        torch.testing.assert_close(hs_ref.cpu(), hs_ls_eval.cpu(), rtol=1e-3, atol=1e-3)

    asyncio.run(main())

debug_layer0()

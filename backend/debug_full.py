import torch
from transformers import AutoModelForCausalLM
import gc

def debug_full():
    model_id = r"D:\SovereignAI\models\installed\Qwen-Qwen2.5-0.5B-Instruct"
    print("Loading FullRAM model...")
    model = AutoModelForCausalLM.from_pretrained(model_id, device_map="cpu", torch_dtype=torch.float16, low_cpu_mem_usage=True)

    input_ids = torch.tensor([[1, 2, 3, 4, 5]])
    
    with torch.no_grad():
        ref_out = model(input_ids, output_hidden_states=True)
        logits_ref = ref_out.logits
        hidden_states_ref = ref_out.hidden_states
    
    print("Reference logits sum:", logits_ref.sum().item(), "min:", logits_ref.min().item(), "max:", logits_ref.max().item())
    for i, hs in enumerate(hidden_states_ref):
        print(f"Ref HS {i} sum: {hs.sum().item()} min: {hs.min().item()} max: {hs.max().item()}")

    from app.engines.layerstream.executor import LayerStreamEngine
    import asyncio
    engine = LayerStreamEngine(model_id, {"device": "cuda"}, None)

    async def main():
        await engine.load()
        with torch.no_grad():
            orig_offload = engine.layer_executor.offload_weights
            # Don't offload to trace easier if needed, but we can leave it
            
            # Trace intermediate states in layer_executor
            executor = engine.layer_executor
            device = executor.device
            batch_size, seq_length = input_ids.shape
            
            executor.assign_weights(executor.components['embed'], executor.loader.get_weights(executor.embed_path))
            hs_ls = executor.components['embed'](input_ids.to(device))
            executor.offload_weights(executor.components['embed'])
            print(f"LS HS 0 sum: {hs_ls.sum().item()} min: {hs_ls.min().item()} max: {hs_ls.max().item()}")

            import inspect
            from app.engines.layerstream.kv_cache import HFProxyCache
            
            past_length = executor.kv_manager.get_seq_length(0)
            position_ids = torch.arange(past_length, past_length + seq_length, dtype=torch.long, device=device).unsqueeze(0)
            cache_position = torch.arange(past_length, past_length + seq_length, dtype=torch.long, device=device)
            attention_mask = executor._create_attention_mask((batch_size, seq_length), past_length, hs_ls.dtype)

            hf_cache = HFProxyCache(executor.kv_manager)

            for i, layer in enumerate(executor.components['layers']):
                executor.assign_weights(layer, executor.loader.get_weights(executor.layer_paths[i]))

                sig = inspect.signature(layer.forward)
                kwargs = {}
                if "position_ids" in sig.parameters:
                    kwargs["position_ids"] = position_ids
                if "attention_mask" in sig.parameters:
                    kwargs["attention_mask"] = attention_mask
                if "use_cache" in sig.parameters:
                    kwargs["use_cache"] = True
                if "past_key_value" in sig.parameters:
                    kwargs["past_key_value"] = hf_cache
                if "cache_position" in sig.parameters:
                    kwargs["cache_position"] = cache_position
                    
                layer_outputs = layer(hs_ls, **kwargs)
                hs_ls = layer_outputs[0]

                if "cuda" in str(device):
                    torch.cuda.empty_cache()
                executor.offload_weights(layer)
                
                if i < 23:
                    print(f"LS HS {i+1} sum: {hs_ls.sum().item()} min: {hs_ls.min().item()} max: {hs_ls.max().item()}")
                    ref_hs = hidden_states_ref[i+1]
                    diff = torch.abs(ref_hs.cpu() - hs_ls.cpu()).max().item()
                    print(f"  -> Max abs diff vs Ref HS {i+1}: {diff}")
                
            executor.assign_weights(executor.components['norm'], executor.loader.get_weights(executor.norm_path))
            hs_ls = executor.components['norm'](hs_ls)
            executor.offload_weights(executor.components['norm'])
            
            print(f"LS out (Norm) sum: {hs_ls.sum().item()} min: {hs_ls.min().item()} max: {hs_ls.max().item()}")
            ref_hs_24 = hidden_states_ref[24]
            diff_norm = torch.abs(ref_hs_24.cpu() - hs_ls.cpu()).max().item()
            print(f"  -> Max abs diff vs Ref HS 24 (Norm): {diff_norm}")
            executor.offload_weights(executor.components['norm'])

            executor.assign_weights(executor.components['lm_head'], executor.loader.get_weights(executor.lm_head_path))
            logits_ls = executor.components['lm_head'](hs_ls)
            executor.offload_weights(executor.components['lm_head'])
        print("Max absolute difference:", diff)

    asyncio.run(main())

debug_full()

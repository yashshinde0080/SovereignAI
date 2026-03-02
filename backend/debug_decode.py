import asyncio
from app.core.engine_factory import EngineFactory
import torch

prompt = "Hello, my name is"

async def debug_decode():
    factory = EngineFactory({"device": "cuda"})
    
    full = await factory.create_engine(
        model_path=r"D:\SovereignAI\models\installed\Qwen-Qwen2.5-0.5B-Instruct",
        mode="fullram"
    )
    
    ls = await factory.create_engine(
        model_path=r"D:\SovereignAI\models\installed\Qwen-Qwen2.5-0.5B-Instruct",
        mode="layerstream"
    )
    
    input_ids = full.tokenizer(prompt, return_tensors="pt")["input_ids"].to(full.device)
    
    with torch.no_grad():
        # Prefill FullRAM
        out_full = full.model(input_ids)
        logits_full_1 = out_full.logits[:, -1, :]
        next_tok_full = torch.argmax(logits_full_1, dim=-1).unsqueeze(-1)
        
        # Decode FullRAM (1 token)
        out_full_2 = full.model(next_tok_full, past_key_values=out_full.past_key_values)
        logits_full_2 = out_full_2.logits[:, -1, :]
        
        # Prefill LayerStream
        executor = ls.layer_executor
        executor.DEBUG = True
        executor.kv_manager.clear()
        logits_ls_1 = executor.execute_forward(input_ids, mode="prefill")[:, -1, :]
        next_tok_ls = torch.argmax(logits_ls_1, dim=-1).unsqueeze(-1)
        
        # Decode LayerStream (1 token)
        logits_ls_2 = executor.execute_forward(next_tok_ls, mode="decode")[:, -1, :]
        
    print("Full Token 1:", next_tok_full.item())
    print("LS Token 1:", next_tok_ls.item())
    print("Full Logits 1 (first 5):", logits_full_1[0, :5].tolist())
    print("LS Logits 1 (first 5):", logits_ls_1[0, :5].tolist())
    
    print("Prefill MATCH:", torch.allclose(logits_full_1.float(), logits_ls_1.float(), atol=1e-3))
    print("Decode MATCH:", torch.allclose(logits_full_2.float(), logits_ls_2.float(), atol=1e-3))
    print("Max diff Decode:", torch.abs(logits_full_2.float() - logits_ls_2.float()).max().item())

asyncio.run(debug_decode())

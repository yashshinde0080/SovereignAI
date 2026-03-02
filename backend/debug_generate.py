import asyncio
from app.core.engine_factory import EngineFactory
import torch

prompt = "Hello, my name is"

async def test_backends():
    factory = EngineFactory({"device": "cuda"})
    
    print("Loading FullRAM...")
    full = await factory.create_engine(
        model_path=r"D:\SovereignAI\models\installed\Qwen-Qwen2.5-0.5B-Instruct",
        mode="fullram"
    )
    
    print("Loading LayerStream...")
    ls = await factory.create_engine(
        model_path=r"D:\SovereignAI\models\installed\Qwen-Qwen2.5-0.5B-Instruct",
        mode="layerstream"
    )
    
    # We must use greedy to ensure exact parity without random variance
    print("\n--- FullRAM ---")
    res_full = await full.generate(prompt, max_tokens=10, temperature=0.0)
    print("Full text:", repr(res_full['text']))
    
    print("\n--- LayerStream ---")
    res_ls = await ls.generate(prompt, max_tokens=10, temperature=0.0)
    print("LS text:", repr(res_ls['text']))
    
asyncio.run(test_backends())

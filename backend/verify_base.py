
import asyncio
from app.engines.fullram.executor import FullRAMEngine
from app.engines.layerstream.executor import LayerStreamEngine

async def test():
    model_path = "models/installed/Qwen-Qwen2.5-0.5B-Instruct"
    print(f"Testing {model_path} with FullRAMEngine...")
    engine = FullRAMEngine(model_path, {"ram_total_gb": 16, "device": "cpu"}, None)
    await engine.load()
    print("FullRAM Load successful!")
    
    messages = [{"role": "user", "content": "Hi"}]
    res = await engine.generate(messages, max_tokens=10)
    print(f"FullRAM Gen: {res['output']}")
    
    await engine.unload()
    
    print(f"\nTesting {model_path} with LayerStreamEngine...")
    engine = LayerStreamEngine(model_path, {"ram_total_gb": 16, "device": "cpu"}, None)
    await engine.load()
    print("LayerStream Load successful!")
    res = await engine.generate(messages, max_tokens=10)
    print(f"LayerStream Gen: {res['output']}")

if __name__ == "__main__":
    asyncio.run(test())

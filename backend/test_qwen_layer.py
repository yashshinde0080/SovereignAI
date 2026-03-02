import sys
import asyncio
from app.core.engine_factory import EngineFactory

async def main():
    factory = EngineFactory({"device": "cpu"})
    engine = await factory.create_engine(
        model_path=r"D:\SovereignAI\models\installed\Qwen-Qwen2.5-0.5B-Instruct",
        mode="layerstream"
    )
    
    prompt = "Hello"
    res = await engine.generate(prompt, max_tokens=10)
    print("RES:", res)
    
if __name__ == "__main__":
    asyncio.run(main()) 

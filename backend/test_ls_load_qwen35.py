
import asyncio
from app.engines.layerstream.executor import LayerStreamEngine
from app.core.hardware_detector import HardwareDetector

async def test_load():
    model_path = "models/installed/Qwen-Qwen3.5-0.8B"
    hardware = HardwareDetector().detect()
    engine = LayerStreamEngine(model_path, hardware, None)
    try:
        await engine.load()
        print("Success load! Generating...")
        res = await engine.generate("Hello! How are you?", max_tokens=10)
        print("Response:", res)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_load())

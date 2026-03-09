
import asyncio
from app.engines.fullram.executor import FullRAMEngine
from app.core.hardware_detector import HardwareDetector
import torch

async def test_load():
    model_path = "models/installed/Qwen-Qwen3.5-0.8B"
    hardware = HardwareDetector().detect()
    engine = FullRAMEngine(model_path, hardware, None)
    try:
        await engine.load()
        print("Success!")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_load())

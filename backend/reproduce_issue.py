
import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path("d:/SovereignAI/backend")))

from app.engines.fullram.executor import FullRAMEngine
from app.core.task_resolver import TaskResolver
from app.core.memory_manager import MemoryManager

async def test_load():
    model_path = "d:/SovereignAI/backend/models/installed/Qwen-Qwen2.5-0.5B-Instruct"
    print(f"Testing load for {model_path}")
    
    # 1. Test TaskResolver
    metadata = TaskResolver.resolve(model_path)
    print(f"Task Metadata: {metadata}")
    
    # 2. Test FullRAMEngine.load
    hardware = {"device": "cpu"}
    memory_manager = MemoryManager()
    
    engine = FullRAMEngine(model_path, hardware, memory_manager)
    try:
        await engine.load()
        print("Success: Model loaded")
    except Exception as e:
        print(f"Error loading model: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_load())

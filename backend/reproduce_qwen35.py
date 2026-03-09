
import asyncio
import os
import sys
import torch
from pathlib import Path

# Add backend to path
sys.path.append(os.path.abspath("."))

from app.engines.layerstream.executor import LayerStreamEngine
from app.core.memory_manager import MemoryManager

async def test_qwen35():
    model_path = "D:/SovereignAI/backend/models/installed/Qwen-Qwen3.5-0.8B"
    print(f"Testing LayerStream load for {model_path}")
    
    hardware = {"ram_total_gb": 16, "device": "cpu"}
    memory_manager = MemoryManager()
    
    engine = LayerStreamEngine(model_path, hardware, memory_manager)
    try:
        await engine.load()
        print("Success: Model loaded")
    except Exception as e:
        print(f"Error loading model: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_qwen35())

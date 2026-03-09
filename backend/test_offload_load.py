
import asyncio
import os
import sys
import torch
from pathlib import Path

# Add backend to path
sys.path.append(os.path.abspath("."))

from app.engines.layerstream.executor import LayerStreamEngine
from app.core.memory_manager import MemoryManager

async def test_qwen25_split():
    model_path = "D:/SovereignAI/backend/offload_cache/Qwen-Qwen2.5-0.5B-Instruct"
    print(f"Testing LayerStream load directly from CACHE for {model_path}")
    
    hardware = {"ram_total_gb": 16, "device": "cpu"}
    memory_manager = MemoryManager()
    
    engine = LayerStreamEngine(model_path, hardware, memory_manager)
    try:
        await engine.load()
        print("Success: Model loaded")
        
        # Test generation
        print("Testing generation...")
        result = await engine.generate("Hello, how are you?", max_tokens=10)
        print(f"Result: {result['output']}")
        
    except Exception as e:
        print(f"Error loading model: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_qwen25_split())

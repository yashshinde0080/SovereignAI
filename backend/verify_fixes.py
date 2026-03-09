
import asyncio
import os
import sys
import json
from pathlib import Path

# Add backend to path
sys.path.append(os.path.abspath("."))

from app.services.model_manager import ModelManager
from app.config import settings

async def verify():
    print("Initializing ModelManager...")
    manager = ModelManager()
    
    # Mock app state
    class MockApp:
        def __init__(self):
            self.state = type('obj', (object,), {
                'hardware_profile': {"ram_total_gb": 16, "device": "cpu"},
                'active_engine': None,
                'active_model': None,
                'active_mode': None
            })
    
    app = MockApp()
    await manager.initialize(app=app)
    
    print("\nScanning models...")
    await manager.scan_installed()
    
    print("\nList of registered models:")
    models = await manager.list_models()
    for m in models:
        print(f"- {m['id']} (Path: {m['path']})")
        
    print("\nAttempting fuzzy load for 'Qwen2.5-0.5B-Instruct'...")
    try:
        # Should fuzzy match to 'split:Qwen-Qwen2.5-0.5B-Instruct' if it's there
        result = await manager.load_model("Qwen2.5-0.5B-Instruct", mode="layerstream")
        print(f"Load Result: {result['status']} (Mode: {result['mode']})")
        
        # Test chat template
        print("\nTesting chat template generation...")
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is the capital of France?"}
        ]
        
        engine = app.state.active_engine
        gen_result = await engine.generate(messages, max_tokens=20)
        print(f"Chat Result: {gen_result['output']}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify())

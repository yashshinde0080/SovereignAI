import asyncio
import traceback
from typing import List, Dict

from app.core.engine_factory import EngineFactory

MODEL_PATH = r"D:\SovereignAI\models\installed\Qwen-Qwen2.5-0.5B-Instruct"

def build_prompt(messages: List[Dict[str, str]]) -> str:
    prompt = ""
    for msg in messages:
        if msg["role"] == "system":
            prompt += f"<|im_start|>system\n{msg['content']}<|im_end|>\n"
        elif msg["role"] == "user":
            prompt += f"<|im_start|>user\n{msg['content']}<|im_end|>\n"
        elif msg["role"] == "assistant":
            prompt += f"<|im_start|>assistant\n{msg['content']}<|im_end|>\n"
    
    prompt += "<|im_start|>assistant\n"
    return prompt

async def test_engine_mode(mode: str):
    print(f"\n{'='*50}")
    print(f"Testing Engine Mode: {mode.upper()}")
    print(f"{'='*50}")
    
    # We create a dummy hardware profile since engine expects it
    hardware_profile = {
        "ram_total_gb": 16,
        "vram_total_gb": 8 if mode == "fullram" else 0, # dummy values
        "cpu_memory": "16GB",
        "gpu_memory": "8GB"
    }

    try:
        factory = EngineFactory(hardware_profile)
        
        print(f"Loading '{MODEL_PATH}' using {mode} mode...")
        # create_engine will automatically call engine.load()
        engine = await factory.create_engine(MODEL_PATH, mode)
        print(f"Model loaded successfully in {mode} mode.")
        
        # Build a prompt for Qwen
        messages = [
            {"role": "system", "content": "You are a helpful AI assistant."},
            {"role": "user", "content": "Explain what 1+1 is briefly."}
        ]
        prompt = build_prompt(messages)
        
        print(f"\nGenerating response in {mode} mode...")
        
        # Test generate_stream
        print("Response: ", end="", flush=True)
        async for chunk in engine.generate_stream(prompt, max_tokens=50, temperature=0.7):
            if "text" in chunk:
                print(chunk["text"], end="", flush=True)
            elif "token" in chunk:
                # some engines might return 'token' instead of 'text'
                pass # depends on how internal stream formats it
        
        print("\n\nDone with stream generation.")
        
        # Unload
        print("Unloading model...")
        await engine.unload()
        del engine
        print(f"{mode.upper()} mode test completed successfully.\n")

    except Exception as e:
        print(f"Error occurred during {mode} mode testing:")
        traceback.print_exc()

async def main():
    print("Starting Inference Engine Mode Tests...\n")
    
    # Test 1: Full RAM Mode
    await test_engine_mode("fullram")
    
    # Test 2: Layer Streaming Mode
    await test_engine_mode("layerstream")
    
    print("All mode tests finished.")

if __name__ == "__main__":
    asyncio.run(main())

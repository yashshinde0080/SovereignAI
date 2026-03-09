import asyncio
import sys
from app.engines.layerstream.executor import LayerStreamEngine
from app.core.hardware_detector import HardwareDetector

async def test():
    model_path = "models/installed/Qwen-Qwen2.5-0.5B-Instruct"
    hardware = HardwareDetector().detect()
    engine = LayerStreamEngine(model_path, hardware, None)
    
    await engine.load()
    print("Loaded! Generating...")
    
    messages = [
        {"role": "user", "content": "What is 2+2? Answer in one short sentence."}
    ]
    res = await engine.generate(messages, max_tokens=30, temperature=0.1)
    output = res.get("output", "")
    print("Output:", output.encode(sys.stdout.encoding, errors="replace").decode(sys.stdout.encoding))

asyncio.run(test())

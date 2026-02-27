from app.providers.huggingface import HuggingFaceProvider
import asyncio
from app.services.model_manager import ModelManager

async def test():
    p = HuggingFaceProvider()
    await p.initialize()
    info = await p.get_model_info("microsoft/bitnet-b1.58-2B-4T")
    print(info)

asyncio.run(test())

import asyncio
from app.providers.huggingface import HuggingFaceProvider
from app.services.model_manager import ModelManager

async def test_dl():
    p = HuggingFaceProvider()
    await p.initialize()
    info = await p.get_model_info("microsoft/bitnet-b1.58-2B-4T")
    print("Files:", len(info.files) if info else "No info")
    
    manager = ModelManager()
    await manager.initialize()
    await manager.download_model("microsoft/bitnet-b1.58-2B-4T", "")
    print(manager.get_download_status("microsoft/bitnet-b1.58-2B-4T"))

if __name__ == "__main__":
    asyncio.run(test_dl())

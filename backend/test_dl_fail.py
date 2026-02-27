from app.services.model_manager import ModelManager
import asyncio

async def test():
    m = ModelManager()
    await m.initialize()
    await m.download_model("microsoft/bitnet-b1.58-2B-4T", "")
    st = m.get_download_status("microsoft/bitnet-b1.58-2B-4T")
    if st["error"]:
        raise Exception(st["error"])
        
asyncio.run(test())

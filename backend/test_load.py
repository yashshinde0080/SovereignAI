import asyncio
from app.core.engine_factory import EngineFactory
import traceback

async def run():
    try:
        f = EngineFactory({"ram_total_gb": 16})
        await f.create_engine("D:\\SovereignAI\\models\\installed\\microsoft-bitnet-b1.58-2B-4T", "auto")
    except Exception as e:
        traceback.print_exc()

asyncio.run(run())

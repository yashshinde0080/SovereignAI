import asyncio
import httpx

async def manage_models():
    async with httpx.AsyncClient(timeout=300.0) as client:
        print('Fetching models...')
        res = await client.get('http://127.0.0.1:8000/v1/models/')
        models = res.json().get('models', [])
        for m in models:
            if 'bitnet' in m['id'].lower():
                print(f"Deleting {m['id']}...")
                await client.delete(f"http://127.0.0.1:8000/v1/models/{m['id']}")
        
        print('Pulling TinyLlama/TinyLlama-1.1B-Chat-v1.0...')
        res = await client.post('http://127.0.0.1:8000/v1/models/pull', json={'model': 'TinyLlama/TinyLlama-1.1B-Chat-v1.0', 'quant': ''})
        print('Pull started:', res.json())
        
        while True:
            res = await client.get('http://127.0.0.1:8000/v1/models/pull/status/TinyLlama/TinyLlama-1.1B-Chat-v1.0')
            status = res.json()
            print(f"Status: {status['status']} - {status['progress']}%")
            if status['status'] in ['complete', 'error']:
                break
            await asyncio.sleep(2)

asyncio.run(manage_models())

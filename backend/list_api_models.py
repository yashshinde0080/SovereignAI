
import httpx
import json
import asyncio

async def test():
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # The list endpoint is GET /v1/models/ based on router.get("/")
            res = await client.get("http://localhost:8000/v1/models/")
            if res.status_code == 200:
                data = res.json()
                models = data.get("models", [])
                print(f"Registered models: {len(models)}")
                for m in models:
                    print(f"- {m['id']} ({m['modes_supported']}) at {m['path']}")
            else:
                print(f"Failed to list models: {res.status_code} {res.text}")
        except Exception as e:
            print(f"Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test())

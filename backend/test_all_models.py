import httpx, asyncio, sys

async def test_all():
    async with httpx.AsyncClient(timeout=300.0) as client:
        # Test 1: Qwen 2.5 fullram
        print("=== Test 1: Qwen 2.5 fullram ===")
        r = await client.post("http://localhost:8000/v1/models/load", json={"model": "Qwen/Qwen2.5-0.5B-Instruct", "mode": "fullram"})
        print(f"Load: {r.status_code}")
        if r.status_code == 200:
            r = await client.post("http://localhost:8000/v1/chat/completions", json={"messages": [{"role": "user", "content": "What is 2+2? Answer briefly."}], "max_tokens": 20})
            print(f"Chat: {r.status_code}")
            if r.status_code == 200:
                txt = r.json()["choices"][0]["message"]["content"]
                print("Answer:", txt.encode(sys.stdout.encoding, errors="replace").decode(sys.stdout.encoding))
            else:
                print("Error:", r.text[:300])

        # Test 2: Qwen 2.5 layerstream
        print("\n=== Test 2: Qwen 2.5 layerstream ===")
        r = await client.post("http://localhost:8000/v1/models/load", json={"model": "Qwen/Qwen2.5-0.5B-Instruct", "mode": "layerstream"})
        print(f"Load: {r.status_code}")
        if r.status_code == 200:
            r = await client.post("http://localhost:8000/v1/chat/completions", json={"messages": [{"role": "user", "content": "What is 2+2? Answer briefly."}], "max_tokens": 20})
            print(f"Chat: {r.status_code}")
            if r.status_code == 200:
                txt = r.json()["choices"][0]["message"]["content"]
                print("Answer:", txt.encode(sys.stdout.encoding, errors="replace").decode(sys.stdout.encoding))
            else:
                print("Error:", r.text[:300])

        # Test 3: Qwen 3.5 fullram
        print("\n=== Test 3: Qwen 3.5 fullram ===")
        r = await client.post("http://localhost:8000/v1/models/load", json={"model": "Qwen/Qwen3.5-0.8B", "mode": "fullram"})
        print(f"Load: {r.status_code}")
        if r.status_code == 200:
            r = await client.post("http://localhost:8000/v1/chat/completions", json={"messages": [{"role": "user", "content": "What is 2+2? Answer briefly."}], "max_tokens": 30})
            print(f"Chat: {r.status_code}")
            if r.status_code == 200:
                txt = r.json()["choices"][0]["message"]["content"]
                print("Answer:", txt.encode(sys.stdout.encoding, errors="replace").decode(sys.stdout.encoding))
            else:
                print("Error:", r.text[:300])

asyncio.run(test_all())


import httpx
import json
import asyncio

async def test_chat_layerstream_qwen35():
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Load Qwen3.5-0.8B in layerstream
        print("Loading Qwen 3.5 in layerstream...")
        load_res = await client.post("http://localhost:8000/v1/models/load", json={
            "model": "Qwen/Qwen3.5-0.8B",
            "mode": "layerstream"
        })
        print(f"Load status: {load_res.status_code}")
        try:
            print(load_res.json())
        except:
            print(load_res.text)
        
        if load_res.status_code != 200:
            return

        # Chat
        print("\nSending chat request...")
        chat_res = await client.post("http://localhost:8000/v1/chat/completions", json={
            "messages": [
                {"role": "user", "content": "How's your day?"}
            ],
            "max_tokens": 100
        })
        print(f"Chat status: {chat_res.status_code}")
        if chat_res.status_code == 200:
            import sys
            text = chat_res.json()["choices"][0]["message"]["content"]
            print("Response:", text.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding))
        else:
            print("Error:", chat_res.text)

if __name__ == "__main__":
    asyncio.run(test_chat_layerstream_qwen35())

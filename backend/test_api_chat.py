
import httpx
import json
import asyncio

async def test_chat():
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Load Qwen2.5-0.5B-Instruct in LayerStream
        print("Loading model...")
        load_res = await client.post("http://localhost:8000/v1/models/load", json={
            "model": "Qwen/Qwen2.5-0.5B-Instruct",
            "mode": "layerstream"
        })
        print(f"Load status: {load_res.status_code}")
        print(load_res.json())
        
        if load_res.status_code != 200:
            return

        # Chat
        print("\nSending chat request...")
        chat_res = await client.post("http://localhost:8000/v1/chat/completions", json={
            "messages": [
                {"role": "user", "content": "What is the capital of France?"}
            ],
            "max_tokens": 50
        })
        print(f"Chat status: {chat_res.status_code}")
        if chat_res.status_code == 200:
            print("Response:", chat_res.json()["choices"][0]["message"]["content"])
        else:
            print("Error:", chat_res.text)

if __name__ == "__main__":
    asyncio.run(test_chat())

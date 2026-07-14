import os
import dotenv
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
import httpx, json, time, uuid

dotenv.load_dotenv()
app = FastAPI()

NIM_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NIM_KEY = "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"
NIM_MODEL = "deepseek-ai/deepseek-v4-pro"
def anthro_to_openai(body):
    msgs = []
    if body.get("system"):
        msgs.append({"role": "system", "content": body["system"]})
    for m in body["messages"]:
        content = m["content"]
        if isinstance(content, list):
            content = "".join(b.get("text","") for b in content if b.get("type")=="text")
        msgs.append({"role": m["role"], "content": content})
    return {
        "model": NIM_MODEL,
        "messages": msgs,
        "max_tokens": body.get("max_tokens", 1024),
        "temperature": body.get("temperature", 1.0),
        "stream": body.get("stream", False),
    }

@app.post("/v1/messages")
async def messages(req: Request):
    body = await req.json()
    oai_body = anthro_to_openai(body)
    headers = {"Authorization": f"Bearer {NIM_KEY}", "Content-Type": "application/json"}

    if oai_body["stream"]:
        async def gen():
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", NIM_URL, json=oai_body, headers=headers) as r:
                    msg_id = f"msg_{uuid.uuid4().hex[:24]}"
                    yield f'event: message_start\ndata: {json.dumps({"type":"message_start","message":{"id":msg_id,"type":"message","role":"assistant","content":[],"model":oai_body["model"]}})}\n\n'
                    yield f'event: content_block_start\ndata: {json.dumps({"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}})}\n\n'
                    async for line in r.aiter_lines():
                        if not line.startswith("data: "): continue
                        data = line[6:]
                        if data.strip() == "[DONE]":
                            break
                        chunk = json.loads(data)
                        delta = chunk["choices"][0]["delta"].get("content","")
                        if delta:
                            yield f'event: content_block_delta\ndata: {json.dumps({"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":delta}})}\n\n'
                    yield f'event: content_block_stop\ndata: {json.dumps({"type":"content_block_stop","index":0})}\n\n'
                    yield f'event: message_delta\ndata: {json.dumps({"type":"message_delta","delta":{"stop_reason":"end_turn"}})}\n\n'
                    yield f'event: message_stop\ndata: {json.dumps({"type":"message_stop"})}\n\n'
        return StreamingResponse(gen(), media_type="text/event-stream")

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(NIM_URL, json=oai_body, headers=headers)
        r.raise_for_status()
        data = r.json()
        text = data["choices"][0]["message"]["content"]
        return JSONResponse({
            "id": f"msg_{uuid.uuid4().hex[:24]}",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": text}],
            "model": oai_body["model"],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": data.get("usage",{}).get("prompt_tokens",0),
                      "output_tokens": data.get("usage",{}).get("completion_tokens",0)}
        })
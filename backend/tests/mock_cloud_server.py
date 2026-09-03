"""Minimal OpenAI-compatible mock server used to verify cloud mode end-to-end.

Run: python mock_cloud_server.py [port]   (default 9009)

Serves /v1/models (model list) and /v1/chat/completions (streaming SSE echo).
"""

import asyncio
import json
import sys

from aiohttp import web

MODELS = [
    {"id": "mock-gpt-4o", "object": "model", "owned_by": "mock"},
    {"id": "mock-gpt-4o-mini", "object": "model", "owned_by": "mock"},
]


async def list_models(request: web.Request) -> web.Response:
    return web.json_response({"object": "list", "data": MODELS})


async def chat_completions(request: web.Request) -> web.StreamResponse:
    body = await request.json()
    stream = body.get("stream", False)
    reply = f"Hello from the mock cloud! You said: {body['messages'][-1]['content']}"

    if not stream:
        return web.json_response(
            {
                "id": "chatcmpl-mock",
                "object": "chat.completion",
                "model": body.get("model", "mock-gpt-4o"),
                "choices": [{"index": 0, "message": {"role": "assistant", "content": reply}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 6, "total_tokens": 10},
            }
        )

    resp = web.StreamResponse(status=200, headers={"Content-Type": "text/event-stream"})
    await resp.prepare(request)
    for word in reply.split(" "):
        chunk = {"choices": [{"index": 0, "delta": {"content": word + " "}, "finish_reason": None}]}
        await resp.write(f"data: {json.dumps(chunk)}\n\n".encode())
    done = {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
    await resp.write(f"data: {json.dumps(done)}\n\n".encode())
    await resp.write(b"data: [DONE]\n\n")
    await resp.write_eof()
    return resp


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9009
    app = web.Application()
    app.router.add_get("/v1/models", list_models)
    app.router.add_post("/v1/chat/completions", chat_completions)
    web.run_app(app, port=port)


if __name__ == "__main__":
    main()
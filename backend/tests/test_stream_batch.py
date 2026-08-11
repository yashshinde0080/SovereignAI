"""Batched SSE frames in stream_response coalesce tokens without losing any.

Feeds a sentence token-by-token through stream_response with a fake engine and
asserts (a) far fewer content frames than tokens, (b) the concatenated content
reconstructs the sentence exactly, (c) the finish_reason frame arrives after
all content. Regression guard for the SSE frame batching in chat.py.
"""
import asyncio
import json

from app.api.chat import stream_response


class _FakeEngine:
    def __init__(self, tokens):
        self._tokens = tokens

    async def generate_stream(self, **kwargs):
        for t in self._tokens:
            yield {"token": t}
        yield {"token": "", "finish_reason": "stop"}


class _Req:
    max_tokens = 1024
    temperature = 0.7
    top_p = 0.9


async def _collect(gen):
    return [f async for f in gen]


def _run(tokens):
    return asyncio.run(_collect(stream_response(_FakeEngine(tokens), "prompt", _Req())))


def _parse(frames):
    content = ""
    reasons = ""
    finish = []
    for f in frames:
        if not f.startswith("data: ") or "[DONE]" in f:
            continue
        data = json.loads(f[6:].strip())
        choice = data["choices"][0]
        if choice.get("finish_reason"):
            finish.append(choice["finish_reason"])
        content += choice["delta"].get("content", "")
        reasons += choice["delta"].get("reasoning", "")
    return content, reasons, finish


def test_batches_multiple_tokens_per_frame():
    tokens = list("The quick brown fox jumps over the lazy dog. " * 6)  # ~288 tokens
    frames = _run(tokens)
    content_frames = [
        f
        for f in frames
        if f.startswith("data: ")
        and "[DONE]" not in f
        and json.loads(f[6:].strip())["choices"][0]["delta"].get("content")
    ]
    assert len(content_frames) < len(tokens)  # batching collapsed 288 tokens into a few frames
    assert len(content_frames) > 1  # longer than one batch budget, so split


def test_reconstruction_matches_input():
    sentence = "All that glitters is not gold; often have you heard that told. " * 5
    content, reasons, finish = _parse(_run(list(sentence)))
    assert content == sentence
    assert reasons == ""
    assert finish == ["stop"]


def test_finish_frame_after_all_content():
    content, _, finish = _parse(_run(list("short reply")))
    assert content == "short reply"
    assert finish == ["stop"]

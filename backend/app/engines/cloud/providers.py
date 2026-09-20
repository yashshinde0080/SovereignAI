"""Provider-specific API translation for cloud mode.

Each provider family gets three small functions:
  - build_chat_request: provider payload for a chat completion
  - parse_chat_response: provider non-stream response -> SovereignAI shape
  - parse_stream_event: one provider SSE payload -> (token, finish_reason)

OpenAI-compatible providers (openai, mistral, custom) share one path;
anthropic and google have their own shapes. Everything stays in plain
dicts — wire format lives here, pydantic schemas in app/schemas/cloud.py.

Errors are raised as fastapi.HTTPException with the status codes mapped in
TODOS.md §10 so callers (chat.py, api/cloud.py) need no provider-specific
handling.
"""

import json
import logging
from typing import Any, Optional, Tuple

from fastapi import HTTPException

logger = logging.getLogger(__name__)

PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "openai": {"base_url": "https://api.openai.com/v1", "label": "OpenAI"},
    "anthropic": {"base_url": "https://api.anthropic.com", "label": "Anthropic"},
    "google": {"base_url": "https://generativelanguage.googleapis.com", "label": "Google"},
    "mistral": {"base_url": "https://api.mistral.ai/v1", "label": "Mistral"},
    "custom": {"base_url": "", "label": "Custom"},
}

OPENAI_COMPAT = ("openai", "mistral", "custom")


def base_url(provider_type: str, configured: Optional[str]) -> str:
    """Effective base URL: configured value wins, else the provider default."""
    if configured and configured.strip():
        return configured.strip().rstrip("/")
    default = PROVIDER_DEFAULTS.get(provider_type, {}).get("base_url", "")
    if not default:
        raise ValueError(f"base_url is required for {provider_type} providers")
    return default


def build_chat_request(
    provider_type: str,
    *,
    messages: list[dict],
    model: str,
    max_tokens: int,
    temperature: float,
    top_p: float,
    stream: bool,
    base: str,
    api_key: str,
) -> Tuple[str, dict, dict]:
    """Build (url, headers, payload) for one chat completion request."""
    if provider_type in OPENAI_COMPAT:
        return (
            f"{base}/chat/completions",
            {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "stream": stream,
            },
        )

    if provider_type == "anthropic":
        system_text = "\n\n".join(
            m["content"] for m in messages if m["role"] == "system"
        )
        # Anthropic wants user/assistant turns only, last turn must be user —
        # merge consecutive same-role turns into one.
        merged: list[dict] = []
        for m in messages:
            if m["role"] not in ("user", "assistant"):
                continue
            if merged and merged[-1]["role"] == m["role"]:
                merged[-1]["content"] += "\n\n" + m["content"]
            else:
                merged.append({"role": m["role"], "content": m["content"]})
        payload: dict[str, Any] = {
            "model": model,
            "messages": merged,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }
        if system_text:
            payload["system"] = system_text
        return (
            f"{base}/v1/messages",
            {"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
            payload,
        )

    if provider_type == "google":
        system_parts = [{"text": m["content"]} for m in messages if m["role"] == "system"]
        contents = [
            {
                "role": "user" if m["role"] == "user" else "model",
                "parts": [{"text": m["content"]}],
            }
            for m in messages
            if m["role"] in ("user", "assistant")
        ]
        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
                "topP": top_p,
            },
        }
        if system_parts:
            payload["systemInstruction"] = {"parts": system_parts}
        return (
            f"{base}/v1beta/models/{model}:generateContent",
            {"x-goog-api-key": api_key, "Content-Type": "application/json"},
            payload,
        )

    raise ValueError(f"Unknown provider type: {provider_type}")


def parse_chat_response(provider_type: str, data: dict) -> dict:
    """Provider non-stream response -> SovereignAI generate() result."""
    if provider_type in OPENAI_COMPAT:
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        finish = choice.get("finish_reason") or "stop"
        usage = data.get("usage") or {}
        return {
            "output": message.get("content") or "",
            "finish_reason": "length" if finish == "length" else "stop",
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }

    if provider_type == "anthropic":
        content = "".join(
            b.get("text", "") for b in (data.get("content") or []) if b.get("type") == "text"
        )
        usage = data.get("usage") or {}
        return {
            "output": content,
            "finish_reason": "length" if data.get("stop_reason") == "max_tokens" else "stop",
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
        }

    if provider_type == "google":
        candidates = data.get("candidates") or []
        parts = ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []
        text = "".join(p.get("text", "") for p in parts)
        usage = data.get("usageMetadata") or {}
        return {
            "output": text,
            "finish_reason": (
                "length" if candidates and candidates[0].get("finishReason") == "MAX_TOKENS" else "stop"
            ),
            "prompt_tokens": usage.get("promptTokenCount", 0),
            "completion_tokens": usage.get("candidatesTokenCount", 0),
            "total_tokens": usage.get("promptTokenCount", 0) + usage.get("candidatesTokenCount", 0),
        }

    raise ValueError(f"Unknown provider type: {provider_type}")


def parse_stream_event(provider_type: str, data: dict) -> Tuple[str, Optional[str]]:
    """One provider SSE payload -> (token, finish_reason). Finish is None
    when the event carries neither."""
    if provider_type in OPENAI_COMPAT:
        choices = data.get("choices") or []
        if not choices:
            return "", None
        choice = choices[0]
        delta = choice.get("delta") or {}
        token = delta.get("content") or ""
        finish = choice.get("finish_reason")
        return token, finish

    if provider_type == "anthropic":
        if data.get("type") == "content_block_delta":
            delta = data.get("delta") or {}
            return delta.get("text") or "", None
        if data.get("type") == "message_delta":
            stop = (data.get("delta") or {}).get("stop_reason")
            if stop:
                return "", "length" if stop == "max_tokens" else "stop"
        return "", None

    if provider_type == "google":
        candidates = data.get("candidates") or []
        if not candidates:
            return "", None
        parts = (candidates[0].get("content") or {}).get("parts") or []
        token = "".join(p.get("text", "") for p in parts)
        reason = candidates[0].get("finishReason")
        finish = None
        if reason == "MAX_TOKENS":
            finish = "length"
        elif reason:
            finish = "stop"
        return token, finish

    raise ValueError(f"Unknown provider type: {provider_type}")


def raise_for_status(provider_name: str, status: int, body: str) -> None:
    """Map a provider HTTP error to the status codes in TODOS.md §10."""
    msg = _extract_error_message(body)
    if status in (401, 403):
        raise HTTPException(401, f"API key rejected by {provider_name}. Check your key.")
    if status == 429:
        raise HTTPException(429, f"Rate limited by {provider_name}. Try again later.")
    if status == 404:
        raise HTTPException(404, f"Model not found on {provider_name}: {msg}")
    if status >= 500:
        raise HTTPException(502, f"{provider_name} server error: {msg}")
    raise HTTPException(status, f"{provider_name} error: {msg}")


def _extract_error_message(body: str) -> str:
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return (body or "")[:200]
    error = data.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or error)[:300]
    if isinstance(error, str):
        return error[:300]
    return str(data)[:300]


async def fetch_models(provider: dict, session) -> list[dict]:
    """Model list for one provider. Raises HTTPException on failure."""
    ptype = provider["provider_type"]
    base = base_url(ptype, provider.get("base_url"))
    key = provider.get("api_key") or ""
    name = provider.get("name", ptype)

    if ptype in OPENAI_COMPAT:
        url = f"{base}/models"
        headers = {"Authorization": f"Bearer {key}"}
    elif ptype == "anthropic":
        url = f"{base}/v1/models"
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
    else:  # google
        url = f"{base}/v1beta/models"
        headers = {"x-goog-api-key": key}

    try:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                raise_for_status(name, resp.status, await resp.text())
            data = await resp.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(504, f"Could not reach {name}: {e}")

    models: list[dict] = []
    if ptype == "google":
        for m in data.get("models") or []:
            methods = m.get("supportedGenerationMethods") or []
            if "generateContent" not in methods:
                continue
            model_id = str(m["name"]).replace("models/", "", 1)
            models.append({
                "id": model_id,
                "name": m.get("displayName") or model_id,
                "context_window": None,
                "supports_streaming": True,
            })
    else:
        for m in data.get("data") or []:
            model_id = m.get("id") or m.get("name") or ""
            if not model_id:
                continue
            models.append({
                "id": model_id,
                "name": m.get("display_name") or model_id,
                "context_window": None,
                "supports_streaming": True,
            })
    return models


async def test_connection(provider: dict, session) -> Tuple[bool, str]:
    """Connectivity + key validity check: fetch the provider model list."""
    try:
        models = await fetch_models(provider, session)
    except HTTPException as e:
        detail = e.detail if isinstance(e.detail, str) else "Connection failed"
        return False, detail
    except Exception as e:
        return False, f"Could not reach {provider.get('name', 'provider')}: {e}"
    return True, f"Connected. {len(models)} models available."
"""CloudAPIEngine — proxy to external chat APIs.

Implements BaseEngine with no local weights: ``generate*`` forwards the
conversation to the provider (OpenAI-compatible / Anthropic / Google) and
re-emits the reply in the SovereignAI chunk format. get_memory_usage() is
all zeros — nothing lives locally.

Provider failures are raised as fastapi.HTTPException with the status codes
mapped in TODOS.md §10, so chat.py needs no provider-specific handling.
"""

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, Optional

import aiohttp
from fastapi import HTTPException

from app.engines.base import BaseEngine
from app.engines.cloud import providers

logger = logging.getLogger(__name__)


class CloudAPIEngine(BaseEngine):
    """Remote-inference engine: the "model" is a provider API endpoint."""

    def __init__(
        self,
        model_path: str,
        hardware: Dict[str, Any],
        memory_manager: Any,
        provider: Optional[dict] = None,
        model_id: Optional[str] = None,
    ):
        super().__init__(model_path, hardware, memory_manager)
        self.mode = "cloud"
        self.experimental = False
        self.provider = provider or {}
        self.model_id = model_id or model_path
        self.task_metadata = {
            "task_type": "causal_lm",
            "is_generative": True,
            "input_modality": "text",
        }
        self._http: Optional[aiohttp.ClientSession] = None

    def _session(self) -> aiohttp.ClientSession:
        if self._http is None or getattr(self._http, "closed", False):
            self._http = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300))
        return self._http

    async def load(self):
        """Validate the API key and fetch the model list — nothing local loads."""
        if not self.provider.get("api_key"):
            raise HTTPException(
                400,
                "No API key configured. Add one via Settings → Cloud / Online "
                "or 'sovereign cloud add'.",
            )
        ok, message = await providers.test_connection(self.provider, self._session())
        if not ok:
            raise HTTPException(502, message)
        self.loaded = True
        self.stats["provider"] = self.provider.get("name")
        self.stats["model"] = self.model_id
        logger.info(
            "Cloud engine ready: %s/%s via %s",
            self.provider.get("name"), self.model_id, self.provider.get("provider_type"),
        )

    async def unload(self):
        if self._http is not None:
            await self._http.close()
            self._http = None
        self.loaded = False

    def _messages(self, input_data: Any) -> list[dict]:
        """Normalize whatever chat.py / execute passes into message dicts."""
        if isinstance(input_data, list):
            return [{"role": m["role"], "content": m["content"]} for m in input_data]
        if isinstance(input_data, dict) and "messages" in input_data:
            return self._messages(input_data["messages"])
        if isinstance(input_data, dict) and "prompt" in input_data:
            return [{"role": "user", "content": input_data["prompt"]}]
        return [{"role": "user", "content": str(input_data)}]

    def _request_kwargs(self, input_data: Any, stream: bool, kwargs: dict) -> tuple[str, dict, dict]:
        return providers.build_chat_request(
            self.provider["provider_type"],
            messages=self._messages(input_data),
            model=self.model_id,
            max_tokens=int(kwargs.get("max_tokens", 512)),
            temperature=float(kwargs.get("temperature", 0.7)),
            top_p=float(kwargs.get("top_p", 0.9)),
            stream=stream,
            base=providers.base_url(self.provider["provider_type"], self.provider.get("base_url")),
            api_key=self.provider.get("api_key", ""),
        )

    async def generate(self, input_data: Any, **kwargs) -> Dict[str, Any]:
        if not self.loaded:
            raise RuntimeError("Model not loaded")
        url, headers, payload = self._request_kwargs(input_data, stream=False, kwargs=kwargs)
        try:
            async with self._session().post(url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    providers.raise_for_status(self.provider.get("name", "provider"), resp.status, await resp.text())
                data = await resp.json()
        except asyncio.TimeoutError:
            raise HTTPException(504, f"Could not reach {self.provider.get('name', 'provider')}. Check your network.")
        except aiohttp.ClientError as e:
            raise HTTPException(504, f"Could not reach {self.provider.get('name', 'provider')}: {e}")

        result = providers.parse_chat_response(self.provider["provider_type"], data)
        result["model_name"] = self.model_id
        return result

    async def generate_stream(self, input_data: Any, **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        if not self.loaded:
            raise RuntimeError("Model not loaded")
        url, headers, payload = self._request_kwargs(input_data, stream=True, kwargs=kwargs)
        try:
            async with self._session().post(
                url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=None, sock_read=180),
            ) as resp:
                if resp.status != 200:
                    providers.raise_for_status(self.provider.get("name", "provider"), resp.status, await resp.text())
                finished = False
                async for line in resp.content:
                    if not line:
                        continue
                    text = line.decode("utf-8", errors="replace").strip()
                    if not text.startswith("data:"):
                        continue
                    data_str = text[len("data:"):].strip()
                    if not data_str or data_str == "[DONE]":
                        break
                    try:
                        event = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    token, finish = providers.parse_stream_event(self.provider["provider_type"], event)
                    if token:
                        yield {"token": token, "finish_reason": None}
                    if finish:
                        yield {"token": "", "finish_reason": finish}
                        finished = True
                        break
        except asyncio.TimeoutError:
            raise HTTPException(504, f"Could not reach {self.provider.get('name', 'provider')}. Check your network.")
        except aiohttp.ClientError as e:
            raise HTTPException(504, f"Could not reach {self.provider.get('name', 'provider')}: {e}")

        if not finished:
            yield {"token": "", "finish_reason": "stop"}

    def get_memory_usage(self) -> Dict[str, Any]:
        """No local weights — everything runs on the provider's hardware."""
        return {"ram_used_gb": 0, "kv_cache_mb": 0, "remote": True}
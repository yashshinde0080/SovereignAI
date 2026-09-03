"""Cloud provider management endpoints — /v1/cloud/*.

Provider config lives in sovereign_settings.db (API keys Fernet-encrypted at
rest, masked in every response). Model lists are fetched live from each
enabled provider on demand — nothing is cached locally.
"""

import asyncio
import logging
from urllib.parse import urlparse

import aiohttp
from fastapi import APIRouter, HTTPException, Request

from app.engines.cloud import providers
from app.engines.cloud.registry import CloudProviderRegistry
from app.schemas.cloud import (
    CloudModelList,
    CloudProviderCreate,
    CloudProviderOut,
    CloudProviderUpdate,
    CloudTestResult,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cloud", tags=["cloud"])


def _registry(request: Request) -> CloudProviderRegistry:
    """Registry from app.state (set in lifespan); fresh fallback for tests."""
    reg = getattr(request.app.state, "cloud_provider_registry", None)
    return reg or CloudProviderRegistry()


def _check_base_url(provider_type: str, base_url) -> None:
    """custom providers need a base_url; plain-HTTP URLs only allowed on localhost."""
    if provider_type == "custom" and not (base_url or "").strip():
        raise HTTPException(
            400,
            "base_url is required for custom providers (e.g. http://localhost:11434/v1)",
        )
    if not base_url:
        return
    parsed = urlparse(base_url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(400, f"base_url must be http(s), got: {base_url}")
    if parsed.scheme != "https" and host not in ("localhost", "127.0.0.1"):
        raise HTTPException(400, "base_url must use HTTPS (http allowed only for localhost endpoints)")


def _out(provider: dict) -> CloudProviderOut:
    data = dict(provider)
    data.pop("api_key", None)  # never leak the decrypted key
    return CloudProviderOut(**data)


# ── providers ──

@router.get("/providers")
async def list_providers(request: Request):
    """All configured providers — keys masked."""
    return {"providers": _registry(request).list_providers()}


@router.post("/providers", response_model=CloudProviderOut)
async def add_provider(request: Request, cfg: CloudProviderCreate):
    """Add a provider. Keys are encrypted at rest; validate with /test/{id}."""
    _check_base_url(cfg.provider_type, cfg.base_url)
    provider = _registry(request).add_provider(
        name=cfg.name or cfg.provider_type.capitalize(),
        provider_type=cfg.provider_type,
        api_key=cfg.api_key or "",
        base_url=cfg.base_url,
        is_enabled=cfg.is_enabled,
        rate_limit_rpm=cfg.rate_limit_rpm,
    )
    return _out(provider)


@router.put("/providers/{provider_id}", response_model=CloudProviderOut)
async def update_provider(request: Request, provider_id: str, updates: CloudProviderUpdate):
    """Update a provider (partial patch). Re-enter the key to rotate it."""
    registry = _registry(request)
    current = registry.get_provider(provider_id)
    if current is None:
        raise HTTPException(404, f"Provider '{provider_id}' not found")
    if updates.base_url is not None:
        _check_base_url(current["provider_type"], updates.base_url)
    updated = registry.update_provider(provider_id, updates.model_dump(exclude_unset=True))
    return _out(updated)


@router.delete("/providers/{provider_id}")
async def delete_provider(request: Request, provider_id: str):
    if not _registry(request).delete_provider(provider_id):
        raise HTTPException(404, f"Provider '{provider_id}' not found")
    return {"status": "deleted", "provider_id": provider_id}


# ── models ──

async def _fetch_provider_models(provider: dict) -> list[dict]:
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        return await providers.fetch_models(provider, session)


@router.get("/models", response_model=CloudModelList)
async def list_cloud_models(request: Request):
    """Model list across all enabled providers (failed providers are skipped)."""
    registry = _registry(request)
    provider_configs = registry.get_enabled_providers()

    async def _one(provider: dict) -> list[dict]:
        try:
            return [
                {**m, "provider_id": provider["id"], "provider_type": provider["provider_type"]}
                for m in await _fetch_provider_models(provider)
            ]
        except HTTPException as e:
            logger.warning("Cloud models: %s skipped (%s)", provider["name"], e.detail)
            return []
        except Exception as e:
            logger.warning("Cloud models: %s skipped (%s)", provider["name"], e)
            return []

    results = await asyncio.gather(*(_one(p) for p in provider_configs))
    return CloudModelList(models=[m for r in results for m in r])


@router.post("/models/refresh")
async def refresh_cloud_models(request: Request):
    """Re-fetch model lists from all enabled providers (same as GET /models)."""
    result = await list_cloud_models(request)
    return {"status": "refreshed", "count": len(result.models)}


@router.get("/models/{provider_id}", response_model=CloudModelList)
async def provider_models(request: Request, provider_id: str):
    """Model list for one specific provider."""
    registry = _registry(request)
    provider = registry.get_provider(provider_id)
    if provider is None:
        raise HTTPException(404, f"Provider '{provider_id}' not found")
    if not provider.get("is_enabled"):
        raise HTTPException(400, f"Provider '{provider_id}' is disabled")
    models = await _fetch_provider_models(provider)
    return CloudModelList(models=[
        {**m, "provider_id": provider["id"], "provider_type": provider["provider_type"]}
        for m in models
    ])


# ── connectivity ──

@router.post("/test/{provider_id}", response_model=CloudTestResult)
async def test_provider(request: Request, provider_id: str):
    """Test API key validity + connectivity for a provider."""
    provider = _registry(request).get_provider(provider_id)
    if provider is None:
        raise HTTPException(404, f"Provider '{provider_id}' not found")
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        ok, message = await providers.test_connection(provider, session)
    return CloudTestResult(ok=ok, message=message)
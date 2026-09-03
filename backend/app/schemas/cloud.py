"""Cloud provider / model schemas."""

from typing import Literal, Optional
from pydantic import BaseModel, Field

ProviderType = Literal["openai", "anthropic", "google", "mistral", "custom"]


class CloudProviderCreate(BaseModel):
    name: str = ""
    provider_type: ProviderType
    api_key: str = Field(default="", description="Write-only — never returned in GET responses")
    base_url: Optional[str] = None
    is_enabled: bool = True
    rate_limit_rpm: int = Field(default=60, ge=1, le=100000)


class CloudProviderUpdate(BaseModel):
    name: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    is_enabled: Optional[bool] = None
    rate_limit_rpm: Optional[int] = Field(default=None, ge=1, le=100000)


class CloudProviderOut(BaseModel):
    """Provider as seen by clients — key is masked, never the raw value."""
    id: str
    name: str
    provider_type: str
    api_key_masked: str
    base_url: Optional[str] = None
    is_enabled: bool
    rate_limit_rpm: int


class CloudModel(BaseModel):
    id: str
    name: str
    provider_id: str
    provider_type: str
    context_window: Optional[int] = None
    supports_streaming: bool = True
    supports_vision: bool = False


class CloudModelList(BaseModel):
    models: list[CloudModel]


class CloudTestResult(BaseModel):
    ok: bool
    message: str
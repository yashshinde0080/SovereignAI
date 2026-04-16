"""Configuration Management"""
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application Settings"""
    
    # Application
    app_name: str = "SovereignAI Edge"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # Server
    host: str = "127.0.0.1"
    port: int = 8000
    
    # Paths
    base_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent)
    workspace_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent / "workspace")
    models_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent / "workspace" / "models")
    plugins_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent / "workspace" / "plugins")
    database_path: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent / "workspace" / "database" / "sovereign.db")
    data_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent / "workspace" / "data")
    
    # Memory
    max_ram_usage_percent: float = 0.75
    layer_prefetch_count: int = 2
    kv_cache_max_mb: int = 2048
    
    # Security
    encryption_enabled: bool = True
    audit_logging: bool = True
    
    # Model Defaults
    default_quant: str = "Q4_K_M"
    default_mode: str = "auto"
    
    class Config:
        env_prefix = "SOVEREIGN_"
        env_file = ".env"


settings = Settings()

# Ensure directories exist
settings.models_dir.mkdir(parents=True, exist_ok=True)
settings.workspace_dir.mkdir(parents=True, exist_ok=True)
settings.plugins_dir.mkdir(parents=True, exist_ok=True)
settings.database_path.parent.mkdir(parents=True, exist_ok=True)
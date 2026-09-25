"""Configuration Management"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict


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
    # Execute custom modeling code shipped inside a model repo (can run
    # arbitrary Python). Off by default — enable only for trusted repos.
    trust_remote_code: bool = False
    
    # Custom model catalog (enterprise / USB YAML definitions)
    catalog_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent / "workspace" / "plugins" / "user" / "models")

    # Model Defaults
    default_quant: str = "Q4_K_M"
    default_mode: str = "auto"

    # TurboQuant KV Cache Compression
    #
    # OFF by default, and it must stay off until the accuracy gate passes.
    # benchmarks/accuracy_eval.py FAILS on Qwen2-0.5B and Pythia-70m at every
    # bit rate: the shipped codebook uses uniform centroids instead of the
    # paper's Beta Lloyd-Max, and the QJL decode scaling is near-no-op (so the
    # compression is nowhere near the 6x claim).
    #
    # There is no runtime check that catches the resulting quality loss — the
    # model still generates, just worse. See
    # reviews/autoplan-report-2026-08-09.md before flipping this.
    #
    # (An earlier comment here blamed "no bit-packing yet"; bit-packing is in
    # fact implemented — see TurboQuantConfig.bit_pack — which made the real
    # blocker harder to find.)
    turboquant_enabled: bool = False
    turboquant_bits: float = 3.5
    turboquant_qjl_enabled: bool = True

    model_config = ConfigDict(env_prefix="SOVEREIGN_", env_file=".env")


settings = Settings()

# Ensure directories exist — best-effort; read-only USBs skip gracefully.
for _d in (settings.models_dir, settings.workspace_dir, settings.catalog_dir,
           settings.plugins_dir, settings.database_path.parent):
    try:
        _d.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

# Keep HuggingFace tokenizer/config/module caches on the pendrive (portable USB).
# setdefault → an externally-set HF_HOME (e.g. launch script) wins.
os.environ.setdefault("HF_HOME", str(settings.workspace_dir / "hf_cache"))
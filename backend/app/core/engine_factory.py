"""Engine Factory"""
from typing import Dict, Any, Optional
from pathlib import Path
import json
import os

from app.core.memory_manager import MemoryManager
from app.engines.base import BaseEngine
from app.engines.fullram.executor import FullRAMEngine
from app.engines.layerstream.executor import LayerStreamEngine


class EngineFactory:
    """Factory for creating inference engines"""

    # ponytail: single MemoryManager per session — hardware doesn't change
    _shared_memory_manager: Optional[MemoryManager] = None

    def __init__(self, hardware_profile: Dict[str, Any]):
        self.hardware = hardware_profile
        if EngineFactory._shared_memory_manager is None:
            EngineFactory._shared_memory_manager = MemoryManager()
        self.memory_manager = EngineFactory._shared_memory_manager
    
    async def create_engine(
        self,
        model_path: str,
        mode: str = "auto",
        model_metadata: Optional[Dict[str, Any]] = None,
    ) -> BaseEngine:
        """Create appropriate engine"""

        # Cloud mode has no local files — model_path is "{provider_id}/{model_id}".
        # Resolve the provider from the registry and return early (before any
        # filesystem path handling mangles the provider/model id).
        if mode == "cloud":
            parts = str(model_path).split("/", 1)
            if len(parts) != 2 or not parts[0] or not parts[1]:
                raise ValueError(
                    f"Cloud model must be '<provider_id>/<model_id>', got: {model_path}"
                )
            provider_id, model_id = parts
            from app.engines.cloud import registry as cloud_registry
            # ponytail: fresh registry per load — one sqlite conn, GC'd after.
            provider = cloud_registry.CloudProviderRegistry().get_provider(provider_id)
            if provider is None:
                raise ValueError(f"Provider '{provider_id}' not found")
            from app.engines.cloud.engine import CloudAPIEngine
            return CloudAPIEngine(
                model_path=str(model_path),
                hardware=self.hardware,
                memory_manager=self.memory_manager,
                provider=provider,
                model_id=model_id,
            )

        model_path = Path(model_path)
        engine_model_path_str = str(model_path)

        # Use size_gb from registry metadata when available — avoids an O(n)
        # rglob scan across the entire model directory.
        model_size = 0
        if model_metadata and model_metadata.get("size_gb"):
            try:
                model_size = int(float(model_metadata["size_gb"]) * (1024**3))
            except (TypeError, ValueError):
                pass

        # If directory, determine model size correctly and ensure we pass the correct directory
        if model_path.is_dir():
             # If config.json exists, this is a standard HuggingFace repo
             if (model_path / "config.json").exists():
                 engine_model_path_str = str(model_path)
                 if not model_size:
                     # ponytail: os.scandir 2-level is faster than rglob for shallow HF repos
                     for entry in os.scandir(model_path):
                         if entry.is_file(follow_symlinks=False):
                             model_size += entry.stat().st_size
                         elif entry.is_dir(follow_symlinks=False):
                             for sub in os.scandir(entry):
                                 if sub.is_file(follow_symlinks=False):
                                     model_size += sub.stat().st_size
             else:
                 # Try to find GGUF or SafeTensors as fallback for size calculations
                 gguf_files = list(model_path.glob("*.gguf")) + list(model_path.glob("*.gguf.enc"))
                 if gguf_files:
                     engine_model_path_str = str(gguf_files[0])
                     if not model_size:
                         model_size = gguf_files[0].stat().st_size
                 else:
                     st_files = list(model_path.glob("*.safetensors")) + list(model_path.glob("*.safetensors.enc"))
                     if st_files:
                         engine_model_path_str = str(model_path)
                         if not model_size:
                             model_size = sum(f.stat().st_size for f in st_files)
        else:
            if not model_size:
                model_size = model_path.stat().st_size if model_path.exists() and model_path.is_file() else 0
            engine_model_path_str = str(model_path)
            
        # 1. Resolve task to determine if streaming is possible
        # For GGUF files, resolve from the parent dir (config.json lives there)
        from app.core.task_resolver import TaskResolver
        resolve_path = engine_model_path_str
        if engine_model_path_str.endswith(('.gguf', '.gguf.enc')):
            resolve_path = str(model_path.parent)
        task_metadata = TaskResolver.resolve(resolve_path)
        is_generative = task_metadata.get("is_generative", False)

        # Determine mode
        if mode == "auto":
            # Use llmfit scoring when metadata available, else legacy size-based
            if model_metadata:
                suggested = self.memory_manager.suggest_mode(
                    model_size, model_metadata=model_metadata
                )
            else:
                suggested = self.memory_manager.suggest_mode(model_size)
            if suggested == "layerstream" and not is_generative:
                # Fallback to fullram for non-generative tasks if layerstream suggested
                mode = "fullram"
            else:
                mode = suggested
                
            if mode == "insufficient":
                raise RuntimeError("Insufficient memory for any execution mode")
        
        # Read quant_method from model metadata (set during download).
        # Maps GGUF quant strings (Q4_K_M, Q5_K_M, Q8_0) to quant_method="gguf".
        quant_method = "none"
        metadata_path = model_path / "metadata.json" if isinstance(model_path, Path) else None
        if metadata_path and metadata_path.exists():
            try:
                with open(metadata_path) as f:
                    metadata = json.load(f)
                quant_method = metadata.get("quant_method", "none")
            except Exception:
                quant_method = "none"

        # Create engine
        if mode == "fullram":
            engine = FullRAMEngine(
                model_path=engine_model_path_str,
                hardware=self.hardware,
                memory_manager=self.memory_manager,
                task_metadata=task_metadata,
            )
        elif mode == "layerstream":
            engine = LayerStreamEngine(
                model_path=engine_model_path_str,
                hardware=self.hardware,
                memory_manager=self.memory_manager,
                quant_method=quant_method
            )
        else:
            raise ValueError(f"Unknown mode: {mode}")
        
        return engine
    
    def get_recommended_mode(self, model_size_bytes: int) -> str:
        """Get recommended mode for model"""
        return self.memory_manager.suggest_mode(model_size_bytes)
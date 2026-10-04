"""Model Management Service"""
import os
import json
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

from app.config import settings
from app.services.registry import ModelRegistry
from app.security.encryption import ModelEncryption
from app.providers.huggingface import HuggingFaceProvider
from app.providers.custom_catalog import CustomModelCatalog


def _model_size_bytes(model: Dict[str, Any]) -> int:
    """Approximate model size in bytes from registry metadata (0 = unknown)."""
    size_gb = model.get("size_gb")
    if size_gb:
        try:
            return int(float(size_gb) * (1024**3))
        except (TypeError, ValueError):
            pass
    return 0


def _fuzzy_match_model(models: List[Dict[str, Any]], model_id: str) -> Optional[Dict[str, Any]]:
    """Resolve a model id that wasn't found in the registry directly.

    Normalizes slashes/colons, prefers an exact normalized match, then a
    containment match. ``split:`` variants never win a fuzzy match — they are
    derived views of a base model, so a display-name request like
    "Qwen3.5-0.8B" must resolve to the base model rather than the split copy
    (otherwise ``app.state.active_model`` ends up as a different id than the
    one the caller asked for). Explicit "split:..." requests still resolve
    through the direct registry lookup before this is called.
    """
    clean_request = model_id.replace("/", "-").replace(":", "-").lower()
    stripped_req = clean_request.replace("split-", "")

    for m in models:
        if m["id"].startswith("split:"):
            continue  # prefer the base model over split variants
        clean_m = m["id"].replace("/", "-").replace(":", "-").lower()
        if clean_m == clean_request:
            return m  # exact normalized match wins outright
        if clean_m.replace("split-", "") == stripped_req:
            return m  # exact match modulo the split: prefix
        if stripped_req in clean_m or clean_m in stripped_req:
            return m  # first containment match (base models only)
    return None


class ModelManager:
    """Manage model lifecycle"""
    
    HUGGINGFACE_API = "https://huggingface.co/api/models"
    
    def __init__(self, settings_service=None):
        self.settings_service = settings_service
        self.models_dir = settings.models_dir
        self.registry = ModelRegistry(settings.database_path)
        # encrypt_models switch (security section) decides whether the
        # ModelEncryption helper is even constructed; cloud key storage keeps
        # its own ModelEncryption instance regardless.
        self.encryption = None  # set in initialize(), after settings linked
        self._encrypt_models = True
        
        self.download_status: Dict[str, Dict[str, Any]] = {}
        self._download_tasks: Dict[str, asyncio.Task] = {}
        # Serialize model loads: two concurrent load requests would both unload
        # the active engine and fight over app.state (one wins, one leaks).
        # ponytail: single global lock, per-model locks if concurrency matters.
        self._load_lock = asyncio.Lock()
        
        self.provider = HuggingFaceProvider()
    
    def _setting(self, section_getter, key, default):
        """Read one settings key; broken/absent settings service = default."""
        if self.settings_service is None:
            return default
        try:
            return (section_getter() or {}).get(key, default)
        except Exception:
            return default

    def _encrypt_models_enabled(self) -> bool:
        return bool(
            self._setting(
                lambda: self.settings_service.get_security(),
                "encrypt_models",
                True,
            )
        )

    def _check_allowed_models(self, model_id: str) -> None:
        """Parental controls: allowed_models non-empty = allowlist (local models only)."""
        allowed = self._setting(
            lambda: self.settings_service.get_parental_controls(),
            "allowed_models",
            [],
        )
        if allowed:
            clean = model_id.replace("/", "-").replace(":", "-").lower()
            norm = [str(a).replace("/", "-").replace(":", "-").lower() for a in allowed]
            if clean not in norm and not any(a in clean or clean in a for a in norm):
                raise PermissionError(
                    f"Model '{model_id}' is blocked by parental controls (allowed models list)."
                )

    async def initialize(self, app=None):
        """Initialize model manager with app reference for engine state"""
        if app is not None:
            self.settings_service = getattr(app.state, "settings_service", None)
        self._encrypt_models = self._encrypt_models_enabled()
        self.encryption = ModelEncryption() if self._encrypt_models else None
        self.app = app
        await self.registry.initialize()
        await self.provider.initialize()
        
        # Load custom model catalogs (enterprise / USB YAML definitions)
        catalog = CustomModelCatalog()
        n = catalog.load_directory(settings.catalog_dir)
        if n:
            logger.info("Custom model catalog: %s models loaded from %s", n, settings.catalog_dir)

        # Scan for models in background so the server starts immediately.
        # load_model() awaits _scan_task before loading, so startup model
        # still loads correctly after the scan finishes.
        self._scan_task: Optional[asyncio.Task] = None
        self._scan_task = asyncio.ensure_future(self.scan_installed())
    
    async def scan_installed(self):
        """Scan models directory for installed models and sync with registry"""
        installed_dir = self.models_dir / "installed"
        installed_dir.mkdir(parents=True, exist_ok=True)
        
        folders = [d for d in installed_dir.iterdir() if d.is_dir()]
        gguf_files = list(installed_dir.glob("*.gguf")) + list(installed_dir.glob("*.gguf.enc"))
        
        # Collect all discovered metadata, then batch-upsert once.
        # This replaces N individual add_model() calls (each opening its own
        # DB connection + commit) with a single transaction.
        discovered: List[Dict[str, Any]] = []
        installed_ids: List[str] = []
        
        # Scan folders
        for model_dir in folders:
            metadata_path = model_dir / "metadata.json"
            metadata = None
            
            if metadata_path.exists():
                try:
                    with open(metadata_path) as f:
                        metadata = json.load(f)
                    
                    # Sync path with current filesystem location
                    if "path" in metadata:
                        original_path = Path(metadata["path"])
                        if not original_path.exists():
                            # If direct path fails, assume it's this directory
                            metadata["path"] = str(model_dir)
                except Exception as e:
                    print(f"Error reading metadata for {model_dir}: {e}")
                    pass
            
            if not metadata:
                # Try to discover model manually if metadata is missing
                metadata = await self._discover_model(model_dir)
            
            if metadata:
                logger.info("SCAN: Found model %s at %s", metadata['id'], metadata['path'])
                discovered.append(metadata)
                installed_ids.append(metadata["id"])

        # Scan standalone GGUF files
        for gguf_path in gguf_files:
            model_id = gguf_path.name
            metadata = {
                "id": model_id,
                "name": gguf_path.name,
                "family": "gguf",
                "parameters": "unknown",
                "quant": "unknown",
                "size_gb": round(gguf_path.stat().st_size / (1024**3), 2),
                "path": str(gguf_path),
                "downloaded": True,
                "modes_supported": ["fullram", "layerstream"],
                "created_at": datetime.now().isoformat()
            }
            logger.info("SCAN: Found GGUF model %s at %s", model_id, gguf_path)
            discovered.append(metadata)
            installed_ids.append(model_id)
        
        # ALSO SCAN OFFLOAD CACHE
        cache_dir = settings.workspace_dir / "offload_cache"
        if cache_dir.exists():
            for cache_model_dir in cache_dir.iterdir():
                if cache_model_dir.is_dir():
                    # Check if it looks like a pre-split model
                    if (cache_model_dir / "embed.safetensors").exists():
                        model_id = f"split:{cache_model_dir.name}"
                        metadata_path = cache_model_dir / "metadata.json"
                        metadata = None
                        
                        if metadata_path.exists():
                            try:
                                with open(metadata_path) as f:
                                    metadata = json.load(f)
                                metadata["id"] = model_id # Force prefix
                                metadata["path"] = str(cache_model_dir)
                            except (OSError, json.JSONDecodeError, ValueError):
                                pass
                            
                        if not metadata:
                            # Create minimal metadata
                            metadata = {
                                "id": model_id,
                                "name": f"{cache_model_dir.name} (Split)",
                                "family": "split",
                                "parameters": "unknown",
                                "quant": "fp16",
                                "size_gb": round(sum(f.stat().st_size for f in cache_model_dir.glob("*.safetensors")) / (1024**3), 2),
                                "path": str(cache_model_dir),
                                "downloaded": True,
                                "modes_supported": ["layerstream"],
                                "created_at": datetime.now().isoformat()
                            }
                        
                        logger.info("SCAN: Found split model %s at %s", model_id, metadata['path'])
                        discovered.append(metadata)
                        installed_ids.append(model_id)

        # Single batch upsert — one DB connection, one commit
        if discovered:
            await self.registry.bulk_upsert(discovered)

        # Cleanup registry: remove models that no longer exist on disk
        installed_set = set(installed_ids)
        db_models = await self.registry.list_models()
        stale_ids = [
            db_m["id"] for db_m in db_models
            if db_m["id"] not in installed_set and not Path(db_m["path"]).exists()
        ]
        for stale_id in stale_ids:
            await self.registry.delete_model(stale_id)

    async def _discover_model(self, model_dir: Path) -> Optional[Dict[str, Any]]:
        """Try to discover model information from a directory"""
        # Look for config.json (HF repo)
        config_path = model_dir / "config.json"
        
        # ID strategy: use folder name if metadata is missing
        # If folder follows name-repo format from download_model, it will stay as is
        model_id = model_dir.name 
        
        if config_path.exists():
            # HF repo
            model_type = "unknown"
            try:
                with open(config_path) as f:
                    config = json.load(f)
                model_type = config.get("model_type", "unknown")
            except Exception:
                pass
            
            # Calculate size with os.scandir (faster than rglob for deep trees)
            size_bytes = 0
            try:
                for entry in os.scandir(model_dir):
                    if entry.is_file(follow_symlinks=False):
                        size_bytes += entry.stat().st_size
                    elif entry.is_dir(follow_symlinks=False):
                        for sub in os.scandir(entry):
                            if sub.is_file(follow_symlinks=False):
                                size_bytes += sub.stat().st_size
            except OSError:
                pass
            
            return {
                "id": model_id,
                "name": model_dir.name,
                "family": model_type,
                "parameters": "unknown",
                "quant": "none",
                "size_gb": round(size_bytes / (1024**3), 2),
                "path": str(model_dir),
                "downloaded": True,
                "modes_supported": ["fullram", "layerstream"],
                "created_at": datetime.now().isoformat()
            }
        
        # Look for .gguf files
        gguf_files = list(model_dir.glob("*.gguf"))
        if gguf_files:
            gguf_path = gguf_files[0]
            return {
                "id": model_id,
                "name": model_id,
                "family": "gguf",
                "parameters": "unknown",
                "quant": "unknown",
                "size_gb": round(gguf_path.stat().st_size / (1024**3), 2),
                "path": str(gguf_path),
                "downloaded": True,
                "modes_supported": ["fullram", "layerstream"],
                "created_at": datetime.now().isoformat()
            }
            
        return None
    
    async def load_model(self, model_id: str, mode: str = "auto") -> Dict[str, Any]:
        """Unified load logic with hardware check"""

        logger.info("LOAD: Request for model %s (mode=%s)", model_id, mode)

        # Cloud models live in the provider registry, not on disk — skip the
        # local registry/scan entirely and let the factory resolve the provider.
        if mode == "cloud":
            if not self.app:
                raise RuntimeError("ModelManager not linked to FastAPI application state")
            async with self._load_lock:
                return await self._load_model_locked(
                    model_id, "cloud", {"id": model_id, "path": model_id}, model_id, []
                )

        # Try to find the model from the existing registry FIRST.
        # Only await the background scan if the model isn't known yet.
        all_models = await self.list_models()
        models_by_id = {m["id"]: m for m in all_models}
        model = models_by_id.get(model_id)

        if not model:
            # Fuzzy match: some callers pass display names or dash-replaced ids
            model = _fuzzy_match_model(all_models, model_id)
            if model:
                logger.info("LOAD: Fuzzy matched %s to %s", model_id, model['id'])
                model_id = model["id"]

        if not model:
            # Model not in registry yet — wait for scan to finish
            scan_task = getattr(self, "_scan_task", None)
            if scan_task and not scan_task.done():
                logger.info("LOAD: Model not in registry, waiting for scan...")
                await scan_task
                all_models = await self.list_models()
                models_by_id = {m["id"]: m for m in all_models}
                model = models_by_id.get(model_id)
                if not model:
                    model = _fuzzy_match_model(all_models, model_id)
                    if model:
                        model_id = model["id"]

        if not model:
            logger.warning("LOAD: Model %s not found in registry", model_id)
            raise ValueError(f"Model {model_id} not found in registry")
            
        if not self.app:
            raise RuntimeError("ModelManager not linked to FastAPI application state")

        self._check_allowed_models(model_id)

        async with self._load_lock:
            return await self._load_model_locked(model_id, mode, model, model_id, all_models)

    async def _load_model_locked(
        self,
        model_id: str,
        mode: str,
        model: Dict[str, Any],
        resolved_id: str,
        all_models: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Body of load_model, run under the concurrent-load lock."""
        from app.core.engine_factory import EngineFactory

        # Save previous engine so we can restore it if the new load fails.
        prev_engine = self.app.state.active_engine
        prev_model = self.app.state.active_model
        prev_mode = self.app.state.active_mode

        # Split models are stored in offload_cache as per-layer safetensors and
        # only support the LayerStream engine. auto must never hand them to
        # fullram (which would look for a consolidated model.safetensors that
        # only exists in the base model dir).
        if mode == "auto" and model["id"].startswith("split:"):
            mode = "layerstream"

        # If we're in fullram mode but selected a split model, try to use the base model
        model_path = model["path"]
        if mode == "fullram" and model["id"].startswith("split:"):
            target_base = model["id"].replace("split:", "")

            # Reuse fuzzy matching logic to find the base model — uses all_models
            # passed from load_model() instead of querying the registry again.
            clean_target = target_base.replace("/", "-").replace(":", "-").lower()

            base_model = None
            for m in all_models:
                # Don't match against other split models
                if m["id"].startswith("split:"):
                    continue

                clean_m = m["id"].replace("/", "-").replace(":", "-").lower()
                if clean_m == clean_target:
                    base_model = m
                    break

            if base_model:
                logger.info("LOAD: Switching to base model %s path for fullram mode", base_model['id'])
                model_path = base_model["path"]

        # LayerStream is experimental: FullRAM is the default for models that
        # fit (measured 2026-08-16: 3.84 tok/s FullRAM CPU vs 0.40 LayerStream).
        # Flag it loudly so experimental loads are visible in server logs.
        if mode == "layerstream":
            logger.warning(
                "LOAD: LayerStream is experimental (measured ~0.4 tok/s on the dev box); "
                "FullRAM is the default for fitting models"
            )

        # Disk-full preflight for LayerStream: swap needs ~model-size of free
        # disk in the offload cache; fail before loading, not mid-generation.
        if mode == "layerstream":
            import shutil
            free_bytes = shutil.disk_usage(settings.workspace_dir).free
            need_bytes = _model_size_bytes(model)
            if need_bytes and free_bytes < need_bytes:
                raise RuntimeError(
                    "Not enough free disk space for LayerStream swap cache "
                    f"(need ~{need_bytes / (1024**3):.1f} GB, have "
                    f"{free_bytes / (1024**3):.1f} GB). Free space or use FullRAM."
                )

        # Initialize engine (pass metadata for llmfit scoring). EngineFactory
        # only creates; the caller owns load() so error mapping stays here.
        # Pass model_metadata so EngineFactory uses size_gb from registry instead
        # of recalculating via rglob, and so TaskResolver only runs once.
        factory = EngineFactory(self.app.state.hardware_profile)
        engine = await factory.create_engine(
            model_path=model_path,
            mode=mode,
            model_metadata=model,
        )
        try:
            await engine.load()
        except Exception:
            await engine.unload()
            # Restore the previous engine so the user doesn't lose their model.
            self.app.state.active_engine = prev_engine
            self.app.state.active_model = prev_model
            self.app.state.active_mode = prev_mode
            raise

        # New engine loaded — unload the old one.
        if prev_engine is not None:
            try:
                await prev_engine.unload()
            except Exception:
                logger.warning("Failed to unload previous engine during model switch")

        # Update app state
        self.app.state.active_engine = engine
        self.app.state.active_model = model_id
        self.app.state.active_mode = engine.mode

        return {
            "status": "loaded",
            "model": model_id,
            "mode": engine.mode,
            "experimental": getattr(engine, "experimental", False),
            "metadata": getattr(engine, "task_metadata", {})
        }
        
    async def unload_model(self):
        """Safely unload active model"""
        if not self.app or not getattr(self.app.state, "active_engine", None):
            return
            
        engine = self.app.state.active_engine
        await engine.unload()
        
        self.app.state.active_engine = None
        self.app.state.active_model = None
        self.app.state.active_mode = None
        
        # ponytail: gc.collect() blocks the event loop; run in thread
        import gc
        await asyncio.to_thread(gc.collect)

    async def list_models(self) -> List[Dict[str, Any]]:
        """List all installed models"""
        return await self.registry.list_models()
    
    async def get_model(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get model by name"""
        return await self.registry.get_model(model_name)
    
    async def model_exists(self, model_name: str) -> bool:
        """Check if model exists"""
        model = await self.registry.get_model(model_name)
        return model is not None
    
    def is_downloading(self, model_name: str) -> bool:
        """Check if model is being downloaded"""
        return model_name in self._download_tasks
    
    def get_download_status(self, model_name: str) -> Dict[str, Any]:
        """Get download status"""
        return self.download_status.get(model_name, {
            "model": model_name,
            "status": "unknown",
            "progress": 0
        })
    
    async def download_model(self, model_name: str, quant: str = "Q4_K_M"):
        """Download model from HuggingFace"""
        self.download_status[model_name] = {
            "model": model_name,
            "status": "downloading",
            "progress": 0,
            "downloaded_gb": 0,
            "total_gb": 0,
            "error": None
        }
        
        def update_progress(progress):
            self.download_status[model_name].update({
                "status": progress.status,
                "progress": progress.progress_percent,
                "downloaded_gb": progress.downloaded_gb,
                "total_gb": progress.total_gb,
                "error": progress.error
            })
            
        try:
            # Get model info
            info = await self.provider.get_model_info(model_name)
            if not info:
                raise Exception(f"Model {model_name} not found")
                
            # Create model directory
            safe_name = model_name.replace(":", "-").replace("/", "-")
            model_dir = self.models_dir / "installed" / safe_name
            model_dir.mkdir(parents=True, exist_ok=True)
            
            # Start download
            # Support full repo download if quant is "full" or empty
            actual_quant = quant if quant not in ["full", "none", ""] else ""
            
            model_path = await self.provider.download(
                model_id=model_name,
                destination=model_dir,
                quantization=actual_quant,
                progress_callback=update_progress
            )
            
            # Get specific file info for metadata
            file_info = info.get_file_by_quant(actual_quant) or info.get_best_file() if actual_quant else None
            
            # calculate size accurately — os.scandir is faster than rglob
            total_size_bytes = 0
            if model_path.is_file():
                total_size_bytes = model_path.stat().st_size
            else:
                for entry in os.scandir(model_path):
                    if entry.is_file(follow_symlinks=False):
                        total_size_bytes += entry.stat().st_size
                    elif entry.is_dir(follow_symlinks=False):
                        for sub in os.scandir(entry):
                            if sub.is_file(follow_symlinks=False):
                                total_size_bytes += sub.stat().st_size
            
            # Map download quant string to engine quant_method.
            # GGUF quant variants (Q4_K_M, Q5_K_M, Q8_0, etc.) imply gguf quant_method.
            # Full model repos imply "none" (LayerStream can later re-quantize to int8).
            quant_string = file_info.quantization.value if file_info and file_info.quantization else (quant if quant else "none")
            if quant_string and quant_string not in ("full", "none", ""):
                quant_method = "gguf"  # All GGUF variants share the same engine quant_method
            else:
                quant_method = "none"

            # Create metadata
            metadata = {
                "id": model_name,
                "name": info.name,
                "family": info.family or model_name.split(":")[0],
                "parameters": info.parameters or "",
                "quant": quant_string,
                "quant_method": quant_method,
                "size_gb": round(total_size_bytes / (1024**3), 2),
                "path": str(model_path),
                "checksum": file_info.checksum if file_info else "",
                "downloaded": True,
                "modes_supported": ["fullram", "layerstream"],
                "created_at": datetime.now().isoformat()
            }
            
            # Save metadata
            with open(model_dir / "metadata.json", "w") as f:
                json.dump(metadata, f, indent=2)
            
            # Register
            await self.registry.add_model(metadata)
            
            self.download_status[model_name]["status"] = "complete"
            self.download_status[model_name]["progress"] = 100
            
        except Exception as e:
            logger.exception("Download failed for %s", model_name)
            self.download_status[model_name]["status"] = "error"
            self.download_status[model_name]["error"] = str(e)
            
        finally:
            if model_name in self._download_tasks:
                del self._download_tasks[model_name]
    
    async def delete_model(self, model_name: str) -> bool:
        """Delete a model"""
        model = await self.registry.get_model(model_name)
        if not model:
            return False
        
        # Delete files
        model_path = Path(model["path"])
        if model_path.is_dir():
            model_dir = model_path
        else:
            model_dir = model_path.parent
            
        if model_dir.exists():
            import shutil
            # Path-root guard: never rmtree outside the models directory, even
            # if registry metadata was tampered with.
            root = self.models_dir.resolve()
            resolved = model_dir.resolve()
            if resolved != root and root not in resolved.parents:
                raise RuntimeError(
                    f"Refusing to delete path outside models directory: {model_dir}"
                )
            shutil.rmtree(model_dir)
        
        # Remove from registry
        await self.registry.delete_model(model_name)
        
        return True

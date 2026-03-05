"""Model Management Service"""
import os
import json
import hashlib
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import aiohttp
import aiofiles

from app.config import settings
from app.services.registry import ModelRegistry
from app.security.encryption import ModelEncryption
from app.providers.huggingface import HuggingFaceProvider


class ModelManager:
    """Manage model lifecycle"""
    
    HUGGINGFACE_API = "https://huggingface.co/api/models"
    
    def __init__(self):
        self.models_dir = settings.models_dir
        self.registry = ModelRegistry(settings.database_path)
        self.encryption = ModelEncryption() if settings.encryption_enabled else None
        
        self.download_status: Dict[str, Dict[str, Any]] = {}
        self._download_tasks: Dict[str, asyncio.Task] = {}
        
        self.provider = HuggingFaceProvider()
    
    async def initialize(self):
        """Initialize model manager"""
        await self.registry.initialize()
        await self.provider.initialize()
        
        # Scan for models
        await self._scan_models()
    
    async def _scan_models(self):
        """Scan models directory for installed models"""
        installed_dir = self.models_dir / "installed"
        installed_dir.mkdir(parents=True, exist_ok=True)
        
        for model_dir in installed_dir.iterdir():
            if model_dir.is_dir():
                metadata_path = model_dir / "metadata.json"
                metadata = None
                if metadata_path.exists():
                    try:
                        with open(metadata_path) as f:
                            metadata = json.load(f)
                        
                        # Sync path with current filesystem location in case of moves
                        if "path" in metadata:
                            original_path = Path(metadata["path"])
                            if not original_path.exists():
                                # Try to find the file or folder within this model_dir
                                if original_path.is_file():
                                    # Single file model
                                    new_path = model_dir / original_path.name
                                    if new_path.exists():
                                        metadata["path"] = str(new_path)
                                else:
                                    # Directory model
                                    metadata["path"] = str(model_dir)
                    except Exception:
                        pass
                
                if not metadata:
                    # Try to discover model
                    metadata = await self._discover_model(model_dir)
                
                if metadata:
                    # Always update registration to ensure paths are synchronized with filesystem moves
                    await self.registry.add_model(metadata)

    async def _discover_model(self, model_dir: Path) -> Optional[Dict[str, Any]]:
        """Try to discover model information from a directory"""
        # Look for config.json (HF repo)
        config_path = model_dir / "config.json"
        if config_path.exists():
            # HF repo
            model_id = model_dir.name.replace("-", "/") # Try to restore original name format if possible
            # Try to get better name from config
            try:
                with open(config_path) as f:
                    config = json.load(f)
                model_type = config.get("model_type", "unknown")
            except Exception:
                model_type = "unknown"
            
            # Calculate size
            size_bytes = sum(f.stat().st_size for f in model_dir.rglob("*") if f.is_file())
            
            return {
                "id": model_id,
                "name": model_dir.name,
                "family": model_type,
                "parameters": "unknown",
                "quant": "none",
                "size_gb": round(size_bytes / (1024**3), 2),
                "path": str(model_dir),
                "downloaded": True,
                "modes_supported": ["fullram"],
                "created_at": datetime.now().isoformat()
            }
        
        # Look for .gguf files
        gguf_files = list(model_dir.glob("*.gguf"))
        if gguf_files:
            gguf_path = gguf_files[0]
            model_id = gguf_path.stem
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
            
            # Skip encryption to allow direct loading via HuggingFace Hub mechanics
            
            # Get specific file info for metadata
            file_info = info.get_file_by_quant(actual_quant) or info.get_best_file() if actual_quant else None
            
            # calculate size accurately
            total_size_bytes = 0
            if model_path.is_file():
                total_size_bytes = model_path.stat().st_size
            else:
                total_size_bytes = sum(f.stat().st_size for f in model_path.rglob("*") if f.is_file())
            
            # Create metadata
            metadata = {
                "id": model_name,
                "name": info.name,
                "family": info.family or model_name.split(":")[0],
                "parameters": info.parameters or "",
                "quant": file_info.quantization.value if file_info and file_info.quantization else (quant if quant else "none"),
                "size_gb": round(total_size_bytes / (1024**3), 2),
                "path": str(model_path),
                "checksum": file_info.checksum if file_info else "",
                "downloaded": True,
                "modes_supported": info.modes_supported if not actual_quant == "" else ["fullram"],
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
            import traceback
            traceback.print_exc()
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
        model_dir = Path(model["path"]).parent
        if model_dir.exists():
            import shutil
            shutil.rmtree(model_dir)
        
        # Remove from registry
        await self.registry.delete_model(model_name)
        
        return True
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


class ModelManager:
    """Manage model lifecycle"""
    
    HUGGINGFACE_API = "https://huggingface.co/api/models"
    
    def __init__(self):
        self.models_dir = settings.models_dir
        self.registry = ModelRegistry(settings.database_path)
        self.encryption = ModelEncryption() if settings.encryption_enabled else None
        
        self.download_status: Dict[str, Dict[str, Any]] = {}
        self._download_tasks: Dict[str, asyncio.Task] = {}
    
    async def initialize(self):
        """Initialize model manager"""
        await self.registry.initialize()
        
        # Scan for models
        await self._scan_models()
    
    async def _scan_models(self):
        """Scan models directory for installed models"""
        installed_dir = self.models_dir / "installed"
        installed_dir.mkdir(parents=True, exist_ok=True)
        
        for model_dir in installed_dir.iterdir():
            if model_dir.is_dir():
                metadata_path = model_dir / "metadata.json"
                if metadata_path.exists():
                    with open(metadata_path) as f:
                        metadata = json.load(f)
                    
                    # Register if not already
                    if not await self.registry.get_model(metadata["id"]):
                        await self.registry.add_model(metadata)
    
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
        # Parse model name
        family, size = self._parse_model_name(model_name)
        
        self.download_status[model_name] = {
            "model": model_name,
            "status": "fetching_metadata",
            "progress": 0,
            "downloaded_gb": 0,
            "total_gb": 0
        }
        
        try:
            # Search for GGUF version
            gguf_repo = await self._find_gguf_repo(family, size)
            
            if not gguf_repo:
                self.download_status[model_name]["status"] = "error"
                self.download_status[model_name]["error"] = "No GGUF version found"
                return
            
            # Get file URL
            file_url, file_size = await self._get_model_file(gguf_repo, quant)
            
            self.download_status[model_name]["total_gb"] = file_size / (1024**3)
            self.download_status[model_name]["status"] = "downloading"
            
            # Download
            model_dir = self.models_dir / "installed" / model_name.replace(":", "-")
            model_dir.mkdir(parents=True, exist_ok=True)
            
            model_path = model_dir / f"{quant}.gguf"
            
            await self._download_file(file_url, model_path, model_name)
            
            # Verify checksum
            self.download_status[model_name]["status"] = "verifying"
            checksum = await self._compute_checksum(model_path)
            
            # Encrypt if enabled
            if self.encryption:
                self.download_status[model_name]["status"] = "encrypting"
                await self.encryption.encrypt_model(model_path)
            
            # Create metadata
            metadata = {
                "id": model_name,
                "name": model_name,
                "family": family,
                "parameters": size,
                "quant": quant,
                "size_gb": round(file_size / (1024**3), 2),
                "path": str(model_path),
                "checksum": checksum,
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
            self.download_status[model_name]["status"] = "error"
            self.download_status[model_name]["error"] = str(e)
        finally:
            if model_name in self._download_tasks:
                del self._download_tasks[model_name]
    
    def _parse_model_name(self, model_name: str) -> tuple:
        """Parse model name into family and size"""
        parts = model_name.split(":")
        family = parts[0]
        size = parts[1] if len(parts) > 1 else "7b"
        return family, size
    
    async def _find_gguf_repo(self, family: str, size: str) -> Optional[str]:
        """Find GGUF repo on HuggingFace"""
        search_query = f"{family}-{size}-GGUF"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.HUGGINGFACE_API}",
                params={"search": search_query, "limit": 5}
            ) as resp:
                if resp.status == 200:
                    results = await resp.json()
                    for result in results:
                        if "gguf" in result["id"].lower():
                            return result["id"]
        
        return None
    
    async def _get_model_file(self, repo: str, quant: str) -> tuple:
        """Get model file URL and size"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.HUGGINGFACE_API}/{repo}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    siblings = data.get("siblings", [])
                    
                    for file in siblings:
                        if quant.lower() in file["rfilename"].lower() and file["rfilename"].endswith(".gguf"):
                            url = f"https://huggingface.co/{repo}/resolve/main/{file['rfilename']}"
                            size = file.get("size", 0)
                            return url, size
        
        raise ValueError(f"No file found for quant {quant}")
    
    async def _download_file(self, url: str, path: Path, model_name: str):
        """Download file with progress"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                total = int(resp.headers.get("content-length", 0))
                downloaded = 0
                
                async with aiofiles.open(path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(8 * 1024 * 1024):
                        await f.write(chunk)
                        downloaded += len(chunk)
                        
                        self.download_status[model_name]["downloaded_gb"] = downloaded / (1024**3)
                        self.download_status[model_name]["progress"] = (downloaded / total * 100) if total else 0
    
    async def _compute_checksum(self, path: Path) -> str:
        """Compute SHA256 checksum"""
        sha256 = hashlib.sha256()
        
        async with aiofiles.open(path, "rb") as f:
            while chunk := await f.read(8192):
                sha256.update(chunk)
        
        return sha256.hexdigest()
    
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
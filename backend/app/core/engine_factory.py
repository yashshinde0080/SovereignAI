"""Engine Factory"""
from typing import Dict, Any, Optional
from pathlib import Path

from app.core.memory_manager import MemoryManager
from app.engines.base import BaseEngine
from app.engines.fullram.executor import FullRAMEngine
from app.engines.layerstream.executor import LayerStreamEngine


class EngineFactory:
    """Factory for creating inference engines"""
    
    def __init__(self, hardware_profile: Dict[str, Any]):
        self.hardware = hardware_profile
        self.memory_manager = MemoryManager()
    
    async def create_engine(
        self,
        model_path: str,
        mode: str = "auto"
    ) -> BaseEngine:
        """Create appropriate engine"""
        
        model_path = Path(model_path)
        
        # If directory, find the model file
        if model_path.is_dir():
             # Try to find GGUF first
             gguf_files = list(model_path.glob("*.gguf")) + list(model_path.glob("*.gguf.enc"))
             if gguf_files:
                 model_path = gguf_files[0]
             else:
                 # Try to find safetensors
                 st_files = list(model_path.glob("*.safetensors")) + list(model_path.glob("*.safetensors.enc"))
                 if st_files:
                     model_path = st_files[0]
                 else:
                     raise ValueError(f"No suitable model file found in directory: {model_path}")
        
        model_size = model_path.stat().st_size if model_path.exists() and model_path.is_file() else 0
        
        # Determine mode
        if mode == "auto":
            mode = self.memory_manager.suggest_mode(model_size)
            if mode == "insufficient":
                raise RuntimeError("Insufficient memory for any execution mode")
        
        # Create engine
        if mode == "fullram":
            engine = FullRAMEngine(
                model_path=str(model_path),
                hardware=self.hardware,
                memory_manager=self.memory_manager
            )
        elif mode == "layerstream":
            engine = LayerStreamEngine(
                model_path=str(model_path),
                hardware=self.hardware,
                memory_manager=self.memory_manager
            )
        else:
            raise ValueError(f"Unknown mode: {mode}")
        
        # Initialize
        await engine.load()
        
        return engine
    
    def get_recommended_mode(self, model_size_bytes: int) -> str:
        """Get recommended mode for model"""
        return self.memory_manager.suggest_mode(model_size_bytes)
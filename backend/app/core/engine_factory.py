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
        model_size = model_path.stat().st_size if model_path.exists() else 0
        
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
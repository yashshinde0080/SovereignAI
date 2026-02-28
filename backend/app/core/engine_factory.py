"""Engine Factory"""
from typing import Dict, Any, Optional
from pathlib import Path

from app.core.memory_manager import MemoryManager
from app.engines.base import BaseEngine
from app.engines.fullram.executor import FullRAMEngine
from app.engines.layerstream.executor import LayerStreamEngine
from app.engines.manualstream.executor import ManualStreamEngine


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
        engine_model_path_str = str(model_path)
        model_size = 0
        
        # If directory, determine model size correctly and ensure we pass the correct directory
        if model_path.is_dir():
             # If config.json exists, this is a standard HuggingFace repo
             if (model_path / "config.json").exists():
                 engine_model_path_str = str(model_path)
                 model_size = sum(f.stat().st_size for f in model_path.rglob("*") if f.is_file())
             else:
                 # Try to find GGUF or SafeTensors as fallback for size calculations
                 gguf_files = list(model_path.glob("*.gguf")) + list(model_path.glob("*.gguf.enc"))
                 if gguf_files:
                     # Currently FullRAMEngine uses AutoModelForCausalLM which prefers directories
                     # Depending on the engine, GGUF might require a specific loader
                     # But for HF transformers, passing the directory is usually better if possible
                     engine_model_path_str = str(gguf_files[0])
                     model_size = gguf_files[0].stat().st_size
                 else:
                     st_files = list(model_path.glob("*.safetensors")) + list(model_path.glob("*.safetensors.enc"))
                     if st_files:
                         # Even if safetensors exist without config.json, passing directory is safer for HF
                         engine_model_path_str = str(model_path)
                         model_size = sum(f.stat().st_size for f in st_files)
                     else:
                         # No recognized models found
                         pass
        else:
            model_size = model_path.stat().st_size if model_path.exists() and model_path.is_file() else 0
            engine_model_path_str = str(model_path)
        
        # Determine mode
        if mode == "auto":
            mode = self.memory_manager.suggest_mode(model_size)
            if mode == "insufficient":
                raise RuntimeError("Insufficient memory for any execution mode")
        
        # Create engine
        if mode == "fullram":
            engine = FullRAMEngine(
                model_path=engine_model_path_str,
                hardware=self.hardware,
                memory_manager=self.memory_manager
            )
        elif mode == "layerstream":
            engine = LayerStreamEngine(
                model_path=engine_model_path_str,
                hardware=self.hardware,
                memory_manager=self.memory_manager
            )
        elif mode == "manualstream":
            engine = ManualStreamEngine(
                model_path=engine_model_path_str,
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
"""Base Engine Interface"""
from abc import ABC, abstractmethod
from typing import Dict, Any, AsyncGenerator, Optional


class BaseEngine(ABC):
    """Abstract base class for inference engines"""
    
    def __init__(
        self,
        model_path: str,
        hardware: Dict[str, Any],
        memory_manager: Any
    ):
        self.model_path = model_path
        self.hardware = hardware
        self.memory_manager = memory_manager
        self.mode = "unknown"
        self.loaded = False
        self.stats = {}
    
    @abstractmethod
    async def load(self):
        """Load model into engine"""
        pass
    
    @abstractmethod
    async def unload(self):
        """Unload model from engine"""
        pass
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9
    ) -> Dict[str, Any]:
        """Generate completion"""
        pass
    
    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate completion with streaming"""
        pass
    
    @abstractmethod
    def get_memory_usage(self) -> Dict[str, Any]:
        """Get current memory usage"""
        pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics"""
        return self.stats
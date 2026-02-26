"""Memory Management"""
import psutil
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class MemoryZone:
    """Memory zone tracking"""
    name: str
    allocated: int = 0
    max_allowed: int = 0


class MemoryManager:
    """Manage memory allocation and tracking"""
    
    def __init__(self, max_usage_percent: float = 0.75):
        self.max_usage_percent = max_usage_percent
        self.lock = Lock()
        
        # Initialize zones
        total_ram = psutil.virtual_memory().total
        max_allowed = int(total_ram * max_usage_percent)
        
        self.zones: Dict[str, MemoryZone] = {
            "layer_buffer": MemoryZone("layer_buffer", max_allowed=max_allowed // 2),
            "prefetch_buffer": MemoryZone("prefetch_buffer", max_allowed=max_allowed // 4),
            "activation_buffer": MemoryZone("activation_buffer", max_allowed=max_allowed // 8),
            "kv_cache": MemoryZone("kv_cache", max_allowed=max_allowed // 4),
        }
        
        self.total_allocated = 0
        self.max_total = max_allowed
    
    def allocate(self, zone: str, size: int) -> bool:
        """Allocate memory in zone"""
        with self.lock:
            if zone not in self.zones:
                return False
            
            zone_obj = self.zones[zone]
            
            # Check zone limit
            if zone_obj.allocated + size > zone_obj.max_allowed:
                return False
            
            # Check total limit
            if self.total_allocated + size > self.max_total:
                return False
            
            zone_obj.allocated += size
            self.total_allocated += size
            return True
    
    def release(self, zone: str, size: int):
        """Release memory from zone"""
        with self.lock:
            if zone in self.zones:
                self.zones[zone].allocated = max(0, self.zones[zone].allocated - size)
                self.total_allocated = max(0, self.total_allocated - size)
    
    def get_available(self, zone: str) -> int:
        """Get available memory in zone"""
        with self.lock:
            if zone in self.zones:
                return self.zones[zone].max_allowed - self.zones[zone].allocated
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        with self.lock:
            return {
                "total_allocated_mb": self.total_allocated / (1024**2),
                "max_allowed_mb": self.max_total / (1024**2),
                "usage_percent": (self.total_allocated / self.max_total * 100) if self.max_total > 0 else 0,
                "zones": {
                    name: {
                        "allocated_mb": zone.allocated / (1024**2),
                        "max_mb": zone.max_allowed / (1024**2)
                    }
                    for name, zone in self.zones.items()
                }
            }
    
    def can_fit_model(self, model_size_bytes: int) -> bool:
        """Check if model can fit in memory"""
        available = self.max_total - self.total_allocated
        # Need some headroom
        return model_size_bytes * 1.2 < available
    
    def suggest_mode(self, model_size_bytes: int) -> str:
        """Suggest execution mode based on memory"""
        available_ram = psutil.virtual_memory().available
        
        if model_size_bytes * 1.4 < available_ram:
            return "fullram"
        elif model_size_bytes * 0.3 < available_ram:
            return "layerstream"
        else:
            return "insufficient"
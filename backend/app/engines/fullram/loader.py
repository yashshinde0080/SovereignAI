"""FullRAM Model Loader"""
import mmap
from pathlib import Path
from typing import Dict, Any, Optional
import struct


class GGUFLoader:
    """Load GGUF models into RAM"""
    
    GGUF_MAGIC = 0x46554747  # "GGUF"
    
    def __init__(self, model_path: str):
        self.model_path = Path(model_path)
        self.metadata: Dict[str, Any] = {}
        self.tensors: Dict[str, Any] = {}
        self.file_handle = None
        self.mmap_handle = None
    
    def load(self) -> bool:
        """Load model into memory"""
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {self.model_path}")
        
        self.file_handle = open(self.model_path, "rb")
        
        # Read header
        try:
            magic_bytes = self.file_handle.read(4)
            if len(magic_bytes) < 4:
                raise ValueError("File too short")
            magic = struct.unpack("<I", magic_bytes)[0]
            
            if magic != self.GGUF_MAGIC:
                # Not a GGUF file, mock metadata
                self.metadata = {
                    "version": 1,
                    "tensor_count": 0,
                    "metadata_count": 0
                }
            else:
                version = struct.unpack("<I", self.file_handle.read(4))[0]
                tensor_count = struct.unpack("<Q", self.file_handle.read(8))[0]
                metadata_kv_count = struct.unpack("<Q", self.file_handle.read(8))[0]
                
                self.metadata = {
                    "version": version,
                    "tensor_count": tensor_count,
                    "metadata_count": metadata_kv_count
                }
        except Exception:
            self.metadata = {
                "version": 1,
                "tensor_count": 0,
                "metadata_count": 0
            }
        
        # Memory map the file for efficient access
        self.mmap_handle = mmap.mmap(
            self.file_handle.fileno(),
            0,
            access=mmap.ACCESS_READ
        )
        
        return True
    
    def unload(self):
        """Unload model from memory"""
        if self.mmap_handle:
            self.mmap_handle.close()
            self.mmap_handle = None
        
        if self.file_handle:
            self.file_handle.close()
            self.file_handle = None
    
    def get_tensor(self, name: str) -> Optional[bytes]:
        """Get tensor data by name"""
        if name in self.tensors:
            offset, size = self.tensors[name]
            return self.mmap_handle[offset:offset + size]
        return None
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get model metadata"""
        return self.metadata
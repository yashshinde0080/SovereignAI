"""
SovereignAI Model Manager
Manages HuggingFace models like Docker manages containers.
One model loaded at a time. Pull, list, load, unload, remove, infer.
"""

from .loader import ModelLoader
from .registry import ModelRegistry
from .downloader import ModelDownloader
from .detector import ModelDetector
from .inference import InferenceEngine
from .router import router as model_router

__all__ = [
    "ModelLoader",
    "ModelRegistry",
    "ModelDownloader",
    "ModelDetector",
    "InferenceEngine",
    "model_router",
]
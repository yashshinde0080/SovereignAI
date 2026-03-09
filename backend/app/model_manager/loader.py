"""
Model Loader — loads exactly ONE model into memory at a time.
Handles loading, unloading, device placement, dtype selection.
"""

import gc
import time
import logging
import threading
import importlib
from pathlib import Path
from typing import Optional, Any
from datetime import datetime

import torch
import psutil
from transformers import (
    AutoTokenizer,
    AutoProcessor,
    AutoFeatureExtractor,
    AutoConfig,
    BitsAndBytesConfig,
)

from .config import (
    ModelStatus,
    ModelTaskType,
    DEFAULT_DEVICE,
)
from .registry import ModelRegistry
from .detector import ModelDetector
from .schemas import LoadedModelInfo

logger = logging.getLogger("sovereign.loader")


class ModelLoader:
    """
    Manages model loading and unloading.
    
    CRITICAL RULE: Only ONE model loaded at a time.
    Loading a new model automatically unloads the current one.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self.registry = ModelRegistry()
        self.detector = ModelDetector()
        
        # Current loaded model state
        self._model: Optional[Any] = None
        self._tokenizer: Optional[Any] = None
        self._processor: Optional[Any] = None
        self._feature_extractor: Optional[Any] = None
        self._loaded_model_id: Optional[str] = None
        self._loaded_task_type: Optional[ModelTaskType] = None
        self._loaded_device: Optional[str] = None
        self._loaded_dtype: Optional[str] = None
        self._loaded_at: Optional[datetime] = None
        self._load_lock = threading.Lock()
    
    @property
    def is_loaded(self) -> bool:
        return self._model is not None
    
    @property
    def model(self):
        return self._model
    
    @property
    def tokenizer(self):
        return self._tokenizer
    
    @property
    def processor(self):
        return self._processor
    
    @property
    def feature_extractor(self):
        return self._feature_extractor
    
    @property
    def loaded_model_id(self) -> Optional[str]:
        return self._loaded_model_id
    
    @property
    def loaded_task_type(self) -> Optional[ModelTaskType]:
        return self._loaded_task_type
    
    def get_loaded_info(self) -> Optional[LoadedModelInfo]:
        """Get info about currently loaded model."""
        if not self.is_loaded:
            return None
        
        model_info = self.registry.get_model(self._loaded_model_id)
        if not model_info:
            return None
        
        # Calculate memory usage
        mem_mb = self._estimate_memory_usage()
        
        return LoadedModelInfo(
            model_id=self._loaded_model_id,
            repo_id=model_info.repo_id,
            task_type=model_info.task_type,
            device=self._loaded_device or "unknown",
            dtype=self._loaded_dtype or "unknown",
            loaded_at=(
                self._loaded_at.isoformat() 
                if self._loaded_at else ""
            ),
            memory_used_mb=mem_mb,
        )
    
    def load(
        self,
        model_id: str,
        device: Optional[str] = None,
        dtype: Optional[str] = None,
    ) -> LoadedModelInfo:
        """
        Load a model into memory.
        
        If another model is loaded, it will be unloaded first.
        Only ONE model at a time.
        """
        with self._load_lock:
            # ─── Validate model exists ────────────────────
            model_info = self.registry.get_model(model_id)
            if not model_info:
                raise ValueError(f"Model {model_id} not found.")
            
            if model_info.status not in (
                ModelStatus.READY.value, 
                ModelStatus.LOADED.value
            ):
                raise ValueError(
                    f"Model {model_id} is not ready. "
                    f"Status: {model_info.status}"
                )
            
            # Already loaded?
            if (
                self._loaded_model_id == model_id 
                and self.is_loaded
            ):
                logger.info(
                    f"Model {model_id} already loaded."
                )
                return self.get_loaded_info()
            
            # ─── Unload current model ─────────────────────
            if self.is_loaded:
                logger.info(
                    f"Unloading current model "
                    f"{self._loaded_model_id} to load {model_id}"
                )
                self._unload_internal()
            
            # ─── Resolve device ───────────────────────────
            resolved_device = self._resolve_device(device)
            resolved_dtype = self._resolve_dtype(
                dtype, resolved_device
            )
            
            logger.info(
                f"Loading model {model_id} "
                f"({model_info.repo_id}) "
                f"on {resolved_device} "
                f"with {resolved_dtype}"
            )
            
            # ─── Load model ──────────────────────────────
            local_path = Path(model_info.local_path)
            task_type = ModelTaskType(model_info.task_type)
            
            start_time = time.time()
            
            try:
                # Load tokenizer / processor
                self._load_tokenizer(local_path, task_type)
                
                # Load model with correct AutoModel class
                self._load_model_weights(
                    local_path, 
                    task_type,
                    resolved_device, 
                    resolved_dtype,
                    model_info,
                )
                
                load_time = time.time() - start_time
                
                # ─── Update state ─────────────────────────
                self._loaded_model_id = model_id
                self._loaded_task_type = task_type
                self._loaded_device = resolved_device
                self._loaded_dtype = resolved_dtype
                self._loaded_at = datetime.utcnow()
                
                # Update registry
                self.registry.mark_loaded(model_id)
                
                logger.info(
                    f"Model {model_id} loaded in "
                    f"{load_time:.1f}s on {resolved_device}"
                )
                
                return self.get_loaded_info()
                
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
                self._cleanup_partial_load()
                raise RuntimeError(
                    f"Failed to load model {model_id}: {e}"
                )
    
    def unload(self) -> bool:
        """Unload the currently loaded model."""
        with self._load_lock:
            if not self.is_loaded:
                logger.info("No model loaded.")
                return False
            
            model_id = self._loaded_model_id
            self._unload_internal()
            logger.info(f"Model {model_id} unloaded.")
            return True
    
    def _unload_internal(self):
        """Internal unload without lock."""
        if self._loaded_model_id:
            self.registry.mark_unloaded(self._loaded_model_id)
        
        # Delete model and associated objects
        del self._model
        del self._tokenizer
        del self._processor
        del self._feature_extractor
        
        self._model = None
        self._tokenizer = None
        self._processor = None
        self._feature_extractor = None
        self._loaded_model_id = None
        self._loaded_task_type = None
        self._loaded_device = None
        self._loaded_dtype = None
        self._loaded_at = None
        
        # Force garbage collection
        gc.collect()
        
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
    
    def _cleanup_partial_load(self):
        """Clean up after failed load."""
        self._model = None
        self._tokenizer = None
        self._processor = None
        self._feature_extractor = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    
    def _load_tokenizer(
        self, 
        model_path: Path, 
        task_type: ModelTaskType
    ):
        """Load appropriate tokenizer/processor."""
        
        # Tasks that need a processor instead of tokenizer
        processor_tasks = {
            ModelTaskType.SPEECH_SEQ2SEQ,
            ModelTaskType.VISION2SEQ,
            ModelTaskType.VISUAL_QA,
            ModelTaskType.DOCUMENT_QA,
            ModelTaskType.IMAGE_SEGMENTATION,
            ModelTaskType.SEMANTIC_SEGMENTATION,
            ModelTaskType.INSTANCE_SEGMENTATION,
            ModelTaskType.OBJECT_DETECTION,
            ModelTaskType.ZERO_SHOT_OBJECT_DETECTION,
            ModelTaskType.DEPTH_ESTIMATION,
            ModelTaskType.IMAGE_TO_IMAGE,
            ModelTaskType.VIDEO_CLASSIFICATION,
        }
        
        feature_extractor_tasks = {
            ModelTaskType.AUDIO_CLASSIFICATION,
            ModelTaskType.AUDIO_FRAME_CLASSIFICATION,
            ModelTaskType.AUDIO_XVECTOR,
            ModelTaskType.CTC,
        }
        
        try:
            if task_type in processor_tasks:
                self._processor = AutoProcessor.from_pretrained(
                    str(model_path),
                    trust_remote_code=True,
                )
                logger.info("Loaded AutoProcessor")
                
            elif task_type in feature_extractor_tasks:
                self._feature_extractor = (
                    AutoFeatureExtractor.from_pretrained(
                        str(model_path)
                    )
                )
                # Also try tokenizer for some audio models
                try:
                    self._tokenizer = (
                        AutoTokenizer.from_pretrained(
                            str(model_path)
                        )
                    )
                except Exception:
                    pass
                logger.info("Loaded AutoFeatureExtractor")
                
            else:
                self._tokenizer = AutoTokenizer.from_pretrained(
                    str(model_path),
                    trust_remote_code=True,
                )
                # Set pad token if missing
                if self._tokenizer.pad_token is None:
                    self._tokenizer.pad_token = (
                        self._tokenizer.eos_token
                    )
                logger.info("Loaded AutoTokenizer")
                
        except Exception as e:
            logger.warning(
                f"Tokenizer/processor load warning: {e}. "
                f"Trying fallback..."
            )
            try:
                self._processor = AutoProcessor.from_pretrained(
                    str(model_path),
                    trust_remote_code=True,
                )
            except Exception:
                logger.warning(
                    "Could not load any tokenizer/processor."
                )
    
    def _load_model_weights(
        self,
        model_path: Path,
        task_type: ModelTaskType,
        device: str,
        dtype: str,
        model_info: Any,
    ):
        """Load model weights with correct AutoModel class."""
        import transformers
        
        auto_class_name = self.detector.get_auto_class_name(
            task_type
        )
        
        logger.info(
            f"Using {auto_class_name} for "
            f"task {task_type.value}"
        )
        
        # Get the AutoModel class
        if hasattr(transformers, auto_class_name):
            auto_class = getattr(transformers, auto_class_name)
        else:
            logger.warning(
                f"{auto_class_name} not found. "
                f"Falling back to AutoModel."
            )
            auto_class = transformers.AutoModel
        
        # Build load kwargs
        load_kwargs = self._build_load_kwargs(
            device, dtype, model_info
        )
        
        # Check trust_remote_code from registry
        config = self.registry.get_model_config(model_info.id)
        trust_remote = False
        if model_info.architectures:
            import json
            try:
                archs = json.loads(model_info.architectures)
                # Some architectures need remote code
                trust_remote = True
            except Exception:
                pass
        
        self._model = auto_class.from_pretrained(
            str(model_path),
            trust_remote_code=trust_remote,
            **load_kwargs,
        )
        
        # Move to device if not already there
        if device != "cpu" and not load_kwargs.get(
            "device_map"
        ):
            try:
                self._model = self._model.to(device)
            except Exception as e:
                logger.warning(
                    f"Could not move to {device}: {e}. "
                    f"Staying on CPU."
                )
        
        self._model.eval()
    
    def _build_load_kwargs(
        self, 
        device: str, 
        dtype: str,
        model_info: Any,
    ) -> dict:
        """Build kwargs for from_pretrained."""
        kwargs = {}
        
        # Dtype
        dtype_map = {
            "float32": torch.float32,
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
        }
        
        if dtype in dtype_map:
            kwargs["torch_dtype"] = dtype_map[dtype]
        elif dtype == "auto":
            kwargs["torch_dtype"] = "auto"
        elif dtype == "int8":
            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_8bit=True,
            )
            kwargs["device_map"] = "auto"
        elif dtype == "int4":
            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
            )
            kwargs["device_map"] = "auto"
        else:
            kwargs["torch_dtype"] = torch.float16
        
        # Device map for CUDA
        if device.startswith("cuda") and "device_map" not in kwargs:
            kwargs["device_map"] = "auto"
        
        # Low CPU memory usage
        kwargs["low_cpu_mem_usage"] = True
        
        return kwargs
    
    def _resolve_device(
        self, device: Optional[str]
    ) -> str:
        """Resolve the target device."""
        if device and device != "auto":
            return device
        
        user_default = DEFAULT_DEVICE
        if user_default != "auto":
            return user_default
        
        if torch.cuda.is_available():
            return "cuda"
        
        if hasattr(torch.backends, "mps") and \
           torch.backends.mps.is_available():
            return "mps"
        
        return "cpu"
    
    def _resolve_dtype(
        self, 
        dtype: Optional[str], 
        device: str
    ) -> str:
        """Resolve data type based on device."""
        if dtype:
            return dtype
        
        if device == "cpu":
            return "float32"
        
        if device.startswith("cuda"):
            # Check BF16 support
            if torch.cuda.is_bf16_supported():
                return "bfloat16"
            return "float16"
        
        if device == "mps":
            return "float16"
        
        return "float32"
    
    def _estimate_memory_usage(self) -> float:
        """Estimate current model memory in MB."""
        if not self._model:
            return 0.0
        
        try:
            if self._loaded_device and \
               self._loaded_device.startswith("cuda"):
                mem = torch.cuda.memory_allocated() / (1024 ** 2)
                return round(mem, 1)
        except Exception:
            pass
        
        # Estimate from parameters
        try:
            total_params = sum(
                p.numel() * p.element_size() 
                for p in self._model.parameters()
            )
            return round(total_params / (1024 ** 2), 1)
        except Exception:
            return 0.0
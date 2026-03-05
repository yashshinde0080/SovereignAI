"""FullRAM Execution Engine"""
import asyncio
import time
import os
from typing import Dict, Any, AsyncGenerator, Optional
import numpy as np

import torch
from transformers import AutoProcessor, AutoTokenizer, TextIteratorStreamer, AutoImageProcessor
from threading import Thread
import psutil

from app.engines.base import BaseEngine
from app.core.task_resolver import TaskResolver
from app.core.task_router import TaskRouter

class FullRAMEngine(BaseEngine):
    """Full RAM inference engine - loads entire model into memory dynamically"""
    
    def __init__(self, model_path: str, hardware: Dict[str, Any], memory_manager: Any):
        super().__init__(model_path, hardware, memory_manager)
        self.mode = "fullram"
        self.processor = None
        self.tokenizer = None
        self.model = None
        self.task_metadata = {}
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
    
    async def load(self):
        """Load model into RAM dynamically based on task"""
        start_time = time.time()
        
        try:
            # 1. Resolve task
            self.task_metadata = TaskResolver.resolve(self.model_path)
            task_type = self.task_metadata["task_type"]
            input_modality = self.task_metadata["input_modality"]
            is_generative = self.task_metadata["is_generative"]
            
            # 2. Get Appropriate Class
            model_class = TaskRouter.TASK_CLASS_MAP.get(task_type)
            if not model_class:
                raise ValueError(f"Unsupported task type: {task_type}")
                
            model_kwargs = {
                "trust_remote_code": True,
                "local_files_only": True,
                "low_cpu_mem_usage": True,
                "ignore_mismatched_sizes": True

            }
            
            if self.device == "cuda":
                model_kwargs["device_map"] = "auto"
                model_kwargs["torch_dtype"] = torch.float16
            else:
                model_kwargs["device_map"] = "cpu"
                model_kwargs["torch_dtype"] = torch.float32
                
            if self.model_path.endswith(".gguf") or self.model_path.endswith(".gguf.enc"):
                model_dir = os.path.dirname(self.model_path)
                model_kwargs["gguf_file"] = os.path.basename(self.model_path)
                # GGUF loading relies heavily on AutoConfig dynamic bridging locally
                self.model = model_class.from_pretrained(model_dir, **model_kwargs)
            else:
                self.model = model_class.from_pretrained(
                    self.model_path,
                    **model_kwargs
                )
            
            # 3. Load Processors
            if input_modality == "text" or is_generative:
                try:
                     tok_kwargs = {
                         "trust_remote_code": True,
                         "local_files_only": True
                     }
                     if self.model_path.endswith(".gguf") or self.model_path.endswith(".gguf.enc"):
                         tok_kwargs["gguf_file"] = os.path.basename(self.model_path)
                         tok_dir = os.path.dirname(self.model_path)
                     else:
                         tok_dir = self.model_path
                     
                     self.tokenizer = AutoTokenizer.from_pretrained(tok_dir, **tok_kwargs)
                     if not self.tokenizer.pad_token:
                         self.tokenizer.pad_token = self.tokenizer.eos_token
                except Exception as e:
                     print(f"Failed loading tokenizer from repo natively: {e}")
                     pass
                     
            if input_modality in ["image", "multimodal"]:
                try:
                    self.processor = AutoProcessor.from_pretrained(
                        self.model_path, trust_remote_code=True
                    )
                except Exception:
                    try:
                        self.processor = AutoImageProcessor.from_pretrained(
                            self.model_path, trust_remote_code=True
                        )
                    except:
                        raise RuntimeError(f"Missing required processor for vision task")
            
            if input_modality == "audio":
                try:
                    self.processor = AutoProcessor.from_pretrained(
                        self.model_path, trust_remote_code=True
                    )
                except:
                    raise RuntimeError("Missing processor for audio task")
                
            self.loaded = True
            self.stats["load_time"] = time.time() - start_time
            print(f"Loaded {self.model_path} [{task_type}] in {self.mode} on {self.device}")
            
        except Exception as e:
            self.loaded = False
            raise RuntimeError(f"Failed to load model dynamically: {e}")
    
    async def unload(self):
        """Unload model from RAM"""
        if self.model:
            del self.model
            self.model = None
        
        if self.tokenizer:
            del self.tokenizer
            self.tokenizer = None
            
        if self.processor:
            del self.processor
            self.processor = None
            
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            
        self.loaded = False
    
    async def generate(self, input_data: Any, **kwargs) -> Dict[str, Any]:
        """Unified Execute Endpoint"""
        if not self.loaded:
            raise RuntimeError("Model not loaded")
            
        task_type = self.task_metadata["task_type"]
        is_generative = self.task_metadata["is_generative"]
        modality = self.task_metadata["input_modality"]
        
        start_time = time.perf_counter()
        
        # 1. Process inputs dynamically
        processed_inputs = {}
        prompt_tokens = 0
        
        if task_type == "question_answering":
             prompt = input_data.get("question", "")
             context = input_data.get("context", "")
             processed_inputs = self.tokenizer(prompt, context, return_tensors="pt")
             prompt_tokens = processed_inputs.input_ids.shape[1]
             
        elif modality == "text" or (task_type in ["causal_lm", "sequence_classification"]):
             if not self.tokenizer:
                 raise RuntimeError("Model requires a tokenizer but none was loaded.")
             prompt = input_data if isinstance(input_data, str) else input_data.get("prompt", "")
             processed_inputs = self.tokenizer(prompt, return_tensors="pt")
             prompt_tokens = processed_inputs.input_ids.shape[1]
             
        elif modality == "image" or task_type == "image_classification":
             image = input_data.get("image")
             processed_inputs = self.processor(images=image, return_tensors="pt")
             
        if is_generative:
             max_tokens = kwargs.get("max_tokens", 512)
             temperature = kwargs.get("temperature", 0.7)
             top_p = kwargs.get("top_p", 0.9)
             
             gen_kwargs = {
                 "max_new_tokens": max_tokens,
                 "temperature": temperature if temperature > 0 else 1.0,
                 "do_sample": temperature > 0,
                 "top_p": top_p
             }
             if self.tokenizer and self.tokenizer.eos_token_id is not None:
                  gen_kwargs["pad_token_id"] = self.tokenizer.eos_token_id
             processed_inputs["generation_kwargs"] = gen_kwargs

        # 2. Route Execution
        def _execute_sync():
            # Send mapped dict to task router correctly handling devices
            try:
                if is_generative:
                     # manual generation handling for stream parsing
                     dev_inputs = {k: v.to(self.device) for k, v in processed_inputs.items() if isinstance(v, torch.Tensor)}
                     with torch.no_grad():
                         output_ids = self.model.generate(**dev_inputs, **gen_kwargs)
                     return {"output": output_ids}
                else: 
                     # use standard routing
                     dev_inputs = {k: v.to(self.device) for k, v in processed_inputs.items() if isinstance(v, torch.Tensor)}
                     with torch.no_grad():
                         outputs = getattr(self.model, "__call__")(**dev_inputs)
                     return {"raw_outputs": outputs}
            except Exception as e:
                return {"error": str(e)}
                 
        result = await asyncio.to_thread(_execute_sync)
        if "error" in result:
             raise RuntimeError(f"Execution Error: {result['error']}")
        
        # 3. Process outputs dynamically
        output_res = None
        confidence = 1.0
        
        if is_generative:
             output_ids = result["output"]
             if modality == "text" or "text" in input_data:
                  # slice the prompt
                  output_ids = output_ids[0][prompt_tokens:]
             else:
                  output_ids = output_ids[0]
             
             output_res = self.tokenizer.decode(output_ids, skip_special_tokens=True)
             completion_tokens = len(output_ids)
             
        elif task_type in ["sequence_classification", "image_classification"]:
             outputs = result["raw_outputs"]
             logits = outputs.logits
             probs = torch.nn.functional.softmax(logits, dim=-1)[0].cpu().tolist()
             predicted_class = logits.argmax(-1).item()
             confidence = probs[predicted_class]
             # label lookup
             output_res = self.model.config.id2label.get(predicted_class, str(predicted_class)) if getattr(self.model.config, "id2label", None) else str(predicted_class)
             completion_tokens = 0
             
        elif task_type == "question_answering":
             outputs = result["raw_outputs"]
             answer_start = torch.argmax(outputs.start_logits)
             answer_end = torch.argmax(outputs.end_logits) + 1
             answer_tokens = processed_inputs["input_ids"][0][answer_start:answer_end]
             output_res = self.tokenizer.decode(answer_tokens)
             completion_tokens = len(answer_tokens)

        elapsed = time.perf_counter() - start_time
        
        return {
            "model_name": self.model_path.split("/")[-1] if "/" in self.model_path else self.model_path.split("\\")[-1],
            "task_type": task_type,
            "mode": self.mode,
            "input": "provided inputs", 
            "output": output_res,
            "confidence": f"{confidence:.4f}",
            "metadata": {
                "ram_usage": f"{self.get_memory_usage()['ram_used_gb']:.2f}GB",
                "latency": f"{elapsed:.3f}s",
                "tokens_generated": str(completion_tokens) if is_generative else "N/A"
            }
        }
    
    async def generate_stream(self, input_data: Any, **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """Streaming endpoint for generative models"""
        if not self.task_metadata.get("is_generative"):
            raise RuntimeError("Selected model does not support streaming generation.")
            
        if not self.loaded:
            raise RuntimeError("Model not loaded")

        task_type = self.task_metadata["task_type"]
        modality = self.task_metadata["input_modality"]
        
        # 1. Process inputs
        if not self.tokenizer:
            raise RuntimeError("Model requires a tokenizer but none was loaded.")
        prompt = input_data if isinstance(input_data, str) else input_data.get("prompt", "")
        inputs = self.tokenizer(prompt, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        # 2. Setup streamer
        streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)
        
        max_tokens = kwargs.get("max_tokens", 512)
        temperature = kwargs.get("temperature", 0.7)
        top_p = kwargs.get("top_p", 0.9)
        
        gen_kwargs = {
            **inputs,
            "streamer": streamer,
            "max_new_tokens": max_tokens,
            "temperature": temperature if temperature > 0 else 1.0,
            "do_sample": temperature > 0,
            "top_p": top_p
        }

        
        if self.tokenizer and self.tokenizer.eos_token_id is not None:
             gen_kwargs["pad_token_id"] = self.tokenizer.eos_token_id

        # 3. Run generation in thread
        thread = Thread(target=self.model.generate, kwargs=gen_kwargs)
        thread.start()

        # 4. Yield tokens
        for new_text in streamer:
            yield {"token": new_text, "finish_reason": None}
            
        yield {"token": "", "finish_reason": "stop"}

    def get_memory_usage(self) -> Dict[str, Any]:
        process = psutil.Process()
        return {
            "ram_used_gb": process.memory_info().rss / (1024**3),
            "peak_ram_gb": process.memory_info().peak_wset / (1024**3) if hasattr(process.memory_info(), 'peak_wset') else 0,
            "kv_cache_mb": 0
        }

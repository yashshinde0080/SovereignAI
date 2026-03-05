"""Task Resolver - Determines model task type dynamically"""
from typing import Dict, Any, List
from transformers import AutoConfig

class TaskResolver:
    """Resolves task capabilities from HuggingFace config"""
    
    @staticmethod
    def resolve(model_path: str) -> Dict[str, Any]:
        """Inspect model config and determine task descriptors"""
        try:
            config = AutoConfig.from_pretrained(model_path, trust_remote_code=True, local_files_only=True)
        except Exception:
            try:
                config = AutoConfig.from_pretrained(model_path, trust_remote_code=True)
            except Exception as e:
                # Provide a safe default for raw GGUF / unconfigured models
                return {
                    "model_path": model_path,
                    "architectures": ["CausalLM"],
                    "model_type": "unknown",
                    "task_type": "causal_lm",
                    "input_modality": "text",
                    "is_generative": True
                }
                
        architectures: List[str] = getattr(config, "architectures", [])
        model_type: str = getattr(config, "model_type", "").lower()
        is_encoder_decoder: bool = getattr(config, "is_encoder_decoder", False)
        
        # Default assumptions
        task_category = "unknown"
        input_modality = "text"
        is_generative = False
        
        # Mapping common architecture suffixes
        if not architectures:
             # Fallback if architectures is empty
             if "gpt" in model_type or "llama" in model_type or "qwen" in model_type:
                 task_category = "causal_lm"
                 is_generative = True
             elif "bert" in model_type:
                 task_category = "masked_lm"
        else:
            arch = architectures[0].lower()
            
            # Generative language modeling
            if "causallm" in arch:
                task_category = "causal_lm"
                is_generative = True
            elif "seq2seqlm" in arch or "conditionalgeneration" in arch:
                task_category = "seq2seq_lm"
                is_generative = True
            elif "maskedlm" in arch:
                task_category = "masked_lm"
            
            # Classification
            elif "sequenceclassification" in arch:
                task_category = "sequence_classification"
            elif "tokenclassification" in arch:
                task_category = "token_classification"
            elif "multiplechoice" in arch:
                task_category = "multiple_choice"
                
            # Question Answering
            elif "questionanswering" in arch:
                task_category = "question_answering"
                
            # Vision tasks
            elif "imageclassification" in arch:
                task_category = "image_classification"
                input_modality = "image"
            elif "objectdetection" in arch:
                task_category = "object_detection"
                input_modality = "image"
            elif "vision2seq" in arch or "llava" in model_type:
                task_category = "vision2seq"
                input_modality = "multimodal"
                is_generative = True
                
            # Audio tasks
            elif "audioclassification" in arch:
                task_category = "audio_classification"
                input_modality = "audio"
            elif "speechseq2seq" in arch or "whisper" in model_type:
                task_category = "speech_seq2seq"
                input_modality = "audio"
                is_generative = True
            
            # Embeddings and Encodings
            elif "model" in arch and not is_generative and task_category == "unknown":
                 # generic bare models (Backbone-only)
                 task_category = "text_encoding"
                 
        # Additional heuristics
        if is_encoder_decoder and task_category == "unknown":
            task_category = "seq2seq_lm"
            is_generative = True
            
        return {
            "model_path": model_path,
            "architectures": architectures,
            "model_type": model_type,
            "task_type": task_category,
            "input_modality": input_modality,
            "is_generative": is_generative
        }

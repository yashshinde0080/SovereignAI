"""Task Router for Unified Execution"""
from typing import Dict, Any, Type, Optional
from transformers import (
    AutoModelForCausalLM, AutoModelForSequenceClassification,
    AutoModelForQuestionAnswering, AutoModelForImageClassification,
    AutoModelForMaskedLM, AutoModelForSeq2SeqLM, AutoModelForTokenClassification,
    AutoModelForAudioClassification, AutoModelForVision2Seq,
    AutoModelForSpeechSeq2Seq, AutoModelForTextEncoding,
    AutoModel, default_data_collator
)
import torch

class TaskRouter:
    """Routes execution based on detected task category"""
    
    TASK_CLASS_MAP = {
        "causal_lm": AutoModelForCausalLM,
        "seq2seq_lm": AutoModelForSeq2SeqLM,
        "masked_lm": AutoModelForMaskedLM,
        "sequence_classification": AutoModelForSequenceClassification,
        "token_classification": AutoModelForTokenClassification,
        "question_answering": AutoModelForQuestionAnswering,
        "image_classification": AutoModelForImageClassification,
        "vision2seq": AutoModelForVision2Seq,
        "audio_classification": AutoModelForAudioClassification,
        "speech_seq2seq": AutoModelForSpeechSeq2Seq,
        "text_encoding": AutoModelForTextEncoding,
        "unknown": AutoModel # backbone only fallback
    }
    
    @classmethod
    def get_model_class(cls, task_type: str) -> Type:
        """Get appropriate AutoModel* class for the task"""
        return cls.TASK_CLASS_MAP.get(task_type, AutoModel)
        
    @staticmethod
    def _to_device(inputs, device):
        return {k: v.to(device) for k, v in inputs.items() if isinstance(v, torch.Tensor)}
        
    @classmethod
    async def execute(cls, model: Any, task_metadata: Dict[str, Any], inputs: Dict[str, Any], device: str) -> Dict[str, Any]:
        """Routes execution correctly. Receives processed inputs."""
        task_type = task_metadata.get("task_type", "unknown")
        is_generative = task_metadata.get("is_generative", False)
        
        # Determine behavior based on generation capability or task
        if is_generative:
            # Pop generation kwargs if passed (max_tokens, temperature, etc)
            gen_kwargs = inputs.pop("generation_kwargs", {})
            device_inputs = cls._to_device(inputs, device)
            
            with torch.no_grad():
                output_ids = model.generate(**device_inputs, **gen_kwargs)
            return {"output": output_ids}
            
        elif task_type in ["sequence_classification", "image_classification", "audio_classification"]:
            device_inputs = cls._to_device(inputs, device)
            with torch.no_grad():
                outputs = model(**device_inputs)
            
            logits = outputs.logits
            probs = torch.nn.functional.softmax(logits, dim=-1)[0].cpu().tolist()
            predicted_class = logits.argmax(-1).item()
            confidence = probs[predicted_class]
            
            # Map index to label if config provides
            label = model.config.id2label.get(predicted_class, str(predicted_class)) if model.config.id2label else str(predicted_class)
            
            return {
                "output": label,
                "confidence": confidence,
                "probabilities": probs
            }
            
        elif task_type == "question_answering":
            device_inputs = cls._to_device(inputs, device)
            with torch.no_grad():
                outputs = model(**device_inputs)
            return {
                "start_logits": outputs.start_logits,
                "end_logits": outputs.end_logits
            }
            
        else:
            # Base forward pass
            device_inputs = cls._to_device(inputs, device)
            with torch.no_grad():
                 outputs = model(**device_inputs)
            
            if hasattr(outputs, "last_hidden_state"):
                return {"output": "Hidden States Emitted", "shape": list(outputs.last_hidden_state.shape)}
            return {"output": "Raw Outputs Emitted"}

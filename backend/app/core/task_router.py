"""Task Router for Unified Execution"""
from typing import Dict, Any, Type

from transformers import (
    AutoModelForCausalLM,
    AutoModelForSeq2SeqLM,
)
import torch


class TaskRouter:
    """Routes execution based on detected task category.

    Only the generative tasks the engines can actually run end-to-end are
    mapped (causal_lm, seq2seq_lm). Anything else fails loudly instead of
    silently producing garbage — unknown configs never fall back to a default
    class or a default task.
    """

    TASK_CLASS_MAP = {
        # Generative — the only tasks executed end-to-end today
        "causal_lm": AutoModelForCausalLM,
        "seq2seq_lm": AutoModelForSeq2SeqLM,
    }

    @classmethod
    def get_model_class(cls, task_type: str) -> Type:
        """Get appropriate AutoModel* class for the task"""
        if task_type not in cls.TASK_CLASS_MAP:
            raise ValueError(
                f"Task type '{task_type}' is not supported by any engine. "
                "SovereignAI executes generative (causal_lm / seq2seq_lm) "
                "models only; use a chat/instruct model."
            )
        return cls.TASK_CLASS_MAP[task_type]

    @staticmethod
    def _to_device(inputs, device):
        return {k: v.to(device) for k, v in inputs.items() if isinstance(v, torch.Tensor)}

    @classmethod
    async def execute(cls, model: Any, task_metadata: Dict[str, Any], inputs: Dict[str, Any], device: str) -> Dict[str, Any]:
        """Routes execution correctly. Receives processed inputs."""
        import asyncio
        task_type = task_metadata.get("task_type", "unknown")
        is_generative = task_metadata.get("is_generative", False)

        def _run():
            if not is_generative:
                raise ValueError(
                    f"Task type '{task_type}' is not supported end-to-end. "
                    "Only generative (causal_lm / seq2seq_lm) models are executable."
                )
            # Pop generation kwargs if passed (max_tokens, temperature, etc)
            gen_kwargs = inputs.pop("generation_kwargs", {})
            device_inputs = cls._to_device(inputs, device)

            with torch.no_grad():
                output_ids = model.generate(**device_inputs, **gen_kwargs)
            return {"output": output_ids}

        return await asyncio.to_thread(_run)

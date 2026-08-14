"""Memory Management"""
import psutil
from typing import Dict, Any, Optional


class MemoryManager:
    """Manage execution-mode selection based on available memory.

    Zone bookkeeping (allocate/release/get_stats) was deleted: no engine or
    service ever called it — each engine computes its own budget. Only
    ``suggest_mode`` remains (used by EngineFactory).
    """

    def __init__(self, max_usage_percent: float = 0.75):
        self.max_usage_percent = max_usage_percent

    def suggest_mode(self, model_size_bytes: int, model_metadata: Optional[Dict[str, Any]] = None) -> str:
        """Suggest execution mode based on memory, VRAM, and optional llmfit score.

        When model_metadata includes a name, tries llmfit for fit-scored selection.
        Falls back to simple threshold-based selection.
        """
        import torch

        # Try llmfit scoring when model metadata available
        if model_metadata and model_metadata.get("name") or model_metadata.get("id"):
            try:
                from llmfit import score_model_fit
                from llmfit.hardware import probe_hardware

                model_name = (
                    model_metadata.get("name")
                    or model_metadata.get("id")
                    or ""
                )
                hw = probe_hardware()
                fit = score_model_fit(model_name, hw)
                if fit.fit_score > 0.85 and fit.ram_required_gb < hw.ram_total_gb * 0.7:
                    return "fullram"
                elif fit.fit_score > 0.6:
                    return "layerstream"
                else:
                    return "insufficient"
            except (ImportError, Exception):
                pass

        # Legacy threshold-based selection
        if torch.cuda.is_available():
            try:
                free_vram, _ = torch.cuda.mem_get_info()
                if model_size_bytes * 1.1 < free_vram:
                    return "fullram"
            except Exception:
                pass

        available_ram = psutil.virtual_memory().available

        if model_size_bytes * 1.1 < available_ram:
            return "fullram"
        elif model_size_bytes * 0.1 < available_ram:
            return "layerstream"
        else:
            return "insufficient"

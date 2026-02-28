from typing import Dict, Optional, Any

class ModelRegistry:
    def __init__(self):
        # Mocking an in-memory SQLite registry to avoid db migrations complexity for this prototype
        self._registry: Dict[str, Dict[str, Any]] = {
            "llama3:8b": {
                "id": "llama3-8b-q4",
                "source": "huggingface",
                "size_gb": 4.9,
                "quant": "Q4_K_M",
                "downloaded": True,
                "modes": ["fullram", "layerstream"]
            },
            "mistral:7b": {
                "id": "mistral-7b-q4",
                "source": "huggingface",
                "size_gb": 4.3,
                "quant": "Q4_K_M",
                "downloaded": False,
                "modes": ["fullram", "layerstream"]
            }
        }

    def get_all_models(self) -> Dict[str, Dict[str, Any]]:
        return self._registry

    def get_model(self, model_name: str) -> Optional[Dict[str, Any]]:
        return self._registry.get(model_name)

    def register_model(self, model_name: str, metadata: Dict[str, Any]):
        self._registry[model_name] = metadata

    def remove_model(self, model_name: str) -> bool:
        if model_name in self._registry:
            del self._registry[model_name]
            return True
        return False

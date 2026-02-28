from typing import Any, Dict

class SimplePlugin:
    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "Math Calculator",
            "version": "1.0",
            "description": "Calculates simple math expressions."
        }

    def execute(self, payload: Any) -> Any:
        try:
            return {"result": eval(str(payload))}
        except Exception as e:
            return {"error": str(e)}

def get_plugin():
    return SimplePlugin()

from typing import Any, Dict

class PluginInterface:
    def get_metadata(self) -> Dict[str, Any]:
        """Returns name, version, description of the plugin."""
        raise NotImplementedError

    def execute(self, payload: Any) -> Any:
        """Execute the plugin action."""
        raise NotImplementedError

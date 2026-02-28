import os
import importlib.util
from typing import Dict, Any
import logging
from .plugin_interface import PluginInterface

logger = logging.getLogger("sovereign-plugins")

class PluginManager:
    def __init__(self, plugins_dir: str = "plugins_data"):
        self.plugins_dir = plugins_dir
        self.plugins: Dict[str, PluginInterface] = {}
        # Ensure dir exists
        os.makedirs(self.plugins_dir, exist_ok=True)
        self.load_plugins()

    def load_plugins(self):
        self.plugins.clear()
        if not os.path.exists(self.plugins_dir):
            return

        for filename in os.listdir(self.plugins_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                plugin_name = filename[:-3]
                path = os.path.join(self.plugins_dir, filename)
                try:
                    spec = importlib.util.spec_from_file_location(plugin_name, path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Assuming each plugin file defines a 'get_plugin()' function
                    # that returns an instance of PluginInterface
                    if hasattr(module, 'get_plugin'):
                        plugin_instance = module.get_plugin()
                        self.plugins[plugin_name] = plugin_instance
                        logger.info(f"Loaded plugin: {plugin_name}")
                except Exception as e:
                    logger.error(f"Failed to load plugin {plugin_name}: {e}")

    def get_all_plugins(self) -> Dict[str, Dict[str, Any]]:
        return {name: plugin.get_metadata() for name, plugin in self.plugins.items()}

    def execute_plugin(self, name: str, payload: Any) -> Any:
        if name not in self.plugins:
            raise ValueError(f"Plugin {name} not found")
        # In a real enterprise system this would run inside a secure sandbox
        # For prototype we execute directly
        return self.plugins[name].execute(payload)

"""
Copyright 2025, Vijay Challa - Use of this source code follows the MIT license found in the LICENSE file.

Plugin loader for auto-discovering and loading plugins
"""

import importlib
import inspect
from pathlib import Path
from typing import List, Type
import logging

from artemis.plugin.base import PluginInterface

logger = logging.getLogger("artemis.plugin.loader")


class PluginLoader:
    """Handles loading and registering plugins."""
    
    def __init__(self, plugins_dir: str = "plugins"):
        """
        Initialize plugin loader.
        
        Args:
            plugins_dir: Directory containing plugin modules
        """
        self.plugins_dir = Path(plugins_dir)
        self.loaded_plugins: List[Type[PluginInterface]] = []
    
    def discover_plugins(self) -> List[Type[PluginInterface]]:
        """
        Discover all plugins in the plugins directory.
        
        Returns:
            List of plugin classes
        """
        plugins = []
        
        if not self.plugins_dir.exists():
            logger.warning(f"Plugins directory {self.plugins_dir} does not exist")
            return plugins
        
        # Find all plugin modules
        for plugin_dir in self.plugins_dir.iterdir():
            if not plugin_dir.is_dir():
                continue
            
            # Look for __init__.py or main plugin file
            plugin_files = [
                plugin_dir / "__init__.py",
                plugin_dir / f"{plugin_dir.name}.py",
            ]
            
            for plugin_file in plugin_files:
                if not plugin_file.exists():
                    continue
                
                try:
                    # Import the module
                    # Try __init__.py first, then plugin file
                    if plugin_file.name == "__init__.py":
                        module_name = f"plugins.{plugin_dir.name}"
                    else:
                        module_name = f"plugins.{plugin_dir.name}.{plugin_file.stem}"
                    
                    module = importlib.import_module(module_name)
                    
                    # Find PluginInterface classes
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if (issubclass(obj, PluginInterface) and 
                            obj != PluginInterface and
                            obj.__module__ == module.__name__):
                            plugins.append(obj)
                            logger.info(f"Discovered plugin: {name} from {module_name}")
                
                except Exception as e:
                    logger.error(f"Error loading plugin from {plugin_file}: {e}", exc_info=True)
        
        return plugins
    
    def load_plugins(self, bot) -> None:
        """
        Load and register all discovered plugins.
        
        Args:
            bot: Bot instance to register plugins with
        """
        plugins = self.discover_plugins()
        
        for plugin_class in plugins:
            try:
                plugin_class.register(bot)
                self.loaded_plugins.append(plugin_class)
                logger.info(f"Loaded plugin: {plugin_class.__name__}")
            except Exception as e:
                logger.error(f"Error registering plugin {plugin_class.__name__}: {e}", exc_info=True)

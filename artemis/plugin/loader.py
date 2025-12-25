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
            plugins_dir: Directory containing plugin modules (relative to project root)
        """
        # Resolve path relative to project root (where main.py is)
        project_root = Path(__file__).parent.parent.parent
        self.plugins_dir = project_root / plugins_dir
        self.loaded_plugins: List[Type[PluginInterface]] = []
        logger.info(f"Plugin loader initialized with plugins directory: {self.plugins_dir}")
    
    def discover_plugins(self) -> List[Type[PluginInterface]]:
        """
        Discover all plugins in the plugins directory.
        
        Returns:
            List of plugin classes
        """
        plugins = []
        
        if not self.plugins_dir.exists():
            logger.error(f"Plugins directory {self.plugins_dir} does not exist! Current working directory: {Path.cwd()}")
            return plugins
        
        logger.info(f"Discovering plugins in: {self.plugins_dir}")
        
        # Find all plugin modules
        for plugin_dir in self.plugins_dir.iterdir():
            if not plugin_dir.is_dir():
                continue
            
            logger.debug(f"Checking plugin directory: {plugin_dir.name}")
            
            # Try importing the plugin module (plugins.plugin_name)
            # This will work whether __init__.py imports from the main file or not
            module_name = f"plugins.{plugin_dir.name}"
            
            try:
                module = importlib.import_module(module_name)
                logger.debug(f"Imported module: {module_name}")
                
                # Find PluginInterface classes in this module
                # Classes might be imported from submodules (e.g., __init__.py imports from plugin.py)
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (issubclass(obj, PluginInterface) and 
                        obj != PluginInterface):
                        # Check if class is defined in this module or imported from a submodule
                        # Allow classes from submodules of the same plugin directory
                        obj_module = obj.__module__
                        if (obj_module == module.__name__ or 
                            obj_module.startswith(f"{module.__name__}.")):
                            if obj not in plugins:  # Avoid duplicates
                                plugins.append(obj)
                                logger.info(f"Discovered plugin: {name} from {obj_module} (via {module_name})")
                
            
            except ImportError as e:
                logger.error(f"Failed to import plugin module {module_name}: {e}")
            except Exception as e:
                logger.error(f"Error loading plugin from {plugin_dir}: {e}", exc_info=True)
        
        return plugins
    
    def load_plugins(self, bot) -> None:
        """
        Load and register all discovered plugins.
        
        Args:
            bot: Bot instance to register plugins with
        """
        plugins = self.discover_plugins()
        
        if not plugins:
            logger.warning("No plugins discovered! Check plugin directory and plugin class definitions.")
        
        for plugin_class in plugins:
            try:
                logger.info(f"Registering plugin: {plugin_class.__name__}")
                plugin_class.register(bot)
                self.loaded_plugins.append(plugin_class)
                logger.info(f"Successfully loaded plugin: {plugin_class.__name__}")
            except Exception as e:
                logger.error(f"Error registering plugin {plugin_class.__name__}: {e}", exc_info=True)

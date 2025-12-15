"""Plugin manager for loading and managing plugins."""

import importlib
import importlib.util
import inspect
import os
import sys
from pathlib import Path
from typing import Dict, List, Type, Optional
import asyncio

import structlog
import yaml
from telegram.ext import Application, CommandHandler

from .base import (
    BasePlugin,
    CommandPlugin,
    HandlerPlugin,
    StatisticsPlugin,
    ServicePlugin,
)


logger = structlog.get_logger(__name__)


class PluginManager:
    """Manages plugin loading, initialization, and lifecycle."""
    
    def __init__(self, plugin_dirs: List[str] = None):
        """
        Initialize the plugin manager.
        
        Args:
            plugin_dirs: List of directories to search for plugins.
                        Defaults to the main plugins directory
        """
        if plugin_dirs is None:
            # Default to the main plugins directory
            plugin_dirs = [os.path.dirname(__file__)]
        
        self.plugin_dirs = plugin_dirs
        self.config_file = os.path.join(plugin_dirs[0], 'plugins.yaml')
        
        # Initialize logger first
        self._logger = structlog.get_logger(__name__)
        
        # Load config after logger is available
        self.plugin_config = self._load_config()
        
        self._plugins: Dict[str, BasePlugin] = {}
        self._command_plugins: Dict[str, CommandPlugin] = {}
        self._handler_plugins: List[HandlerPlugin] = []
        self._statistics_plugins: Dict[str, StatisticsPlugin] = {}
        self._service_plugins: Dict[str, ServicePlugin] = {}
        
        # Hot reload tracking
        self._file_mtimes: Dict[str, float] = {}
        self._hot_reload_task: Optional[asyncio.Task] = None
    
    def _load_config(self) -> dict:
        """Load plugin configuration from YAML file."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = yaml.safe_load(f) or {}
                    self._logger.info("plugin_config_loaded", file=self.config_file)
                    return config
            except Exception as e:
                self._logger.error(
                    "failed_to_load_plugin_config",
                    file=self.config_file,
                    error=str(e)
                )
        return {'plugins': {}, 'settings': {}}
    
    def _is_plugin_enabled_in_config(self, plugin_name: str) -> bool:
        """Check if plugin is enabled in YAML config."""
        plugin_config = self.plugin_config.get('plugins', {}).get(plugin_name, {})
        return plugin_config.get('enabled', True)  # Default to enabled
    
    def _should_load_file(self, filepath: Path) -> bool:
        """
        Check if a file/directory should be loaded as a plugin.
        
        Rules:
        - Must be .py file or directory with __init__.py
        - Must NOT start with underscore (_)
        - Private files/dirs (__pycache__, __init__.py, etc.) are skipped
        """
        name = filepath.name
        
        # Skip private files/directories
        if name.startswith('_'):
            return False
        
        # Skip certain files
        if name in ['base.py', 'manager.py', 'plugins.yaml', 'README.md']:
            return False
        
        # Accept .py files
        if filepath.is_file() and filepath.suffix == '.py':
            return True
        
        # Accept directories with __init__.py
        if filepath.is_dir():
            init_file = filepath / '__init__.py'
            if init_file.exists():
                return True
        
        return False
    
    def discover_plugins(self) -> List[Type[BasePlugin]]:
        """
        Discover all plugin classes in plugin directories.
        
        Returns:
            List of plugin classes (not instances)
        """
        plugin_classes = []
        
        for plugin_dir in self.plugin_dirs:
            if not os.path.exists(plugin_dir):
                self._logger.warning("plugin_dir_not_found", path=plugin_dir)
                continue
            
            plugin_path = Path(plugin_dir)
            
            # Find all Python files and directories
            for item in plugin_path.iterdir():
                if not self._should_load_file(item):
                    continue
                
                try:
                    # Determine module name
                    if item.is_file():
                        module_name = f"tgstats.plugins.{item.stem}"
                        file_path = str(item)
                    else:
                        module_name = f"tgstats.plugins.{item.name}"
                        file_path = str(item / '__init__.py')
                    
                    # Track file modification time for hot reload
                    self._file_mtimes[file_path] = os.path.getmtime(file_path)
                    
                    # Load module
                    if module_name in sys.modules:
                        # Reload if already loaded
                        module = importlib.reload(sys.modules[module_name])
                    else:
                        module = importlib.import_module(module_name)
                    
                    # Find all plugin classes in the module
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        # Skip base classes and non-plugin classes
                        if (issubclass(obj, BasePlugin) and 
                            obj not in [BasePlugin, CommandPlugin, HandlerPlugin, 
                                       StatisticsPlugin, ServicePlugin] and
                            obj.__module__.startswith(module_name)):
                            
                            plugin_classes.append(obj)
                            self._logger.info(
                                "discovered_plugin",
                                plugin_class=name,
                                module=module_name,
                                file=item.name
                            )
                
                except Exception as e:
                    self._logger.error(
                        "failed_to_load_plugin_module",
                        item=str(item),
                        error=str(e),
                        exc_info=True
                    )
        
        return plugin_classes
    
    async def load_plugins(self) -> None:
        """Discover and instantiate all plugins."""
        plugin_classes = self.discover_plugins()
        
        for plugin_class in plugin_classes:
            try:
                plugin = plugin_class()
                plugin_name = plugin.metadata.name
                
                # Check if disabled in YAML config
                if not self._is_plugin_enabled_in_config(plugin_name):
                    self._logger.info(
                        "plugin_disabled_in_config",
                        plugin=plugin_name
                    )
                    continue
                
                # Check dependencies
                if not self._check_dependencies(plugin):
                    self._logger.warning(
                        "plugin_dependencies_not_met",
                        plugin=plugin_name,
                        dependencies=plugin.metadata.dependencies
                    )
                    continue
                
                # Pass plugin-specific config
                plugin_config = self.plugin_config.get('plugins', {}).get(plugin_name, {}).get('config', {})
                if plugin_config:
                    plugin._config = plugin_config
                
                # Store in appropriate registry
                self._plugins[plugin_name] = plugin
                
                if isinstance(plugin, CommandPlugin):
                    self._command_plugins[plugin_name] = plugin
                
                if isinstance(plugin, HandlerPlugin):
                    self._handler_plugins.append(plugin)
                
                if isinstance(plugin, StatisticsPlugin):
                    stat_name = plugin.get_stat_name()
                    self._statistics_plugins[stat_name] = plugin
                
                if isinstance(plugin, ServicePlugin):
                    service_name = plugin.get_service_name()
                    self._service_plugins[service_name] = plugin
                
                self._logger.info(
                    "plugin_loaded",
                    plugin=plugin_name,
                    version=plugin.metadata.version,
                    type=plugin.__class__.__base__.__name__
                )
            
            except Exception as e:
                self._logger.error(
                    "failed_to_load_plugin",
                    plugin_class=plugin_class.__name__,
                    error=str(e),
                    exc_info=True
                )
    
    async def initialize_plugins(self, app: Application) -> None:
        """
        Initialize all loaded plugins.
        
        Args:
            app: The Telegram Application instance
        """
        for plugin_name, plugin in self._plugins.items():
            try:
                await plugin.initialize(app)
                self._logger.info("plugin_initialized", plugin=plugin_name)
            except Exception as e:
                self._logger.error(
                    "plugin_initialization_failed",
                    plugin=plugin_name,
                    error=str(e),
                    exc_info=True
                )
                plugin.disable()
    
    async def shutdown_plugins(self) -> None:
        """Shutdown all plugins gracefully."""
        for plugin_name, plugin in self._plugins.items():
            try:
                await plugin.shutdown()
                self._logger.info("plugin_shutdown", plugin=plugin_name)
            except Exception as e:
                self._logger.error(
                    "plugin_shutdown_failed",
                    plugin=plugin_name,
                    error=str(e),
                    exc_info=True
                )
    
    def register_command_plugins(self, app: Application) -> None:
        """Register all command plugins with the application."""
        for plugin_name, plugin in self._command_plugins.items():
            if not plugin.enabled:
                continue
            
            try:
                commands = plugin.get_commands()
                for command_name, handler in commands.items():
                    app.add_handler(CommandHandler(command_name, handler))
                    self._logger.info(
                        "command_registered",
                        plugin=plugin_name,
                        command=command_name
                    )
            except Exception as e:
                self._logger.error(
                    "failed_to_register_commands",
                    plugin=plugin_name,
                    error=str(e),
                    exc_info=True
                )
    
    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        """Get a plugin by name."""
        return self._plugins.get(name)
    
    def get_statistics_plugins(self) -> Dict[str, StatisticsPlugin]:
        """Get all statistics plugins."""
        return {k: v for k, v in self._statistics_plugins.items() if v.enabled}
    
    def get_handler_plugins(self) -> List[HandlerPlugin]:
        """Get all enabled handler plugins."""
        return [p for p in self._handler_plugins if p.enabled]
    
    def get_service_plugin(self, service_name: str) -> Optional[ServicePlugin]:
        """Get a service plugin by name."""
        plugin = self._service_plugins.get(service_name)
        return plugin if plugin and plugin.enabled else None
    
    def list_plugins(self) -> Dict[str, Dict]:
        """List all plugins with their metadata."""
        return {
            name: {
                'version': plugin.metadata.version,
                'description': plugin.metadata.description,
                'author': plugin.metadata.author,
                'enabled': plugin.enabled,
                'type': plugin.__class__.__base__.__name__,
            }
            for name, plugin in self._plugins.items()
        }
    
    def _check_dependencies(self, plugin: BasePlugin) -> bool:
        """Check if plugin dependencies are met."""
        for dep in plugin.metadata.dependencies:
            try:
                importlib.import_module(dep)
            except ImportError:
                return False
        return True
    
    def enable_plugin(self, name: str) -> bool:
        """Enable a plugin by name."""
        plugin = self._plugins.get(name)
        if plugin:
            plugin.enable()
            return True
        return False
    
    def disable_plugin(self, name: str) -> bool:
        """Disable a plugin by name."""
        plugin = self._plugins.get(name)
        if plugin:
            plugin.disable()
            return True
        return False
    
    async def start_hot_reload(self, app: Application) -> None:
        """Start hot reload monitoring if enabled."""
        hot_reload_enabled = self.plugin_config.get('settings', {}).get('hot_reload', True)
        
        if not hot_reload_enabled:
            self._logger.info("hot_reload_disabled")
            return
        
        interval = self.plugin_config.get('settings', {}).get('reload_check_interval', 3.0)
        
        self._logger.info("hot_reload_started", interval=interval)
        self._hot_reload_task = asyncio.create_task(self._hot_reload_loop(app, interval))
    
    async def stop_hot_reload(self) -> None:
        """Stop hot reload monitoring."""
        if self._hot_reload_task:
            self._hot_reload_task.cancel()
            try:
                await self._hot_reload_task
            except asyncio.CancelledError:
                pass
            self._logger.info("hot_reload_stopped")
    
    async def _hot_reload_loop(self, app: Application, interval: float) -> None:
        """Monitor plugin files for changes and reload."""
        while True:
            try:
                await asyncio.sleep(interval)
                
                # Check if any plugin files have changed
                changed_files = []
                
                for file_path, old_mtime in list(self._file_mtimes.items()):
                    try:
                        if os.path.exists(file_path):
                            current_mtime = os.path.getmtime(file_path)
                            if current_mtime > old_mtime:
                                changed_files.append(file_path)
                                self._file_mtimes[file_path] = current_mtime
                    except Exception as e:
                        self._logger.error(
                            "error_checking_file_mtime",
                            file=file_path,
                            error=str(e)
                        )
                
                # Also check for new files
                for plugin_dir in self.plugin_dirs:
                    if not os.path.exists(plugin_dir):
                        continue
                    
                    plugin_path = Path(plugin_dir)
                    for item in plugin_path.iterdir():
                        if not self._should_load_file(item):
                            continue
                        
                        if item.is_file():
                            file_path = str(item)
                        else:
                            file_path = str(item / '__init__.py')
                        
                        # New file detected
                        if file_path not in self._file_mtimes:
                            changed_files.append(file_path)
                            self._file_mtimes[file_path] = os.path.getmtime(file_path)
                
                if changed_files:
                    self._logger.info(
                        "plugin_files_changed",
                        count=len(changed_files),
                        files=[os.path.basename(f) for f in changed_files]
                    )
                    
                    # Reload all plugins
                    await self._reload_plugins(app)
                    
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self._logger.error(
                    "hot_reload_error",
                    error=str(e),
                    exc_info=True
                )
    
    async def _reload_plugins(self, app: Application) -> None:
        """Reload all plugins."""
        self._logger.info("reloading_plugins")
        
        # Shutdown existing plugins
        for plugin_name, plugin in list(self._plugins.items()):
            try:
                await plugin.shutdown()
            except Exception as e:
                self._logger.error(
                    "error_shutting_down_plugin_for_reload",
                    plugin=plugin_name,
                    error=str(e)
                )
        
        # Clear registries
        self._plugins.clear()
        self._command_plugins.clear()
        self._handler_plugins.clear()
        self._statistics_plugins.clear()
        self._service_plugins.clear()
        
        # Reload config
        self.plugin_config = self._load_config()
        
        # Reload plugins
        await self.load_plugins()
        await self.initialize_plugins(app)
        self.register_command_plugins(app)
        
        self._logger.info(
            "plugins_reloaded",
            count=len(self._plugins),
            plugins=list(self._plugins.keys())
        )

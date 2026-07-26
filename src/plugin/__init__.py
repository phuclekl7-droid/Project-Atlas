"""
Plugin module: Manages dynamic loading of external tools and capabilities.

Provides:
- BasePlugin (ABC) — interface for all plugins with execute() method
- PluginResult — standardized result dataclass
- PluginLoader — dynamic loading using importlib with built-in plugin registry
"""

import importlib
import inspect
import pkgutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from src.core import (
    AssistantError,
    PluginExecutionError,
    setup_logger,
    truncate_text,
)

logger = setup_logger("plugin")


# ============================================================
# Plugin Data Models
# ============================================================


@dataclass
class PluginResult:
    """
    Standardized result returned by any plugin.

    Attributes:
        success: Whether the plugin executed successfully
        output: Human-readable result text
        data: Optional structured data (for programmatic use)
        error: Error message if success=False
    """

    success: bool = True
    output: str = ""
    data: Optional[Any] = None
    error: str = ""

    def __repr__(self) -> str:
        if self.success:
            preview = truncate_text(self.output, max_length=60)
            return f"PluginResult(success=True, output={preview!r})"
        return f"PluginResult(success=False, error={self.error!r})"


# ============================================================
# Base Plugin (ABC)
# ============================================================


class BasePlugin(ABC):
    """
    Abstract base class for all plugins.

    Subclasses must define:
    - name: Human-readable plugin name
    - description: Short description of what the plugin does
    - execute(input_str): Main execution method

    Usage:
        class MyPlugin(BasePlugin):
            name = "my_plugin"
            description = "Does something useful"
            def execute(self, input_str: str) -> PluginResult:
                ...
    """

    name: str = "unnamed"
    description: str = "No description provided"

    def __init__(self):
        logger.debug(f"Plugin initialized: {self.name}")

    @abstractmethod
    def execute(self, input_str: str) -> PluginResult:
        """
        Execute the plugin with the given input.

        Args:
            input_str: Input string from the user (e.g., "2 + 3")

        Returns:
            PluginResult with success status and output
        """
        ...

    def get_info(self) -> dict:
        """Return plugin metadata."""
        return {
            "name": self.name,
            "description": self.description,
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"


# ============================================================
# Plugin Loader
# ============================================================


class PluginLoader:
    """
    Dynamically loads plugins using importlib.

    Scans the src.plugins package for all classes that inherit from BasePlugin.
    Also supports loading plugins from external paths.

    Usage:
        loader = PluginLoader()
        loader.discover()  # Find all plugins
        plugin = loader.get("calculator")
        result = plugin.execute("2 + 3")
    """

    def __init__(self, plugin_package: str = "src.plugins"):
        self.plugin_package = plugin_package
        self._plugins: dict[str, BasePlugin] = {}

    # ── Plugin Discovery ──

    def discover(self) -> dict[str, BasePlugin]:
        """
        Scan the plugins package and load all BasePlugin subclasses.

        Returns:
            Dict of {plugin_name: plugin_instance}
        """
        self._plugins = {}

        try:
            package = importlib.import_module(self.plugin_package)
            package_path = getattr(package, "__path__", [])

            for finder, module_name, is_pkg in pkgutil.iter_modules(package_path):
                full_module = f"{self.plugin_package}.{module_name}"

                try:
                    module = importlib.import_module(full_module)
                    self._register_plugins_from_module(module)
                except Exception as e:
                    logger.warning(f"Failed to load plugin module {full_module}: {e}")

        except ImportError as e:
            logger.warning(f"Plugin package {self.plugin_package} not found: {e}")

        if not self._plugins:
            logger.debug("No plugins discovered")

        return self._plugins

    def _register_plugins_from_module(self, module) -> None:
        """Scan a module for BasePlugin subclasses and register them."""
        for name, obj in inspect.getmembers(module):
            if (
                inspect.isclass(obj)
                and issubclass(obj, BasePlugin)
                and obj is not BasePlugin
                and not inspect.isabstract(obj)
            ):
                try:
                    instance = obj()
                    plugin_name = instance.name
                    if plugin_name in self._plugins:
                        logger.warning(
                            f"Duplicate plugin name '{plugin_name}' — "
                            f"overriding {type(self._plugins[plugin_name]).__name__} "
                            f"with {obj.__name__}"
                        )
                    self._plugins[plugin_name] = instance
                    logger.debug(f"Registered plugin: {plugin_name}")
                except Exception as e:
                    logger.warning(f"Failed to instantiate plugin {obj.__name__}: {e}")

    # ── Plugin Access ──

    def get(self, name: str) -> Optional[BasePlugin]:
        """Get a plugin by name. Returns None if not found."""
        return self._plugins.get(name)

    def get_all(self) -> list[BasePlugin]:
        """Get all loaded plugins as a list."""
        return list(self._plugins.values())

    def list_plugins(self) -> list[dict]:
        """Get metadata for all loaded plugins."""
        return [
            {"name": p.name, "description": p.description}
            for p in self._plugins.values()
        ]

    def execute(self, name: str, input_str: str) -> PluginResult:
        """
        Execute a plugin by name.

        Args:
            name: Plugin name (e.g., "calculator")
            input_str: Input for the plugin (e.g., "2 + 3")

        Returns:
            PluginResult from the plugin execution

        Raises:
            PluginExecutionError if plugin not found or execution fails
        """
        plugin = self.get(name)
        if plugin is None:
            raise PluginExecutionError(
                f"Plugin '{name}' not found. Available: {', '.join(self._plugins.keys())}"
            )

        logger.info(f"Executing plugin '{name}' with input: {input_str!r}")

        try:
            result = plugin.execute(input_str)
            logger.info(f"Plugin '{name}' completed: success={result.success}")
            return result
        except PluginExecutionError:
            raise
        except Exception as e:
            raise PluginExecutionError(
                f"Plugin '{name}' failed during execution",
                details=str(e),
            )

    # ── Utilities ──

    def reload(self) -> dict[str, BasePlugin]:
        """Re-discover all plugins. Useful after adding new plugins at runtime."""
        self._plugins = {}
        return self.discover()

    def __repr__(self) -> str:
        count = len(self._plugins)
        names = ", ".join(self._plugins.keys()) if self._plugins else "none"
        return f"PluginLoader(plugins={count}: {names})"

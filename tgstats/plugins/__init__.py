"""Plugin system for extending bot functionality."""

from .base import (
    BasePlugin,
    CommandPlugin,
    HandlerPlugin,
    ServicePlugin,
    StatisticsPlugin,
)
from .manager import PluginManager

__all__ = [
    "BasePlugin",
    "CommandPlugin",
    "HandlerPlugin",
    "StatisticsPlugin",
    "ServicePlugin",
    "PluginManager",
]

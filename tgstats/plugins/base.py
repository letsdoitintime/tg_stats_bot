"""Base classes for all plugins."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Callable
from dataclasses import dataclass

import structlog
from telegram import Update
from telegram.ext import Application, ContextTypes
from sqlalchemy.ext.asyncio import AsyncSession


logger = structlog.get_logger(__name__)


@dataclass
class PluginMetadata:
    """Metadata for a plugin."""
    name: str
    version: str
    description: str
    author: str
    dependencies: List[str] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class BasePlugin(ABC):
    """Base class for all plugins."""
    
    def __init__(self):
        self._enabled = True
        self._logger = structlog.get_logger(self.__class__.__name__)
    
    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        pass
    
    @abstractmethod
    async def initialize(self, app: Application) -> None:
        """
        Initialize the plugin.
        
        Called when the plugin is loaded, before the bot starts.
        Use this to set up any resources, validate configuration, etc.
        """
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """
        Shutdown the plugin gracefully.
        
        Called when the bot is shutting down.
        Use this to clean up resources, save state, etc.
        """
        pass
    
    def enable(self) -> None:
        """Enable the plugin."""
        self._enabled = True
        self._logger.info("plugin_enabled", plugin=self.metadata.name)
    
    def disable(self) -> None:
        """Disable the plugin."""
        self._enabled = False
        self._logger.info("plugin_disabled", plugin=self.metadata.name)
    
    @property
    def enabled(self) -> bool:
        """Check if plugin is enabled."""
        return self._enabled


class CommandPlugin(BasePlugin):
    """Plugin that adds new commands to the bot."""
    
    @abstractmethod
    def get_commands(self) -> Dict[str, Callable]:
        """
        Return a dictionary of command names and their handler functions.
        
        Returns:
            Dict mapping command names (without /) to async handler functions.
            Handler signature: async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None
        
        Example:
            {
                'mystats': my_stats_command_handler,
                'export': export_command_handler,
            }
        """
        pass
    
    @abstractmethod
    def get_command_descriptions(self) -> Dict[str, str]:
        """
        Return descriptions for each command (for help text).
        
        Returns:
            Dict mapping command names to their descriptions.
        """
        pass


class HandlerPlugin(BasePlugin):
    """Plugin that processes messages, reactions, or other updates."""
    
    @abstractmethod
    async def process_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession
    ) -> None:
        """
        Process a message update.
        
        Called for every message received by the bot (after core processing).
        """
        pass
    
    async def process_reaction(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession
    ) -> None:
        """Process a reaction update (optional)."""
        pass
    
    async def process_edited_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession
    ) -> None:
        """Process an edited message (optional)."""
        pass


class StatisticsPlugin(BasePlugin):
    """Plugin that provides new statistics/analytics."""
    
    @abstractmethod
    async def calculate_stats(
        self,
        session: AsyncSession,
        chat_id: int,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Calculate custom statistics for a chat.
        
        Args:
            session: Database session
            chat_id: Chat ID to analyze
            **kwargs: Additional parameters (time range, filters, etc.)
        
        Returns:
            Dictionary with statistics results
        """
        pass
    
    @abstractmethod
    def get_stat_name(self) -> str:
        """Return the name/key for this statistic."""
        pass
    
    @abstractmethod
    def get_stat_description(self) -> str:
        """Return a human-readable description of this statistic."""
        pass


class ServicePlugin(BasePlugin):
    """Plugin that extends bot services with new functionality."""
    
    @abstractmethod
    async def execute(
        self,
        session: AsyncSession,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute the plugin's service logic.
        
        Args:
            session: Database session
            *args, **kwargs: Service-specific parameters
        
        Returns:
            Service-specific result
        """
        pass
    
    @abstractmethod
    def get_service_name(self) -> str:
        """Return the service name for registration."""
        pass

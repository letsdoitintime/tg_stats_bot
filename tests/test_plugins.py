"""Tests for the plugin system."""

import pytest
from unittest.mock import Mock, AsyncMock

from tgstats.plugins import PluginManager, BasePlugin, CommandPlugin, StatisticsPlugin
from tgstats.plugins.base import PluginMetadata


class SimpleCommandPlugin(CommandPlugin):
    """Simple test command plugin."""
    
    @property
    def metadata(self):
        return PluginMetadata(
            name="test_command",
            version="1.0.0",
            description="Test command plugin",
            author="Test"
        )
    
    async def initialize(self, app):
        pass
    
    async def shutdown(self):
        pass
    
    def get_commands(self):
        return {'test': self._test_handler}
    
    def get_command_descriptions(self):
        return {'test': 'Test command'}
    
    async def _test_handler(self, update, context):
        pass


class SimpleStatisticsPlugin(StatisticsPlugin):
    """Simple test statistics plugin."""
    
    @property
    def metadata(self):
        return PluginMetadata(
            name="test_stats",
            version="1.0.0",
            description="Test stats plugin",
            author="Test"
        )
    
    async def initialize(self, app):
        pass
    
    async def shutdown(self):
        pass
    
    def get_stat_name(self):
        return "test_stat"
    
    def get_stat_description(self):
        return "Test statistic"
    
    async def calculate_stats(self, session, chat_id, **kwargs):
        return {'value': 42}


def test_plugin_metadata():
    """Test plugin metadata creation."""
    metadata = PluginMetadata(
        name="test",
        version="1.0.0",
        description="Test plugin",
        author="Test Author",
        dependencies=["dep1", "dep2"]
    )
    
    assert metadata.name == "test"
    assert metadata.version == "1.0.0"
    assert metadata.description == "Test plugin"
    assert metadata.author == "Test Author"
    assert len(metadata.dependencies) == 2


def test_command_plugin_creation():
    """Test command plugin can be created."""
    plugin = SimpleCommandPlugin()
    
    assert plugin.metadata.name == "test_command"
    assert plugin.enabled is True
    assert len(plugin.get_commands()) == 1
    assert 'test' in plugin.get_commands()


def test_statistics_plugin_creation():
    """Test statistics plugin can be created."""
    plugin = SimpleStatisticsPlugin()
    
    assert plugin.metadata.name == "test_stats"
    assert plugin.get_stat_name() == "test_stat"
    assert plugin.enabled is True


@pytest.mark.asyncio
async def test_statistics_plugin_calculate():
    """Test statistics plugin calculation."""
    plugin = SimpleStatisticsPlugin()
    
    mock_session = Mock()
    result = await plugin.calculate_stats(mock_session, 123)
    
    assert result == {'value': 42}


def test_plugin_enable_disable():
    """Test plugin enable/disable functionality."""
    plugin = SimpleCommandPlugin()
    
    assert plugin.enabled is True
    
    plugin.disable()
    assert plugin.enabled is False
    
    plugin.enable()
    assert plugin.enabled is True


def test_plugin_manager_creation():
    """Test plugin manager can be created."""
    manager = PluginManager()
    
    assert manager is not None
    assert len(manager._plugins) == 0


def test_plugin_manager_list_empty():
    """Test listing plugins when none are loaded."""
    manager = PluginManager()
    plugins = manager.list_plugins()
    
    assert isinstance(plugins, dict)
    assert len(plugins) == 0


@pytest.mark.asyncio
async def test_plugin_manager_manual_load():
    """Test manually adding plugins to manager."""
    manager = PluginManager(plugin_dirs=[])  # Empty dirs to prevent auto-discovery
    
    # Manually add plugins for testing
    cmd_plugin = SimpleCommandPlugin()
    stat_plugin = SimpleStatisticsPlugin()
    
    manager._plugins["test_command"] = cmd_plugin
    manager._command_plugins["test_command"] = cmd_plugin
    
    manager._plugins["test_stats"] = stat_plugin
    manager._statistics_plugins["test_stat"] = stat_plugin
    
    # Test retrieval
    plugins = manager.list_plugins()
    assert len(plugins) == 2
    
    assert manager.get_plugin("test_command") is cmd_plugin
    assert manager.get_plugin("test_stats") is stat_plugin
    
    # Test statistics plugins retrieval
    stats_plugins = manager.get_statistics_plugins()
    assert "test_stat" in stats_plugins


def test_plugin_manager_enable_disable():
    """Test enabling/disabling plugins through manager."""
    manager = PluginManager(plugin_dirs=[])
    
    plugin = SimpleCommandPlugin()
    manager._plugins["test_command"] = plugin
    
    assert plugin.enabled is True
    
    # Disable through manager
    result = manager.disable_plugin("test_command")
    assert result is True
    assert plugin.enabled is False
    
    # Enable through manager
    result = manager.enable_plugin("test_command")
    assert result is True
    assert plugin.enabled is True
    
    # Try non-existent plugin
    result = manager.disable_plugin("nonexistent")
    assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

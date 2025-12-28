"""Tests for plugin dependency resolution."""

import pytest
from unittest.mock import Mock

from tgstats.plugins.dependency_resolver import PluginDependencyResolver
from tgstats.plugins.base import BasePlugin, PluginMetadata


class MockPlugin(BasePlugin):
    """Mock plugin for testing."""

    def __init__(self, name: str, dependencies: list = None):
        super().__init__()
        self._name = name
        self._dependencies = dependencies or []

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name=self._name,
            version="1.0",
            description="Mock plugin",
            author="Test",
            dependencies=self._dependencies,
        )

    async def initialize(self, app):
        pass

    async def shutdown(self):
        pass


class TestPluginDependencyResolver:
    """Test plugin dependency resolution."""

    def test_resolve_no_dependencies(self):
        """Test resolving plugins with no dependencies."""
        resolver = PluginDependencyResolver()

        plugins = {
            "plugin1": MockPlugin("plugin1"),
            "plugin2": MockPlugin("plugin2"),
            "plugin3": MockPlugin("plugin3"),
        }

        order = resolver.resolve_dependencies(plugins)

        assert len(order) == 3
        assert set(order) == {"plugin1", "plugin2", "plugin3"}

    def test_resolve_linear_dependencies(self):
        """Test resolving plugins with linear dependencies."""
        resolver = PluginDependencyResolver()

        plugins = {
            "plugin1": MockPlugin("plugin1"),
            "plugin2": MockPlugin("plugin2", ["plugin1"]),
            "plugin3": MockPlugin("plugin3", ["plugin2"]),
        }

        order = resolver.resolve_dependencies(plugins)

        # plugin1 should come before plugin2, plugin2 before plugin3
        assert order.index("plugin1") < order.index("plugin2")
        assert order.index("plugin2") < order.index("plugin3")

    def test_resolve_complex_dependencies(self):
        """Test resolving plugins with complex dependency tree."""
        resolver = PluginDependencyResolver()

        plugins = {
            "base": MockPlugin("base"),
            "auth": MockPlugin("auth", ["base"]),
            "storage": MockPlugin("storage", ["base"]),
            "api": MockPlugin("api", ["auth", "storage"]),
        }

        order = resolver.resolve_dependencies(plugins)

        # base should be first
        assert order[0] == "base"
        # api should be last
        assert order[-1] == "api"
        # auth and storage should come before api
        assert order.index("auth") < order.index("api")
        assert order.index("storage") < order.index("api")

    def test_circular_dependency_detection(self):
        """Test detection of circular dependencies."""
        resolver = PluginDependencyResolver()

        plugins = {
            "plugin1": MockPlugin("plugin1", ["plugin2"]),
            "plugin2": MockPlugin("plugin2", ["plugin1"]),
        }

        with pytest.raises(ValueError, match="Circular dependency"):
            resolver.resolve_dependencies(plugins)

    def test_validate_dependencies(self):
        """Test validation of plugin dependencies."""
        resolver = PluginDependencyResolver()

        plugins = {
            "plugin1": MockPlugin("plugin1"),
            "plugin2": MockPlugin("plugin2", ["plugin1", "missing_plugin"]),
        }

        missing = resolver.validate_dependencies(plugins)

        assert "plugin2" in missing
        assert "missing_plugin" in missing["plugin2"]

    def test_get_dependency_tree(self):
        """Test getting full dependency tree."""
        resolver = PluginDependencyResolver()

        plugins = {
            "base": MockPlugin("base"),
            "mid": MockPlugin("mid", ["base"]),
            "top": MockPlugin("top", ["mid"]),
        }

        tree = resolver.get_dependency_tree(plugins)

        assert tree["base"] == []
        assert tree["mid"] == ["base"]
        assert set(tree["top"]) == {"mid", "base"}

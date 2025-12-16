"""Plugin dependency resolution using topological sort."""

from typing import Dict, List, Set
import structlog

from .base import BasePlugin, PluginMetadata

logger = structlog.get_logger(__name__)


class PluginDependencyResolver:
    """Resolves plugin dependencies and determines load order."""
    
    def __init__(self):
        self.logger = structlog.get_logger(self.__class__.__name__)
    
    def resolve_dependencies(
        self, 
        plugins: Dict[str, BasePlugin]
    ) -> List[str]:
        """
        Resolve plugin dependencies and return load order.
        
        Args:
            plugins: Dictionary of plugin name to plugin instance
            
        Returns:
            List of plugin names in load order
            
        Raises:
            ValueError: If circular dependencies detected
        """
        # Build dependency graph
        graph: Dict[str, Set[str]] = {}
        in_degree: Dict[str, int] = {}
        
        for name, plugin in plugins.items():
            metadata = plugin.metadata
            graph[name] = set(metadata.dependencies)
            in_degree[name] = 0
        
        # Calculate in-degrees
        for name, deps in graph.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[dep] += 1
        
        # Topological sort using Kahn's algorithm
        queue: List[str] = [
            name for name, degree in in_degree.items() if degree == 0
        ]
        result: List[str] = []
        
        while queue:
            # Sort queue for deterministic ordering
            queue.sort()
            current = queue.pop(0)
            result.append(current)
            
            # Reduce in-degree for dependents
            for name, deps in graph.items():
                if current in deps:
                    in_degree[name] -= 1
                    if in_degree[name] == 0:
                        queue.append(name)
        
        # Check for circular dependencies
        if len(result) != len(plugins):
            missing = set(plugins.keys()) - set(result)
            raise ValueError(
                f"Circular dependency detected in plugins: {missing}"
            )
        
        self.logger.info(
            "plugin_dependencies_resolved",
            load_order=result
        )
        
        return result
    
    def validate_dependencies(
        self,
        plugins: Dict[str, BasePlugin]
    ) -> Dict[str, List[str]]:
        """
        Validate that all plugin dependencies are available.
        
        Args:
            plugins: Dictionary of plugin name to plugin instance
            
        Returns:
            Dictionary of plugin name to list of missing dependencies
        """
        missing_deps: Dict[str, List[str]] = {}
        
        for name, plugin in plugins.items():
            metadata = plugin.metadata
            missing = [
                dep for dep in metadata.dependencies
                if dep not in plugins
            ]
            if missing:
                missing_deps[name] = missing
                self.logger.warning(
                    "plugin_missing_dependencies",
                    plugin=name,
                    missing=missing
                )
        
        return missing_deps
    
    def get_dependency_tree(
        self,
        plugins: Dict[str, BasePlugin]
    ) -> Dict[str, List[str]]:
        """
        Get the full dependency tree for each plugin.
        
        Args:
            plugins: Dictionary of plugin name to plugin instance
            
        Returns:
            Dictionary of plugin name to list of all dependencies (recursive)
        """
        tree: Dict[str, List[str]] = {}
        
        def get_deps(plugin_name: str, visited: Set[str]) -> Set[str]:
            if plugin_name in visited:
                return set()
            
            visited.add(plugin_name)
            deps = set()
            
            if plugin_name in plugins:
                metadata = plugins[plugin_name].metadata
                for dep in metadata.dependencies:
                    deps.add(dep)
                    deps.update(get_deps(dep, visited.copy()))
            
            return deps
        
        for name in plugins:
            tree[name] = list(get_deps(name, set()))
        
        return tree

"""
Heatmap Plugin Package.

This package contains all components needed for the heatmap functionality:
- plugin.py: The main CommandPlugin implementation
- service.py: Business logic and caching
- repository.py: Database queries

The plugin can be disabled by renaming this folder with an underscore prefix
(e.g., _heatmap) which will not affect any other bot functionality.
"""

from .plugin import HeatmapCommandPlugin

__all__ = ['HeatmapCommandPlugin']

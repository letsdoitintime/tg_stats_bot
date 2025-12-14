"""Configuration settings - redirects to core.config for backwards compatibility."""

from .core.config import Settings, settings

__all__ = ['Settings', 'settings']

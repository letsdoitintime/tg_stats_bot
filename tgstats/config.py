"""Configuration settings - DEPRECATED: Use core.config directly.

This module is deprecated and will be removed in a future version.
Please update imports to use:
    from tgstats.core.config import Settings, settings

Instead of:
    from tgstats.config import Settings, settings
"""

import warnings

warnings.warn(
    "Importing from tgstats.config is deprecated. "
    "Use 'from tgstats.core.config import settings' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from .core.config import Settings, settings

__all__ = ["Settings", "settings"]

"""Configuration settings - DEPRECATED: Use core.config directly.

This module is deprecated and will be removed in version 0.3.0 (estimated Q2 2026).
Please update imports to use:
    from tgstats.core.config import Settings, settings

Instead of:
    from tgstats.config import Settings, settings

Migration guide:
    1. Search your codebase for: from tgstats.config import
    2. Replace with: from tgstats.core.config import
    3. Test your code to ensure no breakage
"""

import warnings

# Import before warning to avoid E402 linting error
from .core.config import Settings, settings  # noqa: E402

warnings.warn(
    "Importing from tgstats.config is deprecated and will be removed in v0.3.0. "
    "Use 'from tgstats.core.config import settings' instead. "
    "See module docstring for migration guide.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["Settings", "settings"]

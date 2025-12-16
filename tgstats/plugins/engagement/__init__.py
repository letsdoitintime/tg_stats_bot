"""Package entry for the engagement plugin.

This module re-exports the implementation from `engagements.py` so that the
package can be imported as `tgstats.plugins.engagement` and the
`EngagementPlugin` class remains discoverable by the PluginManager.
"""

from .engagements import EngagementPlugin

__all__ = ["EngagementPlugin"]

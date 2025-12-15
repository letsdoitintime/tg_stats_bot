"""API v1 router."""

from fastapi import APIRouter

from . import analytics, chats, stats

# Create v1 API router
router = APIRouter(prefix="/api/v1", tags=["v1"])

# Include sub-routers (to be implemented)
# router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
# router.include_router(chats.router, prefix="/chats", tags=["chats"])
# router.include_router(stats.router, prefix="/stats", tags=["stats"])

__all__ = ["router"]

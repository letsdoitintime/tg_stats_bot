"""Web application for webhook support."""

from .app import app
from .auth import verify_api_token
from .health import router as health_router
from .routers.webhook import get_bot_application, set_bot_application

__all__ = [
    "app",
    "set_bot_application",
    "get_bot_application",
    "verify_api_token",
    "health_router",
]

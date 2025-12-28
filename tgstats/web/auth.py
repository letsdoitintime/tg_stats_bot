"""Authentication and authorization middleware."""

from typing import Optional
from fastapi import Header, HTTPException, status
import structlog

from ..core.config import settings

logger = structlog.get_logger(__name__)


async def verify_api_token(x_api_token: Optional[str] = Header(None, alias="X-API-Token")) -> str:
    """
    Verify API token from header.

    Args:
        x_api_token: API token from X-API-Token header

    Returns:
        Validated token

    Raises:
        HTTPException: If token is missing or invalid
    """
    if not settings.admin_api_token:
        # If no token configured, allow access (backward compatibility)
        logger.warning("no_api_token_configured")
        return ""

    if not x_api_token:
        logger.warning("api_token_missing")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if x_api_token != settings.admin_api_token:
        logger.warning("api_token_invalid", token_prefix=x_api_token[:8] if x_api_token else "")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API token")

    return x_api_token


async def verify_admin_token(
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")
) -> None:
    """
    Verify admin API token if configured.

    Args:
        x_admin_token: Admin token from X-Admin-Token header

    Raises:
        HTTPException: If token is invalid or missing when required
    """
    if settings.admin_api_token:
        if not x_admin_token or x_admin_token != settings.admin_api_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing admin token"
            )


async def optional_api_token(
    x_api_token: Optional[str] = Header(None, alias="X-API-Token")
) -> Optional[str]:
    """
    Optional API token verification.

    Returns token if valid, None if not provided.
    Used for endpoints that have different behavior for authenticated requests.
    """
    if not x_api_token or not settings.admin_api_token:
        return None

    if x_api_token == settings.admin_api_token:
        return x_api_token

    return None

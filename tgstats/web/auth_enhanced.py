"""Enhanced admin authentication with token rotation and rate limiting."""

import secrets
import hashlib
import time
from typing import Optional, Dict
from datetime import datetime, timedelta

import structlog
from fastapi import Header, HTTPException, status

from ..core.config import settings

logger = structlog.get_logger(__name__)

# Token storage (in production, use Redis or database)
_active_tokens: Dict[str, dict] = {}
_token_attempts: Dict[str, list] = {}

# Rate limiting configuration
MAX_AUTH_ATTEMPTS_PER_HOUR = 10
TOKEN_ROTATION_DAYS = 30


class AdminTokenManager:
    """Manages admin authentication tokens with rotation and rate limiting."""

    def __init__(self):
        self.master_token = settings.admin_api_token
        self._init_master_token()

    def _init_master_token(self):
        """Initialize the master token in active tokens."""
        if self.master_token:
            token_hash = self._hash_token(self.master_token)
            _active_tokens[token_hash] = {
                "created_at": datetime.utcnow(),
                "last_used": datetime.utcnow(),
                "is_master": True,
                "usage_count": 0,
            }

    @staticmethod
    def _hash_token(token: str) -> str:
        """Hash token for secure storage."""
        return hashlib.sha256(token.encode()).hexdigest()

    def generate_token(self, prefix: str = "tgs") -> str:
        """Generate a new admin token."""
        token = f"{prefix}_{secrets.token_urlsafe(32)}"
        token_hash = self._hash_token(token)

        _active_tokens[token_hash] = {
            "created_at": datetime.utcnow(),
            "last_used": datetime.utcnow(),
            "is_master": False,
            "usage_count": 0,
        }

        logger.info("admin_token_generated", token_hash=token_hash[:8])
        return token

    def verify_token(self, token: str, client_ip: Optional[str] = None) -> bool:
        """
        Verify admin token with rate limiting.

        Args:
            token: The admin token to verify
            client_ip: Client IP address for rate limiting

        Returns:
            True if token is valid, False otherwise
        """
        # Rate limiting by IP
        if client_ip:
            if not self._check_rate_limit(client_ip):
                logger.warning("admin_auth_rate_limited", client_ip=client_ip)
                return False

        token_hash = self._hash_token(token)

        if token_hash in _active_tokens:
            token_info = _active_tokens[token_hash]

            # Check token expiration (except master token)
            if not token_info.get("is_master"):
                created_at = token_info["created_at"]
                if datetime.utcnow() - created_at > timedelta(days=TOKEN_ROTATION_DAYS):
                    logger.warning("admin_token_expired", token_hash=token_hash[:8])
                    del _active_tokens[token_hash]
                    return False

            # Update token usage
            token_info["last_used"] = datetime.utcnow()
            token_info["usage_count"] += 1

            logger.info(
                "admin_auth_success",
                token_hash=token_hash[:8],
                usage_count=token_info["usage_count"],
                client_ip=client_ip,
            )
            return True

        logger.warning("admin_auth_failed", token_hash=token_hash[:8], client_ip=client_ip)
        return False

    def _check_rate_limit(self, client_ip: str) -> bool:
        """Check if client IP has exceeded rate limit."""
        now = time.time()
        hour_ago = now - 3600

        # Clean old attempts
        if client_ip in _token_attempts:
            _token_attempts[client_ip] = [t for t in _token_attempts[client_ip] if t > hour_ago]
        else:
            _token_attempts[client_ip] = []

        # Check rate limit
        if len(_token_attempts[client_ip]) >= MAX_AUTH_ATTEMPTS_PER_HOUR:
            return False

        # Record attempt
        _token_attempts[client_ip].append(now)
        return True

    def revoke_token(self, token: str) -> bool:
        """Revoke an admin token."""
        token_hash = self._hash_token(token)

        if token_hash in _active_tokens:
            token_info = _active_tokens[token_hash]
            if token_info.get("is_master"):
                logger.error("attempt_to_revoke_master_token")
                return False

            del _active_tokens[token_hash]
            logger.info("admin_token_revoked", token_hash=token_hash[:8])
            return True

        return False

    def list_tokens(self) -> list:
        """List all active tokens (for admin management)."""
        return [
            {
                "token_hash": hash[:8],
                "created_at": info["created_at"].isoformat(),
                "last_used": info["last_used"].isoformat(),
                "usage_count": info["usage_count"],
                "is_master": info.get("is_master", False),
            }
            for hash, info in _active_tokens.items()
        ]


# Global token manager instance
token_manager = AdminTokenManager()


async def verify_admin_token(
    x_admin_token: Optional[str] = Header(None), x_forwarded_for: Optional[str] = Header(None)
) -> str:
    """
    Dependency for FastAPI endpoints requiring admin authentication.

    Args:
        x_admin_token: Admin token from request header
        x_forwarded_for: Client IP from proxy header

    Returns:
        The verified token

    Raises:
        HTTPException: If authentication fails
    """
    # If no admin token configured, allow access (development mode)
    if not settings.admin_api_token:
        logger.warning("admin_api_running_without_authentication")
        return "dev_mode"

    if not x_admin_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract client IP (handle proxy headers)
    client_ip = x_forwarded_for.split(",")[0].strip() if x_forwarded_for else None

    if not token_manager.verify_token(x_admin_token, client_ip):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired admin token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return x_admin_token

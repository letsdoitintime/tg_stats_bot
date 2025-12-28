"""Configuration validation utilities."""

from typing import List, Tuple

import structlog

from .config import Settings

logger = structlog.get_logger(__name__)


class ConfigValidator:
    """Validates configuration settings at startup."""

    def __init__(self, settings: Settings):
        """Initialize validator with settings."""
        self.settings = settings
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate_all(self) -> Tuple[bool, List[str], List[str]]:
        """
        Validate all configuration settings.

        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        self._validate_database()
        self._validate_bot()
        self._validate_redis()
        self._validate_security()
        self._validate_performance()

        is_valid = len(self.errors) == 0

        if is_valid:
            logger.info("Configuration validation passed", warnings=len(self.warnings))
        else:
            logger.error("Configuration validation failed", errors=len(self.errors))

        return is_valid, self.errors, self.warnings

    def _validate_database(self) -> None:
        """Validate database configuration."""
        if not self.settings.database_url:
            self.errors.append("DATABASE_URL is required")

        if self.settings.db_pool_size < 1:
            self.errors.append("DB_POOL_SIZE must be at least 1")

        if self.settings.db_max_overflow < 0:
            self.errors.append("DB_MAX_OVERFLOW must be non-negative")

        # Warnings for suboptimal settings
        if self.settings.db_pool_size > 50:
            self.warnings.append("DB_POOL_SIZE > 50 may be excessive for most use cases")

        if self.settings.db_pool_size < 5:
            self.warnings.append("DB_POOL_SIZE < 5 may cause connection bottlenecks")

    def _validate_bot(self) -> None:
        """Validate bot configuration."""
        if not self.settings.bot_token:
            self.errors.append("BOT_TOKEN is required")

        if self.settings.mode == "webhook" and not self.settings.webhook_url:
            self.errors.append("WEBHOOK_URL is required when MODE=webhook")

        if self.settings.bot_connection_pool_size < 1:
            self.errors.append("BOT_CONNECTION_POOL_SIZE must be at least 1")

        # Validate timeouts
        if self.settings.bot_read_timeout < 1:
            self.warnings.append("BOT_READ_TIMEOUT < 1s may cause timeout issues")

        if self.settings.bot_read_timeout > 60:
            self.warnings.append("BOT_READ_TIMEOUT > 60s is unusually long")

    def _validate_redis(self) -> None:
        """Validate Redis configuration."""
        if not self.settings.redis_url:
            self.warnings.append("REDIS_URL not set - Celery tasks may not work")

        if not self.settings.redis_url.startswith("redis://"):
            self.errors.append("REDIS_URL must start with redis://")

    def _validate_security(self) -> None:
        """Validate security configuration."""
        if not self.settings.admin_api_token and self.settings.environment == "production":
            self.errors.append(
                "ADMIN_API_TOKEN is required in production - API will be unprotected without it"
            )

        if self.settings.admin_api_token:
            token = self.settings.admin_api_token

            # Length check
            if len(token) < 32:
                self.errors.append(
                    f"ADMIN_API_TOKEN must be at least 32 characters (current: {len(token)})"
                )
            elif len(token) < 16:
                self.warnings.append("ADMIN_API_TOKEN should be at least 16 characters")

            # Entropy check - ensure it's not too simple
            if token.lower() in ["admin", "password", "secret", "token", "test"]:
                self.errors.append("ADMIN_API_TOKEN is too simple - use a strong random token")

            # Check for common weak patterns
            if token == token.lower() or token == token.upper():
                self.warnings.append(
                    "ADMIN_API_TOKEN should contain mixed case characters for better security"
                )

            # Check if it's a demo/test token
            if "test" in token.lower() or "demo" in token.lower():
                if self.settings.environment == "production":
                    self.errors.append(
                        "ADMIN_API_TOKEN appears to be a test token - not suitable for production"
                    )

        if self.settings.rate_limit_per_minute < 1:
            self.warnings.append("RATE_LIMIT_PER_MINUTE < 1 may be too restrictive")

        if self.settings.rate_limit_per_minute > 1000:
            self.warnings.append(
                "RATE_LIMIT_PER_MINUTE > 1000 may not provide effective protection"
            )

        # CORS validation
        if self.settings.cors_origins == "*":
            self.warnings.append(
                "CORS_ORIGINS=* allows all origins - restrict to specific domains in production"
            )

    def _validate_performance(self) -> None:
        """Validate performance configuration."""
        if self.settings.cache_ttl < 0:
            self.errors.append("CACHE_TTL must be non-negative")

        if self.settings.cache_ttl > 3600:
            self.warnings.append("CACHE_TTL > 1 hour may serve stale data")

        if self.settings.max_request_size < 1024:
            self.warnings.append("MAX_REQUEST_SIZE < 1KB may be too restrictive")

        if self.settings.max_request_size > 10485760:  # 10MB
            self.warnings.append("MAX_REQUEST_SIZE > 10MB may allow DoS attacks")


def validate_config(settings: Settings) -> None:
    """
    Validate configuration and raise exception if invalid.

    Args:
        settings: Settings instance to validate

    Raises:
        ValueError: If configuration is invalid
    """
    validator = ConfigValidator(settings)
    is_valid, errors, warnings = validator.validate_all()

    # Log warnings
    for warning in warnings:
        logger.warning("Configuration warning", message=warning)

    # Raise exception if errors found
    if not is_valid:
        error_msg = "\n".join(f"  - {error}" for error in errors)
        raise ValueError(f"Configuration validation failed:\n{error_msg}")

"""Configuration settings using pydantic-settings.

This module defines all application settings with validation and documentation.
Settings are loaded from environment variables with sensible defaults.
"""

from typing import Literal
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings

from .exceptions import ConfigurationError


class Settings(BaseSettings):
    """Application settings loaded from environment variables.
    
    All settings can be configured via environment variables or .env file.
    Required settings must be provided, optional settings have sensible defaults.
    """
    
    # Core Bot Settings
    bot_token: str = Field(
        ..., 
        env="BOT_TOKEN",
        description="Telegram bot token from @BotFather"
    )
    database_url: str = Field(
        ..., 
        env="DATABASE_URL",
        description="PostgreSQL connection string (postgresql+psycopg://...)"
    )
    mode: Literal["polling", "webhook"] = Field(
        default="polling", 
        env="MODE",
        description="Bot operation mode: 'polling' for pull-based updates, 'webhook' for push-based"
    )
    webhook_url: str = Field(
        default="", 
        env="WEBHOOK_URL",
        description="Public HTTPS URL for webhook mode (required if mode=webhook)"
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", 
        env="LOG_LEVEL",
        description="Logging level for application logs"
    )
    
    # Logging Configuration
    telegram_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="WARNING", 
        env="TELEGRAM_LOG_LEVEL",
        description="Log level for python-telegram-bot library"
    )
    httpx_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="WARNING", 
        env="HTTPX_LOG_LEVEL",
        description="Log level for HTTPX library"
    )
    uvicorn_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", 
        env="UVICORN_LOG_LEVEL",
        description="Log level for Uvicorn web server"
    )
    log_to_file: bool = Field(
        default=True, 
        env="LOG_TO_FILE",
        description="Enable logging to file (in addition to console)"
    )
    log_file_path: str = Field(
        default="logs/tgstats.log", 
        env="LOG_FILE_PATH",
        description="Path to log file"
    )
    log_file_max_bytes: int = Field(
        default=10485760, 
        env="LOG_FILE_MAX_BYTES",
        ge=1024,
        le=104857600,
        description="Maximum size of log file before rotation (bytes, 1KB-100MB)"
    )
    log_file_backup_count: int = Field(
        default=5, 
        env="LOG_FILE_BACKUP_COUNT",
        ge=1,
        le=100,
        description="Number of rotated log files to keep"
    )
    log_format: Literal["json", "text"] = Field(
        default="json", 
        env="LOG_FORMAT",
        description="Log output format: 'json' for structured logs, 'text' for human-readable"
    )
    
    # External Services
    redis_url: str = Field(
        default="redis://localhost:6379/0", 
        env="REDIS_URL",
        description="Redis connection URL for Celery task queue"
    )
    admin_api_token: str = Field(
        default="", 
        env="ADMIN_API_TOKEN",
        description="Secret token for API authentication (leave empty for dev/testing)"
    )
    
    # Performance Settings
    enable_cache: bool = Field(
        default=True, 
        env="ENABLE_CACHE",
        description="Enable in-memory caching for frequently accessed data"
    )
    cache_ttl: int = Field(
        default=300, 
        env="CACHE_TTL",
        ge=10,
        le=3600,
        description="Cache time-to-live in seconds (10s-1h)"
    )
    
    # Security Settings
    rate_limit_per_minute: int = Field(
        default=10, 
        env="RATE_LIMIT_PER_MINUTE",
        ge=1,
        le=1000,
        description="Maximum API requests per minute per user"
    )
    rate_limit_per_hour: int = Field(
        default=100, 
        env="RATE_LIMIT_PER_HOUR",
        ge=10,
        le=10000,
        description="Maximum API requests per hour per user"
    )
    max_request_size: int = Field(
        default=1048576, 
        env="MAX_REQUEST_SIZE",
        ge=1024,
        le=10485760,
        description="Maximum HTTP request size in bytes (1KB-10MB)"
    )
    
    # Monitoring
    enable_metrics: bool = Field(
        default=True, 
        env="ENABLE_METRICS",
        description="Enable metrics collection and reporting"
    )
    sentry_dsn: str = Field(
        default="", 
        env="SENTRY_DSN",
        description="Sentry DSN for error tracking (optional)"
    )
    environment: Literal["development", "staging", "production"] = Field(
        default="production", 
        env="ENVIRONMENT",
        description="Deployment environment"
    )
    
    # CORS Settings
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:8000", 
        env="CORS_ORIGINS",
        description="Comma-separated list of allowed CORS origins"
    )
    
    # Database Configuration
    db_pool_size: int = Field(
        default=10, 
        env="DB_POOL_SIZE",
        ge=1,
        le=50,
        description="Database connection pool size"
    )
    db_max_overflow: int = Field(
        default=20, 
        env="DB_MAX_OVERFLOW",
        ge=0,
        le=100,
        description="Maximum overflow connections beyond pool_size"
    )
    db_pool_timeout: int = Field(
        default=30, 
        env="DB_POOL_TIMEOUT",
        ge=1,
        le=120,
        description="Timeout for getting connection from pool (seconds)"
    )
    db_retry_attempts: int = Field(
        default=3, 
        env="DB_RETRY_ATTEMPTS",
        ge=1,
        le=10,
        description="Number of retry attempts for database operations"
    )
    db_retry_delay: float = Field(
        default=1.0, 
        env="DB_RETRY_DELAY",
        ge=0.1,
        le=10.0,
        description="Delay between retry attempts (seconds)"
    )
    
    # Bot Connection Configuration
    bot_connection_pool_size: int = Field(
        default=8, 
        env="BOT_CONNECTION_POOL_SIZE",
        ge=1,
        le=32,
        description="HTTP connection pool size for Telegram API"
    )
    bot_read_timeout: float = Field(
        default=10.0, 
        env="BOT_READ_TIMEOUT",
        ge=1.0,
        le=60.0,
        description="Read timeout for Telegram API requests (seconds)"
    )
    bot_write_timeout: float = Field(
        default=10.0, 
        env="BOT_WRITE_TIMEOUT",
        ge=1.0,
        le=60.0,
        description="Write timeout for Telegram API requests (seconds)"
    )
    bot_connect_timeout: float = Field(
        default=10.0, 
        env="BOT_CONNECT_TIMEOUT",
        ge=1.0,
        le=30.0,
        description="Connection timeout for Telegram API (seconds)"
    )
    bot_pool_timeout: float = Field(
        default=5.0, 
        env="BOT_POOL_TIMEOUT",
        ge=1.0,
        le=30.0,
        description="Timeout for getting connection from pool (seconds)"
    )
    
    # Celery Configuration
    celery_task_max_retries: int = Field(
        default=3, 
        env="CELERY_TASK_MAX_RETRIES",
        ge=0,
        le=10,
        description="Maximum retry attempts for failed Celery tasks"
    )
    celery_task_retry_delay: int = Field(
        default=60, 
        env="CELERY_TASK_RETRY_DELAY",
        ge=1,
        le=3600,
        description="Delay between Celery task retries (seconds)"
    )
    
    @model_validator(mode='after')
    def validate_webhook_mode(self) -> Settings:
        """Validate that webhook_url is provided when mode is webhook."""
        if self.mode == "webhook" and not self.webhook_url:
            raise ConfigurationError(
                "WEBHOOK_URL must be provided when MODE is set to 'webhook'"
            )
        return self
    
    @field_validator('database_url')
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL format."""
        if not v.startswith(('postgresql://', 'postgresql+psycopg://', 'postgresql+asyncpg://')):
            raise ConfigurationError(
                f"Invalid DATABASE_URL format. Must start with 'postgresql://' or "
                f"'postgresql+psycopg://'. Got: {v[:30]}..."
            )
        return v
    
    @field_validator('redis_url')
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        """Validate Redis URL format."""
        if not v.startswith(('redis://', 'rediss://')):
            raise ConfigurationError(
                f"Invalid REDIS_URL format. Must start with 'redis://' or 'rediss://'. "
                f"Got: {v[:30]}..."
            )
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()

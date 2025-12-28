"""Configuration settings using pydantic-settings."""

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    bot_token: str = Field(..., env="BOT_TOKEN")
    database_url: str = Field(..., env="DATABASE_URL")
    mode: str = Field(default="polling", env="MODE")  # polling or webhook
    webhook_url: str = Field(default="", env="WEBHOOK_URL")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    # Logging configuration
    telegram_log_level: str = Field(default="WARNING", env="TELEGRAM_LOG_LEVEL")
    httpx_log_level: str = Field(default="WARNING", env="HTTPX_LOG_LEVEL")
    uvicorn_log_level: str = Field(default="INFO", env="UVICORN_LOG_LEVEL")

    # Log file settings
    log_to_file: bool = Field(default=True, env="LOG_TO_FILE")
    log_file_path: str = Field(default="logs/tgstats.log", env="LOG_FILE_PATH")
    log_file_max_bytes: int = Field(default=10485760, env="LOG_FILE_MAX_BYTES")  # 10MB
    log_file_backup_count: int = Field(default=5, env="LOG_FILE_BACKUP_COUNT")
    log_format: str = Field(default="json", env="LOG_FORMAT")  # json or text

    # Step 2 additions
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    admin_api_token: str = Field(default="", env="ADMIN_API_TOKEN")

    # Performance settings
    enable_cache: bool = Field(default=True, env="ENABLE_CACHE")
    cache_ttl: int = Field(default=300, env="CACHE_TTL")

    # Security settings
    rate_limit_per_minute: int = Field(default=10, env="RATE_LIMIT_PER_MINUTE")
    rate_limit_per_hour: int = Field(default=100, env="RATE_LIMIT_PER_HOUR")

    # Monitoring
    enable_metrics: bool = Field(default=True, env="ENABLE_METRICS")
    sentry_dsn: str = Field(default="", env="SENTRY_DSN")
    environment: str = Field(default="production", env="ENVIRONMENT")

    # CORS settings
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:8000", env="CORS_ORIGINS"
    )

    # Request limits
    max_request_size: int = Field(default=1048576, env="MAX_REQUEST_SIZE")  # 1MB default

    # Database settings
    db_pool_size: int = Field(default=10, env="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=20, env="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(default=30, env="DB_POOL_TIMEOUT")
    db_retry_attempts: int = Field(default=3, env="DB_RETRY_ATTEMPTS")
    db_retry_delay: float = Field(default=1.0, env="DB_RETRY_DELAY")

    # Bot connection settings
    # Note: bot_read_timeout should be > 30s for Telegram's long-polling to work properly
    bot_connection_pool_size: int = Field(default=8, env="BOT_CONNECTION_POOL_SIZE")
    bot_read_timeout: float = Field(default=40.0, env="BOT_READ_TIMEOUT")
    bot_write_timeout: float = Field(default=15.0, env="BOT_WRITE_TIMEOUT")
    bot_connect_timeout: float = Field(default=15.0, env="BOT_CONNECT_TIMEOUT")
    bot_pool_timeout: float = Field(default=15.0, env="BOT_POOL_TIMEOUT")

    # Network retry settings for bot updates
    bot_get_updates_timeout: int = Field(
        default=30, env="BOT_GET_UPDATES_TIMEOUT"
    )  # Long-polling timeout

    # Network loop retry configuration
    bot_network_retry_attempts: int = Field(default=5, env="BOT_NETWORK_RETRY_ATTEMPTS")
    bot_network_retry_delay: float = Field(default=1.0, env="BOT_NETWORK_RETRY_DELAY")

    # Celery settings
    celery_task_max_retries: int = Field(default=3, env="CELERY_TASK_MAX_RETRIES")
    celery_task_retry_delay: int = Field(default=60, env="CELERY_TASK_RETRY_DELAY")

    # Plugin settings
    enable_plugins: bool = Field(default=True, env="ENABLE_PLUGINS")
    plugin_directories: str = Field(default="", env="PLUGIN_DIRECTORIES")  # Comma-separated paths

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        """Validate mode is either polling or webhook."""
        if v not in ["polling", "webhook"]:
            raise ValueError('mode must be either "polling" or "webhook"')
        return v

    @field_validator("log_level", "telegram_log_level", "httpx_log_level", "uvicorn_log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v_upper

    @field_validator("log_format")
    @classmethod
    def validate_log_format(cls, v: str) -> str:
        """Validate log format."""
        if v not in ["json", "text"]:
            raise ValueError('log_format must be either "json" or "text"')
        return v

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment."""
        valid_envs = ["development", "staging", "production", "test"]
        if v not in valid_envs:
            raise ValueError(f"environment must be one of {valid_envs}")
        return v

    @field_validator("db_pool_size", "db_max_overflow", "bot_connection_pool_size")
    @classmethod
    def validate_positive_int(cls, v: int) -> int:
        """Validate positive integers."""
        if v <= 0:
            raise ValueError("Value must be positive")
        return v

    @model_validator(mode="after")
    def validate_webhook_config(self) -> "Settings":
        """Validate webhook configuration."""
        if self.mode == "webhook" and not self.webhook_url:
            raise ValueError('webhook_url is required when mode is "webhook"')
        return self

    @model_validator(mode="after")
    def validate_pool_sizes(self) -> "Settings":
        """Validate database pool configuration."""
        if self.db_pool_size > 50:
            raise ValueError("db_pool_size should not exceed 50")
        if self.db_max_overflow > 100:
            raise ValueError("db_max_overflow should not exceed 100")
        return self

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()

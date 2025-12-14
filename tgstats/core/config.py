"""Configuration settings using pydantic-settings."""

from pydantic import Field
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
    cors_origins: str = Field(default="http://localhost:3000,http://localhost:8000", env="CORS_ORIGINS")
    
    # Request limits
    max_request_size: int = Field(default=1048576, env="MAX_REQUEST_SIZE")  # 1MB default
    
    # Database settings
    db_pool_size: int = Field(default=10, env="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=20, env="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(default=30, env="DB_POOL_TIMEOUT")
    db_retry_attempts: int = Field(default=3, env="DB_RETRY_ATTEMPTS")
    db_retry_delay: float = Field(default=1.0, env="DB_RETRY_DELAY")
    
    # Bot connection settings
    bot_connection_pool_size: int = Field(default=8, env="BOT_CONNECTION_POOL_SIZE")
    bot_read_timeout: float = Field(default=10.0, env="BOT_READ_TIMEOUT")
    bot_write_timeout: float = Field(default=10.0, env="BOT_WRITE_TIMEOUT")
    bot_connect_timeout: float = Field(default=10.0, env="BOT_CONNECT_TIMEOUT")
    bot_pool_timeout: float = Field(default=5.0, env="BOT_POOL_TIMEOUT")
    
    # Celery settings
    celery_task_max_retries: int = Field(default=3, env="CELERY_TASK_MAX_RETRIES")
    celery_task_retry_delay: int = Field(default=60, env="CELERY_TASK_RETRY_DELAY")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()

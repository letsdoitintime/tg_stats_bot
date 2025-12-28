"""Logging configuration utilities with file rotation and structured output."""

import logging
import sys
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler
import structlog
from structlog.types import EventDict


class ColoredConsoleRenderer:
    """Custom renderer for colored console output."""

    COLORS = {
        "debug": "\033[36m",  # Cyan
        "info": "\033[32m",  # Green
        "warning": "\033[33m",  # Yellow
        "error": "\033[31m",  # Red
        "critical": "\033[35m",  # Magenta
        "reset": "\033[0m",  # Reset
    }

    def __call__(self, logger: logging.Logger, name: str, event_dict: EventDict) -> str:
        """Render colored console output."""
        level = event_dict.get("level", "info")
        timestamp = event_dict.get("timestamp", "")
        logger_name = event_dict.get("logger", "")
        event = event_dict.get("event", "")

        # Color for level
        color = self.COLORS.get(level.lower(), "")
        reset = self.COLORS["reset"]

        # Build the log line
        parts = []

        # Timestamp
        if timestamp:
            parts.append(f"\033[90m{timestamp}\033[0m")  # Gray

        # Level
        parts.append(f"{color}[{level.upper():8}]{reset}")

        # Logger name
        if logger_name and logger_name != "__main__":
            parts.append(f"\033[94m{logger_name}\033[0m")  # Blue

        # Event message
        parts.append(f"{color}{event}{reset}")

        # Additional context
        skip_keys = {"timestamp", "level", "logger", "event", "log_level"}
        extras = {k: v for k, v in event_dict.items() if k not in skip_keys}
        if extras:
            extra_str = " ".join(f"{k}={v}" for k, v in extras.items())
            parts.append(f"\033[90m{extra_str}\033[0m")  # Gray

        return " ".join(parts)


def add_app_context(logger: logging.Logger, name: str, event_dict: EventDict) -> EventDict:
    """Add application context to log events."""
    event_dict["app"] = "tgstats"
    event_dict["pid"] = os.getpid()
    return event_dict


def setup_logging(
    log_level: str = "INFO",
    log_to_file: bool = True,
    log_file_path: str = "logs/tgstats.log",
    log_file_max_bytes: int = 10485760,  # 10MB
    log_file_backup_count: int = 5,
    log_format: str = "json",
) -> None:
    """
    Configure structured logging for the application with file rotation.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_to_file: Whether to log to file
        log_file_path: Path to log file
        log_file_max_bytes: Maximum size of each log file (default 10MB)
        log_file_backup_count: Number of backup files to keep (default 5)
        log_format: Format for logs - 'json' or 'text'
    """
    # Create logs directory if it doesn't exist
    if log_to_file:
        log_dir = Path(log_file_path).parent
        log_dir.mkdir(parents=True, exist_ok=True)

    # Configure processors based on format
    if log_format.lower() == "text":
        console_processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            add_app_context,
            ColoredConsoleRenderer(),
        ]
    else:
        # JSON format for both console and file
        common_processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            add_app_context,
        ]

        console_processors = common_processors + [structlog.processors.JSONRenderer()]

    # Configure structlog
    structlog.configure(
        processors=console_processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    console_formatter = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler with rotation
    if log_to_file:
        try:
            file_handler = RotatingFileHandler(
                log_file_path,
                maxBytes=log_file_max_bytes,
                backupCount=log_file_backup_count,
                encoding="utf-8",
            )
            file_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))

            # Use structured format for file logs
            if log_format.lower() == "json":
                file_formatter = logging.Formatter("%(message)s")
            else:
                file_formatter = logging.Formatter(
                    "%(asctime)s [%(levelname)-8s] %(name)s - %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )

            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)

            # Log startup message
            logger = structlog.get_logger(__name__)
            logger.info(
                "Logging configured",
                log_level=log_level,
                log_file=log_file_path,
                max_size_mb=log_file_max_bytes / 1024 / 1024,
                backup_count=log_file_backup_count,
                format=log_format,
            )
        except Exception as e:
            print(f"Warning: Failed to setup file logging: {e}", file=sys.stderr)


def configure_third_party_logging(
    telegram_level: str = "WARNING", httpx_level: str = "WARNING", uvicorn_level: str = "INFO"
) -> None:
    """
    Configure logging levels for third-party libraries.

    Args:
        telegram_level: Logging level for telegram library
        httpx_level: Logging level for httpx library
        uvicorn_level: Logging level for uvicorn library
    """
    # Telegram libraries
    logging.getLogger("httpx").setLevel(getattr(logging, httpx_level.upper(), logging.WARNING))
    logging.getLogger("telegram").setLevel(
        getattr(logging, telegram_level.upper(), logging.WARNING)
    )
    logging.getLogger("telegram.ext").setLevel(
        getattr(logging, telegram_level.upper(), logging.WARNING)
    )

    # HTTP/Web libraries
    logging.getLogger("uvicorn").setLevel(getattr(logging, uvicorn_level.upper(), logging.INFO))
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)

    # Database libraries
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    # Async libraries
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    # Celery
    logging.getLogger("celery").setLevel(logging.INFO)
    logging.getLogger("celery.worker").setLevel(logging.INFO)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)

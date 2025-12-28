"""Standardized error handlers for FastAPI."""

import traceback
from typing import Any, Dict, Optional

import structlog
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from ..core.exceptions import (
    AuthorizationError,
    ChatNotSetupError,
    ConfigurationError,
    DatabaseError,
    InsufficientPermissionsError,
    NotFoundError,
    TgStatsError,
)
from ..core.exceptions import ValidationError as AppValidationError

logger = structlog.get_logger(__name__)


class ErrorResponse:
    """Standardized error response format."""

    def __init__(
        self,
        error_code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ):
        """
        Initialize error response.

        Args:
            error_code: Machine-readable error code
            message: Human-readable error message
            details: Optional additional error details
            request_id: Request ID for tracing
        """
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        self.request_id = request_id

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response."""
        result = {
            "error": {
                "code": self.error_code,
                "message": self.message,
            }
        }

        if self.details:
            result["error"]["details"] = self.details

        if self.request_id:
            result["request_id"] = self.request_id

        return result


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic validation errors."""
    request_id = getattr(request.state, "request_id", None)

    # Extract validation error details
    errors = []
    for error in exc.errors():
        errors.append(
            {
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            }
        )

    logger.warning("Validation error", request_id=request_id, path=request.url.path, errors=errors)

    error_response = ErrorResponse(
        error_code="VALIDATION_ERROR",
        message="Request validation failed",
        details={"errors": errors},
        request_id=request_id,
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=error_response.to_dict()
    )


async def app_validation_error_handler(request: Request, exc: AppValidationError) -> JSONResponse:
    """Handle application validation errors."""
    request_id = getattr(request.state, "request_id", None)

    logger.warning(
        "Application validation error", request_id=request_id, path=request.url.path, error=str(exc)
    )

    error_response = ErrorResponse(
        error_code="VALIDATION_ERROR", message=str(exc), request_id=request_id
    )

    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=error_response.to_dict())


async def not_found_error_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    """Handle not found errors."""
    request_id = getattr(request.state, "request_id", None)

    logger.info("Resource not found", request_id=request_id, path=request.url.path, error=str(exc))

    error_response = ErrorResponse(error_code="NOT_FOUND", message=str(exc), request_id=request_id)

    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=error_response.to_dict())


async def authorization_error_handler(request: Request, exc: AuthorizationError) -> JSONResponse:
    """Handle authorization errors."""
    request_id = getattr(request.state, "request_id", None)

    logger.warning(
        "Authorization error", request_id=request_id, path=request.url.path, error=str(exc)
    )

    error_response = ErrorResponse(
        error_code="UNAUTHORIZED", message=str(exc), request_id=request_id
    )

    return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content=error_response.to_dict())


async def insufficient_permissions_error_handler(
    request: Request, exc: InsufficientPermissionsError
) -> JSONResponse:
    """Handle insufficient permissions errors."""
    request_id = getattr(request.state, "request_id", None)

    logger.warning(
        "Insufficient permissions", request_id=request_id, path=request.url.path, error=str(exc)
    )

    error_response = ErrorResponse(error_code="FORBIDDEN", message=str(exc), request_id=request_id)

    return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content=error_response.to_dict())


async def chat_not_setup_error_handler(request: Request, exc: ChatNotSetupError) -> JSONResponse:
    """Handle chat not setup errors."""
    request_id = getattr(request.state, "request_id", None)

    logger.info("Chat not setup", request_id=request_id, path=request.url.path, error=str(exc))

    error_response = ErrorResponse(
        error_code="CHAT_NOT_SETUP",
        message=str(exc),
        details={"action_required": "Run /setup command in the chat"},
        request_id=request_id,
    )

    return JSONResponse(
        status_code=status.HTTP_428_PRECONDITION_REQUIRED, content=error_response.to_dict()
    )


async def database_error_handler(request: Request, exc: DatabaseError) -> JSONResponse:
    """Handle database errors."""
    request_id = getattr(request.state, "request_id", None)

    logger.error(
        "Database error",
        request_id=request_id,
        path=request.url.path,
        error=str(exc),
        exc_info=True,
    )

    error_response = ErrorResponse(
        error_code="DATABASE_ERROR",
        message="A database error occurred",
        details={"internal_error": str(exc)} if __debug__ else {},
        request_id=request_id,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=error_response.to_dict()
    )


async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Handle SQLAlchemy errors."""
    request_id = getattr(request.state, "request_id", None)

    logger.error(
        "SQLAlchemy error",
        request_id=request_id,
        path=request.url.path,
        error=str(exc),
        exc_info=True,
    )

    error_response = ErrorResponse(
        error_code="DATABASE_ERROR", message="A database error occurred", request_id=request_id
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=error_response.to_dict()
    )


async def configuration_error_handler(request: Request, exc: ConfigurationError) -> JSONResponse:
    """Handle configuration errors."""
    request_id = getattr(request.state, "request_id", None)

    logger.error(
        "Configuration error", request_id=request_id, path=request.url.path, error=str(exc)
    )

    error_response = ErrorResponse(
        error_code="CONFIGURATION_ERROR",
        message="A configuration error occurred",
        details={"internal_error": str(exc)} if __debug__ else {},
        request_id=request_id,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=error_response.to_dict()
    )


async def generic_error_handler(request: Request, exc: TgStatsError) -> JSONResponse:
    """Handle generic application errors."""
    request_id = getattr(request.state, "request_id", None)

    logger.error(
        "Application error",
        request_id=request_id,
        path=request.url.path,
        error=str(exc),
        error_type=type(exc).__name__,
    )

    error_response = ErrorResponse(
        error_code="APPLICATION_ERROR", message=str(exc), request_id=request_id
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=error_response.to_dict()
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unhandled exceptions."""
    request_id = getattr(request.state, "request_id", None)

    # Get full traceback
    tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    logger.error(
        "Unhandled exception",
        request_id=request_id,
        path=request.url.path,
        method=request.method,
        error=str(exc),
        error_type=type(exc).__name__,
        traceback=tb_str,
    )

    error_response = ErrorResponse(
        error_code="INTERNAL_ERROR",
        message="An unexpected error occurred",
        details={"error_type": type(exc).__name__} if __debug__ else {},
        request_id=request_id,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=error_response.to_dict()
    )


def register_error_handlers(app):
    """
    Register all error handlers with FastAPI app.

    Args:
        app: FastAPI application instance
    """
    # Validation errors
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(AppValidationError, app_validation_error_handler)

    # Application errors
    app.add_exception_handler(NotFoundError, not_found_error_handler)
    app.add_exception_handler(AuthorizationError, authorization_error_handler)
    app.add_exception_handler(InsufficientPermissionsError, insufficient_permissions_error_handler)
    app.add_exception_handler(ChatNotSetupError, chat_not_setup_error_handler)
    app.add_exception_handler(DatabaseError, database_error_handler)
    app.add_exception_handler(ConfigurationError, configuration_error_handler)
    app.add_exception_handler(TgStatsError, generic_error_handler)

    # Database errors
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)

    # Catch-all for unhandled exceptions
    app.add_exception_handler(Exception, unhandled_exception_handler)

    logger.info("Error handlers registered")

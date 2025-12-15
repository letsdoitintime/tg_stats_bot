"""Custom exceptions for the application."""


class TgStatsError(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class DatabaseError(TgStatsError):
    """Database operation errors."""
    pass


class ValidationError(TgStatsError):
    """Input validation errors."""
    pass


class AuthorizationError(TgStatsError):
    """Authorization/permission errors."""
    pass


class NotFoundError(TgStatsError):
    """Resource not found errors."""
    pass


class ConfigurationError(TgStatsError):
    """Configuration errors."""
    pass


class ChatNotSetupError(TgStatsError):
    """Chat has not been set up with /setup command."""
    pass


class InsufficientPermissionsError(AuthorizationError):
    """User lacks required permissions."""
    pass


# Additional specific exceptions for better error handling
class RecordNotFoundError(DatabaseError):
    """Raised when a database record is not found."""
    pass


class DuplicateRecordError(DatabaseError):
    """Raised when attempting to create a duplicate record."""
    pass


class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails."""
    pass


class InvalidInputError(ValidationError):
    """Raised when input data is invalid."""
    pass


class InvalidConfigurationError(ValidationError):
    """Raised when configuration is invalid."""
    pass


class UnauthorizedError(AuthorizationError):
    """Raised when user is not authenticated."""
    pass


class InvalidTokenError(AuthorizationError):
    """Raised when API token is invalid."""
    pass


class MessageProcessingError(TgStatsError):
    """Raised when message processing fails."""
    pass


class PluginError(TgStatsError):
    """Base exception for plugin-related errors."""
    pass


class PluginLoadError(PluginError):
    """Raised when plugin fails to load."""
    pass


class RateLimitExceededError(TgStatsError):
    """Raised when rate limit is exceeded."""
    pass


class CacheError(TgStatsError):
    """Base exception for cache-related errors."""
    pass


class TaskError(TgStatsError):
    """Base exception for background task errors."""
    pass

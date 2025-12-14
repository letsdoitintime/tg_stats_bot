"""Custom exceptions for the application."""


class TgStatsError(Exception):
    """Base exception for all application errors."""
    pass


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

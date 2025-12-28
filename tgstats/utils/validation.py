"""Input validation utilities with detailed error messages."""

import re
from typing import Any
from datetime import datetime

from ..core.exceptions import ValidationError


def validate_chat_id(chat_id: Any) -> int:
    """
    Validate and convert chat_id to integer.

    Args:
        chat_id: Chat ID to validate

    Returns:
        Validated integer chat ID

    Raises:
        ValidationError: If chat_id is invalid
    """
    try:
        chat_id_int = int(chat_id)
        if chat_id_int == 0:
            raise ValidationError("Chat ID cannot be zero")
        return chat_id_int
    except (ValueError, TypeError):
        raise ValidationError(f"Invalid chat ID: {chat_id}. Must be a non-zero integer.")


def validate_user_id(user_id: Any) -> int:
    """
    Validate and convert user_id to integer.

    Args:
        user_id: User ID to validate

    Returns:
        Validated integer user ID

    Raises:
        ValidationError: If user_id is invalid
    """
    try:
        user_id_int = int(user_id)
        if user_id_int <= 0:
            raise ValidationError("User ID must be positive")
        return user_id_int
    except (ValueError, TypeError):
        raise ValidationError(f"Invalid user ID: {user_id}. Must be a positive integer.")


def validate_retention_days(days: Any, setting_name: str = "retention") -> int:
    """
    Validate retention days setting.

    Args:
        days: Number of days to validate
        setting_name: Name of the setting for error messages

    Returns:
        Validated integer days

    Raises:
        ValidationError: If days value is invalid
    """
    try:
        days_int = int(days)
        if days_int < 0:
            raise ValidationError(f"{setting_name} days cannot be negative")
        if days_int > 3650:  # ~10 years
            raise ValidationError(f"{setting_name} days cannot exceed 3650 (10 years)")
        return days_int
    except (ValueError, TypeError):
        raise ValidationError(
            f"Invalid {setting_name} days: {days}. Must be an integer between 0 and 3650."
        )


def validate_page_params(page: Any, page_size: Any, max_page_size: int = 100) -> tuple[int, int]:
    """
    Validate pagination parameters.

    Args:
        page: Page number (1-indexed)
        page_size: Items per page
        max_page_size: Maximum allowed page size

    Returns:
        Tuple of (validated_page, validated_page_size)

    Raises:
        ValidationError: If parameters are invalid
    """
    try:
        page_int = int(page) if page else 1
        if page_int < 1:
            raise ValidationError("Page number must be at least 1")
        if page_int > 10000:
            raise ValidationError("Page number too large (max 10,000)")
    except (ValueError, TypeError):
        raise ValidationError(f"Invalid page number: {page}")

    try:
        page_size_int = int(page_size) if page_size else 20
        if page_size_int < 1:
            raise ValidationError("Page size must be at least 1")
        if page_size_int > max_page_size:
            raise ValidationError(f"Page size cannot exceed {max_page_size}")
    except (ValueError, TypeError):
        raise ValidationError(f"Invalid page size: {page_size}")

    return page_int, page_size_int


def validate_date_string(date_str: str, param_name: str = "date") -> datetime:
    """
    Validate and parse date string in ISO format.

    Args:
        date_str: Date string to validate (YYYY-MM-DD format)
        param_name: Parameter name for error messages

    Returns:
        Parsed datetime object

    Raises:
        ValidationError: If date string is invalid
    """
    if not date_str:
        raise ValidationError(f"{param_name} cannot be empty")

    # Check format using regex
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        raise ValidationError(
            f"Invalid {param_name} format: {date_str}. Expected format: YYYY-MM-DD"
        )

    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as e:
        raise ValidationError(f"Invalid {param_name}: {date_str}. {str(e)}")


def validate_timezone(tz_str: str) -> str:
    """
    Validate timezone string.

    Args:
        tz_str: Timezone string to validate

    Returns:
        Validated timezone string

    Raises:
        ValidationError: If timezone is invalid
    """
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        ZoneInfo(tz_str)
        return tz_str
    except ZoneInfoNotFoundError:
        raise ValidationError(
            f"Invalid timezone: {tz_str}. "
            "Please use a valid IANA timezone name (e.g., 'Europe/London', 'America/New_York')"
        )


def validate_locale(locale_str: str) -> str:
    """
    Validate locale string.

    Args:
        locale_str: Locale string to validate (e.g., 'en', 'uk', 'ru')

    Returns:
        Validated lowercase locale string

    Raises:
        ValidationError: If locale is invalid
    """
    locale_clean = locale_str.strip().lower()

    if not re.match(r"^[a-z]{2,3}(_[A-Z]{2})?$", locale_clean):
        raise ValidationError(
            f"Invalid locale format: {locale_str}. "
            "Expected format: two-letter code (e.g., 'en', 'uk') or with country (e.g., 'en_US')"
        )

    return locale_clean


def sanitize_command_input(text: str, max_length: int = 1000) -> str:
    """
    Sanitize user input from commands.

    Args:
        text: Text to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized text

    Raises:
        ValidationError: If input is too long
    """
    if not text:
        return ""

    text_clean = text.strip()

    if len(text_clean) > max_length:
        raise ValidationError(f"Input too long (max {max_length} characters)")

    return text_clean

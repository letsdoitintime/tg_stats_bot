"""Validation utilities."""

from typing import Optional, Any
from ..core.exceptions import ValidationError


def parse_boolean_argument(arg: Optional[str]) -> bool:
    """
    Parse a boolean argument from command text.
    
    Args:
        arg: String argument to parse
        
    Returns:
        Boolean value
        
    Raises:
        ValidationError: If argument is invalid
    """
    if not arg:
        raise ValidationError("Missing argument. Use 'on' or 'off'")
    
    arg_lower = arg.lower()
    
    if arg_lower in ('on', 'true', '1', 'yes', 'enabled', 'enable'):
        return True
    elif arg_lower in ('off', 'false', '0', 'no', 'disabled', 'disable'):
        return False
    else:
        raise ValidationError(
            f"Invalid argument '{arg}'. Use 'on' or 'off'"
        )


def validate_chat_id(chat_id: Any) -> int:
    """
    Validate and convert chat ID.
    
    Args:
        chat_id: Chat ID to validate
        
    Returns:
        Integer chat ID
        
    Raises:
        ValidationError: If chat ID is invalid
    """
    try:
        return int(chat_id)
    except (ValueError, TypeError):
        raise ValidationError(f"Invalid chat ID: {chat_id}")


def validate_user_id(user_id: any) -> int:
    """
    Validate and convert user ID.
    
    Args:
        user_id: User ID to validate
        
    Returns:
        Integer user ID
        
    Raises:
        ValidationError: If user ID is invalid
    """
    try:
        return int(user_id)
    except (ValueError, TypeError):
        raise ValidationError(f"Invalid user ID: {user_id}")


def validate_date_string(date_str: str) -> str:
    """
    Validate date string format (YYYY-MM-DD).
    
    Args:
        date_str: Date string to validate
        
    Returns:
        Validated date string
        
    Raises:
        ValidationError: If date format is invalid
    """
    from datetime import datetime
    
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return date_str
    except ValueError:
        raise ValidationError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")


def validate_timezone(timezone: str) -> str:
    """
    Validate timezone string.
    
    Args:
        timezone: Timezone string to validate
        
    Returns:
        Validated timezone string
        
    Raises:
        ValidationError: If timezone is invalid
    """
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    
    try:
        ZoneInfo(timezone)
        return timezone
    except ZoneInfoNotFoundError:
        raise ValidationError(f"Invalid timezone: {timezone}")


def validate_page_number(page: any, min_page: int = 1) -> int:
    """
    Validate pagination page number.
    
    Args:
        page: Page number to validate
        min_page: Minimum allowed page number
        
    Returns:
        Integer page number
        
    Raises:
        ValidationError: If page number is invalid
    """
    try:
        page_int = int(page)
        if page_int < min_page:
            raise ValidationError(f"Page number must be >= {min_page}")
        return page_int
    except (ValueError, TypeError):
        raise ValidationError(f"Invalid page number: {page}")


def validate_per_page(per_page: any, min_value: int = 1, max_value: int = 100) -> int:
    """
    Validate pagination per_page value.
    
    Args:
        per_page: Items per page to validate
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        
    Returns:
        Integer per_page value
        
    Raises:
        ValidationError: If per_page is invalid
    """
    try:
        per_page_int = int(per_page)
        if per_page_int < min_value or per_page_int > max_value:
            raise ValidationError(
                f"Items per page must be between {min_value} and {max_value}"
            )
        return per_page_int
    except (ValueError, TypeError):
        raise ValidationError(f"Invalid per_page value: {per_page}")


def validate_retention_days(days: any) -> int:
    """
    Validate retention days configuration.
    
    Args:
        days: Number of days to validate
        
    Returns:
        Integer days value
        
    Raises:
        ValidationError: If days value is invalid
    """
    try:
        days_int = int(days)
        if days_int < 1:
            raise ValidationError("Retention days must be at least 1")
        if days_int > 3650:  # 10 years max
            raise ValidationError("Retention days cannot exceed 3650 (10 years)")
        return days_int
    except (ValueError, TypeError):
        raise ValidationError(f"Invalid retention days: {days}")

"""Validation utilities."""

from typing import Optional
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


def validate_chat_id(chat_id: any) -> int:
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

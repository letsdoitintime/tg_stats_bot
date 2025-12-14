"""Input sanitization utilities for security."""

import html
import re
from typing import Optional
import structlog

logger = structlog.get_logger()

# Regex patterns
SQL_INJECTION_PATTERN = re.compile(
    r"(\bUNION\b|\bSELECT\b|\bINSERT\b|\bUPDATE\b|\bDELETE\b|\bDROP\b|\bCREATE\b|\bALTER\b)",
    re.IGNORECASE
)
COMMAND_INJECTION_PATTERN = re.compile(r"[;&|`$()]")
XSS_PATTERN = re.compile(r"<script|javascript:|onerror=|onload=", re.IGNORECASE)


def sanitize_text(text: str, max_length: int = 4000) -> str:
    """
    Sanitize user input text.
    
    Args:
        text: Input text to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized text
    """
    if not text:
        return ""
    
    # Trim to max length
    text = text[:max_length]
    
    # Escape HTML entities
    text = html.escape(text)
    
    # Remove null bytes
    text = text.replace("\x00", "")
    
    return text.strip()


def sanitize_command_arg(arg: str, allow_spaces: bool = True) -> str:
    """
    Sanitize command argument input.
    
    Args:
        arg: Command argument
        allow_spaces: Whether to allow spaces
        
    Returns:
        Sanitized argument
    """
    if not arg:
        return ""
    
    # Remove command injection characters
    arg = COMMAND_INJECTION_PATTERN.sub("", arg)
    
    # Remove leading/trailing whitespace
    arg = arg.strip()
    
    # Remove internal spaces if not allowed
    if not allow_spaces:
        arg = arg.replace(" ", "")
    
    return arg[:1000]  # Max 1000 chars for args


def is_safe_sql_input(text: str) -> bool:
    """
    Check if text appears to contain SQL injection attempts.
    
    Note: This is a basic check. We rely on parameterized queries
    as the primary defense, but this adds an extra layer.
    
    Args:
        text: Input to check
        
    Returns:
        True if safe, False if suspicious
    """
    if not text:
        return True
    
    # Check for SQL keywords
    if SQL_INJECTION_PATTERN.search(text):
        logger.warning("potential_sql_injection", text=text[:100])
        return False
    
    # Check for excessive special characters (possible obfuscation)
    special_char_ratio = sum(1 for c in text if not c.isalnum() and not c.isspace()) / len(text)
    if special_char_ratio > 0.5:
        logger.warning("suspicious_input_high_special_chars", ratio=special_char_ratio)
        return False
    
    return True


def is_safe_web_input(text: str) -> bool:
    """
    Check if text appears to contain XSS attempts.
    
    Args:
        text: Input to check
        
    Returns:
        True if safe, False if suspicious
    """
    if not text:
        return True
    
    if XSS_PATTERN.search(text):
        logger.warning("potential_xss_attempt", text=text[:100])
        return False
    
    return True


def sanitize_chat_id(chat_id: any) -> Optional[int]:
    """
    Validate and convert chat ID to int.
    
    Args:
        chat_id: Chat ID (int or string)
        
    Returns:
        Valid chat ID or None
    """
    try:
        chat_id = int(chat_id)
        # Telegram chat IDs are typically in specific ranges
        if abs(chat_id) > 10**15:  # Sanity check
            return None
        return chat_id
    except (ValueError, TypeError):
        logger.warning("invalid_chat_id", value=chat_id)
        return None


def sanitize_user_id(user_id: any) -> Optional[int]:
    """
    Validate and convert user ID to int.
    
    Args:
        user_id: User ID (int or string)
        
    Returns:
        Valid user ID or None
    """
    try:
        user_id = int(user_id)
        if user_id <= 0 or user_id > 10**15:  # Sanity check
            return None
        return user_id
    except (ValueError, TypeError):
        logger.warning("invalid_user_id", value=user_id)
        return None


def sanitize_username(username: str) -> Optional[str]:
    """
    Sanitize Telegram username.
    
    Args:
        username: Username to sanitize
        
    Returns:
        Sanitized username or None if invalid
    """
    if not username:
        return None
    
    # Remove @ prefix if present
    username = username.lstrip("@")
    
    # Telegram usernames are alphanumeric with underscores, 5-32 chars
    if not re.match(r"^[a-zA-Z0-9_]{5,32}$", username):
        return None
    
    return username.lower()

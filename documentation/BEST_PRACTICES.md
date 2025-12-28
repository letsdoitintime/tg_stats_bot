# Best Practices Guide for TG Stats Bot Development

## Overview

This guide provides coding standards, patterns, and best practices for contributing to the TG Stats Bot project.

## Table of Contents

1. [Code Organization](#code-organization)
2. [Error Handling](#error-handling)
3. [Database Operations](#database-operations)
4. [Async Patterns](#async-patterns)
5. [Security](#security)
6. [Testing](#testing)
7. [Logging](#logging)
8. [Documentation](#documentation)

## Code Organization

### Layered Architecture

Follow the established layered architecture:

```
┌─────────────────────────────────┐
│ Handlers (bot_main.py)          │  ← Telegram event handlers
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐
│ Services (services/)             │  ← Business logic
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐
│ Repositories (repositories/)     │  ← Data access layer
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐
│ Database (PostgreSQL)            │  ← Persistent storage
└─────────────────────────────────┘
```

**Rules:**
- ✅ Handlers should only parse input and call services
- ✅ Services contain business logic and orchestrate repositories
- ✅ Repositories handle database queries only
- ❌ Never access database directly from handlers
- ❌ Never put business logic in repositories

### File Organization

```
tgstats/
├── core/              # Core configuration and constants
│   ├── config.py      # Pydantic settings
│   ├── constants.py   # Global constants
│   └── exceptions.py  # Custom exceptions
├── handlers/          # Telegram event handlers
├── services/          # Business logic layer
├── repositories/      # Data access layer
├── models.py          # SQLAlchemy models
├── schemas/           # Pydantic schemas for validation
└── utils/             # Utility functions and helpers
```

## Error Handling

### Use Custom Exceptions

Always use custom exceptions from `core.exceptions`:

```python
# ✅ Good
from tgstats.core.exceptions import ValidationError, NotFoundError

if not user_id:
    raise ValidationError("user_id is required")

if not chat:
    raise NotFoundError("Chat not found", details={"chat_id": chat_id})
```

```python
# ❌ Bad
if not user_id:
    raise ValueError("user_id is required")  # Generic exception
```

### Exception Hierarchy

```
TgStatsError (base)
├── DatabaseError
│   ├── RecordNotFoundError
│   ├── DuplicateRecordError
│   └── DatabaseConnectionError
├── ValidationError
│   ├── InvalidInputError
│   └── InvalidConfigurationError
├── AuthorizationError
│   ├── UnauthorizedError
│   ├── InsufficientPermissionsError
│   └── InvalidTokenError
├── NotFoundError
├── ConfigurationError
├── MessageProcessingError
├── PluginError
│   └── PluginLoadError
├── RateLimitExceededError
├── CacheError
└── TaskError
```

### Error Handler Decorator

Use the `@with_db_session` decorator for automatic error handling:

```python
@with_db_session
async def my_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession):
    # Session is auto-provided
    # Commit on success, rollback on error
    # Errors are logged and user-friendly messages sent
    pass
```

## Database Operations

### Always Use Async Sessions

```python
# ✅ Good - async session with proper context manager
async with async_session() as session:
    result = await session.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
```

```python
# ❌ Bad - sync session
session = Session()
user = session.query(User).filter_by(user_id=user_id).first()
```

### Use Repositories for Queries

```python
# ✅ Good - use repository
from tgstats.repositories.factory import RepositoryFactory

repos = RepositoryFactory(session)
user = await repos.user.get_by_user_id(user_id)
```

```python
# ❌ Bad - direct query in handler
result = await session.execute(select(User).where(User.user_id == user_id))
```

### Use Factory Pattern

```python
# ✅ Good - use service factory
from tgstats.services.factory import ServiceFactory

services = ServiceFactory(session)
await services.chat.setup_chat(chat_id)
await services.message.process_message(message)
```

### Parameterized Queries Only

```python
# ✅ Good - parameterized query
query = select(Message).where(Message.chat_id == chat_id)
result = await session.execute(query)
```

```python
# ❌ Bad - string concatenation (SQL injection risk!)
query = f"SELECT * FROM messages WHERE chat_id = {chat_id}"
```

### Use Indexes for Query Optimization

When adding new query patterns, consider adding indexes:

```python
# In models.py
__table_args__ = (
    Index("ix_messages_chat_date", "chat_id", "date"),
    Index("ix_messages_user_date", "user_id", "date"),
)
```

## Async Patterns

### Proper Async/Await Usage

```python
# ✅ Good - await all async calls
user = await repos.user.get_by_user_id(user_id)
chat = await repos.chat.get_by_chat_id(chat_id)
```

```python
# ❌ Bad - missing await
user = repos.user.get_by_user_id(user_id)  # Returns coroutine, not result!
```

### Concurrent Operations

Use `asyncio.gather` for concurrent operations:

```python
# ✅ Good - concurrent execution
user, chat = await asyncio.gather(
    repos.user.get_by_user_id(user_id),
    repos.chat.get_by_chat_id(chat_id)
)
```

```python
# ❌ Bad - sequential execution
user = await repos.user.get_by_user_id(user_id)
chat = await repos.chat.get_by_chat_id(chat_id)  # Waits for user first
```

### Timeout Handling

Add timeouts for external API calls:

```python
# ✅ Good - with timeout
try:
    bot_info = await asyncio.wait_for(
        context.bot.get_me(),
        timeout=5.0
    )
except asyncio.TimeoutError:
    logger.error("timeout_getting_bot_info")
```

## Security

### Input Validation

**Always** validate and sanitize user input:

```python
# ✅ Good - validate and sanitize
from tgstats.utils.sanitizer import sanitize_chat_id, sanitize_text

chat_id = sanitize_chat_id(request.chat_id)
if not chat_id:
    raise ValidationError("Invalid chat_id")

text = sanitize_text(user_input, max_length=1000)
```

```python
# ❌ Bad - use raw input
text = user_input  # No validation!
```

### Use Sanitizer Functions

Available sanitizers:
- `sanitize_text()` - Remove HTML, control characters
- `sanitize_chat_id()` - Validate Telegram chat ID format
- `sanitize_user_id()` - Validate Telegram user ID format
- `sanitize_username()` - Validate Telegram username format
- `sanitize_command_arg()` - Remove command injection chars
- `is_safe_sql_input()` - Check for SQL injection patterns
- `is_safe_web_input()` - Check for XSS patterns

### Authentication

Require admin token for sensitive API endpoints:

```python
from tgstats.web.app import verify_admin_token

@app.get("/api/admin/action")
async def admin_action(_token: None = Depends(verify_admin_token)):
    # Only accessible with valid X-Admin-Token header
    pass
```

### Rate Limiting

Use rate limiter for user-facing commands:

```python
from tgstats.utils.rate_limiter import rate_limiter

is_limited, message = rate_limiter.is_rate_limited(user_id)
if is_limited:
    await update.message.reply_text(message)
    return
```

### No Secrets in Code

```python
# ❌ Bad - hardcoded secret
API_TOKEN = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"

# ✅ Good - use environment variables
from tgstats.core.config import settings
API_TOKEN = settings.bot_token
```

## Testing

### Write Tests for New Features

Every new feature should have tests:

```python
# tests/test_my_feature.py
import pytest
from tgstats.services.my_service import MyService

@pytest.mark.asyncio
async def test_my_service_method(session):
    """Test my service method."""
    service = MyService(session)
    result = await service.my_method()
    assert result is not None
```

### Use Fixtures

```python
@pytest.fixture
async def user_service(session):
    """Create user service fixture."""
    from tgstats.services.user_service import UserService
    return UserService(session)
```

### Mock External Dependencies

```python
from unittest.mock import AsyncMock, patch

@patch('tgstats.services.message_service.context.bot.send_message')
async def test_with_mocked_telegram(mock_send):
    mock_send.return_value = AsyncMock()
    # Test code here
```

### Test Edge Cases

```python
# Test with None
result = await service.process_data(None)
assert result is None

# Test with empty string
result = await service.process_data("")
assert result == ""

# Test with very long input
result = await service.process_data("x" * 10000)
assert len(result) <= 4000
```

## Logging

### Use Structured Logging

```python
# ✅ Good - structured logging with context
import structlog
logger = structlog.get_logger(__name__)

logger.info(
    "message_processed",
    chat_id=chat_id,
    user_id=user_id,
    text_length=len(text)
)
```

```python
# ❌ Bad - string formatting
logger.info(f"Processed message from {user_id} in {chat_id}")
```

### Log Levels

- **DEBUG**: Detailed diagnostic info (function entry/exit, variable values)
- **INFO**: General informational messages (command executed, setup completed)
- **WARNING**: Something unexpected but recoverable (rate limit hit, cache miss)
- **ERROR**: Error that prevented operation (database error, API failure)
- **CRITICAL**: System-wide failure requiring immediate attention

```python
logger.debug("Entering process_message", message_id=msg_id)
logger.info("Group setup completed", chat_id=chat_id)
logger.warning("Rate limit exceeded", user_id=user_id)
logger.error("Database connection failed", error=str(e))
logger.critical("Redis unavailable, app cannot start")
```

### Include Context

```python
# ✅ Good - includes context
logger.error(
    "Failed to process message",
    chat_id=message.chat_id,
    user_id=message.from_user.id,
    error=str(e),
    exc_info=True  # Include traceback
)
```

```python
# ❌ Bad - minimal context
logger.error("Error processing message")
```

## Documentation

### Docstrings

Use Google-style docstrings:

```python
def calculate_statistics(
    messages: List[Message],
    start_date: datetime,
    end_date: datetime
) -> Dict[str, Any]:
    """
    Calculate message statistics for a time period.
    
    Args:
        messages: List of Message objects to analyze
        start_date: Start of analysis period (inclusive)
        end_date: End of analysis period (inclusive)
        
    Returns:
        Dictionary containing:
            - total_messages: Total message count
            - unique_users: Count of unique users
            - avg_length: Average message length
            
    Raises:
        ValidationError: If date range is invalid
        
    Example:
        >>> stats = calculate_statistics(messages, start, end)
        >>> print(stats['total_messages'])
        1234
    """
    pass
```

### Type Hints

Always use type hints:

```python
# ✅ Good - with type hints
async def get_user(session: AsyncSession, user_id: int) -> Optional[User]:
    pass

# ❌ Bad - no type hints
async def get_user(session, user_id):
    pass
```

### Complex Types

```python
from typing import List, Dict, Optional, Tuple, Union

# Use specific types
def process_data(
    items: List[Dict[str, Any]],
    config: Optional[Dict[str, str]] = None
) -> Tuple[int, List[str]]:
    pass
```

### README Updates

Update documentation when adding features:
- Add to `README.md` for user-facing features
- Add to `documentation/` for technical details
- Update examples in docstrings

## Common Patterns

### Decorator Stacking

```python
# Correct order: with_db_session first, then other decorators
@with_db_session
@require_admin
@group_only
async def admin_command(update, context, session):
    pass
```

### Configuration Access

```python
# ✅ Good - use settings object
from tgstats.core.config import settings

timeout = settings.bot_read_timeout
```

```python
# ❌ Bad - access environment directly
import os
timeout = int(os.getenv('BOT_READ_TIMEOUT', '30'))
```

### Factory Pattern

```python
# ✅ Good - use factories
services = ServiceFactory(session)
repos = RepositoryFactory(session)
```

```python
# ❌ Bad - manual instantiation
chat_service = ChatService(session, ChatRepository(session), GroupSettingsRepository(session))
```

## Performance Considerations

### Use Indexes

Add database indexes for frequently queried columns:
```python
Index("ix_messages_chat_date", "chat_id", "date")
```

### Batch Operations

```python
# ✅ Good - batch insert
session.add_all(messages)
await session.flush()

# ❌ Bad - one at a time
for message in messages:
    session.add(message)
    await session.flush()
```

### Cache Frequently Accessed Data

```python
from tgstats.utils.cache import cached

@cached("user_stats", ttl=300)
async def get_user_stats(user_id: int) -> dict:
    # Expensive operation cached for 5 minutes
    pass
```

### Connection Pooling

Rely on SQLAlchemy's connection pool - don't create engines manually:

```python
# ✅ Good - use existing async_session
async with async_session() as session:
    pass

# ❌ Bad - create new engine
engine = create_async_engine(...)
```

## Anti-Patterns to Avoid

### ❌ Blocking I/O in Async Functions

```python
# ❌ Bad
async def process():
    result = requests.get(url)  # Blocks event loop!
    
# ✅ Good
async def process():
    async with aiohttp.ClientSession() as client:
        result = await client.get(url)
```

### ❌ Catching All Exceptions

```python
# ❌ Bad
try:
    result = await process()
except:  # Catches KeyboardInterrupt, SystemExit!
    pass

# ✅ Good
try:
    result = await process()
except (ValueError, TypeError) as e:
    logger.error("process_failed", error=str(e))
```

### ❌ Long-Running Tasks in Handlers

```python
# ❌ Bad - blocks bot
@with_db_session
async def long_command(update, context, session):
    await heavy_computation()  # Blocks other updates!
    
# ✅ Good - delegate to Celery
@with_db_session
async def long_command(update, context, session):
    task = heavy_computation.delay()  # Background task
    await update.message.reply_text(f"Processing... Task ID: {task.id}")
```

## Code Review Checklist

Before submitting a PR, check:

- [ ] All async functions use `await`
- [ ] Database queries use parameterized queries
- [ ] User input is validated and sanitized
- [ ] Errors use custom exception classes
- [ ] Functions have type hints
- [ ] Public functions have docstrings
- [ ] Tests are added for new features
- [ ] Logs use structured logging
- [ ] No secrets in code
- [ ] Configuration uses `settings` object
- [ ] Follows layered architecture pattern
- [ ] No wildcard imports
- [ ] Code passes linting (ruff/black)

## Resources

- [SQLAlchemy 2.0 Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [python-telegram-bot Documentation](https://docs.python-telegram-bot.org/)
- [Pydantic Settings Documentation](https://docs.pydantic.dev/latest/usage/settings/)
- [FastAPI Best Practices](https://fastapi.tiangolo.com/tutorial/)
- [Structlog Documentation](https://www.structlog.org/)

## Questions?

Check existing code for examples or ask in the team chat!

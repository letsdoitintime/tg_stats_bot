# Code Quality Guidelines

This document outlines coding standards, best practices, and quality guidelines for the Telegram Stats Bot project.

## Table of Contents

- [Code Style](#code-style)
- [Documentation](#documentation)
- [Error Handling](#error-handling)
- [Testing](#testing)
- [Database Operations](#database-operations)
- [Security](#security)
- [Performance](#performance)
- [Git Practices](#git-practices)

## Code Style

### Python Style Guide

We follow PEP 8 with some modifications:

- **Line Length**: 100 characters (configured in black and ruff)
- **Imports**: Organized using isort with black profile
- **Formatting**: Automated with black
- **Linting**: Enforced with ruff and flake8

### Pre-commit Hooks

Install pre-commit hooks to enforce style automatically:

```bash
pip install pre-commit
pre-commit install
```

This runs on every commit:
- black (formatting)
- isort (import sorting)
- flake8 (linting)
- mypy (type checking)
- trailing whitespace removal
- YAML/JSON validation

### Type Hints

**Always use type hints** for function signatures:

```python
# Good ✅
async def get_user(user_id: int) -> Optional[User]:
    """Get user by ID."""
    ...

# Bad ❌
async def get_user(user_id):
    """Get user by ID."""
    ...
```

**Use type hints for complex types:**

```python
from typing import Dict, List, Optional, Tuple

def process_data(
    items: List[Dict[str, Any]],
    options: Optional[Dict[str, str]] = None
) -> Tuple[int, List[str]]:
    ...
```

### Import Organization

Organize imports in three groups (isort does this automatically):

```python
# Standard library
import asyncio
from datetime import datetime
from typing import Optional

# Third-party
from sqlalchemy import select
from telegram import Update

# Local
from ..models import User
from ..core.exceptions import ValidationError
```

## Documentation

### Module Docstrings

Every module should have a docstring explaining its purpose:

```python
"""Message handlers for the Telegram bot.

This module handles incoming Telegram messages and edited messages,
processing them through the MessageService for storage and analytics.
"""
```

### Function Docstrings

Use Google-style docstrings for functions:

```python
def validate_chat_id(chat_id: Any) -> int:
    """Validate and convert chat_id to integer.
    
    Args:
        chat_id: Chat ID to validate (can be int or string)
        
    Returns:
        Validated integer chat ID
        
    Raises:
        ValidationError: If chat_id is invalid or zero
        
    Example:
        >>> validate_chat_id("-1001234567890")
        -1001234567890
        >>> validate_chat_id("invalid")
        ValidationError: Invalid chat ID
    """
```

### Class Docstrings

Document classes with their purpose and usage:

```python
class MessageService:
    """Service for message-related operations.
    
    This service handles the business logic for processing Telegram messages,
    including feature extraction, user/chat management, and storage.
    
    Attributes:
        session: Database session for this service instance
        message_repo: Repository for message operations
        chat_service: Service for chat-related operations
        user_service: Service for user-related operations
    
    Example:
        async with async_session() as session:
            service = MessageService(session)
            await service.process_message(telegram_message)
            await session.commit()
    """
```

### Inline Comments

Use inline comments sparingly and only for complex logic:

```python
# Good ✅
# Calculate offset in UTC considering DST transitions
utc_offset = timezone.utcoffset(datetime.now())

# Bad ❌ (obvious from code)
# Increment counter
counter += 1
```

## Error Handling

### Custom Exceptions

Use specific exception types from `core.exceptions`:

```python
# Good ✅
from ..core.exceptions import ValidationError, DatabaseError

if not chat_id:
    raise ValidationError("Chat ID is required")

# Bad ❌
if not chat_id:
    raise Exception("Chat ID is required")
```

### Exception Handling Layers

1. **Handlers**: Catch and log, don't crash the bot
2. **Services**: Raise specific exceptions, let handler decide
3. **Repositories**: Let database exceptions bubble up

```python
# Handler layer
async def handle_message(update: Update, context):
    try:
        service = MessageService(session)
        await service.process_message(update.message)
    except DatabaseError as e:
        logger.error("Database error", error=str(e))
        await session.rollback()
    except Exception as e:
        logger.error("Unexpected error", exc_info=True)
        await session.rollback()

# Service layer
async def process_message(self, message: TelegramMessage):
    if not message.from_user:
        raise ValidationError("Message must have user info")
    # Process message...
```

### Logging Errors

Always include context when logging errors:

```python
logger.error(
    "Error processing message",
    chat_id=message.chat.id,
    user_id=message.from_user.id,
    msg_id=message.message_id,
    error_type=type(e).__name__,
    error=str(e),
    exc_info=True  # Include traceback
)
```

## Testing

### Test Organization

```python
# tests/test_services/test_message_service.py

import pytest
from tgstats.services.message_service import MessageService

class TestMessageService:
    """Tests for MessageService."""
    
    @pytest.mark.asyncio
    async def test_process_message_success(self, mock_session, sample_message):
        """Test successful message processing."""
        service = MessageService(mock_session)
        result = await service.process_message(sample_message)
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_process_message_no_user(self, mock_session):
        """Test message without user info is rejected."""
        service = MessageService(mock_session)
        with pytest.raises(ValidationError):
            await service.process_message(message_without_user)
```

### Fixtures

Use fixtures for common test data:

```python
# tests/conftest.py

@pytest.fixture
def sample_message():
    """Create a sample Telegram message."""
    return Message(
        message_id=1,
        chat=Chat(id=-1001234567890, type="supergroup"),
        from_user=User(id=123456, first_name="Test"),
        text="Hello world",
        date=datetime.now()
    )
```

### Test Coverage

Aim for:
- **80%+ overall coverage**
- **100% for critical paths** (authentication, payment processing)
- **90%+ for business logic** (services, repositories)
- **50%+ for handlers** (mostly integration tests)

Run coverage:
```bash
pytest --cov=tgstats --cov-report=html
```

## Database Operations

### Always Use Repositories

Don't write raw SQL queries in services:

```python
# Good ✅
user = await self.user_repo.get_by_id(user_id)

# Bad ❌
result = await session.execute(
    text("SELECT * FROM users WHERE user_id = :id"),
    {"id": user_id}
)
```

### Transaction Management

Manage transactions at the handler level:

```python
# Good ✅
async with async_session() as session:
    try:
        service = MessageService(session)
        await service.process_message(message)
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise

# Bad ❌ (committing in service)
class MessageService:
    async def process_message(self, message):
        # Do work
        await self.session.commit()  # Don't do this!
```

### Avoid N+1 Queries

Use eager loading when accessing relationships:

```python
# Good ✅
from sqlalchemy.orm import selectinload

users = await session.execute(
    select(User)
    .options(selectinload(User.messages))
    .where(User.id.in_(user_ids))
)

# Bad ❌
for user_id in user_ids:
    user = await get_user(user_id)
    messages = user.messages  # Triggers N queries!
```

## Security

### Input Validation

Always validate user inputs:

```python
from ..utils.validation import validate_chat_id, validate_page_params

# Validate and convert
chat_id = validate_chat_id(request_chat_id)
page, page_size = validate_page_params(request_page, request_page_size)
```

### Input Sanitization

Sanitize inputs that will be displayed:

```python
from ..utils.sanitizer import sanitize_text

# Sanitize before storing/displaying
clean_text = sanitize_text(user_input, max_length=4000)
```

### Never Trust User Input

```python
# Good ✅
if not is_user_admin(user_id, chat_id):
    raise InsufficientPermissionsError("Admin required")

# Bad ❌
if request.headers.get("X-Is-Admin") == "true":
    # Never trust client-provided headers!
```

### Use Parameterized Queries

SQLAlchemy does this automatically, but be aware:

```python
# Good ✅ (SQLAlchemy parameterizes automatically)
result = await session.execute(
    select(User).where(User.username == username)
)

# Bad ❌ (vulnerable to SQL injection)
result = await session.execute(
    text(f"SELECT * FROM users WHERE username = '{username}'")
)
```

## Performance

### Use Async Operations

Always use async for I/O operations:

```python
# Good ✅
async def get_users():
    async with async_session() as session:
        result = await session.execute(select(User))
        return result.scalars().all()

# Bad ❌
def get_users():
    with sync_session() as session:
        return session.execute(select(User)).scalars().all()
```

### Cache Expensive Operations

```python
from ..utils.cache import cache

@cache(ttl=300)  # Cache for 5 minutes
async def get_chat_statistics(chat_id: int):
    # Expensive database query
    ...
```

### Batch Operations

When processing multiple items:

```python
# Good ✅
user_ids = [msg.user_id for msg in messages]
users = await session.execute(
    select(User).where(User.id.in_(user_ids))
)

# Bad ❌
users = []
for msg in messages:
    user = await get_user(msg.user_id)  # N queries!
    users.append(user)
```

## Git Practices

### Commit Messages

Use conventional commits format:

```
type(scope): subject

body (optional)

footer (optional)
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Example:
```
feat(api): add pagination to user list endpoint

Add page and page_size query parameters to /api/users endpoint.
Implement pagination using SQLAlchemy offset/limit.

Closes #123
```

### Branch Naming

- `feature/feature-name` - New features
- `fix/bug-name` - Bug fixes
- `refactor/what-changed` - Refactoring
- `docs/what-documented` - Documentation

### Pull Requests

PR checklist:
- [ ] Code follows style guide (pre-commit passes)
- [ ] All tests pass
- [ ] New tests added for new functionality
- [ ] Documentation updated if needed
- [ ] No breaking changes (or clearly documented)
- [ ] Security implications considered

## Code Review Checklist

When reviewing code, check for:

- [ ] **Correctness**: Does it do what it's supposed to?
- [ ] **Error Handling**: Are errors handled appropriately?
- [ ] **Testing**: Are there adequate tests?
- [ ] **Documentation**: Are changes documented?
- [ ] **Performance**: Any obvious performance issues?
- [ ] **Security**: Any security vulnerabilities?
- [ ] **Maintainability**: Is the code readable and well-organized?
- [ ] **Type Hints**: Are type hints present and correct?
- [ ] **Dependencies**: Are new dependencies necessary and properly added?

## Quality Tools

### Running Quality Checks

```bash
# Format code
black .

# Sort imports
isort .

# Lint code
ruff check .

# Type check
mypy tgstats/

# Run tests
pytest

# Check coverage
pytest --cov=tgstats

# Run all pre-commit hooks
pre-commit run --all-files
```

### CI/CD Integration

All of these checks should run in CI:

```yaml
# .github/workflows/ci.yml
- name: Lint
  run: |
    black --check .
    isort --check .
    ruff check .
    mypy tgstats/

- name: Test
  run: pytest --cov=tgstats --cov-fail-under=80
```

## Resources

- [PEP 8 - Style Guide for Python Code](https://www.python.org/dev/peps/pep-0008/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [SQLAlchemy Best Practices](https://docs.sqlalchemy.org/en/14/orm/queryguide.html)
- [FastAPI Best Practices](https://fastapi.tiangolo.com/tutorial/)

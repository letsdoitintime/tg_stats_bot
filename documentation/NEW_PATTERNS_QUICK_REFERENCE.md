# Quick Reference - New Patterns (December 2025)

## Using ServiceFactory (Recommended Pattern)

### In Command Handlers

```python
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update
from telegram.ext import ContextTypes
from tgstats.services import ServiceFactory
from tgstats.utils.decorators import with_db_session

@with_db_session
async def my_command(update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession) -> None:
    """Command handler with new pattern."""
    
    # Create service factory (shares session across all services)
    services = ServiceFactory(session)
    
    # Use any service - all share same transaction
    chat = await services.chat.get_or_create_chat(update.effective_chat)
    user = await services.user.get_or_create_user(update.effective_user)
    
    # Commit happens automatically on success
    # Rollback happens automatically on error
```

### In Message Handlers (Background Processing)

```python
from tgstats.db import async_session
from tgstats.services import ServiceFactory

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process message silently in background."""
    if not update.message:
        return
    
    async with async_session() as session:
        try:
            services = ServiceFactory(session)
            
            # Process message
            await services.message.process_message(update.message)
            
            # Manual commit for background handlers
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error("Error processing message", error=str(e))
```

---

## Service Layer Patterns

### Creating a New Service

```python
"""My new service."""

from typing import TYPE_CHECKING
from sqlalchemy.ext.asyncio import AsyncSession
from .base import BaseService

if TYPE_CHECKING:
    from ..repositories.factory import RepositoryFactory

class MyService(BaseService):
    """Service for my feature."""
    
    def __init__(self, session: AsyncSession, repo_factory: "RepositoryFactory" = None):
        """Initialize service."""
        super().__init__(session, repo_factory)
    
    async def do_something(self, param: int) -> Result:
        """Do something with repositories."""
        # Access repositories via self.repos
        data = await self.repos.my_repo.get_data(param)
        
        # Use self.logger (inherited from BaseService)
        self.logger.info("Operation completed", param=param)
        
        # Optionally commit (or let handler do it)
        await self.commit()
        
        return data
```

---

## Repository Layer Patterns

### Adding a Repository to Factory

1. Create your repository (inherit from `BaseRepository`):

```python
# my_repository.py
from .base import BaseRepository
from ..models import MyModel

class MyRepository(BaseRepository[MyModel]):
    """Repository for MyModel."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(MyModel, session)
    
    async def custom_query(self, param: int):
        """Custom query method."""
        result = await self.session.execute(
            select(MyModel).where(MyModel.param == param)
        )
        return result.scalars().all()
```

2. Add to `RepositoryFactory`:

```python
# repositories/factory.py
from .my_repository import MyRepository

class RepositoryFactory:
    def __init__(self, session: AsyncSession):
        self.session = session
        self._my_repo = None
    
    @property
    def my_repo(self) -> MyRepository:
        """Get or create my repository."""
        if self._my_repo is None:
            self._my_repo = MyRepository(self.session)
        return self._my_repo
```

3. Add to `ServiceFactory` (if needed):

```python
# services/factory.py
from .my_service import MyService

class ServiceFactory:
    def __init__(self, session: AsyncSession):
        self.repos = RepositoryFactory(session)
        self._my_service = None
    
    @property
    def my_service(self) -> MyService:
        """Get or create my service."""
        if self._my_service is None:
            self._my_service = MyService(self.session, self.repos)
        return self._my_service
```

---

## Handler Decorators

### Decorator Stacking Order

```python
@track_time("my_command")      # Optional: metrics tracking
@with_db_session               # Required: provides session
@require_admin                 # Optional: admin check
@group_only                    # Optional: group-only check
async def my_command(update, context, session):
    """Handler with proper decorator order."""
    pass
```

**Important:** `@with_db_session` must come before `@require_admin` and `@group_only`

### Auto-Commit Behavior

The `@with_db_session` decorator now auto-commits:

```python
@with_db_session
async def handler(update, context, session):
    service = ChatService(session)
    
    # Make changes
    await service.setup_chat(chat_id)
    
    # NO NEED to call session.commit()
    # Decorator commits automatically on success
    # Decorator rolls back automatically on error
```

**When to manually commit:**
- In background handlers without decorator
- When you need multiple intermediate commits
- When implementing transaction boundaries explicitly

---

## Configuration Validation

### Environment Variables

**Required for webhook mode:**

```bash
# .env
MODE=webhook
WEBHOOK_URL=https://mybot.example.com  # REQUIRED when MODE=webhook
```

**Validation happens at startup** - the app will fail to start with clear error if misconfigured.

---

## Health Check Endpoints

### Available Endpoints

```bash
# Basic health check
GET /health
# Returns: {"status": "healthy", "service": "tgstats-bot"}

# Liveness probe (K8s)
GET /health/live
# Returns: {"status": "alive"}

# Readiness probe (K8s) - checks all dependencies
GET /health/ready
# Returns: {
#   "status": "ready",
#   "checks": {
#     "database": true,
#     "redis": true,
#     "celery": {"available": true, "worker_count": 2},
#     "telegram_api": {"available": true, "bot_username": "mybot"}
#   }
# }

# Startup probe (K8s)
GET /health/startup
# Returns: {"status": "started"}

# Detailed stats
GET /health/stats
# Returns connection pool stats and environment info
```

### Kubernetes Probe Configuration

```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8010
  initialDelaySeconds: 10
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8010
  initialDelaySeconds: 5
  periodSeconds: 10

startupProbe:
  httpGet:
    path: /health/startup
    port: 8010
  initialDelaySeconds: 0
  periodSeconds: 5
  failureThreshold: 30
```

---

## Error Handling

### Automatic Error Handling

The `@with_db_session` decorator handles:

1. **TgStatsError** - Custom app errors
   - Sends error message to user
   - Logs with error details
   - Rolls back transaction

2. **Exception** - Unexpected errors
   - Sends generic error message to user
   - Logs with full traceback
   - Rolls back transaction

### Custom Error Messages

```python
from tgstats.core.exceptions import ValidationError, ChatNotSetupError

@with_db_session
async def handler(update, context, session):
    if not valid_input:
        raise ValidationError("Invalid input format")
        # User sees: "❌ Error: Invalid input format"
    
    settings = await service.get_chat_settings(chat_id)
    if not settings:
        raise ChatNotSetupError(f"Chat {chat_id} not configured")
        # User sees: "❌ Error: Chat 123 not configured"
```

---

## Testing Patterns

### Testing with Factories

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from tgstats.services import ServiceFactory

@pytest.mark.asyncio
async def test_my_feature(test_session: AsyncSession):
    """Test using ServiceFactory."""
    
    # Create factory with test session
    services = ServiceFactory(test_session)
    
    # Use services
    result = await services.chat.setup_chat(123)
    
    # Verify
    assert result.chat_id == 123
    assert result.store_text is True
```

### Mocking Repositories

```python
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_with_mock_repo(test_session):
    """Test with mocked repository."""
    
    # Create mock factory
    mock_repos = MagicMock()
    mock_repos.chat.get_by_chat_id = AsyncMock(return_value=mock_chat)
    
    # Create service with mock
    service = ChatService(test_session, mock_repos)
    
    # Test
    result = await service.get_or_create_chat(tg_chat)
    
    # Verify
    mock_repos.chat.get_by_chat_id.assert_called_once()
```

---

## Migration Checklist for Existing Code

### ✅ Services
- [ ] Ensure service inherits from `BaseService`
- [ ] Add `repo_factory` parameter to `__init__`
- [ ] Use `self.repos` instead of direct repository instantiation
- [ ] Use `self.logger` instead of module-level logger
- [ ] Use `await self.commit()` instead of `await self.session.commit()`

### ✅ Command Handlers
- [ ] Add `@with_db_session` decorator
- [ ] Add `session: AsyncSession` parameter
- [ ] Remove `async with async_session()` context manager
- [ ] Remove manual error handling (let decorator handle)
- [ ] Remove manual `session.commit()` calls
- [ ] Remove manual `session.rollback()` calls

### ✅ Repositories
- [ ] Add to `RepositoryFactory` if needed
- [ ] Export in `repositories/__init__.py` if needed

---

## Common Pitfalls to Avoid

### ❌ Don't: Manual session in decorated handler

```python
@with_db_session
async def handler(update, context, session):
    # DON'T do this - creates new session
    async with async_session() as new_session:
        service = ChatService(new_session)
```

### ✅ Do: Use provided session

```python
@with_db_session
async def handler(update, context, session):
    # Use the provided session
    service = ChatService(session)
```

---

### ❌ Don't: Create services without factory

```python
service1 = ChatService(session)
service2 = MessageService(session)
# They don't share repository instances
```

### ✅ Do: Use ServiceFactory

```python
services = ServiceFactory(session)
# All services share same repos and session
chat_result = await services.chat.setup_chat(123)
msg_result = await services.message.process_message(msg)
```

---

### ❌ Don't: Import repositories in TYPE_CHECKING

```python
if TYPE_CHECKING:
    from ..repositories.chat_repository import ChatRepository  # Wrong
```

### ✅ Do: Import factory, lazy load repositories

```python
if TYPE_CHECKING:
    from ..repositories.factory import RepositoryFactory  # Right

# In method:
data = await self.repos.chat.some_method()  # Lazy loaded
```

---

## Summary

**Key Takeaways:**

1. **Always inherit from BaseService** for services
2. **Always use @with_db_session** for command handlers
3. **Use ServiceFactory** for cleaner dependency management
4. **Use self.repos** to access repositories
5. **Let decorator handle commits/rollbacks** in handlers
6. **Use TYPE_CHECKING** to avoid circular imports
7. **Validate config at startup** with model validators
8. **Check comprehensive health** endpoints for monitoring

These patterns ensure consistency, testability, and maintainability across the codebase.

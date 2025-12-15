# Migration Guide for Code Improvements

## For Developers Using the Codebase

This guide helps you adapt to the recent code structure improvements.

## 🔄 Breaking Changes: NONE

All changes are backward-compatible. Existing code will continue to work.

## ✅ Recommended Migrations

### 1. Using Repository Factory (Optional)

**Before:**
```python
class MyService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.chat_repo = ChatRepository(session)
        self.user_repo = UserRepository(session)
```

**After (Recommended):**
```python
from ..repositories.factory import RepositoryFactory
from ..services.base import BaseService

class MyService(BaseService):
    def __init__(self, session: AsyncSession, repo_factory: RepositoryFactory = None):
        super().__init__(session, repo_factory)
        # Access repositories via self.repos
        # self.repos.chat, self.repos.user, etc.
```

### 2. Using BaseService (Recommended)

**Benefits:**
- Automatic repository factory integration
- Built-in transaction management methods
- Per-service logger instance
- Consistent service patterns

**Before:**
```python
class MyService:
    def __init__(self, session: AsyncSession):
        self.session = session
        
    async def do_something(self):
        # ... do work ...
        await self.session.commit()
```

**After:**
```python
from ..services.base import BaseService

class MyService(BaseService):
    async def do_something(self):
        # ... do work ...
        await self.commit()  # Use BaseService method
        self.logger.info("Operation completed")  # Use self.logger
```

### 3. Exception Handling

**Before:**
```python
from ..utils.validation import ValidationError  # Don't use this
```

**After:**
```python
from ..core.exceptions import ValidationError  # Use this instead
```

### 4. Feature Extraction

**Before:**
```python
from ..features import extract_message_features
```

**After:**
```python
from ..utils.features import extract_message_features
```

### 5. Repository get_by_id

**Before:**
```python
# This won't work for composite primary keys
item = await repo.get_by_id(123)
```

**After:**
```python
# Works for any primary key structure
item = await repo.get_by_pk(chat_id=123, msg_id=456)
```

### 6. Using New Schemas

**For API Endpoints:**
```python
from ..schemas import (
    ChatResponse,
    GroupSettingsUpdate,
    MessageResponse,
    PaginatedResponse
)

@app.get("/chats/{chat_id}", response_model=ChatResponse)
async def get_chat(chat_id: int):
    # ... fetch chat ...
    return ChatResponse.model_validate(chat)
```

**For Request Validation:**
```python
from ..schemas import GroupSettingsUpdate

@app.put("/chats/{chat_id}/settings")
async def update_settings(
    chat_id: int,
    settings: GroupSettingsUpdate  # Automatic validation
):
    # settings is validated Pydantic model
```

### 7. Health Check Endpoints

**New Endpoints Available:**
- `GET /health` - Basic health
- `GET /health/live` - Liveness probe (K8s)
- `GET /health/ready` - Readiness probe with DB/Redis/Celery checks
- `GET /health/startup` - Startup probe
- `GET /health/stats` - Detailed system statistics
- `GET /metrics` - Prometheus metrics

### 8. Request Tracing

**Automatic for all requests:**
- Every request gets a unique `X-Request-ID` header
- ID is bound to logger context automatically
- ID is returned in response headers

**In your code:**
```python
# Request ID is automatically in logger context
logger.info("Processing request")  # Will include request_id
```

### 9. API Versioning

**When creating new endpoints:**
```python
# Put new endpoints in versioned routers
# tgstats/web/routers/v1.py

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["v1"])

@router.get("/my-endpoint")
async def my_endpoint():
    return {"version": "v1"}
```

## 📝 Configuration Validation

**Your .env file will now be validated at startup:**

```bash
# These will be checked:
MODE=polling  # Must be 'polling' or 'webhook'
LOG_LEVEL=INFO  # Must be valid log level
ENVIRONMENT=production  # Must be valid environment
DB_POOL_SIZE=10  # Must be positive, max 50
```

**If validation fails, you'll get a clear error message at startup.**

## 🧪 Testing Changes

**For Unit Tests:**
```python
from tgstats.repositories.factory import RepositoryFactory
from tgstats.services.base import BaseService

async def test_my_service():
    # Create factory with test session
    factory = RepositoryFactory(test_session)
    
    # Inject into service
    service = MyService(test_session, factory)
    
    # Test service methods
    result = await service.do_something()
    assert result is not None
```

## 📊 Monitoring Improvements

**Health Checks:**
```bash
# Check if bot is ready
curl http://localhost:8000/health/ready

# Get detailed stats
curl http://localhost:8000/health/stats

# Prometheus metrics
curl http://localhost:8000/metrics
```

**Request Tracing:**
```bash
# Send request with custom request ID
curl -H "X-Request-ID: my-trace-123" http://localhost:8000/api/v1/endpoint

# Check response headers for request ID
```

## 🔍 Common Patterns

### Creating a New Service

```python
from sqlalchemy.ext.asyncio import AsyncSession
from ..services.base import BaseService
from ..repositories.factory import RepositoryFactory

class NewService(BaseService):
    """Service for new feature."""
    
    def __init__(
        self, 
        session: AsyncSession,
        repo_factory: RepositoryFactory = None
    ):
        super().__init__(session, repo_factory)
    
    async def do_work(self):
        # Access repositories
        chat = await self.repos.chat.get_by_pk(chat_id=123)
        
        # Do work
        # ...
        
        # Commit transaction
        await self.commit()
        
        # Log result
        self.logger.info("Work completed", chat_id=123)
```

### Creating a New Repository

```python
from ..repositories.base import BaseRepository
from ..models import MyModel

class MyRepository(BaseRepository[MyModel]):
    """Repository for MyModel."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(MyModel, session)
    
    async def custom_query(self, param: str):
        result = await self.session.execute(
            select(MyModel).where(MyModel.field == param)
        )
        return result.scalar_one_or_none()
```

## 🚨 What NOT to Do

1. ❌ Don't create new `ValidationError` classes
2. ❌ Don't use `logging.getLogger()` - use `structlog.get_logger()`
3. ❌ Don't add `commit()`/`rollback()` to repositories
4. ❌ Don't use hardcoded imports of features module
5. ❌ Don't create non-versioned API endpoints

## ✅ What TO Do

1. ✅ Use `BaseService` for new services
2. ✅ Use `RepositoryFactory` for dependency injection
3. ✅ Import from `..core.exceptions`
4. ✅ Use `structlog` for all logging
5. ✅ Add new endpoints to versioned routers
6. ✅ Use new schema classes for API contracts
7. ✅ Leverage request tracing for debugging

## 🎯 Next Steps

1. Review the changes in [CODE_IMPROVEMENTS_APPLIED.md](CODE_IMPROVEMENTS_APPLIED.md)
2. Update your services to use `BaseService` (optional but recommended)
3. Start using the new schema classes for type safety
4. Monitor health check endpoints in production
5. Use request IDs for tracing issues

## 📞 Questions?

Check the documentation:
- [Architecture Diagram](ARCHITECTURE_DIAGRAM.md)
- [Quick Reference](QUICK_REFERENCE.md)
- [Code Improvements Applied](CODE_IMPROVEMENTS_APPLIED.md)

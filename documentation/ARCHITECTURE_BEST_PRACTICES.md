# Architecture Best Practices & Improvements

## Overview

This document provides architectural guidance and best practices for the TG Stats Bot codebase. It serves as a reference for developers to understand the design decisions and patterns used throughout the project.

## Core Architecture Principles

### 1. Layered Architecture

The application follows a strict layered architecture:

```
┌─────────────────────────────────────────┐
│         Presentation Layer              │
│  (Handlers, Web API, Templates)         │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│         Service Layer                   │
│  (Business Logic, Orchestration)        │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│         Repository Layer                │
│  (Data Access, Queries)                 │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│         Data Layer                      │
│  (Database, Models)                     │
└─────────────────────────────────────────┘
```

**Benefits**:
- Clear separation of concerns
- Easy to test each layer independently
- Changes in one layer don't affect others
- Easy to understand and maintain

### 2. Dependency Injection

Sessions are injected via decorators and constructors:

```python
# Handler level - decorator injection
@with_db_session
async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession):
    service = ChatService(session)
    await service.setup_chat(chat_id)
    await session.commit()  # Auto-committed by decorator

# Service level - constructor injection
class ChatService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.chat_repo = ChatRepository(session)
        self.settings_repo = GroupSettingsRepository(session)

# Repository level - constructor injection
class ChatRepository(BaseRepository[Chat]):
    def __init__(self, session: AsyncSession):
        super().__init__(Chat, session)
```

**Benefits**:
- Easy to test with mock sessions
- No global state
- Clear dependencies
- Prevents session leaks

### 3. Repository Pattern

All data access goes through repositories:

```python
# Base repository with common operations
class BaseRepository(Generic[ModelType]):
    async def get_by_pk(self, **pk_values) -> Optional[ModelType]:
        ...
    
    async def create(self, **kwargs) -> ModelType:
        ...
    
    async def update(self, instance: ModelType, **kwargs) -> ModelType:
        ...

# Specific repositories extend base
class ChatRepository(BaseRepository[Chat]):
    async def get_by_chat_id(self, chat_id: int) -> Optional[Chat]:
        result = await self.session.execute(
            select(Chat).where(Chat.chat_id == chat_id)
        )
        return result.scalar_one_or_none()
```

**Benefits**:
- Single source of truth for queries
- Easy to optimize queries in one place
- Testable with mocks
- Type-safe with generics

### 4. Custom Exceptions

Hierarchy of exceptions for better error handling:

```python
# Base exception
class TgStatsError(Exception):
    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

# Category exceptions
class DatabaseError(TgStatsError): pass
class ValidationError(TgStatsError): pass
class AuthorizationError(TgStatsError): pass

# Specific exceptions
class ChatNotSetupError(TgStatsError): pass
class RateLimitExceededError(TgStatsError): pass
```

**Benefits**:
- Easy to catch specific error types
- Better error messages with context
- Clearer intent in code
- Better logging

## Design Patterns

### 1. Decorator Pattern

Decorators for cross-cutting concerns:

```python
# Session management
@with_db_session
async def handler(update, context, session):
    ...

# Authorization
@require_admin
async def admin_handler(update, context, session):
    ...

# Logging
@log_handler_call
async def tracked_handler(update, context, session):
    ...

# Stack decorators for composition
@with_db_session
@require_admin
@group_only
async def setup_command(update, context, session):
    ...
```

### 2. Factory Pattern

Service factory for consistent service creation:

```python
class ServiceFactory:
    """Factory for creating service instances with proper dependencies."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    def create_chat_service(self) -> ChatService:
        return ChatService(self.session)
    
    def create_user_service(self) -> UserService:
        return UserService(self.session)
    
    def create_message_service(self) -> MessageService:
        return MessageService(self.session)
```

### 3. Unit of Work Pattern

For complex transactions across multiple repositories:

```python
class UnitOfWork:
    """Manages a transaction across multiple repositories."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.chats = ChatRepository(session)
        self.users = UserRepository(session)
        self.messages = MessageRepository(session)
    
    async def commit(self):
        await self.session.commit()
    
    async def rollback(self):
        await self.session.rollback()

# Usage
async with async_session() as session:
    uow = UnitOfWork(session)
    try:
        chat = await uow.chats.create(...)
        user = await uow.users.create(...)
        await uow.messages.create(...)
        await uow.commit()
    except:
        await uow.rollback()
        raise
```

### 4. Plugin Architecture

Hot-reloadable plugin system:

```python
# Base plugin interface
class BasePlugin(ABC):
    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        ...
    
    @abstractmethod
    async def initialize(self, app: Application) -> None:
        ...

# Specific plugin types
class CommandPlugin(BasePlugin):
    """Plugins that add bot commands."""
    ...

class StatisticsPlugin(BasePlugin):
    """Plugins that calculate statistics."""
    ...

# Plugin manager handles discovery and loading
plugin_manager = PluginManager()
await plugin_manager.load_all()
await plugin_manager.initialize_all(app)
```

## Security Best Practices

### 1. Input Validation

Always validate and sanitize inputs:

```python
# Query parameter validation
if not is_safe_sql_input(value):
    raise HTTPException(400, "Invalid input detected")

# XSS prevention
if not is_safe_web_input(value):
    raise HTTPException(400, "Invalid input detected")

# Pydantic validation for API
class ChatSettingsUpdate(BaseModel):
    store_text: bool = Field(...)
    timezone: str = Field(..., pattern=r"^[A-Za-z_]+/[A-Za-z_]+$")
```

### 2. Rate Limiting

Protect APIs from abuse:

```python
# Sliding window rate limiting
limiter = APIRateLimiter(
    requests_per_minute=60,
    requests_per_hour=1000,
    burst_size=10
)

# Middleware integration
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    await limiter.check_rate_limit(request)
    return await call_next(request)
```

### 3. Authentication

Token-based authentication:

```python
# Environment-based configuration
ADMIN_API_TOKEN=<strong-secret-token>

# Validation
async def verify_admin_token(x_admin_token: Optional[str] = Header(None)):
    if settings.admin_api_token:
        if not x_admin_token or x_admin_token != settings.admin_api_token:
            raise HTTPException(401, "Invalid or missing admin token")

# Usage
@app.get("/api/admin/stats", dependencies=[Depends(verify_admin_token)])
async def get_stats():
    ...
```

### 4. SQL Injection Prevention

Always use parameterized queries:

```python
# ✅ GOOD - Parameterized query
result = await session.execute(
    select(User).where(User.user_id == user_id)
)

# ✅ GOOD - ORM with parameters
result = await session.execute(
    text("SELECT * FROM users WHERE user_id = :uid"),
    {"uid": user_id}
)

# ❌ BAD - String concatenation
query = f"SELECT * FROM users WHERE user_id = {user_id}"  # NEVER DO THIS!
```

## Performance Best Practices

### 1. Database Connections

Use connection pooling efficiently:

```python
# Configuration
DATABASE_URL=postgresql+psycopg://...
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30

# Engine with connection pool
engine = create_async_engine(
    database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_pre_ping=True,  # Verify connections before use
)
```

### 2. Query Optimization

Use indexes and optimize queries:

```python
# Add indexes for common queries
Index("idx_messages_chat_date", Message.chat_id, Message.date)
Index("idx_messages_user", Message.user_id)

# Use select_related to avoid N+1 queries
result = await session.execute(
    select(Message)
    .options(selectinload(Message.user))
    .where(Message.chat_id == chat_id)
)

# Pagination for large results
result = await session.execute(
    select(Message)
    .where(Message.chat_id == chat_id)
    .order_by(Message.date.desc())
    .limit(100)
    .offset(page * 100)
)
```

### 3. Caching

Cache expensive operations:

```python
# Configuration
ENABLE_CACHE=true
CACHE_TTL=300

# Implementation
from functools import lru_cache

@lru_cache(maxsize=128)
def get_timezone(timezone_str: str) -> ZoneInfo:
    """Cache timezone objects."""
    return ZoneInfo(timezone_str)

# Redis-backed caching for distributed systems
async def get_cached_stats(chat_id: int, redis_client):
    cache_key = f"stats:{chat_id}"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    
    stats = await calculate_stats(chat_id)
    await redis_client.setex(cache_key, 300, json.dumps(stats))
    return stats
```

### 4. Async Operations

Always use async for I/O operations:

```python
# ✅ GOOD - Async all the way
async def handle_message(update: Update, context, session: AsyncSession):
    user = await get_or_create_user(session, update.effective_user)
    chat = await get_or_create_chat(session, update.effective_chat)
    message = await store_message(session, update.message)
    await session.commit()

# ❌ BAD - Mixing sync and async
async def handle_message(update: Update, context, session: AsyncSession):
    user = get_or_create_user(session, update.effective_user)  # Blocking!
    ...
```

## Testing Best Practices

### 1. Test Structure

Organize tests by component:

```
tests/
├── conftest.py              # Fixtures
├── test_repositories.py     # Repository tests
├── test_services.py         # Service tests
├── test_handlers.py         # Handler tests
├── test_api_*.py           # API tests
└── test_plugins.py         # Plugin tests
```

### 2. Fixtures

Use pytest fixtures for common setup:

```python
@pytest.fixture
async def async_session():
    """Provide test database session."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session_maker() as session:
        yield session
    
    await engine.dispose()

@pytest.fixture
async def sample_chat(async_session):
    """Create sample chat for testing."""
    repo = ChatRepository(async_session)
    chat = await repo.create(
        chat_id=-1001234567890,
        title="Test Chat",
        type="supergroup"
    )
    await async_session.commit()
    return chat
```

### 3. Test Coverage

Aim for high coverage of critical paths:

```python
# Test happy path
async def test_create_chat_success(async_session):
    service = ChatService(async_session)
    chat = await service.setup_chat(-1001234567890, "Test")
    assert chat.chat_id == -1001234567890

# Test error cases
async def test_create_chat_duplicate(async_session):
    service = ChatService(async_session)
    await service.setup_chat(-1001234567890, "Test")
    
    with pytest.raises(DuplicateRecordError):
        await service.setup_chat(-1001234567890, "Test")

# Test edge cases
async def test_create_chat_invalid_id(async_session):
    service = ChatService(async_session)
    with pytest.raises(ValidationError):
        await service.setup_chat(0, "Test")
```

## Monitoring & Observability

### 1. Structured Logging

Use structlog for consistent logging:

```python
import structlog
logger = structlog.get_logger(__name__)

# Log with context
logger.info(
    "user_action",
    user_id=user.user_id,
    chat_id=chat.chat_id,
    action="join",
    timestamp=datetime.now()
)

# Log errors with context
try:
    await risky_operation()
except Exception as e:
    logger.error(
        "operation_failed",
        error=str(e),
        user_id=user_id,
        exc_info=True
    )
```

### 2. Request Tracing

Add request IDs for distributed tracing:

```python
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    
    with structlog.contextvars.bound_contextvars(request_id=request_id):
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

### 3. Metrics

Track key metrics:

```python
from prometheus_client import Counter, Histogram

# Define metrics
requests_total = Counter('requests_total', 'Total requests', ['method', 'endpoint'])
request_duration = Histogram('request_duration_seconds', 'Request duration')

# Use in code
@app.middleware("http")
async def track_metrics(request: Request, call_next):
    requests_total.labels(method=request.method, endpoint=request.url.path).inc()
    
    with request_duration.time():
        response = await call_next(request)
    
    return response
```

## Deployment Best Practices

### 1. Configuration Management

Use environment variables:

```bash
# .env file
BOT_TOKEN=your_token_here
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
ADMIN_API_TOKEN=strong_secret_token
LOG_LEVEL=INFO
ENVIRONMENT=production
```

### 2. Health Checks

Implement health check endpoints:

```python
@app.get("/healthz")
async def health_check():
    """Health check for load balancers."""
    return {"status": "healthy"}

@app.get("/readyz")
async def readiness_check(session: AsyncSession = Depends(get_session)):
    """Readiness check including database."""
    try:
        await session.execute(text("SELECT 1"))
        return {"status": "ready"}
    except:
        raise HTTPException(503, "Database not ready")
```

### 3. Graceful Shutdown

Handle shutdown gracefully:

```python
async def shutdown_handler():
    """Cleanup on shutdown."""
    logger.info("Shutting down gracefully...")
    
    # Stop accepting new requests
    await app.shutdown()
    
    # Close database connections
    await engine.dispose()
    
    # Close Redis connections
    await redis.close()
    
    logger.info("Shutdown complete")

# Register handler
signal.signal(signal.SIGTERM, lambda s, f: asyncio.create_task(shutdown_handler()))
```

## Conclusion

Following these architectural patterns and best practices ensures:
- **Maintainability**: Easy to understand and modify
- **Scalability**: Can grow with demand
- **Reliability**: Handles errors gracefully
- **Security**: Protected against common vulnerabilities
- **Testability**: Easy to test at all levels
- **Performance**: Efficient use of resources

For questions or suggestions, refer to the development team or open an issue in the repository.

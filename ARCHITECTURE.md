# Architecture Overview

This document provides an overview of the Telegram Stats Bot architecture, design decisions, and code organization.

## Table of Contents

- [High-Level Architecture](#high-level-architecture)
- [Directory Structure](#directory-structure)
- [Design Patterns](#design-patterns)
- [Key Components](#key-components)
- [Data Flow](#data-flow)
- [Configuration Management](#configuration-management)
- [Error Handling Strategy](#error-handling-strategy)
- [Testing Strategy](#testing-strategy)

## High-Level Architecture

The bot follows a layered architecture pattern:

```
┌─────────────────────────────────────────────┐
│           Telegram Bot Layer                │
│  (Handlers for commands, messages, etc.)    │
└───────────────┬─────────────────────────────┘
                │
┌───────────────▼─────────────────────────────┐
│          Service Layer                      │
│  (Business logic, orchestration)            │
└───────────────┬─────────────────────────────┘
                │
┌───────────────▼─────────────────────────────┐
│        Repository Layer                     │
│  (Data access, database operations)         │
└───────────────┬─────────────────────────────┘
                │
┌───────────────▼─────────────────────────────┐
│          Database Layer                     │
│  (PostgreSQL/TimescaleDB)                   │
└─────────────────────────────────────────────┘
```

### Additional Components

- **FastAPI Web Layer**: REST API for analytics and webhook endpoint
- **Celery Workers**: Background tasks for data aggregation and maintenance
- **Redis**: Task queue and caching backend

## Directory Structure

```
tgstats/
├── core/               # Core functionality
│   ├── config.py       # Configuration with validation
│   ├── constants.py    # Application constants
│   └── exceptions.py   # Custom exception types
├── handlers/           # Telegram update handlers
│   ├── commands.py     # Bot command handlers
│   ├── messages.py     # Message handlers
│   ├── reactions.py    # Reaction handlers
│   └── members.py      # Member update handlers
├── services/           # Business logic layer
│   ├── chat_service.py
│   ├── user_service.py
│   ├── message_service.py
│   └── reaction_service.py
├── repositories/       # Data access layer
│   ├── base.py         # Generic repository base class
│   ├── chat_repository.py
│   ├── user_repository.py
│   └── message_repository.py
├── models.py           # SQLAlchemy ORM models
├── schemas/            # Pydantic schemas for API
│   ├── api.py          # API request/response models
│   └── commands.py     # Command argument models
├── utils/              # Utility functions
│   ├── logging.py      # Structured logging setup
│   ├── validation.py   # Input validation
│   ├── sanitizer.py    # Input sanitization
│   ├── cache.py        # Caching utilities
│   ├── rate_limiter.py # Rate limiting
│   └── metrics.py      # Metrics collection
├── web/                # FastAPI application
│   ├── app.py          # Main FastAPI app
│   ├── auth.py         # Authentication middleware
│   └── routers/        # API route handlers
├── db.py               # Database session management
├── bot_main.py         # Bot entry point
├── celery_app.py       # Celery app configuration
└── celery_tasks.py     # Background task definitions
```

## Design Patterns

### 1. Repository Pattern

We use the repository pattern to abstract database operations:

```python
class BaseRepository(Generic[ModelType]):
    """Generic CRUD operations for any model."""
    async def get_by_id(self, id: int) -> Optional[ModelType]: ...
    async def create(self, **kwargs) -> ModelType: ...
    async def update(self, instance: ModelType, **kwargs) -> ModelType: ...
```

**Benefits:**
- Separates data access from business logic
- Makes testing easier (can mock repositories)
- Provides consistent interface for database operations

### 2. Service Layer Pattern

Services contain business logic and orchestrate multiple repositories:

```python
class MessageService:
    """Process and store Telegram messages."""
    def __init__(self, session: AsyncSession):
        self.message_repo = MessageRepository(session)
        self.chat_service = ChatService(session)
        self.user_service = UserService(session)
```

**Benefits:**
- Encapsulates complex business logic
- Can coordinate multiple repositories
- Easier to test than handlers directly

### 3. Dependency Injection

We use constructor-based dependency injection:

```python
# Handler receives session, creates service
async with async_session() as session:
    service = MessageService(session)
    await service.process_message(message)
```

**Benefits:**
- Loose coupling between components
- Easy to mock dependencies in tests
- Clear dependencies in constructors

### 4. Lazy Initialization

Database engines and config are initialized lazily to avoid circular imports:

```python
def _get_engine() -> AsyncEngine:
    """Get or create engine on first access."""
    global _engine
    if _engine is None:
        from .config import settings
        _engine = create_async_engine(settings.database_url)
    return _engine
```

## Key Components

### Configuration (`core/config.py`)

- Uses Pydantic for validation
- Loads from environment variables or .env file
- Includes range validation, format validation
- Type-safe with Literal types for enums

### Database Session Management (`db.py`)

- Lazy initialization to avoid circular imports
- Separate engines for async (bot) and sync (migrations, Celery)
- Connection pooling with configurable sizes
- Backward compatibility for existing code

### Error Handling (`core/exceptions.py`)

Custom exception hierarchy:

```
TgStatsError (base)
├── DatabaseError
├── ValidationError
├── AuthorizationError
│   └── InsufficientPermissionsError
├── NotFoundError
├── ConfigurationError
└── ChatNotSetupError
```

### Logging (`utils/logging.py`)

- Structured logging with `structlog`
- JSON format for production, human-readable for development
- Contextual information (chat_id, user_id, etc.)
- Configurable log levels per component

## Data Flow

### Message Processing

1. Telegram sends update → Handler receives it
2. Handler creates service with database session
3. Service orchestrates:
   - Upsert chat (via ChatService)
   - Upsert user (via UserService)
   - Extract message features
   - Store message (via MessageRepository)
4. Commit transaction
5. Log success/failure

### API Request

1. FastAPI receives HTTP request
2. Authentication middleware validates token
3. Pydantic validates request body
4. Handler gets database session (dependency injection)
5. Handler calls service methods
6. Service queries repositories
7. Response serialized via Pydantic models

### Background Tasks

1. Celery beat triggers periodic task
2. Task uses sync session (Celery is sync)
3. Task refreshes materialized views (PostgreSQL) or aggregates (TimescaleDB)
4. Task reports success/failure metrics

## Configuration Management

### Environment Variables

All configuration comes from environment variables:

```bash
# Required
BOT_TOKEN=xxx
DATABASE_URL=postgresql://...

# Optional (with defaults)
MODE=polling
LOG_LEVEL=INFO
REDIS_URL=redis://localhost:6379/0
```

### Validation

Pydantic validates on startup:

```python
class Settings(BaseSettings):
    bot_token: str = Field(..., description="Required bot token")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    
    @model_validator(mode='after')
    def validate_webhook_mode(self):
        if self.mode == "webhook" and not self.webhook_url:
            raise ConfigurationError("webhook_url required in webhook mode")
```

### Configuration Categories

1. **Core Settings**: bot_token, database_url, mode
2. **Logging**: log levels, file rotation settings
3. **Performance**: pool sizes, timeouts, cache TTL
4. **Security**: rate limits, max request size, CORS
5. **Monitoring**: metrics, Sentry DSN

## Error Handling Strategy

### Three-Tier Error Handling

1. **Expected Errors**: Use custom exceptions with user-friendly messages
   ```python
   raise ValidationError("Invalid chat ID format")
   ```

2. **Recoverable Errors**: Log and handle gracefully
   ```python
   except DatabaseError as e:
       logger.error("Database error", error=str(e))
       await session.rollback()
   ```

3. **Fatal Errors**: Log and re-raise
   ```python
   except Exception as e:
       logger.error("Unexpected error", exc_info=True)
       raise
   ```

### Error Context

Always include relevant context in logs:

```python
logger.error(
    "Error processing message",
    chat_id=message.chat.id,
    user_id=message.from_user.id,
    msg_id=message.message_id,
    error_type=type(e).__name__,
    error=str(e)
)
```

## Testing Strategy

### Unit Tests

- Test business logic in services
- Mock repositories
- Test validation functions
- Test utility functions

### Integration Tests

- Test handlers with test database
- Test API endpoints
- Test database migrations

### Test Organization

```
tests/
├── conftest.py         # Shared fixtures
├── test_services/      # Service layer tests
├── test_repositories/  # Repository tests
├── test_handlers/      # Handler tests
└── test_api/           # API endpoint tests
```

## Security Considerations

1. **SQL Injection**: Prevented by SQLAlchemy parameterized queries
2. **XSS**: Output encoding in templates, sanitization layer as defense-in-depth
3. **Command Injection**: Input sanitization for shell commands (if any)
4. **Rate Limiting**: Per-user rate limits on API and bot commands
5. **Authentication**: Token-based auth for API endpoints
6. **Input Validation**: Pydantic models + custom validators

## Performance Optimizations

1. **Database Connection Pooling**: Configurable pool sizes
2. **Async Operations**: All I/O operations are async
3. **Caching**: Redis cache for frequently accessed data
4. **Query Optimization**: Indexes on frequently queried columns
5. **Batch Processing**: Celery for background aggregations
6. **TimescaleDB**: Continuous aggregates for real-time analytics

## Future Improvements

1. Add GraphQL API alongside REST
2. Implement event sourcing for audit trail
3. Add more comprehensive metrics and monitoring
4. Implement feature flags for gradual rollouts
5. Add distributed tracing (OpenTelemetry)
6. Implement CQRS pattern for read-heavy operations

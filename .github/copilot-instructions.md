# Copilot Instructions for TG Stats Bot

## Architecture Overview

This is a **Telegram analytics bot** with TimescaleDB/PostgreSQL backend, FastAPI web API, and a plugin system. The codebase follows a **clean layered architecture**:

```
Handlers → Services → Repositories → Database
```

- **Handlers** (`tgstats/handlers/`): Telegram update handlers with decorators
- **Services** (`tgstats/services/`): Business logic layer  
- **Repositories** (`tgstats/repositories/`): Data access layer with `BaseRepository` pattern
- **Models** (`tgstats/models.py`): SQLAlchemy 2.x ORM models

### Key Components

1. **Bot**: `tgstats/bot_main.py` - Main entry point with handler registration
2. **Web API**: `tgstats/web/` - FastAPI endpoints with admin token auth
3. **Celery**: `tgstats/celery_tasks.py` - Background tasks for materialized view refresh
4. **Plugins**: `tgstats/plugins/` - Hot-reloadable extension system

## Critical Patterns

### 1. Database Session Management

**Always use `@with_db_session` decorator** for handlers:

```python
from tgstats.utils.decorators import with_db_session

@with_db_session
async def my_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session: AsyncSession):
    # session is auto-provided, committed, and rolled back on error
```

For services/repositories, pass `session` explicitly through constructor or method parameters.

### 2. Model Attribute Names (CRITICAL)

**DO NOT confuse these common model attributes:**

```python
# Message model
message.date          # NOT created_at
message.text_raw      # NOT text
message.msg_id        # NOT id (id is internal DB primary key)

# User model  
user.user_id          # NOT telegram_id
user.username         # Optional[str]
```

### 3. Repository Pattern

All repositories inherit from `BaseRepository[ModelType]`:

```python
class ChatRepository(BaseRepository[Chat]):
    def __init__(self, session: AsyncSession):
        super().__init__(Chat, session)
    
    async def get_by_chat_id(self, chat_id: int) -> Optional[Chat]:
        result = await self.session.execute(
            select(Chat).where(Chat.chat_id == chat_id)
        )
        return result.scalar_one_or_none()
```

**Repositories are instantiated with a session** in services, not stored as singletons.

### 4. Service Layer

Services coordinate repositories and contain business logic:

```python
class ChatService:
    def __init__(self, session: AsyncSession):
        self.chat_repo = ChatRepository(session)
        self.settings_repo = GroupSettingsRepository(session)
```

Services are instantiated per-request in handlers.

### 5. Plugin System

Plugins live in `tgstats/plugins/` with:
- Base classes: `CommandPlugin`, `StatisticsPlugin` from `base.py`
- Enable/disable: Prefix with `_` to disable (e.g., `_word_cloud.py`)
- Configuration: `plugins/plugins.yaml` for per-plugin settings
- **Hot reload**: Automatically reloads on file changes (no restart needed)

Plugin structure:
```python
class MyPlugin(CommandPlugin):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(name="my_plugin", version="1.0", ...)
    
    async def initialize(self, app: Application) -> None:
        app.add_handler(CommandHandler("mycommand", self.handle_command))
```

## Development Workflow

### Running Locally

```bash
./start_bot.sh        # Starts PostgreSQL, Redis, migrations, bot, Celery
```

**This script manages everything** - don't run services manually unless debugging specific components.

### Database Migrations

```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

Migrations live in `migrations/versions/`. TimescaleDB-specific migrations check for extension availability before creating hypertables.

### Testing

```bash
pytest tests/          # Unit tests with in-memory SQLite
```

Tests use fixtures from `tests/conftest.py` that create isolated async sessions.

### Seeding Data

```bash
python scripts/seed_database.py   # Generates realistic test data
```

## Configuration

Settings use **Pydantic Settings** in `tgstats/core/config.py`:
- Environment variables from `.env` file
- Type-safe with validation
- Access via `from tgstats.config import settings`

## TimescaleDB vs PostgreSQL

The system **auto-detects TimescaleDB** availability:

- **With TimescaleDB**: Uses hypertables + continuous aggregates
- **Without TimescaleDB**: Uses materialized views refreshed by Celery

Write code agnostic to the backend - check `migrations/004_create_aggregates.py` for the pattern.

## Common Decorators

```python
@with_db_session          # Provides session, handles commit/rollback
@require_admin            # Checks if user is admin (use after @with_db_session)  
@group_only               # Ensures command is in group chat
@log_handler_call         # Logs handler entry/exit
```

Stack them: `@with_db_session` → `@require_admin` → handler function.

## Web API

FastAPI endpoints in `tgstats/web/`:
- **Auth**: `X-Admin-Token` header (optional if `ADMIN_API_TOKEN` not set)
- **Timezone-aware**: Uses group settings for timezone conversion
- **Sync sessions**: Use `get_sync_session()` for FastAPI endpoints (not async sessions)

## Logging

Uses **structlog** for structured logging:

```python
import structlog
logger = structlog.get_logger(__name__)

logger.info("event_name", key1=value1, key2=value2)
```

Configuration in `tgstats/utils/logging.py`. Logs to `logs/tgstats.log` by default (JSON format).

## Deployment

- **Docker**: Use `docker-compose.yml` (includes TimescaleDB, Redis, Celery)
- **SystemD**: `setup_systemd.sh` for production Linux servers
- **Supervisor**: `setup_supervisor.sh` as alternative
- **K8s**: See `k8s/deployment.yaml`

## Documentation

Extensive docs in `documentation/`:
- `ARCHITECTURE_DIAGRAM.md` - Visual architecture overview
- `PLUGIN_SYSTEM_V2.md` - Plugin development guide  
- `STEP2_SUMMARY.md` - TimescaleDB + API implementation details
- `QUICK_REFERENCE.md` - Common operations reference

## Gotchas

1. **Never use blocking DB calls** - always use async sessions with SQLAlchemy 2.x
2. **Message IDs are composite**: `(chat_id, msg_id)` - not just `id`
3. **Plugin hot reload**: File modifications auto-reload, but YAML changes need manual trigger
4. **Celery beat**: Required for PostgreSQL mode (materialized view refresh)
5. **Timezone handling**: Always use `zoneinfo` for timezone conversion, never naive datetimes

## Code Style

- **Line length**: 100 characters (Black/Ruff configured)
- **Python**: 3.12+ required
- **Type hints**: Use throughout (checked implicitly)
- **Import order**: Standard lib → third-party → local (isort profile: black)

# System Architecture Overview

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Telegram Bot API                          │
└────────────────┬───────────────────────────────────┬────────────┘
                 │                                   │
                 ▼                                   ▼
┌────────────────────────────┐      ┌───────────────────────────────┐
│     Bot (Polling Mode)     │      │   FastAPI Web (Webhook Mode)  │
│   telegram.ext.Application │      │     + Analytics API           │
└──────────┬─────────────────┘      └───────────┬───────────────────┘
           │                                    │
           │  ┌─────────────────────────────────┘
           │  │
           ▼  ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Handler Layer                            │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐   │
│  │   Commands   │  │   Messages   │  │   Reactions/Members │   │
│  │  /setup etc  │  │   Text/Media │  │   Events & Changes  │   │
│  └──────────────┘  └──────────────┘  └─────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Service Layer                            │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐   │
│  │ ChatService  │  │UserService   │  │  MessageService     │   │
│  │              │  │              │  │  ReactionService    │   │
│  │ • Setup chat │  │• Get/create  │  │  • Store messages   │   │
│  │ • Settings   │  │  users       │  │  • Store reactions  │   │
│  └──────────────┘  └──────────────┘  └─────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Repository Layer                            │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐   │
│  │ChatRepository│  │UserRepository│  │  MessageRepository  │   │
│  │              │  │              │  │  ReactionRepository │   │
│  │ • CRUD ops   │  │• CRUD ops    │  │  • CRUD ops         │   │
│  │ • Queries    │  │• Queries     │  │  • Queries          │   │
│  └──────────────┘  └──────────────┘  └─────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Database Layer                           │
│                 PostgreSQL / TimescaleDB                         │
│  ┌──────────┐  ┌────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │  Chats   │  │ Users  │  │ Messages │  │  Aggregates      │  │
│  │  Settings│  │Members │  │Reactions │  │  (TimescaleDB)   │  │
│  └──────────┘  └────────┘  └──────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      Background Processing                       │
│  ┌──────────────┐  ┌──────────────────────────────────────────┐ │
│  │    Celery    │  │             Redis                         │ │
│  │   Workers    │  │          (Task Queue)                     │ │
│  │              │  │                                           │ │
│  │ • Refresh MVs│  │  • Job scheduling                         │ │
│  │ • Retention  │  │  • Rate limiting                          │ │
│  └──────────────┘  └──────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Detailed Component Architecture

### 1. Bot Layer

**Files:**
- `tgstats/bot_main.py` - Main entry point
- `tgstats/handlers/` - Update handlers

**Responsibilities:**
- Receive Telegram updates (polling or webhook)
- Route updates to appropriate handlers
- Manage bot lifecycle and error handling

**Key Classes:**
- `Application` (python-telegram-bot)
- Handler functions decorated with `@with_db_session`

### 2. Handler Layer

**Files:**
- `tgstats/handlers/commands.py` - Command handlers (/setup, /settings, etc.)
- `tgstats/handlers/messages.py` - Message handlers
- `tgstats/handlers/reactions.py` - Reaction handlers
- `tgstats/handlers/members.py` - Member event handlers

**Responsibilities:**
- Process incoming Telegram updates
- Validate input and permissions
- Call appropriate services
- Format and send responses

**Patterns:**
```python
@with_db_session  # Provides database session
async def setup_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: AsyncSession  # Auto-injected
) -> None:
    services = ServiceFactory(session)
    await services.chat.setup_chat(chat.id)
```

### 3. Service Layer

**Files:**
- `tgstats/services/base.py` - Base service class
- `tgstats/services/chat_service.py` - Chat operations
- `tgstats/services/user_service.py` - User operations
- `tgstats/services/message_service.py` - Message operations
- `tgstats/services/reaction_service.py` - Reaction operations
- `tgstats/services/factory.py` - Service factory

**Responsibilities:**
- Business logic implementation
- Coordinate multiple repositories
- Transaction management
- Domain-specific operations

**Patterns:**
```python
class ChatService(BaseService):
    async def setup_chat(self, chat_id: int) -> GroupSettings:
        settings = await self.repos.settings.create_default(chat_id)
        await self.commit()
        return settings
```

### 4. Repository Layer

**Files:**
- `tgstats/repositories/base.py` - Base repository with CRUD operations
- `tgstats/repositories/chat_repository.py` - Chat data access
- `tgstats/repositories/user_repository.py` - User data access
- `tgstats/repositories/message_repository.py` - Message data access
- `tgstats/repositories/reaction_repository.py` - Reaction data access
- `tgstats/repositories/factory.py` - Repository factory

**Responsibilities:**
- Direct database access
- Query construction
- Data mapping (DB ↔ Models)

**Patterns:**
```python
class ChatRepository(BaseRepository[Chat]):
    async def get_by_chat_id(self, chat_id: int) -> Optional[Chat]:
        result = await self.session.execute(
            select(Chat).where(Chat.chat_id == chat_id)
        )
        return result.scalar_one_or_none()
```

### 5. Web API Layer

**Files:**
- `tgstats/web/app.py` - FastAPI application
- `tgstats/web/routers/chats.py` - Chat management endpoints
- `tgstats/web/routers/analytics.py` - Analytics endpoints
- `tgstats/web/routers/webhook.py` - Webhook endpoints
- `tgstats/web/query_utils.py` - Query builders
- `tgstats/web/date_utils.py` - Date/timezone utilities

**Endpoints:**
```
GET  /api/chats                          - List chats
GET  /api/chats/{id}/settings            - Chat settings
GET  /api/chats/{id}/summary             - Period summary
GET  /api/chats/{id}/timeseries          - Time series data
GET  /api/chats/{id}/heatmap             - Activity heatmap
GET  /api/chats/{id}/users               - User statistics
GET  /api/chats/{id}/retention/preview   - Retention preview
GET  /ui                                  - Web UI
POST /webhook                             - Telegram webhook
```

## Data Flow Examples

### Message Processing Flow

```
1. Telegram sends message → Bot receives update
                             │
2. handle_message() called ──┘
                             │
3. Extract message data ─────┘
                             │
4. MessageService.store() ───┘
                             │
5. MessageRepository.create()─┘
                             │
6. PostgreSQL INSERT ─────────┘
                             │
7. Auto-commit (decorator) ───┘
```

### Analytics Query Flow

```
1. GET /api/chats/123/timeseries?metric=messages
                             │
2. analytics.get_chat_timeseries()
                             │
3. get_group_tz(123) ────────┘
                             │
4. parse_period(dates, tz) ──┘
                             │
5. build_timeseries_query() ─┘
                             │
6. session.execute(query) ───┘
                             │
7. Transform to TimeseriesPoint[]
                             │
8. Return JSON response ─────┘
```

## Plugin System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Plugin Manager                           │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    Plugin Discovery                         │ │
│  │  • Scan tgstats/plugins/ directory                          │ │
│  │  • Skip files starting with '_'                             │ │
│  │  • Load plugin modules dynamically                          │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                   Plugin Initialization                     │ │
│  │  • Call plugin.initialize(app)                              │ │
│  │  • Register handlers/commands                               │ │
│  │  • Setup plugin dependencies                                │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                      Hot Reload                             │ │
│  │  • Watch plugin files for changes                           │ │
│  │  • Reload modified plugins                                  │ │
│  │  • Re-register handlers                                     │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘

                              │
           ┌──────────────────┼──────────────────┐
           ▼                  ▼                  ▼
   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
   │   Command    │   │  Statistics  │   │   Custom     │
   │   Plugin     │   │   Plugin     │   │   Plugin     │
   │              │   │              │   │              │
   │ • /mycommand │   │ • Engagement │   │ • Your       │
   │ • Handle cmd │   │ • Word cloud │   │   plugin     │
   └──────────────┘   └──────────────┘   └──────────────┘
```

## Database Schema

### Core Tables

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│   chats     │       │    users    │       │  messages   │
├─────────────┤       ├─────────────┤       ├─────────────┤
│ chat_id (PK)│       │ user_id (PK)│       │ chat_id (FK)│
│ title       │       │ username    │       │ msg_id      │
│ type        │       │ first_name  │       │ user_id (FK)│
│ is_forum    │       │ last_name   │       │ date        │
│ ...         │       │ is_bot      │       │ text_raw    │
└─────────────┘       │ ...         │       │ ...         │
                      └─────────────┘       └─────────────┘
        │                     │                     │
        │                     │                     │
        └─────────┬───────────┘                     │
                  │                                 │
                  ▼                                 │
          ┌───────────────┐                        │
          │  memberships  │                        │
          ├───────────────┤                        │
          │ chat_id (PK)  │                        │
          │ user_id (PK)  │                        │
          │ joined_at     │                        │
          │ left_at       │                        │
          │ status_current│                        │
          └───────────────┘                        │
                                                   │
                                                   ▼
                                           ┌──────────────┐
                                           │  reactions   │
                                           ├──────────────┤
                                           │ chat_id (FK) │
                                           │ msg_id (FK)  │
                                           │ user_id (FK) │
                                           │ reaction_type│
                                           │ ...          │
                                           └──────────────┘
```

### Aggregate Tables (TimescaleDB)

```
┌───────────────────┐       ┌──────────────────────┐
│   chat_daily      │       │  user_chat_daily     │
├───────────────────┤       ├──────────────────────┤
│ chat_id           │       │ user_id              │
│ day               │       │ chat_id              │
│ msg_cnt           │       │ day                  │
│ dau               │       │ msg_cnt              │
│ ...               │       │ ...                  │
└───────────────────┘       └──────────────────────┘

┌─────────────────────────┐
│ chat_hourly_heatmap     │
├─────────────────────────┤
│ chat_id                 │
│ hour_bucket             │
│ weekday                 │
│ hour                    │
│ msg_cnt                 │
│ ...                     │
└─────────────────────────┘
```

## Configuration Management

```
┌─────────────────────────────────────────────────────────────────┐
│                    Environment Variables                         │
│                         (.env file)                              │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Pydantic Settings                              │
│                 (tgstats/core/config.py)                         │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  • Type validation                                         │  │
│  │  • Default values                                          │  │
│  │  • Field validators                                        │  │
│  │  • Environment variable mapping                            │  │
│  └───────────────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                     settings singleton                           │
│              (used throughout application)                       │
└─────────────────────────────────────────────────────────────────┘
```

## Error Handling Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│                       Exception Hierarchy                        │
│                                                                  │
│                         TgStatsError                             │
│                              │                                   │
│      ┌───────────────────────┼───────────────────────┐          │
│      │                       │                       │          │
│ DatabaseError         ValidationError        AuthorizationError │
│      │                       │                       │          │
│ ┌────┴────┐            ┌────┴────┐            ┌────┴────┐      │
│ │ Record  │            │ Invalid │            │Insufficient│    │
│ │NotFound │            │  Input  │            │Permissions│     │
│ └─────────┘            └─────────┘            └──────────┘      │
└─────────────────────────────────────────────────────────────────┘

Handler Level:     Catch specific exceptions, reply to user
Service Level:     Raise domain exceptions with context
Repository Level:  Catch DB exceptions, wrap as DatabaseError
```

## Deployment Modes

### Polling Mode (Development/Small Scale)

```
┌──────────────────────────────────────────────────┐
│  Bot Process (bot_main.py)                       │
│  ┌──────────────────────────────────────────┐   │
│  │  Application.run_polling()               │   │
│  │  • Calls getUpdates() every N seconds    │   │
│  │  • Processes updates in handler queue    │   │
│  └──────────────────────────────────────────┘   │
└────────────────────┬─────────────────────────────┘
                     │
                     ▼
              ┌────────────┐
              │ PostgreSQL │
              └────────────┘
```

### Webhook Mode (Production)

```
┌────────────────────────────────────────────────────────┐
│  Nginx/Reverse Proxy                                   │
│  • SSL termination                                     │
│  • Rate limiting                                       │
└─────────────────┬──────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│  FastAPI Web Server (app.py)                            │
│  ┌──────────────────────────────────────────────────┐   │
│  │  POST /webhook - Receives Telegram updates       │   │
│  │  • Validates secret token                        │   │
│  │  • Processes update through application          │   │
│  │  • Returns 200 OK immediately                    │   │
│  └──────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────┐   │
│  │  API Endpoints (analytics, management)           │   │
│  └──────────────────────────────────────────────────┘   │
└────────────────┬────────────────────────────────────────┘
                 │
      ┌──────────┴──────────┐
      ▼                     ▼
┌────────────┐        ┌──────────┐
│ PostgreSQL │        │  Celery  │
└────────────┘        │ Workers  │
                      └──────────┘
```

## Security Layers

```
1. Input Validation
   ├─ Middleware (SQL injection, XSS prevention)
   ├─ Pydantic models (type validation)
   └─ Sanitizer utilities (specific checks)

2. Authentication
   ├─ Admin token (X-Admin-Token header)
   ├─ Bot admin checks (Telegram permissions)
   └─ Rate limiting (per user/IP)

3. Authorization
   ├─ Group admin checks
   ├─ Permission validation
   └─ Resource ownership checks

4. Data Protection
   ├─ Configurable text storage
   ├─ Data retention policies
   └─ Soft deletes
```

## Monitoring & Observability

```
┌─────────────────────────────────────────────────────────────────┐
│                       Structured Logging                         │
│                         (structlog)                              │
│  • Request ID tracing                                            │
│  • Contextual information (chat_id, user_id, etc.)               │
│  • JSON format for log aggregation                               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      Metrics Collection                          │
│                    (tgstats/utils/metrics.py)                    │
│  • Command usage counters                                        │
│  • Processing time tracking                                      │
│  • Error rate monitoring                                         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      Health Checks                               │
│  • GET /healthz - Liveness probe                                 │
│  • Database connection check                                     │
│  • Bot status check                                              │
└─────────────────────────────────────────────────────────────────┘
```

## Summary

This architecture provides:

✅ **Clear Separation of Concerns** - Each layer has distinct responsibilities
✅ **Testability** - Layers can be tested independently
✅ **Scalability** - Can scale horizontally with webhook mode
✅ **Maintainability** - Well-organized codebase with clear patterns
✅ **Flexibility** - Plugin system for extensibility
✅ **Reliability** - Proper error handling and monitoring
✅ **Performance** - Optimized with caching, aggregates, and async processing

The layered architecture ensures that changes in one layer don't ripple through the entire system, making the codebase easier to evolve and maintain over time.

# Telegram Bot Architecture - Visual Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         TELEGRAM API                             │
│                      (Updates & Messages)                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BOT MAIN (bot_main.py)                      │
│                    • Application setup                           │
│                    • Handler registration                        │
│                    • Logging configuration                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                        HANDLERS LAYER                            │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐  │
│  │  commands.py │ messages.py  │ reactions.py │  members.py  │  │
│  │              │              │              │              │  │
│  │  • /setup    │ • handle_msg │ • handle_rxn │ • join/leave │  │
│  │  • /settings │ • handle_edit│ • rxn_count  │ • member_upd │  │
│  │  • /set_*    │              │              │              │  │
│  └──────┬───────┴──────┬───────┴──────┬───────┴──────┬───────┘  │
└─────────┼──────────────┼──────────────┼──────────────┼──────────┘
          │              │              │              │
          │    ┌─────────┴──────────────┴──────────┐   │
          │    │       UTILS (decorators)          │   │
          │    │  @with_db_session                 │   │
          │    │  @require_admin                   │   │
          │    │  @group_only                      │   │
          │    └─────────┬─────────────────────────┘   │
          │              │                             │
          ▼              ▼                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                        SERVICES LAYER                            │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐  │
│  │chat_service  │user_service  │msg_service   │rxn_service   │  │
│  │              │              │              │              │  │
│  │ • setup_chat │ • create_user│ • process_msg│ • process_rxn│  │
│  │ • get_settings│ • handle_join│             │              │  │
│  │ • update_cfg │ • handle_leave│             │              │  │
│  └──────┬───────┴──────┬───────┴──────┬───────┴──────┬───────┘  │
└─────────┼──────────────┼──────────────┼──────────────┼──────────┘
          │              │              │              │
          ▼              ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     REPOSITORIES LAYER                           │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐  │
│  │chat_repo     │user_repo     │message_repo  │reaction_repo │  │
│  │              │              │              │              │  │
│  │ • upsert     │ • upsert     │ • create     │ • upsert     │  │
│  │ • get_by_id  │ • get_by_id  │ • get        │ • mark_removed│  │
│  │              │              │              │              │  │
│  │settings_repo │membership_repo│             │              │  │
│  │ • create_def │ • ensure_mem │              │              │  │
│  │ • update     │ • update_join│              │              │  │
│  └──────┬───────┴──────┬───────┴──────┬───────┴──────┬───────┘  │
└─────────┼──────────────┼──────────────┼──────────────┼──────────┘
          │              │              │              │
          └──────────────┴──────────────┴──────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                       DATABASE (db.py)                           │
│                    • AsyncSession                                │
│                    • Connection pooling                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   POSTGRESQL + TIMESCALEDB                       │
│  ┌──────────┬──────────┬───────────┬──────────┬──────────────┐  │
│  │  chats   │  users   │ messages  │ reactions│ memberships  │  │
│  │          │          │           │          │              │  │
│  │          │          │ (hypertbl)│          │              │  │
│  └──────────┴──────────┴───────────┴──────────┴──────────────┘  │
└─────────────────────────────────────────────────────────────────┘


SUPPORTING MODULES:
═══════════════════

┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   CORE          │  │   SCHEMAS       │  │   UTILS         │
│                 │  │                 │  │                 │
│ • config.py     │  │ • commands.py   │  │ • decorators.py │
│ • constants.py  │  │ • api.py        │  │ • validators.py │
│ • exceptions.py │  │                 │  │ • logging.py    │
└─────────────────┘  └─────────────────┘  └─────────────────┘


DATA FLOW EXAMPLE: Message Processing
═════════════════════════════════════

1. Telegram → bot_main → handle_message()
2. handle_message → MessageService.process_message()
3. MessageService:
   - ChatService.get_or_create_chat() → ChatRepository
   - UserService.get_or_create_user() → UserRepository
   - UserService.ensure_membership() → MembershipRepository
   - MessageRepository.create_from_telegram()
4. Repository → Database
5. Commit transaction
6. Log result


BENEFITS OF THIS ARCHITECTURE:
═══════════════════════════════

✅ TESTABILITY
   • Mock repositories for service tests
   • Mock services for handler tests
   • No database needed for unit tests

✅ MAINTAINABILITY
   • Changes isolated to specific layer
   • Single Responsibility Principle
   • Easy to understand data flow

✅ SCALABILITY
   • Add new features without modifying existing code
   • Can add caching at repository level
   • Can swap implementations

✅ TYPE SAFETY
   • Pydantic schemas validate inputs
   • Type hints throughout
   • Catch errors at development time

✅ ERROR HANDLING
   • Custom exception hierarchy
   • Decorators handle common patterns
   • Consistent error messages

✅ CODE REUSE
   • Services used by multiple handlers
   • Repositories used by multiple services
   • Decorators reduce boilerplate


FILE COUNT & LINES:
═══════════════════

New Architecture Files:
  - Core:         4 files, ~150 lines
  - Repositories: 7 files, ~500 lines
  - Services:     5 files, ~400 lines
  - Schemas:      3 files, ~150 lines
  - Utils:        4 files, ~250 lines
  ─────────────────────────────────────
  TOTAL:         23 files, ~1,450 lines

Refactored Files:
  - commands.py:   300 lines → 250 lines (cleaner)
  - messages.py:   140 lines → 45 lines  (80% reduction!)
  - reactions.py:  230 lines → 65 lines  (70% reduction!)
  - members.py:    240 lines → 100 lines (60% reduction!)

Documentation:
  - ARCHITECTURE_REFACTORING.md:  ~300 lines
  - REFACTORING_SUMMARY.md:       ~200 lines
  - POST_REFACTORING_CHECKLIST.md: ~150 lines


COMPARISON:
═══════════

BEFORE                           AFTER
────────────────────────────────────────────────────────────
Handler does everything    →     Handler → Service → Repo
300+ line functions        →     50-100 line functions
Hardcoded values          →     Constants module
Mixed logging styles      →     Structured logging
No validation             →     Pydantic schemas
try-catch everywhere      →     Decorators + exceptions
Circular imports          →     Clean imports
Hard to test              →     Easy to test
Database in handlers      →     Repository layer
Business logic scattered  →     Service layer


NEXT STEPS:
═══════════

1. ✅ Verify all modules compile
2. ✅ Test bot startup
3. ✅ Test all commands
4. ✅ Write unit tests
5. → Split web app into routers
6. → Add API documentation
7. → Add monitoring/metrics
8. → Deploy to production
```

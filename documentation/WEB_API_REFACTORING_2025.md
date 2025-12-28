# Code Structure Improvements - December 2025

## Overview

This document describes the major code structure improvements implemented to enhance maintainability, reduce complexity, and improve code organization in the Telegram Analytics Bot project.

## Key Improvements

### 1. Web API Refactoring

#### Problem
The `tgstats/web/app.py` file was monolithic with 894 lines containing:
- Middleware definitions
- Helper functions
- All API endpoints (chats, analytics, retention)
- UI endpoints
- Duplicate utility code

This made the file difficult to navigate, maintain, and test.

#### Solution
Extracted API endpoints into dedicated router modules and created utility modules for shared functionality:

**New Structure:**
```
tgstats/web/
├── app.py (350 lines, 60% reduction)
├── query_utils.py (reusable query builders)
├── date_utils.py (timezone & date utilities)
└── routers/
    ├── chats.py (chat management endpoints)
    ├── analytics.py (analytics endpoints)
    └── webhook.py (webhook endpoints)
```

**Benefits:**
- **Reduced complexity**: Main app.py reduced from 894 to 350 lines
- **Better organization**: Related endpoints grouped together
- **Code reuse**: Eliminated SQL query duplication
- **Easier testing**: Each router can be tested independently
- **Improved discoverability**: Clear module names indicate functionality

### 2. Query Utilities Module

**File:** `tgstats/web/query_utils.py`

**Purpose:** Centralize database query construction and reduce SQL duplication across endpoints.

**Key Functions:**
- `check_timescaledb_available()` - Detect TimescaleDB presence
- `get_aggregate_table_name()` - Get correct table name based on DB type
- `get_group_tz()` / `get_group_tz_async()` - Retrieve group timezone settings
- `build_chat_stats_query()` - Build chat statistics queries
- `build_timeseries_query()` - Build timeseries queries
- `build_heatmap_query()` - Build heatmap queries
- `build_user_stats_query()` - Build user statistics queries

**Example Usage:**
```python
from ..query_utils import check_timescaledb_available, build_chat_stats_query

is_timescale = check_timescaledb_available(session)
query = build_chat_stats_query(is_timescale, days=30)
result = session.execute(query).fetchall()
```

**Before (duplicated in 3 endpoints):**
```python
if is_timescale:
    query = text("""
        SELECT cd.chat_id, SUM(cd.msg_cnt) as msg_count_30d
        FROM chat_daily cd
        WHERE cd.day >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY cd.chat_id
    """)
else:
    query = text("""
        SELECT cd.chat_id, SUM(cd.msg_cnt) as msg_count_30d
        FROM chat_daily_mv cd
        WHERE cd.day >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY cd.chat_id
    """)
```

**After (single source of truth):**
```python
query = build_chat_stats_query(is_timescale, days=30)
```

### 3. Date/Timezone Utilities Module

**File:** `tgstats/web/date_utils.py`

**Purpose:** Centralize date parsing and timezone conversion logic.

**Key Functions:**
- `parse_period()` - Parse date range parameters with timezone awareness
- `rotate_heatmap_rows()` - Rotate heatmap data from UTC to local timezone
- `convert_local_to_utc()` - Convert local datetime to UTC
- `convert_utc_to_local()` - Convert UTC datetime to local timezone

**Example Usage:**
```python
from ..date_utils import parse_period

tz = get_group_tz(chat_id, session)
start_utc, end_utc, days = parse_period(from_date, to_date, tz)
```

**Benefits:**
- Consistent date handling across all endpoints
- Proper timezone awareness
- Reduced code duplication
- Easier to test date/timezone logic in isolation

### 4. Chat Management Router

**File:** `tgstats/web/routers/chats.py`

**Endpoints:**
- `GET /api/chats` - List all chats with 30-day statistics
- `GET /api/chats/{chat_id}/settings` - Get chat settings

**Features:**
- Full type hints using Pydantic models
- Comprehensive docstrings with parameter descriptions
- Proper error handling with HTTP exceptions
- Admin authentication via dependency injection

**Example:**
```python
@router.get("", response_model=List[ChatSummary])
async def get_chats(
    session: Session = Depends(get_session),
    _token: None = Depends(verify_admin_token),
):
    """
    Get list of known chats with 30-day statistics.

    Returns:
        List of chat summaries with message counts and DAU
    """
    is_timescale = check_timescaledb_available(session)
    query = build_chat_stats_query(is_timescale, days=30)
    result = session.execute(query).fetchall()
    ...
```

### 5. Analytics Router

**File:** `tgstats/web/routers/analytics.py`

**Endpoints:**
- `GET /api/chats/{chat_id}/summary` - Period summary statistics
- `GET /api/chats/{chat_id}/timeseries` - Time series data (messages/DAU)
- `GET /api/chats/{chat_id}/heatmap` - Activity heatmap
- `GET /api/chats/{chat_id}/users` - User statistics with pagination
- `GET /api/chats/{chat_id}/retention/preview` - Retention cleanup preview

**Features:**
- All analytics endpoints in one place
- Consistent parameter validation
- Timezone-aware queries using utility functions
- Pagination support for user lists
- Full docstrings and type hints

### 6. Simplified Main App

**File:** `tgstats/web/app.py`

**Now Contains Only:**
1. **Middleware setup** (request ID, size limits, input validation)
2. **Router includes** (health, webhook, chats, analytics)
3. **UI endpoints** (internal endpoints for web interface)
4. **Root endpoint** (service information)

**Benefits:**
- Easy to understand at a glance
- Clear separation of concerns
- Minimal boilerplate
- Focused responsibility

## Metrics

### Code Complexity Reduction

| File | Before | After | Reduction |
|------|--------|-------|-----------|
| app.py | 894 lines | 350 lines | **60%** |
| Total web/ | 894 lines | 1,100 lines | +206 lines* |

*Total lines increased slightly, but this is expected and beneficial:
- Code is now distributed across multiple focused modules
- Each module has single responsibility
- Reduced duplication (actual logic lines decreased)
- Added comprehensive docstrings

### Code Duplication Reduction

- **SQL Query Builders**: Eliminated duplication in 8+ endpoint functions
- **Timezone Handling**: Centralized from 5+ locations to 1 module
- **Date Parsing**: Unified logic that was copied across 6+ endpoints

## Best Practices Applied

1. **Single Responsibility Principle**: Each module has one clear purpose
2. **DRY (Don't Repeat Yourself)**: Eliminated code duplication
3. **Separation of Concerns**: Clear boundaries between layers
4. **Type Safety**: Full type hints for better IDE support and error detection
5. **Documentation**: Comprehensive docstrings for all public functions
6. **Testability**: Smaller, focused modules are easier to unit test

## Migration Guide

### For Developers

**Old Import:**
```python
from tgstats.web.app import get_group_tz, parse_period
```

**New Import:**
```python
from tgstats.web.query_utils import get_group_tz
from tgstats.web.date_utils import parse_period
```

### For External Code

No changes required for external code using the API:
- All endpoint paths remain the same
- Request/response formats unchanged
- Authentication requirements unchanged
- The refactoring is purely internal

## Testing

### Unit Tests Recommended

```python
# Test query utils
from tgstats.web.query_utils import get_aggregate_table_name

def test_aggregate_table_name():
    assert get_aggregate_table_name(True, "chat_daily") == "chat_daily"
    assert get_aggregate_table_name(False, "chat_daily") == "chat_daily_mv"

# Test date utils
from tgstats.web.date_utils import parse_period
from zoneinfo import ZoneInfo

def test_parse_period():
    tz = ZoneInfo("UTC")
    start, end, days = parse_period("2025-01-01", "2025-01-07", tz)
    assert days == 7
```

### Integration Tests

All existing integration tests should pass without modification since the API interface is unchanged.

## Future Improvements

Based on this refactoring, additional improvements could include:

1. **Service Layer for Analytics**: Create `AnalyticsService` to move query logic from routers to services
2. **Query Builder Pattern**: Consider using SQLAlchemy query builders instead of raw SQL for complex queries
3. **Response Transformers**: Create utilities to transform database results to API responses
4. **Caching Layer**: Add caching decorators for expensive analytics queries
5. **API Versioning**: Prepare for future API versions with proper routing structure

## Conclusion

This refactoring significantly improves code maintainability while preserving all functionality. The new structure makes it easier to:
- Add new endpoints
- Modify existing queries
- Test individual components
- Understand the codebase
- Onboard new developers

The modular approach sets a strong foundation for future enhancements and scaling.

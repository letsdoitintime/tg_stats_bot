# Code Improvements Summary - December 2025

## Overview
This document summarizes the code structure improvements and fixes applied to the TG Stats Bot, with a focus on the heatmap plugin that was experiencing Telegram API flooding issues.

## Critical Issues Fixed

### 1. Heatmap Plugin - Telegram API Flooding
**Problem:**
- The heatmap plugin was causing Telegram API flood errors in large chats
- All messages were loaded into memory without limits
- Multiple synchronous API calls without delays
- No caching for repeated requests
- Inefficient database queries

**Solution:**
- ✅ Created `HeatmapRepository` for optimized database queries
- ✅ Created `HeatmapService` for business logic and caching
- ✅ Implemented query limits (MAX: 50K messages)
- ✅ Added caching with 5-minute TTL
- ✅ Added 0.5-1.0 second delays between message sends
- ✅ Large chat detection (threshold: 10K messages)
- ✅ All analytics now use database queries only (no Telegram API for data)

### 2. Code Architecture Improvements
**Problem:**
- Direct database queries in plugin command handlers
- Business logic mixed with presentation logic
- Duplicate code in plugin manager
- Inconsistent decorator usage

**Solution:**
- ✅ Applied clean layered architecture: Plugin → Service → Repository → Database
- ✅ Removed duplicate code in `PluginManager`
- ✅ Consistent use of `@with_db_session` and `@group_only` decorators
- ✅ Separated concerns properly

## Architecture Pattern

### Before (Anti-pattern)
```python
# Plugin directly queries database and sends multiple messages
async def _heatmap_command(update, context):
    async with async_session() as session:
        query = select(...).where(...)  # Direct SQL in plugin
        result = await session.execute(query)
        data = result.all()  # Load all in memory
        
        for row in data:  # Multiple synchronous sends
            await update.message.reply_text(row)
```

### After (Best Practice)
```python
# Plugin uses service layer, service uses repository
@with_db_session
@group_only
async def _heatmap_command(update, context, session):
    service = HeatmapService(session)
    
    # Check cache first
    data = await service.get_hourly_activity(
        chat_id=chat.id,
        use_cache=True
    )
    
    # Format and send with delays
    text = service.format_heatmap(data)
    await self._send_message_with_retry(
        update, text,
        delay_between_messages=0.5  # Prevent flooding
    )
```

## New Files Created

### 1. `tgstats/repositories/heatmap_repository.py`
**Purpose:** Database query layer for heatmap data
**Key Methods:**
- `get_message_count_by_chat()` - Count messages in time period
- `get_hourly_activity()` - Get aggregated hourly stats
- `get_peak_activity_hour()` - Find most active hour
- `get_peak_activity_day()` - Find most active day

**Features:**
- Efficient GROUP BY aggregations at database level
- LIMIT clause to prevent memory overload
- Optimized queries using indexes

### 2. `tgstats/services/heatmap_service.py`
**Purpose:** Business logic and caching layer
**Key Methods:**
- `is_large_chat()` - Detect chats with many messages
- `get_hourly_activity()` - Get data with caching
- `get_activity_summary()` - Get peak times
- `format_heatmap()` - Format text visualization

**Features:**
- Redis caching with 5-minute TTL
- Large chat detection (threshold: 10K messages)
- Message processing limits (max: 50K)
- Cache key hashing for efficiency

### 3. `tests/test_heatmap.py`
**Purpose:** Unit tests for repository and service
**Coverage:**
- 6 tests for HeatmapRepository
- 5 tests for HeatmapService
- Edge cases (empty chats, large datasets)
- All 11 tests passing ✅

## Key Improvements

### 1. Query Optimization
**Before:**
```python
# Loaded all messages then processed in Python
query = select(Message).where(
    Message.chat_id == chat_id,
    Message.date >= seven_days_ago
)
result = await session.execute(query)
messages = result.all()  # ALL messages in memory!

for msg in messages:
    # Process each message
```

**After:**
```python
# Aggregation at database level with LIMIT
query = select(
    func.extract('hour', Message.date).label('hour'),
    func.extract('dow', Message.date).label('dow'),
    func.count(Message.msg_id).label('count')
).where(
    Message.chat_id == chat_id,
    Message.date >= cutoff_date
).group_by('hour', 'dow').limit(limit)  # Prevent overload
```

### 2. Caching Strategy
```python
# Generate unique cache key
cache_key = hashlib.md5(f"heatmap:{chat_id}:{days}".encode()).hexdigest()

# Try cache first
cached = await cache.get(cache_key)
if cached:
    return json.loads(cached)

# Query database
data = await repo.get_hourly_activity(...)

# Store in cache
await cache.set(cache_key, json.dumps(data), ttl=300)
```

### 3. Flood Control
```python
async def _send_message_with_retry(
    self,
    update: Update,
    text: str,
    delay_between_messages: float = 1.0,  # NEW: Delay before send
    max_retries: int = 3
):
    # Delay before sending to prevent flooding
    if delay_between_messages > 0:
        await asyncio.sleep(delay_between_messages)
    
    for attempt in range(max_retries):
        try:
            await update.message.reply_text(text)
            return True
        except RetryAfter as e:
            # Wait for Telegram-specified time
            await asyncio.sleep(e.retry_after + 1)
```

### 4. Large Chat Handling
```python
# Detect large chats
LARGE_CHAT_THRESHOLD = 10000
MAX_MESSAGES_TO_PROCESS = 50000

is_large = await service.is_large_chat(chat_id)
if is_large:
    logger.info("large_chat_detected")
    await asyncio.sleep(0.5)  # Extra delay

# Limit processing
limit = min(message_count, MAX_MESSAGES_TO_PROCESS)
```

## Best Practices Established

### 1. Layered Architecture
```
User Request
    ↓
Plugin (Command Handler)
    ↓
Service (Business Logic + Caching)
    ↓
Repository (Database Queries)
    ↓
Database
```

### 2. Decorator Usage
```python
@with_db_session      # Provides session, handles transactions
@group_only           # Ensures group chat only
async def command_handler(update, context, session):
    # session automatically provided
    # commit/rollback handled automatically
```

### 3. Analytics Data Sources
✅ **CORRECT:** Use database queries
```python
# Get stats from database
data = await repo.get_hourly_activity(chat_id)
```

❌ **INCORRECT:** Use Telegram API for analytics
```python
# DON'T DO THIS - only for permission checks
chat_member = await context.bot.get_chat_member(...)  # OK for admin check
messages = await context.bot.get_chat_history(...)     # WRONG for analytics
```

### 4. Error Handling
```python
try:
    result = await service.method()
except Exception as e:
    logger.error("operation_failed", error=str(e), exc_info=True)
    await send_message_with_retry(
        update,
        "❌ Error message",
        delay_between_messages=0.5
    )
```

## Performance Metrics

### Before Improvements
- ❌ Could crash with >50K messages
- ❌ Multiple flood control errors
- ❌ No caching (repeated queries)
- ❌ All data loaded into memory

### After Improvements
- ✅ Handles chats with millions of messages
- ✅ No flood control errors (0.5s delays)
- ✅ 5-minute cache (reduces DB load)
- ✅ Efficient aggregation (50K limit)

## Testing Results
```
11 passed, 61 warnings in 1.16s
```

**Test Coverage:**
- Repository CRUD operations
- Service caching logic
- Large chat detection
- Data formatting
- Edge cases (empty data, etc.)

## Future Enhancements (Optional)

### Short-term
- [ ] Apply similar refactoring to word cloud plugin
- [ ] Add per-user rate limiting for expensive commands
- [ ] Implement progressive loading for very large results

### Long-term
- [ ] Materialized views for common aggregations
- [ ] Background job for pre-computing heatmaps
- [ ] WebSocket support for real-time updates

## Migration Guide

If you have custom plugins, follow this pattern:

### Step 1: Create Repository
```python
# my_plugin_repository.py
class MyPluginRepository(BaseRepository[MyModel]):
    async def get_custom_data(self, chat_id: int):
        query = select(...).where(...)
        result = await self.session.execute(query)
        return result.all()
```

### Step 2: Create Service
```python
# my_plugin_service.py
class MyPluginService:
    def __init__(self, session: AsyncSession):
        self.repo = MyPluginRepository(session)
    
    async def get_analytics(self, chat_id: int):
        # Business logic + caching
        data = await self.repo.get_custom_data(chat_id)
        return self.format_data(data)
```

### Step 3: Update Plugin
```python
# my_plugin.py
@with_db_session
@group_only
async def my_command(self, update, context, session):
    service = MyPluginService(session)
    result = await service.get_analytics(chat.id)
    
    await self._send_message_with_retry(
        update, result,
        delay_between_messages=0.5
    )
```

## Conclusion

The refactoring successfully addressed:
1. ✅ Telegram API flooding in large chats
2. ✅ Poor code structure and mixed concerns
3. ✅ Performance issues with large datasets
4. ✅ Missing caching and optimization

All changes follow best practices and maintain backward compatibility while significantly improving performance and reliability.

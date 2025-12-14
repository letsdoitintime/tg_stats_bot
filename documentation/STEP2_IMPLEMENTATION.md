# Step 2 Implementation Guide

## Overview

Step 2 upgrades the tg-stats bot with TimescaleDB aggregations, FastAPI endpoints, and a minimal web UI for analytics visualization.

## Architecture

### Database Layer
- **TimescaleDB Integration**: Optional hypertables and continuous aggregates
- **PostgreSQL Fallback**: Materialized views with Celery refresh for compatibility
- **Automatic Detection**: System detects TimescaleDB availability and chooses appropriate strategy

### API Layer  
- **FastAPI Framework**: RESTful endpoints with automatic OpenAPI documentation
- **Timezone Awareness**: Proper handling of group-specific timezones
- **Authentication**: Optional admin token protection
- **Pydantic Models**: Type-safe request/response handling

### UI Layer
- **Minimal Interface**: Clean dashboard with essential analytics
- **Chart.js Integration**: Interactive time-series and visualization
- **Responsive Design**: Tailwind CSS for mobile-friendly interface

### Background Processing
- **Celery Workers**: Asynchronous task processing
- **Redis Backend**: Task queue and result storage
- **Periodic Tasks**: Automated materialized view refresh

## TimescaleDB vs PostgreSQL

### With TimescaleDB Available

**Benefits:**
- Real-time continuous aggregates
- Automatic data compression
- Optimized time-series queries
- Better performance on large datasets

**Tables Created:**
- `messages` → hypertable (7-day chunks)
- `chat_daily` → continuous aggregate
- `user_chat_daily` → continuous aggregate  
- `chat_hourly_heatmap` → continuous aggregate

### PostgreSQL Fallback

**Features:**
- Materialized views with same schema
- Celery tasks refresh every 10 minutes
- Identical API interface
- Suitable for smaller deployments

**Tables Created:**
- `chat_daily_mv` → materialized view
- `user_chat_daily_mv` → materialized view
- `chat_hourly_heatmap_mv` → materialized view

## Timezone Handling

The system handles timezones correctly throughout:

### Storage
- All timestamps stored in UTC
- Group settings specify local timezone

### API Queries
- Accept local date ranges (`from`, `to`)
- Convert to UTC for database queries
- Return results in appropriate format

### Heatmap Rotation
- Aggregate data is in UTC (by hour)
- UI rotates to local timezone
- Handles DST transitions automatically

### Example: Europe/Sofia (UTC+2/+3)
```sql
-- User queries: 2025-01-15 to 2025-01-15 (Sofia local)
-- Converted to UTC: 2025-01-14 22:00 to 2025-01-15 21:59

-- Heatmap: UTC hour 14 → Sofia hour 16 (winter)
--         UTC hour 22 → Sofia hour 00+1 (next day)
```

## API Endpoints Reference

### Authentication
All endpoints require `X-Admin-Token` header if `ADMIN_API_TOKEN` is set in environment.

### Chat Endpoints

#### `GET /api/chats`
List all chats with 30-day statistics.

**Response:**
```json
[
  {
    "chat_id": -1001234567890,
    "title": "Tech Discussion Group", 
    "msg_count_30d": 4250,
    "avg_dau_30d": 23.5
  }
]
```

#### `GET /api/chats/{chat_id}/settings`
Get group configuration.

**Response:**
```json
{
  "chat_id": -1001234567890,
  "store_text": true,
  "text_retention_days": 90,
  "metadata_retention_days": 365,
  "timezone": "Europe/Sofia",
  "locale": "en",
  "capture_reactions": true
}
```

#### `GET /api/chats/{chat_id}/summary`
Period summary with totals.

**Parameters:**
- `from`: Start date (YYYY-MM-DD, local timezone)
- `to`: End date (YYYY-MM-DD, local timezone)

**Response:**
```json
{
  "total_messages": 1250,
  "unique_users": 45,
  "avg_daily_users": 18.3,
  "new_users": 3,
  "left_users": 1,
  "start_date": "2025-01-15",
  "end_date": "2025-01-21", 
  "days": 7
}
```

### Analytics Endpoints

#### `GET /api/chats/{chat_id}/timeseries`
Time-series data for charts.

**Parameters:**
- `metric`: `messages` or `dau`
- `from`, `to`: Date range

**Response:**
```json
[
  {"day": "2025-01-15", "value": 180},
  {"day": "2025-01-16", "value": 205},
  {"day": "2025-01-17", "value": 192}
]
```

#### `GET /api/chats/{chat_id}/heatmap`  
Activity heatmap (7×24 grid).

**Response:**
```json
{
  "weekdays": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
  "hours": [0, 1, 2, ..., 23],
  "data": [
    [0, 0, 0, 2, 5, 8, 12, ...],  // Monday
    [0, 0, 1, 3, 7, 11, 15, ...], // Tuesday
    ...
  ]
}
```

#### `GET /api/chats/{chat_id}/users`
User statistics with pagination.

**Parameters:**
- `sort`: `act` (activity), `msg` (messages), `ad` (active days), `dsj` (days since joined), `lm` (last message)
- `search`: Filter by username/name (ILIKE)
- `left`: Filter by membership status (boolean)
- `page`, `per_page`: Pagination

**Response:**
```json
{
  "items": [
    {
      "user_id": 123456,
      "username": "alice",
      "first_name": "Alice",
      "last_name": "Smith",
      "msg_count": 145,
      "activity_percentage": 12.5,
      "active_days_ratio": "15/30",
      "last_message": "2025-01-21T14:30:00",
      "days_since_joined": 45,
      "left": false
    }
  ],
  "page": 1,
  "per_page": 50,
  "total": 234
}
```

### Maintenance Endpoints

#### `GET /api/chats/{chat_id}/retention/preview`
Preview retention policy effects.

**Response:**
```json
{
  "chat_id": -1001234567890,
  "text_retention_days": 90,
  "metadata_retention_days": 365,
  "store_text": true,
  "text_removal_count": 1250,
  "metadata_removal_count": 450,
  "reaction_removal_count": 320,
  "text_cutoff_date": "2024-10-23T00:00:00",
  "metadata_cutoff_date": "2024-01-26T00:00:00"
}
```

## Web UI Features

### Chat List (`/ui`)
- Overview of all tracked chats
- 30-day message counts and average DAU
- Quick navigation to detailed views

### Chat Details (`/ui/chat/{chat_id}`)
- **Date Range Picker**: 7/30/90 days + custom range
- **KPI Cards**: Messages, users, DAU, new members
- **Time Series Charts**: Messages and DAU over time
- **Activity Heatmap**: Hour×weekday visualization

### Technical Implementation
- **Tailwind CSS**: Utility-first styling
- **Chart.js**: Interactive charts from CDN
- **Vanilla JavaScript**: No heavy frameworks
- **Responsive Design**: Mobile-friendly layout

## Deployment

### Environment Variables
```env
# Required
BOT_TOKEN=your_telegram_bot_token
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/dbname

# Optional  
ADMIN_API_TOKEN=your_secret_admin_token  # API authentication
REDIS_URL=redis://localhost:6379/0       # Celery backend
LOG_LEVEL=INFO                           # Logging level
```

### Docker Deployment
```bash
# TimescaleDB + full stack
docker-compose up -d

# Services started:
# - db (TimescaleDB)
# - redis (Celery backend)
# - bot (FastAPI + Telegram bot)
# - celery (Background workers)
# - celery-beat (Periodic tasks)
```

### Development Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start components
python -m tgstats.bot_main    # Telegram bot
uvicorn tgstats.web.app:app   # FastAPI server
celery -A tgstats.celery_app worker    # Background worker
celery -A tgstats.celery_app beat      # Periodic tasks
```

## Performance Considerations

### TimescaleDB Optimization
- **Chunk Intervals**: 7-day chunks for optimal query performance
- **Continuous Aggregates**: Real-time updates without manual refresh
- **Compression**: Automatic compression of older chunks
- **Indexing**: Optimized indexes for time-range queries

### PostgreSQL Optimization  
- **Materialized Views**: Pre-computed aggregates
- **Concurrent Refresh**: Non-blocking view updates
- **Indexing**: Proper indexes on aggregate tables
- **Batch Processing**: Large datasets processed in chunks

### API Performance
- **Async Framework**: FastAPI with async/await
- **Connection Pooling**: Efficient database connections
- **Query Optimization**: Efficient SQL with proper joins
- **Pagination**: Large result sets properly paginated

### UI Performance
- **CDN Resources**: Chart.js and Tailwind from CDN
- **Minimal JavaScript**: No heavy frameworks
- **Efficient Queries**: API endpoints optimized for UI needs
- **Caching**: Browser caching for static resources

## Testing

### Test Coverage
- **Timezone Tests**: Europe/Sofia specific cases
- **Heatmap Rotation**: UTC to local conversion
- **User Metrics**: Activity calculations
- **Edge Cases**: Invalid timezones, missing data

### Sample Data
```bash
python scripts/seed_database.py
```

Generates realistic test data:
- 2 sample chats with different activity patterns
- 50 users with varying engagement levels
- 15 days of messages with realistic timing
- Reactions and media messages
- Membership join/leave events

### Manual Testing
```bash
# API testing
curl -H "X-Admin-Token: token" http://localhost:8010/api/chats

# Test the web UI
open http://localhost:8010/ui

# Database verification
psql $DATABASE_URL -c "SELECT COUNT(*) FROM messages;"
```

## Troubleshooting

### TimescaleDB Issues
```sql
-- Check if TimescaleDB is installed
SELECT * FROM pg_extension WHERE extname = 'timescaledb';

-- Check hypertables
SELECT * FROM timescaledb_information.hypertables;

-- Check continuous aggregates
SELECT * FROM timescaledb_information.continuous_aggregates;
```

### PostgreSQL Fallback
```sql
-- Check materialized views
\dv *_mv

-- Manual refresh
REFRESH MATERIALIZED VIEW CONCURRENTLY chat_daily_mv;
```

### Celery Issues
```bash
# Check Redis connection
redis-cli ping

# Monitor Celery tasks
celery -A tgstats.celery_app status
celery -A tgstats.celery_app inspect active

# Check logs
docker-compose logs celery
docker-compose logs celery-beat
```

### API Issues
```bash
# Check FastAPI logs
uvicorn tgstats.web.app:app --reload --log-level debug

# Test endpoints
curl -v http://localhost:8010/healthz
curl -H "X-Admin-Token: token" http://localhost:8010/api/chats
```

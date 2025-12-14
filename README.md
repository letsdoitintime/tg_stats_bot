# Telegram Analytics Bot (tg-stats) - Step 2: Aggregations + API + UI

####
andrew@Andrews-MacBook Chat Stats % cd "/Users/andrew/TelegaBot/Projects Local/Chat Stats" && echo "=== PostgreSQL Connection Details ===" && echo "" && echo "📋 Connection Info:" && echo "  Host: localhost" && echo "  Port: 5433" && echo "  Database: tgstats" && echo "  Username: andrew" && echo "  Password: (none - trust auth)" && echo "" && echo "🔧 Connection Commands:" && echo "  psql: /opt/homebrew/opt/postgresql@16/bin/psql -h localhost -p 5433 -U andrew -d tgstats" && echo "  URL:  postgresql://andrew@localhost:5433/tgstats" && echo "" && echo "📁 Config Files:" && echo "  Main config: postgres_data/postgresql.conf" && echo "  Auth config: postgres_data/pg_hba.conf"
=== PostgreSQL Connection Details ===

📋 Connection Info:
  Host: localhost
  Port: 5433
  Database: tgstats
  Username: andrew
  Password: (none - trust auth)

🔧 Connection Commands:
  psql: /opt/homebrew/opt/postgresql@16/bin/psql -h localhost -p 5433 -U andrew -d tgstats
  URL:  postgresql://andrew@localhost:5433/tgstats

📁 Config Files:
  Main config: postgres_data/postgresql.conf
  Auth config: postgres_data/pg_hba.conf
andrew@Andrews-MacBook Chat Stats % 
####

🗄️ **This is a self-contained local setup with PostgreSQL database files in the project folder.**

A comprehensive Telegram analytics bot with **TimescaleDB aggregations**, **FastAPI endpoints**, and **minimal web UI**.

## ✨ Step 2 Features

### 📊 TimescaleDB Aggregations
- **Automatic hypertables** for time-series message data
- **Continuous aggregates** for real-time analytics (with PostgreSQL fallback)
- **Optimized queries** for large datasets with 7-day chunk intervals

### 🚀 FastAPI Analytics API
- **RESTful endpoints** with timezone-aware queries
- **Admin authentication** via `X-Admin-Token` header
- **Chat statistics**, timeseries data, heatmaps, and user analytics
- **Retention preview** showing what would be deleted

### 🎨 Minimal Web UI
- **Simple dashboard** with Chart.js visualizations
- **Interactive date pickers** (7/30/90 days + custom)
- **Activity heatmaps** with timezone rotation
- **KPI cards** and user statistics

### ⚡ Background Processing
- **Celery workers** for materialized view refresh (PostgreSQL fallback)
- **Redis backend** for task queuing
- **Periodic tasks** with jitter to prevent thundering herd

## Local Quick Start

### 1. Start Everything (One Command)
```bash
./start_bot.sh
```
This automatically:
- Starts the local PostgreSQL database (port 5433) 
- Starts Redis for Celery
- Runs database migrations (including TimescaleDB setup)
- Starts the Telegram bot
- Starts Celery workers and beat scheduler

### 2. Access the Web UI
```bash
# Web UI
http://localhost:8000/ui

# API Documentation
http://localhost:8000/docs
```

### 3. API Authentication
Set the admin token in `.env`:
```env
ADMIN_API_TOKEN=your_secret_token_here
```

Use it in API requests:
```bash
curl -H "X-Admin-Token: your_secret_token_here" \
     http://localhost:8000/api/chats
```

### 4. TimescaleDB vs PostgreSQL
The system automatically detects TimescaleDB availability:

**With TimescaleDB:**
- Messages table becomes a hypertable
- Uses continuous aggregates (`chat_daily`, `user_chat_daily`, etc.)
- Real-time aggregation updates

**Without TimescaleDB:**
- Uses materialized views (`chat_daily_mv`, `user_chat_daily_mv`, etc.)
- Celery tasks refresh views every 10 minutes
- Same API interface

## 📚 Documentation

All project documentation is organized in the `documentation/` folder:

- **[Documentation Index](documentation/README.md)** - Complete guide to all available docs
- **Database Setup** - PostgreSQL configuration, users, remote access
- **DBeaver Connection** - GUI database access guide  
- **Feature Guides** - Reaction analysis, message storage, etc.

## 🔌 API Endpoints

### Chat Management
- `GET /api/chats` - List all chats with 30-day stats
- `GET /api/chats/{id}/settings` - Get chat settings  
- `GET /api/chats/{id}/summary?from&to` - Period summary statistics

### Analytics
- `GET /api/chats/{id}/timeseries?metric=messages|dau&from&to` - Time series data
- `GET /api/chats/{id}/heatmap?from&to` - Activity heatmap (7×24 grid)
- `GET /api/chats/{id}/users?sort&search&left&page` - User statistics with pagination

### Maintenance  
- `GET /api/chats/{id}/retention/preview` - Preview retention cleanup

### Example API Calls
```bash
# Get chat list
curl -H "X-Admin-Token: token" http://localhost:8000/api/chats

# Get last 7 days of messages
curl -H "X-Admin-Token: token" \
     "http://localhost:8000/api/chats/-1001234567890/timeseries?metric=messages&from=2025-01-24&to=2025-01-31"

# Get user statistics sorted by activity
curl -H "X-Admin-Token: token" \
     "http://localhost:8000/api/chats/-1001234567890/users?sort=act&page=1&per_page=25"
```

## 🧪 Testing & Development

### Generate Sample Data
```bash
python scripts/seed_database.py
```
Creates 15 days of sample data across 2 chats with realistic activity patterns.

### Run Tests
```bash
pytest tests/test_step2.py -v
```
Tests timezone handling, heatmap rotation, and user metrics calculations.

### Timezone Handling
The system properly handles timezone conversions:
- Group settings specify timezone (e.g., "Europe/Sofia")
- API queries convert local date ranges to UTC
- Heatmaps rotate from UTC to local time
- Handles DST transitions automatically

## Project Structure
- `postgres_data/` - Local PostgreSQL database files
- `tgstats/web/app.py` - FastAPI application with all endpoints
- `tgstats/celery_tasks.py` - Background task definitions
- `tgstats/web/templates/` - Minimal UI templates
- `migrations/versions/` - Database migrations including TimescaleDB setup
- `scripts/seed_database.py` - Sample data generator
- `documentation/` - 📚 **Complete documentation and guides**

---

## Original Documentation

## Features

- **Multi-group support** with per-group configuration
- **Message analytics**: text length, URL count, emoji count, media type detection
- **Member tracking**: join/leave events, membership status changes
- **Configurable data retention**: optional text storage, customizable retention periods
- **Admin controls**: group setup, settings management
- **Flexible deployment**: polling or webhook mode
- **Production ready**: Docker support, database migrations, structured logging

## Quick Start

### Using Docker (Recommended)

1. Clone the repository and copy environment file:
```bash
cp .env.example .env
```

2. Edit `.env` and add your bot token:
```env
BOT_TOKEN=your_bot_token_from_botfather
ADMIN_API_TOKEN=your_secret_admin_token
REDIS_URL=redis://localhost:6379/0
```

3. Start the services:
```bash
docker-compose up --build
```

The bot will automatically run database migrations and start in polling mode.

### Local Development

1. **Prerequisites**:
   - Python 3.12+
   - PostgreSQL 13+

2. **Install dependencies**:
```bash
pip install -e .
```

3. **Setup environment**:
```bash
cp .env.example .env
# Edit .env with your settings
```

4. **Setup database**:
```bash
# Make sure PostgreSQL is running
alembic upgrade head
```

5. **Run the bot**:
```bash
python -m tgstats.bot_main
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BOT_TOKEN` | Telegram bot token from @BotFather | Required |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+psycopg://postgres:postgres@db:5432/tgstats` |
| `MODE` | Bot mode: `polling` or `webhook` | `polling` |
| `WEBHOOK_URL` | Webhook URL (required for webhook mode) | - |
| `LOG_LEVEL` | Logging level | `INFO` |

### Bot Commands

#### Admin Commands (Group Only)
- `/setup` - Initialize analytics for the group
- `/settings` - View current group settings
- `/set_text on|off` - Toggle text message storage
- `/set_reactions on|off` - Toggle reaction capture

#### General Commands
- `/help` - Show help message
- `/start` - Show help message (private chats)

## Database Schema

The bot uses PostgreSQL with the following main tables:

- **chats**: Telegram chat information
- **users**: User profiles and metadata
- **memberships**: User membership in chats with join/leave tracking
- **group_settings**: Per-group configuration
- **messages**: Message analytics data with configurable text storage
- **reactions**: Individual message reactions with user tracking

## Analytics Features

### Message Analytics
- Text length calculation
- URL detection and counting
- Emoji counting using Unicode standards
- Media type classification (photo, video, document, etc.)
- Entity extraction (mentions, hashtags, etc.)
- Reaction tracking and analytics (when enabled)

### Member Analytics
- Join/leave event tracking
- Membership status changes
- Admin/member role tracking

### Privacy Controls
- **Configurable text storage**: Groups can choose whether to store message text
- **Data retention**: Configurable retention periods for different data types
- **Admin-only settings**: Only group admins can modify settings

## Architecture

### Bot Modes

#### Polling Mode (Default)
- Uses Telegram's `getUpdates` API
- Suitable for development and small deployments
- No external dependencies

#### Webhook Mode
- Uses FastAPI web server
- Better for production deployments
- Requires public HTTPS endpoint

### Database
- PostgreSQL with async SQLAlchemy 2.x
- Alembic for migrations
- Composite primary keys for efficient queries
- Optimized indexes for analytics queries

### Logging
- Structured logging with `structlog`
- JSON output for production
- Contextual information (chat_id, user_id, etc.)

## Development

### Running Tests
```bash
pip install -e ".[dev]"
pytest
```

### Code Style
```bash
# Format code
black .

# Lint code
ruff check .
```

### Creating Migrations
```bash
alembic revision --autogenerate -m "Description of changes"
alembic upgrade head
```

## Deployment

### Docker Production Setup

1. **Use production database**:
```yaml
# docker-compose.prod.yml
services:
  bot:
    environment:
      - DATABASE_URL=postgresql+psycopg://user:pass@your-db-host:5432/tgstats
      - MODE=webhook
      - WEBHOOK_URL=https://your-domain.com
```

2. **Deploy with reverse proxy**:
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Manual Deployment

1. **Setup environment**:
```bash
export BOT_TOKEN="your_token"
export DATABASE_URL="your_db_url"
export MODE="webhook"
export WEBHOOK_URL="https://your-domain.com"
```

2. **Run migrations**:
```bash
alembic upgrade head
```

3. **Start bot**:
```bash
python -m tgstats.bot_main
```

## Monitoring

### Health Checks
- `/healthz` endpoint (webhook mode)
- Structured logging for monitoring
- Database connection health

### Metrics
The bot logs key metrics that can be collected:
- Message processing rates
- Error rates
- Database query performance
- Member activity

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Ensure code passes linting
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
1. Check the documentation
2. Search existing issues
3. Create a new issue with detailed information

## Changelog

### v0.1.0
- Initial release
- Multi-group analytics support
- Configurable text storage
- Admin controls
- Docker deployment
- Comprehensive test suite

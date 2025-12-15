# Developer Quick Start Guide

## 🚀 Getting Started in 5 Minutes

This guide will get you up and running with the TG Stats Bot development environment quickly.

### Prerequisites

- Python 3.12+
- PostgreSQL 13+ or Docker
- Redis (optional, for caching and Celery)
- Git

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/letsdoitintime/tg_stats_bot.git
cd tg_stats_bot

# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and add your bot token
# Get a bot token from @BotFather on Telegram
nano .env  # or use your favorite editor
```

**Minimum required configuration:**
```env
BOT_TOKEN=your_telegram_bot_token_here
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/tgstats
MODE=polling
LOG_LEVEL=DEBUG
```

### 3. Start Development Database

**Option A: Using Docker (Recommended)**
```bash
# Start PostgreSQL and Redis
docker-compose up -d db redis

# Wait a few seconds for services to start
sleep 5
```

**Option B: Using Local PostgreSQL**
```bash
# Create database
createdb tgstats

# Or using psql
psql -c "CREATE DATABASE tgstats;"
```

### 4. Run Database Migrations

```bash
# Apply all migrations
alembic upgrade head

# Verify migrations
alembic current
```

### 5. Start the Bot

```bash
# Run in development mode
python -m tgstats.bot_main
```

You should see:
```
[INFO] Bot started in polling mode
[INFO] Press Ctrl+C to stop
```

### 6. Test the Bot

1. Open Telegram and find your bot
2. Send `/start` to see the welcome message
3. Add the bot to a test group
4. Run `/setup` in the group (as admin)
5. Send some messages and watch them being tracked!

---

## 🔨 Development Workflow

### Project Structure

```
tg_stats_bot/
├── tgstats/              # Main application code
│   ├── handlers/         # Telegram update handlers
│   ├── services/         # Business logic layer
│   ├── repositories/     # Database access layer
│   ├── models.py         # SQLAlchemy ORM models
│   ├── web/             # FastAPI web application
│   ├── plugins/         # Plugin system
│   └── utils/           # Utility functions
├── migrations/          # Alembic database migrations
├── tests/              # Test suite
├── documentation/      # Project documentation
└── scripts/           # Helper scripts
```

### Common Development Tasks

#### Adding a New Feature

1. **Create a new branch:**
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. **Add your code following the architecture:**
   - Handler → Service → Repository → Database
   - Use type hints everywhere
   - Add docstrings for public methods
   - Follow the existing code style

3. **Create a migration if needed:**
   ```bash
   alembic revision --autogenerate -m "Add new feature table"
   alembic upgrade head
   ```

4. **Write tests:**
   ```bash
   # Add tests in tests/test_my_feature.py
   pytest tests/test_my_feature.py -v
   ```

5. **Format and lint:**
   ```bash
   black .
   ruff check . --fix
   isort .
   ```

#### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_validators.py

# Run with coverage
pytest --cov=tgstats --cov-report=html

# Run only unit tests
pytest tests/ -m "not integration"

# Run in watch mode (install pytest-watch first)
ptw -- -v
```

#### Database Operations

```bash
# Create a new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history

# Check current version
alembic current

# Seed test data
python scripts/seed_database.py
```

#### Working with the Web API

```bash
# Start the bot (includes FastAPI server)
python -m tgstats.bot_main

# In another terminal, test endpoints
curl http://localhost:8000/healthz

# View API documentation
open http://localhost:8000/docs  # Or visit in browser
```

#### Code Style and Linting

```bash
# Format code with Black
black tgstats/ tests/

# Sort imports with isort
isort tgstats/ tests/

# Lint with Ruff
ruff check tgstats/ tests/

# Fix auto-fixable issues
ruff check tgstats/ tests/ --fix

# Type checking (optional)
mypy tgstats/
```

### Debugging

#### Debug Logging

Set `LOG_LEVEL=DEBUG` in `.env` to see detailed logs:

```python
import structlog
logger = structlog.get_logger(__name__)

logger.debug("Debugging info", variable=some_value, count=123)
logger.info("Normal operation")
logger.error("Something went wrong", error=str(e))
```

#### Database Debugging

```bash
# Connect to database
psql postgresql://postgres:postgres@localhost:5432/tgstats

# View tables
\dt

# View table structure
\d messages

# Run queries
SELECT * FROM chats LIMIT 10;

# View recent messages
SELECT chat_id, user_id, text_raw, date 
FROM messages 
ORDER BY date DESC 
LIMIT 20;
```

#### Python Debugger

```python
# Add breakpoint in code
import pdb; pdb.set_trace()

# Or use built-in breakpoint() (Python 3.7+)
breakpoint()
```

---

## 🔌 Creating a Plugin

### Simple Command Plugin

Create `tgstats/plugins/my_plugin.py`:

```python
"""My awesome plugin."""

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, Application

from .base import CommandPlugin, PluginMetadata


class MyPlugin(CommandPlugin):
    """Example plugin that adds a custom command."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="my_plugin",
            version="1.0.0",
            description="Adds /mycommand to the bot",
            author="Your Name",
            dependencies=[]
        )

    async def initialize(self, app: Application) -> None:
        """Register command handlers."""
        app.add_handler(CommandHandler("mycommand", self.handle_command))

    async def shutdown(self) -> None:
        """Cleanup when plugin unloads."""
        pass

    async def handle_command(
        self, 
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /mycommand."""
        await update.message.reply_text("Hello from my plugin!")

    @property
    def commands(self) -> dict:
        """Return command descriptions."""
        return {
            'mycommand': 'Does something awesome'
        }
```

**Test your plugin:**
1. Restart the bot
2. Send `/mycommand` in Telegram
3. You should see "Hello from my plugin!"

See `documentation/PLUGIN_SYSTEM.md` for advanced plugin development.

---

## 📊 Useful Development Commands

### Database Seeding

```bash
# Generate realistic test data
python scripts/seed_database.py

# This creates:
# - 2 sample chats
# - Multiple users
# - 15 days of message history
# - Realistic activity patterns
```

### Log Viewing

```bash
# View live logs
tail -f logs/tgstats.log

# Search logs for errors
grep ERROR logs/tgstats.log

# Pretty-print JSON logs
tail -f logs/tgstats.log | jq '.'
```

### Performance Monitoring

```bash
# View database connection pool status
psql tgstats -c "SELECT * FROM pg_stat_activity;"

# View table sizes
psql tgstats -c "
SELECT 
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"
```

---

## 🐛 Troubleshooting

### Bot Won't Start

**Error: "Connection to database failed"**
```bash
# Check PostgreSQL is running
pg_isready -h localhost -p 5432

# Check connection string in .env
cat .env | grep DATABASE_URL
```

**Error: "Bot token is invalid"**
```bash
# Verify token in .env
cat .env | grep BOT_TOKEN

# Token should start with a number followed by colon
# Example: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz
```

### Migrations Fail

**Error: "Target database is not up to date"**
```bash
# View current version
alembic current

# View available versions
alembic heads

# Force to latest
alembic upgrade head
```

**Error: "Duplicate column/table"**
```bash
# Rollback and retry
alembic downgrade -1
alembic upgrade head
```

### Tests Failing

```bash
# Run with verbose output
pytest -v -s

# Run with debugging
pytest --pdb

# Skip slow tests
pytest -m "not slow"
```

### Plugin Not Loading

```bash
# Check plugin file name doesn't start with underscore
ls -la tgstats/plugins/

# Check plugin logs
grep "plugin" logs/tgstats.log

# Enable plugin debugging
export LOG_LEVEL=DEBUG
python -m tgstats.bot_main
```

---

## 📚 Additional Resources

- **Architecture Guide**: `documentation/ARCHITECTURE_DIAGRAM.md`
- **Plugin Development**: `documentation/PLUGIN_SYSTEM.md`
- **Testing Guide**: `documentation/TESTING_GUIDE.md`
- **API Documentation**: `http://localhost:8000/docs` (when bot is running)
- **Code Examples**: `tgstats/plugins/examples/`

---

## 🤝 Getting Help

1. **Check Documentation**: Look in `documentation/` folder
2. **Search Issues**: https://github.com/letsdoitintime/tg_stats_bot/issues
3. **Ask Questions**: Create a new issue with `[Question]` tag
4. **Code Examples**: Look at existing plugins and handlers

---

## 📝 Code Style Guidelines

### Python Style

- Use **type hints** for all function parameters and return values
- Use **docstrings** for all public functions and classes
- Follow **PEP 8** naming conventions
- Line length: **100 characters** maximum
- Use **async/await** for all I/O operations

### Example:

```python
async def process_message(
    message_id: int, 
    chat_id: int, 
    session: AsyncSession
) -> Optional[Message]:
    """
    Process and store a message.
    
    Args:
        message_id: Telegram message ID
        chat_id: Telegram chat ID
        session: Database session
        
    Returns:
        Processed message or None if failed
        
    Raises:
        ValidationError: If message data is invalid
        DatabaseError: If database operation fails
    """
    # Implementation here
    pass
```

### Import Order

1. Standard library imports
2. Third-party library imports
3. Local application imports

```python
# Standard library
import asyncio
from datetime import datetime
from typing import Optional, List

# Third-party
import structlog
from sqlalchemy import select
from telegram import Update

# Local
from tgstats.models import Message
from tgstats.core.exceptions import ValidationError
```

---

## ✅ Pre-commit Checklist

Before committing code:

- [ ] Code is formatted with Black
- [ ] Imports are sorted with isort
- [ ] Code passes Ruff linting
- [ ] All tests pass
- [ ] New features have tests
- [ ] Documentation is updated
- [ ] Migration is created (if schema changed)
- [ ] No debug code or print statements
- [ ] No sensitive data in code

```bash
# Run all checks
black . && isort . && ruff check . && pytest
```

---

**Happy Coding! 🚀**

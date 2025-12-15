# Testing Guide

## Overview

This guide covers testing strategies, patterns, and best practices for the TG Stats Bot project.

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── test_repositories/       # Repository layer tests
│   ├── test_chat_repo.py
│   └── test_user_repo.py
├── test_services/           # Service layer tests
│   ├── test_chat_service.py
│   └── test_message_service.py
├── test_handlers/           # Handler tests
│   ├── test_commands.py
│   └── test_messages.py
├── test_web/                # API tests
│   ├── test_api_chats.py
│   └── test_api_analytics.py
└── test_integration/        # Integration tests
    └── test_message_flow.py
```

## Testing Layers

### 1. Repository Tests

Test data access layer in isolation:

```python
# tests/test_repositories/test_chat_repo.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from tgstats.repositories.chat_repository import ChatRepository
from tgstats.models import Chat

@pytest.mark.asyncio
async def test_get_by_chat_id(db_session: AsyncSession):
    """Test getting chat by chat_id."""
    # Arrange
    repo = ChatRepository(db_session)
    chat = await repo.create(
        chat_id=123,
        title="Test Chat",
        type="group"
    )
    
    # Act
    result = await repo.get_by_chat_id(123)
    
    # Assert
    assert result is not None
    assert result.chat_id == 123
    assert result.title == "Test Chat"

@pytest.mark.asyncio
async def test_get_by_chat_id_not_found(db_session: AsyncSession):
    """Test getting non-existent chat."""
    repo = ChatRepository(db_session)
    result = await repo.get_by_chat_id(999)
    assert result is None
```

### 2. Service Tests

Test business logic with mocked repositories:

```python
# tests/test_services/test_chat_service.py
import pytest
from unittest.mock import Mock, AsyncMock
from tgstats.services.chat_service import ChatService
from tgstats.models import Chat, GroupSettings

@pytest.mark.asyncio
async def test_setup_chat_creates_settings():
    """Test that setup_chat creates default settings."""
    # Arrange
    mock_session = AsyncMock()
    mock_repo_factory = Mock()
    
    # Mock repositories
    mock_chat_repo = Mock()
    mock_settings_repo = Mock()
    mock_repo_factory.chat = mock_chat_repo
    mock_repo_factory.settings = mock_settings_repo
    
    # Setup return values
    chat = Chat(chat_id=123, title="Test", type="group")
    mock_chat_repo.get_by_chat_id.return_value = chat
    mock_settings_repo.get_by_chat_id.return_value = None
    
    settings = GroupSettings(chat_id=123, store_text=False)
    mock_settings_repo.create_default.return_value = settings
    
    # Act
    service = ChatService(mock_session, mock_repo_factory)
    result = await service.setup_chat(123)
    
    # Assert
    assert result.chat_id == 123
    mock_settings_repo.create_default.assert_called_once_with(123)
```

### 3. Handler Tests

Test Telegram handlers with mocked context:

```python
# tests/test_handlers/test_commands.py
import pytest
from unittest.mock import AsyncMock, Mock, patch
from telegram import Update, Chat, User, Message
from telegram.ext import ContextTypes

from tgstats.handlers.commands import setup_command

@pytest.mark.asyncio
async def test_setup_command_success():
    """Test successful setup command."""
    # Arrange
    update = Mock(spec=Update)
    update.effective_chat = Mock(spec=Chat)
    update.effective_chat.id = 123
    update.effective_chat.title = "Test Group"
    update.effective_chat.type = "group"
    
    update.effective_user = Mock(spec=User)
    update.effective_user.id = 456
    
    update.message = Mock(spec=Message)
    update.message.reply_text = AsyncMock()
    
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    # Mock admin check
    with patch('tgstats.handlers.commands._is_user_admin', return_value=True):
        with patch('tgstats.services.chat_service.ChatService') as mock_service:
            # Configure mock
            mock_instance = mock_service.return_value
            mock_instance.setup_chat = AsyncMock()
            
            # Act
            await setup_command(update, context)
            
            # Assert
            update.message.reply_text.assert_called_once()
            call_args = update.message.reply_text.call_args[0][0]
            assert "Setup Complete" in call_args
```

### 4. API Tests

Test FastAPI endpoints:

```python
# tests/test_web/test_api_chats.py
import pytest
from httpx import AsyncClient
from fastapi import status

from tgstats.web.app import app
from tgstats.models import Chat

@pytest.mark.asyncio
async def test_get_chats_success(db_session):
    """Test getting list of chats."""
    # Arrange
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Create test data
        chat = Chat(chat_id=123, title="Test Chat", type="group")
        db_session.add(chat)
        await db_session.commit()
        
        # Act
        response = await client.get(
            "/api/chats",
            headers={"X-Admin-Token": "test_token"}
        )
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["chat_id"] == 123

@pytest.mark.asyncio
async def test_get_chats_unauthorized():
    """Test getting chats without token."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/chats")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
```

### 5. Integration Tests

Test full flows across layers:

```python
# tests/test_integration/test_message_flow.py
import pytest
from telegram import Update, Message as TgMessage, Chat, User
from tgstats.handlers.messages import handle_message
from tgstats.models import Message

@pytest.mark.asyncio
async def test_message_processing_flow(db_session):
    """Test full message processing from handler to database."""
    # Arrange
    update = Mock(spec=Update)
    # ... setup update mock
    
    context = Mock()
    
    # Act
    await handle_message(update, context)
    
    # Assert - verify data in database
    result = await db_session.execute(
        select(Message).where(Message.msg_id == 123)
    )
    message = result.scalar_one_or_none()
    assert message is not None
    assert message.text_len > 0
```

## Fixtures

Common test fixtures in `conftest.py`:

```python
# tests/conftest.py
import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from tgstats.db import Base
from tgstats.config import settings

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def db_session():
    """Create test database session."""
    # Use in-memory SQLite for tests
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()
    
    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()

@pytest.fixture
def mock_telegram_update():
    """Create mock Telegram update."""
    update = Mock(spec=Update)
    update.effective_chat = Mock(spec=Chat)
    update.effective_user = Mock(spec=User)
    update.message = Mock(spec=TgMessage)
    return update
```

## Running Tests

### Run All Tests
```bash
pytest
```

### Run Specific Test File
```bash
pytest tests/test_services/test_chat_service.py
```

### Run Tests by Marker
```bash
pytest -m "not slow"
pytest -m integration
```

### Run with Coverage
```bash
pytest --cov=tgstats --cov-report=html
```

### Run in Parallel
```bash
pytest -n auto
```

## Test Markers

Mark tests with pytest markers:

```python
@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.asyncio
async def test_expensive_operation():
    ...
```

Configure in `pyproject.toml`:
```toml
[tool.pytest.ini_options]
markers = [
    "slow: marks tests as slow",
    "integration: marks tests as integration tests",
    "unit: marks tests as unit tests"
]
```

## Mocking Best Practices

### Mock External Services
```python
@patch('tgstats.services.external_api.requests.get')
def test_with_mocked_api(mock_get):
    mock_get.return_value.json.return_value = {"data": "test"}
    ...
```

### Mock Database Queries
```python
@patch('tgstats.repositories.chat_repository.ChatRepository.get_by_chat_id')
async def test_with_mocked_repo(mock_get):
    mock_get.return_value = Chat(chat_id=123, title="Test")
    ...
```

### Mock Async Functions
```python
from unittest.mock import AsyncMock

@patch('tgstats.services.chat_service.ChatService.setup_chat')
async def test_with_async_mock(mock_setup):
    mock_setup = AsyncMock(return_value=settings_obj)
    ...
```

## Test Data Factories

Create test data easily with factories:

```python
# tests/factories.py
from tgstats.models import Chat, User, Message

class ChatFactory:
    @staticmethod
    def create(session, **kwargs):
        defaults = {
            "chat_id": 123,
            "title": "Test Chat",
            "type": "group"
        }
        defaults.update(kwargs)
        chat = Chat(**defaults)
        session.add(chat)
        return chat

# Usage
chat = ChatFactory.create(session, title="My Chat")
```

## Performance Testing

Use pytest-benchmark for performance tests:

```python
def test_repository_performance(benchmark, db_session):
    """Benchmark repository operations."""
    repo = ChatRepository(db_session)
    
    def run_query():
        return repo.get_by_chat_id(123)
    
    result = benchmark(run_query)
    assert result is not None
```

## Coverage Goals

- **Overall**: 80%+ coverage
- **Critical Paths**: 95%+ coverage
- **Services**: 90%+ coverage
- **Repositories**: 85%+ coverage
- **Handlers**: 75%+ coverage

## CI/CD Integration

Tests run automatically on:
- Pull requests
- Merges to main
- Release tags

GitHub Actions workflow:
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run tests
        run: |
          pip install -e .[dev]
          pytest --cov=tgstats
```

## Troubleshooting

### Async Test Issues
```python
# Use asyncio marker
@pytest.mark.asyncio
async def test_async():
    ...
```

### Database Cleanup
```python
# Always rollback in fixtures
finally:
    await session.rollback()
```

### Flaky Tests
```python
# Add retry decorator
@pytest.mark.flaky(reruns=3)
def test_sometimes_fails():
    ...
```

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio)
- [Testing FastAPI](https://fastapi.tiangolo.com/tutorial/testing/)
- [SQLAlchemy Testing](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites)

"""Database configuration and session management."""

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from .core.config import settings

# Create the declarative base
Base = declarative_base()

# Parse and convert database URL for async driver
db_url = make_url(settings.database_url)
if db_url.drivername == "postgresql+psycopg":
    async_db_url = db_url.set(drivername="postgresql+asyncpg")
else:
    async_db_url = db_url

# Create async engine with optimized connection pooling
# SQLite doesn't support connection pooling or server_settings
if "sqlite" in str(async_db_url):
    engine = create_async_engine(
        async_db_url,
        echo=False
    )
else:
    engine = create_async_engine(
        async_db_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=3600,
        pool_timeout=settings.db_pool_timeout,
        connect_args={
            "server_settings": {
                "jit": "off",
                "statement_timeout": "60000",
            }
        }
    )

# Create sync engine for Celery and other sync operations with connection pooling
# SQLite doesn't support connection pooling
if "sqlite" in settings.database_url:
    sync_engine = create_engine(
        settings.database_url,
        echo=False
    )
else:
    sync_engine = create_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=max(5, settings.db_pool_size // 2),
        max_overflow=max(10, settings.db_max_overflow // 2),
        pool_recycle=3600
    )

# Create async session factory
async_session = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# Create sync session factory
sync_session = sessionmaker(sync_engine, class_=Session, expire_on_commit=False)


async def get_session() -> AsyncSession:
    """Get an async database session (FastAPI dependency)."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_db_session() -> AsyncSession:
    """Get an async database session (legacy name)."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


def get_sync_session() -> Session:
    """Get a synchronous database session context manager."""
    return sync_session()


def get_sync_engine():
    """Get synchronous engine for Alembic migrations."""
    return sync_engine

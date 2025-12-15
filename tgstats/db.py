"""Database configuration and session management.

This module provides database engines, session factories, and connection management
for both async (application) and sync (migrations, Celery) operations.

The module uses lazy initialization to avoid circular dependencies with the config module.
"""

from typing import AsyncGenerator
from sqlalchemy import create_engine, Engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Create the declarative base
Base = declarative_base()

# Module-level variables for engines and session factories (lazily initialized)
_engine: AsyncEngine | None = None
_sync_engine: Engine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None
_sync_session_factory: sessionmaker[Session] | None = None


def _get_engine() -> AsyncEngine:
    """Get or create the async database engine."""
    global _engine
    if _engine is None:
        # Import here to avoid circular dependency
        from .config import settings
        
        _engine = create_async_engine(
            settings.database_url.replace("postgresql+psycopg://", "postgresql+asyncpg://"),
            echo=False,
            pool_pre_ping=True,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_recycle=3600,  # Recycle connections after 1 hour
            pool_timeout=settings.db_pool_timeout,
            connect_args={
                "server_settings": {
                    "jit": "off",  # Disable JIT for predictable performance
                    "statement_timeout": "60000",  # 60 second timeout
                }
            }
        )
    return _engine


def _get_sync_engine() -> Engine:
    """Get or create the synchronous database engine."""
    global _sync_engine
    if _sync_engine is None:
        # Import here to avoid circular dependency
        from .config import settings
        
        _sync_engine = create_engine(
            settings.database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=max(5, settings.db_pool_size // 2),
            max_overflow=max(10, settings.db_max_overflow // 2),
            pool_recycle=3600
        )
    return _sync_engine


def _get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the async session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        eng = _get_engine()
        _async_session_factory = async_sessionmaker(
            eng, class_=AsyncSession, expire_on_commit=False
        )
    return _async_session_factory


def _get_sync_session_factory() -> sessionmaker[Session]:
    """Get or create the sync session factory."""
    global _sync_session_factory
    if _sync_session_factory is None:
        eng = _get_sync_engine()
        _sync_session_factory = sessionmaker(eng, class_=Session, expire_on_commit=False)
    return _sync_session_factory


# Create module-level callables for backward compatibility
# Usage: from tgstats.db import engine, async_session
# Then: async with async_session() as session: ...
engine = _get_engine
sync_engine = _get_sync_engine  
async_session = _get_async_session_factory
sync_session = _get_sync_session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session (FastAPI dependency).
    
    Usage:
        @app.get("/endpoint")
        async def endpoint(session: AsyncSession = Depends(get_session)):
            # Use session
            pass
    
    Yields:
        AsyncSession: Database session
    """
    session_factory = _get_async_session_factory()
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session (legacy name, use get_session instead).
    
    Deprecated: Use get_session() instead for consistency.
    """
    async for session in get_session():
        yield session


def get_sync_session() -> Session:
    """Get a synchronous database session.
    
    Returns:
        Session: Synchronous database session
        
    Usage:
        with get_sync_session() as session:
            # Use session
            pass
    """
    session_factory = _get_sync_session_factory()
    return session_factory()


def get_sync_engine() -> Engine:
    """Get synchronous engine for Alembic migrations and Celery.
    
    Returns:
        Engine: Synchronous database engine
    """
    return _get_sync_engine()

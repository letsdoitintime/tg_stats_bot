"""Database configuration and session management."""

import structlog
from sqlalchemy import create_engine, event, exc, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import Pool

from .core.config import settings
from .core.exceptions import DatabaseConnectionError

logger = structlog.get_logger(__name__)

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
    engine = create_async_engine(async_db_url, echo=False)
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
        },
    )

# Create sync engine for Celery and other sync operations with connection pooling
# SQLite doesn't support connection pooling
if "sqlite" in settings.database_url:
    sync_engine = create_engine(settings.database_url, echo=False)
else:
    sync_engine = create_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=max(5, settings.db_pool_size // 2),
        max_overflow=max(10, settings.db_max_overflow // 2),
        pool_recycle=3600,
    )

# Create async session factory
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Create sync session factory
sync_session = sessionmaker(sync_engine, class_=Session, expire_on_commit=False)


# Event listeners for connection pool monitoring
@event.listens_for(Pool, "connect")
def receive_connect(dbapi_conn, connection_record):
    """Log successful database connections."""
    logger.debug("Database connection established", connection_id=id(dbapi_conn))


@event.listens_for(Pool, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    """Log connection checkout from pool."""
    logger.debug("Connection checked out from pool", connection_id=id(dbapi_conn))


@event.listens_for(Pool, "checkin")
def receive_checkin(dbapi_conn, connection_record):
    """Log connection checkin to pool."""
    logger.debug("Connection returned to pool", connection_id=id(dbapi_conn))


async def get_session() -> AsyncSession:
    """Get an async database session (FastAPI dependency)."""
    async with async_session() as session:
        try:
            yield session
        except exc.OperationalError as e:
            logger.error("Database operational error in session", error=str(e))
            raise DatabaseConnectionError(f"Database connection failed: {str(e)}")
        except Exception as e:
            logger.error("Unexpected error in database session", error=str(e), exc_info=True)
            raise
        finally:
            await session.close()


async def get_db_session() -> AsyncSession:
    """Get an async database session (legacy name)."""
    async with async_session() as session:
        try:
            yield session
        except exc.OperationalError as e:
            logger.error("Database operational error in session", error=str(e))
            raise DatabaseConnectionError(f"Database connection failed: {str(e)}")
        except Exception as e:
            logger.error("Unexpected error in database session", error=str(e), exc_info=True)
            raise
        finally:
            await session.close()


def get_sync_session() -> Session:
    """Get a synchronous database session context manager."""
    return sync_session()


def get_sync_engine():
    """Get synchronous engine for Alembic migrations."""
    return sync_engine


async def verify_database_connection() -> bool:
    """
    Verify database connection is working.

    Returns:
        True if connection is successful, False otherwise
    """
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
            logger.info("Database connection verified successfully")
            return True
    except Exception as e:
        logger.error("Database connection verification failed", error=str(e), exc_info=True)
        return False


def verify_sync_database_connection() -> bool:
    """
    Verify synchronous database connection is working.

    Returns:
        True if connection is successful, False otherwise
    """
    try:
        with get_sync_session() as session:
            session.execute(text("SELECT 1"))
            logger.info("Sync database connection verified successfully")
            return True
    except Exception as e:
        logger.error("Sync database connection verification failed", error=str(e), exc_info=True)
        return False

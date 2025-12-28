"""Health check and monitoring endpoints."""

import asyncio
from fastapi import APIRouter, Response, status
from sqlalchemy import text
import structlog
import redis.asyncio as aioredis

from ..db import engine
from ..utils.metrics import metrics
from ..core.config import settings

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["health"])


async def check_redis() -> bool:
    """Check Redis connectivity."""
    try:
        redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        await redis_client.ping()
        await redis_client.close()
        return True
    except Exception as e:
        logger.error("redis_check_failed", error=str(e))
        return False


async def check_celery() -> dict:
    """Check Celery worker status."""
    try:
        from ..celery_app import celery_app

        inspect = celery_app.control.inspect()

        # Check with timeout
        stats = await asyncio.wait_for(asyncio.to_thread(inspect.stats), timeout=2.0)

        active_workers = len(stats) if stats else 0
        return {"available": active_workers > 0, "worker_count": active_workers}
    except asyncio.TimeoutError:
        logger.warning("celery_check_timeout")
        return {"available": False, "worker_count": 0, "error": "timeout"}
    except Exception as e:
        logger.error("celery_check_failed", error=str(e))
        return {"available": False, "worker_count": 0, "error": str(e)}


async def check_telegram_api() -> dict:
    """Check Telegram Bot API connectivity."""
    try:
        from ..web.app import get_bot_application

        app = get_bot_application()

        if app and app.bot:
            # Try to get bot info with timeout
            bot_info = await asyncio.wait_for(app.bot.get_me(), timeout=3.0)
            return {"available": True, "bot_username": bot_info.username, "bot_id": bot_info.id}
        else:
            return {"available": False, "error": "bot_not_initialized"}
    except asyncio.TimeoutError:
        logger.warning("telegram_api_check_timeout")
        return {"available": False, "error": "timeout"}
    except Exception as e:
        logger.error("telegram_api_check_failed", error=str(e))
        return {"available": False, "error": str(e)}


@router.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy", "service": "tgstats-bot", "environment": settings.environment}


@router.get("/health/live")
async def liveness_probe():
    """
    Kubernetes liveness probe.

    Checks if the application is running.
    Should return 200 if the app is alive, regardless of dependencies.
    """
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness_probe(response: Response):
    """
    Kubernetes readiness probe.

    Checks if the application is ready to serve traffic.
    Verifies database connectivity and other critical dependencies.
    """
    checks = {"database": False, "redis": False, "celery": {}, "telegram_api": {}, "overall": False}

    # Check database connection
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            checks["database"] = True
            logger.debug("readiness_check_db_ok")
    except Exception as e:
        logger.error("readiness_check_db_failed", error=str(e))
        checks["database"] = False

    # Check Redis
    checks["redis"] = await check_redis()

    # Check Celery (optional - don't fail if workers not running)
    checks["celery"] = await check_celery()

    # Check Telegram API
    checks["telegram_api"] = await check_telegram_api()

    # Overall status (database and telegram_api are critical)
    checks["overall"] = checks["database"] and checks["telegram_api"].get("available", False)

    if checks["overall"]:
        return {"status": "ready", "checks": checks}
    else:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "checks": checks}


@router.get("/health/startup")
async def startup_probe(response: Response):
    """
    Kubernetes startup probe.

    Checks if the application has started successfully.
    Similar to readiness but with higher tolerance for slow starts.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "started"}
    except Exception as e:
        logger.error("startup_check_failed", error=str(e))
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "starting", "error": str(e)}


@router.get("/metrics")
async def prometheus_metrics():
    """Prometheus metrics endpoint."""
    metrics_data = metrics.get_metrics()
    return Response(content=metrics_data, media_type="text/plain; version=0.0.4")


@router.get("/health/stats")
async def health_stats():
    """
    Detailed health statistics.

    Provides information about the system state.
    """
    try:
        # Get database pool stats
        pool = engine.pool
        pool_stats = {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "total": pool.size() + pool.overflow(),
        }

        return {
            "status": "healthy",
            "database_pool": pool_stats,
            "environment": settings.environment,
        }
    except Exception as e:
        logger.error("health_stats_failed", error=str(e))
        return {"status": "degraded", "error": str(e)}

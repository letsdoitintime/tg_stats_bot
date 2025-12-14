"""Health check and monitoring endpoints."""

from fastapi import APIRouter, Response, status
from sqlalchemy import text
import structlog

from ..db import engine
from ..utils.metrics import metrics
from ..core.config import settings

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "service": "tgstats-bot",
        "environment": settings.environment
    }


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
    checks = {
        "database": False,
        "overall": False
    }
    
    # Check database connection
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            checks["database"] = True
            logger.debug("readiness_check_db_ok")
    except Exception as e:
        logger.error("readiness_check_db_failed", error=str(e))
        checks["database"] = False
    
    # Overall status
    checks["overall"] = all([
        checks["database"]
    ])
    
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
    return Response(
        content=metrics_data,
        media_type="text/plain; version=0.0.4"
    )


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
            "total": pool.size() + pool.overflow()
        }
        
        return {
            "status": "healthy",
            "database_pool": pool_stats,
            "environment": settings.environment
        }
    except Exception as e:
        logger.error("health_stats_failed", error=str(e))
        return {
            "status": "degraded",
            "error": str(e)
        }

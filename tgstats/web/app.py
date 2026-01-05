"""FastAPI application for webhook endpoint and analytics API.

This is the main application file that sets up middleware, includes routers,
and provides UI endpoints. The actual API logic is in separate router modules.
"""

import uuid
from typing import Dict, Optional

import structlog
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..db import get_session
from ..models import Chat
from ..utils.sanitizer import is_safe_sql_input, is_safe_web_input
from .date_utils import parse_period
from .error_handlers import register_error_handlers
from .health import router as health_router
from .query_utils import get_group_tz_async
from .routers import analytics, chats, webhook

logger = structlog.get_logger(__name__)


# Create FastAPI app with comprehensive OpenAPI documentation
app = FastAPI(
    title="Telegram Analytics Bot API",
    description="""
## Telegram Statistics Bot - Analytics API

A comprehensive analytics platform for Telegram group statistics and insights.

### Features

* 📊 **Real-time Analytics** - Track messages, users, and engagement in real-time
* 📈 **Historical Data** - Analyze trends over time with TimescaleDB
* 🔌 **Plugin System** - Extensible architecture with hot-reloadable plugins
* 🔐 **Secure API** - Token-based authentication for all endpoints
* 🌍 **Timezone Support** - Per-group timezone configuration
* ⚡ **High Performance** - Caching, rate limiting, and optimized queries

### Authentication

All API endpoints require authentication using an admin token.
Include the token in the request header:

```
X-Admin-Token: your-secret-token-here
```

Set the admin token using the `ADMIN_API_TOKEN` environment variable.

### Rate Limiting

API requests are rate-limited to prevent abuse:
- **60 requests per minute** per client
- **1000 requests per hour** per client
- **Burst allowance** of 10 requests in 5 seconds

Rate limit information is included in response headers:
- `X-RateLimit-Limit-Minute`
- `X-RateLimit-Remaining-Minute`
- `X-RateLimit-Limit-Hour`
- `X-RateLimit-Remaining-Hour`
    """,
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "health",
            "description": "Health check and monitoring endpoints",
        },
        {
            "name": "chats",
            "description": "Chat management and statistics endpoints",
        },
        {
            "name": "analytics",
            "description": "Advanced analytics and reporting endpoints",
        },
        {
            "name": "webhook",
            "description": "Telegram webhook endpoint (internal use)",
        },
    ],
    contact={
        "name": "TG Stats Bot",
        "url": "https://github.com/letsdoitintime/tg_stats_bot",
    },
    license_info={
        "name": "MIT",
    },
)

# Parse CORS origins from comma-separated string
cors_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]

# Add middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,  # Configurable via CORS_ORIGINS env var
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


# Request ID tracing middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add unique request ID for tracing."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id

    # Bind request ID to logger context
    with structlog.contextvars.bound_contextvars(request_id=request_id):
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# Request size limit middleware
@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    """Limit incoming request size to prevent DoS attacks."""
    if request.method in ["POST", "PUT", "PATCH"]:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.max_request_size:
            raise HTTPException(
                status_code=413,
                detail=f"Request too large. Max size: {settings.max_request_size} bytes",
            )
    return await call_next(request)


# Input validation middleware
@app.middleware("http")
async def validate_query_params(request: Request, call_next):
    """Validate query parameters for potential injection attacks."""
    # Check query string parameters
    for key, value in request.query_params.items():
        if isinstance(value, str):
            # Check for SQL injection patterns
            if not is_safe_sql_input(value):
                logger.warning(
                    "suspicious_query_param", key=key, value=value[:100], path=request.url.path
                )
                raise HTTPException(
                    status_code=400, detail=f"Invalid input detected in parameter: {key}"
                )

            # Check for XSS patterns
            if not is_safe_web_input(value):
                logger.warning(
                    "suspicious_xss_query_param", key=key, value=value[:100], path=request.url.path
                )
                raise HTTPException(
                    status_code=400, detail=f"Invalid input detected in parameter: {key}"
                )

    return await call_next(request)


# Include routers
app.include_router(health_router)
app.include_router(webhook.router)
app.include_router(chats.router)
app.include_router(analytics.router)

# Register error handlers
register_error_handlers(app)

# Templates for minimal UI
templates = Jinja2Templates(directory="tgstats/web/templates")


# Internal UI endpoints (no authentication required)
@app.get("/internal/chats/{chat_id}/summary")
async def ui_get_chat_summary(
    chat_id: int,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    session: AsyncSession = Depends(get_session),
):
    """Get chat summary for UI (no auth required)."""
    # First check if chat exists
    chat = await session.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    tz = await get_group_tz_async(chat_id, session)
    start_utc, end_utc, days = parse_period(from_date, to_date, tz)

    query = text(
        """
        SELECT
            COUNT(*) as total_messages,
            COUNT(DISTINCT messages.user_id) as unique_users,
            COUNT(DISTINCT messages.user_id)::float as avg_daily_users,
            COUNT(DISTINCT CASE WHEN memberships.joined_at BETWEEN :start_utc AND :end_utc THEN memberships.user_id END) as new_users,
            COUNT(DISTINCT CASE WHEN memberships.left_at BETWEEN :start_utc AND :end_utc THEN memberships.user_id END) as left_users
        FROM messages
        LEFT JOIN memberships ON messages.user_id = memberships.user_id AND messages.chat_id = memberships.chat_id
        WHERE messages.chat_id = :chat_id
        AND messages.date BETWEEN :start_utc AND :end_utc
    """
    )

    result = (
        await session.execute(
            query, {"chat_id": chat_id, "start_utc": start_utc, "end_utc": end_utc}
        )
    ).fetchone()

    # Even if no messages found, return zeros instead of 404
    if not result or result[0] is None:
        return {
            "total_messages": 0,
            "unique_users": 0,
            "avg_daily_users": 0.0,
            "new_users": 0,
            "left_users": 0,
            "start_date": start_utc.isoformat(),
            "end_date": end_utc.isoformat(),
            "days": (end_utc - start_utc).days + 1,
        }

    return {
        "total_messages": result[0] or 0,
        "unique_users": result[1] or 0,
        "avg_daily_users": float(result[2] or 0),
        "new_users": result[3] or 0,
        "left_users": result[4] or 0,
        "start_date": start_utc.isoformat(),
        "end_date": end_utc.isoformat(),
        "days": (end_utc - start_utc).days + 1,
    }


@app.get("/internal/chats/{chat_id}/timeseries")
async def ui_get_chat_timeseries(
    chat_id: int,
    metric: str = Query(..., pattern="^(messages|dau)$"),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    session: AsyncSession = Depends(get_session),
):
    """Get chat timeseries for UI (no auth required)."""
    # First check if chat exists
    chat = await session.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    tz = await get_group_tz_async(chat_id, session)
    start_utc, end_utc, days = parse_period(from_date, to_date, tz)

    if metric == "messages":
        query = text(
            """
            SELECT DATE(date) as day, COUNT(*) as value
            FROM messages
            WHERE chat_id = :chat_id
            AND date BETWEEN :start_utc AND :end_utc
            GROUP BY DATE(date)
            ORDER BY day
        """
        )
    else:  # dau
        query = text(
            """
            SELECT DATE(date) as day, COUNT(DISTINCT user_id) as value
            FROM messages
            WHERE chat_id = :chat_id
            AND date BETWEEN :start_utc AND :end_utc
            GROUP BY DATE(date)
            ORDER BY day
        """
        )

    result = await session.execute(
        query, {"chat_id": chat_id, "start_utc": start_utc, "end_utc": end_utc}
    )

    return [{"day": str(row[0]), "value": row[1]} for row in result]


@app.get("/internal/chats/{chat_id}/heatmap")
async def ui_get_chat_heatmap(
    chat_id: int,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    session: AsyncSession = Depends(get_session),
):
    """Get chat heatmap for UI (no auth required)."""
    # First check if chat exists
    chat = await session.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    tz = await get_group_tz_async(chat_id, session)
    start_utc, end_utc, days = parse_period(from_date, to_date, tz)

    query = text(
        """
        SELECT
            EXTRACT(dow FROM date) as day_of_week,
            EXTRACT(hour FROM date) as hour,
            COUNT(*) as message_count
        FROM messages
        WHERE chat_id = :chat_id
        AND date BETWEEN :start_utc AND :end_utc
        GROUP BY EXTRACT(dow FROM date), EXTRACT(hour FROM date)
        ORDER BY day_of_week, hour
    """
    )

    result = await session.execute(
        query, {"chat_id": chat_id, "start_utc": start_utc, "end_utc": end_utc}
    )

    # Initialize matrix with zeros
    matrix = [[0 for _ in range(24)] for _ in range(7)]

    # Fill in the actual data
    for row in result:
        dow = int(row[0])  # 0=Sunday, 1=Monday, etc.
        hour = int(row[1])
        count = row[2]

        # Rotate: Sunday (0) -> 6, Monday (1) -> 0, etc.
        rotated_dow = (dow + 6) % 7
        matrix[rotated_dow][hour] = count

    return {
        "weekdays": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "hours": list(range(24)),
        "data": matrix,
    }


# Minimal Web UI
@app.get("/ui", response_class=HTMLResponse)
async def ui_chat_list(request: Request, session: AsyncSession = Depends(get_session)):
    """List all chats in a simple web interface."""
    # Get chats (reuse API logic but without auth)
    # For simplicity, use a basic query that works with both TimescaleDB and PostgreSQL
    query = text(
        """
        SELECT c.chat_id, c.title, 0 as msg_count_30d, 0 as avg_dau_30d
        FROM chats c
        ORDER BY c.chat_id
    """
    )

    chats = (await session.execute(query)).fetchall()

    return templates.TemplateResponse("chat_list.html", {"request": request, "chats": chats})


@app.get("/ui/chat/{chat_id}", response_class=HTMLResponse)
async def ui_chat_detail(
    request: Request, chat_id: int, session: AsyncSession = Depends(get_session)
):
    """Show chat details with analytics."""
    # Get chat info
    chat = await session.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    return templates.TemplateResponse(
        "chat_detail.html", {"request": request, "chat": chat, "chat_id": chat_id}
    )


@app.get("/")
async def root() -> Dict[str, str]:
    """Root endpoint with service information."""
    return {
        "service": "Telegram Analytics Bot",
        "version": "0.2.0",
        "status": "running",
        "api_docs": "/docs",
        "ui": "/ui",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8010)

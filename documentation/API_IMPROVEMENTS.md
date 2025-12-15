# API Best Practices and Improvement Guide

## Overview

This document outlines the standards and best practices for the FastAPI endpoints in the TG Stats Bot project.

## Current Architecture

The API is built with:
- **FastAPI** - Modern async web framework
- **Pydantic** - Request/response validation
- **SQLAlchemy 2.x** - Async ORM
- **JWT/Token Auth** - Admin API token authentication
- **CORS** - Cross-origin resource sharing

## Improvements Implemented

### 1. Standardized Error Responses ✅

All API errors now return a consistent format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message",
    "details": {}
  },
  "request_id": "uuid-here"
}
```

Error codes include:
- `VALIDATION_ERROR` - Request validation failed (422)
- `NOT_FOUND` - Resource not found (404)
- `UNAUTHORIZED` - Missing or invalid auth (401)
- `FORBIDDEN` - Insufficient permissions (403)
- `CHAT_NOT_SETUP` - Chat requires setup (428)
- `DATABASE_ERROR` - Database operation failed (500)
- `INTERNAL_ERROR` - Unhandled exception (500)

### 2. Request ID Tracing ✅

Every request gets a unique ID for tracing through logs:
- Auto-generated UUID if not provided
- Can be provided via `X-Request-ID` header
- Included in all log entries
- Returned in response headers
- Included in error responses

### 3. Configuration Validation ✅

Settings are validated at startup:
- Database connection parameters
- Bot configuration
- Redis connection
- Security settings
- Performance tuning

## API Design Standards

### Endpoint Naming

Use RESTful conventions:
```
GET    /api/chats              # List resources
GET    /api/chats/{id}         # Get single resource
POST   /api/chats              # Create resource
PUT    /api/chats/{id}         # Update resource (full)
PATCH  /api/chats/{id}         # Update resource (partial)
DELETE /api/chats/{id}         # Delete resource
```

### Versioning Strategy

For major breaking changes, use path versioning:
```
/api/v1/chats
/api/v2/chats
```

Current endpoints without version prefix are considered v1.

### Pagination

Use query parameters for pagination:
```
GET /api/chats?page=1&per_page=25
```

Response should include metadata:
```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "per_page": 25,
    "total": 100,
    "pages": 4
  }
}
```

### Filtering and Sorting

Use query parameters:
```
GET /api/chats?sort=title&order=asc&filter[type]=group
GET /api/users?search=john&left=false
```

### Date/Time Handling

- Accept ISO 8601 format: `2024-12-15T10:30:00Z`
- Support date-only: `2024-12-15`
- Respect timezone settings from group configuration
- Convert to UTC for storage
- Return in group's timezone

## Security Best Practices

### Authentication

Current implementation:
```python
from tgstats.web.auth import verify_api_token

@app.get("/api/protected")
async def protected_route(
    token: str = Depends(verify_api_token)
):
    ...
```

### Rate Limiting

Should be implemented per endpoint:
```python
from tgstats.utils.rate_limiter import rate_limiter

@app.get("/api/resource")
async def get_resource(request: Request):
    # Check rate limit
    if rate_limiter.is_limited(request.client.host):
        raise HTTPException(429, "Rate limit exceeded")
    ...
```

### Input Validation

Always use Pydantic models:
```python
from pydantic import BaseModel, Field

class CreateChatRequest(BaseModel):
    chat_id: int = Field(..., gt=-9999999999, lt=9999999999)
    title: str = Field(..., min_length=1, max_length=255)
```

### SQL Injection Prevention

Use parameterized queries:
```python
# Good ✅
result = await session.execute(
    select(Chat).where(Chat.chat_id == chat_id)
)

# Bad ❌
result = await session.execute(
    text(f"SELECT * FROM chats WHERE chat_id = {chat_id}")
)
```

## Performance Optimization

### Database Queries

1. **Use select loading** to avoid N+1 queries:
```python
from sqlalchemy.orm import selectinload

result = await session.execute(
    select(Chat)
    .options(selectinload(Chat.settings))
    .where(Chat.chat_id == chat_id)
)
```

2. **Limit result sets**:
```python
result = await session.execute(
    select(Message)
    .where(Message.chat_id == chat_id)
    .limit(1000)
)
```

3. **Use pagination** for large datasets:
```python
result = await session.execute(
    select(Message)
    .where(Message.chat_id == chat_id)
    .offset((page - 1) * per_page)
    .limit(per_page)
)
```

### Caching

For expensive queries, use caching:
```python
from tgstats.utils.cache import cache

@cache(ttl=300)  # Cache for 5 minutes
async def get_chat_stats(chat_id: int):
    # Expensive query
    ...
```

### Response Compression

Already enabled via GZipMiddleware:
```python
app.add_middleware(GZipMiddleware, minimum_size=1000)
```

## Testing Guidelines

### Unit Tests

Test individual endpoints in isolation:
```python
from httpx import AsyncClient

async def test_get_chat():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/chats/123")
        assert response.status_code == 200
```

### Integration Tests

Test full request flow with database:
```python
async def test_create_chat_integration(db_session):
    # Test with real database
    ...
```

### Load Tests

Use tools like locust or k6:
```python
# locustfile.py
from locust import HttpUser, task

class APIUser(HttpUser):
    @task
    def get_chats(self):
        self.client.get("/api/chats")
```

## Monitoring and Observability

### Logging

Use structured logging:
```python
import structlog

logger = structlog.get_logger(__name__)

logger.info(
    "api_request",
    path=request.url.path,
    method=request.method,
    request_id=request.state.request_id,
    duration_ms=duration
)
```

### Metrics

Track important metrics:
- Request count by endpoint
- Request duration (p50, p95, p99)
- Error rate by error code
- Database query time
- Cache hit rate

### Health Checks

Implement comprehensive health checks:
```python
@app.get("/healthz")
async def health_check():
    return {
        "status": "healthy",
        "database": await check_db_connection(),
        "redis": await check_redis_connection(),
        "bot": await check_bot_connection()
    }
```

## API Documentation

### OpenAPI/Swagger

FastAPI auto-generates docs at `/docs` and `/redoc`.

Enhance with:
- Detailed descriptions
- Request/response examples
- Error code documentation

```python
@app.get(
    "/api/chats/{chat_id}",
    response_model=ChatResponse,
    responses={
        404: {"description": "Chat not found"},
        401: {"description": "Unauthorized"}
    },
    summary="Get chat details",
    description="Retrieve detailed information about a specific chat"
)
async def get_chat(chat_id: int):
    ...
```

## Migration Strategy

When making breaking changes:

1. **Add new endpoint** with version prefix
2. **Deprecate old endpoint** with warning header
3. **Update documentation** with migration guide
4. **Remove old endpoint** after deprecation period

Example deprecation:
```python
@app.get("/api/old-endpoint")
async def old_endpoint():
    return Response(
        headers={
            "Deprecation": "true",
            "Sunset": "2025-06-01",
            "Link": "</api/v2/new-endpoint>; rel=\"successor-version\""
        }
    )
```

## Future Improvements

1. **API Versioning**: Implement v2 with path prefix
2. **GraphQL**: Consider for complex queries
3. **WebSockets**: Real-time updates
4. **API Keys**: Per-user API keys with scopes
5. **Rate Limiting**: Per-endpoint and per-user limits
6. **Request Validation**: More strict validation rules
7. **Response Pagination**: Cursor-based pagination
8. **Batch Endpoints**: Support batch operations
9. **Field Selection**: Allow clients to specify fields
10. **API Gateway**: Consider Kong or similar for production

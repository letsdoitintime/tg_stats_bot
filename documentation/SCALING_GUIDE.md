# Scaling Guide for TG Stats Bot

## Overview

This guide covers strategies for scaling the TG Stats Bot to handle increased load, whether from more chats, higher message volume, or more API requests.

## Table of Contents

- [Current Architecture](#current-architecture)
- [Performance Baselines](#performance-baselines)
- [Vertical Scaling](#vertical-scaling)
- [Horizontal Scaling](#horizontal-scaling)
- [Database Scaling](#database-scaling)
- [Caching Strategies](#caching-strategies)
- [Monitoring & Alerting](#monitoring--alerting)
- [Load Testing](#load-testing)

---

## Current Architecture

**Single-Server Setup:**
```
┌─────────────────────────────────────┐
│         Application Server          │
│                                     │
│  ┌──────────┐  ┌─────────┐         │
│  │   Bot    │  │FastAPI  │         │
│  │  Main    │  │  Web    │         │
│  └──────────┘  └─────────┘         │
│                                     │
│  ┌──────────┐  ┌─────────┐         │
│  │  Celery  │  │ Celery  │         │
│  │  Worker  │  │  Beat   │         │
│  └──────────┘  └─────────┘         │
└─────────────────────────────────────┘
           │              │
           ▼              ▼
    ┌──────────┐    ┌─────────┐
    │PostgreSQL│    │  Redis  │
    │ /TimescaleDB  │         │
    └──────────┘    └─────────┘
```

---

## Performance Baselines

### Expected Performance (Single Server)

**Hardware: 4 CPU, 8GB RAM, SSD**

| Metric | Baseline |
|--------|----------|
| Message processing | ~500-1000 msg/sec |
| API requests | ~100-200 req/sec |
| Concurrent chats | 100-500 |
| Database writes | ~1000/sec |
| Database reads | ~5000/sec |

### Bottlenecks to Watch

1. **Database connections** - Pool exhaustion
2. **Memory usage** - OOM from large result sets
3. **CPU usage** - Message processing load
4. **Network I/O** - Telegram API rate limits
5. **Disk I/O** - Database write performance

---

## Vertical Scaling

### Database Server

**Initial:** 2 CPU, 4GB RAM
**Target:** 8 CPU, 32GB RAM

```yaml
# docker-compose.yml
services:
  db:
    image: timescale/timescaledb:latest-pg15
    shm_size: 8g  # Shared memory for PostgreSQL
    environment:
      - POSTGRES_SHARED_BUFFERS=8GB
      - POSTGRES_EFFECTIVE_CACHE_SIZE=24GB
      - POSTGRES_WORK_MEM=128MB
      - POSTGRES_MAINTENANCE_WORK_MEM=2GB
      - POSTGRES_MAX_CONNECTIONS=200
```

**PostgreSQL Configuration (`postgresql.conf`):**

```conf
# Memory Settings
shared_buffers = 8GB
effective_cache_size = 24GB
work_mem = 128MB
maintenance_work_mem = 2GB

# Checkpoints
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100

# Parallelism
max_worker_processes = 8
max_parallel_workers_per_gather = 4
max_parallel_workers = 8

# Connections
max_connections = 200
```

### Application Server

**Initial:** 2 CPU, 4GB RAM
**Target:** 8 CPU, 16GB RAM

**.env Configuration:**

```env
# Database pool settings
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40

# Bot connection pool
BOT_CONNECTION_POOL_SIZE=16

# Celery workers
CELERY_WORKERS=8
```

---

## Horizontal Scaling

### Multi-Server Architecture

```
                  ┌─────────────┐
                  │Load Balancer│
                  └──────┬──────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
   ┌─────────┐      ┌─────────┐     ┌─────────┐
   │ Bot     │      │ Bot     │     │ Bot     │
   │ Server 1│      │ Server 2│     │ Server 3│
   └────┬────┘      └────┬────┘     └────┬────┘
        │                │                │
        └────────────────┼────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
   ┌──────────┐    ┌─────────┐     ┌──────────┐
   │PostgreSQL│    │  Redis  │     │  Celery  │
   │  Primary │    │ Cluster │     │  Workers │
   └─────┬────┘    └─────────┘     └──────────┘
         │
    ┌────┴─────┐
    ▼          ▼
 ┌──────┐  ┌──────┐
 │Read  │  │Read  │
 │Replica│ │Replica│
 └──────┘  └──────┘
```

### Bot Webhook Mode (Multiple Instances)

When running multiple bot instances, use **webhook mode** instead of polling:

**.env:**
```env
MODE=webhook
WEBHOOK_URL=https://your-domain.com/webhook
```

**nginx Load Balancer:**

```nginx
upstream bot_servers {
    least_conn;  # Use least connections algorithm
    server bot1:8000 max_fails=3 fail_timeout=30s;
    server bot2:8000 max_fails=3 fail_timeout=30s;
    server bot3:8000 max_fails=3 fail_timeout=30s;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    location /webhook {
        proxy_pass http://bot_servers;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # Telegram webhook specific
        proxy_connect_timeout 60s;
        proxy_read_timeout 60s;
        proxy_send_timeout 60s;
    }
}
```

### Celery Workers (Separate Servers)

**docker-compose.celery.yml:**

```yaml
version: '3.8'

services:
  celery-worker-1:
    image: tgstats:latest
    command: celery -A tgstats.celery_app worker -l INFO -c 4
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
    deploy:
      replicas: 3

  celery-beat:
    image: tgstats:latest
    command: celery -A tgstats.celery_app beat -l INFO
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
    deploy:
      replicas: 1  # Only 1 beat scheduler
```

---

## Database Scaling

### Read Replicas

**Setup PostgreSQL Streaming Replication:**

**On Primary:**
```sql
-- Create replication user
CREATE USER replicator WITH REPLICATION ENCRYPTED PASSWORD 'strong_password';

-- Allow replication connections
-- Add to pg_hba.conf:
-- host replication replicator replica_ip/32 md5
```

**On Replica:**
```bash
# Stop PostgreSQL
pg_basebackup -h primary_ip -D /var/lib/postgresql/data -U replicator -P -v

# Create recovery.conf or standby.signal (PG12+)
touch /var/lib/postgresql/data/standby.signal

# Start PostgreSQL
```

**Application Configuration:**

```python
# tgstats/db.py
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

# Write database
write_engine = create_async_engine(
    settings.database_url,
    pool_size=20,
    max_overflow=40
)

# Read replicas
read_engines = [
    create_async_engine(
        settings.read_replica_url_1,
        pool_size=10,
        max_overflow=20
    ),
    create_async_engine(
        settings.read_replica_url_2,
        pool_size=10,
        max_overflow=20
    )
]

# Use round-robin for read queries
import random

def get_read_engine():
    return random.choice(read_engines)
```

### TimescaleDB Compression

Enable compression for older data:

```sql
-- Enable compression on hypertable
ALTER TABLE messages SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'chat_id'
);

-- Add compression policy (compress data older than 30 days)
SELECT add_compression_policy('messages', INTERVAL '30 days');
```

### Partitioning Strategy

For non-TimescaleDB setups, use native PostgreSQL partitioning:

```sql
-- Create partitioned table
CREATE TABLE messages_partitioned (
    LIKE messages INCLUDING ALL
) PARTITION BY RANGE (date);

-- Create partitions (one per month)
CREATE TABLE messages_2025_01 PARTITION OF messages_partitioned
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

CREATE TABLE messages_2025_02 PARTITION OF messages_partitioned
    FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');

-- Auto-create partitions with pg_partman extension
```

---

## Caching Strategies

### Redis Caching Layer

**Install Redis Cluster:**

```yaml
# docker-compose.redis.yml
version: '3.8'

services:
  redis-master:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    ports:
      - "6379:6379"
  
  redis-replica-1:
    image: redis:7-alpine
    command: redis-server --replicaof redis-master 6379
  
  redis-replica-2:
    image: redis:7-alpine
    command: redis-server --replicaof redis-master 6379
```

**Implement Caching:**

```python
# tgstats/utils/cache_enhanced.py
import redis
import pickle
from functools import wraps

redis_client = redis.from_url(settings.redis_url)

def cache_result(ttl=300, key_prefix=""):
    """Cache function result in Redis."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{key_prefix}:{func.__name__}:{hash(str(args))}"
            
            # Try to get from cache
            cached = redis_client.get(cache_key)
            if cached:
                return pickle.loads(cached)
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Store in cache
            redis_client.setex(
                cache_key,
                ttl,
                pickle.dumps(result)
            )
            
            return result
        return wrapper
    return decorator


# Usage in services
@cache_result(ttl=600, key_prefix="chat_stats")
async def get_chat_summary(chat_id, from_date, to_date):
    # Expensive database query
    pass
```

### Application-Level Caching

```python
# tgstats/utils/lru_cache.py
from functools import lru_cache
from datetime import datetime, timedelta

class TTLCache:
    """Simple in-memory cache with TTL."""
    
    def __init__(self, ttl_seconds=300):
        self.cache = {}
        self.ttl = ttl_seconds
    
    def get(self, key):
        if key in self.cache:
            value, expires = self.cache[key]
            if datetime.now() < expires:
                return value
            else:
                del self.cache[key]
        return None
    
    def set(self, key, value):
        expires = datetime.now() + timedelta(seconds=self.ttl)
        self.cache[key] = (value, expires)
    
    def clear(self):
        self.cache.clear()

# Global cache instances
chat_cache = TTLCache(ttl_seconds=600)
user_cache = TTLCache(ttl_seconds=300)
```

---

## Monitoring & Alerting

### Prometheus Metrics

**Install Prometheus:**

```yaml
# docker-compose.monitoring.yml
services:
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
  
  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
```

**Add Metrics to Application:**

```python
# tgstats/utils/metrics_enhanced.py
from prometheus_client import Counter, Histogram, Gauge

# Counters
messages_processed = Counter(
    'messages_processed_total',
    'Total messages processed',
    ['chat_id']
)

api_requests = Counter(
    'api_requests_total',
    'Total API requests',
    ['endpoint', 'method', 'status']
)

# Histograms
message_processing_time = Histogram(
    'message_processing_seconds',
    'Time to process message'
)

query_duration = Histogram(
    'database_query_seconds',
    'Database query duration',
    ['query_name']
)

# Gauges
active_chats = Gauge(
    'active_chats',
    'Number of active chats'
)

database_connections = Gauge(
    'database_connections',
    'Number of active database connections'
)
```

### Health Checks

**Enhanced Health Check Endpoint:**

```python
# tgstats/web/health_enhanced.py
@app.get("/healthz/detailed")
async def detailed_health():
    """Detailed health check with component status."""
    health = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {}
    }
    
    # Check database
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        health["components"]["database"] = "healthy"
    except Exception as e:
        health["components"]["database"] = f"unhealthy: {str(e)}"
        health["status"] = "degraded"
    
    # Check Redis
    try:
        redis_client.ping()
        health["components"]["redis"] = "healthy"
    except Exception as e:
        health["components"]["redis"] = f"unhealthy: {str(e)}"
        health["status"] = "degraded"
    
    # Check Telegram API
    try:
        bot_app = get_bot_application()
        await bot_app.bot.get_me()
        health["components"]["telegram"] = "healthy"
    except Exception as e:
        health["components"]["telegram"] = f"unhealthy: {str(e)}"
        health["status"] = "degraded"
    
    return health
```

---

## Load Testing

### Using Locust

**install:**
```bash
pip install locust
```

**locustfile.py:**

```python
from locust import HttpUser, task, between
import random

class TGStatsUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        """Setup - run once per user."""
        self.headers = {
            "X-Admin-Token": "your_token_here"
        }
    
    @task(3)
    def get_chats(self):
        """Get chat list - weight 3."""
        self.client.get("/api/chats", headers=self.headers)
    
    @task(2)
    def get_timeseries(self):
        """Get timeseries data - weight 2."""
        chat_id = -1001234567890
        self.client.get(
            f"/api/chats/{chat_id}/timeseries",
            params={
                "metric": "messages",
                "from": "2025-01-01",
                "to": "2025-01-31"
            },
            headers=self.headers
        )
    
    @task(1)
    def get_users(self):
        """Get user statistics - weight 1."""
        chat_id = -1001234567890
        self.client.get(
            f"/api/chats/{chat_id}/users",
            params={"page": random.randint(1, 10)},
            headers=self.headers
        )
```

**Run load test:**
```bash
locust -f locustfile.py --host=http://localhost:8000
# Open http://localhost:8089 in browser
```

---

## Scaling Checklist

### Before Scaling

- [ ] Enable monitoring and metrics
- [ ] Set up alerts for key metrics
- [ ] Document current performance baselines
- [ ] Identify bottlenecks with profiling
- [ ] Test backup and recovery procedures

### Vertical Scaling (Scale Up)

- [ ] Increase database server resources
- [ ] Tune PostgreSQL configuration
- [ ] Increase connection pool sizes
- [ ] Add more memory for caching
- [ ] Enable compression and optimization

### Horizontal Scaling (Scale Out)

- [ ] Set up load balancer
- [ ] Deploy multiple bot instances
- [ ] Configure read replicas
- [ ] Implement caching layer
- [ ] Distribute Celery workers

### Post-Scaling

- [ ] Monitor resource utilization
- [ ] Check for new bottlenecks
- [ ] Validate data consistency
- [ ] Test failover scenarios
- [ ] Document new architecture

---

## Additional Resources

- [PostgreSQL Performance Tuning](https://wiki.postgresql.org/wiki/Performance_Optimization)
- [TimescaleDB Best Practices](https://docs.timescale.com/timescaledb/latest/overview/core-concepts/best-practices/)
- [Redis Cluster Tutorial](https://redis.io/topics/cluster-tutorial)
- [Telegram Bot API Limits](https://core.telegram.org/bots/faq#broadcasting-to-users)

---

For questions about scaling, create an issue in the repository.

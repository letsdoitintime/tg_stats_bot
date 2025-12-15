# Resource Limits Configuration Guide

## Problem
Multiple Telegram bots running simultaneously can cause CPU load to spike to 200%+ (multiple cores), making the server unresponsive and requiring hard reboots.

## Solution Overview
Implement multi-layered resource limits:
1. **Supervisor resource limits** (cgroups) - Primary method
2. **systemd resource controls** - Alternative/complementary  
3. **Python process limits** - Application-level throttling
4. **Celery worker limits** - Task concurrency control

---

## 1. Supervisor with cgroups (Recommended)

### Installation
```bash
# Install cgroup tools
sudo apt-get update
sudo apt-get install -y cgroup-tools libcgroup1

# Enable cgroups in supervisor
sudo mkdir -p /sys/fs/cgroup/cpu/supervisor
sudo mkdir -p /sys/fs/cgroup/memory/supervisor
```

### Configuration

Edit `/etc/supervisor/conf.d/tgstats.conf`:

```ini
[program:tgstats-bot]
command=/TelegramBots/Chat_Stats/venv/bin/python -m tgstats.bot_main
directory=/TelegramBots/Chat_Stats
user=root
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/TelegramBots/Chat_Stats/logs/bot.log
stderr_logfile=/TelegramBots/Chat_Stats/logs/bot_error.log

; CPU limit: 50% of one core (500 = 50% of 1000 = 1 core)
; Adjust as needed: 1000 = 1 core, 2000 = 2 cores, 500 = 0.5 core
cpus=0.5

; Memory limit: 512MB
memoryswap=0
memory_limit_in_bytes=536870912

; Nice level (process priority: -20 to 19, higher = lower priority)
priority=10

[program:tgstats-celery]
command=/TelegramBots/Chat_Stats/venv/bin/celery -A tgstats.celery_tasks worker --loglevel=info --concurrency=2 --max-tasks-per-child=100
directory=/TelegramBots/Chat_Stats
user=root
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/TelegramBots/Chat_Stats/logs/celery.log
stderr_logfile=/TelegramBots/Chat_Stats/logs/celery_error.log
cpus=0.5
memory_limit_in_bytes=536870912
priority=15
stopwaitsecs=60

[program:tgstats-celery-beat]
command=/TelegramBots/Chat_Stats/venv/bin/celery -A tgstats.celery_tasks beat --loglevel=info
directory=/TelegramBots/Chat_Stats
user=root
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/TelegramBots/Chat_Stats/logs/celery_beat.log
stderr_logfile=/TelegramBots/Chat_Stats/logs/celery_beat_error.log
cpus=0.25
memory_limit_in_bytes=268435456
priority=20

[program:tgstats-api]
command=/TelegramBots/Chat_Stats/venv/bin/uvicorn tgstats.web.app:app --host 0.0.0.0 --port 8000 --log-level warning --workers 2
directory=/TelegramBots/Chat_Stats
user=root
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/TelegramBots/Chat_Stats/logs/api.log
stderr_logfile=/TelegramBots/Chat_Stats/logs/api_error.log
cpus=0.5
memory_limit_in_bytes=536870912
priority=10

[group:tgstats]
programs=tgstats-bot,tgstats-celery,tgstats-celery-beat,tgstats-api
priority=999
```

### Apply Configuration
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl restart tgstats:*
```

---

## 2. systemd Resource Controls (Alternative)

If using systemd instead of supervisor:

Edit `/TelegramBots/Chat_Stats/tgstats-bot.service`:

```ini
[Unit]
Description=TG Stats Bot - Telegram Statistics Bot
After=network.target postgresql.service redis.service
Requires=postgresql.service

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/TelegramBots/Chat_Stats
Environment=PATH=/TelegramBots/Chat_Stats/venv/bin

ExecStartPre=/TelegramBots/Chat_Stats/venv/bin/alembic upgrade head
ExecStart=/TelegramBots/Chat_Stats/venv/bin/python -m tgstats.bot_main

Restart=always
RestartSec=10

# Resource Limits
CPUQuota=50%           # Limit to 50% of one CPU core
MemoryMax=512M         # Maximum memory
MemoryHigh=400M        # Soft limit - triggers early GC
TasksMax=50            # Maximum number of threads/processes

# I/O Limits
IOWeight=100           # I/O priority (1-10000, lower = less priority)

# Nice level
Nice=5                 # Process priority (negative = higher, positive = lower)

# Kill behavior
KillMode=mixed         # SIGTERM to main, SIGKILL to others
TimeoutStopSec=30      # Grace period before force kill

StandardOutput=journal
StandardError=journal
SyslogIdentifier=tgstats-bot

[Install]
WantedBy=multi-user.target
```

Similar files for celery services:

**tgstats-celery.service**:
```ini
[Unit]
Description=TG Stats Celery Worker
After=network.target postgresql.service redis.service
Requires=redis.service

[Service]
Type=simple
User=root
WorkingDirectory=/TelegramBots/Chat_Stats
Environment=PATH=/TelegramBots/Chat_Stats/venv/bin

ExecStart=/TelegramBots/Chat_Stats/venv/bin/celery -A tgstats.celery_tasks worker --loglevel=info --concurrency=2 --max-tasks-per-child=100

Restart=always
RestartSec=10

# Resource Limits
CPUQuota=50%
MemoryMax=512M
MemoryHigh=400M
TasksMax=100

Nice=10

StandardOutput=journal
StandardError=journal
SyslogIdentifier=tgstats-celery

[Install]
WantedBy=multi-user.target
```

Apply systemd changes:
```bash
sudo systemctl daemon-reload
sudo systemctl restart tgstats-bot
sudo systemctl restart tgstats-celery
```

---

## 3. Application-Level Throttling

### Bot Handler Rate Limiting

Create `/TelegramBots/Chat_Stats/tgstats/utils/rate_limiter.py`:

```python
"""Rate limiter for bot handlers to prevent resource exhaustion."""

import asyncio
from functools import wraps
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, Tuple
import structlog

logger = structlog.get_logger(__name__)


class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self, max_calls: int, time_window: int):
        """
        Args:
            max_calls: Maximum number of calls allowed
            time_window: Time window in seconds
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls: Dict[int, list] = defaultdict(list)
        self._lock = asyncio.Lock()
    
    async def is_allowed(self, user_id: int) -> Tuple[bool, int]:
        """
        Check if user is allowed to make a request.
        
        Returns:
            Tuple of (is_allowed, seconds_until_reset)
        """
        async with self._lock:
            now = datetime.now()
            cutoff = now - timedelta(seconds=self.time_window)
            
            # Remove old entries
            self.calls[user_id] = [
                call_time for call_time in self.calls[user_id]
                if call_time > cutoff
            ]
            
            if len(self.calls[user_id]) < self.max_calls:
                self.calls[user_id].append(now)
                return True, 0
            
            # Calculate time until oldest call expires
            oldest_call = min(self.calls[user_id])
            reset_time = (oldest_call + timedelta(seconds=self.time_window) - now).total_seconds()
            
            return False, int(reset_time)


# Global rate limiters
command_limiter = RateLimiter(max_calls=10, time_window=60)  # 10 commands per minute
stats_limiter = RateLimiter(max_calls=3, time_window=300)    # 3 stats per 5 minutes


def rate_limit(limiter: RateLimiter):
    """Decorator to rate limit handler functions."""
    def decorator(func):
        @wraps(func)
        async def wrapper(update, context, *args, **kwargs):
            user_id = update.effective_user.id
            allowed, reset_time = await limiter.is_allowed(user_id)
            
            if not allowed:
                logger.warning(
                    "rate_limit_exceeded",
                    user_id=user_id,
                    handler=func.__name__,
                    reset_in=reset_time
                )
                await update.message.reply_text(
                    f"⏱ Too many requests. Please wait {reset_time} seconds."
                )
                return
            
            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator
```

Usage in handlers:
```python
from tgstats.utils.rate_limiter import rate_limit, command_limiter, stats_limiter

@rate_limit(command_limiter)
@with_db_session
async def my_handler(update, context, session):
    # Your handler code
    pass
```

### Celery Worker Configuration

Update `tgstats/celery_app.py` to add resource limits:

```python
# Add to celery configuration
app.conf.update(
    # Worker limits
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks (prevents memory leaks)
    worker_max_memory_per_child=512000,  # 512MB per worker
    worker_disable_rate_limits=False,
    
    # Task limits
    task_time_limit=300,  # Hard timeout: 5 minutes
    task_soft_time_limit=240,  # Soft timeout: 4 minutes
    
    # Concurrency
    worker_concurrency=2,  # Number of concurrent workers
    worker_prefetch_multiplier=1,  # Tasks to prefetch per worker
    
    # Task routing priorities
    task_default_priority=5,
    task_inherit_parent_priority=True,
)
```

---

## 4. PostgreSQL Connection Pooling

Update `tgstats/db.py` to limit database connections:

```python
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=5,           # Maximum pool size (down from default 10)
    max_overflow=5,        # Maximum overflow connections
    pool_timeout=30,       # Timeout waiting for connection
    pool_recycle=3600,     # Recycle connections after 1 hour
    pool_pre_ping=True,    # Verify connections before use
)
```

---

## 5. Monitoring Script

Create `/TelegramBots/Chat_Stats/scripts/monitor_resources.sh`:

```bash
#!/bin/bash
# Monitor resource usage of TG Stats processes

echo "=== TG Stats Resource Monitor ==="
echo "Date: $(date)"
echo ""

echo "--- CPU & Memory Usage ---"
ps aux | grep -E "tgstats|celery" | grep -v grep | awk '{printf "%-50s CPU: %5s%%  MEM: %5s%%  RSS: %8s KB\n", substr($11,1,50), $3, $4, $6}'

echo ""
echo "--- Total CPU Usage ---"
top -bn1 | grep "Cpu(s)" | awk '{print "CPU: " $2 " user, " $4 " system, " $8 " idle"}'

echo ""
echo "--- Memory Usage ---"
free -h | grep -E "Mem|Swap"

echo ""
echo "--- Disk I/O ---"
iostat -x 1 2 | tail -n +4

echo ""
echo "--- Network Stats ---"
ss -s

echo ""
echo "--- PostgreSQL Connections ---"
psql -U postgres -d tgstats -c "SELECT count(*) as active_connections FROM pg_stat_activity WHERE state = 'active';" 2>/dev/null || echo "Cannot connect to PostgreSQL"

echo ""
echo "--- Redis Memory ---"
redis-cli INFO memory | grep -E "used_memory_human|used_memory_peak_human" || echo "Cannot connect to Redis"
```

Make it executable and run periodically:
```bash
chmod +x scripts/monitor_resources.sh
# Run every 5 minutes
*/5 * * * * /TelegramBots/Chat_Stats/scripts/monitor_resources.sh >> /var/log/tgstats_monitor.log 2>&1
```

---

## 6. Emergency Resource Control

Create `/TelegramBots/Chat_Stats/scripts/emergency_throttle.sh`:

```bash
#!/bin/bash
# Emergency script to throttle resources when server is overloaded

LOAD_THRESHOLD=1.5  # Adjust based on your server (cores * 0.75)

# Get current load
CURRENT_LOAD=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')

echo "Current load: $CURRENT_LOAD"

# Compare (bc for floating point)
if (( $(echo "$CURRENT_LOAD > $LOAD_THRESHOLD" | bc -l) )); then
    echo "⚠️ High load detected! Throttling..."
    
    # Reduce Celery workers
    supervisorctl stop tgstats:tgstats-celery
    sleep 2
    supervisorctl start tgstats:tgstats-celery
    
    # Reduce process priorities
    for pid in $(pgrep -f "tgstats"); do
        renice 19 -p $pid
        ionice -c 3 -p $pid  # Idle I/O priority
    done
    
    echo "✅ Throttling applied"
else
    echo "✅ Load is normal"
fi
```

Add to crontab to run every minute during high-load periods:
```bash
* * * * * /TelegramBots/Chat_Stats/scripts/emergency_throttle.sh >> /var/log/tgstats_emergency.log 2>&1
```

---

## Recommended Configuration Summary

For a 2GB RAM server running multiple bots:

### Per Bot Limits:
- **CPU**: 50% of one core max
- **Memory**: 512MB max
- **Celery concurrency**: 2 workers
- **Database connections**: 5 pool + 5 overflow
- **Rate limiting**: 10 commands/min per user

### System-wide:
- Reserve 25% CPU for system operations
- Reserve 512MB RAM for PostgreSQL
- Reserve 256MB RAM for Redis
- Reserve 256MB RAM for system

### Priority Levels:
1. System services (highest)
2. PostgreSQL, Redis
3. Primary bot services
4. Celery workers
5. Background tasks (lowest)

---

## Deployment

1. **Choose deployment method** (Supervisor recommended for multiple bots)
2. **Apply resource limits** from section 1 or 2
3. **Add rate limiting** to handlers (section 3)
4. **Configure Celery** limits (section 3)
5. **Setup monitoring** (section 5)
6. **Test under load** to verify limits work

## Testing

```bash
# Generate load
ab -n 1000 -c 10 http://localhost:8000/api/health

# Monitor during load
watch -n 1 'ps aux | grep tgstats'

# Check cgroup limits (if using)
cat /sys/fs/cgroup/cpu/supervisor/cpu.cfs_quota_us
cat /sys/fs/cgroup/memory/supervisor/memory.limit_in_bytes
```

## Troubleshooting

**Problem**: Limits not applying
- Check `sudo supervisorctl status` or `systemctl status tgstats-*`
- Verify cgroups: `ls /sys/fs/cgroup/cpu/supervisor`
- Check logs: `sudo supervisorctl tail -f tgstats-bot`

**Problem**: Still high CPU
- Reduce `cpus` value further (e.g., 0.25)
- Reduce Celery `--concurrency` to 1
- Add more aggressive rate limiting
- Profile code to find CPU hotspots

**Problem**: Out of memory
- Reduce `memory_limit_in_bytes`
- Add `--max-tasks-per-child=50` to Celery
- Check for memory leaks with `objgraph`
- Enable memory profiling

---

## Next Steps

1. Implement supervisor configuration with cgroups
2. Add rate limiting to expensive operations
3. Set up monitoring and alerts
4. Document baseline resource usage
5. Gradually tune limits based on actual usage patterns

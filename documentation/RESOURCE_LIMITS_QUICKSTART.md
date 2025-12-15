# Quick Setup: Resource Limits for TG Stats Bot

## 🚀 Quick Install (5 minutes)

```bash
cd /TelegramBots/Chat_Stats
sudo ./setup_resource_limits.sh
```

This will:
- Install system dependencies (cpulimit, bc, sysstat)
- Setup Supervisor/systemd configuration with resource limits
- Configure automatic monitoring every 5 minutes
- Setup emergency throttling to prevent server overload
- Create log directories

---

## 📊 Immediate Actions

### 1. Monitor Current Resource Usage

```bash
./scripts/monitor_resources.sh
```

### 2. Check If Emergency Throttling is Active

```bash
tail -f /var/log/tgstats_emergency.log
```

### 3. Restart Services with New Limits

**If using Supervisor:**
```bash
sudo supervisorctl restart tgstats:*
sudo supervisorctl status
```

**If using systemd:**
```bash
sudo systemctl restart tgstats-bot tgstats-celery tgstats-celery-beat
sudo systemctl status tgstats-*
```

---

## ⚡ Emergency: Server Currently Overloaded?

Run this NOW to throttle everything:

```bash
# Reduce all Python bot priorities
for pid in $(pgrep -f "python.*TelegramBots"); do
    sudo renice -n 15 -p $pid
    sudo ionice -c 3 -p $pid  # Idle I/O priority
done

# Kill any runaway processes
ps aux | grep python | awk '{if ($3 > 90.0) print $2}' | xargs sudo kill -9

# Restart services
sudo supervisorctl restart all
```

---

## 🎯 Resource Limits Applied

### Per Bot Process:
- **CPU**: 50% of one core max
- **Memory**: 512MB max
- **Celery concurrency**: 2 workers
- **Database connections**: 5 + 5 overflow

### Chat_Stats Specific:
- **Bot process**: 50% CPU, 512MB RAM
- **Celery worker**: 50% CPU, 512MB RAM, max 100 tasks/worker
- **Celery beat**: 25% CPU, 256MB RAM
- **API server**: 50% CPU, 512MB RAM, 2 workers

### Rate Limiting:
- Commands: 10 per minute per user
- Statistics: 3 per 5 minutes per user
- Heavy operations: 1 per 10 minutes per user

---

## 📈 Monitoring Commands

### Real-time CPU/Memory
```bash
watch -n 2 'ps aux | grep -E "tgstats|celery" | grep -v grep'
```

### System Load Average
```bash
uptime
# Target: < 1.5 on 2GB server (2 cores)
```

### Top Resource Consumers
```bash
top -o %CPU
htop  # If installed
```

### Database Connections
```bash
psql -U postgres -d tgstats -c "SELECT count(*) FROM pg_stat_activity;"
```

### Redis Memory
```bash
redis-cli INFO memory | grep used_memory_human
```

---

## 🔧 Tuning Guidelines

### If Server Still Overloaded

1. **Reduce CPU limits further** (supervisor_tgstats.conf):
   ```ini
   environment=CPU_LIMIT="0.25"  # Down from 0.5
   ```

2. **Reduce Celery workers**:
   ```bash
   # In supervisor config, change:
   command=.../celery ... worker --concurrency=1  # Down from 2
   ```

3. **Increase rate limits** (tgstats/utils/rate_limiter.py):
   ```python
   command_limiter = RateLimiter(max_calls=5, time_window=60)  # Down from 10
   stats_limiter = RateLimiter(max_calls=1, time_window=600)   # Down from 3/300
   ```

4. **Lower emergency threshold** (scripts/emergency_throttle.sh):
   ```bash
   LOAD_THRESHOLD=1.0  # Down from 1.5
   ```

### If Server Has Resources Available

1. **Increase CPU limits**:
   ```ini
   environment=CPU_LIMIT="1.0"  # Up to 100% of one core
   ```

2. **More Celery workers**:
   ```bash
   command=.../celery ... worker --concurrency=4  # Up from 2
   ```

---

## 📁 Configuration Files

| File | Purpose |
|------|---------|
| `supervisor_tgstats.conf` | Supervisor config with resource limits |
| `tgstats-bot.service` | systemd service with CPUQuota/MemoryMax |
| `scripts/monitor_resources.sh` | Resource monitoring script |
| `scripts/emergency_throttle.sh` | Auto-throttle on high load |
| `tgstats/utils/rate_limiter.py` | Application-level rate limiting |
| `/var/log/tgstats_emergency.log` | Emergency throttling log |
| `/var/log/tgstats/monitor.log` | Resource monitoring log |

---

## 🔍 Troubleshooting

### Services Not Starting
```bash
# Check logs
sudo supervisorctl tail -f tgstats-bot stderr

# Or for systemd
sudo journalctl -u tgstats-bot -f
```

### CPU Still High
```bash
# Find the culprit
ps aux --sort=-%cpu | head -20

# Check what it's doing
sudo strace -p <PID>
```

### Memory Leaks
```bash
# Restart workers more frequently
# In celery config: worker_max_tasks_per_child=50
```

### Database Connection Exhaustion
```bash
# Check active connections
psql -U postgres -d tgstats -c "
SELECT count(*), state 
FROM pg_stat_activity 
GROUP BY state;
"

# Kill idle connections
psql -U postgres -d tgstats -c "
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE state = 'idle' 
AND state_change < now() - interval '5 minutes';
"
```

---

## 📞 Health Check

Run this to verify everything is working:

```bash
# 1. Check services
sudo supervisorctl status | grep tgstats

# 2. Check resource usage
./scripts/monitor_resources.sh

# 3. Check load average (should be < 1.5)
uptime | awk -F'load average:' '{print $2}'

# 4. Test emergency throttling manually
./scripts/emergency_throttle.sh

# 5. Check cron jobs
crontab -l | grep tgstats

# 6. Test rate limiter (from Python)
python3 -c "
from tgstats.utils.rate_limiter import command_limiter
import asyncio
async def test():
    allowed, wait = await command_limiter.is_allowed(123)
    print(f'Allowed: {allowed}, Wait: {wait}s')
asyncio.run(test())
"
```

---

## 🎯 Success Criteria

After setup, you should see:
- ✅ Load average < 1.5 consistently
- ✅ No individual process > 50% CPU
- ✅ Total Python processes < 150% CPU
- ✅ Memory usage < 75% of total
- ✅ No OOM kills in `dmesg`
- ✅ Bot remains responsive during high traffic
- ✅ Emergency throttling activates when needed

---

## 📚 Additional Resources

- Full guide: [RESOURCE_LIMITS_GUIDE.md](./RESOURCE_LIMITS_GUIDE.md)
- Architecture: [ARCHITECTURE_DIAGRAM.md](./ARCHITECTURE_DIAGRAM.md)
- Quick reference: [QUICK_REFERENCE.md](./QUICK_REFERENCE.md)

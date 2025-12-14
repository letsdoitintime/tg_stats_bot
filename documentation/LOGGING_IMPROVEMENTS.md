# Logging Improvements Documentation

## Overview

The logging system has been completely overhauled with the following improvements:

✅ **File rotation** - Automatic log file rotation with configurable size limits  
✅ **Colored console output** - Easy-to-read colored terminal output  
✅ **Structured logging** - JSON or text format with context  
✅ **Size limits** - Configurable max file size (default 10MB)  
✅ **Backup retention** - Keep up to 5 backup log files  
✅ **Log viewer utility** - Built-in log viewer with filtering  
✅ **Third-party filtering** - Control log levels for libraries  

---

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# Main log level
LOG_LEVEL=INFO                            # DEBUG, INFO, WARNING, ERROR, CRITICAL

# Third-party library log levels
TELEGRAM_LOG_LEVEL=WARNING                # Telegram library
HTTPX_LOG_LEVEL=WARNING                   # HTTP client
UVICORN_LOG_LEVEL=INFO                    # Web server

# File logging settings
LOG_TO_FILE=true                          # Enable/disable file logging
LOG_FILE_PATH=logs/tgstats.log            # Path to log file
LOG_FILE_MAX_BYTES=10485760               # Max size per file (10MB = 10485760 bytes)
LOG_FILE_BACKUP_COUNT=5                   # Number of backup files to keep
LOG_FORMAT=text                           # 'text' for colored output or 'json' for JSON
```

### Log Format Options

#### 1. Text Format (Recommended for Development)
```bash
LOG_FORMAT=text
```
**Output:**
```
2025-12-14 20:48:12 [INFO    ] bot_main Bot started successfully version=0.2.0 mode=polling
2025-12-14 20:48:15 [WARNING ] handlers Chat not setup chat_id=123456
2025-12-14 20:48:20 [ERROR   ] database Connection failed error=timeout
```

**Features:**
- ✅ Colored output in terminal
- ✅ Human-readable timestamps
- ✅ Clear level indicators
- ✅ Context key=value pairs

#### 2. JSON Format (Recommended for Production)
```bash
LOG_FORMAT=json
```
**Output:**
```json
{"timestamp":"2025-12-14T20:48:12Z","level":"info","logger":"bot_main","event":"Bot started","version":"0.2.0","app":"tgstats","pid":12345}
```

**Features:**
- ✅ Machine-parseable
- ✅ Easy to process with log aggregators
- ✅ All context preserved
- ✅ Suitable for ELK, Splunk, etc.

---

## File Rotation

### How It Works

1. **Primary log file**: `logs/tgstats.log`
2. When file reaches `LOG_FILE_MAX_BYTES`:
   - Renamed to `logs/tgstats.log.1`
   - New `logs/tgstats.log` created
3. When rotating again:
   - `logs/tgstats.log.1` → `logs/tgstats.log.2`
   - Current log → `logs/tgstats.log.1`
4. Keeps up to `LOG_FILE_BACKUP_COUNT` backups
5. Oldest backup is deleted when limit reached

### Example with 5 Backups

```
logs/
├── tgstats.log         ← Current (newest)
├── tgstats.log.1       ← 1st backup
├── tgstats.log.2       ← 2nd backup
├── tgstats.log.3       ← 3rd backup
├── tgstats.log.4       ← 4th backup
└── tgstats.log.5       ← 5th backup (oldest)
```

### Size Calculation

**Common sizes:**
```bash
1 MB  = 1048576 bytes
5 MB  = 5242880 bytes
10 MB = 10485760 bytes (default)
20 MB = 20971520 bytes
50 MB = 52428800 bytes
```

---

## Log Viewer Utility

### Basic Usage

```bash
# View last 50 lines (default)
python scripts/view_logs.py

# View last 100 lines
python scripts/view_logs.py -n 100

# Follow logs in real-time (like tail -f)
python scripts/view_logs.py --follow

# Filter by log level
python scripts/view_logs.py --level ERROR

# Search for specific text
python scripts/view_logs.py --search "database"

# Combine filters
python scripts/view_logs.py -n 200 --level WARNING --search "timeout"

# Disable colors (for piping to files)
python scripts/view_logs.py --no-color > output.txt
```

### Real-Time Monitoring

```bash
# Watch for errors in real-time
python scripts/view_logs.py --follow --level ERROR

# Monitor specific component
python scripts/view_logs.py --follow --search "message processing"
```

---

## Log Levels

### When to Use Each Level

#### DEBUG
- Detailed information for diagnosing problems
- Variable values, function calls
- **Use when:** Troubleshooting specific issues

```python
logger.debug("Processing message", msg_id=123, text_len=45)
```

#### INFO (Default)
- Confirmation that things are working
- General informational messages
- **Use when:** Normal operations

```python
logger.info("Bot started", version="0.2.0", mode="polling")
```

#### WARNING
- Something unexpected happened, but still working
- Potential issues
- **Use when:** Degraded functionality

```python
logger.warning("Rate limit approaching", current=90, limit=100)
```

#### ERROR
- Serious problem, feature not working
- Exceptions and failures
- **Use when:** Something failed

```python
logger.error("Database connection failed", error=str(e))
```

#### CRITICAL
- System failure, cannot continue
- **Use when:** Application must stop

```python
logger.critical("Configuration invalid", reason="missing BOT_TOKEN")
```

---

## Examples

### Logging in Your Code

```python
from tgstats.utils.logging import get_logger

# Get a logger
logger = get_logger(__name__)

# Basic logging
logger.info("Operation started")

# With context
logger.info("User joined", user_id=123, username="john")

# Error with exception
try:
    result = process_data()
except Exception as e:
    logger.error("Processing failed", error=str(e), exc_info=True)

# Warning with details
logger.warning(
    "Cache miss",
    key="user:123",
    cache_hit_rate=0.75
)
```

---

## Troubleshooting

### Logs Not Appearing in File

```bash
# Check if logs directory exists
ls -la logs/

# Check permissions
ls -lh logs/tgstats.log

# Check configuration
python -c "from tgstats.core.config import settings; print(f'Log to file: {settings.log_to_file}, Path: {settings.log_file_path}')"

# Manually test logging
python << 'EOF'
from tgstats.utils.logging import setup_logging, get_logger
setup_logging(log_level="INFO", log_to_file=True, log_file_path="logs/test.log")
logger = get_logger("test")
logger.info("Test message")
EOF
```

### Too Many Log Files

```bash
# Check current backup count
ls -1 logs/*.log* | wc -l

# Reduce backup count in .env
echo "LOG_FILE_BACKUP_COUNT=3" >> .env

# Or manually clean old logs
find logs/ -name "*.log.*" -mtime +7 -delete
```

### Logs Growing Too Large

```bash
# Check current size
du -h logs/

# Reduce max file size in .env (5MB example)
echo "LOG_FILE_MAX_BYTES=5242880" >> .env

# Or manually compress old logs
gzip logs/tgstats.log.[2-5]
```

### Performance Impact

If logging is impacting performance:

```bash
# Reduce log level to WARNING or ERROR
LOG_LEVEL=WARNING

# Disable file logging temporarily
LOG_TO_FILE=false

# Filter noisy libraries
TELEGRAM_LOG_LEVEL=ERROR
HTTPX_LOG_LEVEL=ERROR
```

---

## Log Analysis Tips

### Find Errors
```bash
python scripts/view_logs.py --level ERROR -n 100
```

### Count Error Occurrences
```bash
grep "ERROR" logs/tgstats.log | wc -l
```

### Find Recent Activity
```bash
tail -100 logs/tgstats.log | grep "message processing"
```

### Export to JSON for Analysis
```bash
# Switch to JSON format
echo "LOG_FORMAT=json" >> .env
sudo systemctl restart tgstats-bot

# Process with jq
tail -100 logs/tgstats.log | jq -r 'select(.level == "error") | .event'
```

---

## Integration with Log Management

### Sending to External Systems

#### Syslog
```bash
# Install rsyslog
sudo apt-get install rsyslog

# Configure forwarding in /etc/rsyslog.d/tgstats.conf
*.* @@your-log-server:514
```

#### Filebeat (for ELK Stack)
```yaml
# filebeat.yml
filebeat.inputs:
- type: log
  enabled: true
  paths:
    - /path/to/logs/tgstats.log
  json.keys_under_root: true
  json.add_error_key: true

output.elasticsearch:
  hosts: ["localhost:9200"]
```

#### Logrotate (Alternative to Built-in Rotation)
```bash
# /etc/logrotate.d/tgstats
/path/to/logs/tgstats.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    postrotate
        systemctl reload tgstats-bot
    endscript
}
```

---

## Best Practices

### ✅ DO:
- Use appropriate log levels
- Include context (key=value pairs)
- Log important state changes
- Log errors with stack traces
- Monitor logs regularly

### ❌ DON'T:
- Log sensitive data (passwords, tokens)
- Log inside tight loops (performance)
- Use DEBUG in production (too verbose)
- Ignore disk space limits
- Log without context

---

## Quick Commands

```bash
# View recent logs
python scripts/view_logs.py -n 50

# Monitor in real-time
python scripts/view_logs.py --follow

# Check errors only
python scripts/view_logs.py --level ERROR

# Search for specific text
python scripts/view_logs.py --search "timeout"

# Check log file size
du -h logs/tgstats.log

# Count log lines
wc -l logs/tgstats.log

# Find specific time period
grep "2025-12-14 20:" logs/tgstats.log

# Restart bot to apply logging changes
sudo systemctl restart tgstats-bot
```

---

## Summary

**What's New:**
- ✅ Automatic file rotation (max 10MB per file)
- ✅ Keep up to 5 backup files
- ✅ Colored terminal output
- ✅ JSON or text format
- ✅ Built-in log viewer
- ✅ Configurable via environment variables

**Storage:**
- Max 60MB total (6 files × 10MB)
- Automatic cleanup
- Disk-safe

**Performance:**
- Minimal overhead
- Async-safe
- Buffered writes

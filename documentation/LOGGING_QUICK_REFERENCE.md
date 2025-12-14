# Logging Quick Reference Card

## 🚀 Quick Start

```bash
# Your logs are automatically saved to:
logs/tgstats.log

# View recent logs
python scripts/view_logs.py

# Follow logs in real-time
python scripts/view_logs.py --follow

# View errors only
python scripts/view_logs.py --level ERROR
```

---

## 📋 Configuration (.env file)

```bash
# Required settings (already configured)
LOG_LEVEL=INFO                     # Main log level
LOG_TO_FILE=true                   # Enable file logging
LOG_FILE_PATH=logs/tgstats.log     # Where logs are saved
LOG_FILE_MAX_BYTES=10485760        # 10MB per file
LOG_FILE_BACKUP_COUNT=5            # Keep 5 backup files
LOG_FORMAT=text                    # text (colored) or json
```

---

## 🎯 Common Commands

```bash
# View logs
python scripts/view_logs.py -n 50              # Last 50 lines
python scripts/view_logs.py --follow           # Real-time monitoring
python scripts/view_logs.py --level ERROR      # Errors only
python scripts/view_logs.py --search "timeout" # Search for text

# Check log files
ls -lh logs/                                   # List all log files
du -h logs/                                    # Check disk usage
tail -f logs/tgstats.log                       # Traditional tail

# Restart bot (after config changes)
sudo systemctl restart tgstats-bot             # Restart service
sudo systemctl status tgstats-bot              # Check status
```

---

## 🔍 Troubleshooting

### No logs appearing?
```bash
# Check if directory exists
ls -la logs/

# Check configuration
python -c "from tgstats.core.config import settings; print(f'To file: {settings.log_to_file}, Path: {settings.log_file_path}')"

# Check bot is running
sudo systemctl status tgstats-bot
```

### Logs too large?
```bash
# Check size
du -h logs/

# Reduce in .env
LOG_FILE_MAX_BYTES=5242880  # 5MB
LOG_FILE_BACKUP_COUNT=3     # 3 backups

# Restart bot
sudo systemctl restart tgstats-bot
```

---

## 📊 Log Levels

| Level    | When to Use                    | Example                           |
|----------|--------------------------------|-----------------------------------|
| DEBUG    | Detailed debugging info        | Variable values, function calls   |
| INFO     | Normal operations (default)    | Bot started, message processed    |
| WARNING  | Unexpected but recoverable     | Rate limit close, cache miss      |
| ERROR    | Something failed               | DB connection failed              |
| CRITICAL | System failure                 | Config invalid, cannot start      |

---

## 💾 Storage

**Default Configuration:**
- Max file size: 10MB
- Backup files: 5
- **Total storage: ~60MB maximum**

**Files:**
```
logs/
├── tgstats.log     ← Current (newest)
├── tgstats.log.1   ← 1st backup
├── tgstats.log.2   ← 2nd backup
├── tgstats.log.3   ← 3rd backup
├── tgstats.log.4   ← 4th backup
└── tgstats.log.5   ← 5th backup (oldest, auto-deleted when full)
```

---

## ✨ What's New

✅ **Automatic rotation** - Old logs archived automatically  
✅ **Colored output** - Easy-to-read terminal colors  
✅ **Size limits** - Never grows beyond configured size  
✅ **Backup retention** - Keeps history without filling disk  
✅ **Log viewer** - Built-in tool to view/filter logs  
✅ **Context** - Every log includes app name and PID  

---

## 📚 More Information

See `LOGGING_IMPROVEMENTS.md` for detailed documentation.

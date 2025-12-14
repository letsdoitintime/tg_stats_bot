# TG Stats Bot - Automation Setup

This document describes how to set up the TG Stats Bot to run automatically using either **Supervisor** or **Systemd**.

## Prerequisites

- System PostgreSQL installed and running
- Bot dependencies installed (`pip install -r requirements.txt`)
- Database migrations completed (`alembic upgrade head`)

## Option 1: Supervisor (Recommended for development)

Supervisor is great for development and provides easy process management with restart capabilities.

### Setup:
```bash
./setup_supervisor.sh
```

### Commands:
```bash
# Start the bot
sudo supervisorctl start tgstats-bot

# Stop the bot
sudo supervisorctl stop tgstats-bot

# Restart the bot
sudo supervisorctl restart tgstats-bot

# Check status
sudo supervisorctl status tgstats-bot

# View live logs
sudo supervisorctl tail -f tgstats-bot

# Run migrations manually
sudo supervisorctl start tgstats-migrations
```

### Configuration File:
- Location: `/etc/supervisor/conf.d/tgstats-bot.conf`
- Logs: `/var/log/tgstats-bot.log`

## Option 2: Systemd (Recommended for production)

Systemd is the native Linux service manager and integrates better with the system.

### Setup:
```bash
./setup_systemd.sh
```

### Commands:
```bash
# Start the bot
sudo systemctl start tgstats-bot

# Stop the bot
sudo systemctl stop tgstats-bot

# Restart the bot
sudo systemctl restart tgstats-bot

# Check status
sudo systemctl status tgstats-bot

# View live logs
sudo journalctl -u tgstats-bot -f

# Disable auto-start
sudo systemctl disable tgstats-bot
```

### Configuration File:
- Location: `/etc/systemd/system/tgstats-bot.service`
- Logs: Available via `journalctl`

## Features

Both setups provide:

- ✅ **Auto-start on boot**: Bot starts automatically when system boots
- ✅ **Auto-restart on crash**: Bot restarts if it crashes or stops unexpectedly
- ✅ **Database dependency**: Waits for PostgreSQL to be ready
- ✅ **Migration handling**: Runs database migrations before starting
- ✅ **Proper logging**: Logs are saved and rotated
- ✅ **Security**: Runs as non-root user with minimal permissions

## Choosing Between Supervisor and Systemd

### Use Supervisor if:
- You're developing or testing
- You want easy log viewing and process management
- You prefer a simpler setup
- You want to manage multiple related processes

### Use Systemd if:
- You're running in production
- You want native Linux integration
- You prefer journal-based logging
- You want better security isolation

## Troubleshooting

### Check if PostgreSQL is running:
```bash
sudo systemctl status postgresql
```

### Check database connection:
```bash
psql -h localhost -p 5432 -U tgstats_user -d tgstats -c "SELECT 1;"
```

### Manual bot start (for testing):
```bash
cd /TelegramBots/Chat_Stats
source venv/bin/activate
python -m tgstats.bot_main
```

### View all logs:
```bash
# Supervisor
sudo supervisorctl tail -f tgstats-bot

# Systemd
sudo journalctl -u tgstats-bot -f --since "1 hour ago"
```

## Security Notes

- Both configurations run the bot as the `root` user (suitable for dedicated bot servers)
- Log files are properly owned and have appropriate permissions
- Database credentials are read from environment variables
- For enhanced security on shared systems, consider creating a dedicated user account

## Monitoring

You can monitor the bot status by:

1. **System status**: Check if the service is running
2. **Log monitoring**: Watch logs for errors or issues
3. **Database monitoring**: Check if bot is processing messages
4. **Telegram monitoring**: Verify bot responds to commands

## Backup Considerations

Since you're using system PostgreSQL:
- Database data is stored in system PostgreSQL directories
- Bot code and configuration are in `/TelegramBots/Chat_Stats/`
- Environment variables are in `.env` file
- Make sure to backup both code and database regularly

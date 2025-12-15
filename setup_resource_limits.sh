#!/bin/bash
# Setup resource limits for TG Stats Bot

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== TG Stats Resource Limits Setup ==="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  This script should be run as root (or with sudo)"
    echo "Some features may not work without root privileges."
    echo ""
fi

# Detect init system
if command -v systemctl &> /dev/null && systemctl --version &> /dev/null 2>&1; then
    INIT_SYSTEM="systemd"
elif command -v supervisorctl &> /dev/null; then
    INIT_SYSTEM="supervisor"
else
    echo "❌ Neither systemd nor supervisor found!"
    echo "Please install supervisor: sudo apt install supervisor"
    exit 1
fi

echo "📦 Detected init system: $INIT_SYSTEM"
echo ""

# Install system dependencies
echo "1. Installing system dependencies..."

# Check for cpulimit
if ! command -v cpulimit &> /dev/null; then
    echo "Installing cpulimit for emergency CPU limiting..."
    apt-get update -qq
    apt-get install -y cpulimit
fi

# Check for bc (for floating point comparison)
if ! command -v bc &> /dev/null; then
    echo "Installing bc for load calculation..."
    apt-get install -y bc
fi

# Check for iostat (part of sysstat)
if ! command -v iostat &> /dev/null; then
    echo "Installing sysstat for I/O monitoring..."
    apt-get install -y sysstat
fi

echo "✅ Dependencies installed"
echo ""

# Setup based on init system
if [ "$INIT_SYSTEM" = "supervisor" ]; then
    echo "2. Setting up Supervisor configuration..."
    
    # Copy supervisor config
    if [ -f "/etc/supervisor/conf.d/tgstats.conf" ]; then
        echo "⚠️  Backing up existing config..."
        cp /etc/supervisor/conf.d/tgstats.conf /etc/supervisor/conf.d/tgstats.conf.backup.$(date +%Y%m%d_%H%M%S)
    fi
    
    cp supervisor_tgstats.conf /etc/supervisor/conf.d/tgstats.conf
    echo "✅ Supervisor config installed to /etc/supervisor/conf.d/tgstats.conf"
    
    # Reload supervisor
    echo "Reloading supervisor..."
    supervisorctl reread
    supervisorctl update
    
    echo ""
    echo "📊 Current status:"
    supervisorctl status | grep tgstats || echo "No tgstats services found"
    
elif [ "$INIT_SYSTEM" = "systemd" ]; then
    echo "2. Setting up systemd services..."
    
    # Update systemd service file with resource limits
    if [ -f "tgstats-bot.service" ]; then
        # Check if already has CPUQuota
        if ! grep -q "CPUQuota" tgstats-bot.service; then
            echo "Adding resource limits to tgstats-bot.service..."
            # This would need manual editing or a template
            echo "⚠️  Please manually add resource limits to tgstats-bot.service"
            echo "See documentation/RESOURCE_LIMITS_GUIDE.md for examples"
        fi
        
        cp tgstats-bot.service /etc/systemd/system/
        systemctl daemon-reload
        echo "✅ Service file installed"
    else
        echo "⚠️  tgstats-bot.service not found. Skipping systemd setup."
    fi
fi

echo ""
echo "3. Setting up monitoring..."

# Create log directory
mkdir -p /var/log/tgstats
chmod 755 /var/log/tgstats

# Make scripts executable
chmod +x scripts/monitor_resources.sh
chmod +x scripts/emergency_throttle.sh

echo "✅ Monitoring scripts ready"
echo ""

# Setup cron jobs
echo "4. Setting up automated monitoring..."

# Check if cron jobs already exist
CRON_MONITOR="*/5 * * * * $SCRIPT_DIR/scripts/monitor_resources.sh >> /var/log/tgstats/monitor.log 2>&1"
CRON_EMERGENCY="* * * * * $SCRIPT_DIR/scripts/emergency_throttle.sh"

# Add to crontab if not present
(crontab -l 2>/dev/null | grep -Fv "monitor_resources.sh" ; echo "$CRON_MONITOR") | crontab -
(crontab -l 2>/dev/null | grep -Fv "emergency_throttle.sh" ; echo "$CRON_EMERGENCY") | crontab -

echo "✅ Cron jobs installed:"
echo "   - Resource monitoring every 5 minutes"
echo "   - Emergency throttling every minute"
echo ""

# Setup PostgreSQL connection pool limits
echo "5. Configuring PostgreSQL connection limits..."

# Check if we can update postgresql.conf
PG_CONF=$(sudo -u postgres psql -t -c "SHOW config_file;" 2>/dev/null | xargs)
if [ -n "$PG_CONF" ] && [ -f "$PG_CONF" ]; then
    echo "PostgreSQL config: $PG_CONF"
    
    # Backup config
    cp "$PG_CONF" "${PG_CONF}.backup.$(date +%Y%m%d_%H%M%S)"
    
    # Recommended settings for 2GB RAM server
    echo "Recommended PostgreSQL settings for 2GB RAM:"
    echo "  max_connections = 50"
    echo "  shared_buffers = 256MB"
    echo "  effective_cache_size = 1GB"
    echo "  work_mem = 4MB"
    echo ""
    echo "⚠️  Please review and manually update if needed: $PG_CONF"
else
    echo "⚠️  Could not locate PostgreSQL config. Skipping."
fi

echo ""

# Update Celery configuration
echo "6. Checking Celery configuration..."

CELERY_APP="tgstats/celery_app.py"
if [ -f "$CELERY_APP" ]; then
    if grep -q "worker_max_tasks_per_child" "$CELERY_APP"; then
        echo "✅ Celery already configured with resource limits"
    else
        echo "⚠️  Consider adding these to $CELERY_APP:"
        echo "    worker_max_tasks_per_child=100"
        echo "    worker_max_memory_per_child=512000"
        echo "    task_time_limit=300"
        echo "See documentation/RESOURCE_LIMITS_GUIDE.md for details"
    fi
else
    echo "⚠️  $CELERY_APP not found"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "📋 Next Steps:"
echo ""
echo "1. Review and adjust resource limits in:"
if [ "$INIT_SYSTEM" = "supervisor" ]; then
    echo "   /etc/supervisor/conf.d/tgstats.conf"
    echo ""
    echo "2. Restart services:"
    echo "   sudo supervisorctl restart tgstats:*"
elif [ "$INIT_SYSTEM" = "systemd" ]; then
    echo "   /etc/systemd/system/tgstats-*.service"
    echo ""
    echo "2. Restart services:"
    echo "   sudo systemctl restart tgstats-bot tgstats-celery"
fi

echo ""
echo "3. Monitor resource usage:"
echo "   ./scripts/monitor_resources.sh"
echo "   tail -f /var/log/tgstats/monitor.log"
echo ""
echo "4. Check emergency throttling logs:"
echo "   tail -f /var/log/tgstats_emergency.log"
echo ""
echo "5. View current cron jobs:"
echo "   crontab -l | grep tgstats"
echo ""
echo "📚 Full documentation: documentation/RESOURCE_LIMITS_GUIDE.md"
echo ""

#!/bin/bash
# Setup script for supervisor configuration

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== TG Stats Bot - Supervisor Setup ==="
echo ""

# Check if supervisor is installed
if ! command -v supervisord &> /dev/null; then
    echo "📦 Installing supervisor..."
    sudo apt update
    sudo apt install -y supervisor
else
    echo "✅ Supervisor is already installed"
fi

# Copy configuration file
echo "📝 Installing supervisor configuration..."
sudo cp tgstats-bot.conf /etc/supervisor/conf.d/

# Create log directory if it doesn't exist
sudo mkdir -p /var/log
sudo touch /var/log/tgstats-bot.log
sudo touch /var/log/tgstats-migrations.log

# Set proper permissions for log files
sudo chown root:root /var/log/tgstats-bot.log
sudo chown root:root /var/log/tgstats-migrations.log

# Reload supervisor configuration
echo "🔄 Reloading supervisor configuration..."
sudo supervisorctl reread
sudo supervisorctl update

echo ""
echo "✅ Supervisor setup complete!"
echo ""
echo "🔧 Supervisor Commands:"
echo "  Start bot:              sudo supervisorctl start tgstats-bot"
echo "  Stop bot:               sudo supervisorctl stop tgstats-bot"
echo "  Restart bot:            sudo supervisorctl restart tgstats-bot"
echo "  Check status:           sudo supervisorctl status tgstats-bot"
echo "  View logs:              sudo supervisorctl tail -f tgstats-bot"
echo "  Run migrations:         sudo supervisorctl start tgstats-migrations"
echo ""
echo "📊 Status:"
sudo supervisorctl status tgstats-bot
echo ""
echo "💡 The bot will now automatically start on system boot!"
echo "   To start it now, run: sudo supervisorctl start tgstats-bot"

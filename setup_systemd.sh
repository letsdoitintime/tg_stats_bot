#!/bin/bash
# Setup script for systemd service configuration

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== TG Stats Bot - Systemd Service Setup ==="
echo ""

# Copy service file
echo "📝 Installing systemd service..."
sudo cp tgstats-bot.service /etc/systemd/system/

# Reload systemd
echo "🔄 Reloading systemd configuration..."
sudo systemctl daemon-reload

# Enable the service (auto-start on boot)
echo "🚀 Enabling auto-start on boot..."
sudo systemctl enable tgstats-bot.service

echo ""
echo "✅ Systemd service setup complete!"
echo ""
echo "🔧 Systemd Commands:"
echo "  Start bot:              sudo systemctl start tgstats-bot"
echo "  Stop bot:               sudo systemctl stop tgstats-bot"
echo "  Restart bot:            sudo systemctl restart tgstats-bot"
echo "  Check status:           sudo systemctl status tgstats-bot"
echo "  View logs:              sudo journalctl -u tgstats-bot -f"
echo "  Disable auto-start:     sudo systemctl disable tgstats-bot"
echo ""
echo "📊 Status:"
sudo systemctl status tgstats-bot --no-pager
echo ""
echo "💡 The bot will now automatically start on system boot!"
echo "   To start it now, run: sudo systemctl start tgstats-bot"

#!/bin/bash
# Project status and overview script

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== TG Stats Bot - Project Status ==="
echo ""

# Check PostgreSQL status
echo "📊 Database Status:"
if systemctl is-active --quiet postgresql; then
    echo "  ✅ System PostgreSQL service is running on port 5432"
    
    # Check if we can connect to our specific database
    if PGPASSWORD="your_secure_password_here" psql -h localhost -p 5432 -U tgstats_user -d tgstats -c "SELECT 1;" > /dev/null 2>&1; then
        echo "  ✅ Database connection successful"
        
        # Show database stats
        echo ""
        echo "📈 Database Contents:"
        PGPASSWORD="your_secure_password_here" psql -h localhost -p 5432 -U tgstats_user -d tgstats -t -c "
            SELECT '  💬 Chats: ' || COUNT(*) FROM chats UNION ALL
            SELECT '  👥 Users: ' || COUNT(*) FROM users UNION ALL  
            SELECT '  📝 Messages: ' || COUNT(*) FROM messages UNION ALL
            SELECT '  �� Memberships: ' || COUNT(*) FROM memberships UNION ALL
            SELECT '  ⚙️  Settings: ' || COUNT(*) FROM group_settings;
        " 2>/dev/null | sed 's/^[ \t]*//' || echo "  ⚠️  Could not retrieve database statistics"
    else
        echo "  ⚠️  PostgreSQL is running but cannot connect to tgstats database"
        echo "  💡 Check database credentials and permissions"
    fi
else
    echo "  ❌ System PostgreSQL service is not running"
    echo "  💡 Run: sudo systemctl start postgresql"
fi

echo ""
echo "🗂️  Project Structure:"
echo "  📁 tgstats/          - Bot source code"
echo "  📁 migrations/       - Database migrations"
echo "  📁 venv/             - Python virtual environment"
echo "  🚀 start_bot.sh      - Main startup script"
echo "  🗄️  Database:         - System PostgreSQL (managed by systemctl)"

echo ""
echo "🔧 Quick Commands:"
echo "  Start bot:            ./start_bot.sh"
echo "  Check DB service:     sudo systemctl status postgresql"
echo "  Start DB service:     sudo systemctl start postgresql"
echo "  Stop DB service:      sudo systemctl stop postgresql"
echo "  Connect to DB:        PGPASSWORD=\"your_secure_password_here\" psql -h localhost -p 5432 -U tgstats_user -d tgstats"

echo ""
echo "📝 Configuration:"
echo "  Bot Token:            $(grep BOT_TOKEN .env | cut -d'=' -f2 | cut -c1-20)..."
echo "  Database:             System PostgreSQL (port 5432)"
echo "  Database User:        tgstats_user"
echo "  Database Name:        tgstats"
echo "  Mode:                 $(grep MODE .env | cut -d'=' -f2)"
echo "  Log Level:            $(grep LOG_LEVEL .env | cut -d'=' -f2)"

echo ""
echo "✅ Using system PostgreSQL database!"
echo "   Database is managed by systemctl and shared with other applications."
echo "   Connection: postgresql+psycopg://tgstats_user:your_secure_password_here@localhost:5432/tgstats"

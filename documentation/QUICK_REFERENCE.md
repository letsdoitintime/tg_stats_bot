# 🚀 Quick Reference Card

## 📚 Documentation
All guides moved to: **[documentation/](documentation/README.md)**

## 🔗 Quick Links
- **Database Setup**: [documentation/POSTGRES_REMOTE_ACCESS_CONFIG.md](documentation/POSTGRES_REMOTE_ACCESS_CONFIG.md)
- **DBeaver Connection**: [documentation/DBEAVER_CONNECTION_GUIDE.md](documentation/DBEAVER_CONNECTION_GUIDE.md)
- **User Management**: [documentation/POSTGRES_USERS_CONFIG.md](documentation/POSTGRES_USERS_CONFIG.md)

## ⚙️ Environment Setup
```bash
# Copy environment template
cp .env.example .env

# Edit your configuration
nano .env

# Required variables:
# - BOT_TOKEN: Your Telegram bot token
# - DATABASE_URL: PostgreSQL connection string
# - REDIS_URL: Redis connection string
# - ADMIN_API_TOKEN: Secret token for API access
```

## 🗄️ Database Info
- **Server**: 95.216.202.228:5432
- **Database**: tgstats
- **User**: andrew
- **Password**: andrew_secure_password_2025

## 🔧 Commands
```bash
# Documentation
ls documentation/           # List all docs
cat documentation/README.md # Documentation index

# Database
sudo systemctl status postgresql  # Check PostgreSQL status
sudo ufw status                   # Check firewall
psql -h localhost -U andrew -d tgstats  # Connect locally
```

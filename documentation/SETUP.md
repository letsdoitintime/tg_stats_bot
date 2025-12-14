# TG Stats Bot - Setup Guide

This guide provides multiple ways to set up the TG Stats Bot depending on your needs and system configuration.

## 🚀 Quick Setup (Recommended)

### For New Users - Complete Automated Setup

```bash
./setup.sh
```

This script automatically:
- ✅ Detects your operating system (macOS/Linux)
- ✅ Installs package managers (Homebrew on macOS)
- ✅ Installs PostgreSQL with proper version
- ✅ Creates Python virtual environment
- ✅ Installs all Python dependencies
- ✅ Initializes PostgreSQL database
- ✅ Runs database migrations
- ✅ Creates configuration files

**Supported Systems:**
- macOS (Intel & Apple Silicon)
- Ubuntu/Debian Linux
- CentOS/RHEL Linux
- Fedora Linux

### After Setup
1. Edit `.env` file and add your bot token from @BotFather:
   ```bash
   nano .env
   # Change: BOT_TOKEN=your_bot_token_here
   ```

2. Start the bot:
   ```bash
   ./start_bot.sh
   ```

## 📋 Alternative Setup Methods

### Option 1: Python Requirements Only

If you already have PostgreSQL installed:

```bash
./install_requirements.sh
```

### Option 2: Manual pip Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install from pyproject.toml
pip install -e .
pip install -e ".[dev]"

# OR install from requirements.txt
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Option 3: Manual System Setup

#### macOS

```bash
# Install Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install PostgreSQL
brew install postgresql@16

# Initialize database
/opt/homebrew/opt/postgresql@16/bin/initdb -D postgres_data

# Start PostgreSQL
/opt/homebrew/opt/postgresql@16/bin/pg_ctl -D postgres_data -l postgres.log start

# Create database
/opt/homebrew/opt/postgresql@16/bin/createdb -h localhost -p 5433 -U $(whoami) tgstats
```

#### Ubuntu/Debian

```bash
# Update packages
sudo apt update

# Install PostgreSQL
sudo apt install postgresql postgresql-contrib python3-venv python3-pip

# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database
sudo -u postgres createuser -s $USER
sudo -u postgres createdb tgstats
```

#### CentOS/RHEL

```bash
# Install PostgreSQL
sudo yum install postgresql postgresql-server postgresql-contrib python3 python3-pip

# Initialize database
sudo postgresql-setup initdb

# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database
sudo -u postgres createuser -s $USER
sudo -u postgres createdb tgstats
```

## 🔧 Configuration

### Environment Variables

Create `.env` file:

```bash
# Required - Get from @BotFather
BOT_TOKEN=your_bot_token_here

# Database connection
DATABASE_URL=postgresql+psycopg://andrew@localhost:5433/tgstats

# Bot mode
MODE=polling

# Optional - for webhook mode
WEBHOOK_URL=

# Logging level
LOG_LEVEL=INFO
```

### Database Configuration

#### Local PostgreSQL (Default)
- Host: `localhost`
- Port: `5433` (macOS) or `5432` (Linux)
- Database: `tgstats`
- User: Your system username

#### External PostgreSQL
Update DATABASE_URL in `.env`:
```bash
DATABASE_URL=postgresql+psycopg://username:password@host:port/database
```

## 🎮 Usage

### Start the Bot
```bash
./start_bot.sh
```

### Stop the Bot
Press `Ctrl+C` in the terminal running the bot

### Stop PostgreSQL
```bash
./stop_postgres.sh
```

### Bot Commands
- `/setup` - Initialize analytics for a group (admin only)
- `/settings` - View current group settings (admin only)
- `/set_text on|off` - Toggle text message storage (admin only)
- `/set_reactions on|off` - Toggle reaction capture (admin only)
- `/help` - Show help message

## 🐛 Troubleshooting

### Common Issues

#### PostgreSQL Connection Error
```bash
# Check if PostgreSQL is running
./start_postgres.sh

# Check database exists
psql -h localhost -p 5433 -U $(whoami) -l
```

#### Python Dependencies Error
```bash
# Reinstall dependencies
source venv/bin/activate
pip install --upgrade pip
pip install -e .
```

#### Permission Denied
```bash
# Make scripts executable
chmod +x setup.sh
chmod +x start_bot.sh
chmod +x start_postgres.sh
chmod +x stop_postgres.sh
chmod +x install_requirements.sh
```

#### Bot Token Error
- Get token from @BotFather on Telegram
- Edit `.env` file with correct token
- Restart the bot

### Database Migrations

If you need to reset the database:
```bash
# Stop the bot first
./stop_postgres.sh

# Remove database files (WARNING: This deletes all data!)
rm -rf postgres_data

# Run setup again
./setup.sh
```

### Logs

- Bot logs: Console output
- PostgreSQL logs: `postgres.log` file
- Debug mode: Set `LOG_LEVEL=DEBUG` in `.env`

## 📦 Project Structure

```
tg-stats/
├── setup.sh                 # Complete automated setup
├── install_requirements.sh  # Python requirements only
├── start_bot.sh             # Start the bot
├── start_postgres.sh        # Start PostgreSQL
├── stop_postgres.sh         # Stop PostgreSQL
├── .env                     # Configuration (create from setup)
├── pyproject.toml           # Python project configuration
├── requirements.txt         # Python dependencies
├── requirements-dev.txt     # Development dependencies
├── tgstats/                 # Main application code
├── migrations/              # Database migrations
├── postgres_data/           # PostgreSQL data files
└── venv/                    # Python virtual environment
```

## 🔒 Security Notes

- Keep your bot token secret
- The local PostgreSQL setup uses trust authentication for simplicity
- For production, use proper authentication and encryption
- Regularly update dependencies for security patches

## 📚 Additional Resources

- [Telegram Bot API Documentation](https://core.telegram.org/bots/api)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Python Virtual Environments](https://docs.python.org/3/tutorial/venv.html)
- [Project Issues & Support](https://github.com/your-repo/issues)

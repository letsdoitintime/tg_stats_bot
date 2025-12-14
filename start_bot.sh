#!/bin/bash
# Main startup script for TG Stats Bot - Step 2 with FastAPI and Celery

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== TG Stats Bot Step 2 Startup ==="

# Load environment variables from .env file
if [ -f ".env" ]; then
    echo "Loading environment variables from .env file..."
    export $(grep -v '^#' .env | grep -v '^$' | xargs)
    echo "✅ Environment variables loaded"
else
    echo "❌ .env file not found! Please create it with required variables."
    echo "   Copy .env.example to .env and configure your settings."
    exit 1
fi

# Validate required environment variables
required_vars=("BOT_TOKEN" "DATABASE_URL" "REDIS_URL")
missing_vars=()

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    echo "❌ Missing required environment variables:"
    for var in "${missing_vars[@]}"; do
        echo "   - $var"
    done
    echo "Please set these variables in your .env file."
    exit 1
fi

echo "✅ All required environment variables are set"

# Check system dependencies
echo "0. Checking system dependencies..."
dependencies_ok=true

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "❌ PostgreSQL client (psql) not found. Install with: sudo apt install postgresql-client"
    dependencies_ok=false
fi

# Check if Redis CLI is available
if ! command -v redis-cli &> /dev/null; then
    echo "❌ Redis CLI not found. Install with: sudo apt install redis-tools"
    dependencies_ok=false
fi

if [ "$dependencies_ok" = false ]; then
    echo "❌ Missing required system dependencies. Please install them first."
    exit 1
fi

echo "✅ System dependencies check passed"

# Start PostgreSQL
echo "1. Checking PostgreSQL connection..."
# Extract database connection details from DATABASE_URL
DB_HOST=$(echo "$DATABASE_URL" | sed -n 's/.*@\([^:]*\):.*/\1/p')
DB_PORT=$(echo "$DATABASE_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
DB_USER=$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
DB_PASS=$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
DB_NAME=$(echo "$DATABASE_URL" | sed -n 's/.*\/\([^?]*\).*/\1/p')

echo "Database configuration:"
echo "  Host: $DB_HOST"
echo "  Port: $DB_PORT"
echo "  User: $DB_USER"
echo "  Database: $DB_NAME"

# Using system PostgreSQL - ensure service is running
if ! systemctl is-active --quiet postgresql; then
    echo "❌ PostgreSQL service is not running. Starting it..."
    sudo systemctl start postgresql
    if [ $? -ne 0 ]; then
        echo "❌ Failed to start PostgreSQL service"
        exit 1
    fi
    sleep 3
fi

# Test PostgreSQL connection with credentials from env
export PGPASSWORD="$DB_PASS"
if ! psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" >/dev/null 2>&1; then
    echo "❌ Cannot connect to PostgreSQL database '$DB_NAME'"
    echo "   Make sure the database and user exist:"
    echo "   sudo -u postgres createuser -P $DB_USER"
    echo "   sudo -u postgres createdb -O $DB_USER $DB_NAME"
    exit 1
fi
echo "✅ PostgreSQL connection successful"

# Check/start Redis
echo "2. Checking Redis connection..."
# Extract Redis connection details from REDIS_URL
REDIS_HOST=$(echo "$REDIS_URL" | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
REDIS_PORT=$(echo "$REDIS_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')

if [ -z "$REDIS_HOST" ]; then
    REDIS_HOST="localhost"
fi
if [ -z "$REDIS_PORT" ]; then
    REDIS_PORT="6379"
fi

echo "Redis configuration:"
echo "  Host: $REDIS_HOST"
echo "  Port: $REDIS_PORT"

if ! systemctl is-active --quiet redis; then
    echo "Starting Redis service..."
    sudo systemctl start redis
    if [ $? -ne 0 ]; then
        echo "❌ Failed to start Redis service"
        echo "   Install Redis: sudo apt install redis-server"
        exit 1
    fi
    sleep 2
fi

# Test Redis connection
if ! redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping >/dev/null 2>&1; then
    echo "❌ Cannot connect to Redis at $REDIS_HOST:$REDIS_PORT"
    exit 1
fi
echo "✅ Redis connection successful"

# Wait a moment for services to be ready
sleep 2

# Activate virtual environment
echo "3. Activating virtual environment..."
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✅ Virtual environment activated"
else
    echo "❌ Virtual environment not found! Please run: python -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Display current configuration
echo ""
echo "Current configuration:"
echo "  Bot Token: ${BOT_TOKEN:0:10}..."
echo "  Mode: ${MODE:-polling}"
echo "  Log Level: ${LOG_LEVEL:-INFO}"
echo "  Admin Token: ${ADMIN_API_TOKEN:+configured}"
echo ""

# Run migrations
echo "4. Running database migrations (including TimescaleDB setup)..."
alembic upgrade head

echo "5. Starting services..."
echo ""
echo "Choose startup mode:"
echo "1) Full stack with FastAPI + Celery (recommended)"
echo "2) Bot only (polling mode)"
echo "3) FastAPI only (webhook/API mode)"
echo "4) Generate sample data and exit"
echo ""

# Read with 10-second timeout, default to option 1
echo -n "Enter choice (1-4) or wait 10s for default [1]: "
if read -t 10 choice; then
    echo ""  # New line after input
else
    echo ""  # New line after timeout
    echo "⏰ No input received in 10 seconds, using default option 1 (Full stack)"
    choice=1
fi

# Set default if empty input
if [ -z "$choice" ]; then
    choice=1
    echo "📋 Using default option 1 (Full stack)"
fi

case $choice in
    1)
        echo "Starting full stack (FastAPI + Bot + Celery)..."
        echo ""
        
        # Clean up any existing processes first
        echo "🧹 Cleaning up existing processes..."
        pkill -f "uvicorn.*tgstats" 2>/dev/null || true
        pkill -f "celery.*tgstats" 2>/dev/null || true
        sleep 2
        
        # Check if port 8000 is free using netstat or ss
        if command -v netstat &> /dev/null; then
            if netstat -tuln | grep -q ":8000 "; then
                echo "⚠️ Port 8000 is still in use. Trying to free it..."
                pkill -f ":8000" 2>/dev/null || true
                sleep 2
            fi
        elif command -v ss &> /dev/null; then
            if ss -tuln | grep -q ":8000 "; then
                echo "⚠️ Port 8000 is still in use. Trying to free it..."
                pkill -f ":8000" 2>/dev/null || true
                sleep 2
            fi
        fi
        
        # Start Celery worker in background
        echo "Starting Celery worker..."
        celery -A tgstats.celery_tasks worker --loglevel=info --concurrency=2 --detach
        
        # Start Celery beat in background
        echo "Starting Celery beat scheduler..."
        celery -A tgstats.celery_tasks beat --loglevel=info --detach
        
        # Start FastAPI server in background
        echo "Starting FastAPI server on port 8000..."
        uvicorn tgstats.web.app:app --host 0.0.0.0 --port 8000 --log-level "${UVICORN_LOG_LEVEL,,}" &
        FASTAPI_PID=$!
        
        sleep 3
        
        echo ""
        echo "✅ Services started successfully!"
        echo ""
        echo "🌐 Web UI: http://localhost:8000/ui"
        echo "📚 API Docs: http://localhost:8000/docs" 
        echo "🔧 Health Check: http://localhost:8000/healthz"
        echo ""
        echo "Starting Telegram bot (press Ctrl+C to stop all services)..."
        
        # Function to cleanup background processes
        cleanup() {
            echo ""
            echo "Stopping services..."
            
            # Stop FastAPI
            if [ ! -z "$FASTAPI_PID" ]; then
                kill $FASTAPI_PID 2>/dev/null || true
            fi
            
            # Stop all related processes more aggressively
            pkill -f "uvicorn.*tgstats" 2>/dev/null || true
            pkill -f "celery.*tgstats" 2>/dev/null || true
            
            # If lsof is available, kill processes on port 8000
            if command -v lsof &> /dev/null; then
                lsof -ti:8000 | xargs kill -9 2>/dev/null || true
            fi
            
            echo "Services stopped."
            exit 0
        }
        
        # Set trap for cleanup
        trap cleanup EXIT INT TERM
        
        # Start bot (this will keep the script running)
        python -m tgstats.bot_main
        ;;
        
    2)
        echo "Starting bot only (polling mode)..."
        python -m tgstats.bot_main
        ;;
        
    3)
        echo "Starting FastAPI server only..."
        echo ""
        echo "🌐 Web UI: http://localhost:8000/ui"
        echo "📚 API Docs: http://localhost:8000/docs"
        echo ""
        uvicorn tgstats.web.app:app --host 0.0.0.0 --port 8000 --reload
        ;;
        
    4)
        echo "Generating sample data..."
        python scripts/seed_database.py
        echo "Sample data generated. You can now start the services."
        ;;
        
    *)
        echo "Invalid choice. Exiting."
        exit 1
        ;;
esac

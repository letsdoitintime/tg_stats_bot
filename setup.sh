#!/bin/bash
# Setup script for TG Stats Bot - Install all requirements and initialize PostgreSQL

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${BLUE}=== TG Stats Bot Setup Script ===${NC}"
echo -e "${YELLOW}This script will install all requirements and set up PostgreSQL locally${NC}"
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if we're on macOS
is_macos() {
    [[ "$OSTYPE" == "darwin"* ]]
}

# Function to check if we're on Linux
is_linux() {
    [[ "$OSTYPE" == "linux-gnu"* ]]
}

# Step 1: Check system requirements
echo -e "${BLUE}1. Checking system requirements...${NC}"

# Check Python version
if command_exists python3; then
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    echo -e "${GREEN}✓ Python found: $PYTHON_VERSION${NC}"
    
    # Check if Python version is >= 3.12
    if python3 -c 'import sys; exit(0 if sys.version_info >= (3, 12) else 1)'; then
        echo -e "${GREEN}✓ Python version is compatible (>= 3.12)${NC}"
    else
        echo -e "${RED}✗ Python 3.12+ required, found $PYTHON_VERSION${NC}"
        echo -e "${YELLOW}Please install Python 3.12 or higher${NC}"
        exit 1
    fi
else
    echo -e "${RED}✗ Python 3 not found${NC}"
    echo -e "${YELLOW}Please install Python 3.12 or higher${NC}"
    exit 1
fi

echo ""

# Step 2: Install Homebrew (macOS) or check package manager (Linux)
echo -e "${BLUE}2. Checking package manager...${NC}"

if is_macos; then
    if command_exists brew; then
        echo -e "${GREEN}✓ Homebrew found${NC}"
    else
        echo -e "${YELLOW}Installing Homebrew...${NC}"
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        
        # Add Homebrew to PATH for current session
        if [[ -f "/opt/homebrew/bin/brew" ]]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        elif [[ -f "/usr/local/bin/brew" ]]; then
            eval "$(/usr/local/bin/brew shellenv)"
        fi
        
        echo -e "${GREEN}✓ Homebrew installed${NC}"
    fi
elif is_linux; then
    if command_exists apt-get; then
        echo -e "${GREEN}✓ APT package manager found${NC}"
    elif command_exists yum; then
        echo -e "${GREEN}✓ YUM package manager found${NC}"
    elif command_exists dnf; then
        echo -e "${GREEN}✓ DNF package manager found${NC}"
    else
        echo -e "${RED}✗ No supported package manager found${NC}"
        echo -e "${YELLOW}This script supports APT (Ubuntu/Debian), YUM (CentOS), or DNF (Fedora)${NC}"
        exit 1
    fi
else
    echo -e "${RED}✗ Unsupported operating system${NC}"
    echo -e "${YELLOW}This script supports macOS and Linux${NC}"
    exit 1
fi

echo ""

# Step 3: Install PostgreSQL
echo -e "${BLUE}3. Installing PostgreSQL...${NC}"

if is_macos; then
    if command_exists /opt/homebrew/opt/postgresql@16/bin/postgres; then
        echo -e "${GREEN}✓ PostgreSQL 16 already installed${NC}"
    else
        echo -e "${YELLOW}Installing PostgreSQL 16 via Homebrew...${NC}"
        brew install postgresql@16
        echo -e "${GREEN}✓ PostgreSQL 16 installed${NC}"
    fi
elif is_linux; then
    if command_exists psql; then
        PG_VERSION=$(psql --version | grep -oP '\d+\.\d+' | head -1)
        echo -e "${GREEN}✓ PostgreSQL found: $PG_VERSION${NC}"
    else
        echo -e "${YELLOW}Installing PostgreSQL...${NC}"
        if command_exists apt-get; then
            sudo apt-get update
            sudo apt-get install -y postgresql postgresql-contrib
        elif command_exists yum; then
            sudo yum install -y postgresql postgresql-server postgresql-contrib
            sudo postgresql-setup initdb
        elif command_exists dnf; then
            sudo dnf install -y postgresql postgresql-server postgresql-contrib
            sudo postgresql-setup --initdb
        fi
        echo -e "${GREEN}✓ PostgreSQL installed${NC}"
    fi
fi

echo ""

# Step 4: Create Python virtual environment
echo -e "${BLUE}4. Creating Python virtual environment...${NC}"

if [[ -d "venv" ]]; then
    echo -e "${GREEN}✓ Virtual environment already exists${NC}"
else
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate
echo -e "${GREEN}✓ Virtual environment activated${NC}"

echo ""

# Step 5: Install Python dependencies
echo -e "${BLUE}5. Installing Python dependencies...${NC}"

echo -e "${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip

echo -e "${YELLOW}Installing project dependencies...${NC}"
pip install -e .

echo -e "${YELLOW}Installing development dependencies...${NC}"
pip install -e ".[dev]"

echo -e "${GREEN}✓ All Python dependencies installed${NC}"

echo ""

# Step 6: Initialize PostgreSQL database
echo -e "${BLUE}6. Initializing PostgreSQL database...${NC}"

if is_macos; then
    # Create postgres_data directory if it doesn't exist
    if [[ ! -d "postgres_data" ]]; then
        echo -e "${YELLOW}Initializing PostgreSQL data directory...${NC}"
        /opt/homebrew/opt/postgresql@16/bin/initdb -D postgres_data
        echo -e "${GREEN}✓ PostgreSQL data directory initialized${NC}"
    else
        echo -e "${GREEN}✓ PostgreSQL data directory already exists${NC}"
    fi
    
    # Create postgres_socket directory if it doesn't exist
    if [[ ! -d "postgres_socket" ]]; then
        mkdir -p postgres_socket
        echo -e "${GREEN}✓ PostgreSQL socket directory created${NC}"
    fi
    
    # Start PostgreSQL if not running
    if ! /opt/homebrew/opt/postgresql@16/bin/pg_ctl -D postgres_data status > /dev/null 2>&1; then
        echo -e "${YELLOW}Starting PostgreSQL...${NC}"
        /opt/homebrew/opt/postgresql@16/bin/pg_ctl -D postgres_data -l postgres.log start
        sleep 3  # Wait for PostgreSQL to start
        echo -e "${GREEN}✓ PostgreSQL started${NC}"
    else
        echo -e "${GREEN}✓ PostgreSQL already running${NC}"
    fi
    
    # Create database if it doesn't exist
    echo -e "${YELLOW}Creating database...${NC}"
    if ! /opt/homebrew/opt/postgresql@16/bin/psql -h localhost -p 5433 -U andrew -lqt | cut -d \| -f 1 | grep -qw tgstats; then
        /opt/homebrew/opt/postgresql@16/bin/createdb -h localhost -p 5433 -U andrew tgstats
        echo -e "${GREEN}✓ Database 'tgstats' created${NC}"
    else
        echo -e "${GREEN}✓ Database 'tgstats' already exists${NC}"
    fi
    
elif is_linux; then
    # For Linux, assume system PostgreSQL service
    echo -e "${YELLOW}Starting PostgreSQL service...${NC}"
    if command_exists systemctl; then
        sudo systemctl start postgresql
        sudo systemctl enable postgresql
    elif command_exists service; then
        sudo service postgresql start
    fi
    
    # Create user and database
    echo -e "${YELLOW}Creating database user and database...${NC}"
    sudo -u postgres createuser -s "$USER" 2>/dev/null || true
    sudo -u postgres createdb tgstats 2>/dev/null || true
    echo -e "${GREEN}✓ Database setup completed${NC}"
fi

echo ""

# Step 7: Create environment file
echo -e "${BLUE}7. Setting up environment configuration...${NC}"

if [[ ! -f ".env" ]]; then
    echo -e "${YELLOW}Creating .env file...${NC}"
    cat > .env << EOF
BOT_TOKEN=your_bot_token_here
DATABASE_URL=postgresql+psycopg://andrew@localhost:5433/tgstats
MODE=polling
WEBHOOK_URL=
LOG_LEVEL=INFO
EOF
    echo -e "${GREEN}✓ .env file created${NC}"
    echo -e "${YELLOW}⚠️  Please edit .env and add your bot token from @BotFather${NC}"
else
    echo -e "${GREEN}✓ .env file already exists${NC}"
fi

echo ""

# Step 8: Run database migrations
echo -e "${BLUE}8. Running database migrations...${NC}"

echo -e "${YELLOW}Running Alembic migrations...${NC}"
alembic upgrade head
echo -e "${GREEN}✓ Database migrations completed${NC}"

echo ""

# Step 9: Make scripts executable
echo -e "${BLUE}9. Setting up scripts...${NC}"

chmod +x start_bot.sh
chmod +x start_postgres.sh
chmod +x stop_postgres.sh
echo -e "${GREEN}✓ Scripts made executable${NC}"

echo ""

# Final summary
echo -e "${GREEN}=== Setup Complete! ===${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo -e "${YELLOW}1. Edit .env file and add your bot token:${NC}"
echo -e "   ${BLUE}BOT_TOKEN=${NC}your_actual_bot_token_from_botfather"
echo ""
echo -e "${YELLOW}2. Start the bot:${NC}"
echo -e "   ${BLUE}./start_bot.sh${NC}"
echo ""
echo -e "${YELLOW}3. Stop PostgreSQL when done:${NC}"
echo -e "   ${BLUE}./stop_postgres.sh${NC}"
echo ""
echo -e "${BLUE}Database connection details:${NC}"
if is_macos; then
    echo -e "   Host: localhost"
    echo -e "   Port: 5433"
    echo -e "   Database: tgstats"
    echo -e "   Username: andrew"
    echo -e "   Connection: postgresql://andrew@localhost:5433/tgstats"
elif is_linux; then
    echo -e "   Host: localhost"
    echo -e "   Port: 5432"
    echo -e "   Database: tgstats"
    echo -e "   Username: $USER"
    echo -e "   Connection: postgresql://$USER@localhost:5432/tgstats"
fi
echo ""
echo -e "${GREEN}✓ TG Stats Bot is ready to use!${NC}"

#!/bin/bash
# Simple requirements installer for TG Stats Bot

set -e

echo "=== Installing Python Requirements ==="

# Check if virtual environment exists
if [[ ! -d "venv" ]]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install requirements
if [[ -f "pyproject.toml" ]]; then
    echo "Installing from pyproject.toml..."
    pip install -e .
    pip install -e ".[dev]"
elif [[ -f "requirements.txt" ]]; then
    echo "Installing from requirements.txt..."
    pip install -r requirements.txt
    
    if [[ -f "requirements-dev.txt" ]]; then
        pip install -r requirements-dev.txt
    fi
else
    echo "No requirements file found!"
    exit 1
fi

echo "✓ All requirements installed successfully!"
echo ""
echo "Next steps:"
echo "1. Set up PostgreSQL (see README.md)"
echo "2. Create .env file with your bot token"
echo "3. Run: ./start_bot.sh"

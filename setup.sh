#!/usr/bin/env bash
#
# LifeOS Setup Script
# Creates virtual environment, installs dependencies, initializes database.
# Safe to run multiple times (idempotent).
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo ""
echo "=============================="
echo "  LifeOS Setup"
echo "=============================="
echo ""

# Check Python version
info "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    error "Python 3 is required but not found. Please install Python 3.11+."
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]; }; then
    warn "Python 3.11+ recommended. Found: $PYTHON_VERSION"
else
    info "Python $PYTHON_VERSION OK"
fi

# Create virtual environment (if not exists)
info "Setting up virtual environment..."
if [ -d ".venv" ]; then
    info "Virtual environment already exists (.venv)"
else
    python3 -m venv .venv
    info "Created virtual environment (.venv)"
fi

# Activate virtual environment
source .venv/bin/activate

# Upgrade pip
info "Upgrading pip..."
pip install --upgrade pip --quiet

# Install dependencies
info "Installing dependencies..."
pip install -r requirements.txt --quiet
info "Dependencies installed"

# Create .env from example if not exists
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        info "Created .env from .env.example"
        warn "Please edit .env and add your API tokens"
    else
        warn "No .env.example found, skipping .env creation"
    fi
else
    info ".env already exists"
fi

# Initialize database
info "Initializing database..."
python3 -c "
from src.database import init_db
from src.models import *  # Import all models so they register with Base
init_db()
print('Database initialized')
"

echo ""
echo "=============================="
echo "  Setup Complete!"
echo "=============================="
echo ""
echo "Next steps:"
echo "  1. Edit .env and add your OURA_TOKEN and LITELLM_API_KEY"
echo "  2. Activate the virtual environment:"
echo "     source .venv/bin/activate"
echo "  3. Run the server:"
echo "     python -m uvicorn src.api:app --reload --port 8080"
echo ""
echo "Open http://localhost:8080"
echo ""

#!/usr/bin/env bash
#
# LifeOS Setup Script
# Creates virtual environment, installs dependencies, initializes database.
# Features interactive configuration with beautiful colored output.
#
# Usage: ./setup.sh [--skip-prompts]
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ============================================================================
# Colors and Styling
# ============================================================================

# Colors
BLACK='\033[0;30m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
GRAY='\033[0;90m'
NC='\033[0m' # No Color

# Bold
BOLD='\033[1m'
DIM='\033[2m'

# Icons (using ASCII for compatibility)
CHECK="${GREEN}✓${NC}"
CROSS="${RED}✗${NC}"
ARROW="${CYAN}→${NC}"
STAR="${YELLOW}★${NC}"
INFO="${BLUE}ℹ${NC}"
WARN="${YELLOW}⚠${NC}"

# ============================================================================
# Helper Functions
# ============================================================================

print_header() {
    echo ""
    echo -e "${MAGENTA}${BOLD}"
    echo "  ╔═══════════════════════════════════════════════════════════╗"
    echo "  ║                                                           ║"
    echo "  ║   ██╗     ██╗███████╗███████╗ ██████╗ ███████╗           ║"
    echo "  ║   ██║     ██║██╔════╝██╔════╝██╔═══██╗██╔════╝           ║"
    echo "  ║   ██║     ██║█████╗  █████╗  ██║   ██║███████╗           ║"
    echo "  ║   ██║     ██║██╔══╝  ██╔══╝  ██║   ██║╚════██║           ║"
    echo "  ║   ███████╗██║██║     ███████╗╚██████╔╝███████║           ║"
    echo "  ║   ╚══════╝╚═╝╚═╝     ╚══════╝ ╚═════╝ ╚══════╝           ║"
    echo "  ║                                                           ║"
    echo "  ║          Your Personal Operating System                   ║"
    echo "  ╚═══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_step() {
    echo ""
    echo -e "${CYAN}${BOLD}[$1/5]${NC} ${WHITE}$2${NC}"
    echo -e "${DIM}────────────────────────────────────────────────────${NC}"
}

print_success() {
    echo -e "  ${CHECK} $1"
}

print_info() {
    echo -e "  ${INFO} ${GRAY}$1${NC}"
}

print_warn() {
    echo -e "  ${WARN} ${YELLOW}$1${NC}"
}

print_error() {
    echo -e "  ${CROSS} ${RED}$1${NC}"
}

print_arrow() {
    echo -e "  ${ARROW} $1"
}

print_divider() {
    echo -e "${DIM}────────────────────────────────────────────────────────────${NC}"
}

# Prompt for input with default value
prompt_with_default() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"

    if [ -n "$default" ]; then
        echo -en "  ${CYAN}?${NC} ${prompt} ${DIM}[$default]${NC}: "
    else
        echo -en "  ${CYAN}?${NC} ${prompt}: "
    fi

    read -r input
    if [ -z "$input" ]; then
        eval "$var_name=\"$default\""
    else
        eval "$var_name=\"$input\""
    fi
}

# Prompt for secret input (hidden)
prompt_secret() {
    local prompt="$1"
    local var_name="$2"

    echo -en "  ${CYAN}?${NC} ${prompt}: "
    read -rs input
    echo ""
    eval "$var_name=\"$input\""
}

# Yes/no prompt
prompt_yn() {
    local prompt="$1"
    local default="$2"

    if [ "$default" = "y" ]; then
        echo -en "  ${CYAN}?${NC} ${prompt} ${DIM}[Y/n]${NC}: "
    else
        echo -en "  ${CYAN}?${NC} ${prompt} ${DIM}[y/N]${NC}: "
    fi

    read -r input
    input=$(echo "$input" | tr '[:upper:]' '[:lower:]')

    if [ -z "$input" ]; then
        input="$default"
    fi

    [ "$input" = "y" ] || [ "$input" = "yes" ]
}

# Check if running in non-interactive mode
SKIP_PROMPTS=false
if [ "$1" = "--skip-prompts" ] || [ ! -t 0 ]; then
    SKIP_PROMPTS=true
fi

# ============================================================================
# Main Setup
# ============================================================================

print_header

# Step 1: Check Python
print_step "1" "Checking Python Installation"

if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is required but not found"
    echo ""
    echo -e "  ${ARROW} Install Python 3.11+ from ${CYAN}https://python.org${NC}"
    echo -e "  ${ARROW} Or use your package manager:"
    echo -e "     ${DIM}brew install python3        # macOS${NC}"
    echo -e "     ${DIM}sudo apt install python3    # Ubuntu/Debian${NC}"
    echo ""
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]; }; then
    print_warn "Python 3.11+ recommended (found: $PYTHON_VERSION)"
    print_info "Some features may not work correctly"
else
    print_success "Python $PYTHON_VERSION detected"
fi

# Check for venv module
if ! python3 -c "import venv; import ensurepip" &> /dev/null; then
    print_error "Python venv module not available"
    echo ""
    echo -e "  ${ARROW} Install it with:"
    echo -e "     ${DIM}sudo apt install python3.${PYTHON_MINOR}-venv   # Ubuntu/Debian${NC}"
    echo -e "     ${DIM}sudo dnf install python3-venv                  # Fedora${NC}"
    echo ""
    exit 1
fi

print_success "venv module available"

# Step 2: Virtual Environment
print_step "2" "Setting Up Virtual Environment"

if [ -d ".venv" ] && [ -f ".venv/bin/pip" ]; then
    print_success "Virtual environment exists (.venv)"
else
    if [ -d ".venv" ]; then
        print_info "Removing incomplete virtual environment..."
        rm -rf .venv
    fi
    print_info "Creating virtual environment..."
    python3 -m venv .venv
    print_success "Created virtual environment"
fi

# Activate
source .venv/bin/activate
print_success "Activated virtual environment"

# Step 3: Dependencies
print_step "3" "Installing Dependencies"

print_info "Upgrading pip..."
pip install --upgrade pip --quiet 2>/dev/null

print_info "Installing Python packages..."
pip install -r requirements.txt --quiet 2>/dev/null

print_success "All dependencies installed"

# Step 4: Configuration
print_step "4" "Configuring Environment"

ENV_CREATED=false
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        ENV_CREATED=true
        print_success "Created .env from template"
    fi
fi

# Interactive configuration (if not skipping)
if [ "$SKIP_PROMPTS" = false ] && [ "$ENV_CREATED" = true ]; then
    echo ""
    echo -e "  ${STAR} ${WHITE}Let's configure your LifeOS installation${NC}"
    echo ""

    # Oura Token
    echo -e "  ${BOLD}Oura Integration${NC}"
    print_info "Get your token at: https://cloud.ouraring.com/personal-access-tokens"
    echo ""

    if prompt_yn "Configure Oura token now?" "y"; then
        prompt_secret "Oura Personal Access Token" OURA_TOKEN
        if [ -n "$OURA_TOKEN" ]; then
            # Update .env file
            if grep -q "^OURA_TOKEN=" .env; then
                sed -i.bak "s|^OURA_TOKEN=.*|OURA_TOKEN=$OURA_TOKEN|" .env && rm -f .env.bak
            fi
            print_success "Oura token saved"
        fi
    else
        print_info "Skipped - configure later in .env"
    fi

    echo ""

    # AI API Key
    echo -e "  ${BOLD}AI Configuration${NC}"
    print_info "Supports OpenAI, Anthropic, or any LiteLLM-compatible API"
    echo ""

    if prompt_yn "Configure AI API key now?" "y"; then
        prompt_secret "AI API Key (OpenAI/Anthropic)" LITELLM_API_KEY
        if [ -n "$LITELLM_API_KEY" ]; then
            if grep -q "^LITELLM_API_KEY=" .env; then
                sed -i.bak "s|^LITELLM_API_KEY=.*|LITELLM_API_KEY=$LITELLM_API_KEY|" .env && rm -f .env.bak
            fi
            print_success "AI API key saved"
        fi

        # Model selection
        echo ""
        echo -e "  ${DIM}Available models:${NC}"
        echo -e "  ${DIM}  1. gpt-4o-mini (fast, cheap - recommended)${NC}"
        echo -e "  ${DIM}  2. gpt-4o (best quality)${NC}"
        echo -e "  ${DIM}  3. claude-3-5-sonnet (Anthropic)${NC}"
        echo ""
        prompt_with_default "AI model" "gpt-4o-mini" LITELLM_MODEL
        if grep -q "^LITELLM_MODEL=" .env; then
            sed -i.bak "s|^LITELLM_MODEL=.*|LITELLM_MODEL=$LITELLM_MODEL|" .env && rm -f .env.bak
        fi
        print_success "Model set to $LITELLM_MODEL"
    else
        print_info "Skipped - configure later in .env"
    fi

    echo ""

    # Notifications (optional)
    echo -e "  ${BOLD}Notifications (Optional)${NC}"
    print_info "Get your daily brief delivered to Telegram or Discord"
    echo ""

    if prompt_yn "Configure notifications?" "n"; then
        echo ""
        echo -e "  ${DIM}Choose notification method:${NC}"
        echo -e "  ${DIM}  1. Telegram${NC}"
        echo -e "  ${DIM}  2. Discord${NC}"
        echo -e "  ${DIM}  3. Skip${NC}"
        echo ""
        prompt_with_default "Choice" "3" NOTIFY_CHOICE

        case "$NOTIFY_CHOICE" in
            1)
                print_info "Create a bot via @BotFather on Telegram"
                prompt_secret "Telegram Bot Token" TELEGRAM_BOT_TOKEN
                prompt_with_default "Telegram Chat ID" "" TELEGRAM_CHAT_ID
                if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
                    sed -i.bak "s|^# TELEGRAM_BOT_TOKEN=.*|TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN|" .env && rm -f .env.bak
                    sed -i.bak "s|^# TELEGRAM_CHAT_ID=.*|TELEGRAM_CHAT_ID=$TELEGRAM_CHAT_ID|" .env && rm -f .env.bak
                    print_success "Telegram configured"
                fi
                ;;
            2)
                print_info "Create a webhook in Discord channel settings"
                prompt_secret "Discord Webhook URL" DISCORD_WEBHOOK_URL
                if [ -n "$DISCORD_WEBHOOK_URL" ]; then
                    sed -i.bak "s|^# DISCORD_WEBHOOK_URL=.*|DISCORD_WEBHOOK_URL=$DISCORD_WEBHOOK_URL|" .env && rm -f .env.bak
                    print_success "Discord configured"
                fi
                ;;
            *)
                print_info "Skipped notifications"
                ;;
        esac
    else
        print_info "Skipped - configure later in .env"
    fi

elif [ "$ENV_CREATED" = false ]; then
    print_success ".env already configured"
fi

# Step 5: Database
print_step "5" "Initializing Database"

print_info "Creating database tables..."
python3 -c "
from src.database import init_db
from src.models import *
init_db()
" 2>/dev/null

print_success "Database initialized (lifeos.db)"

# ============================================================================
# Completion
# ============================================================================

echo ""
echo -e "${GREEN}${BOLD}"
echo "  ╔═══════════════════════════════════════════════════════════╗"
echo "  ║                                                           ║"
echo "  ║                    Setup Complete!                        ║"
echo "  ║                                                           ║"
echo "  ╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "  ${STAR} ${WHITE}${BOLD}Quick Start${NC}"
echo ""
echo -e "  ${ARROW} Activate the environment:"
echo -e "     ${CYAN}source .venv/bin/activate${NC}"
echo ""
echo -e "  ${ARROW} Start the server:"
echo -e "     ${CYAN}python -m uvicorn src.api:app --reload --port 8080${NC}"
echo ""
echo -e "  ${ARROW} Open in browser:"
echo -e "     ${CYAN}http://localhost:8080${NC}"
echo ""

# Check if tokens are configured
if grep -q "^OURA_TOKEN=your_oura" .env 2>/dev/null || grep -q "^OURA_TOKEN=$" .env 2>/dev/null; then
    echo -e "  ${WARN} ${YELLOW}Don't forget to add your Oura token to .env${NC}"
fi

if grep -q "^LITELLM_API_KEY=your_api" .env 2>/dev/null || grep -q "^LITELLM_API_KEY=$" .env 2>/dev/null; then
    echo -e "  ${WARN} ${YELLOW}Don't forget to add your AI API key to .env${NC}"
fi

echo ""
echo -e "  ${DIM}Need help? See QUICKSTART.md or README.md${NC}"
echo ""

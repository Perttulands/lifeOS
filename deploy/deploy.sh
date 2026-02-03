#!/bin/bash
#
# LifeOS Deploy Script
#
# Simple single-machine deployment for privacy-focused local-first setup.
# Handles: build, deploy, health check, rollback.
#
# Usage:
#   ./deploy/deploy.sh          # Full deployment
#   ./deploy/deploy.sh --quick  # Quick restart (no rebuild)
#   ./deploy/deploy.sh --stop   # Stop all containers
#   ./deploy/deploy.sh --status # Show status
#

set -e

# === Configuration ===
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.production.yml"
BACKUP_DIR="$PROJECT_DIR/backups"
LOG_FILE="$PROJECT_DIR/deploy.log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# === Helper Functions ===

log() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${GREEN}[$timestamp]${NC} $1"
    echo "[$timestamp] $1" >> "$LOG_FILE"
}

error() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${RED}[$timestamp] ERROR:${NC} $1" >&2
    echo "[$timestamp] ERROR: $1" >> "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}WARNING:${NC} $1"
}

header() {
    echo ""
    echo -e "${BLUE}======================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}======================================${NC}"
    echo ""
}

# === Pre-flight Checks ===

check_prerequisites() {
    log "Checking prerequisites..."

    # Check Docker
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    # Check Docker Compose
    if ! docker compose version &> /dev/null; then
        error "Docker Compose is not available. Please install Docker Compose."
        exit 1
    fi

    # Check if compose file exists
    if [ ! -f "$COMPOSE_FILE" ]; then
        error "Compose file not found: $COMPOSE_FILE"
        exit 1
    fi

    # Check for .env file
    if [ ! -f "$PROJECT_DIR/.env" ]; then
        warn ".env file not found. Creating from .env.example..."
        if [ -f "$PROJECT_DIR/.env.example" ]; then
            cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
            warn "Please edit .env with your configuration before deploying."
        else
            error ".env.example not found. Please create .env manually."
            exit 1
        fi
    fi

    # Create backup directory
    mkdir -p "$BACKUP_DIR"

    log "Prerequisites check passed."
}

# === Backup ===

backup_database() {
    log "Creating database backup..."

    local backup_name="lifeos-$(date +%Y%m%d-%H%M%S).db"

    # Check if container is running and has database
    if docker ps --format '{{.Names}}' | grep -q "^lifeos$"; then
        if docker exec lifeos test -f /data/lifeos.db 2>/dev/null; then
            docker cp lifeos:/data/lifeos.db "$BACKUP_DIR/$backup_name"
            log "Backup created: $BACKUP_DIR/$backup_name"

            # Keep only last 5 backups
            cd "$BACKUP_DIR" && ls -t lifeos-*.db 2>/dev/null | tail -n +6 | xargs -r rm --
            log "Old backups cleaned up (keeping last 5)"
        else
            log "No existing database to backup"
        fi
    else
        log "No running container, skipping backup"
    fi
}

# === Build ===

build_image() {
    log "Building Docker image..."

    cd "$PROJECT_DIR"

    # Build with buildkit for better caching
    DOCKER_BUILDKIT=1 docker build \
        --target production \
        -t lifeos:latest \
        -t lifeos:$(date +%Y%m%d) \
        .

    log "Docker image built successfully."
}

# === Deploy ===

deploy() {
    log "Deploying LifeOS..."

    cd "$PROJECT_DIR"

    # Pull any base image updates
    docker compose -f "$COMPOSE_FILE" pull nginx 2>/dev/null || true

    # Start containers
    docker compose -f "$COMPOSE_FILE" up -d

    log "Containers started."
}

# === Health Check ===

wait_for_healthy() {
    log "Waiting for service to become healthy..."

    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        # Try direct container health first, then nginx
        if curl -sf http://localhost:8080/api/health > /dev/null 2>&1; then
            log "Service is healthy! (direct)"
            return 0
        elif curl -sf http://localhost/api/health > /dev/null 2>&1; then
            log "Service is healthy! (via nginx)"
            return 0
        fi

        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done

    echo ""
    error "Service failed to become healthy after $max_attempts attempts"
    return 1
}

# === Rollback ===

rollback() {
    error "Deployment failed. Rolling back..."

    # Find most recent backup
    local latest_backup=$(ls -t "$BACKUP_DIR"/lifeos-*.db 2>/dev/null | head -1)

    if [ -n "$latest_backup" ]; then
        log "Restoring from: $latest_backup"
        docker cp "$latest_backup" lifeos:/data/lifeos.db
        docker compose -f "$COMPOSE_FILE" restart lifeos
        log "Rollback complete"
    else
        warn "No backup found. Manual intervention may be required."
    fi
}

# === Status ===

show_status() {
    header "LifeOS Status"

    echo "Containers:"
    docker ps --filter "name=lifeos" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""

    echo "Health Check:"
    if curl -sf http://localhost/api/health 2>/dev/null; then
        echo ""
        curl -s http://localhost/api/health/detailed 2>/dev/null | python3 -m json.tool 2>/dev/null || true
    elif curl -sf http://localhost:8080/api/health 2>/dev/null; then
        echo ""
        curl -s http://localhost:8080/api/health/detailed 2>/dev/null | python3 -m json.tool 2>/dev/null || true
    else
        echo -e "${RED}Service not responding${NC}"
    fi
}

# === Stop ===

stop_all() {
    log "Stopping all containers..."
    cd "$PROJECT_DIR"
    docker compose -f "$COMPOSE_FILE" down
    log "All containers stopped."
}

# === Main ===

main() {
    header "LifeOS Deployment"

    case "${1:-}" in
        --quick)
            log "Quick restart (no rebuild)..."
            docker compose -f "$COMPOSE_FILE" restart
            wait_for_healthy
            ;;
        --stop)
            stop_all
            ;;
        --status)
            show_status
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --quick   Quick restart without rebuilding"
            echo "  --stop    Stop all containers"
            echo "  --status  Show deployment status"
            echo "  --help    Show this help message"
            echo ""
            echo "With no options, performs full deployment:"
            echo "  1. Check prerequisites"
            echo "  2. Backup database"
            echo "  3. Build Docker image"
            echo "  4. Deploy containers"
            echo "  5. Health check"
            ;;
        "")
            # Full deployment
            check_prerequisites
            backup_database
            build_image
            deploy

            if wait_for_healthy; then
                header "Deployment Successful!"
                log "LifeOS is running at: http://localhost"
                show_status
            else
                rollback
                exit 1
            fi
            ;;
        *)
            error "Unknown option: $1"
            echo "Run '$0 --help' for usage."
            exit 1
            ;;
    esac
}

main "$@"

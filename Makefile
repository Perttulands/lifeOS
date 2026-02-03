# LifeOS Makefile
#
# Common commands for development and deployment.
# Run `make help` to see all available commands.

.PHONY: help dev build test lint clean deploy logs shell backup restore

# Default target
.DEFAULT_GOAL := help

# === Configuration ===
DOCKER_COMPOSE := docker compose
DOCKER_COMPOSE_PROD := docker compose -f docker-compose.production.yml
PYTHON := python3
PYTEST := pytest
IMAGE_NAME := lifeos
CONTAINER_NAME := lifeos

# Colors for terminal output
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m  # No Color

# === Help ===
help: ## Show this help message
	@echo "LifeOS - Available Commands"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}'
	@echo ""

# === Development ===
dev: ## Start development server (local Python, no Docker)
	@echo "$(GREEN)Starting development server...$(NC)"
	$(PYTHON) -m uvicorn src.api:app --reload --host 0.0.0.0 --port 8080

dev-docker: ## Start development server with Docker
	@echo "$(GREEN)Starting Docker development environment...$(NC)"
	$(DOCKER_COMPOSE) up --build

dev-down: ## Stop development Docker containers
	$(DOCKER_COMPOSE) down

install: ## Install Python dependencies
	@echo "$(GREEN)Installing dependencies...$(NC)"
	pip install -r requirements.txt

venv: ## Create and activate virtual environment
	@echo "$(GREEN)Creating virtual environment...$(NC)"
	$(PYTHON) -m venv .venv
	@echo "Run: source .venv/bin/activate"

# === Building ===
build: ## Build Docker image
	@echo "$(GREEN)Building Docker image...$(NC)"
	docker build -t $(IMAGE_NAME):latest .

build-prod: ## Build Docker image for production
	@echo "$(GREEN)Building production Docker image...$(NC)"
	docker build --target production -t $(IMAGE_NAME):latest .
	docker tag $(IMAGE_NAME):latest $(IMAGE_NAME):$$(date +%Y%m%d)

# === Testing ===
test: ## Run all tests
	@echo "$(GREEN)Running tests...$(NC)"
	$(PYTEST) tests/ -v

test-cov: ## Run tests with coverage report
	@echo "$(GREEN)Running tests with coverage...$(NC)"
	$(PYTEST) tests/ -v --cov=src --cov-report=html --cov-report=term

test-fast: ## Run tests (fail fast)
	$(PYTEST) tests/ -x -v

# === Code Quality ===
lint: ## Run linters (ruff)
	@echo "$(GREEN)Running linters...$(NC)"
	@command -v ruff >/dev/null 2>&1 && ruff check src/ tests/ || echo "ruff not installed, skipping"

format: ## Format code (ruff)
	@echo "$(GREEN)Formatting code...$(NC)"
	@command -v ruff >/dev/null 2>&1 && ruff format src/ tests/ || echo "ruff not installed, skipping"

typecheck: ## Run type checker (mypy)
	@echo "$(GREEN)Running type checker...$(NC)"
	@command -v mypy >/dev/null 2>&1 && mypy src/ || echo "mypy not installed, skipping"

# === Deployment ===
deploy: ## Deploy to production (single machine)
	@echo "$(GREEN)Deploying LifeOS to production...$(NC)"
	./deploy/deploy.sh

deploy-up: ## Start production containers
	@echo "$(GREEN)Starting production containers...$(NC)"
	$(DOCKER_COMPOSE_PROD) up -d

deploy-down: ## Stop production containers
	@echo "$(YELLOW)Stopping production containers...$(NC)"
	$(DOCKER_COMPOSE_PROD) down

deploy-restart: ## Restart production containers
	@echo "$(YELLOW)Restarting production containers...$(NC)"
	$(DOCKER_COMPOSE_PROD) restart

deploy-pull: ## Pull latest changes and redeploy
	@echo "$(GREEN)Pulling latest changes and redeploying...$(NC)"
	git pull
	$(MAKE) build-prod
	$(DOCKER_COMPOSE_PROD) up -d

# === Logs & Monitoring ===
logs: ## Show application logs (production)
	$(DOCKER_COMPOSE_PROD) logs -f lifeos

logs-dev: ## Show application logs (development)
	$(DOCKER_COMPOSE) logs -f lifeos

logs-nginx: ## Show nginx logs
	$(DOCKER_COMPOSE_PROD) logs -f nginx

status: ## Show container status
	@echo "$(GREEN)Container Status:$(NC)"
	@docker ps --filter "name=lifeos" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

health: ## Check application health
	@echo "$(GREEN)Health Check:$(NC)"
	@curl -s http://localhost:8080/api/health | python3 -m json.tool 2>/dev/null || \
		curl -s http://localhost/api/health | python3 -m json.tool 2>/dev/null || \
		echo "$(RED)Service not responding$(NC)"

health-detailed: ## Show detailed health status
	@curl -s http://localhost:8080/api/health/detailed | python3 -m json.tool 2>/dev/null || \
		curl -s http://localhost/api/health/detailed | python3 -m json.tool 2>/dev/null || \
		echo "$(RED)Service not responding$(NC)"

# === Database & Backup ===
backup: ## Create database backup
	@echo "$(GREEN)Creating database backup...$(NC)"
	@mkdir -p backups
	@docker cp $(CONTAINER_NAME):/data/lifeos.db backups/lifeos-$$(date +%Y%m%d-%H%M%S).db
	@echo "Backup saved to backups/"

restore: ## Restore database from backup (BACKUP=path/to/backup.db)
	@if [ -z "$(BACKUP)" ]; then \
		echo "$(RED)Usage: make restore BACKUP=path/to/backup.db$(NC)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Restoring database from $(BACKUP)...$(NC)"
	docker cp $(BACKUP) $(CONTAINER_NAME):/data/lifeos.db
	$(MAKE) deploy-restart
	@echo "$(GREEN)Database restored.$(NC)"

db-shell: ## Open SQLite shell
	@docker exec -it $(CONTAINER_NAME) sqlite3 /data/lifeos.db

# === Maintenance ===
shell: ## Open shell in container
	docker exec -it $(CONTAINER_NAME) /bin/sh

clean: ## Clean up Docker resources
	@echo "$(YELLOW)Cleaning up Docker resources...$(NC)"
	docker system prune -f
	docker volume prune -f

clean-all: ## Clean up everything (including volumes - DESTRUCTIVE)
	@echo "$(RED)Warning: This will delete all data!$(NC)"
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ]
	$(DOCKER_COMPOSE_PROD) down -v
	$(DOCKER_COMPOSE) down -v
	docker system prune -af

# === Setup ===
setup: ## Initial setup (copy .env, create directories)
	@echo "$(GREEN)Setting up LifeOS...$(NC)"
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env from .env.example - please configure it"; \
	else \
		echo ".env already exists"; \
	fi
	@mkdir -p backups
	@mkdir -p deploy/certs
	@echo "$(GREEN)Setup complete!$(NC)"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Edit .env with your configuration"
	@echo "  2. Run 'make dev' for development"
	@echo "  3. Run 'make deploy' for production"

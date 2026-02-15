SHELL := /usr/bin/bash

# ─── Directories ────────────────────────────────────────────────────────────────
ROOT_DIR  := $(abspath .)
APPS_DIR  := $(ROOT_DIR)/apps
BACKEND   := $(APPS_DIR)/backend
FRONTEND  := $(APPS_DIR)/frontend
COMPOSE   := docker compose
POETRY    := poetry

# ─── Default ────────────────────────────────────────────────────────────────────
.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ═══════════════════════════════════════════════════════════════════════════════
# Docker Compose (production)
# ═══════════════════════════════════════════════════════════════════════════════
.PHONY: build up down logs restart
.PHONY: up-backend up-frontend restart-backend restart-frontend

build: ## Build all Docker images
	$(COMPOSE) build

up: ## Start all services (detached)
	$(COMPOSE) up -d

down: ## Stop all services
	$(COMPOSE) down

logs: ## Tail logs from all running containers
	$(COMPOSE) logs -f

restart: ## Restart all services
	$(COMPOSE) restart

up-backend: ## Start backend service only
	$(COMPOSE) up -d backend

up-frontend: ## Start frontend service only
	$(COMPOSE) up -d frontend

restart-backend: ## Restart backend service
	$(COMPOSE) restart backend

restart-frontend: ## Restart frontend service
	$(COMPOSE) restart frontend

# ═══════════════════════════════════════════════════════════════════════════════
# Local Development (no Docker)
# ═══════════════════════════════════════════════════════════════════════════════
.PHONY: setup dev dev-backend dev-frontend

setup: ## Full local setup (poetry install, frontend build)
	python3 scripts/setup.py

dev: ## Run backend + frontend locally (parallel)
	$(MAKE) -j 2 dev-backend dev-frontend

dev-backend: ## Run backend with uvicorn (hot-reload)
	FLASK_ENV=development $(POETRY) run uvicorn apps.backend.api.app:asgi_app \
		--host 0.0.0.0 --port 5001 --reload

dev-frontend: ## Run Vite dev server
	@cd $(FRONTEND) && pnpm dev

# ═══════════════════════════════════════════════════════════════════════════════
# Build & Dependencies
# ═══════════════════════════════════════════════════════════════════════════════
.PHONY: deps fe-install fe-build

deps: ## Install Python deps via Poetry
	$(POETRY) install --no-interaction

fe-install: ## Install frontend npm packages
	cd $(FRONTEND) && pnpm install --frozen-lockfile || pnpm install

fe-build: fe-install ## Build frontend for production
	cd $(FRONTEND) && pnpm build

# ═══════════════════════════════════════════════════════════════════════════════
# Quality
# ═══════════════════════════════════════════════════════════════════════════════
.PHONY: lint test

lint: ## Run ruff linter on backend code
	@$(POETRY) run ruff check $(BACKEND) || echo "Install ruff: poetry install --with dev"

test: ## Run pytest
	@$(POETRY) run pytest tests/ -v

# ═══════════════════════════════════════════════════════════════════════════════
# Cleanup
# ═══════════════════════════════════════════════════════════════════════════════
.PHONY: clean clean-venv

clean: ## Remove build artifacts and caches
	rm -rf $(BACKEND)/data/cache/*.json || true
	rm -rf $(BACKEND)/logs/* || true
	rm -rf $(FRONTEND)/build || true
	find $(ROOT_DIR) -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

clean-venv: ## Remove Poetry virtualenv
	$(POETRY) env remove --all 2>/dev/null || true
	rm -rf .venv
PYTHON ?= .venv/bin/python
COMPOSE = docker compose -f docker-compose.dev.yml

.PHONY: setup db-up db-down migrate create-admin reconcile db-backup db-restore dev test test-backend test-frontend e2e

setup:
	$(PYTHON) -m pip install -q -r requirements-dev.txt
	npm --prefix frontend ci

db-up:
	$(COMPOSE) up -d --wait

db-down:
	$(COMPOSE) down

migrate: db-up
	$(PYTHON) -m alembic -c backend/alembic.ini upgrade head

# make create-admin USERNAME=luca NAME="Luca Ducceschi"
create-admin: migrate
	$(PYTHON) -m backend.app.cli create-admin "$(USERNAME)" --display-name "$(NAME)"

# Run after any corpus rebuild, so annotations follow changed text.
reconcile: migrate
	$(PYTHON) -m backend.app.cli reconcile-annotations

db-backup: db-up
	mkdir -p data/backups
	$(COMPOSE) exec -T postgres pg_dump -U didi -d didi --format=custom > data/backups/didi_$$(date +%Y%m%d_%H%M%S).dump
	@ls -t data/backups | head -1

# make db-restore FILE=data/backups/didi_20260101_120000.dump replaces the current data.
db-restore: db-up
	$(COMPOSE) exec -T postgres pg_restore -U didi -d didi --clean --if-exists --no-owner < "$(FILE)"

dev: migrate
	PYTHON=$(PYTHON) ./scripts/dev.sh

test: test-backend test-frontend

test-backend: db-up
	$(PYTHON) -m pytest

test-frontend:
	npm --prefix frontend run lint
	npm --prefix frontend test
	npm --prefix frontend run build

# Runs against its own throwaway database. Needs the real corpus file.
e2e: db-up
	npm --prefix frontend run e2e

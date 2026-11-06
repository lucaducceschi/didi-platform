PYTHON ?= .venv/bin/python
COMPOSE = docker compose -f docker-compose.dev.yml

.PHONY: setup db-up db-down migrate dev test test-backend test-frontend e2e

setup:
	$(PYTHON) -m pip install -q -r requirements-dev.txt
	npm --prefix frontend ci

db-up:
	$(COMPOSE) up -d --wait

db-down:
	$(COMPOSE) down

migrate: db-up
	$(PYTHON) -m alembic -c backend/alembic.ini upgrade head

dev: migrate
	PYTHON=$(PYTHON) ./scripts/dev.sh

test: test-backend test-frontend

test-backend: db-up
	$(PYTHON) -m pytest

test-frontend:
	npm --prefix frontend run lint
	npm --prefix frontend test
	npm --prefix frontend run build

# Needs `make dev` running in another terminal.
e2e:
	npm --prefix frontend run e2e

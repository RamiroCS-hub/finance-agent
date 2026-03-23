.PHONY: help test dev up down build migrate

# Variables
PYTHON := $(shell \
	if [ -x ./venv/bin/python ] && ./venv/bin/python -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then \
		echo ./venv/bin/python; \
	elif [ -x ./.venv/bin/python ] && ./.venv/bin/python -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then \
		echo ./.venv/bin/python; \
	elif [ -x /Users/rcarnicer/.fury/fury_venv/bin/python ] && /Users/rcarnicer/.fury/fury_venv/bin/python -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then \
		echo /Users/rcarnicer/.fury/fury_venv/bin/python; \
	else \
		echo ""; \
	fi \
)
PYTEST = $(PYTHON) -m pytest
UVICORN = $(PYTHON) -m uvicorn
ALEMBIC = $(PYTHON) -m alembic
COMPOSE = $(shell if docker compose version >/dev/null 2>&1; then echo "docker compose"; else echo "docker-compose"; fi)

ifeq ($(PYTHON),)
$(error No se encontró un Python 3.11+ compatible. Creá `venv`/`.venv` con Python 3.11+ o usá un entorno equivalente)
endif

help:
	@echo "Comandos disponibles:"
	@echo "  make dev      - Inicia el servidor de desarrollo local (puerto 8080 por defecto)"
	@echo "  make test     - Ejecuta toda la suite de tests localmente"
	@echo "  make up       - Levanta la infraestructura de Docker (Postgres, Redis) en background"
	@echo "  make down     - Apaga y elimina los contenedores de Docker"
	@echo "  make build    - Construye la imagen de Docker de la aplicación principal"
	@echo "  make migrate  - Aplica las migraciones de base de datos pendientes (Alembic)"

dev:
	$(UVICORN) app.main:app --host 0.0.0.0 --port 8080 --reload

test:
	$(PYTEST) tests/

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

build:
	docker build -t finance_bot_api .

migrate:
	$(ALEMBIC) upgrade head

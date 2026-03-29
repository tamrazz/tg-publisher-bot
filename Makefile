.PHONY: help up down logs shell migrate lint test build

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "  up        Start dev services (bot + postgres)"
	@echo "  down      Stop and remove containers"
	@echo "  logs      Tail bot logs"
	@echo "  shell     Open a shell in the running bot container"
	@echo "  migrate   Run Alembic migrations"
	@echo "  lint      Run ruff linter + format check"
	@echo "  test      Run pytest"
	@echo "  build     Build production Docker image"

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f bot

shell:
	docker compose exec bot bash

migrate:
	docker compose exec bot alembic upgrade head

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

test:
	pytest tests/ -v

build:
	docker build --target $${ENV:-prod} -t tg-publisher-bot:latest .

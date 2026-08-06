# Klarnova — developer Makefile (KLR-A8)
# Targets: dev / up / down / test / lint / migrate / seed / demo / reset

SHELL := cmd
VENV_PY := .venv\Scripts\python.exe
VENV_PIP := .venv\Scripts\pip.exe

.PHONY: dev up down ai-up ai-down migrate test lint seed demo reset

## Backend (local venv, needs postgres+redis via docker)
dev:
	$(VENV_PY) -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload

## Full docker stack (postgres + redis + backend)
up:
	docker compose up -d --build

## AI services (chromadb + ollama)
ai-up:
	docker compose --profile ai up -d

down:
	docker compose down

migrate:
	$(VENV_PY) -m alembic -c backend\alembic.ini upgrade head

migrate-new:
	$(VENV_PY) -m alembic -c backend\alembic.ini revision --autogenerate -m "$(name)"

test:
	$(VENV_PY) -m pytest backend\tests -q

lint:
	$(VENV_PY) -m ruff check backend

seed:
	$(VENV_PY) backend\scripts\seed.py

## Phase 1 demo: apply sample apps + RBAC to the running cluster
demo:
	kubectl apply -f k8s\namespace.yaml
	kubectl apply -f k8s\rbac\
	kubectl apply -f k8s\sample-app\
	kubectl apply -f k8s\monitoring\

reset:
	docker compose down -v

.PHONY: setup dev test lint seed demo deploy reset

SHELL := cmd.exe
.SHELLFLAGS := /C

setup:
	cd backend && .\.venv\Scripts\pip install -r requirements.txt
	cd frontend && npm install

dev:
	cd backend && .\.venv\Scripts\uvicorn app.main:app --reload &
	cd frontend && npm run dev &

test:
	cd backend && .\.venv\Scripts\pytest

lint:
	cd backend && .\.venv\Scripts\ruff check .
	cd frontend && npx tsc --noEmit

seed:
	cd scripts && .\..\backend\.venv\Scripts\python seed.py

demo:
	cd scripts && bash demo.sh

deploy:
	helm install klarnova helm/klarnova

reset:
	cd scripts && bash reset.sh

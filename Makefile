.PHONY: setup dev test lint seed demo deploy reset eval e2e e2e-setup collect

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
	cd frontend && npm run lint
	cd frontend && npx tsc --noEmit

seed:
	cd scripts && .\..\backend\.venv\Scripts\python seed.py

demo:
	cd scripts && bash demo.sh

# Offline chaos evaluation matrix + component ablation, failing (exit 1) if the
# full config drops below the quality thresholds.
eval:
	cd chaos-testing && ..\backend\.venv\Scripts\python run_experiments.py --offline --n 2 --gate
	cd chaos-testing && ..\backend\.venv\Scripts\python ablation.py

# Merge backend + e2e + eval results into one CSV for analysis.
collect:
	.\backend\.venv\Scripts\python scripts\collect-results.py

# Playwright E2E: prepares the host, then runs the suite (needs minikube).
e2e-setup:
	bash scripts/e2e-setup.sh

e2e:
	cd frontend && npm run e2e

deploy:
	helm install klarnova helm/klarnova

reset:
	cd scripts && bash reset.sh

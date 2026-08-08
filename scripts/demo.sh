#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -x backend/.venv/Scripts/python.exe ]; then
  PY=backend/.venv/Scripts/python.exe
elif [ -x backend/.venv/bin/python ]; then
  PY=backend/.venv/bin/python
else
  PY=python
fi

echo "== Starting API port-forward =="
kubectl -n default port-forward svc/klarnova-backend 8000:8000 &
PF_PID=$!
trap 'kill $PF_PID 2>/dev/null || true' EXIT

echo "== Waiting for API to be reachable =="
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    echo "  API healthy."
    break
  fi
  sleep 2
done

echo "== Injecting failure into Sock Shop catalogue =="
bash scripts/inject-failure.sh sock-shop catalogue alpine:3.18

echo ""
echo "== Running demo orchestration (detect -> investigate -> approve -> resolve) =="
"$PY" scripts/demo.py

echo ""
echo "== Demo finished. Restore the app with: bash scripts/reset.sh =="

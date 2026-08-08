#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== Building backend image (host docker -> minikube load) =="
docker build -t klarnova-backend:latest -f backend/Dockerfile .
minikube image load klarnova-backend:latest

echo "== Deploying Helm chart =="
helm upgrade --install klarnova helm/klarnova -n default

echo "== Waiting for rollout =="
kubectl -n default rollout status deployment/klarnova --timeout=180s

echo ""
echo "Setup complete."
echo "  API:     kubectl -n default port-forward svc/klarnova-backend 8000:8000"
echo "  Login:   admin / admin123"

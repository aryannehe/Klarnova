#!/bin/bash
# Prepare the host for the Playwright E2E suite (dashboard + backend + minikube).
#
# The Playwright `webServer` block starts the backend (with an isolated SQLite
# DB via scripts/e2e_bootstrap.py) and the Next.js dev server automatically.
# This script only checks/primes the prerequisites.
set -euo pipefail
cd "$(dirname "$0")/.."

say() { printf '\n== %s ==\n' "$1"; }
fail() { printf 'ERROR: %s\n' "$1" >&2; exit 1; }

say "Checking prerequisites"
command -v kubectl >/dev/null 2>&1 || fail "kubectl not found on PATH"
command -v minikube >/dev/null 2>&1 || fail "minikube not found on PATH"
command -v node >/dev/null 2>&1 || fail "node not found on PATH"
command -v npm >/dev/null 2>&1 || fail "npm not found on PATH"

say "Checking minikube"
if ! minikube status >/dev/null 2>&1; then
  fail "minikube is not running. Start it with: minikube start"
fi
echo "minikube is running."

say "Checking demo namespace (sock-shop)"
if ! kubectl get namespace sock-shop >/dev/null 2>&1; then
  echo "WARNING: namespace 'sock-shop' not found."
  echo "The golden-path E2E specs inject alerts for resources in sock-shop;"
  echo "they still exercise the UI/API but the remediation may not resolve."
  echo "Deploy the demo app with:"
  echo "  kubectl apply -n sock-shop -f https://raw.githubusercontent.com/microservices-demo/microservices-demo/master/deploy/kubernetes/complete-demo.yaml"
else
  echo "sock-shop namespace present."
fi

say "Installing frontend dependencies"
(cd frontend && npm install)

say "Installing Playwright browser (chromium)"
(cd frontend && npx playwright install chromium)

say "Ready"
cat <<'EOF'
Run the E2E suite with:
    cd frontend && npm run e2e
or, from the repo root:
    make e2e

The backend runs against your current kubeconfig context, so ensure
KUBE_IN_CLUSTER=false and that the context points at minikube.
EOF

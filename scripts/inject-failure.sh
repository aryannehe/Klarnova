#!/bin/bash
# Inject a crash-looping image into the Sock Shop catalogue deployment.
# alpine has no useful entrypoint, so the container exits immediately and
# Kubernetes restarts it -> CrashLoopBackOff -> KubePodCrashLooping alert.
set -euo pipefail

NS="${1:-sock-shop}"
DEP="${2:-catalogue}"
IMG="${3:-alpine:3.18}"
BASELINE="${4:-weaveworksdemos/catalogue:0.3.5}"

echo "== Ensuring a clean baseline: $DEP -> $BASELINE =="
kubectl -n "$NS" set image "deployment/$DEP" "$DEP=$BASELINE"
kubectl -n "$NS" rollout status "deployment/$DEP" --timeout=120s

echo "== Injecting failure: $DEP -> $IMG (crashloops on start) =="
kubectl -n "$NS" set image "deployment/$DEP" "$DEP=$IMG"

echo "== Waiting for CrashLoopBackOff =="
for i in $(seq 1 20); do
  state=$(kubectl -n "$NS" get pod -l "name=$DEP" -o jsonpath='{.items[0].status.containerStatuses[0].state.waiting.reason}' 2>/dev/null || true)
  echo "  waiting.reason=$state"
  if [ "$state" = "CrashLoopBackOff" ] || [ "$state" = "ImagePullBackOff" ]; then
    break
  fi
  sleep 3
done
echo "Failure active. The alert will reach Alertmanager and then Klarnova."

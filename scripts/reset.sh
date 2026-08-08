#!/bin/bash
echo "Resetting Sock Shop catalogue deployment to stable state..."
kubectl -n sock-shop set image deployment/catalogue catalogue=weaveworksdemos/catalogue:0.3.5

echo "Waiting for reset rollout..."
kubectl -n sock-shop rollout status deployment/catalogue
echo "Reset complete."

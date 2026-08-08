# Klarnova — Cloud Deployment Runbook (Epic H4)

This runbook deploys the Klarnova backend Helm chart to a managed Kubernetes
cluster (AWS EKS, Azure AKS, or GCP GKE). The chart itself is cloud-agnostic;
`helm/klarnova/values-cloud.yaml` supplies the managed-cluster overrides
(registry, ingress, storage class, resources).

> Goal: the same one-command install as minikube, against a cloud cluster.
> Replace every `<placeholder>` in `values-cloud.yaml` before deploying.

## Prerequisites

| Item           | Notes                                                          |
| -------------- | -------------------------------------------------------------- |
| kubectl + helm | helm v4.x recommended (same as local)                          |
| Registry       | A registry the cluster can pull (ECR / ACR / GCR / Docker Hub) |
| Ingress        | nginx-ingress, or the cloud LB controller (ALB / AGIC / GCE)   |
| Postgres       | Managed PG with `pgvector` (RDS / Azure DB / Cloud SQL) + Ollama + Prometheus endpoints |

## 0. Build and push the image

```bash
docker build -t klarnova-backend:latest -f backend/Dockerfile .

# EKS (Amazon ECR)
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ACCOUNT>.dkr.ecr.us-east-1.amazonaws.com
docker tag klarnova-backend:latest <ACCOUNT>.dkr.ecr.us-east-1.amazonaws.com/klarnova-backend:latest
docker push <ACCOUNT>.dkr.ecr.us-east-1.amazonaws.com/klarnova-backend:latest

# AKS (Azure Container Registry)
az acr login --name <ACR>
docker tag klarnova-backend:latest <ACR>.azurecr.io/klarnova-backend:latest
docker push <ACR>.azurecr.io/klarnova-backend:latest

# GKE (Artifact Registry)
docker tag klarnova-backend:latest <REGION>-docker.pkg.dev/<PROJECT>/<REPO>/klarnova-backend:latest
docker push <REGION>-docker.pkg.dev/<PROJECT>/<REPO>/klarnova-backend:latest
```

## 1. Point the values at your endpoints

Edit `helm/klarnova/values-cloud.yaml`:

- `image.repository` — the pushed image, e.g. `<ACCOUNT>.dkr.ecr.us-east-1.amazonaws.com/klarnova-backend`.
- `configmap.DATABASE_URL` — managed Postgres DSN. Install `pgvector` on it and
  run the Alembic migrations (`alembic upgrade head`) from a jump host first.
- `configmap.OLLAMA_BASE_URL` / `configmap.PROMETHEUS_URL` — your Ollama and
  Prometheus (or kube-prometheus-stack) endpoints reachable from the cluster.
- `configmap.ALERTMANAGER_WEBHOOK_TOKEN` / `configmap.JWT_SECRET` — real
  secrets. For production, replace the ConfigMap with a Secret and wire via
  `envFrom` (the chart ships dev defaults by design).
- `persistence.storageClass` — leave empty for the cloud default, or pin
  `gp3` (EKS), `managed-csi` (AKS), `standard-rwo` (GKE).
- `ingress.host` — the DNS name terminating at your ingress controller.

## 2. Deploy

```bash
helm upgrade --install klarnova helm/klarnova \
  -f helm/klarnova/values.yaml \
  -f helm/klarnova/values-cloud.yaml \
  --namespace klarnova --create-namespace

kubectl -n klarnova rollout status deployment/klarnova
kubectl -n klarnova get pods,svc,ingress
```

## 3. Verify

```bash
curl https://<klarnova.example.com>/health
# {"status":"ok"}

# Login smoke test (seed users: admin/admin123)
curl -s -u admin:admin123 \
  https://<klarnova.example.com>/v1/auth/login \
  -d grant_type=password | head -c 120
```

## Provider-specific ingress notes

- **EKS**: install `aws-load-balancer-controller` and set
  `ingress.className: alb` with the `alb.ingress.kubernetes.io/*` annotations
  in `values-cloud.yaml`.
- **AKS**: `ingress.className: webapprouting.kubernetes.azure.com` (or nginx),
  using the `nginx` class with AGIC.
- **GKE**: `ingress.className: gce`, exposing the backend behind a global LB.

## Rollback

```bash
helm -n klarnova rollback klarnova <REVISION>
```

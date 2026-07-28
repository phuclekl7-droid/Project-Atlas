# 🐳 Kubernetes Deployment for Project Atlas

This directory contains Kubernetes manifests to deploy Project Atlas
on any Kubernetes cluster (minikube, kind, EKS, GKE, AKS).

## Prerequisites

- Kubernetes 1.24+
- kubectl configured
- (Optional) Helm for advanced deployment

## Quick Start

```bash
# 1. Create the namespace
kubectl apply -f namespace.yaml

# 2. Create secrets (edit secrets.yaml first with your API keys)
kubectl apply -f secrets.yaml

# 3. Deploy the application
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml

# 4. (Optional) Ingress for external access
kubectl apply -f ingress.yaml

# 5. Check status
kubectl -n project-atlas get pods
kubectl -n project-atlas get services
```

## Access

```bash
# Port-forward to localhost
kubectl -n project-atlas port-forward svc/atlas 8501:8501

# Open in browser
open http://localhost:8501
```

## Resource Requirements

| Component | CPU | Memory | Storage |
|-----------|-----|--------|---------|
| Atlas App | 500m | 512Mi | 1Gi (PVC) |
| ChromaDB  | 500m | 512Mi | 2Gi (PVC) |

## Configuration

Edit `secrets.yaml` to set:
- `OPENAI_API_KEY` (optional)
- `GEMINI_API_KEY` (optional)
- `WEATHER_API_KEY` (optional)

Edit `configmap.yaml` to set:
- `MODEL_PROVIDER`: "ollama" or "mock"
- `OLLAMA_URL`: your Ollama server URL
- `LOG_LEVEL`: "INFO" or "DEBUG"

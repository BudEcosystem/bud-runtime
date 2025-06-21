# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Bud Runtime is a Kubernetes-based microservices platform for AI/ML model serving. It uses Helm charts to deploy an ecosystem of applications with comprehensive infrastructure support including databases, observability tools, and service mesh capabilities.

## Common Development Commands

### Initial Setup
```bash
# Set up K3s cluster (run once)
./scripts/setup-cluster.sh

# Configure kubectl
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
alias kubectl='k3s kubectl'
```

### Helm Repository Setup
```bash
helm repo add minio https://charts.min.io/
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add dapr https://dapr.github.io/helm-charts/
helm repo add jetstack https://charts.jetstack.io
helm repo add altinity https://helm.altinity.com
helm repo add clickhouse-operator https://docs.altinity.com/clickhouse-operator
helm repo update
```

### Pre-requisites Installation
```bash
# Install ClickHouse Operator
helm install altinity-clickhouse-operator altinity-clickhouse-operator/altinity-clickhouse-operator \
  --namespace clickhouse-operator --create-namespace

# Install Cert-Manager
helm install cert-manager jetstack/cert-manager \
  --namespace bud-system --create-namespace --set installCRDs=true
```

### Deploy Bud Stack
```bash
# Update dependencies
cd helm/bud-stack
helm dependency update

# Install the stack
helm install bud-release . --namespace dapr-system --create-namespace -f values.yaml

# Upgrade existing deployment
helm upgrade bud-release . -n dapr-system -f values.yaml

# Check deployment status
helm status bud-release -n dapr-system
kubectl get pods -n dapr-system
```

### Validation and Debugging
```bash
# Lint the Helm chart
helm lint ./helm/bud-stack

# Test template rendering
helm template bud-release ./helm/bud-stack --debug

# View logs
kubectl logs -n dapr-system <pod-name>

# Port forward for local access
kubectl port-forward -n dapr-system svc/grafana 3000:80
kubectl port-forward -n dapr-system svc/prometheus 9090:9090
```

### Utility Scripts
```bash
# Generate RSA key pairs
python scripts/key_generator.py --directory ./keys --password mysecret
```

## Architecture Overview

The platform consists of interconnected microservices deployed via Helm:

### Core Services
- **budapp**: Main application service
- **budsim**: Simulator service for testing
- **budcluster**: Cluster resource management
- **budmodel**: ML model management service
- **budmetrics**: Metrics collection and aggregation
- **budproxy**: LiteLLM proxy for model serving
- **notify**: Notification service (Novu-based)

### Infrastructure Components
- **PostgreSQL**: Primary database and metrics database (separate instances)
- **MongoDB**: Document storage for unstructured data
- **Redis Stack**: Caching, pub/sub, and dynamic configuration
- **MinIO**: S3-compatible object storage for models and artifacts
- **ClickHouse**: Analytics and time-series data processing
- **Dapr**: Service mesh for inter-service communication
- **Traefik**: Ingress controller for external access

### Observability Stack
- **Prometheus**: Metrics collection
- **Grafana**: Visualization and dashboards
- **Alertmanager**: Alert routing and management

### Key Architectural Patterns
1. **Service Mesh**: All services communicate via Dapr sidecars for resilience and observability
2. **Configuration Management**: Dynamic configuration via Redis with ConfigMaps for static values
3. **Multi-Database**: Different databases for different use cases (relational, document, cache, analytics)
4. **Gateway Pattern**: Modified TensorZero gateway provides unified API access with authentication
5. **NUMA-Aware Scheduling**: Performance optimization for multi-socket systems

## Configuration Structure

Primary configuration is in `helm/bud-stack/values.yaml`:
- Global environment variables for cross-service configuration
- Per-service configuration sections with image, resources, and Dapr settings
- Infrastructure component configurations (databases, storage)
- Ingress rules and TLS settings
- Persistent volume configurations

## Development Tips

1. When modifying services, check if they use Dapr annotations in their deployment templates
2. Database connections are configured via environment variables in the global section
3. All services are deployed in the `dapr-system` namespace by default
4. The setup script configures system-level optimizations - review before running in production
5. Use `helm template` to preview changes before applying them
6. Monitor resource usage via Grafana dashboards after deployment
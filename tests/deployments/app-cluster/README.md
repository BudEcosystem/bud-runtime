# App Cluster Test Deployments

This directory contains test deployments for the application cluster.

## Services

### BudProxy (TensorZero Gateway)
- **Image**: `budstudio/budproxy:nightly`
- **Port**: 3000
- **Status**: ✅ Working
- **Configuration**: Running with default config (no Redis/ClickHouse)

## Deployment

```bash
kubectl config use-context k3d-bud-app
kubectl apply -f budproxy.yaml
```

## Access

```bash
# Port forward
kubectl port-forward -n bud-system svc/budproxy-service 8890:3000

# Test
curl http://localhost:8890/status
```

## Notes

- Using default configuration as Redis and ClickHouse are not deployed
- In production, would need proper tensorzero.toml configuration
- Ready for connecting to inference services once properly configured
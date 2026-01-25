# Day-2 Operations Guide

> **Version:** 1.0
> **Last Updated:** 2026-01-23
> **Status:** Operational Guide
> **Audience:** Platform administrators, site reliability engineers

---

## 1. Overview

This guide covers routine administrative tasks for operating Bud AI Foundry in production. It assumes the platform is successfully deployed and focuses on day-to-day operations.

---

## 2. Daily Operations Checklist

### 2.1 Morning Health Check

| Check | Command/Location | Expected State |
|-------|------------------|----------------|
| Pod status | `kubectl get pods -n bud-system` | All Running |
| Service endpoints | Grafana → Health Dashboard | All green |
| Database connectivity | `kubectl exec budapp -- python -c "from budapp.db import engine"` | No errors |
| Dapr sidecar status | `dapr status -k` | All healthy |
| Error rate | Grafana → Error Dashboard | < 0.1% |
| Pending alerts | Grafana → Alerting | None critical |

### 2.2 Health Check Commands

```bash
# Check all pods in bud-system namespace
kubectl get pods -n bud-system -o wide

# Check service health
kubectl get svc -n bud-system

# Check Dapr status
dapr status -k -n bud-system

# Check recent events
kubectl get events -n bud-system --sort-by='.lastTimestamp' | tail -20

# Check resource utilization
kubectl top pods -n bud-system
kubectl top nodes
```

---

## 3. User Management

### 3.1 Create User

**Via API:**

```bash
# Get admin token
TOKEN=$(curl -s -X POST "https://api.bud.example.com/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"..."}' | jq -r '.access_token')

# Create user
curl -X POST "https://api.bud.example.com/users" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newuser@example.com",
    "first_name": "New",
    "last_name": "User",
    "role": "USER"
  }'
```

**Via Keycloak Admin Console:**

1. Navigate to Keycloak Admin → Users
2. Click "Add User"
3. Fill in required fields
4. Set temporary password
5. User will receive email invitation

### 3.2 Modify User Role

```bash
# Update user role
curl -X PUT "https://api.bud.example.com/users/{user_id}" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"role": "PROJECT_ADMIN"}'
```

### 3.3 Deactivate User

```bash
# Deactivate user (keeps audit history)
curl -X PUT "https://api.bud.example.com/users/{user_id}" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "INACTIVE"}'
```

### 3.4 Password Reset

```bash
# Trigger password reset email
curl -X POST "https://api.bud.example.com/auth/password/reset" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com"}'
```

---

## 4. Project Management

### 4.1 Create Project

```bash
curl -X POST "https://api.bud.example.com/projects" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "New Project",
    "description": "Project description"
  }'
```

### 4.2 Manage Project Permissions

```bash
# Grant user access to project
curl -X POST "https://api.bud.example.com/permissions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-uuid",
    "resource_type": "project",
    "resource_id": "project-uuid",
    "permission_level": "edit"
  }'
```

### 4.3 Delete Project

> **Warning:** This is irreversible. Ensure all endpoints are undeployed first.

```bash
# First undeploy all endpoints
for endpoint in $(curl -s "https://api.bud.example.com/projects/{id}/endpoints" \
  -H "Authorization: Bearer $TOKEN" | jq -r '.[].id'); do
  curl -X POST "https://api.bud.example.com/endpoints/$endpoint/undeploy" \
    -H "Authorization: Bearer $TOKEN"
done

# Then delete project
curl -X DELETE "https://api.bud.example.com/projects/{project_id}" \
  -H "Authorization: Bearer $TOKEN"
```

---

## 5. Endpoint Management

### 5.1 Deploy Endpoint

```bash
curl -X POST "https://api.bud.example.com/endpoints/{endpoint_id}/deploy" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "cluster_id": "cluster-uuid",
    "replicas": 1,
    "resources": {
      "gpu_count": 1,
      "memory_gb": 16
    }
  }'
```

### 5.2 Check Deployment Status

```bash
# Get endpoint status
curl "https://api.bud.example.com/endpoints/{endpoint_id}" \
  -H "Authorization: Bearer $TOKEN" | jq '.status'

# Expected values: DEPLOYING, RUNNING, STOPPED, FAILED
```

### 5.3 Scale Endpoint

```bash
curl -X PUT "https://api.bud.example.com/endpoints/{endpoint_id}" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"replicas": 3}'
```

### 5.4 Undeploy Endpoint

```bash
curl -X POST "https://api.bud.example.com/endpoints/{endpoint_id}/undeploy" \
  -H "Authorization: Bearer $TOKEN"
```

---

## 6. Cluster Operations

### 6.1 View Cluster Status

```bash
# List all clusters
curl "https://api.bud.example.com/clusters" \
  -H "Authorization: Bearer $TOKEN"

# Get specific cluster details
curl "https://api.bud.example.com/clusters/{cluster_id}" \
  -H "Authorization: Bearer $TOKEN"
```

### 6.2 Cluster Health Check

```bash
# Check cluster nodes
kubectl --kubeconfig=/path/to/cluster-kubeconfig get nodes

# Check GPU availability
kubectl --kubeconfig=/path/to/cluster-kubeconfig describe nodes | grep -A10 "Capacity:"

# Check deployments
kubectl --kubeconfig=/path/to/cluster-kubeconfig get deployments -n bud-workloads
```

### 6.3 Refresh Cluster Status

```bash
# Trigger status refresh
curl -X POST "https://api.bud.example.com/clusters/{cluster_id}/refresh" \
  -H "Authorization: Bearer $TOKEN"
```

---

## 7. Monitoring Operations

### 7.1 Key Dashboards

| Dashboard | Purpose | Grafana Path |
|-----------|---------|--------------|
| Platform Overview | High-level health | /d/platform-overview |
| Inference Metrics | Request latency, throughput | /d/inference-metrics |
| Resource Utilization | CPU/GPU/Memory | /d/resource-util |
| Error Tracking | Error rates and details | /d/error-tracking |
| Audit Activity | User actions | /d/audit-activity |

### 7.2 Key Metrics to Watch

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| `inference_latency_p99` | > 2s | > 5s | Scale or optimize |
| `error_rate` | > 1% | > 5% | Investigate logs |
| `gpu_utilization` | > 80% | > 95% | Scale cluster |
| `queue_depth` | > 100 | > 500 | Scale endpoints |
| `db_connections` | > 80 | > 95 | Check connection leaks |

### 7.3 Query Logs

**Loki Query Examples:**

```logql
# Find errors in budapp
{app="budapp"} |= "error" | json

# Find slow requests
{app="budgateway"} | json | latency_ms > 2000

# Track specific user
{app="budapp"} | json | user_id="uuid"

# Find authentication failures
{app="budapp"} |= "LOGIN_FAILED"
```

---

## 8. Scheduled Maintenance Tasks

### 8.1 Weekly Tasks

| Task | Description | Command/Procedure |
|------|-------------|-------------------|
| Access review | Verify user access is appropriate | Export user list, review |
| Log retention | Verify log archival | Check Loki retention |
| Backup verification | Test restore of recent backup | See Backup Procedures |
| Security updates | Review and apply patches | Helm upgrade |

### 8.2 Monthly Tasks

| Task | Description | Command/Procedure |
|------|-------------|-------------------|
| Certificate expiry | Check upcoming expirations | `kubectl get certificates -A` |
| Capacity review | Review usage trends | Grafana capacity dashboard |
| Quota review | Verify quotas are appropriate | Review project quotas |
| Performance baseline | Compare to baseline | Review latency trends |

### 8.3 Quarterly Tasks

| Task | Description | Procedure |
|------|-------------|-----------|
| DR drill | Test disaster recovery | DR Drill Procedure |
| Access audit | Full access review | Export all permissions |
| Security review | Vulnerability assessment | Run security scan |
| Documentation update | Review and update docs | This guide |

---

## 9. Common Administrative Tasks

### 9.1 Export Audit Log

```bash
# Export audit log for date range
curl "https://api.bud.example.com/audit/export" \
  -H "Authorization: Bearer $TOKEN" \
  -G \
  --data-urlencode "start_date=2026-01-01T00:00:00Z" \
  --data-urlencode "end_date=2026-01-31T23:59:59Z" \
  --data-urlencode "format=csv" \
  -o audit_export.csv
```

### 9.2 Check API Quota Usage

```bash
# Get project quota usage
curl "https://api.bud.example.com/projects/{project_id}/billing/quota" \
  -H "Authorization: Bearer $TOKEN"
```

### 9.3 Rotate API Key

```bash
# Create new credential
curl -X POST "https://api.bud.example.com/credentials" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "API Key v2",
    "project_id": "project-uuid"
  }'

# Get the key value (only shown once)
# Then delete old credential
curl -X DELETE "https://api.bud.example.com/credentials/{old_credential_id}" \
  -H "Authorization: Bearer $TOKEN"
```

### 9.4 View Service Logs

```bash
# View budapp logs
kubectl logs -n bud-system deployment/budapp --tail=100 -f

# View budcluster logs
kubectl logs -n bud-system deployment/budcluster --tail=100 -f

# View all service logs (aggregated)
# Use Grafana Explore → Loki
```

---

## 10. Troubleshooting Quick Reference

### 10.1 Service Not Responding

```bash
# Check pod status
kubectl get pods -n bud-system -l app=budapp

# Check pod logs
kubectl logs -n bud-system deployment/budapp --tail=100

# Check Dapr sidecar
kubectl logs -n bud-system deployment/budapp -c daprd --tail=100

# Restart deployment
kubectl rollout restart deployment/budapp -n bud-system
```

### 10.2 Database Connection Issues

```bash
# Check PostgreSQL pod
kubectl get pods -n bud-data -l app=postgresql

# Check connection from budapp pod
kubectl exec -n bud-system deployment/budapp -- \
  python -c "from budapp.db import engine; print('OK')"

# Check connection pool
# Review pg_stat_activity in PostgreSQL
```

### 10.3 Inference Failures

```bash
# Check endpoint status
curl "https://api.bud.example.com/endpoints/{id}" \
  -H "Authorization: Bearer $TOKEN"

# Check vLLM pod in target cluster
kubectl --kubeconfig=/path/to/cluster get pods -n bud-workloads

# Check GPU utilization
kubectl --kubeconfig=/path/to/cluster exec -it <vllm-pod> -- nvidia-smi
```

---

## 11. Emergency Contacts

| Role | Name | Contact | Escalation |
|------|------|---------|------------|
| On-call Engineer | [Name] | [Phone] | Primary |
| Platform Lead | [Name] | [Phone] | 15 min |
| Engineering Manager | [Name] | [Phone] | 30 min |
| VP Engineering | [Name] | [Phone] | Critical only |

---

## 12. Related Documentation

| Document | Description |
|----------|-------------|
| Troubleshooting Guide | Detailed troubleshooting procedures |
| Incident Response Playbook | Classification and response |
| Backup Procedures | Backup and restore |
| Monitoring Architecture | Observability stack details |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-23 | Documentation | Initial version |

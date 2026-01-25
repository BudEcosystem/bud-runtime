# Troubleshooting Guide

> **Version:** 1.0
> **Last Updated:** 2026-01-23
> **Status:** Operational Guide
> **Audience:** SREs, platform engineers, support

---

## 1. Quick Reference

### 1.1 Common Issues at a Glance

| Symptom | Likely Cause | Quick Fix | Section |
|---------|--------------|-----------|---------|
| 401 Unauthorized | Token expired | Refresh token | 2.1 |
| 403 Forbidden | Missing permission | Check RBAC | 2.2 |
| 500 Internal Error | Service failure | Check logs | 3.1 |
| 503 Service Unavailable | Pod not ready | Check health | 3.2 |
| Slow inference | Resource contention | Scale up | 4.1 |
| Deployment stuck | Cluster issues | Check cluster | 5.1 |
| Database timeout | Connection pool | Check connections | 6.1 |

---

## 2. Authentication & Authorization Issues

### 2.1 "401 Unauthorized" Errors

**Symptoms:**
- API returns `401 Unauthorized`
- UI redirects to login repeatedly
- Token refresh fails

**Diagnosis:**

```bash
# Check if token is valid
TOKEN="your-token"
jwt decode $TOKEN 2>/dev/null || echo "Invalid token format"

# Check token expiry
exp=$(jwt decode $TOKEN 2>/dev/null | jq -r '.exp')
now=$(date +%s)
[ "$exp" -lt "$now" ] && echo "Token expired"

# Check Keycloak is accessible
curl -s https://keycloak.example.com/realms/bud/.well-known/openid-configuration
```

**Solutions:**

| Cause | Solution |
|-------|----------|
| Token expired | Refresh token or re-authenticate |
| Keycloak down | Check Keycloak pods: `kubectl get pods -n bud-auth` |
| Clock skew | Sync NTP on all nodes |
| Wrong audience | Verify client ID in token |

### 2.2 "403 Forbidden" Errors

**Symptoms:**
- API returns `403 Forbidden`
- User can login but cannot access resources

**Diagnosis:**

```bash
# Check user permissions
curl "https://api.bud.example.com/permissions?user_id={user_id}" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Check user role
curl "https://api.bud.example.com/users/{user_id}" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.role'
```

**Solutions:**

| Cause | Solution |
|-------|----------|
| Missing permission | Grant permission via API or UI |
| Wrong project | Check user is in correct project |
| Role mismatch | Update user role |
| Resource deleted | Verify resource exists |

---

## 3. Service Issues

### 3.1 "500 Internal Server Error"

**Symptoms:**
- API returns `500` status
- UI shows generic error

**Diagnosis:**

```bash
# Check service logs
kubectl logs -n bud-system deployment/budapp --tail=200 | grep -i error

# Check Dapr sidecar logs
kubectl logs -n bud-system deployment/budapp -c daprd --tail=100

# Check recent events
kubectl get events -n bud-system --sort-by='.lastTimestamp' | tail -20

# Check service metrics
# Grafana → Explore → Prometheus
# Query: rate(http_requests_total{status=~"5.."}[5m])
```

**Common Causes:**

| Cause | Indicator | Solution |
|-------|-----------|----------|
| Database error | "connection refused" in logs | Check PostgreSQL |
| Dapr failure | "dapr" in error message | Restart Dapr sidecar |
| Memory OOM | OOMKilled status | Increase memory limits |
| Unhandled exception | Stack trace in logs | Review code/deploy fix |

### 3.2 "503 Service Unavailable"

**Symptoms:**
- Intermittent `503` errors
- Service shows as unhealthy

**Diagnosis:**

```bash
# Check pod status
kubectl get pods -n bud-system -l app=budapp -o wide

# Check pod health
kubectl describe pod -n bud-system <pod-name> | grep -A5 "Conditions:"

# Check readiness probe
kubectl describe deployment -n bud-system budapp | grep -A10 "Readiness:"

# Check service endpoints
kubectl get endpoints -n bud-system budapp
```

**Solutions:**

| Cause | Solution |
|-------|----------|
| Pod starting | Wait for readiness |
| Readiness probe failing | Check probe configuration |
| No endpoints | Scale deployment up |
| Network policy | Check network policies |

### 3.3 Service Not Starting

**Symptoms:**
- Pod in `CrashLoopBackOff`
- Pod stuck in `Pending`
- Container restarting

**Diagnosis:**

```bash
# Check pod events
kubectl describe pod -n bud-system <pod-name>

# Check container logs
kubectl logs -n bud-system <pod-name> --previous

# Check resource requests
kubectl describe pod -n bud-system <pod-name> | grep -A5 "Requests:"
```

**Solutions:**

| Status | Cause | Solution |
|--------|-------|----------|
| CrashLoopBackOff | Application error | Check logs, fix code |
| Pending | No resources | Scale cluster or reduce requests |
| ImagePullBackOff | Wrong image | Check image name and registry access |
| Init:Error | Init container failed | Check init container logs |

---

## 4. Performance Issues

### 4.1 Slow Inference

**Symptoms:**
- High latency on inference requests
- Timeouts on model calls

**Diagnosis:**

```bash
# Check endpoint metrics
# Grafana → Inference Metrics dashboard

# Check queue depth
curl "https://api.bud.example.com/endpoints/{id}/metrics" \
  -H "Authorization: Bearer $TOKEN"

# Check GPU utilization on target cluster
kubectl --kubeconfig=/path/to/cluster exec -it <vllm-pod> -- nvidia-smi

# Check vLLM logs
kubectl --kubeconfig=/path/to/cluster logs <vllm-pod> --tail=100
```

**Solutions:**

| Cause | Indicator | Solution |
|-------|-----------|----------|
| High queue depth | Queue > 100 | Scale replicas |
| GPU contention | GPU util > 95% | Add GPUs or optimize |
| Large requests | Token count high | Reduce max tokens |
| Cold start | First request slow | Keep minimum replicas |

### 4.2 Slow API Response

**Symptoms:**
- Dashboard loading slowly
- API timeouts

**Diagnosis:**

```bash
# Check service latency
# Grafana → Service Latency dashboard

# Trace a request
# Grafana → Explore → Tempo
# Search by request_id

# Check database queries
# Enable slow query log in PostgreSQL
```

**Solutions:**

| Cause | Solution |
|-------|----------|
| Database slow | Add indexes, optimize queries |
| High CPU | Scale horizontally |
| Network latency | Check network policies |
| Large response | Paginate results |

---

## 5. Deployment Issues

### 5.1 Endpoint Deployment Stuck

**Symptoms:**
- Endpoint status stuck at `DEPLOYING`
- Deployment timeout

**Diagnosis:**

```bash
# Check deployment status
curl "https://api.bud.example.com/endpoints/{id}" \
  -H "Authorization: Bearer $TOKEN"

# Check Dapr workflow state
kubectl logs -n bud-system deployment/budcluster | grep "endpoint_id"

# Check target cluster
kubectl --kubeconfig=/path/to/cluster get deployments -n bud-workloads
kubectl --kubeconfig=/path/to/cluster get pods -n bud-workloads
```

**Solutions:**

| Cause | Solution |
|-------|----------|
| Image pull failed | Check image registry access |
| Insufficient resources | Scale cluster or reduce requirements |
| PVC pending | Check storage provisioner |
| Network issue | Check cluster connectivity |

### 5.2 Cluster Not Available

**Symptoms:**
- Cluster status shows `NOT_AVAILABLE` or `ERROR`
- Cannot deploy to cluster

**Diagnosis:**

```bash
# Check cluster status
curl "https://api.bud.example.com/clusters/{id}" \
  -H "Authorization: Bearer $TOKEN"

# Check connectivity
kubectl --kubeconfig=/path/to/cluster get nodes

# Check budcluster logs
kubectl logs -n bud-system deployment/budcluster | grep "cluster_id"

# Verify kubeconfig
kubectl --kubeconfig=/path/to/cluster cluster-info
```

**Solutions:**

| Cause | Solution |
|-------|----------|
| Kubeconfig expired | Re-register cluster |
| Network unreachable | Check VPN/firewall |
| API server down | Contact cluster admin |
| Credentials revoked | Update service account |

---

## 6. Database Issues

### 6.1 Connection Timeouts

**Symptoms:**
- "connection timed out" errors
- Slow database queries
- Pool exhausted errors

**Diagnosis:**

```bash
# Check PostgreSQL connections
kubectl exec -n bud-data postgresql-0 -- psql -U bud -c \
  "SELECT count(*) FROM pg_stat_activity;"

# Check connection pool settings
kubectl exec -n bud-system deployment/budapp -- \
  env | grep DATABASE

# Check PostgreSQL logs
kubectl logs -n bud-data postgresql-0 --tail=100
```

**Solutions:**

| Cause | Solution |
|-------|----------|
| Too many connections | Increase pool size or max connections |
| Long-running queries | Kill blocking queries |
| Network issue | Check network policies |
| PostgreSQL resource | Scale PostgreSQL resources |

### 6.2 Database Lock Issues

**Symptoms:**
- Queries hanging
- "deadlock detected" errors
- Transactions timing out

**Diagnosis:**

```sql
-- Find blocking queries (run in PostgreSQL)
SELECT blocked_locks.pid AS blocked_pid,
       blocking_locks.pid AS blocking_pid,
       blocked_activity.query AS blocked_query,
       blocking_activity.query AS blocking_query
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity
  ON blocked_locks.pid = blocked_activity.pid
JOIN pg_catalog.pg_locks blocking_locks
  ON blocking_locks.locktype = blocked_locks.locktype
JOIN pg_catalog.pg_stat_activity blocking_activity
  ON blocking_locks.pid = blocking_activity.pid
WHERE NOT blocked_locks.granted;
```

**Solutions:**

| Cause | Solution |
|-------|----------|
| Long transaction | Kill blocking process |
| Application bug | Review transaction handling |
| Missing index | Add appropriate indexes |

---

## 7. Network Issues

### 7.1 Inter-Service Communication Failure

**Symptoms:**
- Service-to-service calls failing
- "connection refused" between services

**Diagnosis:**

```bash
# Check service endpoints
kubectl get endpoints -n bud-system

# Check Dapr status
dapr status -k -n bud-system

# Test connectivity from pod
kubectl exec -n bud-system deployment/budapp -- \
  curl -v http://localhost:3500/v1.0/invoke/budcluster/method/health

# Check network policies
kubectl get networkpolicies -n bud-system -o yaml
```

**Solutions:**

| Cause | Solution |
|-------|----------|
| Service not running | Start the target service |
| Network policy blocking | Update network policy |
| Dapr sidecar issue | Restart pod or Dapr |
| DNS issue | Check CoreDNS |

### 7.2 External Connectivity Issues

**Symptoms:**
- Cannot reach external APIs (OpenAI, etc.)
- Model provider calls failing

**Diagnosis:**

```bash
# Test external connectivity
kubectl exec -n bud-system deployment/budgateway -- \
  curl -v https://api.openai.com/v1/models

# Check egress network policies
kubectl get networkpolicies -n bud-system -o yaml | grep -A20 "egress"

# Check proxy settings
kubectl exec -n bud-system deployment/budgateway -- env | grep -i proxy
```

**Solutions:**

| Cause | Solution |
|-------|----------|
| Network policy | Allow egress to required hosts |
| Proxy required | Configure HTTP proxy |
| DNS resolution | Check external DNS |
| Firewall | Update firewall rules |

---

## 8. Storage Issues

### 8.1 PVC Pending

**Symptoms:**
- PersistentVolumeClaim stuck in `Pending`
- Pod waiting for volume

**Diagnosis:**

```bash
# Check PVC status
kubectl get pvc -n bud-data

# Check storage class
kubectl get storageclass

# Check events
kubectl describe pvc -n bud-data <pvc-name>
```

**Solutions:**

| Cause | Solution |
|-------|----------|
| No storage class | Create default storage class |
| Capacity exceeded | Add storage or clean up |
| Zone mismatch | Use topology-aware provisioner |

---

## 9. GPU Issues

### 9.1 GPU Not Available

**Symptoms:**
- Pods stuck pending for GPU
- No GPU nodes available

**Diagnosis:**

```bash
# Check GPU nodes
kubectl get nodes -l nvidia.com/gpu.present=true

# Check GPU resources
kubectl describe nodes | grep -A5 "nvidia.com/gpu"

# Check NVIDIA device plugin
kubectl get pods -n kube-system -l name=nvidia-device-plugin-ds
```

**Solutions:**

| Cause | Solution |
|-------|----------|
| No GPU nodes | Add GPU nodes to cluster |
| Device plugin not running | Install NVIDIA device plugin |
| All GPUs allocated | Scale down or add capacity |
| Driver issue | Check NVIDIA drivers |

---

## 10. Log Locations Reference

| Service | Log Location | Command |
|---------|--------------|---------|
| budapp | Kubernetes logs | `kubectl logs -n bud-system deployment/budapp` |
| budcluster | Kubernetes logs | `kubectl logs -n bud-system deployment/budcluster` |
| budgateway | Kubernetes logs | `kubectl logs -n bud-system deployment/budgateway` |
| PostgreSQL | Kubernetes logs | `kubectl logs -n bud-data postgresql-0` |
| Keycloak | Kubernetes logs | `kubectl logs -n bud-auth deployment/keycloak` |
| All services | Loki | Grafana → Explore → Loki |

---

## 11. Useful Commands Cheat Sheet

```bash
# Service health
kubectl get pods -n bud-system
kubectl top pods -n bud-system
kubectl get events -n bud-system --sort-by='.lastTimestamp'

# Logs
kubectl logs -n bud-system deployment/budapp --tail=100 -f
kubectl logs -n bud-system deployment/budapp --previous

# Restart service
kubectl rollout restart deployment/budapp -n bud-system

# Shell into pod
kubectl exec -it -n bud-system deployment/budapp -- /bin/bash

# Database
kubectl exec -n bud-data postgresql-0 -- psql -U bud -c "SELECT 1"

# Network
kubectl get endpoints -n bud-system
kubectl get networkpolicies -n bud-system
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-23 | Documentation | Initial version |

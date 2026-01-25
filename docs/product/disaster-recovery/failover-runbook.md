# Failover Runbook

> **Version:** 1.0
> **Last Updated:** 2026-01-25
> **Status:** Operational Runbook
> **Audience:** On-call engineers, SREs, incident commanders

---

## 1. Overview

This runbook provides step-by-step procedures for executing failover operations during disaster recovery scenarios. It covers both component-level automatic failover and full regional failover.

**Before You Begin:**
- Ensure you have appropriate access credentials
- Verify DR site connectivity
- Have communication channels ready (Slack: #incident-response, PagerDuty)

---

## 2. Failover Decision Matrix

| Scenario | Failover Type | Automation | This Runbook Section |
|----------|---------------|------------|----------------------|
| Single PostgreSQL node failure | Automatic | Full (Patroni) | Section 3.1 |
| Single Redis node failure | Automatic | Full (Sentinel) | Section 3.2 |
| Kubernetes node failure | Automatic | Full (K8s) | Section 3.3 |
| Primary region degraded | Manual | Scripted | Section 4 |
| Primary region unavailable | Manual | Scripted | Section 4 |
| Planned maintenance | Manual | Scripted | Section 5 |

---

## 3. Component-Level Failover (Automatic)

### 3.1 PostgreSQL Failover

**Managed by:** Patroni + HAProxy

**Automatic Behavior:**
1. Patroni detects leader failure (health check timeout: 30s)
2. Patroni initiates leader election among replicas
3. New leader is promoted automatically
4. HAProxy routes traffic to new leader
5. Expected failover time: < 30 seconds

**Verification Steps:**

```bash
# Check Patroni cluster state
kubectl exec -n bud patroni-0 -- patronictl list

# Expected output shows new leader
# +----------+------------+---------+---------+----+-----------+
# | Member   | Host       | Role    | State   | TL | Lag in MB |
# +----------+------------+---------+---------+----+-----------+
# | patroni-0| 10.x.x.x   | Replica | running |  5 |         0 |
# | patroni-1| 10.x.x.x   | Leader  | running |  5 |           |
# | patroni-2| 10.x.x.x   | Replica | running |  5 |         0 |
# +----------+------------+---------+---------+----+-----------+

# Check HAProxy backend status
kubectl exec -n bud haproxy-0 -- cat /var/lib/haproxy/stats
```

**Manual Intervention (if automatic failover fails):**

```bash
# Force switchover to specific replica
kubectl exec -n bud patroni-0 -- patronictl switchover --master patroni-0 --candidate patroni-1 --force

# Restart Patroni if stuck
kubectl rollout restart statefulset/patroni -n bud
```

**Alerts to Monitor:**
- `PostgreSQLLeaderChanged`
- `PostgreSQLReplicationLag`
- `PatroniClusterUnhealthy`

---

### 3.2 Redis Failover

**Managed by:** Redis Sentinel

**Automatic Behavior:**
1. Sentinel detects master failure (down-after-milliseconds: 5000)
2. Sentinel quorum agrees on failure
3. Replica with lowest replication offset is promoted
4. Clients are notified of new master
5. Expected failover time: < 30 seconds

**Verification Steps:**

```bash
# Check Sentinel view of cluster
kubectl exec -n bud redis-sentinel-0 -- redis-cli -p 26379 SENTINEL masters

# Check current master
kubectl exec -n bud redis-sentinel-0 -- redis-cli -p 26379 SENTINEL get-master-addr-by-name mymaster

# Verify replication status on new master
kubectl exec -n bud redis-master-0 -- redis-cli INFO replication
```

**Manual Intervention:**

```bash
# Force failover via Sentinel
kubectl exec -n bud redis-sentinel-0 -- redis-cli -p 26379 SENTINEL failover mymaster

# Reset Sentinel state if inconsistent
kubectl exec -n bud redis-sentinel-0 -- redis-cli -p 26379 SENTINEL reset mymaster
```

**Alerts to Monitor:**
- `RedisMasterDown`
- `RedisSentinelQuorumLost`
- `RedisReplicationBroken`

---

### 3.3 Kubernetes Node Failover

**Managed by:** Kubernetes scheduler + PodDisruptionBudgets

**Automatic Behavior:**
1. Node becomes NotReady (timeout: 40s)
2. Node controller marks pods for eviction (pod-eviction-timeout: 5m)
3. Scheduler places pods on healthy nodes
4. Services continue via remaining replicas

**Verification Steps:**

```bash
# Check node status
kubectl get nodes

# Check pod distribution
kubectl get pods -n bud -o wide

# Verify service endpoints
kubectl get endpoints -n bud
```

**Manual Intervention:**

```bash
# Drain node gracefully (for planned maintenance)
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data

# Force delete stuck pods
kubectl delete pod <pod-name> -n bud --grace-period=0 --force

# Cordon node to prevent scheduling
kubectl cordon <node-name>
```

---

## 4. Regional Failover (Full DR)

### 4.1 Pre-Failover Checklist

| Check | Command | Expected |
|-------|---------|----------|
| DR site reachable | `ping dr-bastion.example.com` | Response |
| DR Kubernetes healthy | `kubectl --context=dr get nodes` | All Ready |
| PostgreSQL replication | See Section 4.2 | Lag < 1 min |
| Redis replication | See Section 4.2 | Lag < 5 min |
| MinIO replication | Check MinIO console | Synced |
| Credentials available | Check vault/secrets | Accessible |

---

### 4.2 Verify Replication Status

```bash
# PostgreSQL replication lag
kubectl exec -n bud patroni-0 --context=primary -- \
  psql -U postgres -c "SELECT client_addr, state, sent_lsn, write_lsn, flush_lsn, replay_lsn, replay_lag FROM pg_stat_replication;"

# Redis replication lag (from DR site)
kubectl exec -n bud redis-master-0 --context=dr -- \
  redis-cli INFO replication | grep master_link_status

# MinIO replication status
mc admin replicate status minio-primary/bud-data
```

---

### 4.3 Execute Regional Failover

**Step 1: Declare Disaster (DR Commander)**

```bash
# Notify team
# Post in #incident-response: "DR DECLARED: [reason]. Initiating regional failover."

# Create incident ticket
# Update status page to "Investigating"
```

**Step 2: Stop Primary Region Traffic**

```bash
# Update DNS to maintenance page (if primary accessible)
# Or skip if primary is unreachable

# Scale down primary services (if accessible)
kubectl scale deployment --all --replicas=0 -n bud --context=primary
```

**Step 3: Promote DR Databases**

```bash
# Promote PostgreSQL standby to primary
kubectl exec -n bud patroni-0 --context=dr -- \
  patronictl failover --force

# Verify PostgreSQL promotion
kubectl exec -n bud patroni-0 --context=dr -- \
  patronictl list

# Promote Redis replica to master
kubectl exec -n bud redis-sentinel-0 --context=dr -- \
  redis-cli -p 26379 SENTINEL failover mymaster

# Verify Redis promotion
kubectl exec -n bud redis-master-0 --context=dr -- \
  redis-cli INFO replication
```

**Step 4: Update DNS**

```bash
# Update Route53/CloudFlare DNS records
# api.budai.example.com -> DR load balancer IP
# app.budai.example.com -> DR load balancer IP

# Using AWS CLI example:
aws route53 change-resource-record-sets \
  --hosted-zone-id $HOSTED_ZONE_ID \
  --change-batch file://dr-dns-changeset.json

# Verify DNS propagation
dig api.budai.example.com
watch -n 5 "dig +short api.budai.example.com"
```

**Step 5: Scale Up DR Services**

```bash
# Scale up application tier
kubectl scale deployment budapp --replicas=3 -n bud --context=dr
kubectl scale deployment budgateway --replicas=3 -n bud --context=dr
kubectl scale deployment budcluster --replicas=2 -n bud --context=dr

# Verify pods are running
kubectl get pods -n bud --context=dr

# Check service health
kubectl exec -n bud deploy/budapp --context=dr -- curl -s localhost:9081/health
```

**Step 6: Verify Services**

```bash
# Health check all services
for svc in budapp budgateway budcluster budsim budmodel; do
  echo "Checking $svc..."
  kubectl exec -n bud deploy/$svc --context=dr -- curl -s localhost:*/health
done

# Test authentication
curl -X POST https://api.budai.example.com/auth/token \
  -d "username=test&password=test"

# Test inference endpoint
curl -X POST https://api.budai.example.com/v1/chat/completions \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"model": "test", "messages": [{"role": "user", "content": "test"}]}'
```

**Step 7: Notify Stakeholders**

```bash
# Update status page: "Service restored - operating from DR site"
# Notify via Slack: "Failover complete. All services operational in DR region."
# Send customer notification email
```

---

### 4.4 Post-Failover Verification

| Check | Procedure | Success Criteria |
|-------|-----------|------------------|
| API health | `curl /health` all services | 200 OK |
| Authentication | Login via UI and API | Tokens issued |
| Database queries | Run test queries | Data consistent |
| Inference | Submit test inference | Response received |
| Metrics flowing | Check Grafana | Dashboards populated |
| Logs flowing | Check Loki | Recent logs visible |

---

## 5. Planned Failover (Maintenance)

For planned maintenance windows, use this modified procedure:

### 5.1 Pre-Maintenance

```bash
# Schedule maintenance window (minimum 48 hours notice)
# Notify customers via status page and email

# Verify DR readiness (same as Section 4.1)

# Take fresh backup before failover
kubectl exec -n bud patroni-0 -- pg_basebackup -D /backup -Ft -z -P
```

### 5.2 Execute Graceful Failover

```bash
# Enable maintenance mode
kubectl set env deployment/budapp MAINTENANCE_MODE=true -n bud

# Wait for in-flight requests to complete (5 minutes)
sleep 300

# Execute failover steps 3-6 from Section 4.3

# Verify DR operation

# Disable maintenance mode on DR
kubectl set env deployment/budapp MAINTENANCE_MODE=false -n bud --context=dr
```

### 5.3 Post-Maintenance

```bash
# Perform maintenance on primary region

# Execute failback (see failback-runbook.md)

# Verify primary operation

# Close maintenance window
```

---

## 6. Rollback Procedure

If failover fails or causes issues:

### 6.1 Partial Failover Rollback

```bash
# Revert DNS changes
aws route53 change-resource-record-sets \
  --hosted-zone-id $HOSTED_ZONE_ID \
  --change-batch file://primary-dns-changeset.json

# Demote DR databases (if promoted)
kubectl exec -n bud patroni-0 --context=dr -- \
  patronictl reinit <cluster-name> patroni-0

# Resume primary services
kubectl scale deployment --all --replicas=3 -n bud --context=primary
```

### 6.2 Failed Failover Recovery

If both regions are impaired:

1. Focus on restoring primary region first
2. Restore from backup if necessary
3. Do not attempt to sync DR back to corrupted primary
4. Engage vendor support if needed

---

## 7. Contact Information

| Role | Primary | Backup | Contact |
|------|---------|--------|---------|
| DR Commander | [Name] | [Name] | PagerDuty |
| Database Admin | [Name] | [Name] | PagerDuty |
| Network/DNS | [Name] | [Name] | PagerDuty |
| Cloud Provider | - | - | Support ticket |

---

## 8. Related Documents

| Document | Purpose |
|----------|---------|
| [DR Strategy](./dr-strategy.md) | Overall DR architecture |
| [Failback Runbook](./failback-runbook.md) | Return to primary |
| [Backup Strategy](./backup-strategy.md) | Backup procedures |
| [Incident Response](../operations/incident-response-playbook.md) | Incident handling |

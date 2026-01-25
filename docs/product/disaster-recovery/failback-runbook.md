# Failback Runbook

> **Version:** 1.0
> **Last Updated:** 2026-01-25
> **Status:** Operational Runbook
> **Audience:** On-call engineers, SREs, incident commanders

---

## 1. Overview

This runbook provides step-by-step procedures for returning operations from the DR site back to the primary site after a disaster recovery event. Failback should only be performed after the primary site is fully restored and verified.

**Prerequisites:**
- Primary site fully operational
- Root cause of original failure resolved
- Maintenance window scheduled (minimum 4 hours)
- Stakeholder approval obtained

---

## 2. Failback Decision Criteria

### 2.1 When to Failback

| Criteria | Requirement |
|----------|-------------|
| Primary site restored | All infrastructure operational |
| Root cause resolved | Issue fixed and verified |
| Data sync complete | DR → Primary replication caught up |
| Testing complete | Primary site verified via smoke tests |
| Business approval | Change approval obtained |
| Maintenance window | Low-traffic period scheduled |

### 2.2 When NOT to Failback

- Primary site stability not confirmed (wait 24-48 hours)
- Replication lag exceeds RPO
- Another incident is in progress
- Insufficient staff available
- High-traffic period (unless urgent)

---

## 3. Pre-Failback Checklist

### 3.1 Primary Site Verification

```bash
# Check Kubernetes cluster health
kubectl get nodes --context=primary
kubectl get pods -n bud --context=primary

# Verify all nodes are Ready
kubectl get nodes --context=primary | grep -v Ready
# Expected: No output (all nodes Ready)

# Check storage availability
kubectl get pv --context=primary
kubectl get pvc -n bud --context=primary
```

### 3.2 Database Preparation

```bash
# Verify PostgreSQL cluster is healthy on primary
kubectl exec -n bud patroni-0 --context=primary -- patronictl list

# Check replication from DR to Primary is possible
# Primary should be configured as replica of DR temporarily

# Verify Redis cluster on primary
kubectl exec -n bud redis-master-0 --context=primary -- redis-cli PING
```

### 3.3 Data Synchronization

```bash
# Check PostgreSQL replication lag (DR → Primary)
kubectl exec -n bud patroni-0 --context=dr -- \
  psql -U postgres -c "SELECT client_addr, state, replay_lag FROM pg_stat_replication;"

# Verify MinIO sync status
mc admin replicate status minio-dr/bud-data

# Ensure all data created during DR period is synced
# Compare record counts between DR and Primary databases
```

### 3.4 Pre-Failback Checklist Table

| Item | Verified | Notes |
|------|----------|-------|
| Primary Kubernetes healthy | [ ] | |
| Primary PostgreSQL ready | [ ] | |
| Primary Redis ready | [ ] | |
| Data replication complete | [ ] | Lag < 1 min |
| Network connectivity verified | [ ] | |
| DNS TTL lowered (60s) | [ ] | |
| Maintenance window confirmed | [ ] | |
| Rollback plan reviewed | [ ] | |
| Team assembled | [ ] | |

---

## 4. Execute Failback

### 4.1 Phase 1: Preparation (T-30 minutes)

```bash
# Notify team
# Post in #incident-response: "FAILBACK STARTING in 30 minutes"

# Update status page: "Scheduled Maintenance - Failback to Primary"

# Lower DNS TTL if not already done
# TTL should be 60 seconds

# Take backup of DR databases
kubectl exec -n bud patroni-0 --context=dr -- \
  pg_dump -U postgres budapp > /backup/pre-failback-$(date +%Y%m%d).sql
```

### 4.2 Phase 2: Stop DR Traffic (T-0)

```bash
# Enable maintenance mode on DR
kubectl set env deployment/budapp MAINTENANCE_MODE=true -n bud --context=dr
kubectl set env deployment/budgateway MAINTENANCE_MODE=true -n bud --context=dr

# Wait for in-flight requests to complete
sleep 120

# Verify no active connections
kubectl exec -n bud patroni-0 --context=dr -- \
  psql -U postgres -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"
```

### 4.3 Phase 3: Final Data Sync

```bash
# Stop application writes on DR
kubectl scale deployment budapp --replicas=0 -n bud --context=dr
kubectl scale deployment budcluster --replicas=0 -n bud --context=dr

# Wait for final replication
sleep 60

# Verify replication is caught up (lag should be 0)
kubectl exec -n bud patroni-0 --context=dr -- \
  psql -U postgres -c "SELECT replay_lag FROM pg_stat_replication;"

# Take final consistent backup
kubectl exec -n bud patroni-0 --context=dr -- \
  pg_dumpall -U postgres > /backup/final-failback-$(date +%Y%m%d).sql
```

### 4.4 Phase 4: Promote Primary Databases

```bash
# Stop replication on primary and promote
kubectl exec -n bud patroni-0 --context=primary -- \
  patronictl failover --force

# Verify PostgreSQL primary promotion
kubectl exec -n bud patroni-0 --context=primary -- patronictl list
# Should show patroni-0 as Leader

# Promote Redis on primary
kubectl exec -n bud redis-sentinel-0 --context=primary -- \
  redis-cli -p 26379 SENTINEL failover mymaster

# Verify Redis promotion
kubectl exec -n bud redis-master-0 --context=primary -- \
  redis-cli INFO replication | grep role
# Should show role:master
```

### 4.5 Phase 5: Update DNS

```bash
# Update DNS records to primary site
aws route53 change-resource-record-sets \
  --hosted-zone-id $HOSTED_ZONE_ID \
  --change-batch file://primary-dns-changeset.json

# Verify DNS propagation
watch -n 5 "dig +short api.budai.example.com"

# Wait for DNS propagation (based on TTL)
sleep 120
```

### 4.6 Phase 6: Start Primary Services

```bash
# Scale up primary application tier
kubectl scale deployment budapp --replicas=3 -n bud --context=primary
kubectl scale deployment budgateway --replicas=3 -n bud --context=primary
kubectl scale deployment budcluster --replicas=2 -n bud --context=primary
kubectl scale deployment budsim --replicas=2 -n bud --context=primary
kubectl scale deployment budmodel --replicas=2 -n bud --context=primary
kubectl scale deployment budmetrics --replicas=2 -n bud --context=primary

# Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app=budapp -n bud --context=primary --timeout=300s

# Disable maintenance mode
kubectl set env deployment/budapp MAINTENANCE_MODE=false -n bud --context=primary
kubectl set env deployment/budgateway MAINTENANCE_MODE=false -n bud --context=primary
```

### 4.7 Phase 7: Verify Primary Operation

```bash
# Health check all services
for svc in budapp budgateway budcluster budsim budmodel budmetrics; do
  echo "Checking $svc..."
  kubectl exec -n bud deploy/$svc --context=primary -- curl -s localhost:*/health
done

# Test authentication
curl -X POST https://api.budai.example.com/auth/token \
  -d "username=test&password=test"

# Test API endpoints
curl https://api.budai.example.com/api/v1/projects \
  -H "Authorization: Bearer $TOKEN"

# Test inference
curl -X POST https://api.budai.example.com/v1/chat/completions \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"model": "test", "messages": [{"role": "user", "content": "test"}]}'
```

---

## 5. Post-Failback Tasks

### 5.1 DR Site Cleanup

```bash
# Scale down DR application services
kubectl scale deployment --all --replicas=0 -n bud --context=dr

# Reconfigure DR databases as replicas of primary
kubectl exec -n bud patroni-0 --context=dr -- \
  patronictl reinit <cluster-name> patroni-0

# Verify replication is re-established (Primary → DR)
kubectl exec -n bud patroni-0 --context=primary -- \
  psql -U postgres -c "SELECT client_addr, state FROM pg_stat_replication;"
```

### 5.2 Monitoring Verification

| Check | Command | Expected |
|-------|---------|----------|
| Metrics flowing | Check Grafana | Dashboards populated |
| Logs flowing | Check Loki | Recent logs visible |
| Alerts configured | Check Alertmanager | No firing alerts |
| Traces flowing | Check Tempo | Recent traces |

### 5.3 Communication

```bash
# Update status page: "Failback complete - operating from primary site"

# Notify team in #incident-response:
# "FAILBACK COMPLETE. All services operational on primary site."

# Send customer notification if applicable

# Schedule post-failback review meeting
```

### 5.4 Documentation

Complete the failback report:

| Item | Value |
|------|-------|
| Failback start time | |
| Failback end time | |
| Total duration | |
| Data loss (if any) | |
| Issues encountered | |
| Services affected | |

---

## 6. Rollback Procedure

If failback encounters issues, return to DR site:

### 6.1 Immediate Rollback

```bash
# Revert DNS to DR site
aws route53 change-resource-record-sets \
  --hosted-zone-id $HOSTED_ZONE_ID \
  --change-batch file://dr-dns-changeset.json

# Scale down primary (if causing issues)
kubectl scale deployment --all --replicas=0 -n bud --context=primary

# Scale up DR
kubectl scale deployment budapp --replicas=3 -n bud --context=dr
kubectl scale deployment budgateway --replicas=3 -n bud --context=dr

# Disable maintenance mode on DR
kubectl set env deployment/budapp MAINTENANCE_MODE=false -n bud --context=dr
```

### 6.2 Post-Rollback

- Investigate primary site issues
- Do not attempt failback again until root cause resolved
- Schedule new maintenance window

---

## 7. Troubleshooting

### 7.1 Common Issues

| Issue | Cause | Resolution |
|-------|-------|------------|
| Replication lag not decreasing | Network issues | Check connectivity, bandwidth |
| Pods not starting on primary | Resource constraints | Check node capacity, scale nodes |
| DNS not propagating | TTL too high | Wait or flush DNS caches |
| Authentication failing | Keycloak not synced | Verify Keycloak DB, restart pods |
| Inference timeouts | Model not loaded | Check GPU availability, model cache |

### 7.2 Emergency Contacts

| Role | Contact |
|------|---------|
| DR Commander | PagerDuty |
| Database Admin | PagerDuty |
| Network/DNS | PagerDuty |
| Cloud Provider | Support ticket |

---

## 8. Related Documents

| Document | Purpose |
|----------|---------|
| [DR Strategy](./dr-strategy.md) | Overall DR architecture |
| [Failover Runbook](./failover-runbook.md) | Failover to DR |
| [Backup Strategy](./backup-strategy.md) | Backup procedures |
| [DR Drill Procedure](./dr-drill-procedure.md) | Testing methodology |

# Incident Response Playbook

> **Version:** 1.0
> **Last Updated:** 2026-01-23
> **Status:** Operational Guide
> **Audience:** On-call engineers, SREs, incident commanders

---

## 1. Incident Classification

### 1.1 Severity Levels

| Severity | Definition | Response Time | Examples |
|----------|------------|---------------|----------|
| **SEV1** | Complete outage or data loss | 15 min | Platform down, data breach |
| **SEV2** | Major feature degraded | 30 min | Inference failures, auth broken |
| **SEV3** | Minor feature degraded | 4 hours | Slow performance, partial failures |
| **SEV4** | Cosmetic or low impact | 24 hours | UI glitches, non-critical errors |

### 1.2 Classification Criteria

**SEV1 - Critical:**
- Platform completely unavailable
- All inference requests failing
- Data breach or security incident
- Data corruption or loss
- All users affected

**SEV2 - Major:**
- Major feature unavailable (auth, deployments)
- > 50% of inference requests failing
- Significant performance degradation
- Subset of users affected

**SEV3 - Minor:**
- Single endpoint or feature impacted
- < 10% of requests affected
- Performance slightly degraded
- Workaround available

**SEV4 - Low:**
- Cosmetic issues
- Documentation or informational
- Single user affected
- No functional impact

---

## 2. Incident Response Process

### 2.1 Response Flow

```
DETECTION
    │
    ├── Monitoring Alert
    ├── User Report
    └── Internal Discovery
    │
    ▼
TRIAGE (15 min)
    │
    ├── Classify severity
    ├── Assign incident commander
    └── Create incident channel
    │
    ▼
INVESTIGATION (ongoing)
    │
    ├── Gather information
    ├── Identify root cause
    └── Document findings
    │
    ▼
MITIGATION (varies by severity)
    │
    ├── Apply temporary fix
    ├── Roll back if needed
    └── Communicate status
    │
    ▼
RESOLUTION
    │
    ├── Verify fix
    ├── Monitor stability
    └── Close incident
    │
    ▼
POST-MORTEM (within 48 hours)
    │
    ├── Root cause analysis
    ├── Action items
    └── Share learnings
```

### 2.2 Roles

| Role | Responsibility |
|------|----------------|
| **Incident Commander** | Coordinates response, makes decisions |
| **Communications Lead** | External/internal communication |
| **Technical Lead** | Leads investigation and fix |
| **Scribe** | Documents timeline and actions |

---

## 3. SEV1 Response Procedure

### 3.1 Immediate Actions (0-15 minutes)

1. **Acknowledge alert** in PagerDuty/Slack
2. **Create incident channel** `#incident-YYYY-MM-DD-brief-desc`
3. **Page incident commander** if not on-call
4. **Initial assessment:**
   ```bash
   # Quick health check
   kubectl get pods -n bud-system
   kubectl get events -n bud-system --sort-by='.lastTimestamp' | head -20
   ```
5. **Post initial message:**
   ```
   :rotating_light: SEV1 INCIDENT DECLARED
   Summary: [Brief description]
   Impact: [Who/what is affected]
   Commander: @name
   Tech Lead: @name
   ```

### 3.2 Investigation (15-30 minutes)

1. **Check dashboards:**
   - Grafana → Platform Overview
   - Grafana → Error Tracking

2. **Check logs:**
   ```bash
   # Recent errors
   kubectl logs -n bud-system deployment/budapp --tail=200 | grep -i error

   # Loki query
   {app=~"bud.*"} |= "error" | json
   ```

3. **Check recent changes:**
   ```bash
   # Recent deployments
   kubectl rollout history deployment/budapp -n bud-system

   # Git commits
   git log --oneline -10
   ```

4. **Check dependencies:**
   - PostgreSQL status
   - Keycloak status
   - External APIs

### 3.3 Mitigation Options

| Situation | Action |
|-----------|--------|
| Bad deployment | `kubectl rollout undo deployment/budapp -n bud-system` |
| Overload | Scale up replicas |
| Database issue | Failover to replica |
| External API down | Enable fallback/circuit breaker |
| Unknown | Restart affected services |

### 3.4 Communication Template

```
=== SEV1 INCIDENT UPDATE ===
Time: [HH:MM UTC]
Status: [Investigating/Mitigating/Resolved]

Current Impact:
- [What is affected]
- [Number of users/requests]

What We Know:
- [Finding 1]
- [Finding 2]

Current Actions:
- [Action 1]
- [Action 2]

Next Update: [Time]
```

---

## 4. SEV2 Response Procedure

### 4.1 Immediate Actions (0-30 minutes)

1. **Acknowledge alert**
2. **Create incident thread** in #incidents
3. **Initial assessment**
4. **Notify stakeholders** if needed

### 4.2 Investigation

1. **Scope the impact:**
   - Which feature(s)?
   - Which users?
   - Since when?

2. **Check relevant systems:**
   ```bash
   # Service-specific logs
   kubectl logs -n bud-system deployment/<service> --tail=100

   # Metrics for service
   # Grafana → Service dashboard
   ```

3. **Identify changes:**
   - Recent deployments
   - Configuration changes
   - Infrastructure changes

### 4.3 Resolution

1. Apply fix or workaround
2. Verify fix in monitoring
3. Update stakeholders
4. Close incident thread

---

## 5. Common Incident Scenarios

### 5.1 Platform Outage

**Indicators:**
- All endpoints returning errors
- Grafana shows high error rate
- Multiple alerts firing

**Response:**
```bash
# Check all pods
kubectl get pods -n bud-system -o wide

# Check Dapr
dapr status -k

# Check database
kubectl exec -n bud-data postgresql-0 -- pg_isready

# Check Keycloak
kubectl get pods -n bud-auth
```

**Common Causes:**
- Database failure
- Kubernetes control plane issue
- Network partition
- Bad configuration push

### 5.2 Inference Failures

**Indicators:**
- Inference requests timing out
- High error rate on endpoints
- GPU utilization issues

**Response:**
```bash
# Check endpoint status
curl "https://api.bud.example.com/endpoints" \
  -H "Authorization: Bearer $TOKEN" | jq '.[] | {name, status}'

# Check vLLM pods
kubectl --kubeconfig=/path/to/cluster get pods -n bud-workloads

# Check GPU
kubectl --kubeconfig=/path/to/cluster exec -it <vllm-pod> -- nvidia-smi
```

**Common Causes:**
- GPU OOM
- Model serving crash
- Cluster connectivity
- Rate limiting

### 5.3 Authentication Failure

**Indicators:**
- Users cannot login
- 401 errors on all requests
- Token validation failures

**Response:**
```bash
# Check Keycloak
kubectl get pods -n bud-auth
kubectl logs -n bud-auth deployment/keycloak --tail=100

# Check Keycloak connectivity
curl https://keycloak.example.com/realms/bud/.well-known/openid-configuration
```

**Common Causes:**
- Keycloak down
- Database connectivity
- Certificate expiry
- Clock skew

### 5.4 Database Failure

**Indicators:**
- Services returning 500 errors
- "connection refused" in logs
- Database unavailable

**Response:**
```bash
# Check PostgreSQL
kubectl get pods -n bud-data -l app=postgresql

# Check pod status
kubectl describe pod -n bud-data postgresql-0

# Check from app pod
kubectl exec -n bud-system deployment/budapp -- \
  python -c "from budapp.db import engine; print('OK')"
```

**Common Causes:**
- Storage failure
- OOM
- Replication issues
- Network partition

### 5.5 Security Incident

**Indicators:**
- Suspicious activity in audit logs
- Unauthorized access detected
- Data exfiltration attempt

**Response:**
1. **Contain:** Disable affected accounts/tokens
2. **Investigate:** Review audit logs
3. **Preserve:** Capture evidence
4. **Notify:** Legal, security, management

**Commands:**
```bash
# Disable user
curl -X PUT "https://api.bud.example.com/users/{id}" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"status": "INACTIVE"}'

# Revoke tokens
# Blacklist JWT in Dapr state store

# Export audit logs
curl "https://api.bud.example.com/audit/export" \
  -H "Authorization: Bearer $TOKEN" \
  -G --data-urlencode "user_id={suspicious_user}" \
  -o audit_evidence.json
```

---

## 6. Escalation Matrix

| Level | When | Who | Contact |
|-------|------|-----|---------|
| L1 | On-call | On-call engineer | PagerDuty |
| L2 | SEV2 15min, SEV1 immediate | Team lead | Slack/Phone |
| L3 | SEV1 30min | Engineering manager | Phone |
| L4 | SEV1 1hr, data breach | VP Engineering | Phone |
| Executive | Major incident | C-level | Phone |

---

## 7. Communication Channels

| Channel | Purpose | Audience |
|---------|---------|----------|
| `#incidents` | General incident tracking | Engineering |
| `#incident-YYYY-MM-DD` | Specific incident | Incident team |
| `#status-updates` | Customer-facing status | All + external |
| PagerDuty | Alerting | On-call |
| Status page | External communication | Customers |

---

## 8. Post-Incident Process

### 8.1 Post-Mortem Template

```markdown
# Post-Mortem: [Incident Title]

**Date:** YYYY-MM-DD
**Duration:** HH:MM
**Severity:** SEV#
**Author:** [Name]

## Summary
[1-2 sentence summary]

## Impact
- Users affected: [number]
- Requests failed: [number]
- Revenue impact: [if applicable]

## Timeline
| Time (UTC) | Event |
|------------|-------|
| HH:MM | [Event 1] |
| HH:MM | [Event 2] |

## Root Cause
[Detailed explanation]

## Resolution
[How it was fixed]

## What Went Well
- [Item 1]
- [Item 2]

## What Went Wrong
- [Item 1]
- [Item 2]

## Action Items
| Action | Owner | Due Date |
|--------|-------|----------|
| [Action 1] | [Name] | [Date] |

## Lessons Learned
[Key takeaways]
```

### 8.2 Post-Mortem Schedule

| Severity | Post-Mortem Required | Timeline |
|----------|---------------------|----------|
| SEV1 | Yes | Within 48 hours |
| SEV2 | Yes | Within 1 week |
| SEV3 | Optional | Within 2 weeks |
| SEV4 | No | - |

---

## 9. Checklist Templates

### 9.1 SEV1 Checklist

- [ ] Incident channel created
- [ ] Incident commander assigned
- [ ] Initial status posted
- [ ] Stakeholders notified
- [ ] Investigation started
- [ ] Root cause identified
- [ ] Mitigation applied
- [ ] Fix verified
- [ ] All-clear communicated
- [ ] Post-mortem scheduled

### 9.2 Handoff Checklist

- [ ] Current status documented
- [ ] Open actions listed
- [ ] Next steps clear
- [ ] New on-call acknowledged
- [ ] Incident channel updated

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-23 | Documentation | Initial version |

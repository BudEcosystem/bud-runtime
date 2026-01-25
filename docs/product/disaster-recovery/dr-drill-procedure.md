# DR Drill Procedure

> **Version:** 1.0
> **Last Updated:** 2026-01-25
> **Status:** Operational Procedure
> **Audience:** SREs, platform engineers, DR team

---

## 1. Overview

This document defines the procedures for conducting disaster recovery drills to validate the DR strategy, runbooks, and team readiness. Regular DR drills ensure the organization can recover from disasters within defined RTO/RPO objectives.

**Drill Objectives:**
- Validate failover and failback procedures
- Measure actual RTO/RPO against targets
- Identify gaps in runbooks and automation
- Train team members on DR procedures
- Meet compliance requirements

---

## 2. Drill Types

### 2.1 Drill Schedule

| Drill Type | Frequency | Duration | Scope |
|------------|-----------|----------|-------|
| Backup Verification | Weekly | 2 hours | Automated restore test |
| Component Failover | Monthly | 1 hour | Single component |
| Tabletop Exercise | Quarterly | 4 hours | Full team walkthrough |
| Full DR Drill | Annually | 8 hours | Regional failover |

### 2.2 Drill Descriptions

**Backup Verification (Weekly)**
- Automated restore of backups to test environment
- Verify data integrity and completeness
- No production impact

**Component Failover (Monthly)**
- Test failover of individual components (PostgreSQL, Redis)
- Verify automatic recovery mechanisms
- Minimal production impact (brief failover)

**Tabletop Exercise (Quarterly)**
- Team walks through DR scenarios verbally
- Review and update runbooks
- No production impact

**Full DR Drill (Annually)**
- Complete failover to DR site
- Run production traffic from DR
- Failback to primary
- Scheduled maintenance window required

---

## 3. Pre-Drill Planning

### 3.1 Planning Timeline

| Timeframe | Activity |
|-----------|----------|
| T-4 weeks | Schedule drill, notify stakeholders |
| T-2 weeks | Review runbooks, assign roles |
| T-1 week | Pre-drill checklist, confirm participants |
| T-1 day | Final preparations, verify DR site |
| T-0 | Execute drill |
| T+1 day | Preliminary findings review |
| T+1 week | Complete drill report |

### 3.2 Stakeholder Notification

```
Subject: DR Drill Scheduled - [Date]

Team,

A [Drill Type] disaster recovery drill is scheduled for:

Date: [Date]
Time: [Start Time] - [End Time] [Timezone]
Scope: [Description]
Expected Impact: [None/Minimal/Maintenance Window]

Participants:
- DR Commander: [Name]
- Technical Lead: [Name]
- Database Admin: [Name]
- Observers: [Names]

Please confirm your availability by [Date].

Runbooks to review:
- Failover Runbook
- Failback Runbook
- DR Strategy

Questions? Contact [DR Commander].
```

### 3.3 Pre-Drill Checklist

| Item | Owner | Status |
|------|-------|--------|
| Drill date approved | DR Commander | [ ] |
| Participants confirmed | DR Commander | [ ] |
| Runbooks reviewed and updated | Technical Lead | [ ] |
| DR site verified operational | SRE | [ ] |
| Backup verification complete | DBA | [ ] |
| Monitoring dashboards ready | SRE | [ ] |
| Communication channels tested | All | [ ] |
| Rollback plan documented | Technical Lead | [ ] |
| Customer notification sent (if needed) | Communications | [ ] |

---

## 4. Drill Procedures

### 4.1 Backup Verification Drill (Weekly)

**Duration:** 2 hours (automated)

**Procedure:**

```bash
# 1. Restore PostgreSQL backup to test environment
kubectl apply -f restore-job.yaml --context=test

# 2. Wait for restore to complete
kubectl wait --for=condition=complete job/pg-restore -n test --timeout=1h

# 3. Verify data integrity
kubectl exec -n test pg-test-0 -- psql -U postgres -c "
  SELECT 'projects' as table_name, count(*) FROM projects
  UNION ALL
  SELECT 'users', count(*) FROM users
  UNION ALL
  SELECT 'endpoints', count(*) FROM endpoints;
"

# 4. Compare counts with production
# Automated script compares and alerts on discrepancies

# 5. Cleanup test environment
kubectl delete -f restore-job.yaml --context=test
```

**Success Criteria:**
- Restore completes without errors
- Record counts match production (within RPO window)
- Data integrity checks pass

---

### 4.2 Component Failover Drill (Monthly)

**Duration:** 1 hour

**Procedure:**

**Step 1: Pre-Drill Verification (10 min)**
```bash
# Verify cluster health
kubectl exec -n bud patroni-0 -- patronictl list

# Note current leader
CURRENT_LEADER=$(kubectl exec -n bud patroni-0 -- patronictl list -f json | jq -r '.[] | select(.Role=="Leader") | .Member')
echo "Current leader: $CURRENT_LEADER"

# Verify replication is healthy
kubectl exec -n bud patroni-0 -- psql -U postgres -c "SELECT * FROM pg_stat_replication;"
```

**Step 2: Trigger Failover (5 min)**
```bash
# Initiate planned switchover
kubectl exec -n bud patroni-0 -- patronictl switchover --force

# Monitor failover
watch kubectl exec -n bud patroni-0 -- patronictl list
```

**Step 3: Verify Failover (10 min)**
```bash
# Confirm new leader
NEW_LEADER=$(kubectl exec -n bud patroni-0 -- patronictl list -f json | jq -r '.[] | select(.Role=="Leader") | .Member')
echo "New leader: $NEW_LEADER"

# Verify application connectivity
kubectl exec -n bud deploy/budapp -- curl -s localhost:9081/health

# Check for errors in logs
kubectl logs -n bud deploy/budapp --since=5m | grep -i error
```

**Step 4: Measure Recovery Time (5 min)**
```bash
# Calculate actual failover time from monitoring
# Check Grafana for connection drops and recovery
```

**Step 5: Restore Original State (15 min)**
```bash
# Switchover back to original leader
kubectl exec -n bud patroni-0 -- patronictl switchover --candidate $CURRENT_LEADER --force

# Verify original state restored
kubectl exec -n bud patroni-0 -- patronictl list
```

**Step 6: Document Results (15 min)**
- Record failover time
- Note any errors or issues
- Update runbook if needed

---

### 4.3 Tabletop Exercise (Quarterly)

**Duration:** 4 hours

**Agenda:**

| Time | Activity |
|------|----------|
| 0:00 - 0:15 | Introduction and objectives |
| 0:15 - 0:45 | Scenario presentation |
| 0:45 - 2:00 | Walkthrough of DR procedures |
| 2:00 - 2:15 | Break |
| 2:15 - 3:00 | Discussion of edge cases |
| 3:00 - 3:30 | Runbook updates |
| 3:30 - 4:00 | Action items and wrap-up |

**Sample Scenarios:**

**Scenario 1: Primary Region Outage**
```
At 2:00 AM, monitoring alerts indicate the primary AWS region
(us-east-1) is experiencing a major outage. All services in the
primary region are unreachable. Customer impact is reported.

Questions:
1. Who makes the decision to failover?
2. What is the first action taken?
3. How do we communicate to customers?
4. What is our expected RTO?
5. When do we attempt failback?
```

**Scenario 2: Database Corruption**
```
During a routine deployment, a database migration corrupts the
projects table. The corruption is discovered 2 hours after the
deployment. Backups are available.

Questions:
1. Do we failover or restore from backup?
2. How do we determine the extent of corruption?
3. What is the data loss (RPO impact)?
4. How do we handle transactions during the 2-hour window?
```

**Scenario 3: Security Incident**
```
Security team detects unauthorized access to the production
Kubernetes cluster. The attacker may have accessed secrets
and modified deployments.

Questions:
1. Do we failover to DR?
2. How do we verify DR site is not compromised?
3. What credentials need rotation?
4. How do we forensically preserve evidence?
```

---

### 4.4 Full DR Drill (Annual)

**Duration:** 8 hours

**Prerequisites:**
- Maintenance window approved
- Customer notification sent
- All participants confirmed
- DR site verified ready

**Drill Schedule:**

| Time | Phase | Activity |
|------|-------|----------|
| T+0:00 | Preparation | Team assembly, final checks |
| T+0:30 | Declaration | Declare simulated disaster |
| T+1:00 | Failover | Execute failover runbook |
| T+3:00 | Verification | Verify DR site operation |
| T+4:00 | Operation | Run production from DR |
| T+5:00 | Failback Prep | Prepare for failback |
| T+5:30 | Failback | Execute failback runbook |
| T+7:00 | Verification | Verify primary operation |
| T+7:30 | Wrap-up | Document results, debrief |

**Execution:**

**Phase 1: Failover (T+0:30 - T+3:00)**
```bash
# Follow Failover Runbook (failover-runbook.md)
# Document each step completion time
# Note any deviations from runbook
```

**Phase 2: DR Operation (T+3:00 - T+5:00)**
```bash
# Verify all services operational
# Run synthetic transactions
# Monitor error rates and latency
# Verify logging and monitoring

# Test critical user journeys:
# 1. User login
# 2. Project creation
# 3. Model deployment
# 4. Inference request
```

**Phase 3: Failback (T+5:00 - T+7:00)**
```bash
# Follow Failback Runbook (failback-runbook.md)
# Document each step completion time
# Note any deviations from runbook
```

**Phase 4: Verification (T+7:00 - T+7:30)**
```bash
# Verify primary site fully operational
# Verify DR site reconfigured as standby
# Verify replication re-established
# Run final health checks
```

---

## 5. Drill Metrics

### 5.1 Key Metrics to Capture

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Failover RTO | < 4 hours | Time from declaration to DR operational |
| Failback RTO | < 4 hours | Time from start to primary operational |
| RPO achieved | < 1 hour | Data loss measured by timestamp comparison |
| Error rate during failover | < 1% | Monitoring dashboard |
| Runbook accuracy | 100% | Steps executed vs documented |
| Team response time | < 15 min | Time to assemble after page |

### 5.2 Drill Scorecard

| Category | Weight | Score (1-5) | Notes |
|----------|--------|-------------|-------|
| RTO achieved | 25% | | |
| RPO achieved | 25% | | |
| Runbook followed | 20% | | |
| Communication | 15% | | |
| Team coordination | 15% | | |
| **Total** | 100% | | |

---

## 6. Post-Drill Activities

### 6.1 Immediate Debrief (Same Day)

**Agenda (30 min):**
1. What went well?
2. What didn't go as planned?
3. Any runbook gaps identified?
4. Immediate action items

### 6.2 Drill Report (Within 1 Week)

**Report Template:**

```markdown
# DR Drill Report

**Drill Type:** [Type]
**Date:** [Date]
**Duration:** [Actual Duration]
**Participants:** [Names]

## Executive Summary
[2-3 sentence summary of drill outcome]

## Metrics

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Failover RTO | 4 hours | X hours | Pass/Fail |
| RPO | 1 hour | X minutes | Pass/Fail |

## Timeline

| Time | Event | Notes |
|------|-------|-------|
| HH:MM | Event description | |

## Issues Encountered

| Issue | Impact | Resolution | Action Item |
|-------|--------|------------|-------------|
| | | | |

## Runbook Updates Required

| Runbook | Section | Change Required |
|---------|---------|-----------------|
| | | |

## Action Items

| Action | Owner | Due Date | Status |
|--------|-------|----------|--------|
| | | | |

## Recommendations

1. [Recommendation 1]
2. [Recommendation 2]

## Appendix

- Monitoring screenshots
- Log excerpts
- Communication logs
```

### 6.3 Action Item Tracking

All action items from DR drills should be:
- Entered into issue tracking system
- Assigned owners and due dates
- Reviewed in next drill planning
- Closed before next drill

---

## 7. Compliance Requirements

### 7.1 Documentation Retention

| Document | Retention Period |
|----------|------------------|
| Drill reports | 3 years |
| Runbook versions | 3 years |
| Communication logs | 1 year |
| Metrics data | 1 year |

### 7.2 Audit Evidence

For compliance audits, maintain:
- Drill schedule and completion records
- Drill reports with metrics
- Action item closure evidence
- Runbook update history
- Participant attendance records

---

## 8. Related Documents

| Document | Purpose |
|----------|---------|
| [DR Strategy](./dr-strategy.md) | Overall DR architecture |
| [Failover Runbook](./failover-runbook.md) | Failover procedures |
| [Failback Runbook](./failback-runbook.md) | Failback procedures |
| [Backup Strategy](./backup-strategy.md) | Backup procedures |

---

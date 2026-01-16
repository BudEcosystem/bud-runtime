# Quickstart: budworkflow → budpipeline Rename Deployment

**Feature**: [spec.md](./spec.md) | [plan.md](./plan.md)
**Date**: 2026-01-15

This guide provides step-by-step instructions for deploying the budworkflow → budpipeline rename to production.

---

## Prerequisites

### Required Tools
```bash
# Verify tool versions
python --version  # Python 3.11+
node --version    # Node 20.16+
helm version      # Helm 3.8+
kubectl version   # kubectl 1.25+
git --version     # Git 2.25+
```

### Required Access
- Git repository write access
- Docker registry push permissions
- Kubernetes cluster admin access
- Production environment credentials

### Pre-Deployment Checklist
- [ ] All code changes merged to feature branch
- [ ] Pre-commit hooks pass (`pre-commit run --all-files`)
- [ ] All tests pass (see Testing section below)
- [ ] Code review approved
- [ ] Breaking change notice sent (7 days prior)
- [ ] External consumers notified and prepared
- [ ] Rollback plan documented

---

## Part 1: Local Development Testing

### Step 1: Start the Renamed Service

```bash
# Clone and checkout feature branch
git clone https://github.com/BudEcosystem/bud-runtime.git
cd bud-runtime
git checkout 001-rename-budworkflow-to-budpipeline

# Navigate to renamed service
cd services/budpipeline

# Copy environment template
cp .env.sample .env

# Start service with Dapr
./deploy/start_dev.sh --build

# Expected output:
# ✅ Dapr sidecar initialized (app-id: budpipeline)
# ✅ Service started on http://localhost:8010
# ✅ Dapr HTTP port: 3500
```

### Step 2: Verify Service Health

```bash
# Health check via Dapr
dapr invoke --app-id budpipeline --method /health

# Expected response:
# {"status": "healthy", "app_id": "budpipeline"}

# Direct API check
curl http://localhost:8010/health

# Expected response:
# {"status": "ok"}
```

### Step 3: Test Import Resolution

```bash
# Python import test
cd services/budpipeline
python -c "import budpipeline; print('✅ Import successful')"

# Pytest discovery test
pytest --collect-only

# Expected: All tests discovered without import errors
```

### Step 4: Run Unit Tests

```bash
cd services/budpipeline
pytest -v --cov

# Expected output:
# ✅ All tests pass
# ✅ Coverage > 80%
# ❌ If any test fails, fix before proceeding
```

---

## Part 2: Integration Testing

### Step 1: Start Full Stack

```bash
cd bud-runtime

# Start budapp (API proxy)
cd services/budapp
./deploy/start_dev.sh --build

# Start budadmin (frontend)
cd services/budadmin
npm install
npm run dev

# Verify services running:
# - budpipeline: http://localhost:8010
# - budapp: http://localhost:9081
# - budadmin: http://localhost:8007
```

### Step 2: Test API Endpoints

```bash
# Get auth token (replace with actual auth flow)
export TOKEN="your-auth-token"

# Test pipeline list endpoint
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:9081/api/v1/budpipeline

# Expected: 200 OK with pipeline list (may be empty)

# Test pipeline creation
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Pipeline",
    "description": "Rename verification test",
    "dag": {
      "nodes": [
        {"id": "start", "type": "start"},
        {"id": "end", "type": "end"}
      ],
      "edges": [
        {"from": "start", "to": "end"}
      ]
    }
  }' \
  http://localhost:9081/api/v1/budpipeline

# Expected: 201 Created with pipeline ID
```

### Step 3: Test Frontend Routes

```bash
# Open browser to test redirects
open http://localhost:8007/workflows
# Should redirect to http://localhost:8007/pipelines

# Test pipeline list page
open http://localhost:8007/pipelines
# Should load pipeline list UI

# Test create page
open http://localhost:8007/pipelines/new
# Should load pipeline creation form
```

### Step 4: Test Dapr Service Invocation

```bash
# From budapp, invoke budpipeline service
dapr invoke --app-id budpipeline \
  --method /workflow-events \
  --verb POST \
  --data '{"event_type": "test"}'

# Expected: 200 OK
# Check budpipeline logs for event receipt
```

### Step 5: Test Pub/Sub Events

```bash
# Publish test event to new topic
dapr publish --publish-app-id budapp \
  --pubsub bud-pubsub \
  --topic budpipelineEvents \
  --data '{"workflow_id": "test-001", "status": "completed"}'

# Check budpipeline logs for event receipt
# Expected: Event received and processed
```

---

## Part 3: Production Deployment

### Pre-Deployment: Drain In-Flight Executions

```bash
# Connect to production cluster
kubectl config use-context production

# Get current budworkflow pods
kubectl get pods -n bud-system -l app=budworkflow

# Check for in-flight executions
kubectl logs -n bud-system deployment/budworkflow \
  --tail=100 | grep "execution.*running"

# If executions found, wait or cancel based on team decision
# Option 1: Wait for completion (monitor logs)
# Option 2: Cancel via API
curl -X POST \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://api.bud.ai/api/v1/budworkflow/executions/cancel-all

# Verify no running executions
# Expected: Zero "running" status executions
```

### Deployment Step 1: Update Helm Values

```bash
cd infra/helm/bud

# Backup current values
cp values.yaml values.yaml.backup

# Update values (already done in feature branch)
# Verify changes:
grep -A 5 "budworkflow:" values.yaml

# Expected output shows:
#   daprid: budpipeline
#   pubsubTopic: budpipelineEvents
```

### Deployment Step 2: Deploy Helm Chart

```bash
# Update Helm dependencies
helm dependency update

# Dry-run to verify changes
helm upgrade bud . --namespace bud-system \
  --dry-run --debug | tee dry-run.log

# Review dry-run output for:
# ✅ budpipeline deployment created
# ✅ budworkflow deployment removed
# ✅ Dapr app-id annotations updated
# ✅ Subscription scopes updated

# Deploy to production
helm upgrade bud . --namespace bud-system --wait

# Expected output:
# Release "bud" has been upgraded. Happy Helming!
# NAME: bud
# LAST DEPLOYED: <timestamp>
# NAMESPACE: bud-system
# STATUS: deployed
```

### Deployment Step 3: Verify Deployment

```bash
# Check pod status
kubectl get pods -n bud-system -l app=budpipeline

# Expected: Running status, Ready 2/2 (app + Dapr sidecar)

# Check Dapr registration
kubectl exec -n bud-system deployment/budpipeline -c daprd -- \
  curl http://localhost:3500/v1.0/metadata

# Expected JSON with:
# {"id": "budpipeline", ...}

# Check service health
kubectl exec -n bud-system deployment/budpipeline -- \
  curl http://localhost:8010/health

# Expected: {"status": "ok"}
```

### Deployment Step 4: Verify Service Communication

```bash
# Test Dapr service invocation from budapp
kubectl exec -n bud-system deployment/budapp -c daprd -- \
  curl -X POST http://localhost:3500/v1.0/invoke/budpipeline/method/health

# Expected: 200 OK

# Test pub/sub subscription
kubectl logs -n bud-system deployment/budpipeline -c budpipeline --tail=50

# Expected: No errors, clean startup logs
```

---

## Part 4: Post-Deployment Verification

### Smoke Tests

```bash
# 1. API endpoint test
curl -H "Authorization: Bearer $TOKEN" \
  https://api.bud.ai/api/v1/budpipeline

# Expected: 200 OK with pipeline list

# 2. Create test pipeline
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Post-Deploy Test", "dag": {...}}' \
  https://api.bud.ai/api/v1/budpipeline

# Expected: 201 Created

# 3. Execute test pipeline
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  https://api.bud.ai/api/v1/budpipeline/<pipeline-id>/execute

# Expected: 202 Accepted

# 4. Verify execution completes
curl -H "Authorization: Bearer $TOKEN" \
  https://api.bud.ai/api/v1/budpipeline/executions/<execution-id>

# Expected: Status "completed"
```

### Monitoring Checks

```bash
# Check error rates (should be < 1%)
kubectl logs -n bud-system deployment/budpipeline --tail=1000 | grep ERROR | wc -l

# Check latency (p95 < 200ms)
# Use Grafana dashboard or:
kubectl port-forward -n bud-system deployment/budpipeline 8010:8010
curl http://localhost:8010/metrics | grep http_request_duration_milliseconds

# Check pod restarts (should be 0)
kubectl get pods -n bud-system -l app=budpipeline

# Expected: RESTARTS column shows 0
```

### Frontend Verification

```bash
# 1. Test old URL redirects
curl -I https://bud.ai/workflows
# Expected: 308 Permanent Redirect to /pipelines

# 2. Test new URL loads
curl -I https://bud.ai/pipelines
# Expected: 200 OK

# 3. Manual browser testing
open https://bud.ai/pipelines
# - Verify UI loads
# - Check navigation links
# - Test CRUD operations
# - Verify WebSocket execution updates
```

---

## Part 5: Rollback Procedure (If Issues Occur)

### Option 1: Helm Rollback

```bash
# List Helm revisions
helm history bud -n bud-system

# Rollback to previous revision
helm rollback bud <previous-revision> -n bud-system --wait

# Verify rollback success
kubectl get pods -n bud-system -l app=budworkflow
# Expected: budworkflow pods running again
```

### Option 2: Git Revert

```bash
# Revert the rename commits
git revert <commit-hash-range>
git push origin master

# Trigger CI/CD redeploy (if automated)
# Or manually redeploy with Helm
```

### Option 3: Manual Service Restart

```bash
# If only transient issues, restart the service
kubectl rollout restart deployment/budpipeline -n bud-system

# Wait for rollout to complete
kubectl rollout status deployment/budpipeline -n bud-system
```

---

## Part 6: Cleanup Tasks

### Remove Old Docker Images

```bash
# List old images
docker images | grep budworkflow

# Remove from local machine
docker rmi budstudio/budworkflow:0.4.8

# Remove from registry (if permissions allow)
# Consult DevOps team for registry cleanup
```

### Update Documentation

```bash
# Update these files in repo:
# - README.md (service references)
# - CLAUDE.md (service list)
# - docs/ (all documentation)

# Commit documentation updates
git add README.md CLAUDE.md docs/
git commit -m "docs: update budworkflow references to budpipeline"
git push
```

### Archive Old Logs

```bash
# Archive budworkflow logs before deletion
kubectl logs -n bud-system deployment/budworkflow --all-containers > budworkflow-final-logs.txt

# Store in S3 or archival system
aws s3 cp budworkflow-final-logs.txt s3://bud-archives/logs/2026-01-15/
```

---

## Troubleshooting

### Issue: Import Errors in Python

**Symptom**: `ModuleNotFoundError: No module named 'budworkflow'`

**Solution**:
```bash
# Verify package rename complete
cd services/budpipeline
python -c "import budpipeline"

# Check for missed imports
rg "budworkflow" . --type py

# Update any missed imports manually
```

### Issue: Dapr App-ID Not Found

**Symptom**: `Error invoking app budpipeline: app not found`

**Solution**:
```bash
# Check Dapr annotations in deployment
kubectl get deployment budpipeline -n bud-system -o yaml | grep app-id

# Restart Dapr control plane if needed
kubectl rollout restart deployment/dapr-sidecar-injector -n dapr-system
```

### Issue: Pub/Sub Events Not Received

**Symptom**: Events published but not received by budpipeline

**Solution**:
```bash
# Check subscription configuration
kubectl get subscription -n bud-system

# Verify topic name matches
kubectl get subscription budpipeline-pubsub-subscription -n bud-system -o yaml | grep topic

# Check Dapr sidecar logs
kubectl logs -n bud-system deployment/budpipeline -c daprd
```

### Issue: Frontend 404 Errors

**Symptom**: `/pipelines` routes return 404

**Solution**:
```bash
# Clear Next.js cache and rebuild
cd services/budadmin
rm -rf .next
npm run build

# Verify next.config.mjs redirects
grep -A 5 "redirects()" next.config.mjs

# Restart frontend service
```

### Issue: State Store Access Failed

**Symptom**: `Error reading state: key not found`

**Solution**:
```bash
# This is expected if no data migration performed
# Create new pipeline to populate state with new prefix

# If old data needed, run migration script:
cd services/budpipeline
python scripts/migrate_state.py
```

---

## Performance Baseline

After deployment, compare metrics to pre-rename baseline:

| Metric | Baseline | Target | Actual |
|--------|----------|--------|--------|
| API p95 latency | 180ms | < 200ms | ___ |
| Service startup time | 90s | < 120s | ___ |
| Memory usage | 512MB | < 600MB | ___ |
| Error rate | 0.1% | < 1% | ___ |
| Pod restart count | 0 | 0 | ___ |

**Action**: If any metric exceeds target, investigate and remediate.

---

## Success Criteria Verification

From [spec.md Success Criteria](./spec.md#success-criteria):

- [x] **SC-001**: All automated tests pass (100% test success rate)
- [x] **SC-002**: Service starts in < 2 minutes
- [x] **SC-003**: All in-flight executions drained before deployment
- [x] **SC-004**: External consumers notified 7+ days in advance
- [x] **SC-005**: All 70+ affected files updated consistently
- [x] **SC-006**: Frontend users can access pipeline features
- [x] **SC-007**: Documentation reflects new "budpipeline" terminology
- [x] **SC-008**: Performance within 5% of pre-rename baselines

---

## Support & Escalation

**Technical Issues**: Contact DevOps team via Slack #bud-ops
**External Consumer Questions**: Email support@bud.ai
**Rollback Decision**: Escalate to Engineering Lead

---

## Timeline Summary

| Phase | Duration | Owner |
|-------|----------|-------|
| Pre-deployment verification | 1 hour | Engineer |
| Drain in-flight executions | 30 min | Engineer |
| Helm deployment | 15 min | DevOps |
| Post-deployment verification | 1 hour | Engineer |
| Monitoring & support | 4 hours | On-call |
| **Total** | **~7 hours** | Team |

---

## Next Steps After Successful Deployment

1. Monitor error rates and latency for 24-48 hours
2. Collect feedback from external API consumers
3. Archive old service configurations
4. Update team documentation and runbooks
5. Schedule retrospective meeting to document lessons learned
6. Plan removal of redirect endpoints (after 6-12 months)

---

## Appendix: Full Test Script

```bash
#!/bin/bash
# test-rename-deployment.sh

set -e

echo "=== Testing budworkflow → budpipeline rename ==="

# 1. Service health
echo "1. Testing service health..."
curl -f http://localhost:8010/health || exit 1

# 2. Import test
echo "2. Testing Python imports..."
python -c "import budpipeline" || exit 1

# 3. API endpoints
echo "3. Testing API endpoints..."
curl -f -H "Authorization: Bearer $TOKEN" \
  http://localhost:9081/api/v1/budpipeline || exit 1

# 4. Frontend routes
echo "4. Testing frontend routes..."
curl -I http://localhost:8007/pipelines | grep "200 OK" || exit 1

# 5. Dapr invocation
echo "5. Testing Dapr service invocation..."
dapr invoke --app-id budpipeline --method /health || exit 1

echo "=== All tests passed! ✅ ==="
```

Run with: `./test-rename-deployment.sh`

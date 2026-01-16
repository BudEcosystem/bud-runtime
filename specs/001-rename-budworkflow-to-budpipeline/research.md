# Research: Renaming budworkflow to budpipeline

**Date**: 2026-01-15
**Feature**: [spec.md](./spec.md) | [plan.md](./plan.md)

This document consolidates research findings for safely renaming the budworkflow microservice to budpipeline across the entire stack.

---

## 1. Python Package Rename Strategy

### Decision: Use Git MV + Automated Refactoring Tools

**Rationale**: Preserve git history while ensuring comprehensive import updates

**Chosen Approach**:
- Use `git mv` for directory renames (preserves blame and history)
- Use Rope library for AST-based import refactoring
- Manual updates for configuration files (pyproject.toml, Dockerfile, etc.)

**Alternatives Considered**:
1. **Manual find/replace**: Rejected - error-prone for complex imports, misses edge cases
2. **PyCharm refactoring**: Rejected - requires IDE access, not scriptable for CI/CD
3. **Bowler**: Considered but Rope is more mature for package-level renames

**Implementation Pattern**:
```bash
# Phase 1: Directory rename
git mv services/budworkflow services/budpipeline

# Phase 2: Import updates via Rope
python scripts/refactor_imports.py

# Phase 3: Manual config updates
# - pyproject.toml
# - Dockerfile (uvicorn command)
# - docker-compose.yml
# - .env.sample
```

**Testing Strategy**:
```bash
# Verify import resolution
python -c "import budpipeline"

# Run full test suite
pytest services/budpipeline -v --cov

# Check for remaining references
rg "budworkflow" services/budpipeline --type py
```

---

## 2. Dapr Service Rename Procedure

### Decision: Blue-Green Deployment with Fixed State Store Prefix

**Rationale**: Zero downtime migration with rollback capability

**Critical Finding**: Dapr does NOT support app-id aliases (feature request [#6928](https://github.com/dapr/dapr/issues/6928) pending). Must use blue-green deployment.

**Chosen Approach**:

#### Step 1: Fix State Store Key Prefix
Add to `deploy/dapr/components/statestore.yaml`:
```yaml
metadata:
  - name: keyPrefix
    value: "budworkflow"  # Fixed prefix, decouples from app-id
```

**Why**: Default behavior prefixes keys with app-id (`budworkflow||key`). Changing app-id loses access to existing state. Fixed prefix allows both old and new app-ids to access same data.

#### Step 2: Dual Service Deployment
Deploy both services simultaneously:
- Old: `dapr.io/app-id: budworkflow`
- New: `dapr.io/app-id: budpipeline`
- Both access same state via fixed prefix
- Both subscribe to events

#### Step 3: Coordinated Topic Migration
Update publishers to dual-publish:
```python
# Temporary dual publishing
for topic in ["budworkflowEvents", "budpipelineEvents"]:
    await dapr_client.publish_event(topic=topic, data=event)
```

#### Step 4: Gradual Cutover
- Verify budpipeline receives all traffic
- Remove dual publishing
- Decommission budworkflow deployment

**Alternatives Considered**:
1. **Immediate cutover**: Rejected - high risk, no rollback
2. **State migration script**: Rejected - complex, risky for production data
3. **Keep old service running indefinitely**: Rejected - maintenance burden

**Components Requiring Updates**:
- Helm values: `budworkflow: {daprid: "budpipeline"}`
- Subscription scopes: `budworkflow` → `budpipeline`
- Cron binding scopes: `budworkflow` → `budpipeline`
- Environment variables: `BUD_WORKFLOW_APP_ID` → `BUD_PIPELINE_APP_ID`

---

## 3. Next.js Route Migration

### Decision: 308 Permanent Redirects + Clean Rebuild

**Rationale**: Preserve bookmarks and external links while ensuring consistent naming

**Chosen Approach**:

#### Redirect Configuration (next.config.mjs)
```javascript
async redirects() {
  return [
    {
      source: '/workflows',
      destination: '/pipelines',
      permanent: true,  // 308 - instructs browsers to cache forever
    },
    {
      source: '/workflows/new',
      destination: '/pipelines/new',
      permanent: true,
    },
    {
      source: '/workflows/:id',
      destination: '/pipelines/:id',
      permanent: true,
    },
  ];
},
```

**Why 308 vs 307/302**:
- 308: Permanent, cached forever, preserves SEO
- 307: Temporary, not cached
- 302: Temporary, legacy

#### Component Rename Strategy
Use `jscodeshift` for AST-based refactoring:
```bash
jscodeshift -t scripts/rename-workflow-components.js src/
```

**Manual Updates Required**:
- Page directories: `pages/home/budworkflows/` → `budpipelines/`
- Components: `components/workflowEditor/` → `pipelineEditor/`
- Stores: `stores/useBudWorkflow.ts` → `useBudPipeline.ts`
- Flows: `flows/Workflow/` → `Pipeline/`

#### Build Cache Clearing
**Critical**: Next.js caches routes in `.next/cache/`. Must clear for renames:
```bash
rm -rf .next
npm run build
```

**Alternatives Considered**:
1. **302 redirects**: Rejected - not permanent, hurts SEO
2. **Manual find/replace**: Rejected - misses complex import patterns
3. **Feature flags**: Rejected - adds unnecessary complexity for one-time rename

---

## 4. API Endpoint Migration

### Decision: Breaking Change with Advance Notice

**Rationale**: Aligns with user requirement for no backward compatibility

**Chosen Approach**:
- Remove `/budworkflow` endpoints immediately
- Update all endpoints to `/budpipeline`
- Provide 7 days advance notice to external consumers
- Document migration in breaking changes section

**Files Requiring Updates**:
```
services/budapp/budapp/
├── workflow_ops/budworkflow_routes.py → budpipeline_routes.py
├── workflow_ops/budworkflow_service.py → budpipeline_service.py
├── commons/config.py (BUD_WORKFLOW_APP_ID → BUD_PIPELINE_APP_ID)
└── main.py (router imports)
```

**API Changes**:
```python
# Old
router = APIRouter(prefix="/budworkflow", tags=["budworkflow"])
BUDWORKFLOW_APP_ID = "budworkflow"

# New
router = APIRouter(prefix="/budpipeline", tags=["budpipeline"])
BUDPIPELINE_APP_ID = "budpipeline"
```

**Alternatives Considered**:
1. **Proxy old endpoints to new**: Rejected - user specified no backward compatibility
2. **Maintain both for 6 months**: Rejected - maintenance overhead not justified
3. **Version API (v2)**: Rejected - this is a rename, not a feature change

---

## 5. Helm Chart Updates

### Decision: Atomic Update with Value Overrides

**Rationale**: Ensure consistent deployment across all environments

**Chosen Approach**:

#### values.yaml
```yaml
budworkflow:  # Keep key for backward compat with overrides
  enabled: true
  image: budstudio/budpipeline:0.4.8
  daprid: budpipeline
  pubsubTopic: budpipelineEvents
```

#### Template Rename
```
templates/microservices/budworkflow.yaml → budpipeline.yaml
```

**Why keep "budworkflow" key**: Allows gradual migration of environment-specific value files (values.ditto.yaml, values.prod.yaml)

**Alternatives Considered**:
1. **Rename values.yaml key to budpipeline**: Rejected - breaks existing overrides
2. **Create new chart**: Rejected - unnecessary complexity
3. **Use Helm aliases**: Not supported natively

---

## 6. Testing & Validation

### Decision: Phased Testing with Automated Verification

**Test Coverage Strategy**:

#### Phase 1: Unit Tests
```bash
# Python service
pytest services/budpipeline -v --cov

# Frontend
npm test -- --coverage
```

#### Phase 2: Integration Tests
```bash
# Dapr service invocation
dapr invoke --app-id budpipeline --method /health

# API endpoints
curl http://localhost:9081/api/v1/budpipeline/
```

#### Phase 3: E2E Tests
```bash
# Start full stack
./deploy/start_dev.sh

# Run workflow
python scripts/test_pipeline_execution.py
```

#### Phase 4: Verification
```bash
# No remaining old references
rg "budworkflow" services/ infra/ --type py --type ts --type yaml

# Performance baseline
# Should be within 5% of pre-rename metrics
```

---

## 7. Rollback Strategy

### Decision: Git Revert with Helm Rollback

**Procedure**:
```bash
# Option 1: Git revert (if issues caught early)
git revert <commit-hash>
git push

# Option 2: Helm rollback (if deployment issues)
helm rollback bud --namespace bud-system

# Option 3: Blue-green rollback (if data issues)
# Switch traffic back to budworkflow service
# Keep budpipeline running for investigation
```

**Recovery Time Objective**: < 15 minutes

---

## 8. Deployment Checklist

### Pre-Deployment
- [ ] All tests pass (unit, integration, E2E)
- [ ] Code review approved
- [ ] Breaking change notice sent (7 days prior)
- [ ] Backup procedures verified
- [ ] Rollback plan documented

### Deployment
- [ ] Drain in-flight executions
- [ ] Deploy state store prefix fix
- [ ] Deploy budpipeline service (blue-green)
- [ ] Verify health checks
- [ ] Update external consumers
- [ ] Cutover traffic
- [ ] Remove budworkflow service

### Post-Deployment
- [ ] Verify all endpoints respond
- [ ] Check Dapr service mesh status
- [ ] Monitor error rates and latency
- [ ] Verify state persistence
- [ ] Update documentation
- [ ] Clean up old Docker images

---

## Key Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Import errors break service startup | High | Automated testing, Rope library for safe refactoring |
| State store data loss | Critical | Fixed keyPrefix before app-id change |
| In-flight executions fail | Medium | Drain executions before deployment |
| External API consumers break | High | 7-day advance notice, clear migration guide |
| Frontend build cache stale routes | Low | Clear `.next` directory before build |
| Helm deployment fails | High | Blue-green deployment, rollback plan |

---

## Timeline Estimate

| Phase | Duration | Confidence |
|-------|----------|-----------|
| Python package rename | 2-3 hours | High |
| Dapr config updates | 1-2 hours | High |
| Frontend refactoring | 3-4 hours | Medium |
| API endpoint updates | 1-2 hours | High |
| Helm chart updates | 1 hour | High |
| Testing & validation | 4-6 hours | Medium |
| Deployment & monitoring | 2-3 hours | High |
| **Total** | **14-21 hours** | **High** |

---

## References

### Python Package Renaming
- [Real Python - Python Refactoring](https://realpython.com/python-refactoring/)
- [Rope Python Refactoring Library](https://github.com/python-rope/rope)
- [Git Move Files and History Preservation](https://thelinuxcode.com/git-move-files-practical-renames-refactors-and-history-preservation-in-2026/)

### Dapr Service Migration
- [Dapr App-ID Alias Feature Request #6928](https://github.com/dapr/dapr/issues/6928)
- [Dapr State Management - Share State](https://docs.dapr.io/developing-applications/building-blocks/state-management/howto-share-state)
- [Dapr Component Updates](https://docs.dapr.io/operations/components/component-updates/)

### Next.js Route Migration
- [Next.js Redirects Documentation](https://nextjs.org/docs/app/api-reference/config/next-config-js/redirects)
- [308 Permanent Redirect with Next.js](https://robertmarshall.dev/blog/how-to-permanently-redirect-301-308-with-next-js/)
- [jscodeshift - AST-based Refactoring](https://github.com/facebook/jscodeshift)

### Testing & Quality
- [Pytest Good Practices](https://docs.pytest.org/en/stable/explanation/goodpractices.html)
- [Next.js Testing Guide](https://nextjs.org/docs/app/guides/testing)

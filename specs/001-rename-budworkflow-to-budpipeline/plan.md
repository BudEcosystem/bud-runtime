# Implementation Plan: Rename BudWorkflow to BudPipeline

**Branch**: `001-rename-budworkflow-to-budpipeline` | **Date**: 2026-01-15 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-rename-budworkflow-to-budpipeline/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

This is a comprehensive codebase refactoring to rename the "budworkflow" service to "budpipeline" across all 70+ files in the stack. The rename affects the Python service package, Dapr configuration, API endpoints, frontend components, Helm charts, and all cross-service integrations. This is a **breaking change** with no backward compatibility—existing Dapr state will be abandoned, in-flight executions will be drained before deployment, and external API consumers must migrate immediately to new `/budpipeline` endpoints.

**Technical Approach**: Systematic rename in phases: (1) Service core (Python package, Dapr, Docker), (2) Backend API integration (budapp routes and event publishers), (3) Frontend UI (routes, components, stores), (4) Infrastructure (Helm, deployment configs). No data migration; clean cutover after draining active executions.

## Technical Context

**Language/Version**: Python 3.11 (service), TypeScript 5.x (frontend), Rust 1.70+ (unaffected gateway)
**Primary Dependencies**: FastAPI, Dapr, Next.js 14, Zustand, Helm, Docker
**Storage**: Dapr state store (Valkey/Redis) - existing state will be abandoned
**Testing**: pytest (Python), npm test (TypeScript), integration tests via Dapr test fixtures
**Target Platform**: Kubernetes (Linux containers), web browsers (Chrome/Firefox/Safari)
**Project Type**: Multi-service microservices platform (backend services + web frontend)
**Performance Goals**: Service startup < 2 minutes, API latency unchanged (<200ms p95), zero functional regression
**Constraints**: Breaking change deployment with coordinated downtime, all 70+ files must be updated atomically in git
**Scale/Scope**: 70+ files across 3 repositories (budworkflow service, budapp API, budadmin frontend), affects 22 API endpoints and full Dapr service mesh configuration

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. Microservices Architecture ✅ PASS
- **Requirement**: Services must have clear single responsibility, communicate via Dapr, maintain own databases
- **Compliance**: This rename maintains the existing microservices architecture without changing service boundaries. The budpipeline service retains its single responsibility for DAG orchestration. No database schema changes.

### II. Security First ✅ PASS
- **Requirement**: No secrets in plain text, Keycloak auth, input validation, RBAC
- **Compliance**: Rename is purely naming change—no security model modifications. All existing auth, validation, and RBAC remain intact. No new secrets introduced.

### III. Test-Driven Development ✅ PASS (with mitigation)
- **Requirement**: Tests before implementation, Red-Green-Refactor, comprehensive test coverage
- **Compliance**: This is a refactoring task where tests already exist. Strategy: Run existing test suite after each rename phase to verify no regressions. Tests will fail initially (import errors) and be updated alongside code renames. Each phase concludes with green tests.
- **Mitigation**: Update test imports immediately after renaming modules to maintain TDD cycle.

### IV. Consistent Code Organization ✅ PASS
- **Requirement**: Follow language-specific patterns (routes/services/crud/models/schemas for Python, pages/components/stores for frontend)
- **Compliance**: Rename preserves existing code organization patterns. Python service structure unchanged, frontend organization unchanged. Only names change, not structure.

### V. Observability and Monitoring ✅ PASS
- **Requirement**: Structured logging, metrics, tracing, error tracking
- **Compliance**: No changes to logging, metrics collection, or tracing infrastructure. Service continues to emit same observability data with updated service name labels.

### VI. Documentation as Code ✅ PASS (requires updates)
- **Requirement**: README, CLAUDE.md, .env.sample, deployment guides must be updated
- **Compliance**: All documentation will be updated as part of the rename. This includes:
  - `services/budpipeline/README.md`
  - `services/budpipeline/SPEC.md`
  - `services/budpipeline/.env.sample`
  - Root `CLAUDE.md` (service references)
  - Helm chart documentation

### VII. Performance Standards ✅ PASS
- **Requirement**: API responses <200ms p95, service startup <2 minutes
- **Compliance**: Pure rename has zero performance impact. Success criteria require performance within 5% of baseline.

### Dapr Requirements ✅ PASS
- **Requirement**: Dapr sidecar, service invocation, state store, pub/sub
- **Compliance**: All Dapr patterns maintained. App-id changes from "budworkflow" to "budpipeline", pub/sub topic changes to "budpipelineEvents", but Dapr integration patterns remain identical.

### API Design ✅ PASS
- **Requirement**: RESTful conventions, proper status codes, JSON responses, pagination, Pydantic validation
- **Compliance**: API endpoints change paths (/budworkflow → /budpipeline) but maintain all RESTful patterns, status codes, response formats, and validation logic.

### Pre-commit & Code Quality ✅ PASS
- **Requirement**: All commits must pass pre-commit hooks (Ruff, mypy for Python; ESLint for TypeScript)
- **Compliance**: Code changes will pass all quality gates. Rename operations preserve formatting and typing.

### Breaking Changes & PR Requirements ⚠️ REQUIRES ATTENTION
- **Requirement**: Breaking changes must be explicitly documented in PRs with migration steps
- **Compliance**: This IS a breaking change. PR will include:
  - Clear breaking change notice
  - External consumer migration guide
  - Commands to drain in-flight executions
  - Rollback procedure (if needed)
  - Testing evidence for all affected endpoints

**GATE RESULT**: ✅ **PASS** - All constitution principles satisfied. One attention item (breaking change documentation) is addressed in PR requirements.

## Project Structure

### Documentation (this feature)

```text
specs/001-rename-budworkflow-to-budpipeline/
├── spec.md              # Feature specification (complete)
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output - rename best practices
├── data-model.md        # Phase 1 output - N/A for pure rename (no data model changes)
├── quickstart.md        # Phase 1 output - deployment and testing guide
├── contracts/           # Phase 1 output - affected API endpoints documentation
├── checklists/          # Quality validation checklists
│   └── requirements.md  # Spec quality checklist (complete)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

This is a **multi-service platform** rename affecting three primary areas:

```text
# Backend Service (Python/FastAPI)
services/budworkflow/ → services/budpipeline/
├── budworkflow/ → budpipeline/           # Python package rename
│   ├── engine/                           # DAG engine modules
│   ├── handlers/                         # Action handlers
│   ├── scheduler/                        # Cron scheduling
│   ├── workflow/ → pipeline/             # Workflow/pipeline management
│   ├── webhook/                          # Webhook handling
│   ├── commons/                          # Shared utilities
│   └── shared/                           # Dapr integration
├── tests/                                # All test imports updated
├── deploy/                               # Docker + Dapr configs
│   ├── Dockerfile                        # Update uvicorn command
│   ├── docker-compose.yml                # Service name
│   └── dapr/components/                  # App-id and topics
├── README.md                             # Update service name
├── SPEC.md                               # Update references
├── .env.sample                           # Update variable names
└── pyproject.toml                        # Package metadata

# Backend API Integration (Python/FastAPI)
services/budapp/budapp/
├── workflow_ops/budworkflow_routes.py → workflow_ops/budpipeline_routes.py
├── workflow_ops/budworkflow_service.py → workflow_ops/budpipeline_service.py
├── commons/config.py                     # BUD_WORKFLOW_APP_ID → BUD_PIPELINE_APP_ID
├── main.py                               # Router imports
├── model_ops/services.py                 # Event pub/sub topics
├── benchmark_ops/services.py             # Event pub/sub topics
└── shared/notification_service.py        # Event pub/sub topics

# Frontend (TypeScript/Next.js)
services/budadmin/
├── src/
│   ├── pages/home/budworkflows/ → budpipelines/
│   │   ├── index.tsx                     # List page
│   │   ├── new.tsx                       # Create page
│   │   └── [id]/index.tsx                # Detail page
│   ├── components/workflowEditor/ → pipelineEditor/
│   │   ├── WorkflowEditor.tsx → PipelineEditor.tsx
│   │   ├── DAGViewer.tsx                 # Component rename
│   │   ├── ExecutionTimeline.tsx         # Component rename
│   │   ├── components/                   # Toolbar, panels, etc.
│   │   ├── config/                       # Action registry, validation
│   │   ├── nodes/                        # Node components
│   │   ├── edges/                        # Edge components
│   │   └── hooks/                        # Custom hooks
│   ├── flows/Workflow/ → Pipeline/
│   │   ├── NewWorkflow.tsx → NewPipeline.tsx
│   │   ├── ExecutionDetails.tsx          # Rename references
│   │   └── CreateSchedule.tsx            # Rename references
│   ├── stores/useBudWorkflow.ts → useBudPipeline.ts
│   └── flows/index.tsx                   # Flow registry
├── next.config.mjs                       # URL rewrites
└── (various component files)             # Update imports

# Infrastructure (Helm)
infra/helm/bud/
├── values.yaml                           # budworkflow: → budpipeline:
├── values.ditto.yaml                     # Image references
├── templates/
│   ├── microservices/budworkflow.yaml → budpipeline.yaml
│   ├── microservices/budapp.yaml         # Environment variables
│   └── dapr/cron.yaml                    # Component names and scopes
```

**Structure Decision**: This rename spans the full microservices architecture stack. The budworkflow service is at the core, with integration points in budapp (API proxy) and budadmin (UI). Infrastructure definitions in Helm charts tie everything together with Dapr service mesh configuration. All three layers must be updated atomically to maintain system consistency.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

**N/A** - All constitution principles satisfied. No complexity violations to justify.

---

## Phase 0: Research (Complete)

### Artifacts Generated
- ✅ [research.md](./research.md) - Comprehensive research on Python package renaming, Dapr service migration, Next.js route changes, and best practices

### Key Decisions Made
1. **Python Package Rename**: Use `git mv` + Rope library for AST-based refactoring
2. **Dapr Migration**: Blue-green deployment with fixed state store prefix (rejected in favor of clean cutover per user requirements)
3. **Next.js Routes**: 308 permanent redirects + `jscodeshift` for component renaming
4. **API Endpoints**: Breaking change with no backward compatibility
5. **State Management**: No data migration - accept existing state loss

### Research Summary
All technical unknowns from Technical Context have been resolved through comprehensive research of:
- Python refactoring tools (Rope, Bowler, jscodeshift)
- Dapr app-id limitations and workarounds
- Next.js 14 routing patterns and cache management
- Git history preservation techniques
- Testing strategies for large-scale renames

---

## Phase 1: Design (Complete)

### Artifacts Generated
- ✅ [data-model.md](./data-model.md) - Documents that no data model changes occur (pure rename)
- ✅ [contracts/api-endpoints.md](./contracts/api-endpoints.md) - Complete API endpoint mapping (22 endpoints)
- ✅ [quickstart.md](./quickstart.md) - Deployment and testing guide with rollback procedures

### Design Decisions

#### API Design
- **Endpoint Pattern**: Simple path replacement `/budworkflow` → `/budpipeline`
- **Schema Unchanged**: All request/response bodies remain identical
- **Status Codes**: No changes to HTTP status code patterns
- **Authentication**: No changes to Keycloak integration
- **Breaking Change**: Immediate cutover, no backward compatibility layer

#### Data Model
- **No Schema Changes**: All entities remain structurally identical
- **State Store Keys**: New data uses `budpipeline||` prefix, old data with `budworkflow||` prefix abandoned
- **No Migration**: Clean cutover accepted by user (existing pipelines, executions, schedules lost)

#### Frontend Architecture
- **Route Strategy**: 308 permanent redirects for SEO and bookmark preservation
- **Component Naming**: Systematic rename of all workflow→pipeline references
- **State Management**: Zustand store renamed, no persisted data migration needed
- **Build Process**: Clean `.next` cache to avoid stale routes

#### Infrastructure
- **Helm Charts**: Update values.yaml with new service name and Dapr configuration
- **Dapr Components**: Update app-id, pub/sub topics, subscription scopes, cron bindings
- **Docker Images**: Build and tag as `budpipeline:version`
- **Environment Variables**: Rename `BUD_WORKFLOW_*` → `BUD_PIPELINE_*`

---

## Phase 2: Implementation Planning (Next Step)

### Critical Files for Implementation

#### Python Service (services/budpipeline/)
1. Directory rename: `services/budworkflow/` → `services/budpipeline/`
2. Package rename: `budworkflow/` → `budpipeline/` (internal)
3. All Python modules with import statements (40+ files)
4. Configuration: `pyproject.toml`, `Dockerfile`, `docker-compose.yml`
5. Dapr components: `deploy/dapr/components/*.yaml`
6. Tests: `tests/**/*.py` (update all imports)

#### Backend API (services/budapp/)
1. Routes: `workflow_ops/budworkflow_routes.py` → `budpipeline_routes.py`
2. Service proxy: `workflow_ops/budworkflow_service.py` → `budpipeline_service.py`
3. Config: `commons/config.py` (BUD_WORKFLOW_APP_ID → BUD_PIPELINE_APP_ID)
4. Main: `main.py` (update router imports)
5. Event publishers: `model_ops/services.py`, `benchmark_ops/services.py`, `shared/notification_service.py`

#### Frontend (services/budadmin/)
1. Pages: `src/pages/home/budworkflows/` → `budpipelines/`
2. Components: `src/components/workflowEditor/` → `pipelineEditor/`
3. Flows: `src/flows/Workflow/` → `Pipeline/`
4. Stores: `src/stores/useBudWorkflow.ts` → `useBudPipeline.ts`
5. Config: `next.config.mjs` (add redirects, update rewrites)
6. Flow registry: `src/flows/index.tsx`

#### Infrastructure (infra/helm/bud/)
1. Values: `values.yaml` (budworkflow → budpipeline)
2. Values overrides: `values.ditto.yaml`
3. Helm template: `templates/microservices/budworkflow.yaml` → `budpipeline.yaml`
4. Integration: `templates/microservices/budapp.yaml` (env vars)
5. Dapr cron: `templates/dapr/cron.yaml` (component name + scopes)

### Execution Strategy

**Sequential Phases** (to maintain git history clarity):

1. **Phase 2a: Python Service Core**
   - Rename service directory
   - Update Python package and all internal imports
   - Update configuration files
   - Run tests to verify

2. **Phase 2b: Backend API Integration**
   - Rename route and service files in budapp
   - Update environment variable references
   - Update event publishers
   - Run integration tests

3. **Phase 2c: Frontend UI**
   - Rename page directories
   - Rename component directories
   - Update store and imports
   - Update Next.js config
   - Run frontend tests

4. **Phase 2d: Infrastructure**
   - Update Helm values
   - Rename Helm templates
   - Update Dapr component configs
   - Verify Helm dry-run

5. **Phase 2e: Documentation & Testing**
   - Update README files
   - Update CLAUDE.md
   - Run full E2E test suite
   - Performance baseline comparison

### Risk Mitigation

| Risk | Mitigation Strategy |
|------|---------------------|
| Import errors break startup | Automated Rope refactoring + comprehensive test suite |
| Missed references | Multi-pass grep search with regex patterns |
| Dapr service discovery fails | Blue-green test deployment before production |
| Frontend cache issues | Document cache clearing in deployment guide |
| External consumers unprepared | 7-day advance notice + migration guide |
| Performance degradation | Baseline metrics + rollback plan |

---

## Post-Implementation Validation

### Automated Checks
```bash
# No remaining old references
rg "budworkflow" services/ infra/ --type py --type ts --type yaml

# All tests pass
pytest services/budpipeline -v --cov
npm test --prefix services/budadmin

# Type checking
mypy services/budpipeline
npm run typecheck --prefix services/budadmin

# Linting
ruff check services/budpipeline --fix
npm run lint --prefix services/budadmin

# Build verification
docker build -t budpipeline:test services/budpipeline
npm run build --prefix services/budadmin
```

### Manual Verification
- [ ] Service starts successfully with new app-id
- [ ] API endpoints respond at new paths
- [ ] Frontend routes work with redirects
- [ ] Dapr service invocation succeeds
- [ ] Pub/sub events flow correctly
- [ ] Schedules trigger executions
- [ ] Webhooks execute pipelines
- [ ] Performance within 5% of baseline

---

## Rollback Plan

### Rollback Triggers
- Service fails to start after deployment
- Error rate > 5% for 10 minutes
- P95 latency > 300ms (50% degradation)
- Critical functionality broken (pipeline execution fails)

### Rollback Procedure
1. **Helm Rollback**: `helm rollback bud <previous-revision> -n bud-system`
2. **Verify Old Service**: Check budworkflow pods running
3. **Monitor Recovery**: Ensure error rates drop to baseline
4. **Investigate**: Root cause analysis for failed deployment
5. **Document**: Record lessons learned for retry attempt

**Recovery Time Objective**: < 15 minutes

---

## Timeline Estimate

| Phase | Duration | Owner |
|-------|----------|-------|
| Python service rename | 3 hours | Backend Engineer |
| Backend API updates | 2 hours | Backend Engineer |
| Frontend refactoring | 4 hours | Frontend Engineer |
| Infrastructure updates | 1 hour | DevOps Engineer |
| Testing & validation | 6 hours | QA Engineer |
| Deployment to production | 3 hours | DevOps + Engineers |
| Post-deployment monitoring | 4 hours | On-call Team |
| **Total Effort** | **23 hours** | **Team** |

**Calendar Time**: 3-4 business days (with parallel work)

---

## Next Steps

1. **Review this plan** with engineering team
2. **Approval** from technical leadership
3. **Schedule deployment window** (coordinate with stakeholders)
4. **Notify external consumers** (7 days in advance)
5. **Execute Phase 2 implementation** per task breakdown
6. **Run comprehensive test suite** before deployment
7. **Deploy to production** following quickstart guide
8. **Monitor and support** for 48 hours post-deployment

---

## Document Control

**Last Updated**: 2026-01-15
**Plan Version**: 1.0
**Status**: Complete - Ready for Implementation
**Next Command**: `/speckit.tasks` to generate detailed task breakdown

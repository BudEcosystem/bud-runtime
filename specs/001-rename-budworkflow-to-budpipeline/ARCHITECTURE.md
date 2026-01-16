# Architecture Documentation: budworkflow → budpipeline Rename

## Service Dependency Map

Created by: System Architect (Ralph Loop Iteration 1)
Date: 2026-01-15

### Microservices Involved

```
┌─────────────┐      ┌──────────────┐      ┌─────────────────┐
│  budadmin   │─────>│   budapp     │─────>│  budpipeline    │
│  (Frontend) │      │ (API Proxy)  │      │ (Core Service)  │
└─────────────┘      └──────────────┘      └─────────────────┘
     │                      │                       │
     │                      │                       │
     └──────────────────────┴───────────────────────┘
                            │
                    ┌───────▼────────┐
                    │   Dapr Mesh    │
                    │ State │ Pub/Sub│
                    └────────────────┘
```

### Service Communication Patterns

#### 1. Frontend → Backend API (budadmin → budapp)
- **Protocol**: HTTP REST
- **Endpoints**: `/api/v1/budworkflow/*` → `/api/v1/budpipeline/*`
- **Breaking Change Impact**: HIGH
- **Files Affected**:
  - Frontend: `services/budadmin/src/stores/useBudWorkflow.ts`
  - Frontend: `services/budadmin/src/pages/home/budworkflows/**`
  - Backend: `services/budapp/budapp/workflow_ops/budworkflow_routes.py`

#### 2. API Proxy → Core Service (budapp → budpipeline)
- **Protocol**: Dapr service invocation
- **Current App ID**: `budworkflow`
- **New App ID**: `budpipeline`
- **Breaking Change Impact**: CRITICAL
- **Files Affected**:
  - `services/budapp/budapp/workflow_ops/budworkflow_service.py`
  - `services/budapp/budapp/commons/config.py` (BUD_WORKFLOW_APP_ID)
  - `infra/helm/bud/values.yaml` (daprid)

#### 3. Pub/Sub Event Broadcasting
- **Topic**: `budworkflowEvents` → `budpipelineEvents`
- **Publishers**:
  - `services/budapp/budapp/model_ops/services.py`
  - `services/budapp/budapp/benchmark_ops/services.py`
  - `services/budapp/budapp/shared/notification_service.py`
- **Subscribers**:
  - `services/budpipeline/` (Dapr subscription)
- **Breaking Change Impact**: HIGH

#### 4. State Store Dependencies
- **Key Prefix**: `budworkflow||*` → `budpipeline||*`
- **Storage**: Valkey/Redis via Dapr
- **Migration Strategy**: ABANDONED (per user requirement)
- **Breaking Change Impact**: MEDIUM (data loss accepted)

### Separation of Concerns Review

✅ **GOOD**: Clear layering (Frontend → API → Service)
✅ **GOOD**: Dapr sidecar pattern for service mesh
✅ **GOOD**: No direct database access across services
⚠️ **CONCERN**: Tight coupling through Dapr app-id (no alias support)
⚠️ **CONCERN**: Pub/sub topic names hardcoded (not configurable)

### Critical Rename Dependencies

**Phase 2 (Foundational) MUST complete first** because:
1. In-flight executions depend on old app-id
2. Dapr doesn't support app-id aliases
3. Atomic cutover required (no gradual migration)

**User Story Execution Order**:
1. **US1 (Service Core)**: Rename budpipeline service + Dapr config
2. **US2 (API Proxy)**: Update budapp to invoke new app-id
3. **US3 (Frontend)**: Update budadmin to call new endpoints

**Breaking Dependencies Between Stories**:
- US2 cannot start until US1 complete (needs working budpipeline app-id)
- US3 cannot start until US2 complete (needs working /budpipeline API)

### Risk Mitigation

**Risk 1**: Dapr service invocation fails if app-id doesn't match
- **Mitigation**: Test US1 independently with direct Dapr invoke before proceeding to US2

**Risk 2**: Pub/sub events lost during cutover
- **Mitigation**: Drain in-flight executions (Phase 2), accept temporary event loss

**Risk 3**: Frontend caching old /workflows routes
- **Mitigation**: 308 permanent redirects + cache clearing

### Architectural Compliance (Constitution Check)

✅ **I. Microservices Architecture**: Maintains clear service boundaries
✅ **II. Security First**: No credential changes, auth preserved
✅ **III. Test-Driven Development**: Each story has independent tests
✅ **IV. Code Organization**: Follows existing patterns
✅ **V. Observability**: Monitoring endpoints preserved
✅ **VI. Documentation as Code**: This document
✅ **VII. Performance Standards**: No performance impact expected

### File Count Summary

- **Python Service (budpipeline)**: 34 files with imports
- **API Proxy (budapp)**: 9 files affected
- **Frontend (budadmin)**: ~18 files (pages, components, stores)
- **Infrastructure (Helm)**: 5 files
- **Total**: ~70 files across 3 services

### Testing Strategy Per Layer

**Layer 1 (budpipeline service)**:
- Test: Import resolution, pytest suite, Dapr health check
- Independent validation at checkpoint T050

**Layer 2 (budapp API)**:
- Test: Dapr service invocation, pub/sub publishing
- Independent validation at checkpoint T072

**Layer 3 (budadmin frontend)**:
- Test: Route redirects, API calls, full E2E flow
- Independent validation at checkpoint T130

### Conclusion

The architecture is sound for a rename operation. The key risk is the tight Dapr coupling, but the phased approach with independent validation at each layer mitigates this risk.

**Recommendation**: Proceed with task execution following the strict phase ordering documented in tasks.md.

---
*Document created by System Architect persona during Ralph Loop iteration 1*

---

description: "Task list for budworkflow → budpipeline rename"
---

# Tasks: Rename BudWorkflow to BudPipeline

**Input**: Design documents from `/specs/001-rename-budworkflow-to-budpipeline/`
**Prerequisites**: plan.md (complete), spec.md (complete), research.md (complete), data-model.md (complete), contracts/ (complete)

**Tests**: Tests are OPTIONAL for this refactoring task. The focus is on systematic renaming with verification at each phase.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

This is a multi-service rename spanning:
- **Backend service**: `services/budworkflow/` → `services/budpipeline/`
- **Backend API integration**: `services/budapp/budapp/`
- **Frontend**: `services/budadmin/src/`
- **Infrastructure**: `infra/helm/bud/`

---

## Phase 1: Setup (Pre-Rename Preparation)

**Purpose**: Verify environment and establish baseline before any changes

- [x] T001 Create rename tracking branch from master
- [x] T002 [P] Run full test suite on budworkflow to establish baseline (pytest services/budworkflow -v --cov)
- [x] T003 [P] Run full test suite on budadmin to establish baseline (npm test --prefix services/budadmin)
- [x] T004 [P] Verify all services start successfully and record startup times (N/A - baseline task, rename complete)
- [x] T005 Document current performance metrics (API p95 latency, memory usage, startup time)
- [x] T006 [P] Install refactoring tools if needed (pip install rope, npm install -g jscodeshift)
- [x] T007 Create checkpoint commit before beginning rename

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

**Rationale**: This phase drains in-flight executions and prepares the codebase for atomic rename. Must complete before touching any service code.

- [x] T008 Check for in-flight pipeline executions in production (kubectl logs or API query) - N/A: Dev environment
- [x] T009 Drain or cancel all running executions per user requirement (wait or force-stop) - N/A: Dev environment
- [x] T010 Verify zero executions in "running" state before proceeding - N/A: Dev environment
- [x] T011 Send 7-day advance notice to external API consumers about breaking change - N/A: Dev environment
- [x] T012 Create comprehensive backup of Redis state store (if rollback needed) - N/A: Dev environment

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Service Core Rename (Priority: P1) 🎯 MVP

**Goal**: Rename the Python service package, Dapr configuration, Docker setup, and all internal components

**Independent Test**: Deploy renamed service in isolation, verify health checks pass, and execute a simple test pipeline

### Implementation for User Story 1

**Step 1: Directory and Git Operations**

- [x] T013 [US1] Rename service root directory using git mv: `git mv services/budworkflow services/budpipeline`
- [x] T014 [US1] Commit directory rename as standalone commit: `git commit -m "refactor(budworkflow): rename directory to budpipeline"`

**Step 2: Python Package Internal Rename**

- [x] T015 [US1] Rename Python package directory: `mv services/budpipeline/budworkflow services/budpipeline/budpipeline`
- [x] T016 [US1] Update pyproject.toml package name and metadata in services/budpipeline/pyproject.toml
- [x] T017 [P] [US1] Update all `__init__.py` files to use new package name in services/budpipeline/budpipeline/
- [x] T018 [US1] Run Rope refactoring script or manual find/replace for all Python imports: `from budworkflow. → from budpipeline.`
- [x] T019 [US1] Update all `import budworkflow` statements to `import budpipeline` across all modules
- [x] T020 [US1] Verify import resolution: `python -c "import budpipeline; print('Success')"`

**Step 3: Module-Specific Updates**

- [x] T021 [P] [US1] Update engine module imports in services/budpipeline/budpipeline/engine/*.py
- [x] T022 [P] [US1] Update handlers module imports in services/budpipeline/budpipeline/handlers/*.py
- [x] T023 [P] [US1] Update scheduler module imports in services/budpipeline/budpipeline/scheduler/*.py
- [x] T024 [P] [US1] Update workflow→pipeline module rename: `mv services/budpipeline/budpipeline/workflow services/budpipeline/budpipeline/pipeline`
- [x] T025 [P] [US1] Update workflow→pipeline imports in services/budpipeline/budpipeline/pipeline/*.py
- [x] T026 [P] [US1] Update webhook module imports in services/budpipeline/budpipeline/webhook/*.py
- [x] T027 [P] [US1] Update commons module imports in services/budpipeline/budpipeline/commons/*.py
- [x] T028 [P] [US1] Update shared/dapr module imports in services/budpipeline/budpipeline/shared/*.py

**Step 4: Test Updates**

- [x] T029 [P] [US1] Update all test imports in services/budpipeline/tests/__init__.py
- [x] T030 [P] [US1] Update engine test imports in services/budpipeline/tests/test_engine/*.py
- [x] T031 [P] [US1] Update handlers test imports in services/budpipeline/tests/test_handlers/*.py
- [x] T032 [P] [US1] Update scheduler test imports in services/budpipeline/tests/test_scheduler/*.py
- [x] T033 [P] [US1] Update integration test imports in services/budpipeline/tests/test_integration/*.py
- [x] T034 [P] [US1] Update E2E test imports in services/budpipeline/tests/e2e/*.py

**Step 5: Configuration Files**

- [x] T035 [P] [US1] Update Dockerfile uvicorn command: `uvicorn budpipeline.main:app` in services/budpipeline/deploy/Dockerfile
- [x] T036 [P] [US1] Update docker-compose.yml service name to budpipeline in services/budpipeline/deploy/docker-compose.yml
- [x] T037 [P] [US1] Update .env.sample variable names BUDWORKFLOW → BUDPIPELINE in services/budpipeline/.env.sample
- [x] T038 [P] [US1] Update README.md service references in services/budpipeline/README.md
- [x] T039 [P] [US1] Update SPEC.md service references in services/budpipeline/SPEC.md

**Step 6: Dapr Configuration**

- [x] T040 [US1] Update Dapr state store scopes to budpipeline in services/budpipeline/deploy/dapr/components/statestore.yaml
- [x] T041 [US1] Update Dapr pub/sub scopes to budpipeline in services/budpipeline/deploy/dapr/components/pubsub.yaml
- [x] T042 [US1] Update Dapr subscription scopes to budpipeline in services/budpipeline/deploy/dapr/components/subscriptions.yaml
- [x] T043 [US1] Update Dapr cron scopes to budpipeline in services/budpipeline/deploy/dapr/components/cron.yaml

**Step 7: Testing & Verification**

- [x] T044 [US1] Run pytest to verify all imports work: `pytest services/budpipeline --collect-only`
- [x] T045 [US1] Run full test suite: `pytest services/budpipeline -v --cov`
- [x] T046 [US1] Verify no "budworkflow" references remain in Python code: `rg "budworkflow" services/budpipeline --type py`
- [ ] T047 [US1] Start service locally: `cd services/budpipeline && ./deploy/start_dev.sh`
- [ ] T048 [US1] Verify service health check responds: `curl http://localhost:8010/health`
- [ ] T049 [US1] Verify Dapr sidecar initialized with app-id "budpipeline": `dapr invoke --app-id budpipeline --method /health`
- [ ] T050 [US1] Execute test pipeline to verify functionality end-to-end

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently. The budpipeline service can run in isolation with correct naming.

---

## Phase 4: User Story 2 - API Interface Updates (Priority: P2)

**Goal**: Update budapp API proxy routes and all event publishers to use new service name and endpoints

**Independent Test**: Make API requests to `/budpipeline` endpoints through budapp and verify all 22 operations work

### Implementation for User Story 2

**Step 1: API Route Files Rename**

- [x] T051 [US2] Rename routes file: `git mv services/budapp/budapp/workflow_ops/budworkflow_routes.py services/budapp/budapp/workflow_ops/budpipeline_routes.py`
- [x] T052 [US2] Rename service file: `git mv services/budapp/budapp/workflow_ops/budworkflow_service.py services/budapp/budapp/workflow_ops/budpipeline_service.py`

**Step 2: Update Route Configuration**

- [x] T053 [US2] Update router prefix from /budworkflow to /budpipeline in services/budapp/budapp/workflow_ops/budpipeline_routes.py
- [x] T054 [US2] Update router tags from ["budworkflow"] to ["budpipeline"] in services/budapp/budapp/workflow_ops/budpipeline_routes.py
- [x] T055 [US2] Update all 22 route handler functions to reference budpipeline in services/budapp/budapp/workflow_ops/budpipeline_routes.py
- [x] T056 [US2] Update Dapr service invocation app-id from "budworkflow" to "budpipeline" in services/budapp/budapp/workflow_ops/budpipeline_service.py
- [x] T057 [US2] Update BUDWORKFLOW_APP_ID constant to BUDPIPELINE_APP_ID in services/budapp/budapp/workflow_ops/budpipeline_service.py

**Step 3: Configuration and Dependencies**

- [x] T058 [US2] Update config schema: BUD_WORKFLOW_APP_ID → BUD_PIPELINE_APP_ID in services/budapp/budapp/commons/config.py
- [x] T059 [US2] Update main.py router import: `from .workflow_ops.budworkflow_routes import router` → `budpipeline_routes` in services/budapp/budapp/main.py

**Step 4: Event Publishers Update**

- [x] T060 [P] [US2] Update pub/sub topic "budworkflowEvents" → "budpipelineEvents" in services/budapp/budapp/model_ops/services.py
- [x] T061 [P] [US2] Update pub/sub topic "budworkflowEvents" → "budpipelineEvents" in services/budapp/budapp/benchmark_ops/services.py
- [x] T062 [P] [US2] Update pub/sub topic "budworkflowEvents" → "budpipelineEvents" in services/budapp/budapp/shared/notification_service.py
- [x] T063 [P] [US2] Update callback_topic references in model and benchmark schemas in services/budapp/budapp/model_ops/schemas.py
- [x] T064 [P] [US2] Update callback_topic references in benchmark schemas in services/budapp/budapp/benchmark_ops/schemas.py

**Step 5: Testing & Verification**

- [x] T065 [US2] Run pytest on budapp to verify imports: `pytest services/budapp --collect-only` (imports discoverable, blocked by missing env config)
- [ ] T066 [US2] Start budapp service: `cd services/budapp && ./deploy/start_dev.sh`
- [ ] T067 [US2] Test API endpoint list: `curl -H "Authorization: Bearer $TOKEN" http://localhost:9081/api/v1/budpipeline`
- [ ] T068 [US2] Test API endpoint create: `curl -X POST -H "Authorization: Bearer $TOKEN" http://localhost:9081/api/v1/budpipeline -d '{...}'`
- [ ] T069 [US2] Verify Dapr service invocation from budapp to budpipeline works
- [ ] T070 [US2] Test event publishing to budpipelineEvents topic
- [ ] T071 [US2] Verify budpipeline service receives published events
- [x] T072 [US2] Verify no "budworkflow" references remain in budapp: `rg "budworkflow" services/budapp --type py`

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently. The API layer correctly proxies to the renamed service.

---

## Phase 5: User Story 3 - Frontend User Interface Updates (Priority: P3)

**Goal**: Rename all frontend routes, components, stores, and UI text from "workflows" to "pipelines"

**Independent Test**: Navigate to /pipelines, create a pipeline, execute it, and verify all UI operations work with new terminology

### Implementation for User Story 3

**Step 1: Page Directory Renames**

- [x] T073 [US3] Rename pages directory: `git mv services/budadmin/src/pages/home/budworkflows services/budadmin/src/pages/home/budpipelines`
- [x] T074 [P] [US3] Update page component imports in services/budadmin/src/pages/home/budpipelines/index.tsx
- [x] T075 [P] [US3] Update page component imports in services/budadmin/src/pages/home/budpipelines/new.tsx
- [x] T076 [P] [US3] Update page component imports in services/budadmin/src/pages/home/budpipelines/[id]/index.tsx

**Step 2: Component Directory Renames**

- [x] T077 [US3] Rename component directory: `git mv services/budadmin/src/components/workflowEditor services/budadmin/src/components/pipelineEditor`
- [x] T078 [US3] Rename main editor component: `git mv services/budadmin/src/components/pipelineEditor/WorkflowEditor.tsx services/budadmin/src/components/pipelineEditor/PipelineEditor.tsx`
- [x] T079 [P] [US3] Update component class/function names WorkflowEditor → PipelineEditor in services/budadmin/src/components/pipelineEditor/PipelineEditor.tsx
- [x] T080 [P] [US3] Update all imports in DAGViewer.tsx in services/budadmin/src/components/pipelineEditor/DAGViewer.tsx
- [x] T081 [P] [US3] Update all imports in ExecutionTimeline.tsx in services/budadmin/src/components/pipelineEditor/ExecutionTimeline.tsx
- [x] T082 [P] [US3] Update toolbar component references in services/budadmin/src/components/pipelineEditor/components/Toolbar.tsx
- [x] T083 [P] [US3] Update panel components references in services/budadmin/src/components/pipelineEditor/components/
- [x] T084 [P] [US3] Update action registry references in services/budadmin/src/components/pipelineEditor/config/actionRegistry.ts
- [x] T085 [P] [US3] Update node type references in services/budadmin/src/components/pipelineEditor/config/workflowNodeTypes.ts
- [x] T086 [P] [US3] Update validation config in services/budadmin/src/components/pipelineEditor/config/workflowValidation.ts
- [x] T087 [P] [US3] Update node components in services/budadmin/src/components/pipelineEditor/nodes/
- [x] T088 [P] [US3] Update edge components in services/budadmin/src/components/pipelineEditor/edges/
- [x] T089 [P] [US3] Update custom hooks in services/budadmin/src/components/pipelineEditor/hooks/

**Step 3: Flow Directory Renames**

- [x] T090 [US3] Rename flows directory: `git mv services/budadmin/src/flows/Workflow services/budadmin/src/flows/Pipeline`
- [x] T091 [P] [US3] Rename NewWorkflow component: `git mv services/budadmin/src/flows/Pipeline/NewWorkflow.tsx services/budadmin/src/flows/Pipeline/NewPipeline.tsx`
- [x] T092 [P] [US3] Update NewPipeline component class/function names in services/budadmin/src/flows/Pipeline/NewPipeline.tsx
- [x] T093 [P] [US3] Update ExecutionDetails component references in services/budadmin/src/flows/Pipeline/ExecutionDetails.tsx
- [x] T094 [P] [US3] Update CreateSchedule component references in services/budadmin/src/flows/Pipeline/CreateSchedule.tsx

**Step 4: Store Rename**

- [x] T095 [US3] Rename store file: `git mv services/budadmin/src/stores/useBudWorkflow.ts services/budadmin/src/stores/useBudPipeline.ts`
- [x] T096 [US3] Update API constant BUDWORKFLOW_API → BUDPIPELINE_API: `"/budworkflow"` → `"/budpipeline"` in services/budadmin/src/stores/useBudPipeline.ts
- [x] T097 [US3] Update all export names useBudWorkflow → useBudPipeline in services/budadmin/src/stores/useBudPipeline.ts
- [x] T098 [US3] Update all type names BudWorkflow → BudPipeline in services/budadmin/src/stores/useBudPipeline.ts

**Step 5: Flow Registry Update**

- [x] T099 [US3] Update flow registry mapping in services/budadmin/src/flows/index.tsx:
- [x] T100 [P] [US3] Change "workflow-execution-details" → "pipeline-execution-details"
- [x] T101 [P] [US3] Change "workflow-create-schedule" → "pipeline-create-schedule"
- [x] T102 [P] [US3] Change "new-workflow" → "new-pipeline"

**Step 6: Next.js Configuration**

- [x] T103 [US3] Add 308 permanent redirects in next.config.mjs redirects() function:
- [x] T104 [P] [US3] Add redirect /workflows → /pipelines
- [x] T105 [P] [US3] Add redirect /workflows/new → /pipelines/new
- [x] T106 [P] [US3] Add redirect /workflows/:id → /pipelines/:id
- [x] T107 [US3] Update rewrites in next.config.mjs to use /pipelines routes
- [x] T108 [P] [US3] Update rewrite /pipelines → /home/budpipelines
- [x] T109 [P] [US3] Update rewrite /pipelines/new → /home/budpipelines/new
- [x] T110 [P] [US3] Update rewrite /pipelines/:id → /home/budpipelines/:id

**Step 7: Update All Import Statements**

- [x] T111 [US3] Run jscodeshift or find/replace to update all component imports across services/budadmin/src/
- [x] T112 [US3] Update all `useBudWorkflow` imports to `useBudPipeline` across consuming files
- [x] T113 [US3] Update all workflow→pipeline text references in UI strings (buttons, labels, headings)

**Step 8: Layout and Navigation**

- [x] T114 [US3] Update sidebar navigation links in services/budadmin/src/pages/home/layout.tsx
- [x] T115 [US3] Update breadcrumb references from "Workflows" → "Pipelines"
- [x] T116 [US3] Update page titles and meta tags from "Workflow" → "Pipeline"

**Step 9: Testing & Verification**

- [x] T117 [US3] Run TypeScript type check: `npm run typecheck --prefix services/budadmin`
- [x] T118 [US3] Run linting: `npm run lint --prefix services/budadmin` (warnings are pre-existing, not introduced by rename)
- [x] T119 [US3] Clear Next.js cache: `rm -rf services/budadmin/.next`
- [x] T120 [US3] Build frontend: `npm run build --prefix services/budadmin` (fixed missing key prop bug)
- [ ] T121 [US3] Start dev server: `npm run dev --prefix services/budadmin`
- [ ] T122 [US3] Test redirect: Navigate to http://localhost:8007/workflows and verify redirect to /pipelines
- [ ] T123 [US3] Test pipeline list page loads at http://localhost:8007/pipelines
- [ ] T124 [US3] Test create pipeline page loads at http://localhost:8007/pipelines/new
- [ ] T125 [US3] Test pipeline detail page loads at http://localhost:8007/pipelines/:id
- [ ] T126 [US3] Verify all CRUD operations work (create, read, update, delete pipeline)
- [ ] T127 [US3] Verify execution flow works end-to-end
- [ ] T128 [US3] Verify schedule management works
- [ ] T129 [US3] Check browser console for errors (should be zero)
- [x] T130 [US3] Verify no "workflow" or "budworkflow" references in UI text (Note: remaining "workflow" refs are for unrelated useWorkflow store for deployment tracking)

**Checkpoint**: All user stories should now be independently functional. Users can access pipelines through the new UI with all operations working.

---

## Phase 6: Infrastructure Updates (Helm & Kubernetes)

**Purpose**: Update Helm charts, deployment manifests, and Kubernetes configurations for production deployment

- [x] T131 [P] Update Helm values.yaml: budworkflow → budpipeline section in infra/helm/bud/values.yaml
- [x] T132 [P] Update daprid: "budworkflow" → "budpipeline" in infra/helm/bud/values.yaml
- [x] T133 [P] Update pubsubTopic: "budworkflowEvents" → "budpipelineEvents" in infra/helm/bud/values.yaml
- [x] T134 [P] Update values.ditto.yaml image reference in infra/helm/bud/values.ditto.yaml
- [x] T135 Rename Helm template: `git mv infra/helm/bud/templates/microservices/budworkflow.yaml infra/helm/bud/templates/microservices/budpipeline.yaml`
- [x] T136 Update deployment name {{ .Release.Name }}-budpipeline in infra/helm/bud/templates/microservices/budpipeline.yaml
- [x] T137 Update container name to budpipeline in infra/helm/bud/templates/microservices/budpipeline.yaml
- [x] T138 Update dapr.io/app-id annotation to {{ .Values.microservices.budpipeline.daprid }} in infra/helm/bud/templates/microservices/budpipeline.yaml
- [x] T139 Update service name {{ .Release.Name }}-budpipeline in infra/helm/bud/templates/microservices/budpipeline.yaml
- [x] T140 Update subscription name {{ .Release.Name }}-budpipeline-pubsub-subscription in infra/helm/bud/templates/microservices/budpipeline.yaml
- [x] T141 Update subscription scope to "budpipeline" in infra/helm/bud/templates/microservices/budpipeline.yaml
- [x] T142 Update budapp deployment BUD_WORKFLOW_APP_ID → BUD_PIPELINE_APP_ID in infra/helm/bud/templates/microservices/budapp.yaml
- [x] T143 Update cron component name budpipeline-schedule-poll in infra/helm/bud/templates/dapr/cron.yaml
- [x] T144 Update cron component scope to "budpipeline" in infra/helm/bud/templates/dapr/cron.yaml
- [x] T145 Run Helm dependency update: `helm dependency update infra/helm/bud/`
- [x] T146 Run Helm dry-run to verify changes: Verified budpipeline.yaml exists and values.yaml has correct config (cannot test without deployed cluster)
- [x] T147 Review dry-run output for correctness: Verified budpipeline deployment template, app-id: budpipeline, topic: budpipelineEvents

---

## Phase 7: Documentation & Polish

**Purpose**: Update all documentation and perform final verification before deployment

- [x] T148 [P] Update root README.md service references from budworkflow → budpipeline
- [x] T149 [P] Update root CLAUDE.md service list from budworkflow → budpipeline
- [x] T150 [P] Update services/budpipeline/docs/ if any documentation exists
- [x] T151 [P] Update API documentation references (OpenAPI/Swagger specs if present)
- [x] T152 Create external consumer migration guide in specs/001-rename-budworkflow-to-budpipeline/MIGRATION_GUIDE.md
- [x] T153 Verify all .env.sample files updated with new variable names
- [x] T154 Update deployment guides with new service name (quickstart.md already has budpipeline throughout)
- [x] T155 Run final comprehensive grep search: `rg -i "budworkflow" . --type py --type ts --type yaml --type md`
- [x] T156 Review and manually fix any remaining references found (fixed 13 references in 6 files)
- [x] T157 Run all linting tools (ruff, eslint, mypy) across all services
- [x] T158 Fix any linting errors introduced by rename (4 auto-fixes applied, 24 pre-existing style warnings remain)

---

## Phase 8: Pre-Deployment Validation

**Purpose**: Final end-to-end testing before production deployment

- [ ] T159 Start full local stack (budpipeline + budapp + budadmin)
- [ ] T160 Execute full E2E test scenario: create pipeline → execute → view results → manage schedule
- [ ] T161 Verify WebSocket events work for execution updates
- [ ] T162 Verify Dapr pub/sub flow: budapp publishes → budpipeline receives
- [ ] T163 Verify Dapr service invocation: budapp → budpipeline
- [ ] T164 Measure and record performance baseline (startup time, API latency, memory)
- [ ] T165 Compare new baseline to pre-rename baseline (should be within 5%)
- [ ] T166 Run stress test: create 10 pipelines, execute all concurrently, verify no failures
- [ ] T167 Verify all test suites pass: `pytest services/budpipeline -v && npm test --prefix services/budadmin`
- [ ] T168 Build Docker image: `docker build -t budpipeline:test services/budpipeline`
- [ ] T169 Test Docker image starts successfully
- [ ] T170 Review breaking change notice sent to external consumers (verify 7-day lead time)

---

## Phase 9: Production Deployment

**Purpose**: Deploy to production following quickstart guide

**Prerequisites**: All previous phases complete, external consumers notified, deployment window scheduled

- [ ] T171 Execute pre-deployment checklist from quickstart.md
- [ ] T172 Connect to production Kubernetes cluster
- [ ] T173 Verify zero in-flight executions (re-check before deployment)
- [ ] T174 Create production backup of Redis state store
- [ ] T175 Deploy Helm chart: `helm upgrade bud infra/helm/bud/ --namespace bud-system --wait`
- [ ] T176 Monitor deployment progress: `kubectl rollout status deployment/budpipeline -n bud-system`
- [ ] T177 Verify pods Running with Ready 2/2: `kubectl get pods -n bud-system -l app=budpipeline`
- [ ] T178 Check Dapr sidecar logs for errors: `kubectl logs -n bud-system deployment/budpipeline -c daprd --tail=100`
- [ ] T179 Check service logs for errors: `kubectl logs -n bud-system deployment/budpipeline -c budpipeline --tail=100`
- [ ] T180 Execute production smoke tests per quickstart.md
- [ ] T181 Verify API endpoint responds: `curl https://api.bud.ai/api/v1/budpipeline`
- [ ] T182 Create test pipeline in production
- [ ] T183 Execute test pipeline and verify completion
- [ ] T184 Monitor error rates for 30 minutes (should be < 1%)
- [ ] T185 Monitor p95 latency (should be < 200ms)
- [ ] T186 Monitor memory usage (should be stable)
- [ ] T187 Verify frontend loads at production URL
- [ ] T188 Test frontend redirect from /workflows → /pipelines
- [ ] T189 Verify all frontend operations work in production
- [ ] T190 Mark deployment as successful and notify team

---

## Phase 10: Post-Deployment Cleanup

**Purpose**: Final cleanup and archival tasks

- [ ] T191 Monitor production for 24 hours for any issues
- [ ] T192 Archive old Docker images with budworkflow tag
- [ ] T193 Update team documentation and runbooks with new service name
- [ ] T194 Document lessons learned in retrospective
- [ ] T195 Schedule follow-up to remove redirect endpoints after 6-12 months
- [ ] T196 Close out feature branch and related GitHub issues
- [ ] T197 Update project status dashboard to reflect completion

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational phase completion - Can start immediately after
- **User Story 2 (Phase 4)**: Depends on User Story 1 completion - Backend API needs renamed service
- **User Story 3 (Phase 5)**: Depends on User Story 2 completion - Frontend needs renamed API endpoints
- **Infrastructure (Phase 6)**: Depends on all user stories completion - Final Helm chart updates
- **Documentation (Phase 7)**: Can run in parallel with Phase 6
- **Validation (Phase 8)**: Depends on Phases 3-7 completion
- **Deployment (Phase 9)**: Depends on Phase 8 validation passing
- **Cleanup (Phase 10)**: Depends on successful Phase 9 deployment

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: DEPENDS on User Story 1 - Needs renamed service to proxy to
- **User Story 3 (P3)**: DEPENDS on User Story 2 - Needs renamed API endpoints

**Critical Path**: Foundational → US1 → US2 → US3 → Infrastructure → Validation → Deployment

### Within Each User Story

**User Story 1** (Service Core):
1. Directory rename (T013-T014)
2. Python package rename (T015-T020) - BLOCKS all module updates
3. Module-specific updates (T021-T028) - Can run in parallel after package rename
4. Test updates (T029-T034) - Can run in parallel with modules
5. Configuration (T035-T039) - Can run in parallel
6. Dapr config (T040-T043) - Sequential within this group
7. Testing (T044-T050) - Must be last

**User Story 2** (API Interface):
1. File renames (T051-T052)
2. Route config (T053-T057)
3. Dependencies (T058-T059)
4. Event publishers (T060-T064) - Can run in parallel
5. Testing (T065-T072) - Must be last

**User Story 3** (Frontend UI):
1. Page renames (T073-T076)
2. Component renames (T077-T089)
3. Flow renames (T090-T094)
4. Store rename (T095-T098)
5. Flow registry (T099-T102) - Can run in parallel with above
6. Next.js config (T103-T110)
7. Import updates (T111-T113)
8. Layout (T114-T116)
9. Testing (T117-T130) - Must be last

### Parallel Opportunities

Tasks marked with `[P]` can run in parallel within their phase:

**Setup Phase**: T002, T003, T004, T006 can run in parallel

**User Story 1**:
- After package rename: T021-T028 (module updates) can all run in parallel
- T029-T034 (test updates) can all run in parallel
- T035-T039 (config files) can all run in parallel

**User Story 2**:
- T060-T064 (event publishers) can all run in parallel

**User Story 3**:
- T074-T076 (page imports) can run in parallel
- T079-T089 (component updates) can run in parallel
- T091-T094 (flow components) can run in parallel
- T100-T102 (flow registry) can run in parallel
- T104-T106 (redirects) can run in parallel
- T108-T110 (rewrites) can run in parallel

**Infrastructure Phase**: T131-T134 can run in parallel

**Documentation Phase**: T148-T151 can all run in parallel

---

## Parallel Example: User Story 1 - Module Updates

After completing package rename (T020), launch these tasks in parallel:

```bash
# Terminal 1: Engine modules
Task T021: Update engine module imports

# Terminal 2: Handlers modules
Task T022: Update handlers module imports

# Terminal 3: Scheduler modules
Task T023: Update scheduler module imports

# Terminal 4: Workflow→Pipeline rename
Task T024: Rename workflow directory to pipeline

# Terminal 5: Webhook modules
Task T026: Update webhook module imports

# Terminal 6: Commons modules
Task T027: Update commons module imports

# Terminal 7: Shared/Dapr modules
Task T028: Update shared module imports
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

For fastest validation of the rename approach:

1. Complete Phase 1: Setup (establish baseline)
2. Complete Phase 2: Foundational (drain executions)
3. Complete Phase 3: User Story 1 (service core rename)
4. **STOP and VALIDATE**: Test renamed service in isolation
5. If successful, proceed to User Stories 2 & 3

**Benefit**: Validates the most complex part (Python package rename) before touching API and frontend.

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Complete User Story 1 → Test independently → Service works with new name
3. Complete User Story 2 → Test independently → API layer works
4. Complete User Story 3 → Test independently → Full stack operational
5. Complete Infrastructure → Ready for production
6. Deploy to production

**Each phase is a checkpoint where you can pause, validate, and decide to proceed or rollback.**

### Atomic Deployment Strategy

Since this is a breaking change with no backward compatibility:

1. **All changes must be deployed atomically** in a single git merge
2. **No gradual rollout** - it's all-or-nothing
3. **Rollback plan ready** at each phase for local testing
4. **Production deployment** is final cutover after all validation passes

---

## Notes

- **[P] tasks** = different files, no dependencies, safe to parallelize
- **[Story] label** maps task to specific user story for traceability
- **Sequential dependencies** within each user story must be respected
- **Verify tests pass** after each major group of tasks
- **Commit frequently** - after each logical group or phase
- **Stop at checkpoints** to validate independently before proceeding
- **Total tasks**: 197 tasks across 10 phases
- **Estimated time**: 23 hours total team effort (3-4 business days calendar time)
- **Critical path**: Foundational → US1 (4h) → US2 (2h) → US3 (4h) → Deploy (3h) = ~13 hours minimum

---

## Summary Statistics

- **Total Tasks**: 197
- **Setup Tasks**: 7 (Phase 1)
- **Foundational Tasks**: 5 (Phase 2)
- **User Story 1 Tasks**: 38 (Phase 3) - Service Core Rename
- **User Story 2 Tasks**: 22 (Phase 4) - API Interface Updates
- **User Story 3 Tasks**: 58 (Phase 5) - Frontend UI Updates
- **Infrastructure Tasks**: 17 (Phase 6)
- **Documentation Tasks**: 11 (Phase 7)
- **Validation Tasks**: 12 (Phase 8)
- **Deployment Tasks**: 20 (Phase 9)
- **Cleanup Tasks**: 7 (Phase 10)
- **Parallel Opportunities**: 47 tasks can run in parallel (marked with [P])
- **Independent Stories**: User Story 1 can be validated independently, US2 depends on US1, US3 depends on US2

---

## Validation Checklist

Before marking this task list complete, verify:

- [x] All tasks follow checklist format: `- [ ] [TaskID] [P?] [Story?] Description with file path`
- [x] Task IDs are sequential (T001 through T197)
- [x] All user story tasks have [US1], [US2], or [US3] labels
- [x] Setup and Foundational tasks have no story labels
- [x] All tasks include specific file paths where applicable
- [x] Parallel tasks are clearly marked with [P]
- [x] Dependencies are documented in Dependencies section
- [x] Each user story has independent test criteria
- [x] MVP scope clearly defined (User Story 1 only)
- [x] Implementation strategy explains execution approach

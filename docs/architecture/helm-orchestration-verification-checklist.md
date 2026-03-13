# Helm Component & Pipeline Orchestration -- Verification Checklist

This document provides a comprehensive manual verification and end-to-end testing
checklist for the Helm component type and BudPipeline orchestration feature spanning
BudCluster, BudPipeline, BudUseCases, and BudAdmin.

---

## Pre-requisites

- [ ] All four services running: `budusecases`, `budcluster`, `budpipeline`, `budadmin`
- [ ] PostgreSQL databases migrated (`alembic upgrade head` in budusecases and budcluster)
- [ ] Dapr sidecars active for all services (verify via `dapr list`)
- [ ] Redis/Valkey state store available for Dapr pub/sub
- [ ] Environment variable `USE_PIPELINE_ORCHESTRATION=true` set in budusecases `.env`
- [ ] BudPipeline `helm_deploy` action plugin registered (check `pyproject.toml` entry point)
- [ ] Crypto keys generated for budcluster (`crypto-keys/rsa-private-key.pem`, `crypto-keys/symmetric-key-256`)

---

## Phase A: BudCluster Verification

### A.1 Database Migration

- [ ] Run `alembic upgrade head` in budcluster
- [ ] Verify `helm_deploy` enum value added to `job_type_enum` PostgreSQL type
  - SQL check: `SELECT enum_range(NULL::job_type_enum);` should include `helm_deploy`
- [ ] Migration file: `budcluster/alembic/versions/2026_02_06_add_helm_deploy_enum.py`

### A.2 Job Enums and Model

- [ ] `JobType.HELM_DEPLOY` enum value exists with value `"helm_deploy"`
  - File: `budcluster/jobs/enums.py`
- [ ] `Job` model includes all required fields: `id`, `name`, `job_type`, `status`, `source`, `source_id`, `cluster_id`, `namespace`, `priority`, `config` (JSONB), `metadata_` (JSONB), `error_message`, `retry_count`, `timeout_seconds`, `started_at`, `completed_at`
  - File: `budcluster/jobs/models.py`
- [ ] `JobCRUD` inherits from `CRUDMixin` and has `__model__ = Job`

### A.3 Helm Deployment Playbook

- [ ] Verify `deploy_helm_chart.yaml` exists in playbooks directory
  - File: `budcluster/playbooks/deploy_helm_chart.yaml`
- [ ] Playbook registered in `budcluster/playbooks/__init__.py` as `DEPLOY_HELM_CHART`
- [ ] Playbook accepts `extra_vars`: `helm_release_name`, `helm_chart_ref`, `helm_chart_version`, `namespace`, `values`, `helm_wait`, `create_namespace`
- [ ] Playbook gathers deployed Service resources after install

### A.4 KubernetesHandler.deploy_helm_chart()

- [ ] Method exists on `KubernetesHandler` class
  - File: `budcluster/cluster_ops/kubernetes.py`
- [ ] Accepts parameters: `release_name`, `chart_ref`, `namespace`, `values`, `chart_version`, `delete_on_failure`
- [ ] On success: returns `("successful", result_info)` with `release_name`, `namespace`, `services` list
- [ ] On failure with `delete_on_failure=True`: calls `delete_namespace()` and raises `KubernetesException`
- [ ] On failure with `delete_on_failure=False`: returns `("failed", result_info)` without raising

### A.5 Job Execution Endpoint

- [ ] `POST /jobs/{job_id}/execute` endpoint exists, returns HTTP 202
  - File: `budcluster/jobs/routes.py`
- [ ] HELM_DEPLOY job with valid config: transitions to RUNNING, dispatches background task
- [ ] Non-HELM_DEPLOY job type: returns HTTP 400 "does not support direct execution"
- [ ] HELM_DEPLOY job with invalid config (e.g., `ftp://` chart_ref): returns HTTP 400 "Invalid Helm config"

### A.6 Helm Config Security Validator

- [ ] `validate_helm_config()` function exists
  - File: `budcluster/jobs/validators.py`
- [ ] Valid OCI chart reference (`oci://...`): returns empty errors list
- [ ] Valid HTTPS chart reference (`https://...`): returns empty errors list
- [ ] Invalid protocol (`ftp://...`): returns error "does not match any allowed pattern"
- [ ] Blocked top-level key (`hostNetwork: true`): returns error mentioning `hostNetwork`
- [ ] Blocked nested key (`containers.main.securityContext.privileged: true`): returns error with full dotted path
- [ ] Missing `chart_ref`: returns error "chart_ref is required"

### A.7 Job Event Publisher

- [ ] `publish_job_event()` function exists
  - File: `budcluster/jobs/events.py`
- [ ] Publishes to topic `budpipelineEvents` (constant `PIPELINE_EVENTS_TOPIC`)
- [ ] Event payload includes: `job_id`, `job_type`, `source`, `source_id`, `status`, and optional `error`
- [ ] Called on HELM_DEPLOY success with status `SUCCEEDED`
- [ ] Called on HELM_DEPLOY failure with status `FAILED` and error message

---

## Phase B: BudPipeline Verification

### B.1 Action Registration

- [ ] `helm_deploy` action registered in `pyproject.toml` under `[project.entry-points."budpipeline.actions"]`
- [ ] Action appears in BudPipeline's registered actions on startup
- [ ] Action metadata: `type=helm_deploy`, `execution_mode=EVENT_DRIVEN`
  - File: `budpipeline/actions/helm_deploy/executor.py` (or similar)

### B.2 Action Execution

- [ ] Create pipeline with `helm_deploy` step: verify execution starts
- [ ] Step creates job in BudCluster via Dapr service invocation to `budcluster`
- [ ] Step enters `awaiting_event` state after job creation
- [ ] On receiving job completion event from BudCluster via `budpipelineEvents` topic: step completes
- [ ] On receiving job failure event: step fails with error message

### B.3 Callback Topic

- [ ] BudPipeline publishes step/execution progress events to the topic specified in `callback_topics` of the pipeline DAG
- [ ] For BudUseCases deployments, callback topic is `budusecasesEvents`

---

## Phase C: BudUseCases Verification

### C.1 Template with Helm Components

- [ ] `helm` is a valid component type in template definitions
- [ ] `POST /api/v1/templates` with helm component (including `chart.ref`, `chart.version`, `chart.values`): returns 201
- [ ] `GET /api/v1/templates`: helm component visible with chart configuration
- [ ] Helm component validation requires `chart.ref` to be present
  - File: `budusecases/templates/schemas.py`

### C.2 HelmChartConfig Schema

- [ ] `HelmChartConfig` Pydantic model exists with fields: `ref` (required), `version` (optional), `values` (optional dict), `release_name` (optional)
  - File: `budusecases/templates/schemas.py`
- [ ] Template component `chart` field accepts `HelmChartConfig` instances

### C.3 Deployment Creation

- [ ] `POST /api/v1/deployments` with template containing helm + model components: returns 201
- [ ] `POST /api/v1/deployments/{id}/start`: deployment starts via BudPipeline
- [ ] `pipeline_execution_id` stored on the `UseCaseDeployment` model after pipeline creation
  - File: `budusecases/deployments/models.py`

### C.4 DAG Builder

- [ ] `build_deployment_dag()` function exists
  - File: `budusecases/deployments/dag_builder.py`
- [ ] Model-only template: DAG uses `deployment_create` action type for model steps
- [ ] Helm-only template: DAG uses `helm_deploy` action type for helm steps
- [ ] Mixed template: correct action types assigned per component type
- [ ] Dependency chain: deploy steps depend on `cluster_health` check; `notify_complete` depends on all deploy steps
- [ ] Jinja2 step references preserved in helm chart values (e.g., `{{ steps.deploy_llm.outputs.endpoint_url }}`)
- [ ] `callback_topics` includes `budusecasesEvents`

### C.5 BudPipeline Client

- [ ] `BudPipelineClient` class exists with Dapr service invocation
  - File: `budusecases/clients/budpipeline/client.py`
- [ ] Methods: `create_execution()`, `get_execution()`, `get_execution_progress()`, `cancel_execution()`
- [ ] Error handling: `BudPipelineError`, `BudPipelineConnectionError`, `BudPipelineTimeoutError`, `ExecutionNotFoundError`

### C.6 Pipeline Event Handling

- [ ] `GET /dapr/subscribe` returns subscription config for `budusecasesEvents` topic on pubsub `pubsub`, routed to `/budusecases-events`
  - File: `budusecases/main.py`
- [ ] `POST /budusecases-events` extracts CloudEvent `data` and delegates to `handle_pipeline_event()`
- [ ] `handle_pipeline_event()` function handles the following event types:
  - File: `budusecases/events/pipeline_listener.py`
  - `step_completed`: updates matched component deployment to `RUNNING`; stores `job_id` and `endpoint_url` from outputs if present
  - `step_failed`: updates matched component deployment to `FAILED` with error message (checks both `error_message` and `error` keys)
  - `workflow_completed`: updates deployment status to `RUNNING`
  - `workflow_failed`: updates deployment status to `FAILED` with error message
  - `execution_cancelled`: updates deployment to `STOPPED`; sets non-terminal components (`DEPLOYING`, `PENDING`) to `STOPPED`; skips terminal components (`RUNNING`, `FAILED`, `STOPPED`)
- [ ] Unknown event types are silently ignored (no crash)
- [ ] Missing `execution_id` is handled gracefully (early return, no DB query)
- [ ] Unknown `execution_id` (no matching deployment) is handled gracefully
- [ ] Non-deploy steps (e.g., `cluster_health`, `notify_complete`) do not update component status
- [ ] Invalid `job_id` (non-UUID) in step outputs logs warning but does not crash

### C.7 Stop Deployment

- [ ] `POST /api/v1/deployments/{id}/stop` with pipeline deployment: calls `cancel_execution()` on BudPipeline client
- [ ] Deployment status set to `STOPPED`
- [ ] Non-terminal component deployments set to `STOPPED`

### C.8 Status Sync

- [ ] `POST /api/v1/deployments/{id}/sync` with `pipeline_execution_id`: uses pipeline path (calls `get_execution_progress()`)
- [ ] `POST /api/v1/deployments/{id}/sync` without `pipeline_execution_id`: uses legacy BudCluster path

### C.9 Backward Compatibility

- [ ] Set `USE_PIPELINE_ORCHESTRATION=false`: `start_deployment` uses legacy direct-job path via BudCluster
- [ ] Set `USE_PIPELINE_ORCHESTRATION=true` (default): `start_deployment` uses BudPipeline orchestration

---

## Phase D: BudAdmin Frontend Verification

### D.1 Template Creation

- [ ] Open "Create Template" drawer in BudAdmin UI
- [ ] Add a helm component: verify chart fields appear (ref, version, values)
  - File: `budadmin/src/flows/UseCases/HelmChartFields.tsx`
- [ ] Add a model component: verify standard fields appear
  - File: `budadmin/src/flows/UseCases/ComponentFormFields.tsx`
- [ ] Submit template with both helm and model components: verify template created successfully

### D.2 Template Detail View

- [ ] Select a template with helm components: open detail drawer
  - File: `budadmin/src/flows/UseCases/TemplateDetail.tsx`
- [ ] Verify helm components show "Helm Chart" badge in cyan color
- [ ] Verify chart reference and version displayed
- [ ] Verify collapsible JSON values section works (expand/collapse)

### D.3 Deployment Progress

- [ ] Start a deployment: verify progress component renders
  - File: `budadmin/src/flows/UseCases/DeploymentProgress.tsx`
- [ ] Verify component status updates in real-time (polling)
- [ ] Verify progress bar updates as components complete
- [ ] Verify "Stop" button visible during `DEPLOYING` state

### D.4 API Integration

- [ ] BudUseCases API client includes helm component types
  - File: `budadmin/src/pages/api/budusecases.ts`
- [ ] TypeScript types include `HelmChartConfig` with `ref`, `version`, `values`, `release_name`

---

## Phase E: Integration & Edge Cases

### E.1 Full End-to-End Flow

- [ ] Create template with multiple components: e.g., `qdrant` (vector_db) + `llama-3` (model) + `agent-runtime` (helm)
  - Reference: `templates/agent-rag.yaml`
- [ ] Create deployment from template on a test cluster
- [ ] Start deployment: verify pipeline created with correct DAG
- [ ] Verify step sequence: `cluster_health` -> deploy steps (parallel or sequential as per DAG) -> `notify_complete`
- [ ] Wait for completion: verify all components reach `RUNNING` status
- [ ] Verify deployment status transitions: `PENDING` -> `DEPLOYING` -> `RUNNING`
- [ ] Check endpoints accessible (if applicable)

### E.2 Failure Recovery

- [ ] Deploy with invalid chart ref (e.g., `ftp://bad-protocol/chart`): verify graceful failure
  - Job created but execution fails at validation
  - Step fails, component status set to `FAILED` with error message
- [ ] Deploy with insufficient resources: verify failure with clear error message
- [ ] Stop mid-deployment: verify clean cancellation via `cancel_execution()`
  - Deployment status -> `STOPPED`
  - In-flight components -> `STOPPED`
  - Already completed components remain `RUNNING`
  - Already failed components remain `FAILED`

### E.3 Backward Compatibility

- [ ] Set `USE_PIPELINE_ORCHESTRATION=false`: legacy direct-job path works for model-only templates
- [ ] Model-only templates work correctly through pipeline path when `USE_PIPELINE_ORCHESTRATION=true`
- [ ] Existing deployments without `pipeline_execution_id` sync via legacy BudCluster path
- [ ] New pipeline-based deployments with `pipeline_execution_id` sync via BudPipeline

### E.4 Security Validation

- [ ] Helm chart config with `hostNetwork: true` in values: rejected before job creation
- [ ] Helm chart config with `privileged: true` nested in security context: rejected with full path reported
- [ ] Helm chart config with valid OCI reference and clean values: accepted

### E.5 Event Flow Verification

- [ ] BudCluster publishes job completion events to `budpipelineEvents` topic
- [ ] BudPipeline receives events and updates step status
- [ ] BudPipeline publishes step/workflow events to `budusecasesEvents` callback topic
- [ ] BudUseCases receives events on `/budusecases-events` and updates component/deployment status
- [ ] Full event chain: BudCluster -> BudPipeline -> BudUseCases (verified via logs)

---

## Automated Test Results Summary

| Test Suite | Service | File | Tests | Status |
|---|---|---|---|---|
| BudCluster Helm Deploy | budcluster | `tests/test_helm_deploy.py` | 12 | |
| BudCluster Job Enums | budcluster | `tests/test_job_enums.py` | 60 | |
| BudCluster Job Model | budcluster | `tests/test_job_model.py` | 38 | |
| BudCluster Job Schemas | budcluster | `tests/test_job_schemas.py` | 63 | |
| BudCluster Job CRUD | budcluster | `tests/test_job_crud.py` | 42 | |
| BudCluster Job Services | budcluster | `tests/test_job_services.py` | 37 | |
| BudCluster Job Routes | budcluster | `tests/test_job_routes.py` | 38 | |
| BudPipeline Helm Action | budpipeline | `tests/test_helm_deploy_action.py` | 12 | |
| Helm Schema Validation | budusecases | `tests/test_helm_schema.py` | 10 | |
| Helm Security Validation | budusecases | `tests/test_helm_security.py` | 11 | |
| DAG Builder | budusecases | `tests/test_dag_builder.py` | 13 | |
| Pipeline Event Listener | budusecases | `tests/test_pipeline_listener.py` | 25 | |
| Model-Only Pipeline | budusecases | `tests/test_integration_model_pipeline.py` | 19 | |
| Mixed Deployment | budusecases | `tests/test_integration_mixed_deployment.py` | 19 | |
| Failure & Stop | budusecases | `tests/test_integration_failure_stop.py` | 21 | |
| **TOTAL (feature-specific)** | | | **142** | |
| **TOTAL (incl. job infra)** | | | **420** | |

### Running the Tests

```bash
# BudCluster -- Helm deploy tests
cd services/budcluster && pytest tests/test_helm_deploy.py -v

# BudCluster -- Full job subsystem tests
cd services/budcluster && pytest tests/test_job_enums.py tests/test_job_model.py \
    tests/test_job_schemas.py tests/test_job_crud.py tests/test_job_services.py \
    tests/test_job_routes.py tests/test_helm_deploy.py -v

# BudPipeline -- Helm deploy action
cd services/budpipeline && pytest tests/test_helm_deploy_action.py -v

# BudUseCases -- Helm and pipeline tests
cd services/budusecases && pytest tests/test_helm_schema.py tests/test_helm_security.py \
    tests/test_dag_builder.py tests/test_pipeline_listener.py -v

# BudUseCases -- Integration tests
cd services/budusecases && pytest tests/test_integration_model_pipeline.py \
    tests/test_integration_mixed_deployment.py tests/test_integration_failure_stop.py -v

# All feature tests at once (from repo root)
pytest services/budcluster/tests/test_helm_deploy.py \
       services/budpipeline/tests/test_helm_deploy_action.py \
       services/budusecases/tests/test_helm_schema.py \
       services/budusecases/tests/test_helm_security.py \
       services/budusecases/tests/test_dag_builder.py \
       services/budusecases/tests/test_pipeline_listener.py \
       services/budusecases/tests/test_integration_model_pipeline.py \
       services/budusecases/tests/test_integration_mixed_deployment.py \
       services/budusecases/tests/test_integration_failure_stop.py -v
```

---

## Key File Reference

| Area | File | Purpose |
|---|---|---|
| Helm enum | `services/budcluster/budcluster/jobs/enums.py` | `JobType.HELM_DEPLOY` |
| Helm migration | `services/budcluster/budcluster/alembic/versions/2026_02_06_add_helm_deploy_enum.py` | Add `helm_deploy` to PostgreSQL enum |
| Ansible playbook | `services/budcluster/budcluster/playbooks/deploy_helm_chart.yaml` | Helm chart install/upgrade via Ansible |
| K8s handler | `services/budcluster/budcluster/cluster_ops/kubernetes.py` | `deploy_helm_chart()` method |
| Job routes | `services/budcluster/budcluster/jobs/routes.py` | `POST /{job_id}/execute` |
| Security validator | `services/budcluster/budcluster/jobs/validators.py` | `validate_helm_config()` |
| Event publisher | `services/budcluster/budcluster/jobs/events.py` | `publish_job_event()` to `budpipelineEvents` |
| Pipeline action | `services/budpipeline/` (helm_deploy action plugin) | `helm_deploy` execution in BudPipeline |
| DAG builder | `services/budusecases/budusecases/deployments/dag_builder.py` | `build_deployment_dag()` |
| Pipeline listener | `services/budusecases/budusecases/events/pipeline_listener.py` | `handle_pipeline_event()` |
| BudPipeline client | `services/budusecases/budusecases/clients/budpipeline/client.py` | Dapr service invocation to BudPipeline |
| BudCluster client | `services/budusecases/budusecases/clients/budcluster/client.py` | Dapr service invocation to BudCluster |
| Dapr subscribe | `services/budusecases/budusecases/main.py` | `/dapr/subscribe` and `/budusecases-events` |
| Deployment service | `services/budusecases/budusecases/deployments/services.py` | `start_deployment()` with pipeline toggle |
| Config flag | `services/budusecases/budusecases/commons/config.py` | `use_pipeline_orchestration` flag |
| Helm chart fields | `services/budadmin/src/flows/UseCases/HelmChartFields.tsx` | React form for helm chart config |
| Template detail | `services/budadmin/src/flows/UseCases/TemplateDetail.tsx` | Helm badge and chart display |
| Deployment progress | `services/budadmin/src/flows/UseCases/DeploymentProgress.tsx` | Real-time deployment tracking |
| API types | `services/budadmin/src/pages/api/budusecases.ts` | TypeScript API client and types |
| Example template | `services/budusecases/templates/agent-rag.yaml` | Agent RAG template with helm components |

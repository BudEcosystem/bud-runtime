# Plan: Helm Component Type + Pipeline Orchestration for BudUseCases

> **Document Version:** 1.0
> **Date:** 2026-02-06
> **Status:** Draft
> **Author:** AI-assisted
> **Dependencies:**
> - [Implementation Phase Plan](./implementation-phase-plan.md)
> - [Job Scheduling & Orchestration Architecture](./job-scheduling-orchestration.md)
> - BudPipeline SPEC.md
> - BudCluster Jobs system (Phase 1 deliverable)

---

## Executive Summary

This plan adds two capabilities to the Bud AI Foundry platform:

1. **`type: helm` components** in use case templates — allowing arbitrary Helm charts (agent runtimes, tool servers, custom services) to be deployed as part of a use case
2. **Pipeline-based orchestration** — replacing the manual poll-based status sync with BudPipeline DAG execution for ordered, event-driven, monitored deployments

Together, these enable agent use cases where an LLM, vector DB, and custom agent runtime (Helm chart) are deployed in dependency order with real-time progress tracking and user notifications.

### Motivation

Current budusecases only supports `model` and `vector_db` component types. An agent use case requires:

| Component | Example | Current Support |
|-----------|---------|----------------|
| LLM | llama-3-8b via vLLM | Yes (`type: model`) |
| Vector DB | Qdrant | Partial (`type: vector_db`, no chart) |
| Agent Runtime | LangGraph/CrewAI server | **No** |
| Tool Server | Custom MCP/FastAPI service | **No** |
| Memory Store | Redis/Valkey | **No** |

Without `type: helm`, there is no way to deploy custom services. Without pipeline orchestration, there is no way to deploy components in order (vector_db before agent runtime), pass outputs between them (LLM endpoint URL into agent config), or notify users when deployment completes.

---

## Architecture Overview

```
User: POST /deployments {template: "agent-rag", components: {...}}
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│ BudUseCases                                             │
│  1. Resolve template + validate components              │
│  2. Create UseCaseDeployment + ComponentDeployment rows  │
│  3. Generate pipeline DAG from deployment_order          │
│  4. Submit DAG to BudPipeline                           │
│  5. Store pipeline_execution_id on deployment           │
│  6. Receive progress events via Dapr pub/sub            │
│  7. Update component/deployment status in DB            │
└──────────┬──────────────────────────────┬───────────────┘
           │ Dapr invoke                  │ Dapr pub/sub
           ▼                              ▲ (progress events)
┌──────────────────────┐      ┌───────────────────────────┐
│ BudPipeline          │      │ BudPipeline               │
│  DAG Execution:      │      │  Publishes to callback    │
│   step1: cluster_    │──────│  topic on each step       │
│          health      │      │  completion/failure       │
│   step2: deploy_     │      └───────────────────────────┘
│          vector_db   │
│   step3: deploy_llm  │
│   step4: helm_deploy │──── NEW action
│   step5: notify      │
└──────────┬───────────┘
           │ Dapr invoke
           ▼
┌──────────────────────┐
│ BudCluster           │
│  Jobs API:           │
│   - MODEL_DEPLOYMENT │
│   - VECTOR_DB_DEPLOY │
│   - HELM_DEPLOY ──── │──── NEW job type
│                      │
│  Execution:          │
│   - Ansible playbook │
│   - kubernetes.core. │
│     helm module      │
│   - Publish event on │
│     completion       │
└──────────────────────┘
```

---

## Phase Breakdown

| Phase | Scope | Services Changed | Estimated Effort |
|-------|-------|-----------------|-----------------|
| **Phase A** | BudCluster: `HELM_DEPLOY` job type + generic Helm playbook | budcluster | 3-4 days |
| **Phase B** | BudPipeline: `helm_deploy` action | budpipeline | 2-3 days |
| **Phase C** | BudUseCases: `type: helm` + DAG builder + event listener | budusecases | 4-5 days |
| **Phase D** | BudAdmin: UI for helm components + deployment progress | budadmin | 3-4 days |
| **Phase E** | Testing + integration | all | 2-3 days |

---

## Phase A: BudCluster — HELM_DEPLOY Job Type

### A.1 Add `HELM_DEPLOY` to Job Enums

**File:** `services/budcluster/budcluster/jobs/enums.py`

```python
class JobType(StrEnum):
    MODEL_DEPLOYMENT = "model_deployment"
    CUSTOM_JOB = "custom_job"
    FINE_TUNING = "fine_tuning"
    BATCH_INFERENCE = "batch_inference"
    USECASE_COMPONENT = "usecase_component"
    BENCHMARK = "benchmark"
    DATA_PIPELINE = "data_pipeline"
    HELM_DEPLOY = "helm_deploy"          # NEW
```

**File:** `services/budcluster/budcluster/jobs/constants.py`

```python
JOB_TYPE_TIMEOUTS: dict[JobType, int] = {
    # ... existing ...
    JobType.HELM_DEPLOY: 3600,  # 1 hour — configurable per-job via timeout_seconds
}
```

### A.2 Alembic Migration for New Enum Value

**File:** `services/budcluster/budcluster/alembic/versions/XXXX_add_helm_deploy_job_type.py`

```python
"""Add helm_deploy to job_type_enum."""

def upgrade():
    op.execute("ALTER TYPE job_type_enum ADD VALUE IF NOT EXISTS 'helm_deploy'")

def downgrade():
    # PostgreSQL doesn't support removing enum values; safe to leave
    pass
```

### A.3 Create Generic Helm Deployment Playbook

**File:** `services/budcluster/budcluster/playbooks/deploy_helm_chart.yaml`

This playbook handles deploying any Helm chart — local bundled charts or remote OCI/repo charts.

```yaml
---
- name: Deploy Generic Helm Chart
  hosts: localhost
  connection: local
  gather_facts: false

  vars_files:
    - vars/common.yaml

  vars:
    release_name: "{{ helm_release_name }}"
    chart_ref: "{{ helm_chart_ref }}"
    chart_version: "{{ helm_chart_version | default(omit) }}"
    target_namespace: "{{ namespace }}"
    helm_values: "{{ values | default({}) }}"
    wait_for_ready: "{{ helm_wait | default(true) }}"
    wait_timeout: "{{ helm_timeout | default('600s') }}"
    create_ns: "{{ create_namespace | default(true) }}"

  roles:
    - create_kubeconfig

  tasks:
    - name: Create namespace if needed
      kubernetes.core.k8s:
        kind: Namespace
        name: "{{ target_namespace }}"
        state: present
        kubeconfig: "{{ kubeconfig_path }}"
        validate_certs: "{{ validate_certs }}"
      when: create_ns | bool

    - name: Deploy Helm chart
      kubernetes.core.helm:
        release_name: "{{ release_name }}"
        chart_ref: "{{ chart_ref }}"
        chart_version: "{{ chart_version | default(omit) }}"
        release_namespace: "{{ target_namespace }}"
        create_namespace: "{{ create_ns | bool }}"
        kubeconfig: "{{ kubeconfig_path }}"
        validate_certs: "{{ validate_certs }}"
        wait: "{{ wait_for_ready | bool }}"
        timeout: "{{ wait_timeout }}"
        values: "{{ helm_values }}"
      register: helm_result
      failed_when: helm_result.failed

    - name: Gather deployed resources
      kubernetes.core.k8s_info:
        kind: Service
        namespace: "{{ target_namespace }}"
        label_selectors:
          - "app.kubernetes.io/instance={{ release_name }}"
        kubeconfig: "{{ kubeconfig_path }}"
        validate_certs: "{{ validate_certs }}"
      register: deployed_services
      when: not helm_result.failed
```

**Key design decisions:**
- `chart_ref` supports both local paths (`charts/my-chart`) and remote references (`oci://registry.example.com/charts/my-chart`, `https://charts.example.com/my-chart`)
- `chart_version` is optional — omitted for local charts
- `wait: true` by default — Helm waits for all resources to become ready
- `wait_timeout` configurable per deployment (default 10 min)
- Gathers deployed Service resources for endpoint discovery

### A.4 Add Playbook Mapping

**File:** `services/budcluster/budcluster/playbooks/__init__.py` (or wherever playbook names are mapped)

Add the new playbook to the playbook registry so `AnsibleExecutor` can resolve it:

```python
PLAYBOOK_MAP = {
    # ... existing ...
    "DEPLOY_HELM_CHART": "deploy_helm_chart.yaml",
}
```

### A.5 Add `deploy_helm_chart()` to KubernetesHandler

**File:** `services/budcluster/budcluster/cluster_ops/kubernetes.py`

```python
def deploy_helm_chart(
    self,
    release_name: str,
    chart_ref: str,
    namespace: str,
    values: dict,
    chart_version: str | None = None,
    wait: bool = True,
    timeout: str = "600s",
    create_namespace: bool = True,
    delete_on_failure: bool = True,
) -> tuple[str, dict]:
    """Deploy a generic Helm chart to the cluster.

    Args:
        release_name: Helm release name
        chart_ref: Chart reference (local path, OCI URL, or repo URL)
        namespace: Target Kubernetes namespace
        values: Helm values dict
        chart_version: Chart version (optional, for remote charts)
        wait: Wait for resources to be ready
        timeout: Helm wait timeout
        create_namespace: Create namespace if missing
        delete_on_failure: Delete namespace on failure

    Returns:
        Tuple of (status, result_info dict with services/endpoints)
    """
    extra_vars = {
        "kubeconfig_content": self.config,
        "helm_release_name": release_name,
        "helm_chart_ref": chart_ref,
        "namespace": namespace,
        "values": values,
        "helm_wait": wait,
        "helm_timeout": timeout,
        "create_namespace": create_namespace,
        "platform": self.platform,
    }
    if chart_version:
        extra_vars["helm_chart_version"] = chart_version

    result = self.ansible_executor.run_playbook(
        playbook="DEPLOY_HELM_CHART",
        extra_vars=extra_vars,
    )

    if result["status"] != "successful":
        if delete_on_failure:
            self.delete_namespace(namespace)
        raise KubernetesException(
            f"Failed to deploy Helm chart {chart_ref}: {result.get('message', 'Unknown error')}"
        )

    # Extract service endpoints from playbook output
    result_info = self._extract_helm_deploy_result(result, namespace)
    return result["status"], result_info
```

### A.6 Add Helm Deploy Workflow Activity

**File:** `services/budcluster/budcluster/deployment/workflows.py` (extend existing)

```python
@dapr_workflows.register_activity
@staticmethod
def deploy_helm_chart(ctx: wf.WorkflowActivityContext, deploy_request: str):
    """Deploy a generic Helm chart as a workflow activity."""
    request = json.loads(deploy_request)

    cluster_id = request["cluster_id"]
    cluster = ClusterService.get_cluster(cluster_id)
    config = decrypt_cluster_config(cluster.configuration)

    handler = KubernetesHandler(config=config, ingress_url=cluster.ingress_url)

    status, result_info = handler.deploy_helm_chart(
        release_name=request["release_name"],
        chart_ref=request["chart_ref"],
        namespace=request["namespace"],
        values=request.get("values", {}),
        chart_version=request.get("chart_version"),
        wait=request.get("wait", True),
        timeout=request.get("timeout", "600s"),
    )

    return json.dumps({
        "status": status,
        "namespace": request["namespace"],
        "release_name": request["release_name"],
        **result_info,
    })
```

### A.7 Add Helm Deploy Job Execution Route

**File:** `services/budcluster/budcluster/jobs/routes.py` (or new file `services/budcluster/budcluster/jobs/helm_handler.py`)

When a `HELM_DEPLOY` job is started, it needs to trigger the actual deployment and publish completion events.

```python
@job_router.post("/{job_id}/execute")
async def execute_job(job_id: UUID, db: AsyncSession = Depends(get_session)):
    """Execute a job based on its type. For HELM_DEPLOY, triggers Helm deployment."""
    job = await job_service.get_job(job_id)

    if job.job_type == JobType.HELM_DEPLOY:
        await job_service.start_job(job_id)
        config = job.config or {}

        try:
            cluster = await cluster_service.get_cluster(job.cluster_id)
            k8s_config = decrypt_cluster_config(cluster.configuration)
            handler = KubernetesHandler(config=k8s_config, ingress_url=cluster.ingress_url)

            status, result_info = handler.deploy_helm_chart(
                release_name=config["release_name"],
                chart_ref=config["chart_ref"],
                namespace=config.get("namespace", f"usecase-{job.source_id}"),
                values=config.get("values", {}),
                chart_version=config.get("chart_version"),
            )

            await job_service.complete_job(job_id)
            job = await job_service.get_job(job_id)

            # Publish completion event to budpipelineEvents topic
            await _publish_job_event(job, status="COMPLETED", result=result_info)

        except Exception as e:
            await job_service.fail_job(job_id, str(e))
            await _publish_job_event(job, status="FAILED", error=str(e))
            raise

    return job
```

### A.8 Add Event Publishing for Job Completion

**File:** `services/budcluster/budcluster/jobs/events.py` (new file)

```python
"""Publish job lifecycle events to Dapr pub/sub for pipeline integration."""

from dapr.clients import DaprClient

async def publish_job_event(
    job: Job,
    status: str,
    result: dict | None = None,
    error: str | None = None,
):
    """Publish job completion/failure event to budpipelineEvents topic."""
    event_data = {
        "type": "job_completed" if status == "COMPLETED" else "job_failed",
        "workflow_id": str(job.id),  # job_id used as correlation ID
        "payload": {
            "job_id": str(job.id),
            "job_type": job.job_type,
            "source": job.source,
            "source_id": str(job.source_id) if job.source_id else None,
            "status": status,
            "content": {
                "result": result or {},
                "status": status,
            },
        },
    }
    if error:
        event_data["payload"]["error"] = error

    with DaprClient() as client:
        client.publish_event(
            pubsub_name="pubsub",
            topic_name="budpipelineEvents",
            data=json.dumps(event_data),
            data_content_type="application/json",
        )
```

### A.9 Security: Chart Source Validation

**File:** `services/budcluster/budcluster/jobs/validators.py` (new file)

```python
"""Validation for Helm deployment job configs."""

import re

# Allowed chart source patterns
ALLOWED_CHART_PATTERNS = [
    r"^oci://[\w\-\.]+/[\w\-/]+$",           # OCI registry
    r"^https://[\w\-\.]+/[\w\-/]+$",          # HTTPS chart repo
    r"^charts/[\w\-]+$",                       # Local bundled charts
]

# Blocked Helm values keys (security)
BLOCKED_VALUES_KEYS = {
    "hostNetwork",
    "hostPID",
    "hostIPC",
    "privileged",
}


def validate_helm_config(config: dict) -> list[str]:
    """Validate Helm deploy job config for security."""
    errors = []

    chart_ref = config.get("chart_ref", "")
    if not any(re.match(p, chart_ref) for p in ALLOWED_CHART_PATTERNS):
        errors.append(f"Chart reference '{chart_ref}' does not match allowed patterns")

    values = config.get("values", {})
    _check_blocked_keys(values, "", errors)

    return errors


def _check_blocked_keys(obj: dict, path: str, errors: list[str]):
    """Recursively check for blocked security keys in values."""
    for key, value in obj.items():
        full_path = f"{path}.{key}" if path else key
        if key in BLOCKED_VALUES_KEYS:
            errors.append(f"Blocked security key in Helm values: {full_path}")
        if isinstance(value, dict):
            _check_blocked_keys(value, full_path, errors)
```

### A.10 Files Changed (Phase A Summary)

| File | Action | Description |
|------|--------|-------------|
| `budcluster/jobs/enums.py` | Modify | Add `HELM_DEPLOY` to `JobType` |
| `budcluster/jobs/constants.py` | Modify | Add timeout for `HELM_DEPLOY` |
| `budcluster/alembic/versions/XXXX_add_helm_deploy.py` | Create | Migration for enum value |
| `budcluster/playbooks/deploy_helm_chart.yaml` | Create | Generic Helm playbook |
| `budcluster/cluster_ops/kubernetes.py` | Modify | Add `deploy_helm_chart()` method |
| `budcluster/deployment/workflows.py` | Modify | Add `deploy_helm_chart` activity |
| `budcluster/jobs/routes.py` | Modify | Add `/execute` endpoint |
| `budcluster/jobs/events.py` | Create | Job event publisher |
| `budcluster/jobs/validators.py` | Create | Helm config validation |
| `tests/test_helm_deploy.py` | Create | Tests |

---

## Phase B: BudPipeline — `helm_deploy` Action

### B.1 Create the `helm_deploy` Action

**File:** `services/budpipeline/budpipeline/actions/deployment/helm_deploy.py`

```python
"""Action: Deploy a Helm chart via BudCluster."""

import structlog

from budpipeline.actions.base import (
    ActionContext,
    ActionMeta,
    ActionResult,
    BaseActionExecutor,
    EventAction,
    EventContext,
    EventResult,
    ExecutionMode,
    OutputDefinition,
    ParamDefinition,
    ParamType,
    StepStatus,
    register_action,
)
from budpipeline.commons.config import settings

logger = structlog.get_logger(__name__)


class HelmDeployExecutor(BaseActionExecutor):
    """Deploy a Helm chart to a Kubernetes cluster via BudCluster."""

    async def execute(self, context: ActionContext) -> ActionResult:
        cluster_id = context.params["cluster_id"]
        chart_ref = context.params["chart_ref"]
        release_name = context.params.get("release_name", f"uc-{context.execution_id[:8]}")
        namespace = context.params.get("namespace", f"usecase-{context.execution_id[:8]}")
        chart_version = context.params.get("chart_version")
        values = context.params.get("values", {})
        timeout = context.params.get("timeout", "600s")

        logger.info(
            "helm_deploy_starting",
            step_id=context.step_id,
            chart_ref=chart_ref,
            cluster_id=cluster_id,
            namespace=namespace,
        )

        # Create a HELM_DEPLOY job in BudCluster
        job_config = {
            "chart_ref": chart_ref,
            "release_name": release_name,
            "namespace": namespace,
            "values": values,
            "timeout": timeout,
        }
        if chart_version:
            job_config["chart_version"] = chart_version

        try:
            response = await context.invoke_service(
                app_id=settings.budcluster_app_id,
                method_path="job",
                http_method="POST",
                data={
                    "name": f"helm-{release_name}",
                    "job_type": "helm_deploy",
                    "source": "budpipeline",
                    "source_id": context.execution_id,
                    "cluster_id": cluster_id,
                    "config": job_config,
                    "metadata_": {
                        "step_id": context.step_id,
                        "chart_ref": chart_ref,
                    },
                },
                timeout_seconds=30,
            )
        except Exception as e:
            logger.exception("helm_deploy_create_job_error", error=str(e))
            return ActionResult(success=False, error=f"Failed to create Helm deploy job: {e}")

        job_id = response.get("id")

        # Trigger execution
        try:
            await context.invoke_service(
                app_id=settings.budcluster_app_id,
                method_path=f"job/{job_id}/execute",
                http_method="POST",
                timeout_seconds=10,
            )
        except Exception as e:
            logger.exception("helm_deploy_execute_error", error=str(e))
            return ActionResult(success=False, error=f"Failed to execute Helm deploy job: {e}")

        logger.info(
            "helm_deploy_awaiting",
            step_id=context.step_id,
            job_id=job_id,
        )

        # Wait for completion event from BudCluster
        return ActionResult(
            success=True,
            awaiting_event=True,
            external_workflow_id=str(job_id),
            timeout_seconds=context.timeout_seconds or 3600,
            outputs={
                "job_id": str(job_id),
                "status": "deploying",
                "namespace": namespace,
                "release_name": release_name,
            },
        )

    async def on_event(self, context: EventContext) -> EventResult:
        """Handle job completion event from BudCluster."""
        event_type = context.event_data.get("type", "")
        payload = context.event_data.get("payload", {})
        content = payload.get("content", {})
        status = content.get("status", payload.get("status", ""))

        logger.info(
            "helm_deploy_event_received",
            event_type=event_type,
            status=status,
            job_id=context.external_workflow_id,
        )

        if event_type == "job_completed" and status == "COMPLETED":
            result = content.get("result", {})
            return EventResult(
                action=EventAction.COMPLETE,
                status=StepStatus.COMPLETED,
                outputs={
                    "job_id": context.external_workflow_id,
                    "namespace": result.get("namespace", ""),
                    "release_name": result.get("release_name", ""),
                    "endpoint_url": result.get("endpoint_url", ""),
                    "services": result.get("services", []),
                    "status": "running",
                },
            )

        if event_type == "job_failed" or status == "FAILED":
            error = payload.get("error", "Helm deployment failed")
            return EventResult(
                action=EventAction.COMPLETE,
                status=StepStatus.FAILED,
                error=error,
            )

        # Ignore unrelated events
        return EventResult(action=EventAction.IGNORE)

    def validate_params(self, params: dict) -> list[str]:
        errors = []
        if not params.get("cluster_id"):
            errors.append("cluster_id is required")
        if not params.get("chart_ref"):
            errors.append("chart_ref is required")
        return errors


META = ActionMeta(
    type="helm_deploy",
    version="1.0.0",
    name="Deploy Helm Chart",
    category="Deployment",
    icon="box",
    color="#6366F1",  # Indigo
    description=(
        "Deploy any Helm chart to a Kubernetes cluster via BudCluster. "
        "Supports OCI registries, HTTPS chart repos, and local bundled charts. "
        "Event-driven: waits for BudCluster to report deployment completion."
    ),
    execution_mode=ExecutionMode.EVENT_DRIVEN,
    timeout_seconds=3600,  # 1 hour
    idempotent=False,
    required_services=["budcluster"],
    required_permissions=[],
    params=[
        ParamDefinition(
            name="cluster_id",
            label="Cluster",
            type=ParamType.CLUSTER_REF,
            description="Target cluster for deployment",
            required=True,
        ),
        ParamDefinition(
            name="chart_ref",
            label="Chart Reference",
            type=ParamType.STRING,
            description="Helm chart reference: OCI URL (oci://...), HTTPS repo URL, or local path (charts/...)",
            required=True,
        ),
        ParamDefinition(
            name="chart_version",
            label="Chart Version",
            type=ParamType.STRING,
            description="Chart version constraint (e.g., '1.2.0', '>=1.0.0'). Optional for local charts.",
            required=False,
        ),
        ParamDefinition(
            name="release_name",
            label="Release Name",
            type=ParamType.STRING,
            description="Helm release name. Auto-generated if omitted.",
            required=False,
        ),
        ParamDefinition(
            name="namespace",
            label="Namespace",
            type=ParamType.STRING,
            description="Kubernetes namespace. Auto-generated if omitted.",
            required=False,
        ),
        ParamDefinition(
            name="values",
            label="Helm Values",
            type=ParamType.JSON,
            description="Helm values dict to override chart defaults. Supports Jinja2 templates for step output references.",
            required=False,
        ),
        ParamDefinition(
            name="timeout",
            label="Deploy Timeout",
            type=ParamType.STRING,
            description="Helm wait timeout (e.g., '600s', '10m'). Default: 600s.",
            required=False,
        ),
    ],
    outputs=[
        OutputDefinition(
            name="job_id",
            type="string",
            description="BudCluster job ID for the Helm deployment",
        ),
        OutputDefinition(
            name="namespace",
            type="string",
            description="Kubernetes namespace where the chart was deployed",
        ),
        OutputDefinition(
            name="release_name",
            type="string",
            description="Helm release name",
        ),
        OutputDefinition(
            name="endpoint_url",
            type="string",
            description="Service endpoint URL if discoverable",
        ),
        OutputDefinition(
            name="services",
            type="array",
            description="List of Kubernetes Service names created by the chart",
        ),
    ],
)


@register_action(META)
class HelmDeployAction:
    """Deploy a Helm chart via BudCluster."""

    meta = META
    executor_class = HelmDeployExecutor
```

### B.2 Register Entry Point

**File:** `services/budpipeline/pyproject.toml`

```toml
[project.entry-points."budpipeline.actions"]
# ... existing entries ...
helm_deploy = "budpipeline.actions.deployment.helm_deploy:HelmDeployAction"
```

### B.3 Files Changed (Phase B Summary)

| File | Action | Description |
|------|--------|-------------|
| `budpipeline/actions/deployment/helm_deploy.py` | Create | `helm_deploy` action executor + meta |
| `budpipeline/pyproject.toml` | Modify | Register entry point |
| `tests/test_helm_deploy_action.py` | Create | Unit tests for action |

---

## Phase C: BudUseCases — `type: helm` + DAG Builder + Event Listener

### C.1 Add `helm` to Valid Component Types

**File:** `services/budusecases/budusecases/templates/services.py`

```python
VALID_COMPONENT_TYPES = {
    "model", "llm", "embedder", "reranker",
    "vector_db", "memory_store",
    "helm",  # NEW — arbitrary Helm chart components
}
```

### C.2 Extend Template Component Schema for Helm

**File:** `services/budusecases/budusecases/templates/schemas.py`

Add helm-specific fields to component schema:

```python
class HelmChartConfig(BaseModel):
    """Configuration for a Helm chart component."""
    ref: str = Field(..., description="Chart reference: OCI URL, HTTPS repo, or local path")
    version: str | None = Field(None, description="Chart version constraint")
    values: dict[str, Any] = Field(default_factory=dict, description="Default Helm values")

    @field_validator("ref")
    @classmethod
    def validate_ref(cls, v: str) -> str:
        import re
        patterns = [
            r"^oci://[\w\-\.]+/[\w\-/]+$",
            r"^https://[\w\-\.]+/[\w\-/]+$",
            r"^charts/[\w\-]+$",
        ]
        if not any(re.match(p, v) for p in patterns):
            raise ValueError(f"Invalid chart reference: {v}")
        return v


class TemplateComponentSchema(BaseModel):
    """Schema for a component within a template."""
    name: str
    display_name: str
    description: str = ""
    type: str  # model, llm, embedder, reranker, vector_db, memory_store, helm
    required: bool = True
    default_component: str | None = None
    compatible_components: list[str] = []
    chart: HelmChartConfig | None = None  # NEW — required when type=helm

    @model_validator(mode="after")
    def validate_chart_for_helm(self) -> "TemplateComponentSchema":
        if self.type == "helm" and self.chart is None:
            raise ValueError("'chart' is required when type is 'helm'")
        if self.type != "helm" and self.chart is not None:
            raise ValueError("'chart' should only be set when type is 'helm'")
        return self
```

### C.3 Store Chart Config in Component Model

**File:** `services/budusecases/budusecases/templates/models.py`

The component data is already stored as JSONB in the template's `components` field. The `chart` sub-object will be naturally serialized. No model change needed.

### C.4 Update Component-to-Job Mapping

**File:** `services/budusecases/budusecases/deployments/services.py`

```python
COMPONENT_TYPE_TO_JOB_TYPE = {
    "model": JobType.MODEL_DEPLOYMENT,
    "llm": JobType.MODEL_DEPLOYMENT,
    "embedder": JobType.MODEL_DEPLOYMENT,
    "reranker": JobType.MODEL_DEPLOYMENT,
    "vector_db": JobType.VECTOR_DB_DEPLOYMENT,
    "helm": JobType.HELM_DEPLOY,  # NEW
}
```

### C.5 Add `pipeline_execution_id` to Deployment Model

**File:** `services/budusecases/budusecases/deployments/models.py`

```python
class UseCaseDeployment(PSQLBase):
    # ... existing fields ...
    pipeline_execution_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True,
        comment="BudPipeline execution ID for orchestrated deployments",
    )
```

**Migration:** Add column `pipeline_execution_id` to `usecase_deployment` table.

### C.6 Create DAG Builder

This is the core new module — it converts a template + deployment request into a BudPipeline DAG.

**File:** `services/budusecases/budusecases/deployments/dag_builder.py`

```python
"""Build BudPipeline DAGs from use case template deployment orders."""

from __future__ import annotations

from typing import Any
from uuid import UUID


def build_deployment_dag(
    deployment_id: UUID,
    deployment_name: str,
    cluster_id: UUID,
    user_id: str,
    template: dict,
    component_selections: dict[str, str],
    parameters: dict[str, Any],
    callback_topic: str = "budusecasesEvents",
) -> dict:
    """Build a BudPipeline DAG from a use case template.

    Args:
        deployment_id: Use case deployment UUID
        deployment_name: Human-readable deployment name
        cluster_id: Target cluster UUID
        user_id: Deploying user's ID
        template: Resolved template dict with components and deployment_order
        component_selections: Map of component_name → selected_component
        parameters: User-provided deployment parameters
        callback_topic: Dapr pub/sub topic for progress events

    Returns:
        DAG definition dict compatible with BudPipeline /executions API
    """
    components = {c["name"]: c for c in template.get("components", [])}
    deployment_order = template.get("deployment_order", list(components.keys()))

    steps = []
    # Track which step provides which component's outputs
    # so downstream steps can reference {{ steps.<name>.outputs.endpoint_url }}

    # Step 0: Cluster health check
    steps.append({
        "id": "cluster_health",
        "action": "cluster_health",
        "params": {
            "cluster_id": str(cluster_id),
        },
    })

    previous_step_id = "cluster_health"

    for component_name in deployment_order:
        component = components.get(component_name)
        if component is None:
            continue

        selected = component_selections.get(
            component_name,
            component.get("default_component"),
        )
        if selected is None and component.get("required", True):
            raise ValueError(f"No component selected for required slot '{component_name}'")
        if selected is None:
            continue  # optional, not selected

        component_type = component["type"]

        step = {
            "id": component_name,
            "depends_on": [previous_step_id],
        }

        if component_type == "helm":
            chart = component["chart"]
            # Resolve Jinja2 references in values
            # e.g., {{ steps.llm.outputs.endpoint_url }}
            step["action"] = "helm_deploy"
            step["params"] = {
                "cluster_id": str(cluster_id),
                "chart_ref": chart["ref"],
                "chart_version": chart.get("version"),
                "release_name": f"{deployment_name}-{component_name}",
                "namespace": f"uc-{str(deployment_id)[:8]}",
                "values": _resolve_values(chart.get("values", {}), parameters),
            }
        else:
            # Model/vector_db/etc — use existing deployment_create action
            step["action"] = "deployment_create"
            step["params"] = {
                "cluster_id": str(cluster_id),
                "component_name": component_name,
                "component_type": component_type,
                "selected_component": selected,
                "deployment_id": str(deployment_id),
                "user_id": user_id,
            }

        steps.append(step)
        previous_step_id = component_name

    # Final step: notification
    steps.append({
        "id": "notify_complete",
        "action": "notification",
        "depends_on": [previous_step_id],
        "params": {
            "message": f"Use case '{deployment_name}' deployed successfully",
            "user_id": user_id,
            "level": "success",
        },
    })

    return {
        "name": f"deploy-usecase-{deployment_name}",
        "version": "1.0.0",
        "description": f"Deploy use case: {deployment_name}",
        "parameters": parameters,
        "settings": {
            "timeout_seconds": 7200,  # 2 hours total
            "on_failure": "fail",
        },
        "steps": steps,
        "outputs": {
            "deployment_id": str(deployment_id),
        },
        "callback_topics": [callback_topic],
    }


def _resolve_values(values: dict, parameters: dict) -> dict:
    """Shallow merge user parameters into chart values.

    Deep Jinja2 resolution happens in BudPipeline's DAG engine.
    """
    resolved = dict(values)
    for key, val in resolved.items():
        if isinstance(val, str) and val.startswith("{{ parameters."):
            param_name = val.replace("{{ parameters.", "").replace(" }}", "")
            if param_name in parameters:
                resolved[key] = parameters[param_name]
    return resolved
```

### C.7 Create BudPipeline Client

**File:** `services/budusecases/budusecases/clients/budpipeline/client.py`

```python
"""Client for BudPipeline service via Dapr service invocation."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import structlog
from dapr.clients import DaprClient

from budusecases.commons.config import settings

logger = structlog.get_logger(__name__)


class BudPipelineClient:
    """Client for interacting with BudPipeline service."""

    def __init__(self):
        self.app_id = settings.budpipeline_app_id  # "budpipeline"

    async def create_execution(self, dag: dict) -> dict:
        """Submit a DAG for execution.

        Args:
            dag: Pipeline DAG definition dict

        Returns:
            Execution response with execution_id, status
        """
        logger.info("budpipeline_create_execution", dag_name=dag.get("name"))

        with DaprClient() as client:
            response = client.invoke_method(
                app_id=self.app_id,
                method_name="executions",
                http_verb="POST",
                data=json.dumps(dag),
                content_type="application/json",
            )
            return json.loads(response.data)

    async def get_execution(self, execution_id: str) -> dict:
        """Get execution status."""
        with DaprClient() as client:
            response = client.invoke_method(
                app_id=self.app_id,
                method_name=f"executions/{execution_id}",
                http_verb="GET",
            )
            return json.loads(response.data)

    async def get_execution_progress(self, execution_id: str) -> dict:
        """Get execution progress with step details."""
        with DaprClient() as client:
            response = client.invoke_method(
                app_id=self.app_id,
                method_name=f"executions/{execution_id}/progress?detail=steps",
                http_verb="GET",
            )
            return json.loads(response.data)

    async def cancel_execution(self, execution_id: str) -> dict:
        """Cancel a running execution."""
        with DaprClient() as client:
            response = client.invoke_method(
                app_id=self.app_id,
                method_name=f"executions/{execution_id}/cancel",
                http_verb="POST",
            )
            return json.loads(response.data)
```

**File:** `services/budusecases/budusecases/clients/budpipeline/__init__.py`

```python
from .client import BudPipelineClient

__all__ = ["BudPipelineClient"]
```

### C.8 Modify Deployment Service — Pipeline-Based Start

**File:** `services/budusecases/budusecases/deployments/services.py`

Replace the manual per-component deployment with pipeline submission:

```python
async def start_deployment(self, deployment_id: UUID, user_id: str) -> UseCaseDeployment:
    """Start a deployment by submitting a DAG to BudPipeline."""
    deployment = self.deployment_manager.get_deployment(deployment_id)
    if deployment.status != DeploymentStatus.PENDING:
        raise ValueError(f"Deployment {deployment_id} is not in PENDING status")

    template = self._get_template_dict(deployment.template_id)
    component_selections = {
        cd.component_name: cd.selected_component
        for cd in deployment.component_deployments
    }

    # Build pipeline DAG
    dag = build_deployment_dag(
        deployment_id=deployment.id,
        deployment_name=deployment.name,
        cluster_id=deployment.cluster_id,
        user_id=user_id,
        template=template,
        component_selections=component_selections,
        parameters=deployment.parameters or {},
    )

    # Submit to BudPipeline
    pipeline_client = BudPipelineClient()
    execution = await pipeline_client.create_execution(dag)
    execution_id = execution["execution_id"]

    # Update deployment with pipeline execution reference
    self.deployment_manager.update_deployment(
        deployment_id=deployment.id,
        status=DeploymentStatus.DEPLOYING,
        pipeline_execution_id=execution_id,
    )

    # Update all components to DEPLOYING
    for cd in deployment.component_deployments:
        self.deployment_manager.update_component_deployment_status(
            component_id=cd.id,
            status=ComponentDeploymentStatus.DEPLOYING,
        )

    return self.deployment_manager.get_deployment(deployment_id)
```

### C.9 Add Dapr Pub/Sub Event Listener

BudUseCases needs to receive progress events from BudPipeline.

**File:** `services/budusecases/budusecases/events/pipeline_listener.py`

```python
"""Dapr pub/sub listener for BudPipeline execution events."""

from __future__ import annotations

import structlog

from budusecases.deployments.enums import (
    ComponentDeploymentStatus,
    DeploymentStatus,
)

logger = structlog.get_logger(__name__)

# Map pipeline step status to component deployment status
STEP_STATUS_MAP = {
    "COMPLETED": ComponentDeploymentStatus.RUNNING,
    "FAILED": ComponentDeploymentStatus.FAILED,
    "RUNNING": ComponentDeploymentStatus.DEPLOYING,
    "PENDING": ComponentDeploymentStatus.PENDING,
    "TIMEOUT": ComponentDeploymentStatus.FAILED,
}


async def handle_pipeline_event(event_data: dict, deployment_manager) -> None:
    """Handle a pipeline execution event from BudPipeline.

    Routes:
    - Step completion → update corresponding ComponentDeployment
    - Execution completion → update UseCaseDeployment
    - Execution failure → mark deployment as failed
    """
    event_type = event_data.get("type", "")
    payload = event_data.get("payload", {})
    execution_id = payload.get("execution_id")

    if not execution_id:
        logger.warning("pipeline_event_no_execution_id", event=event_data)
        return

    # Find deployment by pipeline_execution_id
    deployment = deployment_manager.get_deployment_by_pipeline_execution(execution_id)
    if deployment is None:
        logger.warning("pipeline_event_no_deployment", execution_id=execution_id)
        return

    if event_type == "step_completed":
        step_id = payload.get("step_id")
        step_status = payload.get("status", "")
        step_outputs = payload.get("outputs", {})

        # Find matching component deployment by step_id == component_name
        component = next(
            (cd for cd in deployment.component_deployments if cd.component_name == step_id),
            None,
        )
        if component:
            new_status = STEP_STATUS_MAP.get(step_status, ComponentDeploymentStatus.DEPLOYING)
            deployment_manager.update_component_deployment_status(
                component_id=component.id,
                status=new_status,
                endpoint_url=step_outputs.get("endpoint_url"),
                error_message=step_outputs.get("error"),
            )
            if step_outputs.get("job_id"):
                deployment_manager.update_component_deployment_job(
                    component_id=component.id,
                    job_id=step_outputs["job_id"],
                )

            logger.info(
                "pipeline_component_updated",
                deployment_id=str(deployment.id),
                component=step_id,
                status=new_status,
            )

    elif event_type == "execution_completed":
        exec_status = payload.get("status", "")
        if exec_status == "COMPLETED":
            deployment_manager.update_deployment_status(
                deployment_id=deployment.id,
                status=DeploymentStatus.RUNNING,
            )
        elif exec_status == "FAILED":
            error = payload.get("error", "Pipeline execution failed")
            deployment_manager.update_deployment_status(
                deployment_id=deployment.id,
                status=DeploymentStatus.FAILED,
                error_message=error,
            )

        logger.info(
            "pipeline_deployment_completed",
            deployment_id=str(deployment.id),
            status=exec_status,
        )
```

### C.10 Register Pub/Sub Subscription in Main App

**File:** `services/budusecases/budusecases/main.py`

```python
from fastapi import Request

@app.post("/budusecases-events")
async def handle_budusecases_events(request: Request):
    """Dapr pub/sub subscription handler for pipeline events."""
    event = await request.json()
    event_data = event.get("data", {})

    await handle_pipeline_event(event_data, deployment_manager)

    return {"status": "SUCCESS"}


# Dapr subscription configuration
@app.get("/dapr/subscribe")
async def subscribe():
    """Register Dapr pub/sub subscriptions."""
    return [
        {
            "pubsubname": "pubsub",
            "topic": "budusecasesEvents",
            "route": "/budusecases-events",
        },
    ]
```

### C.11 Add Config Setting for BudPipeline

**File:** `services/budusecases/budusecases/commons/config.py`

```python
class Settings(BaseSettings):
    # ... existing ...
    budpipeline_app_id: str = "budpipeline"
```

### C.12 Update Sync Endpoint (Backward Compatibility)

The existing `/sync` endpoint should now check pipeline execution status if `pipeline_execution_id` is set:

```python
async def sync_deployment_status(self, deployment_id: UUID) -> UseCaseDeployment:
    deployment = self.deployment_manager.get_deployment(deployment_id)

    if deployment.pipeline_execution_id:
        # Pipeline-managed: fetch progress from BudPipeline
        pipeline_client = BudPipelineClient()
        progress = await pipeline_client.get_execution_progress(
            deployment.pipeline_execution_id
        )
        # Progress events update status via pub/sub listener,
        # so just return current state
        return deployment

    # Legacy: direct job polling (backward compat for existing deployments)
    # ... existing sync logic ...
```

### C.13 Files Changed (Phase C Summary)

| File | Action | Description |
|------|--------|-------------|
| `budusecases/templates/services.py` | Modify | Add `helm` to `VALID_COMPONENT_TYPES` |
| `budusecases/templates/schemas.py` | Modify | Add `HelmChartConfig`, `chart` field on component schema |
| `budusecases/deployments/services.py` | Modify | Pipeline-based `start_deployment()`, update type mapping |
| `budusecases/deployments/models.py` | Modify | Add `pipeline_execution_id` column |
| `budusecases/deployments/dag_builder.py` | Create | DAG builder from template |
| `budusecases/clients/budpipeline/client.py` | Create | BudPipeline Dapr client |
| `budusecases/clients/budpipeline/__init__.py` | Create | Package init |
| `budusecases/events/pipeline_listener.py` | Create | Pub/sub event handler |
| `budusecases/main.py` | Modify | Register pub/sub subscription |
| `budusecases/commons/config.py` | Modify | Add `budpipeline_app_id` |
| `alembic/versions/XXXX_add_pipeline_execution_id.py` | Create | Migration |
| `tests/test_dag_builder.py` | Create | DAG builder tests |
| `tests/test_pipeline_listener.py` | Create | Event listener tests |

---

## Phase D: BudAdmin — UI Updates

### D.1 Template Creation — Helm Component Form

When creating a custom template, the UI should allow adding `type: helm` components with:

- Chart reference input (text field with validation)
- Chart version input (optional)
- Helm values editor (JSON editor)
- Preview of resolved values with Jinja2 references highlighted

### D.2 Deployment Progress View

Replace the manual "Sync" button with real-time progress:

- Subscribe to deployment status updates (poll `/deployments/{id}` or use SSE)
- Show step-by-step progress bar from pipeline execution
- Show per-component status with icons (pending, deploying, running, failed)
- Show ETA from BudPipeline progress tracking
- Show logs/error messages on failure

### D.3 Template Detail — Helm Component Display

When viewing a template with helm components, show:

- Chart reference and version
- Default values (collapsible JSON view)
- Dependency arrows from `deployment_order`

### D.4 Files Changed (Phase D Summary)

| File | Action | Description |
|------|--------|-------------|
| `budadmin/src/pages/api/budusecases.ts` | Modify | Add `chart` field to template types, progress API |
| `budadmin/src/stores/useUseCases.ts` | Modify | Add progress polling, template helm support |
| `budadmin/src/components/usecases/TemplateForm.tsx` | Create | Helm component form fields |
| `budadmin/src/components/usecases/DeploymentProgress.tsx` | Create | Real-time progress component |

---

## Phase E: Testing + Integration

### E.1 Unit Tests

| Service | Test File | Coverage |
|---------|-----------|----------|
| budcluster | `tests/test_helm_deploy_job.py` | Job CRUD, enum, playbook invocation mock |
| budcluster | `tests/test_helm_validators.py` | Chart ref validation, blocked keys |
| budpipeline | `tests/test_helm_deploy_action.py` | Action execute, on_event, validate_params |
| budusecases | `tests/test_dag_builder.py` | DAG generation from various templates |
| budusecases | `tests/test_pipeline_listener.py` | Event handling, status mapping |
| budusecases | `tests/test_helm_component_schema.py` | Schema validation for helm type |

### E.2 Integration Tests

| Scenario | Steps | Services |
|----------|-------|----------|
| Simple model deploy via pipeline | Create deployment → start → verify DAG submitted → mock pipeline events → verify status | budusecases, budpipeline (mocked) |
| Mixed model+helm deploy | Template with llm + helm agent → verify DAG ordering → verify Jinja2 refs | budusecases |
| Helm chart security rejection | Submit chart with `hostNetwork: true` → verify 422 | budcluster |
| End-to-end helm deploy | Create template with helm → deploy → pipeline executes → budcluster deploys chart → events flow back | all services |

### E.3 Manual Verification Checklist

- [ ] Create a template with `type: helm` component via API
- [ ] Deploy a use case with mixed model + helm components
- [ ] Verify deployment_order is respected (vector_db before agent runtime)
- [ ] Verify Jinja2 value resolution (LLM endpoint injected into helm values)
- [ ] Verify progress events flow from budpipeline to budusecases
- [ ] Verify component statuses update in real-time
- [ ] Verify user notification on completion
- [ ] Verify deployment failure handling (one component fails → deployment fails)
- [ ] Verify stop deployment cancels pipeline execution
- [ ] Verify chart ref validation rejects invalid patterns
- [ ] Verify Helm values security validation blocks privileged configs

---

## Example: Agent RAG Template (YAML)

```yaml
name: agent-rag
display_name: Agent RAG
version: "1.0.0"
description: >
  RAG-powered AI agent with a vector database, language model,
  and custom LangGraph agent runtime deployed via Helm chart.
category: agent
tags: [agent, rag, langraph]

components:
  - name: vector_db
    display_name: Vector Database
    type: vector_db
    required: true
    default_component: qdrant
    compatible_components:
      - qdrant
      - milvus

  - name: llm
    display_name: Language Model
    type: model
    required: true
    default_component: llama-3-8b
    compatible_components:
      - llama-3-8b
      - llama-3-70b
      - mistral-7b

  - name: agent_runtime
    display_name: Agent Runtime
    type: helm
    required: true
    chart:
      ref: oci://registry.bud.ai/charts/langraph-agent
      version: "1.2.0"
      values:
        replicas: 1
        port: 8080
        llm_endpoint: "{{ steps.llm.outputs.endpoint_url }}"
        vectordb_endpoint: "{{ steps.vector_db.outputs.endpoint_url }}"
        log_level: "info"

parameters:
  chunk_size:
    type: integer
    default: 512
    min: 128
    max: 2048
  agent_concurrency:
    type: integer
    default: 4
    min: 1
    max: 32

resources:
  minimum:
    cpu: 4
    memory: 16Gi
    gpu: 1
  recommended:
    cpu: 16
    memory: 64Gi
    gpu: 2

deployment_order:
  - vector_db
  - llm
  - agent_runtime
```

### Generated DAG (sent to BudPipeline)

```json
{
  "name": "deploy-usecase-my-agent-rag",
  "version": "1.0.0",
  "settings": {"timeout_seconds": 7200, "on_failure": "fail"},
  "callback_topics": ["budusecasesEvents"],
  "steps": [
    {
      "id": "cluster_health",
      "action": "cluster_health",
      "params": {"cluster_id": "abc-123"}
    },
    {
      "id": "vector_db",
      "action": "deployment_create",
      "depends_on": ["cluster_health"],
      "params": {
        "cluster_id": "abc-123",
        "component_name": "vector_db",
        "component_type": "vector_db",
        "selected_component": "qdrant",
        "deployment_id": "def-456",
        "user_id": "user-789"
      }
    },
    {
      "id": "llm",
      "action": "deployment_create",
      "depends_on": ["vector_db"],
      "params": {
        "cluster_id": "abc-123",
        "component_name": "llm",
        "component_type": "model",
        "selected_component": "llama-3-8b",
        "deployment_id": "def-456",
        "user_id": "user-789"
      }
    },
    {
      "id": "agent_runtime",
      "action": "helm_deploy",
      "depends_on": ["llm"],
      "params": {
        "cluster_id": "abc-123",
        "chart_ref": "oci://registry.bud.ai/charts/langraph-agent",
        "chart_version": "1.2.0",
        "release_name": "my-agent-rag-agent-runtime",
        "namespace": "uc-def45678",
        "values": {
          "replicas": 1,
          "port": 8080,
          "llm_endpoint": "{{ steps.llm.outputs.endpoint_url }}",
          "vectordb_endpoint": "{{ steps.vector_db.outputs.endpoint_url }}",
          "log_level": "info"
        }
      }
    },
    {
      "id": "notify_complete",
      "action": "notification",
      "depends_on": ["agent_runtime"],
      "params": {
        "message": "Use case 'my-agent-rag' deployed successfully",
        "user_id": "user-789",
        "level": "success"
      }
    }
  ]
}
```

---

## Data Flow Diagram

```
                    ┌─────────────┐
                    │   User/UI   │
                    └──────┬──────┘
                           │ POST /deployments + POST /deployments/{id}/start
                           ▼
                    ┌──────────────┐
                    │ BudUseCases  │
                    │              │
                    │ 1. Validate  │
                    │ 2. Save DB   │◄────── Dapr pub/sub: budusecasesEvents
                    │ 3. Build DAG │        (step_completed, execution_completed)
                    │ 4. Submit    │        Updates component/deployment status
                    └──────┬───────┘
                           │ Dapr invoke: POST /executions
                           ▼
                    ┌──────────────┐
                    │ BudPipeline  │
                    │              │
                    │ DAG Engine:  │──── Publishes progress to callback_topics
                    │  step1 →     │
                    │  step2 →     │
                    │  step3 →     │
                    └──┬───┬───┬───┘
                       │   │   │  Dapr invoke per step action
          ┌────────────┘   │   └────────────┐
          ▼                ▼                ▼
   cluster_health   deployment_create   helm_deploy
          │                │                │
          │                │                │ POST /job (type=helm_deploy)
          │                │                │ POST /job/{id}/execute
          │                ▼                ▼
          │         ┌──────────────┐
          └────────►│ BudCluster   │
                    │              │
                    │ Jobs API     │
                    │ Ansible      │──── Publishes to budpipelineEvents
                    │ Helm deploy  │     on job completion/failure
                    └──────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ Kubernetes   │
                    │ Cluster      │
                    │              │
                    │ Helm release │
                    │ Pods/Svc/Ing │
                    └──────────────┘
```

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Untrusted Helm charts could escalate privileges | High | Chart ref validation, blocked values keys, namespace isolation, network policies |
| Pipeline execution timeout for large deployments | Medium | Configurable timeouts per step, 2-hour default total |
| BudPipeline service unavailable | Medium | Fallback to direct deployment (legacy path), retry on transient errors |
| Circular dependency in deployment_order | Low | DAG parser validates acyclic graph before execution |
| Jinja2 template injection in Helm values | Medium | BudPipeline's Jinja2 is sandboxed, values are JSON-serialized |
| Orphaned Helm releases on deployment deletion | Medium | Stop deployment → cancel pipeline → run helm uninstall cleanup step |

---

## Migration Strategy

1. **Backward compatible**: Existing deployments without `pipeline_execution_id` continue using the legacy direct-job path
2. **Opt-in**: New deployments created after this change automatically use pipeline orchestration
3. **Gradual rollout**: Can be feature-flagged via `USE_PIPELINE_ORCHESTRATION=true` in config
4. **No breaking API changes**: All existing endpoints continue to work; new fields are optional

---

## Implementation Order

```
Week 1-2: Phase A (BudCluster)
  ├── A.1-A.2: Enum + migration
  ├── A.3-A.5: Playbook + handler
  ├── A.6-A.7: Workflow activity + execute route
  └── A.8-A.9: Event publishing + validation

Week 2-3: Phase B (BudPipeline)
  ├── B.1: helm_deploy action
  └── B.2: Entry point registration

Week 3-5: Phase C (BudUseCases)
  ├── C.1-C.3: Schema + type changes
  ├── C.4-C.5: Model + config changes
  ├── C.6-C.8: DAG builder + pipeline client + service rewrite
  └── C.9-C.12: Event listener + pub/sub + backward compat

Week 5-6: Phase D (BudAdmin)
  ├── D.1-D.2: Helm component form + progress view
  └── D.3: Template detail UI

Week 6-7: Phase E (Testing)
  ├── E.1: Unit tests
  ├── E.2: Integration tests
  └── E.3: Manual verification
```

Total estimated: **6-7 weeks**

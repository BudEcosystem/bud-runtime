# Guardrail Deployment Workflow Migration Implementation Plan

**Goal:** Migrate guardrail deployment workflow to use BudPipeline for multi-model orchestration while preserving frontend compatibility.

**Architecture:** Workflow layer (budapp) handles UI step coordination and triggers BudPipeline DAGs at execution points (Steps 5, 8, 12). Pipeline actions in budpipeline service handle async operations with event-driven completion. Workflow wraps Pipeline pattern (F1).

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, Pydantic v2, BudPipeline actions, Dapr service invocation, Redis

**Design Doc:** `docs/plans/2026-01-28-guardrail-deployment-workflow-migration-design.md`

---

## Phase 1: Schema Extensions (budapp)

### Task 1.1: Add ModelDeploymentStatus Enum

**Files:**
- Modify: `budapp/guardrails/schemas.py`
- Test: `tests/guardrails/test_schemas.py`

**Step 1: Add the enum after existing imports**

```python
# Add after line 32 (after existing imports)
from enum import Enum

class ModelDeploymentStatus(str, Enum):
    """Composite status for guardrail model deployment."""
    NOT_ONBOARDED = "not_onboarded"
    ONBOARDED = "onboarded"
    RUNNING = "running"
    UNHEALTHY = "unhealthy"
    DEPLOYING = "deploying"
    PENDING = "pending"
    FAILURE = "failure"
    DELETING = "deleting"
```

**Step 2: Verify enum values match EndpointStatusEnum**

Run: `grep -A 10 "class EndpointStatusEnum" budapp/commons/constants.py`

**Step 3: Commit**

```bash
git add budapp/guardrails/schemas.py
git commit -m "feat(guardrails): add ModelDeploymentStatus enum"
```

---

### Task 1.2: Add GuardrailModelStatus Schema

**Files:**
- Modify: `budapp/guardrails/schemas.py`

**Step 1: Add schema after ModelDeploymentStatus enum**

```python
class GuardrailModelStatus(BaseModel):
    """Status of a model required by guardrail rules."""

    model_config = ConfigDict(from_attributes=True)

    # Rule identification
    rule_id: UUID4
    rule_name: str
    probe_id: UUID4
    probe_name: str

    # Model info
    model_uri: str
    model_id: UUID4 | None = None

    # Status
    status: ModelDeploymentStatus

    # Endpoint details (populated when deployed)
    endpoint_id: UUID4 | None = None
    endpoint_name: str | None = None
    endpoint_url: str | None = None
    cluster_id: UUID4 | None = None
    cluster_name: str | None = None

    # Derived flags for UI
    requires_onboarding: bool
    requires_deployment: bool
    can_reuse: bool
    show_warning: bool = False
```

**Step 2: Add response wrapper schema**

```python
class GuardrailModelStatusResponse(SuccessResponse):
    """Response for model status identification step."""

    models: list[GuardrailModelStatus]
    total_models: int
    models_requiring_onboarding: int
    models_requiring_deployment: int
    models_reusable: int
    skip_to_step: int | None = None
    credential_required: bool = False
    object: str = "guardrail.model_status"
```

**Step 3: Commit**

```bash
git add budapp/guardrails/schemas.py
git commit -m "feat(guardrails): add GuardrailModelStatus schema"
```

---

### Task 1.3: Extend RetrieveWorkflowStepData Schema

**Files:**
- Modify: `budapp/workflow_ops/schemas.py`

**Step 1: Add new fields to RetrieveWorkflowStepData class (after line 129)**

```python
    # Guardrail model status fields (Step 4)
    model_statuses: list[dict] | None = None
    models_requiring_onboarding: int | None = None
    models_requiring_deployment: int | None = None
    models_reusable: int | None = None

    # Skip logic
    skip_to_step: int | None = None
    credential_required: bool | None = None

    # Pipeline execution tracking
    pipeline_execution_id: UUID4 | None = None
    pipeline_status: str | None = None
    pipeline_results: dict | None = None

    # Cluster recommendation results
    recommended_clusters: list[dict] | None = None
    per_model_configs: list[dict] | None = None

    # Models categorization for deployment
    models_to_deploy: list[dict] | None = None
    models_to_reuse: list[dict] | None = None

    # Deployment results
    deployment_id: UUID4 | None = None
    deployed_endpoint_ids: list[UUID4] | None = None
```

**Step 2: Commit**

```bash
git add budapp/workflow_ops/schemas.py
git commit -m "feat(workflow): extend RetrieveWorkflowStepData for guardrail pipeline"
```

---

## Phase 2: BudPipeline Actions Setup (budpipeline)

### Task 2.1: Create Guardrail Actions Directory Structure

**Files:**
- Create: `budpipeline/actions/guardrail/__init__.py`

**Step 1: Create directory and __init__.py**

```bash
mkdir -p /home/crypt/Repos/bud-runtime/.worktrees/sentinel-v2/services/budpipeline/budpipeline/actions/guardrail
```

**Step 2: Create __init__.py with exports**

```python
"""Guardrail pipeline actions.

Actions for orchestrating guardrail deployment workflows including
model onboarding, cluster recommendations, and deployment.
"""

from budpipeline.actions.guardrail.validate_credential import ValidateCredentialAction
from budpipeline.actions.guardrail.batch_onboard import BatchOnboardAction
from budpipeline.actions.guardrail.update_rules import UpdateRuleModelIdsAction
from budpipeline.actions.guardrail.parallel_simulate import ParallelSimulateAction
from budpipeline.actions.guardrail.aggregate_requirements import AggregateRequirementsAction
from budpipeline.actions.guardrail.validate_cluster_fit import ValidateClusterFitAction
from budpipeline.actions.guardrail.deploy_models import DeployModelsAction
from budpipeline.actions.guardrail.create_profile import CreateProfileAction
from budpipeline.actions.guardrail.create_deployment import CreateDeploymentAction
from budpipeline.actions.guardrail.build_config import BuildConfigAction
from budpipeline.actions.guardrail.sync_redis import SyncRedisAction
from budpipeline.actions.guardrail.rollback import RollbackAction

__all__ = [
    "ValidateCredentialAction",
    "BatchOnboardAction",
    "UpdateRuleModelIdsAction",
    "ParallelSimulateAction",
    "AggregateRequirementsAction",
    "ValidateClusterFitAction",
    "DeployModelsAction",
    "CreateProfileAction",
    "CreateDeploymentAction",
    "BuildConfigAction",
    "SyncRedisAction",
    "RollbackAction",
]
```

**Step 3: Commit**

```bash
git add budpipeline/actions/guardrail/
git commit -m "feat(budpipeline): create guardrail actions directory structure"
```

---

### Task 2.2: Implement validate_credential Action (SYNC)

**Files:**
- Create: `budpipeline/actions/guardrail/validate_credential.py`
- Test: `tests/actions/guardrail/test_validate_credential.py`

**Step 1: Create the action file**

```python
"""Validate Credential Action.

Validates that a credential exists and is accessible for model onboarding.
"""

from __future__ import annotations

import structlog

from budpipeline.actions.base import (
    ActionContext,
    ActionMeta,
    ActionResult,
    BaseActionExecutor,
    ExecutionMode,
    OutputDefinition,
    ParamDefinition,
    ParamType,
    register_action,
)
from budpipeline.commons.config import settings

logger = structlog.get_logger(__name__)


class ValidateCredentialExecutor(BaseActionExecutor):
    """Executor that validates a credential exists."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Validate credential via budapp."""
        credential_id = context.params.get("credential_id")

        if not credential_id:
            return ActionResult(
                success=False,
                outputs={"valid": False, "credential_type": None},
                error="credential_id is required",
            )

        logger.info(
            "validate_credential_starting",
            step_id=context.step_id,
            credential_id=credential_id,
        )

        try:
            response = await context.invoke_service(
                app_id=settings.budapp_app_id,
                method_path=f"/credentials/{credential_id}",
                http_method="GET",
                timeout_seconds=30,
            )

            credential_data = response.get("data", response)
            credential_type = credential_data.get("type", "unknown")

            logger.info(
                "validate_credential_success",
                step_id=context.step_id,
                credential_id=credential_id,
                credential_type=credential_type,
            )

            return ActionResult(
                success=True,
                outputs={
                    "valid": True,
                    "credential_id": credential_id,
                    "credential_type": credential_type,
                },
            )

        except Exception as e:
            error_msg = f"Failed to validate credential: {e!s}"
            logger.error(
                "validate_credential_failed",
                step_id=context.step_id,
                credential_id=credential_id,
                error=error_msg,
            )
            return ActionResult(
                success=False,
                outputs={"valid": False, "credential_type": None},
                error=error_msg,
            )


META = ActionMeta(
    type="guardrail.validate_credential",
    version="1.0.0",
    name="Validate Credential",
    description="Validates that a credential exists and is accessible for model onboarding",
    category="Guardrail",
    icon="key",
    color="#F59E0B",
    execution_mode=ExecutionMode.SYNC,
    idempotent=True,
    required_services=["budapp"],
    params=[
        ParamDefinition(
            name="credential_id",
            label="Credential ID",
            type=ParamType.STRING,
            required=True,
            description="The credential ID to validate",
        ),
    ],
    outputs=[
        OutputDefinition(
            name="valid",
            type="boolean",
            description="Whether the credential is valid",
        ),
        OutputDefinition(
            name="credential_id",
            type="string",
            description="The validated credential ID",
        ),
        OutputDefinition(
            name="credential_type",
            type="string",
            description="The type of credential",
        ),
    ],
)


@register_action(META)
class ValidateCredentialAction:
    """Validate Credential action for entry point registration."""

    meta = META
    executor_class = ValidateCredentialExecutor
```

**Step 2: Commit**

```bash
git add budpipeline/actions/guardrail/validate_credential.py
git commit -m "feat(budpipeline): add guardrail.validate_credential action"
```

---

### Task 2.3: Implement batch_onboard Action (EVENT_DRIVEN)

**Files:**
- Create: `budpipeline/actions/guardrail/batch_onboard.py`

**Step 1: Create the action file**

```python
"""Batch Onboard Models Action.

Onboards multiple models required by guardrail rules.
Uses event-driven completion - waits for all models to complete.
"""

from __future__ import annotations

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
from budpipeline.commons.constants import CALLBACK_TOPIC

logger = structlog.get_logger(__name__)


class BatchOnboardExecutor(BaseActionExecutor):
    """Executor for batch model onboarding."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Start onboarding workflows for all models."""
        models = context.params.get("models", [])
        credential_id = context.params.get("credential_id")
        user_id = context.params.get("user_id") or context.workflow_params.get("user_id")

        if not models:
            return ActionResult(
                success=True,
                outputs={
                    "results": [],
                    "all_succeeded": True,
                    "total": 0,
                    "completed": 0,
                    "failed": 0,
                },
            )

        logger.info(
            "batch_onboard_starting",
            step_id=context.step_id,
            model_count=len(models),
        )

        workflow_ids = []
        pending_results = []

        for model in models:
            try:
                response = await context.invoke_service(
                    app_id=settings.budapp_app_id,
                    method_path="/models/local-model-workflow",
                    http_method="POST",
                    params={"user_id": user_id} if user_id else None,
                    data={
                        "workflow_total_steps": 1,
                        "step_number": 1,
                        "trigger_workflow": True,
                        "provider_type": model.get("model_provider_type", "hugging_face"),
                        "uri": model["model_uri"],
                        "name": model["model_uri"].split("/")[-1],
                        "credential_id": credential_id,
                        "callback_topic": CALLBACK_TOPIC,
                    },
                    timeout_seconds=60,
                )

                workflow_id = response.get("data", {}).get("workflow_id") or response.get("workflow_id")
                workflow_ids.append(str(workflow_id))
                pending_results.append({
                    "rule_id": model["rule_id"],
                    "model_uri": model["model_uri"],
                    "workflow_id": str(workflow_id),
                    "status": "running",
                    "model_id": None,
                })

            except Exception as e:
                logger.error(
                    "batch_onboard_model_failed",
                    step_id=context.step_id,
                    model_uri=model.get("model_uri"),
                    error=str(e),
                )
                # Partial success = failure, so fail immediately
                return ActionResult(
                    success=False,
                    outputs={
                        "results": pending_results,
                        "all_succeeded": False,
                        "total": len(models),
                        "completed": 0,
                        "failed": 1,
                    },
                    error=f"Failed to start onboarding for {model.get('model_uri')}: {e!s}",
                )

        # Combine all workflow IDs for tracking
        combined_id = ",".join(workflow_ids)

        return ActionResult(
            success=True,
            outputs={
                "results": pending_results,
                "all_succeeded": False,  # Will be True when all complete
                "total": len(models),
                "completed": 0,
                "failed": 0,
                "pending_workflow_ids": workflow_ids,
            },
            awaiting_event=True,
            external_workflow_id=combined_id,
            timeout_seconds=context.params.get("max_wait_seconds", 1800),
        )

    async def on_event(self, context: EventContext) -> EventResult:
        """Process completion events for model onboarding."""
        event_type = context.event_data.get("type", "")
        workflow_id = context.event_data.get("workflow_id", "")

        logger.info(
            "batch_onboard_event_received",
            step_execution_id=context.step_execution_id,
            event_type=event_type,
            workflow_id=workflow_id,
        )

        if event_type != "workflow_completed":
            return EventResult(action=EventAction.IGNORE)

        # Get current results from step outputs
        current_results = context.step_outputs.get("results", [])
        pending_ids = context.step_outputs.get("pending_workflow_ids", [])

        # Update the matching result
        status = context.event_data.get("status", "UNKNOWN")
        result_data = context.event_data.get("result", {})

        for result in current_results:
            if result.get("workflow_id") == workflow_id:
                if status == "COMPLETED":
                    result["status"] = "completed"
                    result["model_id"] = result_data.get("model_id")
                else:
                    result["status"] = "failed"
                    result["error"] = context.event_data.get("reason", "Unknown error")
                break

        # Check if all completed
        completed = sum(1 for r in current_results if r.get("status") == "completed")
        failed = sum(1 for r in current_results if r.get("status") == "failed")
        total = len(current_results)

        if failed > 0:
            # Partial success = failure
            return EventResult(
                action=EventAction.COMPLETE,
                status=StepStatus.FAILED,
                outputs={
                    "results": current_results,
                    "all_succeeded": False,
                    "total": total,
                    "completed": completed,
                    "failed": failed,
                },
                error=f"Model onboarding failed: {failed}/{total} models failed",
            )

        if completed == total:
            return EventResult(
                action=EventAction.COMPLETE,
                status=StepStatus.COMPLETED,
                outputs={
                    "results": current_results,
                    "all_succeeded": True,
                    "total": total,
                    "completed": completed,
                    "failed": 0,
                },
            )

        # Still waiting for more completions - update outputs but don't complete
        return EventResult(
            action=EventAction.UPDATE_OUTPUTS,
            outputs={
                "results": current_results,
                "all_succeeded": False,
                "total": total,
                "completed": completed,
                "failed": failed,
                "pending_workflow_ids": pending_ids,
            },
        )


META = ActionMeta(
    type="guardrail.batch_onboard_models",
    version="1.0.0",
    name="Batch Onboard Models",
    description="Onboard multiple models required by guardrail rules",
    category="Guardrail",
    icon="database-plus",
    color="#10B981",
    execution_mode=ExecutionMode.EVENT_DRIVEN,
    timeout_seconds=1800,
    idempotent=False,
    required_services=["budapp"],
    params=[
        ParamDefinition(
            name="models",
            label="Models to Onboard",
            type=ParamType.JSON,
            required=True,
            description="Array of models: [{rule_id, model_uri, model_provider_type}]",
        ),
        ParamDefinition(
            name="credential_id",
            label="Credential ID",
            type=ParamType.STRING,
            required=True,
            description="Credential for accessing gated models",
        ),
        ParamDefinition(
            name="user_id",
            label="User ID",
            type=ParamType.STRING,
            required=False,
            description="User initiating the onboarding",
        ),
        ParamDefinition(
            name="max_wait_seconds",
            label="Max Wait Time",
            type=ParamType.NUMBER,
            required=False,
            default=1800,
            description="Maximum time to wait for all models to onboard",
        ),
    ],
    outputs=[
        OutputDefinition(
            name="results",
            type="json",
            description="Array of results: [{rule_id, model_id, status}]",
        ),
        OutputDefinition(
            name="all_succeeded",
            type="boolean",
            description="Whether all models were onboarded successfully",
        ),
        OutputDefinition(
            name="total",
            type="number",
            description="Total number of models",
        ),
        OutputDefinition(
            name="completed",
            type="number",
            description="Number of successfully completed",
        ),
        OutputDefinition(
            name="failed",
            type="number",
            description="Number of failed",
        ),
    ],
)


@register_action(META)
class BatchOnboardAction:
    """Batch onboard action for entry point registration."""

    meta = META
    executor_class = BatchOnboardExecutor
```

**Step 2: Commit**

```bash
git add budpipeline/actions/guardrail/batch_onboard.py
git commit -m "feat(budpipeline): add guardrail.batch_onboard_models action"
```

---

### Task 2.4: Implement update_rules Action (SYNC)

**Files:**
- Create: `budpipeline/actions/guardrail/update_rules.py`

**Step 1: Create the action file**

```python
"""Update Rule Model IDs Action.

Updates GuardrailRule.model_id after successful model onboarding.
"""

from __future__ import annotations

import structlog

from budpipeline.actions.base import (
    ActionContext,
    ActionMeta,
    ActionResult,
    BaseActionExecutor,
    ExecutionMode,
    OutputDefinition,
    ParamDefinition,
    ParamType,
    register_action,
)
from budpipeline.commons.config import settings

logger = structlog.get_logger(__name__)


class UpdateRuleModelIdsExecutor(BaseActionExecutor):
    """Executor that updates rule model IDs after onboarding."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Update model_id for each rule based on onboarding results."""
        onboard_results = context.params.get("onboard_results", [])

        if not onboard_results:
            return ActionResult(
                success=True,
                outputs={"success": True, "updated_count": 0},
            )

        logger.info(
            "update_rule_model_ids_starting",
            step_id=context.step_id,
            result_count=len(onboard_results),
        )

        updated_count = 0
        errors = []

        for result in onboard_results:
            rule_id = result.get("rule_id")
            model_id = result.get("model_id")

            if not rule_id or not model_id:
                continue

            try:
                await context.invoke_service(
                    app_id=settings.budapp_app_id,
                    method_path=f"/internal/guardrails/rules/{rule_id}/model",
                    http_method="PATCH",
                    data={"model_id": model_id},
                    timeout_seconds=30,
                )
                updated_count += 1

            except Exception as e:
                error_msg = f"Failed to update rule {rule_id}: {e!s}"
                logger.error("update_rule_model_id_failed", rule_id=rule_id, error=error_msg)
                errors.append(error_msg)

        if errors:
            return ActionResult(
                success=False,
                outputs={
                    "success": False,
                    "updated_count": updated_count,
                    "errors": errors,
                },
                error=f"Failed to update {len(errors)} rules",
            )

        logger.info(
            "update_rule_model_ids_success",
            step_id=context.step_id,
            updated_count=updated_count,
        )

        return ActionResult(
            success=True,
            outputs={"success": True, "updated_count": updated_count},
        )


META = ActionMeta(
    type="guardrail.update_rule_model_ids",
    version="1.0.0",
    name="Update Rule Model IDs",
    description="Updates GuardrailRule.model_id after successful model onboarding",
    category="Guardrail",
    icon="refresh",
    color="#6366F1",
    execution_mode=ExecutionMode.SYNC,
    idempotent=True,
    required_services=["budapp"],
    params=[
        ParamDefinition(
            name="onboard_results",
            label="Onboard Results",
            type=ParamType.JSON,
            required=True,
            description="Results from batch onboarding: [{rule_id, model_id}]",
        ),
    ],
    outputs=[
        OutputDefinition(
            name="success",
            type="boolean",
            description="Whether all updates succeeded",
        ),
        OutputDefinition(
            name="updated_count",
            type="number",
            description="Number of rules updated",
        ),
    ],
)


@register_action(META)
class UpdateRuleModelIdsAction:
    """Update rule model IDs action for entry point registration."""

    meta = META
    executor_class = UpdateRuleModelIdsExecutor
```

**Step 2: Commit**

```bash
git add budpipeline/actions/guardrail/update_rules.py
git commit -m "feat(budpipeline): add guardrail.update_rule_model_ids action"
```

---

### Task 2.5: Implement parallel_simulate Action (EVENT_DRIVEN)

**Files:**
- Create: `budpipeline/actions/guardrail/parallel_simulate.py`

**Step 1: Create the action file**

```python
"""Parallel Simulate Action.

Runs budsim simulations for multiple models in parallel.
Part of D3 hybrid cluster recommendation strategy.
"""

from __future__ import annotations

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


class ParallelSimulateExecutor(BaseActionExecutor):
    """Executor for parallel model simulations."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Start simulations for all models in parallel."""
        models = context.params.get("models", [])
        hardware_mode = context.params.get("hardware_mode", "dedicated")

        if not models:
            return ActionResult(
                success=True,
                outputs={"results": [], "all_completed": True},
            )

        logger.info(
            "parallel_simulate_starting",
            step_id=context.step_id,
            model_count=len(models),
            hardware_mode=hardware_mode,
        )

        simulation_ids = []
        pending_results = []

        for model in models:
            deploy_config = model.get("deployment_config", {})

            try:
                response = await context.invoke_service(
                    app_id=settings.budsim_app_id,
                    method_path="/simulator/run",
                    http_method="POST",
                    data={
                        "pretrained_model_uri": model["model_uri"],
                        "model_uri": model["model_uri"],
                        "input_tokens": deploy_config.get("input_tokens", 1024),
                        "output_tokens": deploy_config.get("output_tokens", 128),
                        "concurrency": deploy_config.get("concurrency", 10),
                        "target_ttft": deploy_config.get("target_ttft"),
                        "target_e2e_latency": deploy_config.get("target_e2e_latency"),
                        "hardware_mode": hardware_mode,
                        "is_proprietary_model": False,
                    },
                    timeout_seconds=60,
                )

                sim_workflow_id = response.get("workflow_id")
                simulation_ids.append(str(sim_workflow_id))
                pending_results.append({
                    "model_id": model.get("model_id"),
                    "model_uri": model["model_uri"],
                    "simulation_id": str(sim_workflow_id),
                    "status": "running",
                    "recommendations": None,
                    "deployment_configuration": None,
                })

            except Exception as e:
                logger.error(
                    "parallel_simulate_model_failed",
                    step_id=context.step_id,
                    model_uri=model.get("model_uri"),
                    error=str(e),
                )
                return ActionResult(
                    success=False,
                    outputs={"results": pending_results, "all_completed": False},
                    error=f"Failed to start simulation for {model.get('model_uri')}: {e!s}",
                )

        combined_id = ",".join(simulation_ids)

        return ActionResult(
            success=True,
            outputs={
                "results": pending_results,
                "all_completed": False,
                "pending_simulation_ids": simulation_ids,
            },
            awaiting_event=True,
            external_workflow_id=combined_id,
            timeout_seconds=context.params.get("max_wait_seconds", 300),
        )

    async def on_event(self, context: EventContext) -> EventResult:
        """Process simulation completion events."""
        event_type = context.event_data.get("type", "")
        workflow_id = context.event_data.get("workflow_id", "")

        if event_type not in ("simulation_completed", "workflow_completed"):
            return EventResult(action=EventAction.IGNORE)

        current_results = context.step_outputs.get("results", [])

        # Update matching result
        status = context.event_data.get("status", "UNKNOWN")

        for result in current_results:
            if result.get("simulation_id") == workflow_id:
                if status == "COMPLETED":
                    result["status"] = "completed"
                    result["recommendations"] = context.event_data.get("recommendations", [])
                    result["deployment_configuration"] = context.event_data.get("deployment_configuration")
                    # Extract cluster IDs from recommendations
                    result["cluster_ids"] = [
                        r.get("cluster_id") for r in result["recommendations"] if r.get("cluster_id")
                    ]
                else:
                    result["status"] = "failed"
                    result["error"] = context.event_data.get("reason", "Simulation failed")
                break

        completed = sum(1 for r in current_results if r.get("status") == "completed")
        failed = sum(1 for r in current_results if r.get("status") == "failed")
        total = len(current_results)

        if failed > 0:
            return EventResult(
                action=EventAction.COMPLETE,
                status=StepStatus.FAILED,
                outputs={"results": current_results, "all_completed": False},
                error=f"Simulation failed for {failed}/{total} models",
            )

        if completed == total:
            return EventResult(
                action=EventAction.COMPLETE,
                status=StepStatus.COMPLETED,
                outputs={"results": current_results, "all_completed": True},
            )

        return EventResult(
            action=EventAction.UPDATE_OUTPUTS,
            outputs={
                "results": current_results,
                "all_completed": False,
                "pending_simulation_ids": context.step_outputs.get("pending_simulation_ids", []),
            },
        )


META = ActionMeta(
    type="guardrail.parallel_simulate",
    version="1.0.0",
    name="Parallel Model Simulations",
    description="Run budsim simulations for multiple models in parallel",
    category="Guardrail",
    icon="chart-bar",
    color="#8B5CF6",
    execution_mode=ExecutionMode.EVENT_DRIVEN,
    timeout_seconds=300,
    idempotent=False,
    required_services=["budsim"],
    params=[
        ParamDefinition(
            name="models",
            label="Models",
            type=ParamType.JSON,
            required=True,
            description="Array of models with deployment config",
        ),
        ParamDefinition(
            name="hardware_mode",
            label="Hardware Mode",
            type=ParamType.STRING,
            required=True,
            description="dedicated or shared",
        ),
        ParamDefinition(
            name="max_wait_seconds",
            label="Max Wait Time",
            type=ParamType.NUMBER,
            required=False,
            default=300,
        ),
    ],
    outputs=[
        OutputDefinition(
            name="results",
            type="json",
            description="Simulation results per model",
        ),
        OutputDefinition(
            name="all_completed",
            type="boolean",
            description="Whether all simulations completed",
        ),
    ],
)


@register_action(META)
class ParallelSimulateAction:
    """Parallel simulate action for entry point registration."""

    meta = META
    executor_class = ParallelSimulateExecutor
```

**Step 2: Commit**

```bash
git add budpipeline/actions/guardrail/parallel_simulate.py
git commit -m "feat(budpipeline): add guardrail.parallel_simulate action"
```

---

### Task 2.6: Implement aggregate_requirements Action (SYNC)

**Files:**
- Create: `budpipeline/actions/guardrail/aggregate_requirements.py`

**Step 1: Create the action file**

```python
"""Aggregate Requirements Action.

Aggregates resource requirements from parallel simulations
and finds candidate clusters that appear in all recommendation lists.
"""

from __future__ import annotations

import structlog

from budpipeline.actions.base import (
    ActionContext,
    ActionMeta,
    ActionResult,
    BaseActionExecutor,
    ExecutionMode,
    OutputDefinition,
    ParamDefinition,
    ParamType,
    register_action,
)

logger = structlog.get_logger(__name__)


class AggregateRequirementsExecutor(BaseActionExecutor):
    """Executor for aggregating simulation requirements."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Aggregate requirements and find candidate clusters."""
        simulation_results = context.params.get("simulation_results", [])

        if not simulation_results:
            return ActionResult(
                success=True,
                outputs={
                    "candidate_clusters": [],
                    "total_requirements": {"total_memory_gb": 0, "total_replicas": 0},
                    "per_model_requirements": [],
                },
            )

        logger.info(
            "aggregate_requirements_starting",
            step_id=context.step_id,
            result_count=len(simulation_results),
        )

        # Extract per-model requirements
        per_model_requirements = []
        cluster_sets = []

        for result in simulation_results:
            config = result.get("deployment_configuration", {})
            node_groups = config.get("node_groups", [])

            # Sum memory across node groups
            total_weight = sum(ng.get("weight_memory_gb", 0) for ng in node_groups)
            total_kv_cache = sum(ng.get("kv_cache_memory_gb", 0) for ng in node_groups)
            total_replicas = config.get("replica", 1)

            per_model_requirements.append({
                "model_id": result.get("model_id"),
                "model_uri": result.get("model_uri"),
                "weight_memory_gb": total_weight,
                "kv_cache_memory_gb": total_kv_cache,
                "total_memory_gb": total_weight + total_kv_cache,
                "replicas": total_replicas,
            })

            # Collect cluster IDs from this model's recommendations
            cluster_ids = set(result.get("cluster_ids", []))
            if cluster_ids:
                cluster_sets.append(cluster_ids)

        # Find clusters that appear in ALL recommendation lists
        if cluster_sets:
            candidate_clusters = list(set.intersection(*cluster_sets))
        else:
            candidate_clusters = []

        # Sum total requirements
        total_requirements = {
            "total_memory_gb": sum(m["total_memory_gb"] for m in per_model_requirements),
            "total_replicas": sum(m["replicas"] for m in per_model_requirements),
        }

        logger.info(
            "aggregate_requirements_complete",
            step_id=context.step_id,
            candidate_cluster_count=len(candidate_clusters),
            total_memory_gb=total_requirements["total_memory_gb"],
        )

        return ActionResult(
            success=True,
            outputs={
                "candidate_clusters": candidate_clusters,
                "total_requirements": total_requirements,
                "per_model_requirements": per_model_requirements,
            },
        )


META = ActionMeta(
    type="guardrail.aggregate_requirements",
    version="1.0.0",
    name="Aggregate Resource Requirements",
    description="Sum resource requirements from simulations and find candidate clusters",
    category="Guardrail",
    icon="calculator",
    color="#EC4899",
    execution_mode=ExecutionMode.SYNC,
    idempotent=True,
    params=[
        ParamDefinition(
            name="simulation_results",
            label="Simulation Results",
            type=ParamType.JSON,
            required=True,
            description="Results from parallel simulations",
        ),
    ],
    outputs=[
        OutputDefinition(
            name="candidate_clusters",
            type="json",
            description="Cluster IDs that appear in all recommendations",
        ),
        OutputDefinition(
            name="total_requirements",
            type="json",
            description="Summed resource requirements",
        ),
        OutputDefinition(
            name="per_model_requirements",
            type="json",
            description="Requirements breakdown per model",
        ),
    ],
)


@register_action(META)
class AggregateRequirementsAction:
    """Aggregate requirements action for entry point registration."""

    meta = META
    executor_class = AggregateRequirementsExecutor
```

**Step 2: Commit**

```bash
git add budpipeline/actions/guardrail/aggregate_requirements.py
git commit -m "feat(budpipeline): add guardrail.aggregate_requirements action"
```

---

### Task 2.7: Implement validate_cluster_fit Action (SYNC)

**Files:**
- Create: `budpipeline/actions/guardrail/validate_cluster_fit.py`

**Step 1: Create the action file**

```python
"""Validate Cluster Fit Action.

Sequentially validates that candidate clusters can fit all models.
Final step of D3 hybrid cluster recommendation strategy.
"""

from __future__ import annotations

import structlog

from budpipeline.actions.base import (
    ActionContext,
    ActionMeta,
    ActionResult,
    BaseActionExecutor,
    ExecutionMode,
    OutputDefinition,
    ParamDefinition,
    ParamType,
    register_action,
)
from budpipeline.commons.config import settings

logger = structlog.get_logger(__name__)


class ValidateClusterFitExecutor(BaseActionExecutor):
    """Executor for validating cluster fit."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Validate each candidate cluster can fit all models."""
        candidate_clusters = context.params.get("candidate_clusters", [])
        total_requirements = context.params.get("total_requirements", {})
        models = context.params.get("models", [])

        if not candidate_clusters:
            return ActionResult(
                success=True,
                outputs={
                    "valid_clusters": [],
                    "per_model_configs": models,
                    "message": "No candidate clusters to validate",
                },
            )

        total_memory_needed = total_requirements.get("total_memory_gb", 0)

        logger.info(
            "validate_cluster_fit_starting",
            step_id=context.step_id,
            candidate_count=len(candidate_clusters),
            total_memory_needed=total_memory_needed,
        )

        valid_clusters = []

        for cluster_id in candidate_clusters:
            try:
                response = await context.invoke_service(
                    app_id=settings.budcluster_app_id,
                    method_path=f"/clusters/{cluster_id}/resources",
                    http_method="GET",
                    timeout_seconds=30,
                )

                cluster_data = response.get("data", response)
                available_memory = cluster_data.get("available_memory_gb", 0)
                cluster_name = cluster_data.get("name", cluster_id)

                if available_memory >= total_memory_needed:
                    valid_clusters.append({
                        "cluster_id": cluster_id,
                        "cluster_name": cluster_name,
                        "available_memory_gb": available_memory,
                        "required_memory_gb": total_memory_needed,
                        "headroom_gb": available_memory - total_memory_needed,
                    })

            except Exception as e:
                logger.warning(
                    "validate_cluster_fit_error",
                    step_id=context.step_id,
                    cluster_id=cluster_id,
                    error=str(e),
                )
                # Skip this cluster but continue with others
                continue

        logger.info(
            "validate_cluster_fit_complete",
            step_id=context.step_id,
            valid_count=len(valid_clusters),
        )

        return ActionResult(
            success=True,
            outputs={
                "valid_clusters": valid_clusters,
                "per_model_configs": models,
            },
        )


META = ActionMeta(
    type="guardrail.validate_cluster_fit",
    version="1.0.0",
    name="Validate Cluster Fit",
    description="Sequential validation that clusters can fit all models",
    category="Guardrail",
    icon="check-circle",
    color="#22C55E",
    execution_mode=ExecutionMode.SYNC,
    idempotent=True,
    required_services=["budcluster"],
    params=[
        ParamDefinition(
            name="candidate_clusters",
            label="Candidate Clusters",
            type=ParamType.JSON,
            required=True,
            description="Cluster IDs to validate",
        ),
        ParamDefinition(
            name="total_requirements",
            label="Total Requirements",
            type=ParamType.JSON,
            required=True,
            description="Aggregated resource requirements",
        ),
        ParamDefinition(
            name="models",
            label="Models",
            type=ParamType.JSON,
            required=True,
            description="Model configurations",
        ),
    ],
    outputs=[
        OutputDefinition(
            name="valid_clusters",
            type="json",
            description="Clusters that can fit all models",
        ),
        OutputDefinition(
            name="per_model_configs",
            type="json",
            description="Model configurations passed through",
        ),
    ],
)


@register_action(META)
class ValidateClusterFitAction:
    """Validate cluster fit action for entry point registration."""

    meta = META
    executor_class = ValidateClusterFitExecutor
```

**Step 2: Commit**

```bash
git add budpipeline/actions/guardrail/validate_cluster_fit.py
git commit -m "feat(budpipeline): add guardrail.validate_cluster_fit action"
```

---

### Task 2.8: Register Entry Points in pyproject.toml

**Files:**
- Modify: `budpipeline/pyproject.toml`

**Step 1: Add guardrail action entry points after line 94**

```toml
# Guardrail Actions
guardrail_validate_credential = "budpipeline.actions.guardrail.validate_credential:ValidateCredentialAction"
guardrail_batch_onboard = "budpipeline.actions.guardrail.batch_onboard:BatchOnboardAction"
guardrail_update_rule_model_ids = "budpipeline.actions.guardrail.update_rules:UpdateRuleModelIdsAction"
guardrail_parallel_simulate = "budpipeline.actions.guardrail.parallel_simulate:ParallelSimulateAction"
guardrail_aggregate_requirements = "budpipeline.actions.guardrail.aggregate_requirements:AggregateRequirementsAction"
guardrail_validate_cluster_fit = "budpipeline.actions.guardrail.validate_cluster_fit:ValidateClusterFitAction"
guardrail_deploy_models = "budpipeline.actions.guardrail.deploy_models:DeployModelsAction"
guardrail_create_profile = "budpipeline.actions.guardrail.create_profile:CreateProfileAction"
guardrail_create_deployment = "budpipeline.actions.guardrail.create_deployment:CreateDeploymentAction"
guardrail_build_config = "budpipeline.actions.guardrail.build_config:BuildConfigAction"
guardrail_sync_redis = "budpipeline.actions.guardrail.sync_redis:SyncRedisAction"
guardrail_rollback = "budpipeline.actions.guardrail.rollback:RollbackAction"
```

**Step 2: Commit**

```bash
git add budpipeline/pyproject.toml
git commit -m "feat(budpipeline): register guardrail action entry points"
```

---

## Phase 3: Remaining Pipeline Actions

### Task 3.1: Implement deploy_models Action (EVENT_DRIVEN)

**Files:**
- Create: `budpipeline/actions/guardrail/deploy_models.py`

*(Similar pattern to batch_onboard - calls budcluster deployment API, waits for events)*

### Task 3.2: Implement create_profile Action (SYNC)

**Files:**
- Create: `budpipeline/actions/guardrail/create_profile.py`

*(Calls budapp to create GuardrailProfile with probe selections)*

### Task 3.3: Implement create_deployment Action (SYNC)

**Files:**
- Create: `budpipeline/actions/guardrail/create_deployment.py`

*(Creates GuardrailDeployment and GuardrailRuleDeployment records)*

### Task 3.4: Implement build_config Action (SYNC)

**Files:**
- Create: `budpipeline/actions/guardrail/build_config.py`

*(Builds the guardrail config JSON structure)*

### Task 3.5: Implement sync_redis Action (SYNC)

**Files:**
- Create: `budpipeline/actions/guardrail/sync_redis.py`

*(Writes config to Redis guardrail_table)*

### Task 3.6: Implement rollback Action (SYNC)

**Files:**
- Create: `budpipeline/actions/guardrail/rollback.py`

*(Deletes endpoints, cleans Redis, removes deployment records)*

---

## Phase 4: Workflow Service Integration (budapp)

### Task 4.1: Add Internal Endpoints for Pipeline Actions

**Files:**
- Create: `budapp/guardrails/internal_routes.py`

*(Add /internal/guardrails/rules/{id}/model PATCH endpoint)*
*(Add /internal/guardrails/redis/{profile_id} DELETE endpoint)*

### Task 4.2: Implement Model Status Derivation

**Files:**
- Modify: `budapp/guardrails/services.py`

*(Add _derive_model_status method that queries Endpoint table)*

### Task 4.3: Refactor Workflow Step Handlers

**Files:**
- Modify: `budapp/guardrails/services.py`

*(Update each step handler to use new schema and trigger pipelines)*

### Task 4.4: Add Pipeline Triggering and Progress Polling

**Files:**
- Modify: `budapp/guardrails/services.py`

*(Use BudPipelineService to run pipelines and poll progress)*

### Task 4.5: Implement Workflow Cancellation with Rollback

**Files:**
- Modify: `budapp/guardrails/services.py`

*(Add cancel_workflow method that triggers rollback pipeline)*

---

## Phase 5: Testing

### Task 5.1: Unit Tests for Schema Extensions

**Files:**
- Create: `tests/guardrails/test_model_status_schema.py`

### Task 5.2: Unit Tests for Pipeline Actions

**Files:**
- Create: `tests/actions/guardrail/test_validate_credential.py`
- Create: `tests/actions/guardrail/test_batch_onboard.py`
- Create: `tests/actions/guardrail/test_aggregate_requirements.py`

### Task 5.3: Integration Tests for Pipelines

**Files:**
- Create: `tests/integration/test_guardrail_onboarding_pipeline.py`
- Create: `tests/integration/test_guardrail_recommendation_pipeline.py`
- Create: `tests/integration/test_guardrail_deployment_pipeline.py`

### Task 5.4: End-to-End Workflow Tests

**Files:**
- Create: `tests/e2e/test_guardrail_workflow.py`

---

## Execution Notes

- Each task is designed to be committed independently
- Phases can be worked on in parallel by different engineers:
  - Phase 1 (budapp schemas) + Phase 2 (budpipeline actions) can run in parallel
  - Phase 4 depends on Phases 1-3
  - Phase 5 can start as soon as code is available
- Use `ruff check . --fix && ruff format .` before each commit
- Run `pytest` for affected test files before committing

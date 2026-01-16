"""Workflow service for managing DAGs and executions."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from budpipeline.commons.config import settings
from budpipeline.commons.constants import ExecutionStatus, StepStatus
from budpipeline.commons.exceptions import (
    CyclicDependencyError,
    DAGParseError,
    DAGValidationError,
    ExecutionNotFoundError,
    WorkflowNotFoundError,
)
from budpipeline.engine.condition_evaluator import ConditionEvaluator
from budpipeline.engine.dag_parser import DAGParser
from budpipeline.engine.dependency_resolver import DependencyResolver
from budpipeline.engine.param_resolver import ParamResolver
from budpipeline.engine.schemas import OnFailureAction
from budpipeline.handlers.base import HandlerContext, HandlerResult
from budpipeline.handlers.registry import global_registry

logger = logging.getLogger(__name__)


class WorkflowStorage:
    """In-memory storage for workflows and executions.

    TODO: Replace with Dapr state store in production.
    """

    def __init__(self) -> None:
        self.workflows: dict[str, dict[str, Any]] = {}
        self.executions: dict[str, dict[str, Any]] = {}

    def save_workflow(self, workflow_id: str, data: dict[str, Any]) -> None:
        self.workflows[workflow_id] = data

    def get_workflow(self, workflow_id: str) -> dict[str, Any] | None:
        return self.workflows.get(workflow_id)

    def list_workflows(self) -> list[dict[str, Any]]:
        return list(self.workflows.values())

    def delete_workflow(self, workflow_id: str) -> bool:
        if workflow_id in self.workflows:
            del self.workflows[workflow_id]
            return True
        return False

    def save_execution(self, execution_id: str, data: dict[str, Any]) -> None:
        self.executions[execution_id] = data

    def get_execution(self, execution_id: str) -> dict[str, Any] | None:
        return self.executions.get(execution_id)

    def list_executions(self, workflow_id: str | None = None) -> list[dict[str, Any]]:
        if workflow_id:
            return [e for e in self.executions.values() if e.get("workflow_id") == workflow_id]
        return list(self.executions.values())


# Global storage instance
storage = WorkflowStorage()


class WorkflowService:
    """Service for managing workflow DAGs and executions."""

    def __init__(self) -> None:
        self.storage = storage

    def validate_dag(self, dag_dict: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
        """Validate a DAG definition.

        Args:
            dag_dict: DAG definition dict

        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        errors: list[str] = []
        warnings: list[str] = []

        try:
            dag = DAGParser.parse(dag_dict)

            # Check for cycles
            resolver = DependencyResolver(dag)
            resolver.get_execution_order()

            # Validate parameter references
            available_params = {p.name for p in dag.parameters}
            step_ids = {s.id for s in dag.steps}

            for step in dag.steps:
                # Check param references
                param_errors = ParamResolver.validate_references(
                    step.params,
                    available_params,
                    step_ids,
                )
                errors.extend(param_errors)

                # Check condition references
                if step.condition:
                    cond_errors = ConditionEvaluator.validate(
                        step.condition,
                        available_params,
                        step_ids,
                    )
                    errors.extend(cond_errors)

                # Check dependencies reference valid steps
                for dep_id in step.depends_on:
                    if dep_id not in step_ids:
                        errors.append(f"Step '{step.id}' depends on unknown step '{dep_id}'")

            # Check for unregistered actions
            for step in dag.steps:
                if not global_registry.has(step.action):
                    warnings.append(f"Action '{step.action}' is not registered")

        except DAGParseError as e:
            errors.append(str(e))
        except CyclicDependencyError as e:
            errors.append(str(e))
        except DAGValidationError as e:
            errors.extend(e.errors if e.errors else [str(e)])

        return (len(errors) == 0, errors, warnings)

    def create_workflow(
        self, dag_dict: dict[str, Any], name_override: str | None = None
    ) -> dict[str, Any]:
        """Create/register a workflow from DAG definition.

        Args:
            dag_dict: DAG definition dict
            name_override: Optional name override

        Returns:
            Workflow metadata dict
        """
        # Check if this is a draft workflow (empty or no steps)
        steps = dag_dict.get("steps") or []
        is_draft = len(steps) == 0

        if is_draft:
            # For draft workflows, skip full validation but ensure required fields exist
            if "name" not in dag_dict and not name_override:
                raise DAGValidationError(
                    "Workflow name is required", errors=["name: Field required"]
                )

            # Create a minimal parsed representation for drafts
            name = name_override or dag_dict.get("name", "Untitled Workflow")
            version = dag_dict.get("version", "1.0.0")
            warnings = []
        else:
            # Validate first for non-empty workflows
            is_valid, errors, warnings = self.validate_dag(dag_dict)
            if not is_valid:
                raise DAGValidationError("DAG validation failed", errors=errors)

            # Parse DAG
            dag = DAGParser.parse(dag_dict)
            name = name_override or dag.name
            version = dag.version

        # Generate workflow ID
        workflow_id = str(uuid4())

        workflow_data = {
            "id": workflow_id,
            "name": name,
            "version": version,
            "status": "draft" if is_draft else "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "step_count": len(steps),
            "dag": dag_dict,
            "warnings": warnings,
        }

        self.storage.save_workflow(workflow_id, workflow_data)

        logger.info(f"Created workflow: {workflow_id} ({name})")
        return workflow_data

    def get_workflow(self, workflow_id: str) -> dict[str, Any]:
        """Get workflow by ID."""
        workflow = self.storage.get_workflow(workflow_id)
        if not workflow:
            raise WorkflowNotFoundError(workflow_id)
        return workflow

    def list_workflows(self) -> list[dict[str, Any]]:
        """List all workflows."""
        return self.storage.list_workflows()

    def delete_workflow(self, workflow_id: str) -> bool:
        """Delete a workflow."""
        return self.storage.delete_workflow(workflow_id)

    def update_workflow(
        self, workflow_id: str, dag_dict: dict[str, Any], name_override: str | None = None
    ) -> dict[str, Any]:
        """Update an existing workflow.

        Args:
            workflow_id: Workflow ID to update
            dag_dict: Updated DAG definition dict
            name_override: Optional name override

        Returns:
            Updated workflow metadata dict

        Raises:
            WorkflowNotFoundError: If workflow doesn't exist
            DAGValidationError: If DAG validation fails
        """
        # Get existing workflow (raises WorkflowNotFoundError if not found)
        existing = self.get_workflow(workflow_id)

        # Check if this is a draft workflow (empty or no steps)
        steps = dag_dict.get("steps") or []
        is_draft = len(steps) == 0

        if is_draft:
            # For draft workflows, skip full validation
            name = name_override or dag_dict.get("name", existing.get("name", "Untitled"))
            version = dag_dict.get("version", existing.get("version", "1.0.0"))
            warnings: list[str] = []
        else:
            # Validate for non-empty workflows
            is_valid, errors, warnings = self.validate_dag(dag_dict)
            if not is_valid:
                raise DAGValidationError("DAG validation failed", errors=errors)
            dag = DAGParser.parse(dag_dict)
            name = name_override or dag.name
            version = dag.version

        # Update workflow data
        workflow_data = {
            "id": workflow_id,
            "name": name,
            "version": version,
            "status": "draft" if is_draft else "active",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "created_at": existing.get("created_at"),
            "step_count": len(steps),
            "dag": dag_dict,
            "warnings": warnings,
        }

        # Save to storage
        self.storage.save_workflow(workflow_id, workflow_data)

        logger.info(f"Updated workflow: {workflow_id} ({name})")
        return workflow_data

    async def execute_workflow(self, workflow_id: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a workflow.

        Args:
            workflow_id: Workflow ID to execute
            params: Input parameters

        Returns:
            Execution result dict

        Raises:
            DAGValidationError: If workflow has no steps (is still a draft)
        """
        workflow = self.get_workflow(workflow_id)

        # Check if workflow has steps before executing
        dag_dict = workflow.get("dag", {})
        steps = dag_dict.get("steps") or []
        if len(steps) == 0:
            raise DAGValidationError(
                "Cannot execute a draft workflow with no steps",
                errors=["steps: At least one step is required to execute workflow"],
            )

        dag = DAGParser.parse(dag_dict)

        execution_id = str(uuid4())
        started_at = datetime.now(timezone.utc)

        # Merge provided params with DAG defaults
        merged_params = {}
        for param in dag.parameters:
            if param.name in params:
                merged_params[param.name] = params[param.name]
            elif param.default is not None:
                merged_params[param.name] = param.default
        # Include any extra params not in DAG definition
        for key, value in params.items():
            if key not in merged_params:
                merged_params[key] = value

        # Initialize execution state
        execution_data = {
            "execution_id": execution_id,
            "workflow_id": workflow_id,
            "workflow_name": workflow["name"],
            "status": ExecutionStatus.RUNNING.value,
            "started_at": started_at.isoformat(),
            "completed_at": None,
            "params": merged_params,
            "outputs": {},
            "error": None,
            "steps": {},
        }

        # Initialize step states
        for step in dag.steps:
            execution_data["steps"][step.id] = {
                "step_id": step.id,
                "name": step.name,
                "status": StepStatus.PENDING.value,
                "started_at": None,
                "completed_at": None,
                "outputs": {},
                "error": None,
            }

        self.storage.save_execution(execution_id, execution_data)

        logger.info(f"Starting execution: {execution_id} for workflow {workflow_id}")

        try:
            # Get execution order
            resolver = DependencyResolver(dag)
            batches = resolver.get_execution_order()

            step_outputs: dict[str, dict[str, Any]] = {}

            # Execute batches
            for batch in batches:
                for step in batch:
                    step_state = execution_data["steps"][step.id]

                    if step_state["status"] == StepStatus.SKIPPED.value:
                        continue

                    step_state["status"] = StepStatus.RUNNING.value
                    step_state["started_at"] = datetime.now(timezone.utc).isoformat()
                    self.storage.save_execution(execution_id, execution_data)

                    # Check condition
                    if step.condition:
                        should_run = ConditionEvaluator.evaluate(
                            step.condition, merged_params, step_outputs
                        )
                        if not should_run:
                            step_state["status"] = StepStatus.SKIPPED.value
                            step_state["completed_at"] = datetime.now(timezone.utc).isoformat()
                            self.storage.save_execution(execution_id, execution_data)
                            logger.info(f"Step {step.id} skipped (condition not met)")
                            continue

                    # Resolve parameters
                    resolved_params = ParamResolver.resolve_dict(
                        step.params, merged_params, step_outputs
                    )

                    # Execute handler
                    if global_registry.has(step.action):
                        if step.retry:
                            max_attempts = step.retry.max_attempts
                            backoff_seconds = step.retry.backoff_seconds
                            backoff_multiplier = step.retry.backoff_multiplier
                            max_backoff_seconds = step.retry.max_backoff_seconds
                        else:
                            max_attempts = settings.retry_max_attempts
                            backoff_seconds = settings.retry_backoff_seconds
                            backoff_multiplier = settings.retry_backoff_multiplier
                            max_backoff_seconds = settings.retry_max_backoff_seconds

                        attempt = 0
                        result: HandlerResult | None = None

                        while attempt < max_attempts:
                            context = HandlerContext(
                                step_id=step.id,
                                execution_id=execution_id,
                                params=resolved_params,
                                workflow_params=merged_params,
                                step_outputs=step_outputs,
                                timeout_seconds=step.timeout_seconds,
                                retry_count=attempt,
                            )

                            result = await global_registry.execute(step.action, context)

                            if result.success:
                                break

                            attempt += 1
                            if step.on_failure != OnFailureAction.RETRY or attempt >= max_attempts:
                                break

                            step_state["status"] = StepStatus.RETRYING.value
                            step_state["error"] = result.error
                            self.storage.save_execution(execution_id, execution_data)

                            await asyncio.sleep(backoff_seconds)
                            backoff_seconds = min(
                                int(backoff_seconds * backoff_multiplier),
                                max_backoff_seconds,
                            )

                        if not result:
                            raise Exception("Handler execution failed without a result")

                        if result.success:
                            step_state["status"] = StepStatus.COMPLETED.value
                            step_state["outputs"] = result.outputs
                            step_outputs[step.id] = result.outputs

                            # Handle conditional branch routing
                            if step.action == "conditional" and resolved_params.get("branches"):
                                matched_target = result.outputs.get("target_step")
                                branches = resolved_params.get("branches", [])

                                # Mark non-matching branch targets as skipped
                                for branch in branches:
                                    target = branch.get("target_step")
                                    if target and target != matched_target:
                                        # Find the step node by stepId
                                        target_step_id = target
                                        if target_step_id in execution_data["steps"]:
                                            target_state = execution_data["steps"][target_step_id]
                                            if target_state["status"] == StepStatus.PENDING.value:
                                                target_state["status"] = StepStatus.SKIPPED.value
                                                target_state["completed_at"] = datetime.now(
                                                    timezone.utc
                                                ).isoformat()
                                                target_state["error"] = (
                                                    "Branch condition not matched "
                                                    f"(matched: {result.outputs.get('matched_label', 'none')})"
                                                )
                                                logger.info(
                                                    "Step %s skipped (branch '%s' not matched)",
                                                    target_step_id,
                                                    branch.get("label"),
                                                )
                        else:
                            step_state["status"] = StepStatus.FAILED.value
                            step_state["error"] = result.error
                            logger.warning(
                                "Step %s failed%s: %s",
                                step.id,
                                " after retries"
                                if step.on_failure == OnFailureAction.RETRY
                                else "",
                                result.error,
                            )

                            if step.on_failure == OnFailureAction.CONTINUE:
                                logger.warning(
                                    "Step %s failed but continuing: %s",
                                    step.id,
                                    result.error,
                                )
                            else:
                                step_state["completed_at"] = datetime.now(timezone.utc).isoformat()
                                self.storage.save_execution(execution_id, execution_data)
                                raise Exception(result.error or "Step execution failed")
                    else:
                        # Mock execution for unregistered handlers
                        logger.warning(f"Handler not found for {step.action}, using mock")
                        step_state["status"] = StepStatus.COMPLETED.value
                        step_state["outputs"] = {"mock": True, "params": resolved_params}
                        step_outputs[step.id] = step_state["outputs"]

                    step_state["completed_at"] = datetime.now(timezone.utc).isoformat()
                    self.storage.save_execution(execution_id, execution_data)

            # Resolve workflow outputs
            if dag.outputs:
                execution_data["outputs"] = ParamResolver.resolve_dict(
                    dag.outputs, merged_params, step_outputs
                )

            execution_data["status"] = ExecutionStatus.COMPLETED.value
            execution_data["completed_at"] = datetime.now(timezone.utc).isoformat()

            logger.info(f"Execution completed: {execution_id}")

        except Exception as e:
            execution_data["status"] = ExecutionStatus.FAILED.value
            execution_data["error"] = str(e)
            failure_time = datetime.now(timezone.utc).isoformat()
            execution_data["completed_at"] = failure_time

            for step_state in execution_data["steps"].values():
                if step_state["status"] in {
                    StepStatus.PENDING.value,
                    StepStatus.RUNNING.value,
                    StepStatus.RETRYING.value,
                }:
                    step_state["status"] = StepStatus.SKIPPED.value
                    step_state["completed_at"] = failure_time
                    step_state.setdefault("error", "Workflow aborted")

            logger.error(f"Execution failed: {execution_id} - {e}")

        self.storage.save_execution(execution_id, execution_data)
        return execution_data

    def get_execution(self, execution_id: str) -> dict[str, Any]:
        """Get execution by ID."""
        execution = self.storage.get_execution(execution_id)
        if not execution:
            raise ExecutionNotFoundError(execution_id)
        return execution

    def list_executions(self, workflow_id: str | None = None) -> list[dict[str, Any]]:
        """List executions, optionally filtered by workflow."""
        return self.storage.list_executions(workflow_id)


# Global service instance
workflow_service = WorkflowService()

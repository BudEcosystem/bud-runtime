"""Workflow service for managing DAGs and executions."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

# New action architecture (002-pipeline-event-persistence)
from budpipeline.actions.base import ActionContext, ActionResult, action_registry
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
from budpipeline.pipeline.crud import PipelineDefinitionCRUD
from budpipeline.pipeline.models import PipelineStatus

logger = logging.getLogger(__name__)


# Import persistence service for database persistence (002-pipeline-event-persistence)
# Using lazy import to avoid circular dependency
_persistence_service = None


def get_persistence_service():
    """Get persistence service instance with lazy loading."""
    global _persistence_service
    if _persistence_service is None:
        from budpipeline.pipeline.persistence_service import persistence_service

        _persistence_service = persistence_service
    return _persistence_service


class ExecutionStorage:
    """In-memory storage for execution state during workflow execution.

    This is used to track real-time execution state during workflow runs.
    Persistent storage is handled via the database (PipelineExecution model).
    """

    def __init__(self) -> None:
        self.executions: dict[str, dict[str, Any]] = {}

    def save_execution(self, execution_id: str, data: dict[str, Any]) -> None:
        self.executions[execution_id] = data

    def get_execution(self, execution_id: str) -> dict[str, Any] | None:
        return self.executions.get(execution_id)

    def list_executions(self, workflow_id: str | None = None) -> list[dict[str, Any]]:
        if workflow_id:
            return [e for e in self.executions.values() if e.get("workflow_id") == workflow_id]
        return list(self.executions.values())

    def delete_execution(self, execution_id: str) -> bool:
        if execution_id in self.executions:
            del self.executions[execution_id]
            return True
        return False


# Global execution storage instance (for real-time state during workflow execution)
execution_storage = ExecutionStorage()


# Keep WorkflowStorage as an alias for backwards compatibility (deprecated)
class WorkflowStorage(ExecutionStorage):
    """Deprecated: Use ExecutionStorage for execution state.

    Workflow definitions are now stored in the database via PipelineDefinition model.
    """

    def __init__(self) -> None:
        super().__init__()
        self.workflows: dict[str, dict[str, Any]] = {}

    def save_workflow(self, workflow_id: str, data: dict[str, Any]) -> None:
        """Deprecated: Workflows are now stored in database."""
        self.workflows[workflow_id] = data

    def get_workflow(self, workflow_id: str) -> dict[str, Any] | None:
        """Deprecated: Workflows are now stored in database."""
        return self.workflows.get(workflow_id)

    def list_workflows(self) -> list[dict[str, Any]]:
        """Deprecated: Workflows are now stored in database."""
        return list(self.workflows.values())

    def delete_workflow(self, workflow_id: str) -> bool:
        """Deprecated: Workflows are now stored in database."""
        if workflow_id in self.workflows:
            del self.workflows[workflow_id]
            return True
        return False


# Global storage instance (deprecated, use execution_storage)
storage = WorkflowStorage()


class WorkflowService:
    """Service for managing workflow DAGs and executions.

    This service provides both sync (deprecated, uses in-memory storage) and
    async (uses database via CRUD) methods for workflow management.

    For new code, use the async methods with a database session:
    - create_workflow_async(session, dag_dict, name_override, created_by)
    - get_workflow_async(session, workflow_id)
    - list_workflows_async(session)
    - update_workflow_async(session, workflow_id, dag_dict, name_override)
    - delete_workflow_async(session, workflow_id)
    """

    def __init__(self) -> None:
        self.storage = storage
        self.execution_storage = execution_storage

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

            # Check for unregistered actions (using new action_registry)
            for step in dag.steps:
                if not action_registry.has(step.action):
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

    # =========================================================================
    # Async Database Methods (002-pipeline-event-persistence)
    # These methods use the database for persistent workflow storage
    # =========================================================================

    async def create_workflow_async(
        self,
        session: AsyncSession,
        dag_dict: dict[str, Any],
        name_override: str | None = None,
        created_by: str = "api",
        description: str | None = None,
    ) -> dict[str, Any]:
        """Create/register a workflow from DAG definition (database persistence).

        Args:
            session: Database session.
            dag_dict: DAG definition dict.
            name_override: Optional name override.
            created_by: User or service creating the workflow.
            description: Optional workflow description.

        Returns:
            Workflow metadata dict.
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
            name = name_override or dag_dict.get("name", "Untitled Workflow")
        else:
            # Validate first for non-empty workflows
            is_valid, errors, _ = self.validate_dag(dag_dict)
            if not is_valid:
                raise DAGValidationError("DAG validation failed", errors=errors)

            dag = DAGParser.parse(dag_dict)
            name = name_override or dag.name

        # Create in database
        crud = PipelineDefinitionCRUD(session)
        status = PipelineStatus.DRAFT if is_draft else PipelineStatus.ACTIVE

        definition = await crud.create(
            name=name,
            dag_definition=dag_dict,
            created_by=created_by,
            description=description,
            status=status,
        )
        await session.commit()

        logger.info(f"Created workflow in database: {definition.id} ({name})")

        return {
            "id": str(definition.id),
            "name": definition.name,
            "version": str(definition.version),
            "status": definition.status.value,
            "created_at": definition.created_at.isoformat(),
            "updated_at": definition.updated_at.isoformat(),
            "step_count": definition.step_count,
            "dag": definition.dag_definition,
            "created_by": definition.created_by,
            "description": definition.description,
        }

    async def get_workflow_async(
        self,
        session: AsyncSession,
        workflow_id: str,
    ) -> dict[str, Any]:
        """Get workflow by ID from database.

        Args:
            session: Database session.
            workflow_id: Workflow ID (UUID string).

        Returns:
            Workflow metadata dict.

        Raises:
            WorkflowNotFoundError: If workflow not found.
        """
        try:
            definition_id = UUID(workflow_id)
        except ValueError:
            raise WorkflowNotFoundError(workflow_id)

        crud = PipelineDefinitionCRUD(session)
        definition = await crud.get_by_id(definition_id)

        if definition is None:
            raise WorkflowNotFoundError(workflow_id)

        execution_count = await crud.get_execution_count(definition_id)

        return {
            "id": str(definition.id),
            "name": definition.name,
            "version": str(definition.version),
            "status": definition.status.value,
            "created_at": definition.created_at.isoformat(),
            "updated_at": definition.updated_at.isoformat(),
            "step_count": definition.step_count,
            "dag": definition.dag_definition,
            "created_by": definition.created_by,
            "description": definition.description,
            "execution_count": execution_count,
        }

    async def list_workflows_async(
        self,
        session: AsyncSession,
        status: PipelineStatus | None = None,
        created_by: str | None = None,
    ) -> list[dict[str, Any]]:
        """List all workflows from database.

        Args:
            session: Database session.
            status: Filter by pipeline status.
            created_by: Filter by creator.

        Returns:
            List of workflow metadata dicts.
        """
        crud = PipelineDefinitionCRUD(session)
        definitions = await crud.list_all(status=status, created_by=created_by)

        return [
            {
                "id": str(d.id),
                "name": d.name,
                "version": str(d.version),
                "status": d.status.value,
                "created_at": d.created_at.isoformat(),
                "updated_at": d.updated_at.isoformat(),
                "step_count": d.step_count,
                "dag": d.dag_definition,
                "created_by": d.created_by,
                "description": d.description,
            }
            for d in definitions
        ]

    async def update_workflow_async(
        self,
        session: AsyncSession,
        workflow_id: str,
        dag_dict: dict[str, Any],
        name_override: str | None = None,
        expected_version: int | None = None,
    ) -> dict[str, Any]:
        """Update an existing workflow in database.

        Args:
            session: Database session.
            workflow_id: Workflow ID to update.
            dag_dict: Updated DAG definition dict.
            name_override: Optional name override.
            expected_version: Version for optimistic locking (if not provided, current version is used).

        Returns:
            Updated workflow metadata dict.

        Raises:
            WorkflowNotFoundError: If workflow doesn't exist.
            DAGValidationError: If DAG validation fails.
        """
        try:
            definition_id = UUID(workflow_id)
        except ValueError:
            raise WorkflowNotFoundError(workflow_id)

        crud = PipelineDefinitionCRUD(session)
        existing = await crud.get_by_id(definition_id)

        if existing is None:
            raise WorkflowNotFoundError(workflow_id)

        # Use provided version or current version for optimistic locking
        version = expected_version if expected_version is not None else existing.version

        # Check if this is a draft workflow (empty or no steps)
        steps = dag_dict.get("steps") or []
        is_draft = len(steps) == 0

        if is_draft:
            name = name_override or dag_dict.get("name", existing.name)
        else:
            is_valid, errors, _ = self.validate_dag(dag_dict)
            if not is_valid:
                raise DAGValidationError("DAG validation failed", errors=errors)
            dag = DAGParser.parse(dag_dict)
            name = name_override or dag.name

        status = PipelineStatus.DRAFT if is_draft else PipelineStatus.ACTIVE

        definition = await crud.update_with_version(
            definition_id=definition_id,
            expected_version=version,
            name=name,
            dag_definition=dag_dict,
            status=status,
        )
        await session.commit()

        logger.info(f"Updated workflow in database: {definition.id} ({name})")

        return {
            "id": str(definition.id),
            "name": definition.name,
            "version": str(definition.version),
            "status": definition.status.value,
            "created_at": definition.created_at.isoformat(),
            "updated_at": definition.updated_at.isoformat(),
            "step_count": definition.step_count,
            "dag": definition.dag_definition,
            "created_by": definition.created_by,
            "description": definition.description,
        }

    async def delete_workflow_async(
        self,
        session: AsyncSession,
        workflow_id: str,
    ) -> bool:
        """Delete a workflow from database.

        Args:
            session: Database session.
            workflow_id: Workflow ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        try:
            definition_id = UUID(workflow_id)
        except ValueError:
            return False

        crud = PipelineDefinitionCRUD(session)
        deleted = await crud.delete(definition_id)

        if deleted:
            await session.commit()
            logger.info(f"Deleted workflow from database: {workflow_id}")

        return deleted

    async def execute_workflow_async(
        self,
        session: AsyncSession,
        workflow_id: str,
        params: dict[str, Any],
        callback_topics: list[str] | None = None,
        initiator: str = "api",
    ) -> dict[str, Any]:
        """Execute a workflow from database.

        This method fetches the workflow from database and executes it,
        linking the execution to the pipeline definition via pipeline_id.

        Args:
            session: Database session.
            workflow_id: Workflow ID to execute.
            params: Input parameters.
            callback_topics: Optional list of callback topics for real-time updates.
            initiator: User or service that initiated execution.

        Returns:
            Execution result dict.

        Raises:
            WorkflowNotFoundError: If workflow not found.
            DAGValidationError: If workflow has no steps (is still a draft).
        """
        # Get workflow from database
        workflow = await self.get_workflow_async(session, workflow_id)
        dag_dict = workflow.get("dag", {})
        steps = dag_dict.get("steps") or []

        if len(steps) == 0:
            raise DAGValidationError(
                "Cannot execute a draft workflow with no steps",
                errors=["steps: At least one step is required to execute workflow"],
            )

        # Get the pipeline_id for linking execution
        pipeline_id = UUID(workflow_id)

        # Use the existing execute_workflow_with_definition method
        return await self._execute_workflow_impl(
            workflow=workflow,
            params=params,
            callback_topics=callback_topics,
            initiator=initiator,
            pipeline_id=pipeline_id,
        )

    async def _execute_workflow_impl(
        self,
        workflow: dict[str, Any],
        params: dict[str, Any],
        callback_topics: list[str] | None = None,
        initiator: str = "api",
        pipeline_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Internal implementation for workflow execution.

        This method executes a workflow using the provided workflow data.
        Used by both execute_workflow (in-memory) and execute_workflow_async (database).

        Args:
            workflow: Workflow data dict.
            params: Input parameters.
            callback_topics: Optional list of callback topics for real-time updates.
            initiator: User or service that initiated execution.
            pipeline_id: Optional pipeline definition ID for linking.

        Returns:
            Execution result dict.
        """
        dag_dict = workflow.get("dag", {})
        dag = DAGParser.parse(dag_dict)

        execution_id = str(uuid4())
        started_at = datetime.now(timezone.utc)
        workflow_id = workflow.get("id", "unknown")

        # Persist execution to database (002-pipeline-event-persistence)
        db_version = 1  # Track version for optimistic locking
        # Track step DB info: step_id -> (db_uuid, version, sequence_number)
        step_db_info: dict[str, tuple[UUID, int, int]] = {}
        db_execution_id: UUID | None = None
        try:
            persistence = get_persistence_service()
            pipeline_definition = {
                "workflow_id": workflow_id,
                "workflow_name": workflow["name"],
                "dag": dag_dict,
                "params": params,
            }
            db_execution_id, db_version = await persistence.create_execution(
                pipeline_definition=pipeline_definition,
                initiator=initiator,
                callback_topics=callback_topics,
                pipeline_id=pipeline_id,
            )
            # Use the DB-generated UUID if available
            execution_id = str(db_execution_id)
            logger.info(f"Persisted execution to database: {execution_id}, version={db_version}")

            # Create step records in database (1-indexed for DB constraint)
            step_records = [
                {
                    "step_id": step.id,
                    "step_name": step.name,
                    "sequence_number": idx + 1,
                }
                for idx, step in enumerate(dag.steps)
            ]
            if step_records:
                try:
                    created_steps = await persistence.create_steps_for_execution(
                        execution_id=db_execution_id,
                        steps=step_records,
                    )
                    # Build mapping: step_id -> (db_uuid, version, sequence_number)
                    for (db_uuid, step_id, version), record in zip(
                        created_steps, step_records, strict=False
                    ):
                        step_db_info[step_id] = (db_uuid, version, record["sequence_number"])
                    logger.info(
                        f"Created {len(step_records)} step records for execution {execution_id}"
                    )
                except Exception as step_err:
                    logger.warning(f"Failed to create step records: {step_err}")

            # Update execution status to RUNNING with start_time
            try:
                from budpipeline.pipeline.models import ExecutionStatus as DBExecutionStatus

                success, db_version = await persistence.update_execution_status(
                    execution_id=db_execution_id,
                    expected_version=db_version,
                    status=DBExecutionStatus.RUNNING,
                    start_time_value=started_at,
                )
                if success:
                    logger.info(f"Updated execution {execution_id} to RUNNING with start_time")
            except Exception as status_err:
                logger.warning(f"Failed to update execution status to RUNNING: {status_err}")

        except Exception as e:
            # Log but continue - execution can proceed without DB persistence
            logger.warning(f"Failed to persist execution to database: {e}")

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

        self.execution_storage.save_execution(execution_id, execution_data)

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
                    step_started_at = datetime.now(timezone.utc)
                    step_state["started_at"] = step_started_at.isoformat()
                    self.execution_storage.save_execution(execution_id, execution_data)

                    # Persist step RUNNING to database
                    if step.id in step_db_info:
                        try:
                            persistence = get_persistence_service()
                            from budpipeline.pipeline.models import StepStatus as DBStepStatus

                            db_uuid, step_version, seq_num = step_db_info[step.id]
                            success, new_version = await persistence.update_step_status(
                                step_uuid=db_uuid,
                                expected_version=step_version,
                                status=DBStepStatus.RUNNING,
                                start_time_value=step_started_at,
                                execution_id=db_execution_id,
                                step_id=step.id,
                                step_name=step.name,
                                sequence_number=seq_num,
                            )
                            if success:
                                step_db_info[step.id] = (db_uuid, new_version, seq_num)
                        except Exception as e:
                            logger.warning(f"Failed to persist step RUNNING status: {e}")

                    # Check condition
                    if step.condition:
                        should_run = ConditionEvaluator.evaluate(
                            step.condition, merged_params, step_outputs
                        )
                        if not should_run:
                            step_state["status"] = StepStatus.SKIPPED.value
                            step_skipped_at = datetime.now(timezone.utc)
                            step_state["completed_at"] = step_skipped_at.isoformat()
                            self.execution_storage.save_execution(execution_id, execution_data)
                            logger.info(f"Step {step.id} skipped (condition not met)")
                            # Persist step SKIPPED to database
                            if step.id in step_db_info:
                                try:
                                    persistence = get_persistence_service()
                                    from budpipeline.pipeline.models import (
                                        StepStatus as DBStepStatus,
                                    )

                                    db_uuid, step_version, seq_num = step_db_info[step.id]
                                    await persistence.update_step_status(
                                        step_uuid=db_uuid,
                                        expected_version=step_version,
                                        status=DBStepStatus.SKIPPED,
                                        end_time_value=step_skipped_at,
                                        execution_id=db_execution_id,
                                        step_id=step.id,
                                        step_name=step.name,
                                        sequence_number=seq_num,
                                    )
                                except Exception as e:
                                    logger.warning(f"Failed to persist step SKIPPED status: {e}")
                            continue

                    # Resolve parameters
                    resolved_params = ParamResolver.resolve_dict(
                        step.params, merged_params, step_outputs
                    )

                    # Execute action using action_registry
                    if action_registry.has(step.action):
                        # Get retry policy from action metadata or step config
                        action_meta = action_registry.get_meta(step.action)
                        if step.retry:
                            max_attempts = step.retry.max_attempts
                            backoff_seconds = step.retry.backoff_seconds
                            backoff_multiplier = step.retry.backoff_multiplier
                            max_backoff_seconds = step.retry.max_backoff_seconds
                        elif action_meta and action_meta.retry_policy:
                            max_attempts = action_meta.retry_policy.max_attempts
                            backoff_seconds = action_meta.retry_policy.initial_interval_seconds
                            backoff_multiplier = action_meta.retry_policy.backoff_multiplier
                            max_backoff_seconds = settings.retry_max_backoff_seconds
                        else:
                            max_attempts = settings.retry_max_attempts
                            backoff_seconds = settings.retry_backoff_seconds
                            backoff_multiplier = settings.retry_backoff_multiplier
                            max_backoff_seconds = settings.retry_max_backoff_seconds

                        # Use timeout from action meta if not specified in step
                        timeout_seconds = step.timeout_seconds
                        if timeout_seconds is None and action_meta:
                            timeout_seconds = action_meta.timeout_seconds

                        attempt = 0
                        result: ActionResult | None = None

                        while attempt < max_attempts:
                            # Create ActionContext for new actions
                            action_context = ActionContext(
                                step_id=step.id,
                                execution_id=execution_id,
                                params=resolved_params,
                                workflow_params=merged_params,
                                step_outputs=step_outputs,
                                timeout_seconds=timeout_seconds,
                                retry_count=attempt,
                            )

                            # Execute via action registry
                            executor = action_registry.get_executor(step.action)
                            result = await executor.execute(action_context)

                            if result.success:
                                break

                            attempt += 1
                            if step.on_failure != OnFailureAction.RETRY or attempt >= max_attempts:
                                break

                            step_state["status"] = StepStatus.RETRYING.value
                            step_state["error"] = result.error
                            self.execution_storage.save_execution(execution_id, execution_data)

                            await asyncio.sleep(backoff_seconds)
                            backoff_seconds = min(
                                int(backoff_seconds * backoff_multiplier),
                                max_backoff_seconds,
                            )

                        if not result:
                            raise Exception("Action execution failed without a result")

                        if result.success:
                            # Check if handler is waiting for external event (event-driven completion)
                            if result.awaiting_event and result.external_workflow_id:
                                # Event-driven step: mark as RUNNING + awaiting_event
                                step_state["status"] = StepStatus.RUNNING.value
                                step_state["outputs"] = result.outputs
                                step_state["awaiting_event"] = True
                                step_state["external_workflow_id"] = result.external_workflow_id
                                # Store partial outputs for later merge
                                step_outputs[step.id] = result.outputs

                                # Calculate timeout
                                timeout_seconds = (
                                    result.timeout_seconds or settings.default_async_step_timeout
                                )
                                timeout_at = datetime.now(timezone.utc) + timedelta(
                                    seconds=timeout_seconds
                                )

                                logger.info(
                                    f"Step {step.id} awaiting event from workflow "
                                    f"{result.external_workflow_id}, timeout_at={timeout_at}"
                                )

                                # Persist step as awaiting event in database
                                if step.id in step_db_info:
                                    try:
                                        persistence = get_persistence_service()
                                        db_uuid, step_version, seq_num = step_db_info[step.id]
                                        (
                                            success,
                                            new_version,
                                        ) = await persistence.mark_step_awaiting_event(
                                            step_uuid=db_uuid,
                                            expected_version=step_version,
                                            external_workflow_id=result.external_workflow_id,
                                            handler_type=step.action,
                                            timeout_at=timeout_at,
                                            outputs=result.outputs,
                                        )
                                        if success:
                                            step_db_info[step.id] = (db_uuid, new_version, seq_num)
                                            logger.info(
                                                f"Persisted step {step.id} awaiting event, "
                                                f"external_workflow_id={result.external_workflow_id}"
                                            )
                                    except Exception as e:
                                        logger.warning(
                                            f"Failed to persist step awaiting event: {e}"
                                        )

                                # Step stays RUNNING, don't set completed_at
                                # Continue to next step or return execution as RUNNING
                                self.execution_storage.save_execution(execution_id, execution_data)
                                continue  # Continue to next step in batch

                            # Synchronous completion
                            step_state["status"] = StepStatus.COMPLETED.value
                            step_state["outputs"] = result.outputs
                            step_outputs[step.id] = result.outputs
                            step_completed_at = datetime.now(timezone.utc)

                            # Persist step COMPLETED to database
                            if step.id in step_db_info:
                                try:
                                    persistence = get_persistence_service()
                                    from decimal import Decimal

                                    from budpipeline.pipeline.models import (
                                        StepStatus as DBStepStatus,
                                    )

                                    db_uuid, step_version, seq_num = step_db_info[step.id]
                                    await persistence.update_step_status(
                                        step_uuid=db_uuid,
                                        expected_version=step_version,
                                        status=DBStepStatus.COMPLETED,
                                        progress_percentage=Decimal("100.00"),
                                        end_time_value=step_completed_at,
                                        outputs=result.outputs,
                                        execution_id=db_execution_id,
                                        step_id=step.id,
                                        step_name=step.name,
                                        sequence_number=seq_num,
                                    )
                                except Exception as e:
                                    logger.warning(f"Failed to persist step COMPLETED status: {e}")

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
                            step_failed_at = datetime.now(timezone.utc)
                            logger.warning(
                                "Step %s failed%s: %s",
                                step.id,
                                " after retries"
                                if step.on_failure == OnFailureAction.RETRY
                                else "",
                                result.error,
                            )

                            # Persist step FAILED to database
                            if step.id in step_db_info:
                                try:
                                    persistence = get_persistence_service()
                                    from budpipeline.pipeline.models import (
                                        StepStatus as DBStepStatus,
                                    )

                                    db_uuid, step_version, seq_num = step_db_info[step.id]
                                    await persistence.update_step_status(
                                        step_uuid=db_uuid,
                                        expected_version=step_version,
                                        status=DBStepStatus.FAILED,
                                        end_time_value=step_failed_at,
                                        error_message=result.error,
                                        execution_id=db_execution_id,
                                        step_id=step.id,
                                        step_name=step.name,
                                        sequence_number=seq_num,
                                    )
                                except Exception as e:
                                    logger.warning(f"Failed to persist step FAILED status: {e}")

                            if step.on_failure == OnFailureAction.CONTINUE:
                                logger.warning(
                                    "Step %s failed but continuing: %s",
                                    step.id,
                                    result.error,
                                )
                            else:
                                step_state["completed_at"] = datetime.now(timezone.utc).isoformat()
                                self.execution_storage.save_execution(execution_id, execution_data)
                                raise Exception(result.error or "Step execution failed")
                    else:
                        # Mock execution for unregistered handlers
                        logger.warning(f"Handler not found for {step.action}, using mock")
                        step_state["status"] = StepStatus.COMPLETED.value
                        step_state["outputs"] = {"mock": True, "params": resolved_params}
                        step_outputs[step.id] = step_state["outputs"]

                    step_state["completed_at"] = datetime.now(timezone.utc).isoformat()
                    self.execution_storage.save_execution(execution_id, execution_data)

            # Resolve workflow outputs
            if dag.outputs:
                execution_data["outputs"] = ParamResolver.resolve_dict(
                    dag.outputs, merged_params, step_outputs
                )

            # Check if any steps are still awaiting external events
            steps_awaiting_events = [
                step_id
                for step_id, step_state in execution_data["steps"].items()
                if step_state.get("awaiting_event", False)
                and step_state["status"] == StepStatus.RUNNING.value
            ]

            if steps_awaiting_events:
                # Execution stays in RUNNING state until all event-driven steps complete
                logger.info(
                    f"Execution {execution_id} has {len(steps_awaiting_events)} steps "
                    f"awaiting events: {steps_awaiting_events}. Staying in RUNNING state."
                )
                self.execution_storage.save_execution(execution_id, execution_data)
                # Don't mark as COMPLETED - wait for events to complete the steps
            else:
                # All steps completed synchronously - mark execution as COMPLETED
                execution_data["status"] = ExecutionStatus.COMPLETED.value
                execution_data["completed_at"] = datetime.now(timezone.utc).isoformat()

                logger.info(f"Execution completed: {execution_id}")

                # Update database with completion (002-pipeline-event-persistence)
                try:
                    persistence = get_persistence_service()
                    from decimal import Decimal

                    from budpipeline.pipeline.models import ExecutionStatus as DBExecutionStatus

                    success, new_version = await persistence.update_execution_status(
                        execution_id=UUID(execution_id),
                        expected_version=db_version,
                        status=DBExecutionStatus.COMPLETED,
                        progress_percentage=Decimal("100.00"),
                        end_time_value=datetime.now(timezone.utc),
                        final_outputs=execution_data.get("outputs"),
                    )
                    if success:
                        db_version = new_version
                        logger.info(f"Persisted completion to database: {execution_id}")
                except Exception as persist_err:
                    logger.warning(f"Failed to persist completion to database: {persist_err}")

        except Exception as e:
            execution_data["status"] = ExecutionStatus.FAILED.value
            execution_data["error"] = str(e)
            failure_time = datetime.now(timezone.utc).isoformat()
            execution_data["completed_at"] = failure_time

            for step_id, step_state in execution_data["steps"].items():
                if step_state["status"] in {
                    StepStatus.PENDING.value,
                    StepStatus.RUNNING.value,
                    StepStatus.RETRYING.value,
                }:
                    step_state["status"] = StepStatus.SKIPPED.value
                    step_state["completed_at"] = failure_time
                    step_state.setdefault("error", "Workflow aborted")

                    # Persist step SKIPPED/CANCELLED to database
                    if step_id in step_db_info:
                        try:
                            persistence = get_persistence_service()
                            from budpipeline.pipeline.models import StepStatus as DBStepStatus

                            db_uuid, step_version, seq_num = step_db_info[step_id]
                            await persistence.update_step_status(
                                step_uuid=db_uuid,
                                expected_version=step_version,
                                status=DBStepStatus.SKIPPED,
                                end_time_value=datetime.fromisoformat(failure_time),
                                error_message="Workflow aborted",
                                execution_id=db_execution_id,
                                step_id=step_id,
                                step_name=step_state.get("name", step_id),
                                sequence_number=seq_num,
                            )
                        except Exception as persist_step_err:
                            logger.warning(
                                f"Failed to persist step SKIPPED status: {persist_step_err}"
                            )

            logger.error(f"Execution failed: {execution_id} - {e}")

            # Update database with failure (002-pipeline-event-persistence)
            try:
                persistence = get_persistence_service()
                from budpipeline.pipeline.models import ExecutionStatus as DBExecutionStatus

                await persistence.update_execution_status(
                    execution_id=UUID(execution_id),
                    expected_version=db_version,
                    status=DBExecutionStatus.FAILED,
                    end_time_value=datetime.now(timezone.utc),
                    error_info={"error": str(e)},
                )
                logger.info(f"Persisted failure to database: {execution_id}")
            except Exception as persist_err:
                logger.warning(f"Failed to persist failure to database: {persist_err}")

        self.execution_storage.save_execution(execution_id, execution_data)
        return execution_data

    async def execute_workflow(
        self,
        workflow_id: str,
        params: dict[str, Any],
        callback_topics: list[str] | None = None,
        initiator: str = "api",
    ) -> dict[str, Any]:
        """Execute a workflow (from in-memory storage).

        This method uses in-memory storage for backwards compatibility.
        For new code using database persistence, use execute_workflow_async().

        Args:
            workflow_id: Workflow ID to execute.
            params: Input parameters.
            callback_topics: Optional list of callback topics for real-time updates.
            initiator: User or service that initiated execution.

        Returns:
            Execution result dict.

        Raises:
            DAGValidationError: If workflow has no steps (is still a draft).
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

        # Delegate to the shared implementation
        return await self._execute_workflow_impl(
            workflow=workflow,
            params=params,
            callback_topics=callback_topics,
            initiator=initiator,
            pipeline_id=None,  # No pipeline_id for in-memory workflows
        )

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

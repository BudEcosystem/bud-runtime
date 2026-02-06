"""Pipeline service for managing DAGs and executions."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

# New action architecture (002-pipeline-event-persistence)
from budpipeline.actions.base import ActionContext, ActionResult, action_registry
from budpipeline.commons.config import settings
from budpipeline.commons.constants import ExecutionStatus, StepStatus
from budpipeline.commons.exceptions import (
    CyclicDependencyError,
    DAGParseError,
    DAGValidationError,
    DuplicatePipelineNameError,
    ExecutionNotFoundError,
    WorkflowNotFoundError,
)
from budpipeline.engine.condition_evaluator import ConditionEvaluator
from budpipeline.engine.dag_parser import DAGParser
from budpipeline.engine.dependency_resolver import DependencyResolver
from budpipeline.engine.param_resolver import ParamResolver
from budpipeline.engine.schemas import OnFailureAction
from budpipeline.pipeline.crud import PipelineDefinitionCRUD
from budpipeline.pipeline.models import PipelineExecution, PipelineStatus

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


class PipelineService:
    """Service for managing pipeline DAGs and executions.

    This service provides both sync (deprecated, uses in-memory storage) and
    async (uses database via CRUD) methods for pipeline management.

    For new code, use the async methods with a database session:
    - create_pipeline_async(session, dag_dict, name_override, created_by, user_id, system_owned)
    - get_pipeline_async(session, pipeline_id)
    - get_pipeline_async_for_user(session, pipeline_id, user_id)
    - list_pipelines_async(session, user_id, include_system)
    - update_pipeline_async(session, pipeline_id, dag_dict, name_override)
    - delete_pipeline_async(session, pipeline_id)
    """

    def __init__(self) -> None:
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

            # Validate action params against action metadata (required params, validation rules)
            for step in dag.steps:
                action_meta = action_registry.get_meta(step.action)
                if action_meta:
                    param_errors = self._validate_action_params(
                        step.id, step.params, action_meta.params
                    )
                    errors.extend(param_errors)

        except DAGParseError as e:
            errors.append(str(e))
        except CyclicDependencyError as e:
            errors.append(str(e))
        except DAGValidationError as e:
            errors.extend(e.errors if e.errors else [str(e)])

        return (len(errors) == 0, errors, warnings)

    def _validate_action_params(
        self,
        step_id: str,
        step_params: dict[str, Any],
        param_definitions: list,
    ) -> list[str]:
        """Validate step params against action's parameter definitions.

        Args:
            step_id: Step identifier for error messages
            step_params: Parameters provided in the step
            param_definitions: List of ParamDefinition from action metadata

        Returns:
            List of validation error messages
        """
        errors: list[str] = []

        for param_def in param_definitions:
            param_name = param_def.name
            param_value = step_params.get(param_name)

            # Check required params
            if param_def.required:
                # Value is missing, None, or empty string
                if param_value is None or param_value == "":
                    errors.append(
                        f"Step '{step_id}': Required parameter '{param_name}' is missing or empty"
                    )
                    continue

            # Skip further validation if value is not provided (optional param)
            if param_value is None:
                continue

            # Validate against ValidationRules if present
            if param_def.validation:
                rules = param_def.validation

                # Min/max for numbers
                if rules.min is not None and isinstance(param_value, int | float):
                    if param_value < rules.min:
                        errors.append(
                            f"Step '{step_id}': Parameter '{param_name}' value {param_value} "
                            f"is less than minimum {rules.min}"
                        )

                if rules.max is not None and isinstance(param_value, int | float):
                    if param_value > rules.max:
                        errors.append(
                            f"Step '{step_id}': Parameter '{param_name}' value {param_value} "
                            f"exceeds maximum {rules.max}"
                        )

                # Min/max length for strings
                if rules.min_length is not None and isinstance(param_value, str):
                    if len(param_value) < rules.min_length:
                        errors.append(
                            f"Step '{step_id}': Parameter '{param_name}' length {len(param_value)} "
                            f"is less than minimum {rules.min_length}"
                        )

                if rules.max_length is not None and isinstance(param_value, str):
                    if len(param_value) > rules.max_length:
                        errors.append(
                            f"Step '{step_id}': Parameter '{param_name}' length {len(param_value)} "
                            f"exceeds maximum {rules.max_length}"
                        )

        return errors

    # =========================================================================
    # Async Database Methods (002-pipeline-event-persistence)
    # These methods use the database for persistent pipeline storage
    # =========================================================================

    async def create_pipeline_async(
        self,
        session: AsyncSession,
        dag_dict: dict[str, Any],
        name_override: str | None = None,
        created_by: str = "api",
        description: str | None = None,
        user_id: UUID | None = None,
        system_owned: bool = False,
    ) -> dict[str, Any]:
        """Create/register a pipeline from DAG definition (database persistence).

        Args:
            session: Database session.
            dag_dict: DAG definition dict.
            name_override: Optional name override.
            created_by: User or service creating the pipeline.
            description: Optional pipeline description.
            user_id: UUID of the owning user (None for system/anonymous pipelines).
            system_owned: True if this is a system-owned pipeline visible to all users.

        Returns:
            Pipeline metadata dict.
        """
        # Check if this is a draft pipeline (empty or no steps)
        steps = dag_dict.get("steps") or []
        is_draft = len(steps) == 0

        if is_draft:
            # For draft pipelines, skip full validation but ensure required fields exist
            if "name" not in dag_dict and not name_override:
                raise DAGValidationError(
                    "Pipeline name is required", errors=["name: Field required"]
                )
            name = name_override or dag_dict.get("name", "Untitled Pipeline")
        else:
            # Validate first for non-empty pipelines
            is_valid, errors, _ = self.validate_dag(dag_dict)
            if not is_valid:
                raise DAGValidationError("DAG validation failed", errors=errors)

            dag = DAGParser.parse(dag_dict)
            name = name_override or dag.name

        # Create in database
        crud = PipelineDefinitionCRUD(session)

        # Check for duplicate pipeline name within user scope
        if await crud.exists_by_name_for_user(name=name, user_id=user_id):
            raise DuplicatePipelineNameError(
                name=name,
                user_id=str(user_id) if user_id else None,
            )
        status = PipelineStatus.DRAFT if is_draft else PipelineStatus.ACTIVE

        definition = await crud.create(
            name=name,
            dag_definition=dag_dict,
            created_by=created_by,
            description=description,
            status=status,
            user_id=user_id,
            system_owned=system_owned,
        )
        await session.commit()

        logger.info(f"Created pipeline in database: {definition.id} ({name})")

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
            "user_id": str(definition.user_id) if definition.user_id else None,
            "system_owned": definition.system_owned,
        }

    async def get_pipeline_async(
        self,
        session: AsyncSession,
        pipeline_id: str,
    ) -> dict[str, Any]:
        """Get pipeline by ID from database.

        Args:
            session: Database session.
            pipeline_id: Pipeline ID (UUID string).

        Returns:
            Pipeline metadata dict.

        Raises:
            WorkflowNotFoundError: If pipeline not found.
        """
        try:
            definition_id = UUID(pipeline_id)
        except ValueError:
            raise WorkflowNotFoundError(pipeline_id)

        crud = PipelineDefinitionCRUD(session)
        definition = await crud.get_by_id(definition_id)

        if definition is None:
            raise WorkflowNotFoundError(pipeline_id)

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
            "user_id": str(definition.user_id) if definition.user_id else None,
            "system_owned": definition.system_owned,
        }

    async def get_pipeline_async_for_user(
        self,
        session: AsyncSession,
        pipeline_id: str,
        user_id: UUID | None,
    ) -> dict[str, Any]:
        """Get pipeline by ID with user permission check.

        Returns the pipeline if:
        - It belongs to the specified user, OR
        - It is a system-owned pipeline, OR
        - user_id is None (system/admin context)

        Args:
            session: Database session.
            pipeline_id: Pipeline ID (UUID string).
            user_id: User UUID to check ownership. None means system/admin access.

        Returns:
            Pipeline metadata dict.

        Raises:
            WorkflowNotFoundError: If pipeline not found or user doesn't have permission.
        """
        try:
            definition_id = UUID(pipeline_id)
        except ValueError:
            raise WorkflowNotFoundError(pipeline_id)

        crud = PipelineDefinitionCRUD(session)
        definition = await crud.get_by_id_for_user(definition_id, user_id)

        if definition is None:
            raise WorkflowNotFoundError(pipeline_id)

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
            "user_id": str(definition.user_id) if definition.user_id else None,
            "system_owned": definition.system_owned,
        }

    async def list_pipelines_async(
        self,
        session: AsyncSession,
        status: PipelineStatus | None = None,
        created_by: str | None = None,
        user_id: UUID | None = None,
        include_system: bool = False,
    ) -> list[dict[str, Any]]:
        """List all pipelines from database with optional user filtering.

        Args:
            session: Database session.
            status: Filter by pipeline status.
            created_by: Filter by creator.
            user_id: Filter by user_id (returns only pipelines owned by this user).
            include_system: If True, also include system-owned pipelines when filtering by user_id.

        Returns:
            List of pipeline metadata dicts.
        """
        crud = PipelineDefinitionCRUD(session)
        definitions = await crud.list_all(
            status=status,
            created_by=created_by,
            user_id=user_id,
            include_system=include_system,
        )

        # Get execution stats for all pipelines
        pipeline_ids = [d.id for d in definitions]
        execution_stats: dict[UUID, dict[str, Any]] = {}

        if pipeline_ids:
            # Query execution counts and last execution times
            stats_query = (
                select(
                    PipelineExecution.pipeline_id,
                    func.count(PipelineExecution.id).label("execution_count"),
                    func.max(PipelineExecution.created_at).label("last_execution_at"),
                )
                .where(PipelineExecution.pipeline_id.in_(pipeline_ids))
                .group_by(PipelineExecution.pipeline_id)
            )
            result = await session.execute(stats_query)
            for row in result:
                execution_stats[row.pipeline_id] = {
                    "execution_count": row.execution_count,
                    "last_execution_at": row.last_execution_at.isoformat()
                    if row.last_execution_at
                    else None,
                }

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
                "user_id": str(d.user_id) if d.user_id else None,
                "system_owned": d.system_owned,
                "execution_count": execution_stats.get(d.id, {}).get("execution_count", 0),
                "last_execution_at": execution_stats.get(d.id, {}).get("last_execution_at"),
            }
            for d in definitions
        ]

    async def update_pipeline_async(
        self,
        session: AsyncSession,
        pipeline_id: str,
        dag_dict: dict[str, Any],
        name_override: str | None = None,
        expected_version: int | None = None,
    ) -> dict[str, Any]:
        """Update an existing pipeline in database.

        Args:
            session: Database session.
            pipeline_id: Pipeline ID to update.
            dag_dict: Updated DAG definition dict.
            name_override: Optional name override.
            expected_version: Version for optimistic locking (if not provided, current version is used).

        Returns:
            Updated pipeline metadata dict.

        Raises:
            WorkflowNotFoundError: If pipeline doesn't exist.
            DAGValidationError: If DAG validation fails.
        """
        try:
            definition_id = UUID(pipeline_id)
        except ValueError:
            raise WorkflowNotFoundError(pipeline_id)

        crud = PipelineDefinitionCRUD(session)
        existing = await crud.get_by_id(definition_id)

        if existing is None:
            raise WorkflowNotFoundError(pipeline_id)

        # Use provided version or current version for optimistic locking
        version = expected_version if expected_version is not None else existing.version

        # Check if this is a draft pipeline (empty or no steps)
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

        # Check for duplicate pipeline name within user scope (exclude current pipeline)
        if name != existing.name:
            if await crud.exists_by_name_for_user(
                name=name,
                user_id=existing.user_id,
                exclude_id=definition_id,
            ):
                raise DuplicatePipelineNameError(
                    name=name,
                    user_id=str(existing.user_id) if existing.user_id else None,
                )

        status = PipelineStatus.DRAFT if is_draft else PipelineStatus.ACTIVE

        definition = await crud.update_with_version(
            definition_id=definition_id,
            expected_version=version,
            name=name,
            dag_definition=dag_dict,
            status=status,
        )
        await session.commit()

        logger.info(f"Updated pipeline in database: {definition.id} ({name})")

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
            "user_id": str(definition.user_id) if definition.user_id else None,
            "system_owned": definition.system_owned,
        }

    async def delete_pipeline_async(
        self,
        session: AsyncSession,
        pipeline_id: str,
    ) -> bool:
        """Delete a pipeline from database.

        Args:
            session: Database session.
            pipeline_id: Pipeline ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        try:
            definition_id = UUID(pipeline_id)
        except ValueError:
            return False

        crud = PipelineDefinitionCRUD(session)
        deleted = await crud.delete(definition_id)

        if deleted:
            await session.commit()
            logger.info(f"Deleted pipeline from database: {pipeline_id}")

        return deleted

    async def execute_pipeline_async(
        self,
        session: AsyncSession,
        pipeline_id: str,
        params: dict[str, Any],
        callback_topics: list[str] | None = None,
        initiator: str = "api",
    ) -> dict[str, Any]:
        """Execute a pipeline from database.

        This method fetches the pipeline from database and executes it,
        linking the execution to the pipeline definition via pipeline_id.

        Args:
            session: Database session.
            pipeline_id: Pipeline ID to execute.
            params: Input parameters.
            callback_topics: Optional list of callback topics for real-time updates.
            initiator: User or service that initiated execution.

        Returns:
            Execution result dict.

        Raises:
            WorkflowNotFoundError: If pipeline not found.
            DAGValidationError: If pipeline has no steps (is still a draft).
        """
        # Get pipeline from database
        pipeline = await self.get_pipeline_async(session, pipeline_id)
        dag_dict = pipeline.get("dag", {})
        steps = dag_dict.get("steps") or []

        if len(steps) == 0:
            raise DAGValidationError(
                "Cannot execute a draft pipeline with no steps",
                errors=["steps: At least one step is required to execute pipeline"],
            )

        # Get the pipeline_id for linking execution
        pipeline_uuid = UUID(pipeline_id)

        # Use the internal implementation
        return await self._execute_pipeline_impl(
            pipeline=pipeline,
            params=params,
            callback_topics=callback_topics,
            initiator=initiator,
            pipeline_id=pipeline_uuid,
        )

    async def _execute_pipeline_impl(
        self,
        pipeline: dict[str, Any],
        params: dict[str, Any],
        callback_topics: list[str] | None = None,
        initiator: str = "api",
        pipeline_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Internal implementation for pipeline execution.

        This method executes a pipeline using the provided pipeline data.

        Args:
            pipeline: Pipeline data dict.
            params: Input parameters.
            callback_topics: Optional list of callback topics for real-time updates.
            initiator: User or service that initiated execution.
            pipeline_id: Optional pipeline definition ID for linking.

        Returns:
            Execution result dict.
        """
        dag_dict = pipeline.get("dag", {})
        dag = DAGParser.parse(dag_dict)

        execution_id = str(uuid4())
        started_at = datetime.now(timezone.utc)
        workflow_id = pipeline.get("id", "unknown")

        # Persist execution to database (002-pipeline-event-persistence)
        db_version = 1  # Track version for optimistic locking
        # Track step DB info: step_id -> (db_uuid, version, sequence_number)
        step_db_info: dict[str, tuple[UUID, int, int]] = {}
        db_execution_id: UUID | None = None
        try:
            persistence = get_persistence_service()
            pipeline_definition = {
                "workflow_id": workflow_id,
                "workflow_name": pipeline["name"],
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
            "workflow_name": pipeline["name"],
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

                                # IMPORTANT: Step is awaiting an event. Execution must pause here.
                                # Do NOT continue to dependent steps until this step completes.
                                # The event router will trigger continuation when the event arrives.
                                self.execution_storage.save_execution(execution_id, execution_data)
                                logger.info(
                                    f"Execution {execution_id} pausing: step {step.id} awaiting "
                                    f"event. Dependent steps will not run until event completes step."
                                )
                                # Return early - execution stays in RUNNING state
                                return execution_data

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

    def get_execution(self, execution_id: str) -> dict[str, Any]:
        """Get execution by ID."""
        execution = self.execution_storage.get_execution(execution_id)
        if not execution:
            raise ExecutionNotFoundError(execution_id)
        return execution

    def list_executions(self, pipeline_id: str | None = None) -> list[dict[str, Any]]:
        """List executions, optionally filtered by pipeline."""
        return self.execution_storage.list_executions(pipeline_id)


# Global service instance
pipeline_service = PipelineService()

# Backwards compatibility alias
workflow_service = pipeline_service

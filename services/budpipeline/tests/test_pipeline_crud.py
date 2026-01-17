"""Unit tests for pipeline CRUD operations with optimistic locking.

Tests for T029 (002-pipeline-event-persistence):
- PipelineExecution CRUD create/get/update with optimistic locking
- StepExecution CRUD create/get/update with optimistic locking
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from budpipeline.pipeline.crud import (
    OptimisticLockError,
    PipelineExecutionCRUD,
    StepExecutionCRUD,
)
from budpipeline.pipeline.models import (
    ExecutionStatus,
    PipelineExecution,
    StepExecution,
    StepStatus,
)


@pytest.fixture
def mock_session():
    """Create a mock async session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.execute = AsyncMock()
    session.scalar = AsyncMock()
    return session


@pytest.fixture
def sample_execution_id():
    """Generate a sample execution ID."""
    return uuid4()


@pytest.fixture
def sample_pipeline_definition():
    """Sample pipeline definition."""
    return {
        "name": "test-pipeline",
        "version": "1.0",
        "steps": [
            {"id": "step1", "name": "Step 1", "action": "test.action"},
            {"id": "step2", "name": "Step 2", "action": "test.action", "depends_on": ["step1"]},
        ],
    }


class TestPipelineExecutionCRUD:
    """Tests for PipelineExecution CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_execution(self, mock_session, sample_pipeline_definition):
        """Test creating a new pipeline execution."""
        crud = PipelineExecutionCRUD(mock_session)

        # Mock the add operation - when add is called, set the ID
        def mock_add(obj):
            obj.id = uuid4()

        mock_session.add.side_effect = mock_add

        execution = await crud.create(
            pipeline_definition=sample_pipeline_definition,
            initiator="test-user",
        )

        assert execution is not None
        assert execution.pipeline_definition == sample_pipeline_definition
        assert execution.initiator == "test-user"
        assert execution.status == ExecutionStatus.PENDING
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_execution_with_callback_topics(
        self, mock_session, sample_pipeline_definition
    ):
        """Test creating execution with callback topics."""
        crud = PipelineExecutionCRUD(mock_session)

        def mock_add(obj):
            obj.id = uuid4()

        mock_session.add.side_effect = mock_add

        callback_topics = ["topic1", "topic2"]
        execution = await crud.create(
            pipeline_definition=sample_pipeline_definition,
            initiator="test-user",
            callback_topics=callback_topics,
        )

        assert execution is not None
        assert execution.callback_topics == callback_topics

    @pytest.mark.asyncio
    async def test_get_by_id_found(self, mock_session, sample_execution_id):
        """Test getting an execution by ID when it exists."""
        crud = PipelineExecutionCRUD(mock_session)

        # Create mock execution
        mock_execution = MagicMock(spec=PipelineExecution)
        mock_execution.id = sample_execution_id
        mock_execution.status = ExecutionStatus.RUNNING
        mock_session.scalar.return_value = mock_execution

        result = await crud.get_by_id(sample_execution_id)

        assert result is not None
        assert result.id == sample_execution_id
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, mock_session):
        """Test getting an execution by ID when it doesn't exist."""
        crud = PipelineExecutionCRUD(mock_session)
        mock_session.scalar.return_value = None

        result = await crud.get_by_id(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_update_with_version_success(self, mock_session, sample_execution_id):
        """Test successful update with correct version."""
        crud = PipelineExecutionCRUD(mock_session)

        # Mock successful update (1 row updated)
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        # Mock getting the updated execution
        mock_execution = MagicMock(spec=PipelineExecution)
        mock_execution.id = sample_execution_id
        mock_execution.version = 2
        mock_session.scalar.return_value = mock_execution

        result = await crud.update_with_version(
            execution_id=sample_execution_id,
            version=1,
            status=ExecutionStatus.RUNNING,
        )

        assert result is not None
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_with_version_conflict(self, mock_session, sample_execution_id):
        """Test update fails when version doesn't match (optimistic lock)."""
        crud = PipelineExecutionCRUD(mock_session)

        # Mock failed update (0 rows updated - version mismatch)
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute.return_value = mock_result

        with pytest.raises(OptimisticLockError) as exc_info:
            await crud.update_with_version(
                execution_id=sample_execution_id,
                version=1,
                status=ExecutionStatus.COMPLETED,
            )

        assert sample_execution_id in str(exc_info.value)
        mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_status(self, mock_session, sample_execution_id):
        """Test updating execution status."""
        crud = PipelineExecutionCRUD(mock_session)

        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        mock_execution = MagicMock(spec=PipelineExecution)
        mock_execution.id = sample_execution_id
        mock_execution.status = ExecutionStatus.COMPLETED
        mock_session.scalar.return_value = mock_execution

        result = await crud.update_status(
            execution_id=sample_execution_id,
            version=1,
            status=ExecutionStatus.COMPLETED,
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_update_status_with_completed_at(self, mock_session, sample_execution_id):
        """Test updating status also sets completed_at for terminal states."""
        crud = PipelineExecutionCRUD(mock_session)

        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        mock_execution = MagicMock(spec=PipelineExecution)
        mock_execution.id = sample_execution_id
        mock_execution.status = ExecutionStatus.COMPLETED
        mock_execution.completed_at = datetime.now(timezone.utc)
        mock_session.scalar.return_value = mock_execution

        result = await crud.update_status(
            execution_id=sample_execution_id,
            version=1,
            status=ExecutionStatus.COMPLETED,
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_list_paginated(self, mock_session):
        """Test paginated listing of executions."""
        crud = PipelineExecutionCRUD(mock_session)

        # Mock count query
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 25

        # Mock list query
        mock_exec1 = MagicMock(spec=PipelineExecution)
        mock_exec1.id = uuid4()
        mock_exec2 = MagicMock(spec=PipelineExecution)
        mock_exec2.id = uuid4()

        mock_list_result = MagicMock()
        mock_list_result.scalars.return_value.all.return_value = [mock_exec1, mock_exec2]

        # Configure execute to return count first, then list
        mock_session.execute.side_effect = [mock_count_result, mock_list_result]

        executions, total = await crud.list_paginated(page=1, page_size=10)

        assert total == 25
        assert len(executions) == 2


class TestStepExecutionCRUD:
    """Tests for StepExecution CRUD operations."""

    @pytest.fixture
    def sample_step_execution_id(self):
        """Generate a sample step execution ID."""
        return uuid4()

    @pytest.mark.asyncio
    async def test_create_for_execution(self, mock_session, sample_execution_id):
        """Test creating a step execution."""
        crud = StepExecutionCRUD(mock_session)

        def mock_add(obj):
            obj.id = uuid4()

        mock_session.add.side_effect = mock_add

        step = await crud.create_for_execution(
            execution_id=sample_execution_id,
            step_id="step1",
            step_name="First Step",
            handler_type="internal.test.action",
            sequence_number=1,
        )

        assert step is not None
        assert step.step_id == "step1"
        assert step.step_name == "First Step"
        assert step.status == StepStatus.PENDING
        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_batch_for_execution(self, mock_session, sample_execution_id):
        """Test batch creation of step executions."""
        crud = StepExecutionCRUD(mock_session)

        steps_data = [
            {
                "step_id": "step1",
                "step_name": "Step 1",
                "handler_type": "action1",
                "sequence_number": 1,
            },
            {
                "step_id": "step2",
                "step_name": "Step 2",
                "handler_type": "action2",
                "sequence_number": 2,
            },
        ]

        # Mock add_all
        mock_session.add_all = MagicMock()

        steps = await crud.create_batch_for_execution(
            execution_id=sample_execution_id,
            steps=steps_data,
        )

        assert len(steps) == 2
        assert steps[0].step_id == "step1"
        assert steps[1].step_id == "step2"
        mock_session.add_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_execution_id(self, mock_session, sample_execution_id):
        """Test getting all steps for an execution."""
        crud = StepExecutionCRUD(mock_session)

        mock_step1 = MagicMock(spec=StepExecution)
        mock_step1.sequence_number = 1
        mock_step2 = MagicMock(spec=StepExecution)
        mock_step2.sequence_number = 2

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_step1, mock_step2]
        mock_session.execute.return_value = mock_result

        steps = await crud.get_by_execution_id(sample_execution_id)

        assert len(steps) == 2
        # Should be ordered by sequence_number
        assert steps[0].sequence_number == 1
        assert steps[1].sequence_number == 2

    @pytest.mark.asyncio
    async def test_update_with_version_success(self, mock_session, sample_execution_id):
        """Test successful step update with correct version."""
        crud = StepExecutionCRUD(mock_session)
        step_id = uuid4()

        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        mock_step = MagicMock(spec=StepExecution)
        mock_step.id = step_id
        mock_step.version = 2
        mock_step.status = StepStatus.RUNNING
        mock_session.scalar.return_value = mock_step

        result = await crud.update_with_version(
            step_execution_id=step_id,
            version=1,
            status=StepStatus.RUNNING,
            progress_percentage=Decimal("50.00"),
        )

        assert result is not None
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_with_version_conflict(self, mock_session):
        """Test step update fails when version doesn't match."""
        crud = StepExecutionCRUD(mock_session)
        step_id = uuid4()

        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute.return_value = mock_result

        with pytest.raises(OptimisticLockError):
            await crud.update_with_version(
                step_execution_id=step_id,
                version=1,
                status=StepStatus.COMPLETED,
            )

        mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_status(self, mock_session):
        """Test updating step status."""
        crud = StepExecutionCRUD(mock_session)
        step_id = uuid4()

        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        mock_step = MagicMock(spec=StepExecution)
        mock_step.id = step_id
        mock_step.status = StepStatus.COMPLETED
        mock_session.scalar.return_value = mock_step

        result = await crud.update_status(
            step_execution_id=step_id,
            version=1,
            status=StepStatus.COMPLETED,
            progress_percentage=Decimal("100.00"),
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_update_progress(self, mock_session):
        """Test updating step progress percentage."""
        crud = StepExecutionCRUD(mock_session)
        step_id = uuid4()

        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        mock_step = MagicMock(spec=StepExecution)
        mock_step.id = step_id
        mock_step.progress_percentage = Decimal("75.00")
        mock_session.scalar.return_value = mock_step

        result = await crud.update_with_version(
            step_execution_id=step_id,
            version=1,
            progress_percentage=Decimal("75.00"),
        )

        assert result is not None


class TestOptimisticLocking:
    """Tests for optimistic locking behavior."""

    @pytest.mark.asyncio
    async def test_concurrent_updates_cause_conflict(self, mock_session, sample_execution_id):
        """Test that concurrent updates to the same execution cause conflicts."""
        crud = PipelineExecutionCRUD(mock_session)

        # First update succeeds
        mock_result1 = MagicMock()
        mock_result1.rowcount = 1
        mock_session.execute.return_value = mock_result1

        mock_execution = MagicMock(spec=PipelineExecution)
        mock_execution.id = sample_execution_id
        mock_execution.version = 2
        mock_session.scalar.return_value = mock_execution

        result1 = await crud.update_with_version(
            execution_id=sample_execution_id,
            version=1,
            progress_percentage=Decimal("50.00"),
        )
        assert result1 is not None

        # Second update with same version fails (simulating concurrent access)
        mock_result2 = MagicMock()
        mock_result2.rowcount = 0
        mock_session.execute.return_value = mock_result2

        with pytest.raises(OptimisticLockError):
            await crud.update_with_version(
                execution_id=sample_execution_id,
                version=1,  # Same version as first update
                progress_percentage=Decimal("75.00"),
            )

    @pytest.mark.asyncio
    async def test_version_increments_on_update(self, mock_session, sample_execution_id):
        """Test that version is incremented on each successful update."""
        crud = PipelineExecutionCRUD(mock_session)

        # Mock successful update
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        # Version should be 2 after first update from version 1
        mock_execution = MagicMock(spec=PipelineExecution)
        mock_execution.id = sample_execution_id
        mock_execution.version = 2
        mock_session.scalar.return_value = mock_execution

        result = await crud.update_with_version(
            execution_id=sample_execution_id,
            version=1,
            status=ExecutionStatus.RUNNING,
        )

        # The returned execution should have version 2
        assert result.version == 2

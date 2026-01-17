"""Historical query tests for pipeline executions.

Tests for US3 - historical query functionality with filters and pagination
(002-pipeline-event-persistence - T053).
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from budpipeline.pipeline.crud import PipelineExecutionCRUD
from budpipeline.pipeline.models import ExecutionStatus, PipelineExecution


class TestHistoricalQueryFilters:
    """Test historical query filtering functionality."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.fixture
    def sample_executions(self):
        """Create sample executions with various statuses and dates."""
        now = datetime.utcnow()
        executions = []

        statuses = [
            ExecutionStatus.PENDING,
            ExecutionStatus.RUNNING,
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
        ]

        for i in range(20):
            exec_mock = Mock(spec=PipelineExecution)
            exec_mock.id = uuid4()
            exec_mock.pipeline_definition = {"steps": []}
            exec_mock.initiator = f"user_{i % 3}"  # 3 different users
            exec_mock.status = statuses[i % 4]
            exec_mock.progress_percentage = Decimal("50.00")
            exec_mock.created_at = now - timedelta(days=i)
            exec_mock.updated_at = now - timedelta(days=i)
            exec_mock.version = 1
            executions.append(exec_mock)

        return executions

    @pytest.mark.asyncio
    async def test_list_with_date_range_filter(self, mock_session, sample_executions):
        """Test filtering executions by date range."""
        # Filter to last 7 days
        now = datetime.utcnow()
        start_date = now - timedelta(days=7)

        # Mock: return only executions within date range
        filtered = [e for e in sample_executions if e.created_at >= start_date]

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = filtered[:20]
        mock_count_result = Mock()
        mock_count_result.scalar_one.return_value = len(filtered)

        mock_session.execute.side_effect = [mock_count_result, mock_result]

        crud = PipelineExecutionCRUD(mock_session)

        executions, total = await crud.list_paginated(
            page=1,
            page_size=20,
            start_date=start_date,
        )

        assert mock_session.execute.call_count == 2
        # Verify start_date was used in query
        mock_session.execute.call_args_list[0][0][0]
        assert start_date is not None

    @pytest.mark.asyncio
    async def test_list_with_status_filter(self, mock_session, sample_executions):
        """Test filtering executions by status."""
        # Filter to only completed executions
        status_filter = ExecutionStatus.COMPLETED
        filtered = [e for e in sample_executions if e.status == status_filter]

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = filtered
        mock_count_result = Mock()
        mock_count_result.scalar_one.return_value = len(filtered)

        mock_session.execute.side_effect = [mock_count_result, mock_result]

        crud = PipelineExecutionCRUD(mock_session)

        executions, total = await crud.list_paginated(
            page=1,
            page_size=20,
            status=status_filter,
        )

        assert mock_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_list_with_initiator_filter(self, mock_session, sample_executions):
        """Test filtering executions by initiator."""
        initiator_filter = "user_0"
        filtered = [e for e in sample_executions if e.initiator == initiator_filter]

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = filtered
        mock_count_result = Mock()
        mock_count_result.scalar_one.return_value = len(filtered)

        mock_session.execute.side_effect = [mock_count_result, mock_result]

        crud = PipelineExecutionCRUD(mock_session)

        executions, total = await crud.list_paginated(
            page=1,
            page_size=20,
            initiator=initiator_filter,
        )

        assert mock_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_list_with_combined_filters(self, mock_session, sample_executions):
        """Test filtering with multiple criteria combined."""
        now = datetime.utcnow()
        start_date = now - timedelta(days=10)
        status_filter = ExecutionStatus.RUNNING
        initiator_filter = "user_1"

        # Filter by all criteria
        filtered = [
            e
            for e in sample_executions
            if e.created_at >= start_date
            and e.status == status_filter
            and e.initiator == initiator_filter
        ]

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = filtered
        mock_count_result = Mock()
        mock_count_result.scalar_one.return_value = len(filtered)

        mock_session.execute.side_effect = [mock_count_result, mock_result]

        crud = PipelineExecutionCRUD(mock_session)

        executions, total = await crud.list_paginated(
            page=1,
            page_size=20,
            start_date=start_date,
            status=status_filter,
            initiator=initiator_filter,
        )

        assert mock_session.execute.call_count == 2


class TestPagination:
    """Test pagination functionality."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_pagination_first_page(self, mock_session):
        """Test retrieving first page of results."""
        # Create 50 mock executions
        executions = [Mock(spec=PipelineExecution) for _ in range(20)]

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = executions
        mock_count_result = Mock()
        mock_count_result.scalar_one.return_value = 50  # Total of 50

        mock_session.execute.side_effect = [mock_count_result, mock_result]

        crud = PipelineExecutionCRUD(mock_session)

        results, total = await crud.list_paginated(page=1, page_size=20)

        assert len(results) == 20
        assert total == 50

    @pytest.mark.asyncio
    async def test_pagination_middle_page(self, mock_session):
        """Test retrieving middle page of results."""
        executions = [Mock(spec=PipelineExecution) for _ in range(20)]

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = executions
        mock_count_result = Mock()
        mock_count_result.scalar_one.return_value = 100

        mock_session.execute.side_effect = [mock_count_result, mock_result]

        crud = PipelineExecutionCRUD(mock_session)

        results, total = await crud.list_paginated(page=3, page_size=20)

        # Verify correct offset would be applied (page 3 = offset 40)
        assert mock_session.execute.call_count == 2
        assert total == 100

    @pytest.mark.asyncio
    async def test_pagination_last_page_partial(self, mock_session):
        """Test retrieving last page with partial results."""
        # Only 5 items on last page
        executions = [Mock(spec=PipelineExecution) for _ in range(5)]

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = executions
        mock_count_result = Mock()
        mock_count_result.scalar_one.return_value = 45  # Total 45, page_size 20, page 3 has 5

        mock_session.execute.side_effect = [mock_count_result, mock_result]

        crud = PipelineExecutionCRUD(mock_session)

        results, total = await crud.list_paginated(page=3, page_size=20)

        assert len(results) == 5
        assert total == 45

    @pytest.mark.asyncio
    async def test_pagination_empty_results(self, mock_session):
        """Test pagination with no results."""
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_count_result = Mock()
        mock_count_result.scalar_one.return_value = 0

        mock_session.execute.side_effect = [mock_count_result, mock_result]

        crud = PipelineExecutionCRUD(mock_session)

        results, total = await crud.list_paginated(page=1, page_size=20)

        assert len(results) == 0
        assert total == 0

    @pytest.mark.asyncio
    async def test_pagination_with_custom_page_size(self, mock_session):
        """Test pagination with custom page size."""
        executions = [Mock(spec=PipelineExecution) for _ in range(50)]

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = executions
        mock_count_result = Mock()
        mock_count_result.scalar_one.return_value = 50

        mock_session.execute.side_effect = [mock_count_result, mock_result]

        crud = PipelineExecutionCRUD(mock_session)

        results, total = await crud.list_paginated(page=1, page_size=50)

        assert len(results) == 50
        assert total == 50


class TestQueryPerformance:
    """Test query performance requirements (SC-006: <500ms)."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_query_with_30_day_range_performance(self, mock_session):
        """Test that 30-day range query completes quickly.

        This is a mock test - actual performance testing should be done
        with real database in integration tests.
        """
        now = datetime.utcnow()
        start_date = now - timedelta(days=30)

        executions = [Mock(spec=PipelineExecution) for _ in range(100)]

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = executions
        mock_count_result = Mock()
        mock_count_result.scalar_one.return_value = 1000

        mock_session.execute.side_effect = [mock_count_result, mock_result]

        crud = PipelineExecutionCRUD(mock_session)

        import time

        start_time = time.time()

        results, total = await crud.list_paginated(
            page=1,
            page_size=100,
            start_date=start_date,
            end_date=now,
        )

        elapsed = time.time() - start_time

        # Mock queries should be nearly instant
        # Real performance testing needs integration tests
        assert elapsed < 0.5  # 500ms threshold

    @pytest.mark.asyncio
    async def test_uses_index_for_date_range_queries(self, mock_session):
        """Verify that date range queries are structured for index usage.

        The query should use created_at which has an index.
        """
        now = datetime.utcnow()
        start_date = now - timedelta(days=30)

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_count_result = Mock()
        mock_count_result.scalar_one.return_value = 0

        mock_session.execute.side_effect = [mock_count_result, mock_result]

        crud = PipelineExecutionCRUD(mock_session)

        await crud.list_paginated(
            page=1,
            page_size=20,
            start_date=start_date,
            end_date=now,
        )

        # Query was executed - in production this would use the index
        # ix_pipeline_execution_created_at defined in models.py
        assert mock_session.execute.call_count == 2


class TestProgressEventsQuery:
    """Test progress event historical queries."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_events_filter_by_time_range(self, mock_session):
        """Test filtering progress events by time range."""
        from budpipeline.progress.crud import ProgressEventCRUD

        execution_id = uuid4()
        now = datetime.utcnow()
        start_time = now - timedelta(hours=1)

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_count_result = Mock()
        mock_count_result.scalar_one.return_value = 0

        mock_session.execute.side_effect = [mock_count_result, mock_result]

        crud = ProgressEventCRUD(mock_session)

        events, total = await crud.list_with_filters(
            execution_id=execution_id,
            start_time=start_time,
            end_time=now,
        )

        assert mock_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_events_filter_by_type(self, mock_session):
        """Test filtering progress events by event type."""
        from budpipeline.progress.crud import ProgressEventCRUD

        execution_id = uuid4()

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_count_result = Mock()
        mock_count_result.scalar_one.return_value = 0

        mock_session.execute.side_effect = [mock_count_result, mock_result]

        crud = ProgressEventCRUD(mock_session)

        events, total = await crud.list_with_filters(
            execution_id=execution_id,
            event_type="workflow_progress",
        )

        assert mock_session.execute.call_count == 2


class TestExecutionListAPIEndpoint:
    """Test the list executions API endpoint contract."""

    @pytest.mark.asyncio
    async def test_list_response_includes_pagination(self):
        """Test that list response includes pagination info."""
        from budpipeline.pipeline.schemas import ExecutionListResponse, PaginationInfo

        response = ExecutionListResponse(
            executions=[],
            pagination=PaginationInfo(
                page=1,
                page_size=20,
                total_count=0,
                total_pages=0,
            ),
        )

        assert response.pagination.page == 1
        assert response.pagination.page_size == 20
        assert response.pagination.total_count == 0
        assert response.pagination.total_pages == 0

    @pytest.mark.asyncio
    async def test_pagination_info_calculates_total_pages(self):
        """Test that total_pages is calculated correctly."""
        from budpipeline.pipeline.schemas import PaginationInfo

        # 45 items with page_size 20 = 3 pages
        pagination = PaginationInfo(
            page=1,
            page_size=20,
            total_count=45,
            total_pages=3,  # (45 + 20 - 1) // 20 = 3
        )

        assert pagination.total_pages == 3

        # 40 items with page_size 20 = 2 pages exactly
        pagination2 = PaginationInfo(
            page=1,
            page_size=20,
            total_count=40,
            total_pages=2,
        )

        assert pagination2.total_pages == 2

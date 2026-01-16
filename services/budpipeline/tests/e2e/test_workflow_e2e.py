"""End-to-end tests for workflow service."""

import pytest
from httpx import ASGITransport, AsyncClient

from budpipeline.main import app

# Sample DAG for testing
SAMPLE_DAG = {
    "name": "test-workflow",
    "version": "1.0.0",
    "description": "End-to-end test workflow",
    "parameters": [
        {"name": "input_message", "type": "string", "default": "Hello, World!"},
        {"name": "transform_enabled", "type": "boolean", "default": True},
    ],
    "steps": [
        {
            "id": "log_start",
            "name": "Log Start",
            "action": "log",
            "params": {
                "message": "Starting workflow with message: {{ params.input_message }}",
                "level": "info",
            },
        },
        {
            "id": "transform",
            "name": "Transform Message",
            "action": "transform",
            "depends_on": ["log_start"],
            "condition": "{{ params.transform_enabled }}",
            "params": {
                "input": "{{ params.input_message }}",
                "operation": "uppercase",
            },
        },
        {
            "id": "set_result",
            "name": "Set Result",
            "action": "set_output",
            "depends_on": ["transform"],
            "params": {
                "outputs": {
                    "transformed": "{{ steps.transform.outputs.result | default('SKIPPED') }}",
                    "original": "{{ params.input_message }}",
                },
            },
        },
        {
            "id": "log_end",
            "name": "Log End",
            "action": "log",
            "depends_on": ["set_result"],
            "params": {
                "message": "Workflow completed with result: {{ steps.set_result.outputs.transformed }}",
                "level": "info",
            },
        },
    ],
    "outputs": {
        "final_message": "{{ steps.set_result.outputs.transformed }}",
        "original_message": "{{ steps.set_result.outputs.original }}",
    },
}


@pytest.fixture
async def client():
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


class TestHealthEndpoints:
    """Test health check endpoints."""

    @pytest.mark.asyncio
    async def test_health(self, client: AsyncClient):
        """Test health endpoint."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_ready(self, client: AsyncClient):
        """Test readiness endpoint."""
        response = await client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"


class TestDAGValidation:
    """Test DAG validation endpoints."""

    @pytest.mark.asyncio
    async def test_validate_valid_dag(self, client: AsyncClient):
        """Test validation of valid DAG."""
        response = await client.post(
            "/api/v1/workflow/validate",
            json={"dag": SAMPLE_DAG},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["errors"] == []
        assert data["step_count"] == 4
        assert data["has_cycles"] is False

    @pytest.mark.asyncio
    async def test_validate_invalid_dag_missing_steps(self, client: AsyncClient):
        """Test validation of DAG missing steps."""
        invalid_dag = {
            "name": "invalid",
            "version": "1.0.0",
        }
        response = await client.post(
            "/api/v1/workflow/validate",
            json={"dag": invalid_dag},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert len(data["errors"]) > 0

    @pytest.mark.asyncio
    async def test_validate_dag_with_cycles(self, client: AsyncClient):
        """Test validation of DAG with cycles."""
        cyclic_dag = {
            "name": "cyclic",
            "version": "1.0.0",
            "steps": [
                {"id": "a", "name": "Step A", "action": "log", "depends_on": ["b"]},
                {"id": "b", "name": "Step B", "action": "log", "depends_on": ["a"]},
            ],
        }
        response = await client.post(
            "/api/v1/workflow/validate",
            json={"dag": cyclic_dag},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["has_cycles"] is True


class TestWorkflowCRUD:
    """Test workflow CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_workflow(self, client: AsyncClient):
        """Test creating a workflow."""
        response = await client.post(
            "/api/v1/workflow/workflows",
            json={"dag": SAMPLE_DAG, "name": "my-test-workflow"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "my-test-workflow"
        assert data["version"] == "1.0.0"
        assert data["status"] == "active"
        assert data["step_count"] == 4
        assert "id" in data

    @pytest.mark.asyncio
    async def test_list_workflows(self, client: AsyncClient):
        """Test listing workflows."""
        # Create a workflow first
        await client.post(
            "/api/v1/workflow/workflows",
            json={"dag": SAMPLE_DAG},
        )

        response = await client.get("/api/v1/workflow/workflows")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_get_workflow(self, client: AsyncClient):
        """Test getting a specific workflow."""
        # Create a workflow first
        create_response = await client.post(
            "/api/v1/workflow/workflows",
            json={"dag": SAMPLE_DAG},
        )
        workflow_id = create_response.json()["id"]

        response = await client.get(f"/api/v1/workflow/workflows/{workflow_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == workflow_id
        assert "dag" in data

    @pytest.mark.asyncio
    async def test_get_nonexistent_workflow(self, client: AsyncClient):
        """Test getting a nonexistent workflow."""
        response = await client.get("/api/v1/workflow/workflows/nonexistent-id")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_workflow(self, client: AsyncClient):
        """Test deleting a workflow."""
        # Create a workflow first
        create_response = await client.post(
            "/api/v1/workflow/workflows",
            json={"dag": SAMPLE_DAG},
        )
        workflow_id = create_response.json()["id"]

        response = await client.delete(f"/api/v1/workflow/workflows/{workflow_id}")
        assert response.status_code == 204

        # Verify it's deleted
        get_response = await client.get(f"/api/v1/workflow/workflows/{workflow_id}")
        assert get_response.status_code == 404


class TestWorkflowExecution:
    """Test workflow execution."""

    @pytest.mark.asyncio
    async def test_execute_workflow(self, client: AsyncClient):
        """Test executing a workflow."""
        # Create a workflow first
        create_response = await client.post(
            "/api/v1/workflow/workflows",
            json={"dag": SAMPLE_DAG},
        )
        workflow_id = create_response.json()["id"]

        # Execute the workflow
        response = await client.post(
            "/api/v1/workflow/executions",
            json={
                "workflow_id": workflow_id,
                "params": {"input_message": "Test Message"},
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["workflow_id"] == workflow_id
        assert data["status"] == "completed"
        assert "execution_id" in data
        assert data["outputs"]["final_message"] == "TEST MESSAGE"
        assert data["outputs"]["original_message"] == "Test Message"

    @pytest.mark.asyncio
    async def test_execute_workflow_with_condition_false(self, client: AsyncClient):
        """Test executing a workflow with condition evaluating to false."""
        # Create a workflow first
        create_response = await client.post(
            "/api/v1/workflow/workflows",
            json={"dag": SAMPLE_DAG},
        )
        workflow_id = create_response.json()["id"]

        # Execute with transform disabled
        response = await client.post(
            "/api/v1/workflow/executions",
            json={
                "workflow_id": workflow_id,
                "params": {
                    "input_message": "Test",
                    "transform_enabled": False,
                },
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "completed"
        # When transform is skipped, the default value should be used
        assert data["outputs"]["final_message"] == "SKIPPED"

    @pytest.mark.asyncio
    async def test_get_execution_details(self, client: AsyncClient):
        """Test getting execution details."""
        # Create and execute a workflow
        create_response = await client.post(
            "/api/v1/workflow/workflows",
            json={"dag": SAMPLE_DAG},
        )
        workflow_id = create_response.json()["id"]

        exec_response = await client.post(
            "/api/v1/workflow/executions",
            json={"workflow_id": workflow_id, "params": {}},
        )
        execution_id = exec_response.json()["execution_id"]

        # Get execution details
        response = await client.get(f"/api/v1/workflow/executions/{execution_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["execution_id"] == execution_id
        assert "steps" in data
        assert len(data["steps"]) == 4

        # Check step statuses
        step_statuses = {s["step_id"]: s["status"] for s in data["steps"]}
        assert step_statuses["log_start"] == "completed"
        assert step_statuses["transform"] == "completed"
        assert step_statuses["set_result"] == "completed"
        assert step_statuses["log_end"] == "completed"

    @pytest.mark.asyncio
    async def test_list_executions(self, client: AsyncClient):
        """Test listing executions."""
        # Create and execute a workflow
        create_response = await client.post(
            "/api/v1/workflow/workflows",
            json={"dag": SAMPLE_DAG},
        )
        workflow_id = create_response.json()["id"]

        await client.post(
            "/api/v1/workflow/executions",
            json={"workflow_id": workflow_id, "params": {}},
        )

        # List all executions
        response = await client.get("/api/v1/workflow/executions")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_list_executions_by_workflow(self, client: AsyncClient):
        """Test listing executions filtered by workflow."""
        # Create and execute a workflow
        create_response = await client.post(
            "/api/v1/workflow/workflows",
            json={"dag": SAMPLE_DAG},
        )
        workflow_id = create_response.json()["id"]

        await client.post(
            "/api/v1/workflow/executions",
            json={"workflow_id": workflow_id, "params": {}},
        )

        # List executions for this workflow
        response = await client.get(
            "/api/v1/workflow/executions",
            params={"workflow_id": workflow_id},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert all(e["workflow_id"] == workflow_id for e in data)


class TestComplexWorkflow:
    """Test complex workflow scenarios."""

    @pytest.mark.asyncio
    async def test_parallel_steps(self, client: AsyncClient):
        """Test workflow with parallel steps."""
        parallel_dag = {
            "name": "parallel-workflow",
            "version": "1.0.0",
            "steps": [
                {"id": "start", "name": "Start", "action": "log", "params": {"message": "Start"}},
                {
                    "id": "parallel_a",
                    "name": "Parallel A",
                    "action": "set_output",
                    "depends_on": ["start"],
                    "params": {"outputs": {"value": "A"}},
                },
                {
                    "id": "parallel_b",
                    "name": "Parallel B",
                    "action": "set_output",
                    "depends_on": ["start"],
                    "params": {"outputs": {"value": "B"}},
                },
                {
                    "id": "parallel_c",
                    "name": "Parallel C",
                    "action": "set_output",
                    "depends_on": ["start"],
                    "params": {"outputs": {"value": "C"}},
                },
                {
                    "id": "aggregate",
                    "name": "Aggregate",
                    "action": "aggregate",
                    "depends_on": ["parallel_a", "parallel_b", "parallel_c"],
                    "params": {
                        "inputs": [
                            "{{ steps.parallel_a.outputs.value }}",
                            "{{ steps.parallel_b.outputs.value }}",
                            "{{ steps.parallel_c.outputs.value }}",
                        ],
                        "operation": "join",
                        "separator": "-",
                    },
                },
            ],
            "outputs": {
                "result": "{{ steps.aggregate.outputs.result }}",
            },
        }

        # Create and execute
        create_response = await client.post(
            "/api/v1/workflow/workflows",
            json={"dag": parallel_dag},
        )
        workflow_id = create_response.json()["id"]

        exec_response = await client.post(
            "/api/v1/workflow/executions",
            json={"workflow_id": workflow_id, "params": {}},
        )
        assert exec_response.status_code == 201
        data = exec_response.json()
        assert data["status"] == "completed"
        assert data["outputs"]["result"] == "A-B-C"

    @pytest.mark.asyncio
    async def test_step_failure_with_continue(self, client: AsyncClient):
        """Test workflow with step failure and continue policy."""
        failure_dag = {
            "name": "failure-workflow",
            "version": "1.0.0",
            "steps": [
                {"id": "start", "name": "Start", "action": "log", "params": {"message": "Start"}},
                {
                    "id": "fail_step",
                    "name": "Fail Step",
                    "action": "fail",
                    "depends_on": ["start"],
                    "on_failure": "continue",
                    "params": {"message": "Intentional failure"},
                },
                {
                    "id": "after_fail",
                    "name": "After Fail",
                    "action": "set_output",
                    "depends_on": ["fail_step"],
                    "params": {"outputs": {"reached": True}},
                },
            ],
        }

        create_response = await client.post(
            "/api/v1/workflow/workflows",
            json={"dag": failure_dag},
        )
        workflow_id = create_response.json()["id"]

        exec_response = await client.post(
            "/api/v1/workflow/executions",
            json={"workflow_id": workflow_id, "params": {}},
        )
        assert exec_response.status_code == 201
        data = exec_response.json()
        assert data["status"] == "completed"

        # Get detailed status
        detail_response = await client.get(f"/api/v1/workflow/executions/{data['execution_id']}")
        details = detail_response.json()
        step_statuses = {s["step_id"]: s for s in details["steps"]}
        assert step_statuses["fail_step"]["status"] == "failed"
        assert step_statuses["after_fail"]["status"] == "completed"

"""
Model registry fixtures for E2E tests.

Provides fixtures for model onboarding, management, and testing.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from enum import Enum

import pytest
import httpx

from tests.e2e.helpers.model_helper import ModelHelper


class ModelProviderType(str, Enum):
    """Model provider types."""

    HUGGING_FACE = "hugging_face"
    CLOUD_MODEL = "cloud_model"
    URL = "url"
    DISK = "disk"


class WorkflowStatus(str, Enum):
    """Workflow status values."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


@dataclass
class Tag:
    """Model tag."""

    name: str
    color: str = "#3B82F6"  # Default blue


@dataclass
class TestModel:
    """Test model data structure."""

    id: Optional[UUID] = None
    name: str = ""
    description: str = ""
    provider_type: ModelProviderType = ModelProviderType.CLOUD_MODEL
    uri: str = ""
    author: str = ""
    tags: Optional[List[Tag]] = None
    source: str = ""
    modality: Optional[List[str]] = None
    provider_id: Optional[UUID] = None


@dataclass
class CloudModelInfo:
    """Cloud model information for onboarding."""

    cloud_model_id: Optional[UUID] = None
    name: str = ""
    uri: str = ""
    source: str = ""
    modality: Optional[List[str]] = None
    provider_id: Optional[UUID] = None


@dataclass
class ModelWorkflow:
    """Model workflow tracking."""

    workflow_id: Optional[UUID] = None
    status: WorkflowStatus = WorkflowStatus.PENDING
    current_step: int = 0
    total_steps: int = 0
    model_id: Optional[UUID] = None


@dataclass
class Provider:
    """Model provider information."""

    id: UUID
    name: str
    type: str
    description: str = ""
    icon: str = ""
    capabilities: List[str] = None


# ============================================================================
# Test Data Generators
# ============================================================================


def generate_unique_model_name(prefix: str = "e2e-test-model") -> str:
    """Generate a unique model name for testing."""
    return f"{prefix}-{uuid4().hex[:8]}"


def generate_model_tags(count: int = 2) -> List[Dict[str, str]]:
    """Generate test model tags."""
    tag_names = ["test", "e2e", "automated", "validation", "benchmark"]
    colors = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6"]

    tags = []
    for i in range(min(count, len(tag_names))):
        tags.append({"name": tag_names[i], "color": colors[i % len(colors)]})
    return tags


# ============================================================================
# Pytest Fixtures
# ============================================================================


@pytest.fixture
def unique_model_name() -> str:
    """Generate a unique model name."""
    return generate_unique_model_name()


@pytest.fixture
def model_tags() -> List[Dict[str, str]]:
    """Generate test tags for a model."""
    return generate_model_tags(2)


@pytest.fixture
async def cloud_model_provider(
    budapp_client: httpx.AsyncClient,
    authenticated_user,
) -> Optional[Provider]:
    """
    Get a cloud model provider for testing.

    Returns the first available cloud model provider.
    """

    user, tokens = authenticated_user

    response = await budapp_client.get(
        "/models/providers",
        headers={"Authorization": f"Bearer {tokens.access_token}"},
        params={"capabilities": "CHAT"},
    )

    if response.status_code != 200:
        pytest.skip("Could not fetch providers")
        return None

    data = response.json()
    providers = data.get("providers", [])

    # Find a cloud model provider (e.g., OpenAI, Anthropic)
    for p in providers:
        if p.get("type") in ["openai", "anthropic", "google", "azure_openai"]:
            return Provider(
                id=UUID(p["id"]),
                name=p["name"],
                type=p["type"],
                description=p.get("description", ""),
                icon=p.get("icon", ""),
                capabilities=p.get("capabilities", []),
            )

    # Return first provider if no cloud provider found
    if providers:
        p = providers[0]
        return Provider(
            id=UUID(p["id"]),
            name=p["name"],
            type=p["type"],
            description=p.get("description", ""),
            icon=p.get("icon", ""),
            capabilities=p.get("capabilities", []),
        )

    pytest.skip("No providers available for testing")
    return None


@pytest.fixture
async def available_cloud_model(
    budapp_client: httpx.AsyncClient,
    authenticated_user,
    cloud_model_provider: Optional[Provider],
) -> Optional[CloudModelInfo]:
    """
    Get an available cloud model for testing.

    Returns a cloud model that hasn't been added to the registry yet.
    """

    if cloud_model_provider is None:
        pytest.skip("No provider available")
        return None

    user, tokens = authenticated_user
    ModelHelper(budapp_client)

    # This would fetch available cloud models from the provider
    # For testing, we'll create a mock cloud model reference
    return CloudModelInfo(
        name=f"test-cloud-model-{uuid4().hex[:8]}",
        uri=f"test-provider/test-model-{uuid4().hex[:8]}",
        source=cloud_model_provider.type,
        modality=["text"],
        provider_id=cloud_model_provider.id,
    )


@pytest.fixture
async def created_model(
    budapp_client: httpx.AsyncClient,
    authenticated_user,
    cloud_model_provider: Optional[Provider],
) -> TestModel:
    """
    Create a test model and clean up after test.

    This fixture creates a cloud model through the workflow and
    yields the model data. After the test, it deletes the model.
    """

    if cloud_model_provider is None:
        pytest.skip("No provider available for model creation")

    user, tokens = authenticated_user
    helper = ModelHelper(budapp_client)

    model_name = generate_unique_model_name()

    # Start cloud model workflow
    workflow_result = await helper.start_cloud_model_workflow(
        access_token=tokens.access_token,
        provider_type="cloud_model",
        name=model_name,
        modality=["text"],
        uri=f"test-provider/{model_name}",
        provider_id=str(cloud_model_provider.id),
        tags=generate_model_tags(2),
        total_steps=2,
    )

    if not workflow_result.success:
        pytest.skip(f"Could not create test model: {workflow_result.error}")

    # Complete workflow
    complete_result = await helper.complete_cloud_model_workflow(
        access_token=tokens.access_token,
        workflow_id=workflow_result.workflow_id,
        step_number=2,
        trigger_workflow=True,
    )

    if not complete_result.success:
        pytest.skip(f"Could not complete model workflow: {complete_result.error}")

    model = TestModel(
        id=complete_result.model_id,
        name=model_name,
        provider_type=ModelProviderType.CLOUD_MODEL,
        uri=f"test-provider/{model_name}",
        provider_id=cloud_model_provider.id,
        tags=[
            Tag(name=t["name"], color=t.get("color", "#3B82F6"))
            for t in generate_model_tags(2)
        ],
    )

    yield model

    # Cleanup: Delete the model
    if model.id:
        try:
            await helper.delete_model(
                access_token=tokens.access_token,
                model_id=str(model.id),
            )
        except Exception as e:
            print(f"Warning: Failed to cleanup model {model.id}: {e}")


@pytest.fixture
async def model_list(
    budapp_client: httpx.AsyncClient,
    authenticated_user,
) -> List[Dict[str, Any]]:
    """
    Get list of existing models for testing.

    Returns a list of models currently in the registry.
    """

    user, tokens = authenticated_user
    helper = ModelHelper(budapp_client)

    result = await helper.list_models(
        access_token=tokens.access_token,
        limit=10,
    )

    if not result.success:
        return []

    return result.data.get("models", [])

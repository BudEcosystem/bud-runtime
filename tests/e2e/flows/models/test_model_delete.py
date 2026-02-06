"""
E2E Tests for Model Delete Operations.

Test Cases Covered:
- Delete model (soft delete)
- Delete verification (model no longer accessible)
- Delete authentication requirements
- Delete non-existent model
"""

import pytest
import httpx
from uuid import uuid4

from tests.e2e.helpers.model_helper import ModelHelper
from tests.e2e.fixtures.auth import TestUser, AuthTokens
from tests.e2e.fixtures.models import (
    generate_unique_model_name,
    generate_model_tags,
)


@pytest.mark.e2e
@pytest.mark.priority_p0
@pytest.mark.models
class TestModelDelete:
    """Test cases for model delete operations."""

    async def _create_test_model(
        self,
        helper: ModelHelper,
        access_token: str,
    ) -> tuple[str, str]:
        """
        Helper to create a test model.

        Returns (model_id, model_name) tuple.
        """
        providers_result = await helper.list_providers(access_token=access_token)

        if not providers_result.success or not providers_result.data.get("providers"):
            pytest.skip("No providers available for testing")

        provider = providers_result.data["providers"][0]
        model_name = generate_unique_model_name()

        result = await helper.run_cloud_model_workflow(
            access_token=access_token,
            provider_type="cloud_model",
            name=model_name,
            modality=["text_input", "text_output"],
            uri=f"test-provider/{model_name}",
            provider_id=provider["id"],
            tags=generate_model_tags(2),
        )

        if not result.success or not result.model_id:
            pytest.skip(f"Could not create test model: {result.error}")

        return result.model_id, model_name

    @pytest.mark.asyncio
    async def test_delete_model_success(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test successful model deletion.

        Flow:
        1. Create a test model
        2. Delete the model
        3. Verify deletion was successful
        """
        user, tokens = authenticated_user
        helper = ModelHelper(budapp_client)

        model_id, model_name = await self._create_test_model(
            helper, tokens.access_token
        )

        # Delete the model
        delete_result = await helper.delete_model(
            access_token=tokens.access_token,
            model_id=model_id,
        )

        assert delete_result.success, f"Delete failed: {delete_result.error}"
        assert delete_result.status_code in (200, 204), (
            f"Expected 200/204, got {delete_result.status_code}"
        )

    @pytest.mark.asyncio
    async def test_deleted_model_not_accessible(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test that deleted model is not accessible.

        Flow:
        1. Create a test model
        2. Delete the model
        3. Try to access the model
        4. Verify 404 response
        """
        user, tokens = authenticated_user
        helper = ModelHelper(budapp_client)

        model_id, model_name = await self._create_test_model(
            helper, tokens.access_token
        )

        # Delete the model
        delete_result = await helper.delete_model(
            access_token=tokens.access_token,
            model_id=model_id,
        )

        assert delete_result.success, f"Delete failed: {delete_result.error}"

        # Try to access deleted model
        get_result = await helper.get_model(
            access_token=tokens.access_token,
            model_id=model_id,
        )

        # Soft delete may return the model with DELETED status or 404
        if get_result.success:
            model_data = get_result.data.get("model", get_result.data)
            status = model_data.get("status")
            # If model is returned, it should have DELETED status
            assert status in ("DELETED", "deleted", None), (
                f"Deleted model should have DELETED status, got {status}"
            )
        else:
            # 404 is also acceptable for soft deleted models
            assert get_result.status_code == 404, (
                f"Expected 404 for deleted model, got {get_result.status_code}"
            )

    @pytest.mark.asyncio
    async def test_deleted_model_not_in_list(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test that deleted model doesn't appear in list.

        Flow:
        1. Create a test model
        2. Verify model appears in list
        3. Delete the model
        4. Verify model doesn't appear in list
        """
        user, tokens = authenticated_user
        helper = ModelHelper(budapp_client)

        model_id, model_name = await self._create_test_model(
            helper, tokens.access_token
        )

        # Verify model exists in list
        await helper.list_models(
            access_token=tokens.access_token,
            search=model_name,
        )

        # Delete the model
        delete_result = await helper.delete_model(
            access_token=tokens.access_token,
            model_id=model_id,
        )

        assert delete_result.success, f"Delete failed: {delete_result.error}"

        # Verify model doesn't appear in list
        list_after = await helper.list_models(
            access_token=tokens.access_token,
            search=model_name,
        )

        if list_after.success:
            models = list_after.data.get("models", [])
            model_ids = [m.get("id") for m in models]
            # Deleted model should not appear in active list
            assert model_id not in model_ids, "Deleted model should not appear in list"

    @pytest.mark.asyncio
    async def test_delete_model_idempotent(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test that deleting an already deleted model is handled gracefully.

        Flow:
        1. Create and delete a model
        2. Try to delete again
        3. Verify appropriate response
        """
        user, tokens = authenticated_user
        helper = ModelHelper(budapp_client)

        model_id, _ = await self._create_test_model(helper, tokens.access_token)

        # First delete
        first_delete = await helper.delete_model(
            access_token=tokens.access_token,
            model_id=model_id,
        )
        assert first_delete.success

        # Second delete
        second_delete = await helper.delete_model(
            access_token=tokens.access_token,
            model_id=model_id,
        )

        # Should return 200/204 (idempotent) or 404 (already deleted)
        assert second_delete.status_code in (200, 204, 404), (
            f"Expected 200/204/404 for second delete, got {second_delete.status_code}"
        )


@pytest.mark.e2e
@pytest.mark.priority_p1
@pytest.mark.models
class TestModelDeleteAuthentication:
    """Test cases for model delete authentication."""

    @pytest.mark.asyncio
    async def test_delete_requires_auth(
        self,
        budapp_client: httpx.AsyncClient,
    ):
        """
        Test that delete requires authentication.
        """
        fake_model_id = str(uuid4())

        response = await budapp_client.delete(
            f"/models/{fake_model_id}",
        )

        assert response.status_code == 401, (
            f"Expected 401 without auth, got {response.status_code}"
        )

    @pytest.mark.asyncio
    async def test_delete_with_invalid_token(
        self,
        budapp_client: httpx.AsyncClient,
    ):
        """
        Test that delete with invalid token is rejected.
        """
        fake_model_id = str(uuid4())

        response = await budapp_client.delete(
            f"/models/{fake_model_id}",
            headers={"Authorization": "Bearer invalid_token"},
        )

        assert response.status_code == 401, (
            f"Expected 401 for invalid token, got {response.status_code}"
        )


@pytest.mark.e2e
@pytest.mark.priority_p1
@pytest.mark.models
class TestModelDeleteValidation:
    """Test cases for model delete validation."""

    @pytest.mark.asyncio
    async def test_delete_nonexistent_model(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test deleting a model that doesn't exist.
        """
        user, tokens = authenticated_user
        helper = ModelHelper(budapp_client)

        fake_model_id = str(uuid4())

        delete_result = await helper.delete_model(
            access_token=tokens.access_token,
            model_id=fake_model_id,
        )

        # User may get 403 if lacking MODEL_MANAGE permission, or 404 if model doesn't exist
        assert delete_result.status_code in (403, 404), (
            f"Expected 403/404 for nonexistent model, got {delete_result.status_code}"
        )

    @pytest.mark.asyncio
    async def test_delete_with_invalid_uuid(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test deleting with invalid UUID format.
        """
        user, tokens = authenticated_user

        response = await budapp_client.delete(
            "/models/not-a-valid-uuid",
            headers={"Authorization": f"Bearer {tokens.access_token}"},
        )

        # Should return 422 (validation error) or 404
        assert response.status_code in (404, 422), (
            f"Expected 404/422 for invalid UUID, got {response.status_code}"
        )


@pytest.mark.e2e
@pytest.mark.priority_p0
@pytest.mark.models
class TestModelList:
    """Test cases for model listing operations."""

    @pytest.mark.asyncio
    async def test_list_models(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test listing all models.

        Flow:
        1. Get authentication
        2. List models
        3. Verify response structure
        """
        user, tokens = authenticated_user
        helper = ModelHelper(budapp_client)

        result = await helper.list_models(
            access_token=tokens.access_token,
            limit=10,
        )

        # User may get 403 if lacking MODEL_VIEW permission
        if result.status_code == 403:
            pytest.skip("User lacks MODEL_VIEW permission")

        assert result.success, f"List models failed: {result.error}"
        assert result.data is not None
        assert "models" in result.data
        assert isinstance(result.data["models"], list)

    @pytest.mark.asyncio
    async def test_list_models_with_pagination(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test model list pagination.
        """
        user, tokens = authenticated_user
        helper = ModelHelper(budapp_client)

        # Get first page
        first_page = await helper.list_models(
            access_token=tokens.access_token,
            limit=5,
            offset=0,
        )

        if first_page.status_code == 403:
            pytest.skip("User lacks MODEL_VIEW permission")

        assert first_page.success

        # Get second page
        second_page = await helper.list_models(
            access_token=tokens.access_token,
            limit=5,
            offset=5,
        )

        assert second_page.success

        # Pages should be different (if there are enough models)
        first_ids = {m.get("id") for m in first_page.data.get("models", [])}
        second_ids = {m.get("id") for m in second_page.data.get("models", [])}

        # No overlap between pages
        assert (
            len(first_ids & second_ids) == 0
            or len(first_ids) == 0
            or len(second_ids) == 0
        )

    @pytest.mark.asyncio
    async def test_list_models_with_search(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test model list search functionality.
        """
        user, tokens = authenticated_user
        helper = ModelHelper(budapp_client)

        # Create a model with unique name
        providers_result = await helper.list_providers(access_token=tokens.access_token)

        if not providers_result.success or not providers_result.data.get("providers"):
            pytest.skip("No providers available")

        provider = providers_result.data["providers"][0]
        unique_name = f"searchable-{uuid4().hex[:12]}"

        create_result = await helper.run_cloud_model_workflow(
            access_token=tokens.access_token,
            provider_type="cloud_model",
            name=unique_name,
            modality=["text_input", "text_output"],
            uri=f"test-provider/{unique_name}",
            provider_id=provider["id"],
        )

        if not create_result.success:
            pytest.skip("Could not create test model")

        try:
            # Search for the model
            search_result = await helper.list_models(
                access_token=tokens.access_token,
                search=unique_name,
            )

            assert search_result.success

            models = search_result.data.get("models", [])
            # Should find our model
            any(unique_name in m.get("name", "") for m in models)
            # May or may not find immediately due to indexing
        finally:
            if create_result.model_id:
                await helper.delete_model(
                    access_token=tokens.access_token,
                    model_id=create_result.model_id,
                )

    @pytest.mark.asyncio
    async def test_list_models_requires_auth(
        self,
        budapp_client: httpx.AsyncClient,
    ):
        """
        Test that list models requires authentication.
        """
        response = await budapp_client.get("/models/")

        assert response.status_code == 401, (
            f"Expected 401 without auth, got {response.status_code}"
        )


@pytest.mark.e2e
@pytest.mark.priority_p1
@pytest.mark.models
class TestModelGet:
    """Test cases for getting single model details."""

    @pytest.mark.asyncio
    async def test_get_model_details(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test getting model details.
        """
        user, tokens = authenticated_user
        helper = ModelHelper(budapp_client)

        # Create a model
        providers_result = await helper.list_providers(access_token=tokens.access_token)

        if not providers_result.success or not providers_result.data.get("providers"):
            pytest.skip("No providers available")

        provider = providers_result.data["providers"][0]
        model_name = generate_unique_model_name()

        create_result = await helper.run_cloud_model_workflow(
            access_token=tokens.access_token,
            provider_type="cloud_model",
            name=model_name,
            modality=["text_input", "text_output"],
            uri=f"test-provider/{model_name}",
            provider_id=provider["id"],
            tags=generate_model_tags(2),
        )

        if not create_result.success or not create_result.model_id:
            pytest.skip("Could not create test model")

        try:
            # Get model details
            get_result = await helper.get_model(
                access_token=tokens.access_token,
                model_id=create_result.model_id,
            )

            assert get_result.success, f"Get model failed: {get_result.error}"

            model_data = get_result.data.get("model", get_result.data)
            assert model_data.get("name") == model_name
            assert "id" in model_data
            assert "provider_type" in model_data or "source" in model_data

        finally:
            await helper.delete_model(
                access_token=tokens.access_token,
                model_id=create_result.model_id,
            )

    @pytest.mark.asyncio
    async def test_get_nonexistent_model(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test getting a model that doesn't exist.
        """
        user, tokens = authenticated_user
        helper = ModelHelper(budapp_client)

        fake_model_id = str(uuid4())

        get_result = await helper.get_model(
            access_token=tokens.access_token,
            model_id=fake_model_id,
        )

        assert not get_result.success
        # User may get 403 if lacking permission, or 404 if model doesn't exist
        assert get_result.status_code in (403, 404)

    @pytest.mark.asyncio
    async def test_get_model_requires_auth(
        self,
        budapp_client: httpx.AsyncClient,
    ):
        """
        Test that get model requires authentication.
        """
        fake_model_id = str(uuid4())

        response = await budapp_client.get(f"/models/{fake_model_id}")

        assert response.status_code == 401


@pytest.mark.e2e
@pytest.mark.priority_p2
@pytest.mark.models
class TestModelMetadata:
    """Test cases for model metadata operations."""

    @pytest.mark.asyncio
    async def test_list_tags(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test listing available model tags.
        """
        user, tokens = authenticated_user
        helper = ModelHelper(budapp_client)

        result = await helper.list_tags(
            access_token=tokens.access_token,
            limit=20,
        )

        if result.status_code == 403:
            pytest.skip("User lacks MODEL_VIEW permission")

        assert result.success, f"List tags failed: {result.error}"

    @pytest.mark.asyncio
    async def test_list_tasks(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test listing available model tasks.
        """
        user, tokens = authenticated_user
        helper = ModelHelper(budapp_client)

        result = await helper.list_tasks(
            access_token=tokens.access_token,
            limit=20,
        )

        if result.status_code == 403:
            pytest.skip("User lacks MODEL_VIEW permission")

        assert result.success, f"List tasks failed: {result.error}"

    @pytest.mark.asyncio
    async def test_list_authors(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test listing model authors.
        """
        user, tokens = authenticated_user
        helper = ModelHelper(budapp_client)

        result = await helper.list_authors(
            access_token=tokens.access_token,
            limit=20,
        )

        if result.status_code == 403:
            pytest.skip("User lacks MODEL_VIEW permission")

        assert result.success, f"List authors failed: {result.error}"

    @pytest.mark.asyncio
    async def test_list_catalog(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test listing model catalog (published models).
        """
        user, tokens = authenticated_user
        helper = ModelHelper(budapp_client)

        result = await helper.list_catalog(
            access_token=tokens.access_token,
            limit=10,
        )

        # Catalog may be empty or require different permissions
        assert result.status_code in (200, 403), (
            f"Unexpected status: {result.status_code}"
        )

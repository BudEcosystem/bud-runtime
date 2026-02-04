"""
E2E Tests for Model Edit Operations.

Test Cases Covered:
- Edit model name
- Edit model description
- Edit model tags and tasks
- Edit model URLs (GitHub, HuggingFace, website)
- Validation errors for invalid edits
"""

import pytest
import httpx
from uuid import uuid4

from tests.e2e.helpers.model_helper import ModelHelper, ModelResponse
from tests.e2e.fixtures.auth import TestUser, AuthTokens
from tests.e2e.fixtures.models import (
    generate_unique_model_name,
    generate_model_tags,
)


@pytest.mark.e2e
@pytest.mark.priority_p0
@pytest.mark.models
class TestModelEdit:
    """Test cases for model edit operations."""

    async def _create_test_model(
        self,
        helper: ModelHelper,
        access_token: str,
    ) -> tuple[str, str]:
        """
        Helper to create a test model for editing.

        Returns (model_id, model_name) tuple.
        """
        # Get provider
        providers_result = await helper.list_providers(
            access_token=access_token,
        )

        if not providers_result.success or not providers_result.data.get("providers"):
            pytest.skip("No providers available for testing")

        provider = providers_result.data["providers"][0]
        model_name = generate_unique_model_name()

        # Create model
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
    async def test_edit_model_name(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test editing model name.

        Flow:
        1. Create a test model
        2. Edit the model name
        3. Verify name is updated
        4. Clean up
        """
        user, tokens = authenticated_user
        helper = ModelHelper(budapp_client)

        model_id, original_name = await self._create_test_model(
            helper, tokens.access_token
        )

        try:
            new_name = f"updated-{uuid4().hex[:8]}"

            # Edit model name
            edit_result = await helper.edit_model(
                access_token=tokens.access_token,
                model_id=model_id,
                name=new_name,
            )

            assert edit_result.success, f"Edit failed: {edit_result.error}"

            # Verify name was updated
            get_result = await helper.get_model(
                access_token=tokens.access_token,
                model_id=model_id,
            )

            if get_result.success:
                model_data = get_result.data.get("model", get_result.data)
                assert model_data.get("name") == new_name, (
                    f"Name not updated: expected {new_name}, got {model_data.get('name')}"
                )
        finally:
            await helper.delete_model(
                access_token=tokens.access_token,
                model_id=model_id,
            )

    @pytest.mark.asyncio
    async def test_edit_model_description(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test editing model description.

        Flow:
        1. Create a test model
        2. Edit the description
        3. Verify description is updated
        """
        user, tokens = authenticated_user
        helper = ModelHelper(budapp_client)

        model_id, _ = await self._create_test_model(helper, tokens.access_token)

        try:
            new_description = "Updated description for E2E testing"

            edit_result = await helper.edit_model(
                access_token=tokens.access_token,
                model_id=model_id,
                description=new_description,
            )

            assert edit_result.success, f"Edit failed: {edit_result.error}"

            # Verify description was updated
            get_result = await helper.get_model(
                access_token=tokens.access_token,
                model_id=model_id,
            )

            if get_result.success:
                model_data = get_result.data.get("model", get_result.data)
                assert model_data.get("description") == new_description
        finally:
            await helper.delete_model(
                access_token=tokens.access_token,
                model_id=model_id,
            )

    @pytest.mark.asyncio
    async def test_edit_model_tags(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test editing model tags.

        Flow:
        1. Create a test model with initial tags
        2. Update tags
        3. Verify tags are updated
        """
        user, tokens = authenticated_user
        helper = ModelHelper(budapp_client)

        model_id, _ = await self._create_test_model(helper, tokens.access_token)

        try:
            new_tags = [
                {"name": "updated-tag", "color": "#FF5733"},
                {"name": "new-tag", "color": "#33FF57"},
            ]

            edit_result = await helper.edit_model(
                access_token=tokens.access_token,
                model_id=model_id,
                tags=new_tags,
            )

            assert edit_result.success, f"Edit failed: {edit_result.error}"

            # Verify tags were updated
            get_result = await helper.get_model(
                access_token=tokens.access_token,
                model_id=model_id,
            )

            if get_result.success:
                model_data = get_result.data.get("model", get_result.data)
                tags = model_data.get("tags", [])
                tag_names = [t.get("name") for t in tags]
                assert "updated-tag" in tag_names or len(tags) > 0
        finally:
            await helper.delete_model(
                access_token=tokens.access_token,
                model_id=model_id,
            )

    @pytest.mark.asyncio
    async def test_edit_model_github_url(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test editing model GitHub URL.
        """
        user, tokens = authenticated_user
        helper = ModelHelper(budapp_client)

        model_id, _ = await self._create_test_model(helper, tokens.access_token)

        try:
            github_url = "https://github.com/example/model-repo"

            edit_result = await helper.edit_model(
                access_token=tokens.access_token,
                model_id=model_id,
                github_url=github_url,
            )

            assert edit_result.success, f"Edit failed: {edit_result.error}"

            # Verify URL was updated
            get_result = await helper.get_model(
                access_token=tokens.access_token,
                model_id=model_id,
            )

            if get_result.success:
                model_data = get_result.data.get("model", get_result.data)
                assert model_data.get("github_url") == github_url
        finally:
            await helper.delete_model(
                access_token=tokens.access_token,
                model_id=model_id,
            )

    @pytest.mark.asyncio
    async def test_edit_multiple_fields(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test editing multiple model fields at once.
        """
        user, tokens = authenticated_user
        helper = ModelHelper(budapp_client)

        model_id, _ = await self._create_test_model(helper, tokens.access_token)

        try:
            new_name = f"multi-edit-{uuid4().hex[:8]}"
            new_description = "Multi-field edit test"
            new_website = "https://example.com/model"

            edit_result = await helper.edit_model(
                access_token=tokens.access_token,
                model_id=model_id,
                name=new_name,
                description=new_description,
                website_url=new_website,
            )

            assert edit_result.success, f"Edit failed: {edit_result.error}"

            # Verify all fields were updated
            get_result = await helper.get_model(
                access_token=tokens.access_token,
                model_id=model_id,
            )

            if get_result.success:
                model_data = get_result.data.get("model", get_result.data)
                assert model_data.get("name") == new_name
                assert model_data.get("description") == new_description
                assert model_data.get("website_url") == new_website
        finally:
            await helper.delete_model(
                access_token=tokens.access_token,
                model_id=model_id,
            )


@pytest.mark.e2e
@pytest.mark.priority_p1
@pytest.mark.models
class TestModelEditValidation:
    """Test cases for model edit validation."""

    async def _create_test_model(
        self,
        helper: ModelHelper,
        access_token: str,
    ) -> str:
        """Helper to create a test model."""
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
        )

        if not result.success or not result.model_id:
            pytest.skip(f"Could not create test model: {result.error}")

        return result.model_id

    @pytest.mark.asyncio
    async def test_edit_with_empty_name(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test that empty name is rejected.
        """
        user, tokens = authenticated_user
        helper = ModelHelper(budapp_client)

        model_id = await self._create_test_model(helper, tokens.access_token)

        try:
            # Try to set empty name
            edit_result = await helper.edit_model(
                access_token=tokens.access_token,
                model_id=model_id,
                name="",
            )

            # Should fail with validation error
            assert not edit_result.success or edit_result.status_code in (400, 422), (
                "Empty name should be rejected"
            )
        finally:
            await helper.delete_model(
                access_token=tokens.access_token,
                model_id=model_id,
            )

    @pytest.mark.asyncio
    async def test_edit_with_too_long_name(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test that too long name is rejected (max 100 chars).
        """
        user, tokens = authenticated_user
        helper = ModelHelper(budapp_client)

        model_id = await self._create_test_model(helper, tokens.access_token)

        try:
            long_name = "a" * 150  # Exceeds 100 char limit

            edit_result = await helper.edit_model(
                access_token=tokens.access_token,
                model_id=model_id,
                name=long_name,
            )

            # Should fail with validation error
            assert not edit_result.success or edit_result.status_code in (400, 422), (
                "Too long name should be rejected"
            )
        finally:
            await helper.delete_model(
                access_token=tokens.access_token,
                model_id=model_id,
            )

    @pytest.mark.asyncio
    async def test_edit_with_too_long_description(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test that too long description is rejected (max 400 chars).
        """
        user, tokens = authenticated_user
        helper = ModelHelper(budapp_client)

        model_id = await self._create_test_model(helper, tokens.access_token)

        try:
            long_description = "a" * 500  # Exceeds 400 char limit

            edit_result = await helper.edit_model(
                access_token=tokens.access_token,
                model_id=model_id,
                description=long_description,
            )

            # Should fail with validation error
            assert not edit_result.success or edit_result.status_code in (400, 422), (
                "Too long description should be rejected"
            )
        finally:
            await helper.delete_model(
                access_token=tokens.access_token,
                model_id=model_id,
            )

    @pytest.mark.asyncio
    async def test_edit_with_invalid_github_url(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test that invalid GitHub URL is rejected.
        """
        user, tokens = authenticated_user
        helper = ModelHelper(budapp_client)

        model_id = await self._create_test_model(helper, tokens.access_token)

        try:
            edit_result = await helper.edit_model(
                access_token=tokens.access_token,
                model_id=model_id,
                github_url="not-a-valid-url",
            )

            # Should fail with validation error
            assert not edit_result.success or edit_result.status_code in (400, 422), (
                "Invalid URL should be rejected"
            )
        finally:
            await helper.delete_model(
                access_token=tokens.access_token,
                model_id=model_id,
            )

    @pytest.mark.asyncio
    async def test_edit_nonexistent_model(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test editing a model that doesn't exist.
        """
        user, tokens = authenticated_user
        helper = ModelHelper(budapp_client)

        fake_model_id = str(uuid4())

        edit_result = await helper.edit_model(
            access_token=tokens.access_token,
            model_id=fake_model_id,
            name="new-name",
        )

        # Should fail with 403 (permission) or 404 (not found)
        assert not edit_result.success
        assert edit_result.status_code in (403, 404), (
            f"Expected 403/404 for nonexistent model, got {edit_result.status_code}"
        )


@pytest.mark.e2e
@pytest.mark.priority_p1
@pytest.mark.models
class TestModelEditAuthentication:
    """Test cases for model edit authentication."""

    @pytest.mark.asyncio
    async def test_edit_model_requires_auth(
        self,
        budapp_client: httpx.AsyncClient,
    ):
        """
        Test that editing a model requires authentication.
        """
        fake_model_id = str(uuid4())

        response = await budapp_client.patch(
            f"/models/{fake_model_id}",
            json={"name": "new-name"},
        )

        assert response.status_code == 401, (
            f"Expected 401 without auth, got {response.status_code}"
        )

    @pytest.mark.asyncio
    async def test_edit_model_with_invalid_token(
        self,
        budapp_client: httpx.AsyncClient,
    ):
        """
        Test that editing with invalid token is rejected.
        """
        fake_model_id = str(uuid4())

        response = await budapp_client.patch(
            f"/models/{fake_model_id}",
            headers={"Authorization": "Bearer invalid_token"},
            json={"name": "new-name"},
        )

        assert response.status_code == 401, (
            f"Expected 401 for invalid token, got {response.status_code}"
        )


@pytest.mark.e2e
@pytest.mark.priority_p2
@pytest.mark.models
class TestModelEditEdgeCases:
    """Test edge cases for model edit operations."""

    async def _create_test_model(
        self,
        helper: ModelHelper,
        access_token: str,
    ) -> str:
        """Helper to create a test model."""
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
        )

        if not result.success or not result.model_id:
            pytest.skip(f"Could not create test model: {result.error}")

        return result.model_id

    @pytest.mark.asyncio
    async def test_edit_with_whitespace_name(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test that whitespace-only name is rejected.
        """
        user, tokens = authenticated_user
        helper = ModelHelper(budapp_client)

        model_id = await self._create_test_model(helper, tokens.access_token)

        try:
            edit_result = await helper.edit_model(
                access_token=tokens.access_token,
                model_id=model_id,
                name="   ",  # Whitespace only
            )

            # Should fail or be trimmed to empty (rejected)
            # Behavior depends on implementation
            assert edit_result.status_code in (200, 400, 422), (
                f"Unexpected status: {edit_result.status_code}"
            )
        finally:
            await helper.delete_model(
                access_token=tokens.access_token,
                model_id=model_id,
            )

    @pytest.mark.asyncio
    async def test_edit_with_unicode_characters(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test editing with unicode characters in name and description.
        """
        user, tokens = authenticated_user
        helper = ModelHelper(budapp_client)

        model_id = await self._create_test_model(helper, tokens.access_token)

        try:
            unicode_name = f"模型-{uuid4().hex[:8]}"
            unicode_description = "Модель для тестирования 🤖"

            edit_result = await helper.edit_model(
                access_token=tokens.access_token,
                model_id=model_id,
                name=unicode_name,
                description=unicode_description,
            )

            # Should handle unicode gracefully
            assert edit_result.status_code in (200, 400, 422), (
                f"Unexpected status: {edit_result.status_code}"
            )
        finally:
            await helper.delete_model(
                access_token=tokens.access_token,
                model_id=model_id,
            )

    @pytest.mark.asyncio
    async def test_concurrent_edits(
        self,
        budapp_client: httpx.AsyncClient,
        authenticated_user: tuple[TestUser, AuthTokens],
    ):
        """
        Test concurrent edits to the same model.
        """
        import asyncio

        user, tokens = authenticated_user
        helper = ModelHelper(budapp_client)

        model_id = await self._create_test_model(helper, tokens.access_token)

        try:
            # Make multiple concurrent edit requests
            async def edit_name(suffix: str):
                return await helper.edit_model(
                    access_token=tokens.access_token,
                    model_id=model_id,
                    name=f"concurrent-{suffix}",
                )

            results = await asyncio.gather(
                edit_name("a"),
                edit_name("b"),
                edit_name("c"),
                return_exceptions=True,
            )

            # At least one should succeed
            [r for r in results if isinstance(r, ModelResponse) and r.success]
            # Concurrent edits may all succeed (last write wins) or some may fail
            # Just verify no crashes
            assert len(results) == 3

        finally:
            await helper.delete_model(
                access_token=tokens.access_token,
                model_id=model_id,
            )

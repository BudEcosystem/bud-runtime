"""
Model registry helper for E2E tests.

Provides helper methods for model operations including:
- Cloud model onboarding workflow
- Local model onboarding workflow
- Model listing and filtering
- Model editing
- Model deletion
"""

import asyncio
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from uuid import UUID

import httpx


@dataclass
class ModelResponse:
    """Standard response wrapper for model operations."""
    success: bool
    status_code: int
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    workflow_id: Optional[str] = None
    model_id: Optional[str] = None
    current_step: Optional[int] = None
    total_steps: Optional[int] = None
    workflow_status: Optional[str] = None


class ModelHelper:
    """Helper class for model registry operations."""

    def __init__(self, client: httpx.AsyncClient):
        """Initialize with HTTP client."""
        self.client = client

    def _get_headers(self, access_token: str) -> Dict[str, str]:
        """Get authorization headers."""
        return {"Authorization": f"Bearer {access_token}"}

    # =========================================================================
    # Provider Operations
    # =========================================================================

    async def list_providers(
        self,
        access_token: str,
        capabilities: Optional[str] = None,
    ) -> ModelResponse:
        """
        List available model providers.

        Args:
            access_token: JWT access token
            capabilities: Filter by provider capabilities

        Returns:
            ModelResponse with providers list
        """
        params = {}
        if capabilities:
            params["capabilities"] = capabilities

        try:
            response = await self.client.get(
                "/models/providers",
                headers=self._get_headers(access_token),
                params=params,
            )

            if response.status_code == 200:
                return ModelResponse(
                    success=True,
                    status_code=response.status_code,
                    data=response.json(),
                )
            else:
                return ModelResponse(
                    success=False,
                    status_code=response.status_code,
                    error=response.text,
                )
        except Exception as e:
            return ModelResponse(
                success=False,
                status_code=0,
                error=str(e),
            )

    # =========================================================================
    # Cloud Model Workflow Operations
    # =========================================================================

    async def start_cloud_model_workflow(
        self,
        access_token: str,
        provider_type: str,
        name: str,
        modality: List[str],  # Use "text_input", "text_output", "image_input", etc.
        uri: str,
        provider_id: str,
        tags: Optional[List[Dict[str, str]]] = None,
        total_steps: int = 2,
        cloud_model_id: Optional[str] = None,
        add_model_modality: Optional[List[str]] = None,  # "text", "image", "audio"
    ) -> ModelResponse:
        """
        Start a cloud model onboarding workflow.

        Args:
            access_token: JWT access token
            provider_type: Type of provider (e.g., "cloud_model")
            name: Model name
            modality: List of modalities (e.g., ["text"])
            uri: Model URI
            provider_id: Provider UUID
            tags: Optional list of tags
            total_steps: Total workflow steps
            cloud_model_id: Optional cloud model ID if selecting existing

        Returns:
            ModelResponse with workflow details
        """
        payload = {
            "step_number": 1,
            "workflow_total_steps": total_steps,
            "provider_type": provider_type,
            "name": name,
            "modality": modality,
            "uri": uri,
            "provider_id": provider_id,
            "trigger_workflow": False,
        }

        if tags:
            payload["tags"] = tags

        if cloud_model_id:
            payload["cloud_model_id"] = cloud_model_id

        if add_model_modality:
            payload["add_model_modality"] = add_model_modality

        try:
            response = await self.client.post(
                "/models/cloud-model-workflow",
                headers=self._get_headers(access_token),
                json=payload,
            )

            if response.status_code in (200, 201):
                data = response.json()
                return ModelResponse(
                    success=True,
                    status_code=response.status_code,
                    data=data,
                    workflow_id=str(data.get("workflow_id")),
                    current_step=data.get("current_step"),
                    total_steps=data.get("total_steps"),
                    workflow_status=data.get("status"),
                )
            else:
                return ModelResponse(
                    success=False,
                    status_code=response.status_code,
                    error=response.text,
                )
        except Exception as e:
            return ModelResponse(
                success=False,
                status_code=0,
                error=str(e),
            )

    async def complete_cloud_model_workflow(
        self,
        access_token: str,
        workflow_id: str,
        step_number: int,
        trigger_workflow: bool = True,
    ) -> ModelResponse:
        """
        Complete a cloud model workflow step.

        Args:
            access_token: JWT access token
            workflow_id: Workflow UUID
            step_number: Current step number
            trigger_workflow: Whether to trigger final model creation

        Returns:
            ModelResponse with workflow/model details
        """
        payload = {
            "workflow_id": workflow_id,
            "step_number": step_number,
            "trigger_workflow": trigger_workflow,
        }

        try:
            response = await self.client.post(
                "/models/cloud-model-workflow",
                headers=self._get_headers(access_token),
                json=payload,
            )

            if response.status_code in (200, 201):
                data = response.json()
                workflow_steps = data.get("workflow_steps", {})
                return ModelResponse(
                    success=True,
                    status_code=response.status_code,
                    data=data,
                    workflow_id=str(data.get("workflow_id")),
                    model_id=str(workflow_steps.get("model_id")) if workflow_steps.get("model_id") else None,
                    current_step=data.get("current_step"),
                    total_steps=data.get("total_steps"),
                    workflow_status=data.get("status"),
                )
            else:
                return ModelResponse(
                    success=False,
                    status_code=response.status_code,
                    error=response.text,
                )
        except Exception as e:
            return ModelResponse(
                success=False,
                status_code=0,
                error=str(e),
            )

    async def run_cloud_model_workflow(
        self,
        access_token: str,
        provider_type: str,
        name: str,
        modality: List[str],  # Use "text_input", "text_output", etc.
        uri: str,
        provider_id: str,
        tags: Optional[List[Dict[str, str]]] = None,
        cloud_model_id: Optional[str] = None,
        add_model_modality: Optional[List[str]] = None,  # "text", "image", "audio"
        timeout: int = 60,
    ) -> ModelResponse:
        """
        Run complete cloud model onboarding workflow.

        This is a convenience method that runs all workflow steps.

        Args:
            access_token: JWT access token
            provider_type: Type of provider
            name: Model name
            modality: List of modalities (text_input, text_output, etc.)
            uri: Model URI
            provider_id: Provider UUID
            tags: Optional tags
            cloud_model_id: Optional existing cloud model ID
            add_model_modality: High-level modality (text, image, audio)
            timeout: Timeout in seconds

        Returns:
            ModelResponse with created model details
        """
        # Step 1: Start workflow
        start_result = await self.start_cloud_model_workflow(
            access_token=access_token,
            provider_type=provider_type,
            name=name,
            modality=modality,
            uri=uri,
            provider_id=provider_id,
            tags=tags,
            cloud_model_id=cloud_model_id,
            add_model_modality=add_model_modality,
            total_steps=2,
        )

        if not start_result.success:
            return start_result

        # Step 2: Complete workflow with trigger
        complete_result = await self.complete_cloud_model_workflow(
            access_token=access_token,
            workflow_id=start_result.workflow_id,
            step_number=2,
            trigger_workflow=True,
        )

        return complete_result

    # =========================================================================
    # Local Model Workflow Operations
    # =========================================================================

    async def start_local_model_workflow(
        self,
        access_token: str,
        provider_type: str,
        name: str,
        uri: str,
        author: Optional[str] = None,
        tags: Optional[List[Dict[str, str]]] = None,
        icon: Optional[str] = None,
        total_steps: int = 2,
    ) -> ModelResponse:
        """
        Start a local model onboarding workflow.

        Args:
            access_token: JWT access token
            provider_type: Type (hugging_face, url, disk)
            name: Model name
            uri: Model URI/path
            author: Model author
            tags: Optional tags
            icon: Optional icon
            total_steps: Total workflow steps

        Returns:
            ModelResponse with workflow details
        """
        payload = {
            "step_number": 1,
            "workflow_total_steps": total_steps,
            "provider_type": provider_type,
            "name": name,
            "uri": uri,
            "trigger_workflow": False,
        }

        if author:
            payload["author"] = author
        if tags:
            payload["tags"] = tags
        if icon:
            payload["icon"] = icon

        try:
            response = await self.client.post(
                "/models/local-model-workflow",
                headers=self._get_headers(access_token),
                json=payload,
            )

            if response.status_code in (200, 201):
                data = response.json()
                return ModelResponse(
                    success=True,
                    status_code=response.status_code,
                    data=data,
                    workflow_id=str(data.get("workflow_id")),
                    current_step=data.get("current_step"),
                    total_steps=data.get("total_steps"),
                    workflow_status=data.get("status"),
                )
            else:
                return ModelResponse(
                    success=False,
                    status_code=response.status_code,
                    error=response.text,
                )
        except Exception as e:
            return ModelResponse(
                success=False,
                status_code=0,
                error=str(e),
            )

    async def complete_local_model_workflow(
        self,
        access_token: str,
        workflow_id: str,
        step_number: int,
        trigger_workflow: bool = True,
    ) -> ModelResponse:
        """
        Complete a local model workflow step.

        Args:
            access_token: JWT access token
            workflow_id: Workflow UUID
            step_number: Current step number
            trigger_workflow: Whether to trigger extraction

        Returns:
            ModelResponse with workflow details
        """
        payload = {
            "workflow_id": workflow_id,
            "step_number": step_number,
            "trigger_workflow": trigger_workflow,
        }

        try:
            response = await self.client.post(
                "/models/local-model-workflow",
                headers=self._get_headers(access_token),
                json=payload,
            )

            if response.status_code in (200, 201):
                data = response.json()
                return ModelResponse(
                    success=True,
                    status_code=response.status_code,
                    data=data,
                    workflow_id=str(data.get("workflow_id")),
                    current_step=data.get("current_step"),
                    total_steps=data.get("total_steps"),
                    workflow_status=data.get("status"),
                )
            else:
                return ModelResponse(
                    success=False,
                    status_code=response.status_code,
                    error=response.text,
                )
        except Exception as e:
            return ModelResponse(
                success=False,
                status_code=0,
                error=str(e),
            )

    async def wait_for_local_model_completion(
        self,
        access_token: str,
        workflow_id: str,
        timeout: int = 300,
        poll_interval: int = 5,
    ) -> ModelResponse:
        """
        Wait for local model extraction to complete.

        Local model extraction is async, so we poll until complete.

        Args:
            access_token: JWT access token
            workflow_id: Workflow UUID
            timeout: Max wait time in seconds
            poll_interval: Time between polls in seconds

        Returns:
            ModelResponse with final workflow status
        """
        elapsed = 0

        while elapsed < timeout:
            # Check workflow status by calling the endpoint with current step
            result = await self.complete_local_model_workflow(
                access_token=access_token,
                workflow_id=workflow_id,
                step_number=2,
                trigger_workflow=False,
            )

            if not result.success:
                return result

            status = result.workflow_status
            if status == "SUCCESS":
                return result
            elif status == "FAILED":
                return ModelResponse(
                    success=False,
                    status_code=result.status_code,
                    error=f"Workflow failed: {result.data}",
                    workflow_id=workflow_id,
                    workflow_status=status,
                )

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        return ModelResponse(
            success=False,
            status_code=408,
            error=f"Timeout waiting for model extraction after {timeout}s",
            workflow_id=workflow_id,
        )

    # =========================================================================
    # Model CRUD Operations
    # =========================================================================

    async def list_models(
        self,
        access_token: str,
        limit: int = 10,
        offset: int = 0,
        search: Optional[str] = None,
        provider_type: Optional[str] = None,
        source: Optional[str] = None,
    ) -> ModelResponse:
        """
        List models with optional filtering.

        Args:
            access_token: JWT access token
            limit: Max results to return
            offset: Pagination offset
            search: Search query
            provider_type: Filter by provider type
            source: Filter by source

        Returns:
            ModelResponse with models list
        """
        params = {
            "limit": limit,
            "offset": offset,
        }
        if search:
            params["search"] = search
        if provider_type:
            params["provider_type"] = provider_type
        if source:
            params["source"] = source

        try:
            response = await self.client.get(
                "/models/",
                headers=self._get_headers(access_token),
                params=params,
            )

            if response.status_code == 200:
                return ModelResponse(
                    success=True,
                    status_code=response.status_code,
                    data=response.json(),
                )
            else:
                return ModelResponse(
                    success=False,
                    status_code=response.status_code,
                    error=response.text,
                )
        except Exception as e:
            return ModelResponse(
                success=False,
                status_code=0,
                error=str(e),
            )

    async def get_model(
        self,
        access_token: str,
        model_id: str,
    ) -> ModelResponse:
        """
        Get model details by ID.

        Args:
            access_token: JWT access token
            model_id: Model UUID

        Returns:
            ModelResponse with model details
        """
        try:
            response = await self.client.get(
                f"/models/{model_id}",
                headers=self._get_headers(access_token),
            )

            if response.status_code == 200:
                data = response.json()
                return ModelResponse(
                    success=True,
                    status_code=response.status_code,
                    data=data,
                    model_id=model_id,
                )
            else:
                return ModelResponse(
                    success=False,
                    status_code=response.status_code,
                    error=response.text,
                    model_id=model_id,
                )
        except Exception as e:
            return ModelResponse(
                success=False,
                status_code=0,
                error=str(e),
                model_id=model_id,
            )

    async def edit_model(
        self,
        access_token: str,
        model_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[Dict[str, str]]] = None,
        tasks: Optional[List[Dict[str, str]]] = None,
        github_url: Optional[str] = None,
        huggingface_url: Optional[str] = None,
        website_url: Optional[str] = None,
        paper_urls: Optional[List[str]] = None,
    ) -> ModelResponse:
        """
        Edit model metadata.

        Args:
            access_token: JWT access token
            model_id: Model UUID
            name: New model name
            description: New description
            tags: New tags list
            tasks: New tasks list
            github_url: GitHub URL
            huggingface_url: HuggingFace URL
            website_url: Website URL
            paper_urls: List of paper URLs

        Returns:
            ModelResponse with updated model
        """
        # Build form data (PATCH endpoint uses form data, not JSON)
        data = {}
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description
        if github_url is not None:
            data["github_url"] = github_url
        if huggingface_url is not None:
            data["huggingface_url"] = huggingface_url
        if website_url is not None:
            data["website_url"] = website_url

        # For arrays, we may need to handle JSON serialization
        files = {}

        try:
            headers = self._get_headers(access_token)

            # The endpoint might accept JSON or form data
            # Try JSON first
            json_data = {}
            if name is not None:
                json_data["name"] = name
            if description is not None:
                json_data["description"] = description
            if tags is not None:
                json_data["tags"] = tags
            if tasks is not None:
                json_data["tasks"] = tasks
            if github_url is not None:
                json_data["github_url"] = github_url
            if huggingface_url is not None:
                json_data["huggingface_url"] = huggingface_url
            if website_url is not None:
                json_data["website_url"] = website_url
            if paper_urls is not None:
                json_data["paper_urls"] = paper_urls

            response = await self.client.patch(
                f"/models/{model_id}",
                headers=headers,
                json=json_data,
            )

            if response.status_code in (200, 201):
                return ModelResponse(
                    success=True,
                    status_code=response.status_code,
                    data=response.json(),
                    model_id=model_id,
                )
            else:
                return ModelResponse(
                    success=False,
                    status_code=response.status_code,
                    error=response.text,
                    model_id=model_id,
                )
        except Exception as e:
            return ModelResponse(
                success=False,
                status_code=0,
                error=str(e),
                model_id=model_id,
            )

    async def delete_model(
        self,
        access_token: str,
        model_id: str,
    ) -> ModelResponse:
        """
        Delete a model (soft delete).

        Args:
            access_token: JWT access token
            model_id: Model UUID

        Returns:
            ModelResponse indicating success/failure
        """
        try:
            response = await self.client.delete(
                f"/models/{model_id}",
                headers=self._get_headers(access_token),
            )

            if response.status_code in (200, 204):
                return ModelResponse(
                    success=True,
                    status_code=response.status_code,
                    model_id=model_id,
                )
            else:
                return ModelResponse(
                    success=False,
                    status_code=response.status_code,
                    error=response.text,
                    model_id=model_id,
                )
        except Exception as e:
            return ModelResponse(
                success=False,
                status_code=0,
                error=str(e),
                model_id=model_id,
            )

    # =========================================================================
    # Supporting Operations
    # =========================================================================

    async def list_tags(
        self,
        access_token: str,
        search: Optional[str] = None,
        limit: int = 20,
    ) -> ModelResponse:
        """List available model tags."""
        params = {"limit": limit}
        if search:
            params["search"] = search

        try:
            response = await self.client.get(
                "/models/tags",
                headers=self._get_headers(access_token),
                params=params,
            )

            if response.status_code == 200:
                return ModelResponse(
                    success=True,
                    status_code=response.status_code,
                    data=response.json(),
                )
            else:
                return ModelResponse(
                    success=False,
                    status_code=response.status_code,
                    error=response.text,
                )
        except Exception as e:
            return ModelResponse(
                success=False,
                status_code=0,
                error=str(e),
            )

    async def list_tasks(
        self,
        access_token: str,
        search: Optional[str] = None,
        limit: int = 20,
    ) -> ModelResponse:
        """List available model tasks."""
        params = {"limit": limit}
        if search:
            params["search"] = search

        try:
            response = await self.client.get(
                "/models/tasks",
                headers=self._get_headers(access_token),
                params=params,
            )

            if response.status_code == 200:
                return ModelResponse(
                    success=True,
                    status_code=response.status_code,
                    data=response.json(),
                )
            else:
                return ModelResponse(
                    success=False,
                    status_code=response.status_code,
                    error=response.text,
                )
        except Exception as e:
            return ModelResponse(
                success=False,
                status_code=0,
                error=str(e),
            )

    async def list_authors(
        self,
        access_token: str,
        search: Optional[str] = None,
        limit: int = 20,
    ) -> ModelResponse:
        """List model authors."""
        params = {"limit": limit}
        if search:
            params["search"] = search

        try:
            response = await self.client.get(
                "/models/authors",
                headers=self._get_headers(access_token),
                params=params,
            )

            if response.status_code == 200:
                return ModelResponse(
                    success=True,
                    status_code=response.status_code,
                    data=response.json(),
                )
            else:
                return ModelResponse(
                    success=False,
                    status_code=response.status_code,
                    error=response.text,
                )
        except Exception as e:
            return ModelResponse(
                success=False,
                status_code=0,
                error=str(e),
            )

    async def get_model_leaderboards(
        self,
        access_token: str,
        model_id: str,
    ) -> ModelResponse:
        """Get leaderboard data for a model."""
        try:
            response = await self.client.get(
                f"/models/{model_id}/leaderboards",
                headers=self._get_headers(access_token),
            )

            if response.status_code == 200:
                return ModelResponse(
                    success=True,
                    status_code=response.status_code,
                    data=response.json(),
                    model_id=model_id,
                )
            else:
                return ModelResponse(
                    success=False,
                    status_code=response.status_code,
                    error=response.text,
                    model_id=model_id,
                )
        except Exception as e:
            return ModelResponse(
                success=False,
                status_code=0,
                error=str(e),
                model_id=model_id,
            )

    async def list_catalog(
        self,
        access_token: str,
        limit: int = 10,
        offset: int = 0,
    ) -> ModelResponse:
        """List published models in catalog."""
        params = {
            "limit": limit,
            "offset": offset,
        }

        try:
            response = await self.client.get(
                "/models/catalog",
                headers=self._get_headers(access_token),
                params=params,
            )

            if response.status_code == 200:
                return ModelResponse(
                    success=True,
                    status_code=response.status_code,
                    data=response.json(),
                )
            else:
                return ModelResponse(
                    success=False,
                    status_code=response.status_code,
                    error=response.text,
                )
        except Exception as e:
            return ModelResponse(
                success=False,
                status_code=0,
                error=str(e),
            )

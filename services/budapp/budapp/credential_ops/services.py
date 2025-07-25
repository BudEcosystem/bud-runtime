import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from fastapi import HTTPException, status
from fastapi.exceptions import HTTPException

from budapp.commons import logging
from budapp.commons.config import app_settings
from budapp.commons.constants import EndpointStatusEnum, ModelProviderTypeEnum, PermissionEnum, ProjectStatusEnum
from budapp.commons.db_utils import SessionMixin
from budapp.commons.security import RSAHandler
from budapp.endpoint_ops.crud import AdapterDataManager, EndpointDataManager
from budapp.endpoint_ops.models import Endpoint as EndpointModel
from budapp.model_ops.crud import ProviderDataManager

# from ..models import Route as RouteModel
from budapp.model_ops.models import Model
from budapp.model_ops.models import Provider as ProviderModel
from budapp.permissions.crud import PermissionDataManager, ProjectPermissionDataManager
from budapp.project_ops.crud import ProjectDataManager
from budapp.project_ops.services import ProjectService
from budapp.shared.redis_service import RedisService, cache

from ..project_ops.models import Project as ProjectModel
from .crud import CloudProviderDataManager, CredentialDataManager, ProprietaryCredentialDataManager
from .helpers import generate_random_string
from .models import CloudCredentials, CloudProviders
from .models import Credential as CredentialModel
from .models import ProprietaryCredential as ProprietaryCredentialModel
from .schemas import (
    BudCredentialCreate,
    CacheConfig,
    CloudProvidersCreateRequest,
    CredentialDetails,
    CredentialRequest,
    CredentialResponse,
    CredentialUpdate,
    ModelConfig,
    ProprietaryCredentialDetailedView,
    ProprietaryCredentialRequest,
    ProprietaryCredentialResponse,
    ProprietaryCredentialResponseList,
    ProprietaryCredentialUpdate,
    RouterConfig,
    RoutingPolicy,
)


logger = logging.get_logger(__name__)


class CredentialService(SessionMixin):
    async def _check_duplicate_credential(self, credential: dict) -> bool:
        db_credential = await CredentialDataManager(self.session).retrieve_credential_by_fields(
            {"name": credential["name"], "project_id": credential["project_id"]}, missing_ok=True
        )
        return db_credential is not None

    async def add_credential(self, current_user_id: UUID, credential: CredentialRequest) -> CredentialResponse:
        # Validate project id
        db_project = await ProjectDataManager(self.session).retrieve_project_by_fields(
            {"id": credential.project_id, "status": ProjectStatusEnum.ACTIVE}
        )

        if await self._check_duplicate_credential({"name": credential.name, "project_id": credential.project_id}):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Credential already exists with the same name",
            )
        # Check user has authority to create credential for project
        db_permission = await PermissionDataManager(self.session).retrieve_permission_by_fields(
            {"user_id": current_user_id}, missing_ok=True
        )
        user_scopes = db_permission.scopes_list if db_permission else []

        # NOTE: user with project:manage scope can create credential for any project. Otherwise user must be a project member
        if PermissionEnum.PROJECT_MANAGE.value not in user_scopes:
            # Check user has access to project
            await ProjectService(self.session).check_project_membership(db_project.id, current_user_id)

        # Add or generate credential
        db_credential = await self.add_or_generate_credential(credential, current_user_id)

        await self.update_proxy_cache(db_credential.project_id, db_credential.key, db_credential.expiry)

        credential_response = CredentialResponse(
            name=db_credential.name,
            project_id=db_credential.project_id,
            key=await RSAHandler().encrypt(db_credential.key),
            expiry=db_credential.expiry,
            max_budget=db_credential.max_budget,
            model_budgets=db_credential.model_budgets,
            id=db_credential.id,
        )

        return credential_response

    async def add_or_generate_credential(self, request: CredentialRequest, user_id: UUID) -> CredentialModel:
        # Generate new credential if type is BUDSERVE
        api_key = f"budserve_{await generate_random_string(40)}"

        expiry = datetime.now(UTC) + timedelta(days=request.expiry) if request.expiry else None
        credential_data = BudCredentialCreate(
            name=request.name,
            user_id=user_id,
            project_id=request.project_id,
            expiry=expiry,
            key=api_key,
            max_budget=request.max_budget,
            model_budgets=request.model_budgets,
        )

        # Insert credential in to database
        credential_model = CredentialModel(**credential_data.model_dump())
        credential_model.hashed_key = CredentialModel.set_hashed_key(credential_model.key)
        db_credential = await CredentialDataManager(self.session).create_credential(credential_model)
        logger.info(f"Credential inserted to database: {db_credential.id}")

        return db_credential

    async def update_proxy_cache(
        self, project_id: UUID, api_key: Optional[str] = None, expiry: Optional[datetime] = None
    ):
        """Update the proxy cache in Redis with the latest endpoints and adapters for a given project.

        This method collects all active endpoints and adapters associated with the specified project,
        maps their names to their IDs with additional metadata (model_id, project_id), and updates
        the Redis cache with this information.

        Args:
            api_key (str): The API key to associate with the project and its models.
            project_id (UUID): The unique identifier of the project whose endpoints and adapters are to be cached.

        Returns:
            None
        """
        keys_to_update = []
        if api_key is None:
            db_credentials, count = await CredentialDataManager(self.session).get_all_credentials(
                filters={"project_id": project_id}
            )
            for credential in db_credentials:
                keys_to_update.append({"api_key": credential.key, "expiry": credential.expiry})
        else:
            keys_to_update.append({"api_key": api_key, "expiry": expiry})

        models = {}

        # Get endpoints with their model_id and project_id
        endpoints = await EndpointDataManager(self.session).get_all_running_endpoints(project_id)
        for endpoint in endpoints:
            models[endpoint.name] = {
                "endpoint_id": str(endpoint.id),
                "model_id": str(endpoint.model_id),
                "project_id": str(endpoint.project_id),
            }

        # Get adapters with their model_id and project_id
        adapters, _ = await AdapterDataManager(self.session).get_all_adapters_in_project(project_id)
        for adapter in adapters:
            # For adapters, endpoint_id refers to the adapter id itself
            models[adapter.name] = {
                "endpoint_id": str(adapter.id),
                "model_id": str(adapter.model_id),
                "project_id": str(project_id),  # Adapters don't have direct project_id, use the passed project_id
            }

        redis_service = RedisService()

        for key in keys_to_update:
            ttl = None
            if key["expiry"]:
                ttl = int((key["expiry"] - datetime.now()).total_seconds())
            await redis_service.set(f"api_key:{key['api_key']}", json.dumps({key["api_key"]: models}), ex=ttl)

        logger.info("Updated api keys in proxy cache")

    async def get_credentials(
        self,
        offset: int = 0,
        limit: int = 10,
        filters: Optional[Dict] = None,
        order_by: Optional[List[str]] = None,
        search: bool = False,
    ) -> List[CredentialDetails]:
        # Check user permissions for viewing credentials
        # db_permission = await PermissionDataManager(self.session).retrieve_permission_by_fields({"user_id": user_id}, missing_ok=True)
        # user_scopes = db_permission.scopes_list if db_permission else []
        # if PermissionEnum.PROJECT_MANAGE.value not in user_scopes:
        #     # Check user has access to project
        #     await ProjectService(self.session).check_project_membership(project_id, user_id)
        filters = filters or {}
        order_by = order_by or []
        db_credentials, count = await CredentialDataManager(self.session).get_all_credentials(
            offset, limit, filters, order_by, search
        )
        return await self.parse_credentials(db_credentials), count

    async def retrieve_credential_details(self, api_key: str) -> CredentialModel:
        db_credential = await CredentialDataManager(self.session).retrieve_credential_by_fields({"key": api_key})
        return db_credential

    async def parse_credentials(
        self,
        db_credentials: List[CredentialModel],
    ) -> List[CredentialDetails]:
        # Store bud serve credentials in a list
        bud_serve_credentials = []

        # Iterate over credentials and append as per type
        for db_credential in db_credentials:
            if db_credential.project and db_credential.project.benchmark:
                continue
            bud_serve_credentials.append(
                CredentialDetails(
                    name=db_credential.name,
                    project=db_credential.project,
                    key=await RSAHandler().encrypt(db_credential.key),
                    expiry=db_credential.expiry,
                    max_budget=db_credential.max_budget,
                    model_budgets=db_credential.model_budgets,
                    id=db_credential.id,
                    last_used_at=db_credential.last_used_at,
                )
            )
        return bud_serve_credentials

    async def delete_credential(self, credential_id: UUID, user_id: UUID) -> None:
        """Delete the credential from the database."""
        # Retrieve the credential from the database
        db_credential = await CredentialDataManager(self.session).retrieve_credential_by_fields(
            {"id": credential_id, "user_id": user_id}
        )

        if db_credential.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have permission to update this credential",
            )

        # project_id = db_credential.project_id
        # # Check user permissions for viewing credentials
        # db_permission = await PermissionDataManager(self.session).retrieve_permission_by_fields({"user_id": user_id}, missing_ok=True)
        # user_scopes = db_permission.scopes_list if db_permission else []
        # if PermissionEnum.PROJECT_MANAGE.value not in user_scopes:
        #     # Check user has access to project
        #     await ProjectService(self.session).check_project_membership(project_id, user_id)

        # delete proxy cache related to this credential
        api_key = db_credential.key
        redis_service = RedisService()
        await redis_service.delete_keys_by_pattern(f"api_key:{api_key}*")
        # Delete the credential from the database
        await CredentialDataManager(self.session).delete_credential(db_credential)

        return

    async def update_credential(self, data: CredentialUpdate, credential_id: UUID, user_id: UUID) -> CredentialModel:
        """Update the OpenAI or HuggingFace credential in the database."""
        # Check if credential exists
        db_credential = await CredentialDataManager(self.session).retrieve_credential_by_fields({"id": credential_id})

        if db_credential.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have permission to update this credential",
            )

        # project_id = db_credential.project_id

        # # Check user permissions for viewing credentials
        # db_permission = await PermissionDataManager(self.session).retrieve_permission_by_fields({"user_id": user_id}, missing_ok=True)
        # user_scopes = db_permission.scopes_list if db_permission else []
        # if PermissionEnum.PROJECT_MANAGE.value not in user_scopes:
        #     # Check user has access to project
        #     await ProjectService(self.session).check_project_membership(project_id, user_id)

        credential_update_data = data.model_dump(exclude_none=True)
        if credential_update_data.get("name", None):
            if await self._check_duplicate_credential(
                {"name": credential_update_data["name"], "project_id": db_credential.project_id}
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Credential already exists with the same name",
                )
            db_credential.name = credential_update_data["name"]

        if credential_update_data.get("expiry", None):
            credential_update_data["expiry"] = datetime.now(UTC) + timedelta(days=data.expiry)

        if credential_update_data.get("max_budget", None):
            if (
                credential_update_data.get("model_budgets", None) is not None
                and db_credential.model_budgets
                and sum(db_credential.model_budgets.values()) > data.max_budget
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Sum of model budgets - {db_credential.model_budgets} - should not exceed max budget - {data.max_budget}",
                )
        elif db_credential.max_budget is not None:
            credential_update_data["max_budget"] = None

        if credential_update_data.get("model_budgets", None):
            if (
                credential_update_data.get("max_budget", None) is not None
                and db_credential.max_budget
                and sum(credential_update_data["model_budgets"].values()) > db_credential.max_budget
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"""Sum of model budgets - {credential_update_data["model_budgets"]}
                        should not exceed max budget - {db_credential.max_budget}""",
                )
            credential_update_data["model_budgets"] = {
                str(k): v for k, v in credential_update_data["model_budgets"].items()
            }

        # Update the credential in the database
        db_credential = await CredentialDataManager(self.session).update_credential_by_fields(
            db_credential, credential_update_data
        )

        return db_credential

    # @cache(
    #     key_func=lambda s, api_key, endpoint_name: f"router_config:{api_key}:{endpoint_name}",
    #     ttl=3600,
    #     serializer=lambda x: x.model_dump_json(),
    #     deserializer=lambda x: RouterConfig.model_validate_json(x),
    # )
    async def get_router_config(
        self, api_key: Optional[str], endpoint_name: str, current_user_id: Optional[UUID], project_id: Optional[UUID]
    ) -> RouterConfig:
        router_config = None
        db_project = None

        # Project can be identified by either api_key or current_user_id and project_id
        if api_key:
            db_credential = await self.retrieve_credential_details(api_key)
            db_project = db_credential.project
        elif current_user_id and project_id:
            db_project = await ProjectDataManager(self.session).retrieve_by_fields(
                ProjectModel, {"id": project_id, "status": ProjectStatusEnum.ACTIVE}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Api-key or User accessible project id required.",
            )

        endpoints = db_project.endpoints
        db_endpoint = None
        adapters, _ = await AdapterDataManager(self.session).get_all_adapters_in_project(db_project.id)
        logger.info("adapters: %s", adapters)
        db_router = None
        db_adapter = None
        for endpoint in endpoints:
            if endpoint.name == endpoint_name and endpoint.status == EndpointStatusEnum.RUNNING.value:
                db_endpoint = endpoint
                break
        if not db_endpoint and adapters:
            for adapter in adapters:
                if adapter.name == endpoint_name:
                    db_adapter = adapter
                    break
        if not db_endpoint and not db_adapter:
            for router in db_project.routers:
                if router.name == endpoint_name:
                    db_router = router
                    break
        if not db_endpoint and not db_adapter and not db_router:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint or Route not found")

        if db_router:
            router_config = await self.generate_route_config_from_router(db_router)
        elif db_adapter:
            db_model = db_adapter.model
            router_config = await self.generate_route_config_from_adapter(db_adapter, db_model)
        else:
            db_model = db_endpoint.model
            router_config = await self.generate_route_config_from_endpoint(db_endpoint, db_model)

        return router_config

    async def generate_route_config_from_endpoint(self, db_endpoint: EndpointModel, db_model: Model) -> RouterConfig:
        db_project = db_endpoint.project
        db_model = db_endpoint.model
        # For cloud model, the model name is the endpoint name
        # because cloud model deployment is done using endpoint name and proprietary credentials
        # For other models, the model name is the uri
        # because central litellm proxy uses openai client to forward request to actual bud runtime deployment
        # which accepts model uri as model parameter
        actual_model_name = f"openai/{db_endpoint.name}"
        api_base = db_endpoint.url
        if db_model.provider_type != ModelProviderTypeEnum.CLOUD_MODEL:
            api_base = f"{db_endpoint.url}/v1"
            deploy_model_uri = f"{db_endpoint.namespace}"
            actual_model_name = f"openai/{deploy_model_uri}"
        else:
            model_uri = db_model.uri
            model_source = db_model.source
            if model_uri.startswith(f"{model_source}/"):
                model_uri = model_uri.removeprefix(f"{model_source}/")
            deploy_model_uri = f"{model_source}/{model_uri}"
            actual_model_name = f"openai/{db_endpoint.namespace}"

        model_config = ModelConfig(
            model_name=db_endpoint.namespace,
            litellm_params={
                "model": actual_model_name,
                "api_base": api_base,
                "api_key": app_settings.litellm_proxy_master_key,
            },
            model_info={
                "id": db_model.id,
                "metadata": {
                    "name": db_model.name,
                    "provider": db_model.provider.name,
                    "modality": [modality.value for modality in db_model.modality],
                    "endpoint_id": db_endpoint.id,
                    "cloud": db_model.provider_type == ModelProviderTypeEnum.CLOUD_MODEL,
                    "deploy_model_uri": deploy_model_uri,
                },
            },
            input_cost_per_token=None,
            output_cost_per_token=None,
            tpm=None,
            rpm=None,
            complexity_threshold=None,
            weight=None,
            cool_down_period=None,
            fallback_endpoint_ids=None,
        )

        router_config = RouterConfig(
            project_id=db_project.id,
            project_name=db_project.name,
            endpoint_name=db_endpoint.name,
            routing_policy=None,
            cache_configuration=CacheConfig(**json.loads(db_endpoint.cache_config))
            if db_endpoint.cache_enabled
            else None,
            model_configuration=[model_config],
        )

        return router_config

    async def generate_route_config_from_adapter(self, db_adapter, db_model) -> RouterConfig:
        """Generate a RouterConfig from the given adapter and model.

        Args:
            db_adapter: The database adapter instance.
            db_model: The database model instance.

        Returns:
            RouterConfig: The generated router configuration.
        """
        db_endpoint = db_adapter.endpoint
        db_model = db_adapter.model

        actual_model_name = f"openai/{db_adapter.name}"

        api_base = f"{db_endpoint.url}/v1"
        deploy_model_uri = f"{db_adapter.deployment_name}"
        actual_model_name = f"openai/{deploy_model_uri}"

        model_config = ModelConfig(
            model_name=db_adapter.deployment_name,
            litellm_params={
                "model": actual_model_name,
                "api_base": api_base,
                "api_key": app_settings.litellm_proxy_master_key,
            },
            model_info={
                "id": db_model.id,
                "metadata": {
                    "name": db_model.name,
                    "provider": db_model.provider.name,
                    "modality": [modality.value for modality in db_model.modality],
                    "endpoint_id": db_endpoint.id,
                    "adapter_id": db_adapter.id,
                    "cloud": db_model.provider_type == ModelProviderTypeEnum.CLOUD_MODEL,
                    "deploy_model_uri": deploy_model_uri,
                },
            },
            input_cost_per_token=None,
            output_cost_per_token=None,
            tpm=None,
            rpm=None,
            complexity_threshold=None,
            weight=None,
            cool_down_period=None,
            fallback_endpoint_ids=None,
        )

        router_config = RouterConfig(
            project_id=db_endpoint.project_id,
            project_name=db_endpoint.project.name,
            endpoint_name=db_adapter.name,
            routing_policy=None,
            cache_configuration=CacheConfig(**json.loads(db_endpoint.cache_config))
            if db_endpoint.cache_enabled
            else None,
            model_configuration=[model_config],
        )

        return router_config

    async def generate_route_config_from_router(self, db_router) -> RouterConfig:
        db_project = db_router.project
        model_configs = []

        for db_router_endpoint in db_router.endpoints:
            db_endpoint = db_router_endpoint.endpoint
            db_model = db_endpoint.model
            actual_model_name = f"openai/{db_endpoint.name}"
            api_base = db_endpoint.url
            if db_model.provider_type != ModelProviderTypeEnum.CLOUD_MODEL:
                api_base = f"{db_endpoint.url}/v1"
                deploy_model_uri = f"{app_settings.add_model_dir}/{db_model.local_path}"
                actual_model_name = f"openai/{deploy_model_uri}"
            else:
                model_uri = db_model.uri
                model_source = db_model.source
                if model_uri.startswith(f"{model_source}/"):
                    model_uri = model_uri.removeprefix(f"{model_source}/")
                deploy_model_uri = f"{model_source}/{model_uri}"

            # TODO: Take fallback endpoint ids from router
            model_configs.append(
                ModelConfig(
                    model_name=db_endpoint.name,
                    litellm_params={
                        "model": actual_model_name,
                        "api_base": api_base,
                        "api_key": app_settings.litellm_proxy_master_key,
                    },
                    model_info={
                        "id": db_model.id,
                        "metadata": {
                            "name": db_model.name,
                            "provider": db_model.provider.name,
                            "modality": [modality.value for modality in db_model.modality],
                            "endpoint_id": db_endpoint.id,
                            "cloud": db_model.provider_type == ModelProviderTypeEnum.CLOUD_MODEL,
                            "deploy_model_uri": deploy_model_uri,
                        },
                        # "sequence_length": 4096,
                        "tasks": db_model.tasks,
                        "domains": db_model.tags,
                        "languages": db_model.languages,
                        "use_cases": db_model.use_cases,
                        "evals": {},
                    },
                    input_cost_per_token=None,
                    output_cost_per_token=None,
                    tpm=db_router_endpoint.tpm,
                    rpm=db_router_endpoint.rpm,
                    complexity_threshold=None,
                    weight=db_router_endpoint.weight,
                    cool_down_period=db_router_endpoint.cool_down_period,
                    fallback_endpoint_ids=db_router_endpoint.fallback_endpoint_ids,
                )
            )

        router_config = RouterConfig(
            project_id=db_project.id,
            project_name=db_project.name,
            endpoint_name=db_router.name,
            routing_policy=RoutingPolicy(
                name=db_router.name,
                strategies=db_router.routing_strategy,
                fallback_policies=[],
                decision_mode="intersection",
            ),
            cache_configuration=None,  # TODO: add cache configuration per endpoint
            model_configuration=model_configs,
        )

        return router_config

    @cache(
        key_func=lambda s, api_key: f"decrypted_key:{api_key}",
        ttl=3600,
        serializer=lambda x: x,
        deserializer=lambda x: x,
    )
    async def decrypt_credential(self, api_key: str) -> str:
        return await RSAHandler().decrypt(api_key)


class ProprietaryCredentialService(SessionMixin):
    async def add_credential(
        self, current_user_id: UUID, credential: ProprietaryCredentialRequest
    ) -> ProprietaryCredentialResponse:
        # Check duplicate credential exists with same name and type for user_id
        db_credential = await ProprietaryCredentialDataManager(self.session).retrieve_credential_by_fields(
            {"name": credential.name, "type": credential.type.value, "user_id": current_user_id}, missing_ok=True
        )

        # Raise error if credential already exists with same name and type
        if db_credential:
            error_msg = f"{credential.type.value.capitalize()} credential already exists with the same name, change name or update existing credential"
            logger.error(error_msg)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg,
            )

        # Encrypt credential and add in db
        db_credential = await self.add_encrypted_credential(credential, current_user_id)

        credential_response = ProprietaryCredentialResponse(
            name=db_credential.name,
            type=db_credential.type,
            id=db_credential.id,
            other_provider_creds=db_credential.other_provider_creds,
        )

        return credential_response

    async def add_encrypted_credential(
        self, credential: ProprietaryCredentialRequest, user_id: UUID
    ) -> ProprietaryCredentialModel:
        # Encrypt proprietary credentials
        if credential.other_provider_creds:
            for key, value in credential.other_provider_creds.items():
                credential.other_provider_creds[key] = await RSAHandler().encrypt(value)

        # get provider id
        if not credential.provider_id:
            db_provider = await ProviderDataManager(self.session).retrieve_by_fields(
                ProviderModel, {"type": credential.type.value}
            )
            credential.provider_id = db_provider.id

        # Insert credential in to database
        credential_model = ProprietaryCredentialModel(**credential.model_dump(), user_id=user_id)
        credential_model.type = credential_model.type.value
        db_credential = await ProprietaryCredentialDataManager(self.session).create_credential(credential_model)
        logger.info(f"Proprietary Credential inserted to database: {db_credential.id}")

        return db_credential

    async def get_all_credentials(
        self,
        offset: int = 0,
        limit: int = 10,
        filters: Optional[Dict] = None,
        order_by: Optional[List[str]] = None,
        search: bool = False,
    ) -> tuple[list[ProprietaryCredentialResponseList], int]:
        filters = filters or {}
        order_by = order_by or []

        num_of_endpoint_sort = None
        for field, direction in order_by:
            if field == "num_of_endpoints":
                num_of_endpoint_sort = (field, direction)
                order_by.remove(num_of_endpoint_sort)
                break

        if filters.get("type"):
            filters["type"] = filters["type"].value

        db_credentials, count = await ProprietaryCredentialDataManager(self.session).get_all_credentials(
            offset, limit, filters, order_by, search
        )
        cred_list = await self.parse_credentials(db_credentials)
        if num_of_endpoint_sort:
            cred_list.sort(key=lambda x: x.num_of_endpoints, reverse=num_of_endpoint_sort[1] == "desc")
        return cred_list, count

    async def parse_credentials(
        self,
        db_credentials: List[ProprietaryCredentialModel],
    ) -> List[ProprietaryCredentialResponseList]:
        # Parse credentials to a common format
        result = []

        # Iterate over credentials and append as per type
        for db_credential in db_credentials:
            # if db_credential.other_provider_creds:
            #     for key, value in db_credential.other_provider_creds.items():
            #         db_credential.other_provider_creds[key] = await RSAHandler().decrypt(value)
            running_endpoints = [
                endpoint for endpoint in db_credential.endpoints if endpoint.status == EndpointStatusEnum.RUNNING
            ]
            result.append(
                ProprietaryCredentialResponseList(
                    name=db_credential.name,
                    type=db_credential.type,
                    other_provider_creds=db_credential.other_provider_creds,
                    id=db_credential.id,
                    created_at=db_credential.created_at,
                    num_of_endpoints=len(running_endpoints),
                    provider_icon=db_credential.provider.icon,
                )
            )

        return result

    async def update_credential(
        self,
        credential_id: UUID,
        data: ProprietaryCredentialUpdate,
        current_user_id: UUID,
    ) -> ProprietaryCredentialResponse:
        # Check if credential exists
        db_credential = await ProprietaryCredentialDataManager(self.session).retrieve_credential_by_fields(
            {"id": credential_id}
        )

        if db_credential.user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have permission to update this credential",
            )

        # Check data type
        if data.type != db_credential.type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Credential type cannot be changed from {db_credential.type} to {data.type.value}",
            )

        proprietary_update_data = data.model_dump(exclude_none=True, exclude={"type"})
        # Handle name
        if proprietary_update_data.get("name", None):
            # Check duplicate credential exists with same name and type for user_id
            db_credential_by_name = await ProprietaryCredentialDataManager(self.session).retrieve_credential_by_fields(
                {"name": data.name, "type": db_credential.type, "user_id": current_user_id}, missing_ok=True
            )

            # Raise error if credential already exists with same name and type
            if db_credential_by_name:
                error_msg = f"Update failed : {db_credential.type} credential already exists with the same name"
                logger.error(error_msg)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_msg,
                )

        if proprietary_update_data.get("other_provider_creds", None) and data.other_provider_creds:
            # if proprietary_update_data has other_provider_creds,
            # then data will also have attribute other_provider_creds
            # the data.other_provider_creds clause is added to resolve mypy error
            for key, value in data.other_provider_creds.items():
                proprietary_update_data["other_provider_creds"][key] = await RSAHandler().encrypt(value)

        # Handle endpoint
        if proprietary_update_data.get("endpoint_id", None):
            credential_endpoints = db_credential.endpoints
            endpoint_id = data.endpoint_id
            del proprietary_update_data["endpoint_id"]

            # check if endpoint exists in credential endpoints
            for endpoint in credential_endpoints:
                if endpoint.id == endpoint_id:
                    break
            else:
                # Check if endpoint exists
                db_endpoint = await EndpointDataManager(self.session).retrieve_endpoint_by_fields({"id": endpoint_id})
                project_id = db_endpoint.project_id
                # Check user has authority to create credential for project
                db_permission = await PermissionDataManager(self.session).retrieve_permission_by_fields(
                    {"user_id": current_user_id}, missing_ok=True
                )
                global_user_scopes = db_permission.scopes_list if db_permission else []
                if PermissionEnum.PROJECT_MANAGE.value not in global_user_scopes:
                    db_project_permission = await ProjectPermissionDataManager(
                        self.session
                    ).retrieve_project_permission_by_fields(
                        {"user_id": current_user_id, "project_id": project_id},
                        missing_ok=True,
                    )
                    project_user_scopes = db_project_permission.scopes_list if db_project_permission else []

                    # Check user has access to endpoint
                    if PermissionEnum.ENDPOINT_MANAGE.value not in project_user_scopes:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="User does not have permission to update credential for this endpoint",
                        )
                db_credential.endpoints.append(db_endpoint)

        # Update the credential in the database
        db_credential = await ProprietaryCredentialDataManager(self.session).update_credential_by_fields(
            db_credential, proprietary_update_data
        )

        return db_credential

    async def delete_credential(self, credential_id: UUID, current_user_id: UUID):
        """Delete the proprietary credential from the database."""
        # Retrieve the credential from the database
        db_credential = await ProprietaryCredentialDataManager(self.session).retrieve_credential_by_fields(
            {"id": credential_id}
        )

        if db_credential.user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have permission to delete this credential",
            )

        endpoints = db_credential.endpoints
        if endpoints:
            project_names = [endpoint.project.name for endpoint in endpoints]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"""Credential is associated with deployed models in the below projects :
                {", ".join(project_names)}.
                Please delete the deployed models first or link other credentials to those models for deleting this credential""",
            )

        # Delete the credential from the database
        await ProprietaryCredentialDataManager(self.session).delete_credential(db_credential)

    async def get_credential_details(
        self, credential_id: UUID, detailed_view: bool = False
    ) -> Union[ProprietaryCredentialModel, ProprietaryCredentialDetailedView]:
        """Get details of a proprietary credential."""
        db_credential = await ProprietaryCredentialDataManager(self.session).retrieve_credential_by_fields(
            {"id": credential_id}
        )
        # Decrypt proprietary credentials
        if not detailed_view and db_credential.other_provider_creds:
            for key, value in db_credential.other_provider_creds.items():
                db_credential.other_provider_creds[key] = await RSAHandler().decrypt(value)
        if detailed_view:
            endpoints = []
            for endpoint in db_credential.endpoints:
                if endpoint.status == EndpointStatusEnum.RUNNING.value:
                    endpoints.append(
                        {
                            "id": str(endpoint.id),
                            "name": endpoint.name,
                            "status": endpoint.status.value,
                            "project_info": {
                                "id": str(endpoint.project.id),
                                "name": endpoint.project.name,
                            },
                            "model_info": {
                                "id": str(endpoint.model.id),
                                "name": endpoint.model.name,
                                "icon": endpoint.model.provider.icon,
                                "modality": endpoint.model.modality.value,
                            },
                            "created_at": endpoint.created_at,
                        }
                    )
            return ProprietaryCredentialDetailedView(
                name=db_credential.name,
                type=db_credential.type,
                other_provider_creds=db_credential.other_provider_creds,
                id=db_credential.id,
                created_at=db_credential.created_at,
                endpoints=endpoints,
                num_of_endpoints=len(db_credential.endpoints),
                provider_icon=db_credential.provider.icon,
            )
        return db_credential


class ClusterProviderService(SessionMixin):
    """ClusterProviderService is a service class that provides cluster-related operations."""

    async def create_provider_credential(self, req: CloudProvidersCreateRequest, current_user_id: UUID) -> None:
        """Create a new credential for a provider.

        Args:
            req: CloudProvidersCreateRequest containing provider_id and credential_values

        Raises:
            ValueError: If provider is not found or required fields are missing
            HTTPException: If there are validation errors
        """
        try:
            # Convert provider_id string to UUID if needed
            provider_id = req.provider_id
            if not isinstance(provider_id, uuid.UUID):
                try:
                    provider_id = uuid.UUID(provider_id)
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid provider_id format: {provider_id}"
                    ) from None

            # Get the provider from the database
            provider = await CloudProviderDataManager(self.session).retrieve_by_fields(
                CloudProviders, {"id": provider_id}
            )

            # Validate the provider
            if not provider:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=f"Provider with id {provider_id} not found"
                )

            # Handle schema_definition which might be a dict or a JSON string
            schema = self._get_schema_definition(provider.schema_definition)

            # Get the required fields from the schema
            required_fields = schema.get("required", [])

            # Validate the required fields
            for field in required_fields:
                if field not in req.credential_values:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Required field '{field}' is missing in the credential values",
                    )

            # Save the credential values
            cloud_credential = CloudCredentials(
                user_id=current_user_id,
                provider_id=provider_id,
                credential=req.credential_values,
                credential_name=req.credential_name,
            )
            await CloudProviderDataManager(self.session).insert_one(cloud_credential)

            logger.debug(f"Created credential for provider {cloud_credential.id}")
        except HTTPException:
            # Re-raise HTTP exceptions without additional logging
            raise
        except Exception as e:
            logger.error(f"Failed to create credential for provider {req.provider_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create credential: {str(e)}"
            ) from None

    def _get_schema_definition(self, schema_definition: Union[Dict[str, Any], str]) -> Dict[str, Any]:
        """Parse the schema_definition which could be a dict or a JSON string.

        Args:
            schema_definition: The schema definition as either a dict or JSON string

        Returns:
            Dict containing the parsed schema

        Raises:
            ValueError: If the schema_definition is invalid
        """
        if isinstance(schema_definition, dict):
            return schema_definition
        elif isinstance(schema_definition, str):
            try:
                return json.loads(schema_definition)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid schema_definition JSON: {e}")
                raise ValueError(f"Invalid schema_definition: {e}")
        else:
            logger.error(f"Unexpected schema_definition type: {type(schema_definition)}")
            return {}  # Return empty dict as fallback

    async def get_provider_regions(self, unique_id: str) -> List[Dict[str, Any]]:
        """Get the regions supported by a specific cloud provider.

        Args:
            provider: The cloud provider entity

        Returns:
            List of regions as dictionaries with at least 'id' and 'name' keys
        """
        provider_regions = {
            "aws": [
                {"id": "us-east-1", "name": "US East (N. Virginia)"},
                {"id": "us-east-2", "name": "US East (Ohio)"},
                {"id": "us-west-1", "name": "US West (N. California)"},
                {"id": "us-west-2", "name": "US West (Oregon)"},
                {"id": "ca-central-1", "name": "Canada (Central)"},
                {"id": "ca-west-1", "name": "Canada West (Calgary)"},
                {"id": "sa-east-1", "name": "South America (São Paulo)"},
                {"id": "eu-west-1", "name": "Europe (Ireland)"},
                {"id": "eu-west-2", "name": "Europe (London)"},
                {"id": "eu-west-3", "name": "Europe (Paris)"},
                {"id": "eu-central-1", "name": "Europe (Frankfurt)"},
                {"id": "eu-north-1", "name": "Europe (Stockholm)"},
                {"id": "eu-south-1", "name": "Europe (Milan)"},
                {"id": "eu-central-2", "name": "Europe (Zurich)"},
                {"id": "eu-south-2", "name": "Europe (Spain)"},
                {"id": "ap-northeast-1", "name": "Asia Pacific (Tokyo)"},
                {"id": "ap-northeast-2", "name": "Asia Pacific (Seoul)"},
                {"id": "ap-northeast-3", "name": "Asia Pacific (Osaka)"},
                {"id": "ap-southeast-1", "name": "Asia Pacific (Singapore)"},
                {"id": "ap-southeast-2", "name": "Asia Pacific (Sydney)"},
                {"id": "ap-east-1", "name": "Asia Pacific (Hong Kong)"},
                {"id": "ap-south-1", "name": "Asia Pacific (Mumbai)"},
                {"id": "ap-southeast-3", "name": "Asia Pacific (Jakarta)"},
                {"id": "ap-southeast-4", "name": "Asia Pacific (Melbourne)"},
                {"id": "ap-south-2", "name": "Asia Pacific (Hyderabad)"},
                {"id": "ap-southeast-5", "name": "Asia Pacific (Malaysia)"},
                {"id": "me-south-1", "name": "Middle East (Bahrain)"},
                {"id": "me-central-1", "name": "Middle East (UAE)"},
                {"id": "il-central-1", "name": "Israel (Tel Aviv)"},
                {"id": "af-south-1", "name": "Africa (Cape Town)"},
                {"id": "cn-north-1", "name": "China (Beijing)"},
                {"id": "cn-northwest-1", "name": "China (Ningxia)"},
                {"id": "us-gov-west-1", "name": "AWS GovCloud (US-West)"},
                {"id": "us-gov-east-1", "name": "AWS GovCloud (US-East)"},
            ],
            "azure": [
                {"id": "eastus", "name": "East US"},
                {"id": "eastus2", "name": "East US 2"},
                {"id": "southcentralus", "name": "South Central US"},
                {"id": "westus", "name": "West US"},
                {"id": "westus2", "name": "West US 2"},
                {"id": "westus3", "name": "West US 3"},
                {"id": "centralus", "name": "Central US"},
                {"id": "canadacentral", "name": "Canada Central"},
                {"id": "canadaeast", "name": "Canada East"},
                {"id": "brazilsouth", "name": "Brazil South"},
                {"id": "uksouth", "name": "UK South"},
                {"id": "ukwest", "name": "UK West"},
                {"id": "francecentral", "name": "France Central"},
                {"id": "francesouth", "name": "France South"},
                {"id": "germanywestcentral", "name": "Germany West Central"},
                {"id": "germanynorth", "name": "Germany North"},
                {"id": "switzerlandnorth", "name": "Switzerland North"},
                {"id": "switzerlandwest", "name": "Switzerland West"},
                {"id": "norwayeast", "name": "Norway East"},
                {"id": "norwaywest", "name": "Norway West"},
                {"id": "australiaeast", "name": "Australia East"},
                {"id": "australiasoutheast", "name": "Australia Southeast"},
                {"id": "australiacentral", "name": "Australia Central"},
                {"id": "australiacentral2", "name": "Australia Central 2"},
                {"id": "japaneast", "name": "Japan East"},
                {"id": "japanwest", "name": "Japan West"},
                {"id": "koreacentral", "name": "Korea Central"},
                {"id": "koreasouth", "name": "Korea South"},
                {"id": "southeastasia", "name": "Southeast Asia"},
                {"id": "eastasia", "name": "East Asia"},
                {"id": "centralindia", "name": "Central India"},
                {"id": "southindia", "name": "South India"},
                {"id": "westindia", "name": "West India"},
                {"id": "uaenorth", "name": "UAE North"},
                {"id": "uaecentral", "name": "UAE Central"},
                {"id": "southafricanorth", "name": "South Africa North"},
                {"id": "southafricawest", "name": "South Africa West"},
                {"id": "qatarcentral", "name": "Qatar Central"},
                {"id": "israelcentral", "name": "Israel Central"},
            ],
        }

        # Match based on the unique_id
        if unique_id in provider_regions:
            return provider_regions[unique_id]

        return []

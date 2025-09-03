#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

"""The playground ops services. Contains business logic for playground ops."""

import hashlib
import json
import time
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import status

from ..auth.schemas import RefreshTokenRequest
from ..commons import logging
from ..commons.config import app_settings
from ..commons.constants import EndpointStatusEnum, ProjectStatusEnum, ProjectTypeEnum, UserTypeEnum
from ..commons.db_utils import SessionMixin
from ..commons.exceptions import ClientException
from ..commons.keycloak import KeycloakManager
from ..commons.security import hash_token
from ..credential_ops.crud import CredentialDataManager
from ..credential_ops.models import Credential as CredentialModel
from ..endpoint_ops.crud import EndpointDataManager
from ..endpoint_ops.models import Endpoint as EndpointModel
from ..model_ops.services import ModelService
from ..project_ops.crud import ProjectDataManager
from ..project_ops.models import Project as ProjectModel
from ..project_ops.services import ProjectService
from ..shared.redis_service import RedisService
from ..user_ops.crud import UserDataManager
from ..user_ops.models import Tenant, TenantClient
from ..user_ops.models import User as UserModel
from ..user_ops.schemas import TenantClientSchema
from .crud import ChatSessionDataManager, ChatSettingDataManager, MessageDataManager, NoteDataManager
from .models import ChatSession, ChatSetting, Message, Note
from .schemas import (
    ChatSessionCreate,
    ChatSessionListResponse,
    ChatSettingListResponse,
    EndpointInfo,
    EndpointListResponse,
    MessageResponse,
    NoteResponse,
    PlaygroundInitializeResponse,
)


logger = logging.get_logger(__name__)


class PlaygroundService(SessionMixin):
    """Playground service."""

    async def get_all_playground_deployments(
        self,
        current_user_id: Optional[UUID] = None,
        api_key: Optional[str] = None,
        offset: int = 0,
        limit: int = 10,
        filters: Optional[Dict] = None,
        order_by: Optional[List] = None,
        search: bool = False,
    ) -> Tuple[List[EndpointModel], int]:
        """Get all playground deployments."""
        filters = filters or {}
        order_by = order_by or []

        project_ids, filter_published_only = await self._get_authorized_project_ids(current_user_id, api_key)
        logger.debug("authorized project_ids: %s, filter_published_only: %s", project_ids, filter_published_only)

        # Add published filter if needed for CLIENT users
        if filter_published_only:
            filters["is_published"] = True

        db_endpoints, count = await EndpointDataManager(self.session).get_all_playground_deployments(
            project_ids,
            offset,
            limit,
            filters,
            order_by,
            search,
        )
        db_deployments_list = []
        model_uris = []
        for db_endpoint in db_endpoints:
            deployment, input_cost, output_cost, context_length = db_endpoint
            model_uris.append(deployment.model.uri)
            db_deployment = EndpointListResponse(
                id=deployment.id,
                name=deployment.name,
                status=deployment.status,
                model=deployment.model,
                project=deployment.project,
                created_at=deployment.created_at,
                modified_at=deployment.modified_at,
                input_cost=input_cost,
                output_cost=output_cost,
                context_length=context_length,
                leaderboard=None,
            )
            db_deployments_list.append(db_deployment)
        db_leaderboards = await ModelService(self.session).get_leaderboard_by_model_uris(model_uris)
        for db_deployment in db_deployments_list:
            db_deployment.leaderboard = db_leaderboards.get(db_deployment.model.uri, None)

        return db_deployments_list, count

    async def _get_authorized_project_ids(
        self, current_user_id: Optional[UUID] = None, api_key: Optional[str] = None
    ) -> Tuple[Optional[List[UUID]], bool]:
        """Get all authorized project ids and whether to filter published only.

        Returns:
            Tuple[Optional[List[UUID]], bool]: List of project IDs (None for all projects) and whether to filter for published models only.
                - When filter_published_only is True and project_ids is None, show ALL published models across all projects
                - When filter_published_only is False, project_ids contains specific projects to filter
        """
        if current_user_id:
            # Get the user to check their type
            user = await UserDataManager(self.session).retrieve_by_fields(UserModel, fields={"id": current_user_id})

            # For CLIENT users, only show published models
            filter_published_only = user.user_type == UserTypeEnum.CLIENT

            if filter_published_only:
                # For CLIENT users, show ALL published models (not restricted by project)
                logger.debug(f"Getting all published deployments for CLIENT user {current_user_id}")
                project_ids = None  # None means no project filtering - show all published
            else:
                # For ADMIN users, get all active project ids
                logger.debug(f"Getting all playground deployments for ADMIN user {current_user_id}")
                project_ids = await ProjectDataManager(self.session).get_all_active_project_ids()

            return project_ids, filter_published_only
        elif api_key:
            # if api_key is present identify the project id and type
            # Hash the API key to compare with stored hashed keys
            hashed_api_key = hash_token(f"bud-{api_key}")
            db_credential = await CredentialDataManager(self.session).retrieve_by_fields(
                CredentialModel, fields={"hashed_key": hashed_api_key}, missing_ok=True
            )
            if not db_credential:
                logger.error("Invalid API key found")
                raise ClientException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message="Invalid API key",
                )
            else:
                # Get the project to check its type
                project = await ProjectDataManager(self.session).retrieve_by_fields(
                    ProjectModel, fields={"id": db_credential.project_id}
                )

                # Check if the API key belongs to a CLIENT project
                # CLIENT projects should only see published models
                filter_published_only = project.project_type == ProjectTypeEnum.CLIENT_APP

                if filter_published_only:
                    # CLIENT API keys see ALL published models (not restricted to their project)
                    logger.debug(f"CLIENT API key for project {project.id}, showing all published models")
                    project_ids = None  # None means no project filtering - show all published
                else:
                    # Non-CLIENT API keys see all models from their specific project
                    logger.debug(
                        f"Non-CLIENT API key for project {project.id} (type: {project.project_type}), "
                        f"showing all models from this project"
                    )
                    project_ids = [project.id]

                return project_ids, filter_published_only
        else:
            raise ClientException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                message="Unauthorized to access this resource",
            )

    async def hash_jwt_token(self, jwt: str) -> str:
        """Hash JWT token using same pattern as API keys.

        This ensures compatibility with existing gateway validation logic.
        Uses the same hashing pattern as CredentialModel.set_hashed_key()

        Args:
            jwt: The JWT token to hash

        Returns:
            str: The hashed JWT token
        """
        # Use same pattern as CredentialModel.set_hashed_key()
        return hash_token(f"bud-{jwt}")

    async def initialize_session_with_refresh_token(self, refresh_token: str) -> PlaygroundInitializeResponse:
        """Initialize playground session with refresh token authentication.

        This method:
        1. Verifies the refresh token and generates new access/refresh tokens
        2. Hashes the new access token for Redis storage
        3. Fetches user's available endpoints/deployments for Redis cache
        4. Stores data in Redis with appropriate TTL (same structure as API keys)
        5. Returns initialization response with new token details

        Args:
            refresh_token: The refresh token to verify and exchange for new tokens

        Returns:
            PlaygroundInitializeResponse with session info and new tokens
        """
        try:
            # Step 1: Use refresh token to get new access and refresh tokens
            # Get default tenant with realm_name
            tenant = await UserDataManager(self.session).retrieve_by_fields(
                Tenant, {"realm_name": app_settings.default_realm_name}, missing_ok=True
            )
            if not tenant:
                raise ClientException("Default tenant not found")

            # Get tenant client credentials
            tenant_client = await UserDataManager(self.session).retrieve_by_fields(
                TenantClient, {"tenant_id": tenant.id}, missing_ok=True
            )
            if not tenant_client:
                raise ClientException("Tenant client configuration not found")

            # Initialize Keycloak manager and refresh tokens
            keycloak_manager = KeycloakManager()

            # Decrypt client secret for use
            decrypted_secret = await tenant_client.get_decrypted_client_secret()
            credentials = TenantClientSchema(
                id=tenant_client.id,
                client_id=tenant_client.client_id,
                client_named_id=tenant_client.client_named_id,
                client_secret=decrypted_secret,
            )

            # Refresh Token to get new access/refresh token pair
            token_data = await keycloak_manager.refresh_token(
                realm_name=tenant.realm_name,
                credentials=credentials,
                refresh_token=refresh_token,
            )

            if not token_data or not token_data.get("access_token"):
                raise ClientException(status_code=status.HTTP_401_UNAUTHORIZED, message="Invalid refresh token")

            # Step 2: Extract auth_id (Keycloak user ID) from the new access token
            import jwt

            try:
                # Decode without verification to get user info (already verified by Keycloak)
                decoded = jwt.decode(token_data["access_token"], options={"verify_signature": False})
                auth_id = decoded.get("sub")
                if not auth_id:
                    raise ClientException(
                        status_code=status.HTTP_401_UNAUTHORIZED, message="No subject found in access token"
                    )
            except jwt.DecodeError as e:
                logger.error(f"Failed to decode access token: {e}")
                raise ClientException(status_code=status.HTTP_401_UNAUTHORIZED, message="Invalid access token format")

            # Step 3: Get user details using auth_id (Keycloak user ID)
            db_user = await UserDataManager(self.session).retrieve_by_fields(
                UserModel, {"auth_id": auth_id}, missing_ok=True
            )

            if not db_user:
                logger.error(f"User not found for auth_id: {auth_id}")
                raise ClientException(status_code=status.HTTP_404_NOT_FOUND, message="User not found")

            # Step 4: Get user's accessible projects
            project_service = ProjectService(self.session)

            # CLIENT users see published models, ADMIN users see all
            filter_published_only = db_user.user_type == UserTypeEnum.CLIENT

            # Get project IDs based on user type
            if filter_published_only:
                # CLIENT users: Get their first active project for metadata
                user_projects, _ = await project_service.get_all_active_projects(
                    current_user=db_user,
                    offset=0,
                    limit=1,  # Just need one for metadata
                )

                if not user_projects:
                    raise ClientException(
                        status_code=status.HTTP_404_NOT_FOUND, message="No active projects found for user"
                    )

                project = user_projects[0]
                project_ids = None  # CLIENT users see all published endpoints
            else:
                # ADMIN users: Get ALL their active projects
                all_projects, total_count = await project_service.get_all_active_projects(
                    current_user=db_user,
                    offset=0,
                    limit=1000,  # Get all projects (reasonable upper limit)
                )

                if not all_projects:
                    raise ClientException(
                        status_code=status.HTTP_404_NOT_FOUND, message="No active projects found for user"
                    )

                project = all_projects[0]  # Use first project for metadata
                # Extract all project IDs for ADMIN users
                project_ids = [p.project.id for p in all_projects]

            # Step 5: Hash the new access token for Redis storage
            hashed_access_token = await self.hash_jwt_token(token_data["access_token"])

            # Step 6: Prepare filters for endpoint retrieval
            endpoint_filters = {"status": EndpointStatusEnum.RUNNING}
            if filter_published_only:
                endpoint_filters["is_published"] = True

            # Get endpoints - CLIENT users get all published, ADMIN users get from all their projects
            db_endpoints, _ = await EndpointDataManager(self.session).get_all_playground_deployments(
                project_ids=project_ids,  # None for CLIENT (all published), list of IDs for ADMIN
                offset=0,
                limit=1000,  # Increased limit to get more endpoints
                filters=endpoint_filters,
                order_by=[],
                search=False,
            )

            # Step 7: Prepare cache data (same structure as API keys)
            cache_data = {}

            for db_endpoint_tuple in db_endpoints:
                endpoint, input_cost, output_cost, context_length = db_endpoint_tuple

                # Prepare cache data (same structure as API keys)
                cache_data[endpoint.name] = {
                    "endpoint_id": str(endpoint.id),
                    "model_id": str(endpoint.model.id),
                    "project_id": str(endpoint.project_id),
                }

            # Add metadata to cache
            cache_data["__metadata__"] = {
                "api_key_id": None,  # Not applicable for JWT
                "user_id": str(db_user.id),
                "api_key_project_id": str(project.project.id),
            }

            # Step 8: Calculate TTL based on access token expiry
            ttl = None
            expires_in = token_data.get("expires_in")
            if expires_in:
                ttl = expires_in  # Use expires_in from token response
            else:
                # Fallback: try to get expiry from token
                try:
                    access_token_expiry = decoded.get("exp")
                    if access_token_expiry:
                        current_time = int(time.time())
                        ttl = max(access_token_expiry - current_time, 0)
                except Exception:
                    ttl = 3600  # Default 1 hour if unable to determine expiry

            # Step 9: Store in Redis with same key format as API keys
            redis_service = RedisService()
            redis_key = f"api_key:{hashed_access_token}"

            await redis_service.set(
                redis_key,
                json.dumps(cache_data),
                ex=ttl,  # Set expiry if TTL is provided
            )

            logger.info(
                f"Initialized playground session for user {db_user.id} with {len(db_endpoints)} endpoints cached"
            )

            # Step 10: Return response with new tokens
            return PlaygroundInitializeResponse(
                user_id=db_user.id,
                initialization_status="success",
                ttl=ttl,
                message="Playground session initialized successfully with new tokens",
                access_token=token_data["access_token"],
                refresh_token=token_data.get(
                    "refresh_token", refresh_token
                ),  # Use new refresh token or fallback to original
                token_type=token_data.get("token_type", "Bearer"),
                expires_in=expires_in,
            )

        except ClientException:
            # Re-raise client exceptions as-is
            raise
        except Exception as e:
            logger.error(f"Failed to initialize playground session with refresh token: {e}")
            raise ClientException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"Failed to initialize playground session: {str(e)}",
            )


class ChatSessionService(SessionMixin):
    """Chat Session Service."""

    async def create_chat_session(self, user_id: UUID, chat_session_data: dict) -> ChatSession:
        """Create a new chat session and insert it into the database."""
        chat_session_data["user_id"] = user_id

        chat_session = ChatSession(**chat_session_data)

        db_chat_session = await ChatSessionDataManager(self.session).insert_one(chat_session)

        return db_chat_session

    async def list_chat_sessions(
        self,
        user_id: UUID,
        offset: int = 0,
        limit: int = 10,
        filters: Dict = {},
        order_by: List = [],
        search: bool = False,
    ) -> Tuple[List[ChatSessionListResponse], int]:
        """List all chat sessions for a given user."""
        db_results, count = await ChatSessionDataManager(self.session).get_all_chat_sessions(
            user_id, offset, limit, filters, order_by, search
        )
        chat_sessions = []
        for db_result in db_results:
            db_chat_session = db_result[0]
            chat_session = ChatSessionListResponse(
                id=db_chat_session.id,
                name=db_chat_session.name,
                total_tokens=db_result[1],
                created_at=db_chat_session.created_at,
                modified_at=db_chat_session.modified_at,
            )
            chat_sessions.append(chat_session)
        return chat_sessions, count

    async def get_chat_session_details(self, chat_session_id: UUID) -> ChatSession:
        """Retrieve details of a session by its ID."""
        db_chat_session = await ChatSessionDataManager(self.session).retrieve_by_fields(
            ChatSession,
            fields={"id": chat_session_id},
        )

        return db_chat_session

    async def delete_chat_session(self, chat_session_id: UUID) -> None:
        """Delete chat session."""
        db_chat_session = await ChatSessionDataManager(self.session).retrieve_by_fields(
            ChatSession,
            fields={"id": chat_session_id},
        )

        await ChatSessionDataManager(self.session).delete_one(db_chat_session)

        return

    async def edit_chat_session(self, chat_session_id: UUID, data: Dict[str, Any]) -> ChatSession:
        """Edit chat session by validating and updating specific fields."""
        # Retrieve existing chat session
        db_chat_session = await ChatSessionDataManager(self.session).retrieve_by_fields(
            ChatSession,
            fields={"id": chat_session_id},
        )

        db_chat_session = await ChatSessionDataManager(self.session).update_by_fields(db_chat_session, data)

        return db_chat_session


class MessageService(SessionMixin):
    """Message Service."""

    async def create_message(self, user_id: UUID, message_data: dict) -> Message:
        """Create a new message and insert it into the database."""
        # validate deployment id
        await EndpointDataManager(self.session).retrieve_by_fields(
            EndpointModel,
            fields={"id": message_data["deployment_id"]},
            exclude_fields={"status": EndpointStatusEnum.DELETED},
        )

        chat_setting_id = message_data.pop("chat_setting_id", None)
        if chat_setting_id:
            await ChatSettingDataManager(self.session).retrieve_by_fields(ChatSetting, fields={"id": chat_setting_id})

        # If chat_session_id is not provided, create a new chat session first
        if not message_data.get("chat_session_id"):
            prompt = message_data.get("prompt")
            chat_session_name = prompt[:20].strip()

            chat_session_data = ChatSessionCreate(name=chat_session_name, chat_setting_id=chat_setting_id).model_dump(
                exclude_unset=True, exclude_none=True
            )
            chat_session_data["user_id"] = user_id
            chat_session = ChatSession(**chat_session_data)
            db_chat_session = await ChatSessionDataManager(self.session).insert_one(chat_session)
            message_data["chat_session_id"] = db_chat_session.id  # Assign the new session ID
            message_data["parent_message_id"] = None
        else:
            # validate chat session id
            db_chat_session = await ChatSessionDataManager(self.session).retrieve_by_fields(
                ChatSession, fields={"id": message_data["chat_session_id"]}
            )
            # Fetch the last message in the session to determine parent_id
            last_db_message = await MessageDataManager(self.session).get_last_message(message_data["chat_session_id"])
            message_data["parent_message_id"] = last_db_message.id if last_db_message else None

        # Create a new message
        message = Message(**message_data)
        db_message = await MessageDataManager(self.session).insert_one(message)

        return db_message

    async def get_messages_by_chat_session(
        self,
        chat_session_id: UUID,
        filters: Dict,
        offset: int = 0,
        limit: int = 10,
        order_by: List = [],
        search: bool = False,
    ) -> Tuple[List[MessageResponse], int]:
        """Retrieve messages based on provided filters."""
        await ChatSessionDataManager(self.session).retrieve_by_fields(ChatSession, fields={"id": chat_session_id})

        db_messages, count = await MessageDataManager(self.session).get_messages(
            chat_session_id, filters, offset, limit, order_by, search
        )

        return db_messages, count

    async def edit_message(self, message_id: UUID, data: Dict[str, Any]) -> Message:
        """Edit a message by validating and updating specific fields."""
        # Retrieve existing message
        db_message = await MessageDataManager(self.session).retrieve_by_fields(
            Message,
            fields={"id": message_id},
        )
        if data.get("prompt"):
            # Retrieve the child message if it exists
            child_message = await MessageDataManager(self.session).retrieve_by_fields(
                Message, fields={"parent_message_id": message_id}, missing_ok=True
            )

            # Delete the child message if it exists
            if child_message:
                await MessageDataManager(self.session).delete_one(child_message)

        # Update the message with new data
        db_message = await MessageDataManager(self.session).update_by_fields(db_message, data)

        return db_message

    async def delete_message(self, message_id: UUID) -> None:
        """Delete a message and its child messages."""
        # Retrieve the message by ID
        db_message = await MessageDataManager(self.session).retrieve_by_fields(
            Message,
            fields={"id": message_id},
        )

        # Delete the message
        await MessageDataManager(self.session).delete_one(db_message)

        return


class ChatSettingService(SessionMixin):
    """Chat Setting Service."""

    async def create_chat_setting(self, user_id: UUID, chat_setting_data: dict) -> ChatSetting:
        """Create a new chat setting and insert it into the database."""
        chat_setting_data["user_id"] = user_id

        chat_setting = ChatSetting(**chat_setting_data)

        db_chat_setting = await ChatSettingDataManager(self.session).insert_one(chat_setting)

        return db_chat_setting

    async def list_chat_settings(
        self,
        user_id: UUID,
        offset: int = 0,
        limit: int = 10,
        filters: Dict = {},
        order_by: List = [],
        search: bool = False,
    ) -> Tuple[List[ChatSettingListResponse], int]:
        """List all chat settings for a given user."""
        db_chat_settings, count = await ChatSettingDataManager(self.session).get_all_chat_settings(
            user_id, offset, limit, filters, order_by, search
        )

        return db_chat_settings, count

    async def get_chat_setting_details(self, chat_setting_id: UUID) -> ChatSetting:
        """Retrieve details of a chat setting by its ID."""
        db_chat_setting = await ChatSettingDataManager(self.session).retrieve_by_fields(
            ChatSetting,
            fields={"id": chat_setting_id},
        )

        return db_chat_setting

    async def edit_chat_setting(self, chat_setting_id: UUID, data: Dict[str, Any]) -> ChatSetting:
        """Edit chat setting by validating and updating specific fields."""
        # Retrieve existing chat setting
        db_chat_setting = await ChatSettingDataManager(self.session).retrieve_by_fields(
            ChatSetting,
            fields={"id": chat_setting_id},
        )

        db_chat_setting = await ChatSettingDataManager(self.session).update_by_fields(db_chat_setting, data)

        return db_chat_setting

    async def delete_chat_setting(self, chat_setting_id: UUID) -> None:
        """Delete chat setting."""
        db_chat_setting = await ChatSettingDataManager(self.session).retrieve_by_fields(
            ChatSetting,
            fields={"id": chat_setting_id},
        )

        await ChatSettingDataManager(self.session).delete_one(db_chat_setting)

        return


class NoteService(SessionMixin):
    """Note Service."""

    async def create_note(self, user_id: UUID, note_data: dict) -> Note:
        """Create a new note and insert it into the database."""
        # validate chat session id
        await ChatSessionDataManager(self.session).retrieve_by_fields(
            ChatSession, fields={"id": note_data["chat_session_id"]}
        )

        note_data["user_id"] = user_id

        note = Note(**note_data)

        db_note = await NoteDataManager(self.session).insert_one(note)

        return db_note

    async def get_all_notes(
        self,
        chat_session_id: UUID,
        user_id: UUID,
        offset: int = 0,
        limit: int = 10,
        filters: Dict = {},
        order_by: List = [],
        search: bool = False,
    ) -> Tuple[List[NoteResponse], int]:
        """Retrieve all notes for a given chat session and user."""
        # validate chat session id
        await ChatSessionDataManager(self.session).retrieve_by_fields(ChatSession, fields={"id": chat_session_id})

        db_notes, total_count = await NoteDataManager(self.session).get_all_notes(
            chat_session_id, user_id, offset, limit, filters, order_by, search
        )

        return db_notes, total_count

    async def edit_note(self, note_id: UUID, data: Dict[str, Any]) -> Note:
        """Edit note by validating and updating specific fields."""
        # Retrieve existing note
        db_note = await NoteDataManager(self.session).retrieve_by_fields(
            Note,
            fields={"id": note_id},
        )

        db_note = await NoteDataManager(self.session).update_by_fields(db_note, data)

        return db_note

    async def delete_note(self, note_id: UUID) -> None:
        """Delete note."""
        db_note = await NoteDataManager(self.session).retrieve_by_fields(
            Note,
            fields={"id": note_id},
        )

        await NoteDataManager(self.session).delete_one(db_note)

        return

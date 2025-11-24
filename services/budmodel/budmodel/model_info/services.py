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


"""Implements core services and business logic that power the microservices, including key functionality and integrations."""

import asyncio
import json
import math
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from budmicroframe.commons import logging
from budmicroframe.commons.constants import WorkflowStatus
from budmicroframe.commons.schemas import (
    NotificationContent,
    NotificationRequest,
)
from budmicroframe.shared.dapr_service import DaprService
from budmicroframe.shared.dapr_workflow import DaprWorkflow
from minio.error import S3Error

from ..commons.async_utils import validate_url_exists
from ..commons.config import app_settings
from ..commons.constants import LICENSE_MINIO_OBJECT_NAME, ModelExtractionStatus
from ..commons.constants import ModelDownloadStatus as DownloadStatus
from ..commons.exceptions import (
    CompressionException,
    InvalidUriException,
    LicenseExtractionException,
    ModelDownloadException,
    ModelExtractionException,
)
from ..commons.helpers import (
    estimate_download_speed,
    generate_unique_name,
    get_remote_file_size,
    get_size_in_bytes,
    is_zip_file,
    is_zip_url,
    list_directory_files,
    measure_transfer_speed,
    safe_delete,
    sanitize_name,
)
from ..leaderboard.crud import LeaderboardCRUD
from ..leaderboard.services import LeaderboardService
from .download_history import DownloadHistory
from .exceptions import (
    HubDownloadException,
    ModelScanException,
    RepoAccessException,
    SaveRegistryException,
    SpaceNotAvailableException,
    UnsupportedModelException,
)
from .huggingface import HuggingFaceModelInfo, HuggingfaceUtils
from .huggingface_budconnect import HuggingFaceWithBudConnect
from .license import LicenseExtractor
from .local_model import LocalModelDownloadService, LocalModelExtraction
from .models import ModelInfoCRUD
from .schemas import (
    LicenseFAQRequest,
    LicenseFAQResponse,
    ModelExtractionETAObserverRequest,
    ModelExtractionRequest,
    ModelExtractionResponse,
    ModelInfo,
    ModelSecurityScanRequest,
    ModelSecurityScanResponse,
)
from .store import ModelStore, measure_minio_download_speed, measure_minio_upload_speed


logger = logging.get_logger(__name__)

dapr_workflow = DaprWorkflow()


class ModelExtractionService:
    """Service class for model extraction."""

    @staticmethod
    def validate_model_uri(
        workflow_id: str,
        notification_request: NotificationRequest,
        model_uri: str,
        provider_type: str,
        hf_token: Optional[str] = None,
        target_topic_name: Optional[str] = None,
        target_name: Optional[str] = None,
    ) -> bool:
        """Validate the model URI. Returns True if valid, raises exception if not."""
        notification_req = notification_request.model_copy(deep=True)
        notification_req.payload.event = "validation"

        notification_req.payload.content = NotificationContent(
            title="Validating model uri",
            message="Validating given model uri",
            status=WorkflowStatus.STARTED,
        )
        dapr_workflow.publish_notification(
            workflow_id=workflow_id,
            notification=notification_req,
            target_topic_name=target_topic_name,
            target_name=target_name,
        )

        # Update current step in state store
        try:
            state_store_key = f"eta_{workflow_id}"
            dapr_service = DaprService()
            state_store_data = dapr_service.get_state(
                store_name=app_settings.statestore_name,
                key=state_store_key,
            ).json()
            state_store_data["current_step"] = "validation"
            dapr_service.save_to_statestore(
                store_name=app_settings.statestore_name,
                key=state_store_key,
                value=state_store_data,
                ttl=86400,
            )
        except Exception as e:
            logger.exception("Error updating workflow eta in state store: %s", e)

        try:
            logger.info("Validating the model uri: %s", model_uri)
            logger.debug("Requested provider type: %s", provider_type)
            if provider_type == "hugging_face":
                # Check if hugging face uri is valid
                masked_hf_token = "*" * 10 if hf_token else "None"
                logger.debug("Check hugging face model uri is valid. Requested HF token: %s", masked_hf_token)
                HuggingfaceUtils.has_access_to_repo(model_uri, hf_token)
            elif provider_type == "url":
                # Check if url is valid
                logger.debug("Check model url is valid: %s", model_uri)
                is_valid_url = validate_url_exists(model_uri)
                if not is_valid_url:
                    raise InvalidUriException("Invalid model url provided.")
            elif provider_type == "disk":
                # Check if disk path is valid in add_model_dir
                add_model_uri = os.path.join(app_settings.add_model_dir, model_uri)
                logger.debug("Check model path is valid: %s", add_model_uri)
                if not os.path.exists(add_model_uri):
                    raise InvalidUriException("Invalid disk path provided.")

            logger.debug(f"Access to '{model_uri}' granted.")
            # Added sleep to avoid workflow registration failure
            time.sleep(3)

            notification_req.payload.content = NotificationContent(
                title="Validated model uri",
                message="Validated given model uri",
                status=WorkflowStatus.COMPLETED,
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )
            return True  # Return True for successful validation
        except InvalidUriException as e:
            logger.exception("Error validating model uri: %s", str(e))
            notification_req.payload.content = NotificationContent(
                title=str(e),
                message="Fix: Provide valid model uri",
                status=WorkflowStatus.FAILED,
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )
            raise e
        except RepoAccessException as e:
            logger.exception("Error validating model uri: %s", str(e))
            notification_req.payload.content = NotificationContent(
                title=str(e),
                message="Fix: Provide valid model uri and check model permissions",
                status=WorkflowStatus.FAILED,
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )
            raise e  # Let the exception propagate for now
        except Exception as e:
            logger.exception("Error validating model uri: %s", str(e))
            error_message = str(e)
            notification_req.payload.content = NotificationContent(
                title="Failed to validate model uri",
                message=f"{error_message}. Fix: Check the model uri and permissions"
                if error_message
                else "Fix: Check the model uri and permissions",
                status=WorkflowStatus.FAILED,
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )
            raise e

    @staticmethod
    def download_model(
        workflow_id: str,
        model_name: str,
        model_uri: str,
        provider_type: str,
        notification_request: NotificationRequest,
        hf_token: Optional[str] = None,
        target_topic_name: Optional[str] = None,
        target_name: Optional[str] = None,
    ) -> str:
        """Download the model."""
        notification_req = notification_request.model_copy(deep=True)
        try:
            logger.info("Downloading to path downloads/%s", model_name)
            # Start model download
            notification_req.payload.event = "model_download"
            notification_req.payload.content = NotificationContent(
                title="Downloading the model",
                message="Downloading the model from the given URI",
                status=WorkflowStatus.STARTED,
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )

            logger.info("Downloading the model from the given URI: %s (workflow: %s)", model_uri, workflow_id)

            # Check if a download for this model is already in progress
            # This prevents duplicate downloads when workflows are retried or replayed
            existing_download = DownloadHistory.check_existing_download(model_uri)
            if existing_download:
                logger.info(
                    "Found existing download record for model %s, directory: %s, status: %s",
                    model_uri,
                    existing_download.directory_name,
                    existing_download.status,
                )

                # Return the existing directory name if download is in progress
                if existing_download.status == DownloadStatus.RUNNING:
                    # Check if the download is still active (files being written)
                    is_active = DownloadHistory.is_download_active(existing_download.directory_name)

                    if is_active:
                        logger.info(
                            "Download is still actively running for %s, waiting for completion: %s",
                            model_uri,
                            existing_download.directory_name,
                        )
                        notification_req.payload.content = NotificationContent(
                            title="Waiting for existing download to complete",
                            message=f"Model {model_name} download already in progress, waiting for completion",
                            status=WorkflowStatus.STARTED,
                        )
                        dapr_workflow.publish_notification(
                            workflow_id=workflow_id,
                            notification=notification_req,
                            target_topic_name=target_topic_name,
                            target_name=target_name,
                        )

                        # Wait for the download to complete by checking status periodically
                        import time

                        max_wait_time = 7200  # 2 hours max wait
                        check_interval = 10  # Check every 10 seconds
                        elapsed_time = 0

                        while elapsed_time < max_wait_time:
                            time.sleep(check_interval)
                            elapsed_time += check_interval

                            # Re-check the download status
                            current_download = DownloadHistory.get_download_by_directory(
                                existing_download.directory_name
                            )

                            if current_download and current_download.status == DownloadStatus.COMPLETED:
                                logger.info(
                                    "Download completed for %s after waiting %d seconds: %s",
                                    model_uri,
                                    elapsed_time,
                                    existing_download.directory_name,
                                )
                                notification_req.payload.content = NotificationContent(
                                    title="Download completed",
                                    message=f"Model {model_name} download completed after waiting",
                                    status=WorkflowStatus.COMPLETED,
                                )
                                dapr_workflow.publish_notification(
                                    workflow_id=workflow_id,
                                    notification=notification_req,
                                    target_topic_name=target_topic_name,
                                    target_name=target_name,
                                )
                                return existing_download.directory_name

                            elif current_download and current_download.status == DownloadStatus.FAILED:
                                logger.error(
                                    "Download failed for %s after waiting %d seconds", model_uri, elapsed_time
                                )
                                # Continue with new download below
                                break

                            # Check if download is still active
                            if not DownloadHistory.is_download_active(existing_download.directory_name):
                                logger.warning(
                                    "Download appears stale for %s after waiting %d seconds", model_uri, elapsed_time
                                )
                                DownloadHistory.mark_download_failed(existing_download.directory_name)
                                # Continue with new download below
                                break

                            # Log progress every minute
                            if elapsed_time % 60 == 0:
                                logger.info(
                                    "Still waiting for download to complete for %s (waited %d seconds)",
                                    model_uri,
                                    elapsed_time,
                                )

                        if elapsed_time >= max_wait_time:
                            logger.error(
                                "Download wait timeout exceeded for %s after %d seconds", model_uri, max_wait_time
                            )
                            DownloadHistory.mark_download_failed(existing_download.directory_name)
                            # Continue with new download below
                    else:
                        # Download appears stale, mark as failed and proceed with new download
                        logger.warning(
                            "Existing download for %s appears stale (no recent activity), marking as failed", model_uri
                        )
                        DownloadHistory.mark_download_failed(existing_download.directory_name)
                        # Continue with new download below

                # If completed, verify files exist before using
                elif existing_download.status == DownloadStatus.COMPLETED:
                    logger.info("Model marked as downloaded, verifying files: %s", existing_download.directory_name)

                    # Verify that the download is actually complete with files present
                    download_path = os.path.join(app_settings.model_download_dir, existing_download.directory_name)

                    if not os.path.exists(download_path):
                        logger.warning("Download directory does not exist despite COMPLETED status: %s", download_path)
                        # Mark as failed and continue with new download
                        DownloadHistory.mark_download_failed(existing_download.directory_name)
                        # Continue with new download below
                    else:
                        # Check if directory has files
                        files_in_dir = []
                        for root, _dirs, files in os.walk(download_path):
                            # Skip .cache directories
                            if ".cache" in root:
                                continue
                            files_in_dir.extend(files)

                        # Check for minimum expected files
                        has_config = any(f == "config.json" for f in files_in_dir)
                        has_weights = any(f.endswith((".safetensors", ".bin", ".pt", ".pth")) for f in files_in_dir)

                        if not files_in_dir or not has_config or not has_weights:
                            logger.warning(
                                "Download marked COMPLETED but files are missing (files: %d, config: %s, weights: %s): %s",
                                len(files_in_dir),
                                has_config,
                                has_weights,
                                download_path,
                            )
                            # Mark as failed and continue with new download
                            DownloadHistory.mark_download_failed(existing_download.directory_name)
                            # Continue with new download below
                        else:
                            logger.info(
                                "Verified %d files in completed download, using existing: %s",
                                len(files_in_dir),
                                existing_download.directory_name,
                            )
                            notification_req.payload.content = NotificationContent(
                                title="Using existing download",
                                message=f"Model {model_name} was already downloaded ({len(files_in_dir)} files verified)",
                                status=WorkflowStatus.COMPLETED,
                            )
                            dapr_workflow.publish_notification(
                                workflow_id=workflow_id,
                                notification=notification_req,
                                target_topic_name=target_topic_name,
                                target_name=target_name,
                            )
                            return existing_download.directory_name

            # First, try to get existing directory from state store (for workflow replay scenarios)
            dir_name = None
            dapr_service = None
            try:
                state_store_key = f"eta_{workflow_id}"
                dapr_service = DaprService()
                state_data = dapr_service.get_state(
                    store_name=app_settings.statestore_name,
                    key=state_store_key,
                ).json()

                if (
                    state_data
                    and "steps_data" in state_data
                    and "model_download" in state_data["steps_data"]
                    and "directory_name" in state_data["steps_data"]["model_download"]
                ):
                    dir_name = state_data["steps_data"]["model_download"]["directory_name"]
                    logger.info(f"Reusing directory from state store for workflow {workflow_id}: {dir_name}")
            except Exception:
                logger.debug(f"No existing state found for workflow {workflow_id}, will generate new directory name")

            # Only generate new name if not found in state store
            if not dir_name:
                sanitized_model_name = sanitize_name(model_name)
                dir_name = generate_unique_name(sanitized_model_name)
                logger.info(f"Generated new directory name for workflow {workflow_id}: {dir_name}")

            # Update current step in state store
            try:
                state_store_key = f"eta_{workflow_id}"
                if not dapr_service:
                    dapr_service = DaprService()

                # Get current state or create new
                try:
                    state_store_data = dapr_service.get_state(
                        store_name=app_settings.statestore_name,
                        key=state_store_key,
                    ).json()
                except Exception:
                    state_store_data = {"steps_data": {"model_download": {}}}

                state_store_data["current_step"] = "model_download"
                if "steps_data" not in state_store_data:
                    state_store_data["steps_data"] = {}
                if "model_download" not in state_store_data["steps_data"]:
                    state_store_data["steps_data"]["model_download"] = {}

                state_store_data["steps_data"]["model_download"]["start_time"] = datetime.now(timezone.utc).isoformat()
                state_store_data["steps_data"]["model_download"]["directory_name"] = dir_name

                dapr_service.save_to_statestore(
                    store_name=app_settings.statestore_name,
                    key=state_store_key,
                    value=state_store_data,
                    ttl=86400,
                )
                logger.debug(f"Saved directory name {dir_name} to state store for workflow {workflow_id}")
            except Exception as e:
                logger.exception("Error updating workflow eta in state store: %s", e)

            if provider_type == "hugging_face":
                model_info = HuggingFaceModelInfo()
                # TODO: remove this after testing (hf snapshot implementation)
                # downloaded_path = model_info.download_from_hf_hub(
                #     model_name_or_path=model_uri, rel_dir=dir_name, hf_token=hf_token
                # )
                downloaded_path = model_info.download_repository_files(model_uri, dir_name, hf_token, workflow_id)
            elif provider_type == "url":
                download_service = LocalModelDownloadService()
                downloaded_path = download_service.download_model_from_url(model_uri, dir_name, workflow_id)
            elif provider_type == "disk":
                download_service = LocalModelDownloadService()
                downloaded_path = download_service.transfer_model_from_disk(model_uri, dir_name, workflow_id)
            else:
                logger.error("Invalid provider type.")
                raise ValueError("Invalid provider type")

            # Complete model download
            notification_req.payload.content = NotificationContent(
                title="Downloaded the model",
                message="Downloaded the model from the given URI",
                status=WorkflowStatus.COMPLETED,
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )

            logger.info("Downloaded model to: %s", downloaded_path)
            return dir_name
        except SpaceNotAvailableException as e:
            logger.exception("Error downloading the model: %s", str(e))
            notification_req.payload.event = "model_download"
            # Include the actual space requirements in the notification
            error_details = str(e)
            notification_req.payload.content = NotificationContent(
                title=f"Insufficient disk space for {model_name}",
                message=error_details if error_details else "Fix: Free up space or choose a smaller model",
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )
            raise e  # Let the exception propagate for now
        except CompressionException as e:
            logger.exception("Error extracting zip file: %s", str(e))
            notification_req.payload.event = "model_download"
            notification_req.payload.content = NotificationContent(
                title=f"Unable to extract zip file for {model_name} model",
                message="Fix: Provide a valid zip file or retry the download",
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )
            raise e
        except (Exception, HubDownloadException, ModelDownloadException) as e:
            logger.exception("Error downloading the model: %s", str(e))
            notification_req.payload.event = "model_download"

            # Extract the actual error message to include in the notification
            error_message = str(e)
            if "Space not available" in error_message:
                # For space errors, use the detailed message
                title = f"Insufficient disk space for {model_name}"
                message = error_message
            else:
                # For other errors, include the error details in the message
                title = "Failed to download the model"
                message = (
                    f"{error_message}. Fix: Retry the model download"
                    if error_message
                    else "Fix: Retry the model download"
                )

            notification_req.payload.content = NotificationContent(
                title=title,
                message=message,
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )
            raise e

    @staticmethod
    def save_model_to_registry(
        workflow_id: str,
        model_path: str,
        notification_request: NotificationRequest,
        target_topic_name: Optional[str] = None,
        target_name: Optional[str] = None,
    ) -> str:
        """Save the model to the registry."""
        notification_req = notification_request.model_copy(deep=True)
        try:
            # TODO: Notify the ETA based on the size of the model or upload speed etc.
            logger.info("Uploading to minio: %s", model_path)
            try:
                state_store_key = f"eta_{workflow_id}"
                dapr_service = DaprService()
                state_store_data = dapr_service.get_state(
                    store_name=app_settings.statestore_name,
                    key=state_store_key,
                ).json()
                state_store_data["current_step"] = "save_model"
                state_store_data["steps_data"]["save_model"]["start_time"] = datetime.now(timezone.utc).isoformat()
                dapr_service.save_to_statestore(
                    store_name=app_settings.statestore_name,
                    key=state_store_key,
                    value=state_store_data,
                    ttl=86400,
                )
            except Exception as e:
                logger.exception("Error updating workflow eta in state store: %s", e)

            # Start model upload
            notification_req.payload.event = "save_model"
            notification_req.payload.content = NotificationContent(
                title="Saving the model to the registry",
                message="Saving the model to the registry",
                status=WorkflowStatus.STARTED,
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )

            # TODO: fix the prefix and base path
            store_client = ModelStore(model_download_dir=app_settings.model_download_dir)
            if not store_client.upload_folder(prefix=model_path):
                raise SaveRegistryException("Error uploading the model to the registry")

            # TODO: Update download history status to UPLOADED once migration is done
            # try:
            #     DownloadHistory.update_download_status(model_path, ModelDownloadStatus.UPLOADED)
            #     logger.info("Updated download history status to UPLOADED for %s", model_path)
            # except Exception as e:
            #     logger.warning("Failed to update download history status to UPLOADED: %s", e)
            #     # Non-critical error, continue

            # Complete model download
            notification_req.payload.content = NotificationContent(
                title="Saved the model to the registry",
                message="Saved the model to the registry",
                status=WorkflowStatus.COMPLETED,
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )

            return model_path
        except (Exception, SaveRegistryException) as e:
            logger.exception("Error saving the model to the registry: %s", str(e))

            # DON'T delete local files or download history - preserve for retry/resume
            # Mark download as FAILED instead
            try:
                DownloadHistory.mark_download_failed(model_path)
                logger.info("Marked download as FAILED for %s (files preserved for retry)", model_path)
            except Exception as mark_error:
                logger.warning("Failed to mark download as FAILED: %s", mark_error)

            notification_req.payload.event = "save_model"
            error_message = str(e)
            notification_req.payload.content = NotificationContent(
                title="Failed to save the model to the registry",
                message=f"{error_message}. Files preserved for retry. Fix: Retry the workflow to resume upload"
                if error_message
                else "Files preserved for retry. Fix: Retry the workflow to resume upload",
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )
            raise e

    @staticmethod
    def extract_model_info(
        workflow_id: str,
        model_path: str,
        model_uri: str,
        provider_type: str,
        notification_request: NotificationRequest,
        hf_token: Optional[str] = None,
        target_topic_name: Optional[str] = None,
        target_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Extract the model info if it doesn't already exist."""
        notification_req = notification_request.model_copy(deep=True)

        # Start model extraction notification first
        notification_req.payload.event = "model_extraction"
        notification_req.payload.content = NotificationContent(
            title="Extracting the model",
            message="Extracting the model from the given path",
            status=WorkflowStatus.STARTED,
        )
        dapr_workflow.publish_notification(
            workflow_id=workflow_id,
            notification=notification_req,
            target_topic_name=target_topic_name,
            target_name=target_name,
        )

        try:
            state_store_key = f"eta_{workflow_id}"
            dapr_service = DaprService()
            state_store_data = dapr_service.get_state(
                store_name=app_settings.statestore_name,
                key=state_store_key,
            ).json()
            state_store_data["current_step"] = "model_extraction"
            dapr_service.save_to_statestore(
                store_name=app_settings.statestore_name,
                key=state_store_key,
                value=state_store_data,
                ttl=86400,
            )
        except Exception as e:
            logger.exception("Error updating workflow eta in state store: %s", e)

        try:
            if provider_type == "hugging_face":
                # Check if model with extraction status completed already exists using fetch_one
                try:
                    crud = ModelInfoCRUD()
                    existing_model = crud.check_existing_model(
                        model_uri=model_uri, extraction_status=ModelExtractionStatus.COMPLETED
                    )

                    if existing_model:
                        logger.info("Model already exists, skipping extraction")
                        existing_model_info = ModelInfo.model_validate(existing_model, from_attributes=True)

                        # Validate the model info
                        ModelExtractionService.validate_model_info(existing_model_info, provider_type, model_path)

                        notification_req.payload.content = NotificationContent(
                            title="Extracted the model",
                            message="Extracted the model information",
                            status=WorkflowStatus.COMPLETED,
                        )
                        dapr_workflow.publish_notification(
                            workflow_id=workflow_id,
                            notification=notification_req,
                            target_topic_name=target_topic_name,
                            target_name=target_name,
                        )
                        return existing_model_info.model_dump(mode="json")

                except Exception as e:
                    logger.exception(f"Error checking existing model information: {e}")
                    raise
            # initializing model evals
            model_evals = []
            if provider_type == "hugging_face":
                # Try to get from BudConnect first, then extract if needed
                budconnect_extractor = HuggingFaceWithBudConnect()

                try:
                    # Run async extraction in sync context
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        model_info, model_evals, from_cache = loop.run_until_complete(
                            budconnect_extractor.extract_model_info(model_uri, hf_token)
                        )
                        logger.info("Model info extracted (from_cache=%s): %s", from_cache, model_uri)
                    finally:
                        loop.close()
                except Exception as e:
                    logger.warning("BudConnect integration failed, falling back to direct extraction: %s", str(e))
                    # Fallback to direct HuggingFace extraction
                    model_info, model_evals = HuggingFaceModelInfo().from_pretrained(model_uri, hf_token)

                ModelExtractionService.validate_model_extraction(model_info, model_evals, True)
            elif provider_type in ["url", "disk"]:
                model_info = LocalModelExtraction(model_uri, model_path).extract_model_info()
                ModelExtractionService.validate_model_extraction(model_info, None, False)

            if provider_type == "hugging_face":
                try:
                    if model_info is not None:
                        model_info_dict = model_info.model_dump(exclude={"license"})

                        if model_info.license is not None:
                            model_info_dict["license_id"] = model_info.license.id

                        # check if the model already exists
                        with ModelInfoCRUD() as crud:
                            existing_model = crud.fetch_one(conditions={"uri": model_info.uri})
                            if existing_model:
                                db_model_info = crud.update(data=model_info_dict, conditions={"uri": model_info.uri})
                                logger.debug("Model info updated for uri %s", model_info.uri)
                            else:
                                db_model_info = crud.insert(data=model_info_dict, raise_on_error=False)
                                logger.debug("Model info inserted for uri %s", model_info.uri)
                        if model_evals:
                            leaderboard_data = LeaderboardService().format_llm_leaderboard_data(
                                model_evals, db_model_info.id
                            )
                            with LeaderboardCRUD() as crud:
                                crud.update_or_insert_leaderboards(db_model_info.id, leaderboard_data)
                                logger.debug("Leaderboard data inserted for model %s", model_info.uri)
                except Exception as e:
                    logger.exception("Error inserting the model info: %s", str(e))

            # Validate the model info
            ModelExtractionService.validate_model_info(model_info, provider_type, model_path)

            # Complete model extraction
            notification_req.payload.content = NotificationContent(
                title="Extracted the model",
                message="Extracted the model information",
                status=WorkflowStatus.COMPLETED,
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )

            return model_info.model_dump(mode="json") if model_info else {}
        except UnsupportedModelException as e:
            # Delete downloaded model from local path
            downloaded_model_path = os.path.join(app_settings.model_download_dir, model_path)
            safe_delete(downloaded_model_path)
            DownloadHistory.delete_download_history(model_path)

            logger.exception("Unsupported model detected: %s", str(e))
            notification_req.payload.content = NotificationContent(
                title=f"{str(e)}",
                message="Fix: Add different model",
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )
            raise e
        except ModelExtractionException as e:
            # Delete downloaded model from local path
            downloaded_model_path = os.path.join(app_settings.model_download_dir, model_path)
            safe_delete(downloaded_model_path)
            DownloadHistory.delete_download_history(model_path)

            notification_req.payload.content = NotificationContent(
                title=f"{str(e)}",
                message="Fix: Add valid model",
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )
            raise e
        except Exception as e:
            logger.exception("Error extracting the model: %s", str(e))
            # Delete downloaded model from local path
            downloaded_model_path = os.path.join(app_settings.model_download_dir, model_path)
            safe_delete(downloaded_model_path)
            DownloadHistory.delete_download_history(model_path)

            error_message = str(e)
            notification_req.payload.content = NotificationContent(
                title="Failed to extract the model",
                message=f"{error_message}. Fix: Retry the model extraction"
                if error_message
                else "Fix: Retry the model extraction",
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )
            raise e

    @staticmethod
    def calculate_initial_eta(
        provider_type: Literal["hugging_face", "url", "disk"],
        model_uri: str,
        workflow_id: str,
        hf_token: Optional[str] = None,
    ) -> int:
        """Calculate the initial ETA for the model extraction process."""
        # Workflow steps order
        steps_order = ["validation", "model_download", "model_extraction", "save_model"]

        # State store data structure
        state_store_data = {
            "workflow_id": workflow_id,
            "provider_type": provider_type,
            "current_step": "validation",  # default step
            "initial_eta": None,
            "steps_order": steps_order,
            "steps_data": {
                "validation": {"eta": None},
                "model_download": {
                    "is_archived": None,
                    "current_process": "download",
                    "start_time": None,
                    "eta": None,
                    "download_eta": None,
                    "extraction_eta": None,
                    "current_file": None,
                    "total_files": None,
                    "current_file_name": None,
                    "current_file_size": None,
                    "total_size": None,
                    "output_path": None,
                    "directory_name": None,
                },
                "model_extraction": {"eta": None},
                "save_model": {
                    "start_time": None,
                    "eta": None,
                    "current_file": None,
                    "total_files": None,
                    "current_file_name": None,
                    "current_file_size": None,
                    "total_size": None,
                },
            },
        }

        # Define static etas in seconds
        validation_eta = None
        if provider_type == "hugging_face":
            # Average HuggingFace api response 0.5752439022
            validation_eta = 0.6
        elif provider_type == "url":
            # Average url validation 0.9805357933
            validation_eta = 1
        elif provider_type == "disk":
            # Average os path exists 0.002617835999
            validation_eta = 0.01

        model_extraction_eta = 160

        # If model info exist with completed extraction status then only db query is required
        try:
            with ModelInfoCRUD() as crud:
                existing_model = crud.fetch_one(
                    conditions={"uri": model_uri, "extraction_status": ModelExtractionStatus.COMPLETED}
                )
                if existing_model:
                    model_extraction_eta = 1
        except Exception as e:
            logger.exception("Error fetching existing model: %s", e)

        # Define dynamic etas
        is_archived = False

        model_download_eta = None
        model_archive_extraction_eta = 0
        model_download_total_files = 0
        model_download_total_size = 0

        save_to_registry_eta = None
        save_to_registry_total_files = 0
        save_to_registry_total_size = 0

        extraction_bytes_per_second = 80549605.3

        # HuggingFace download eta
        if provider_type == "hugging_face":
            model_files, total_size = HuggingFaceModelInfo().list_repository_files(model_uri, hf_token)
            if len(model_files) != 0:
                model_download_total_files = len(model_files)
                model_download_total_size = total_size

                # Estimate download speed
                download_speed = estimate_download_speed("https://huggingface.co")

                try:
                    model_download_eta = total_size / download_speed
                    logger.debug("HuggingFace model download eta: %s", model_download_eta)
                except ZeroDivisionError as e:
                    logger.exception("Error calculating HuggingFace model download eta: %s", e)
                    model_download_eta = 120

                # Analyze large files
                large_files_info = HuggingfaceUtils().analyze_large_files(model_files)
                save_to_registry_total_files = large_files_info["large_file_count"]
                save_to_registry_total_size = large_files_info["total_size_bytes"]
                logger.debug("Save to registry total files: %s", save_to_registry_total_files)
                logger.debug("Save to registry total size: %s", save_to_registry_total_size)

                # Estimate minio upload speed
                minio_upload_speed = measure_minio_upload_speed()
                logger.debug("Minio upload speed: %s", minio_upload_speed)

                try:
                    save_to_registry_eta = save_to_registry_total_size / minio_upload_speed
                    logger.debug("Save to registry eta: %s", save_to_registry_eta)
                except ZeroDivisionError as e:
                    logger.exception("Error calculating Save to registry eta: %s", e)
                    save_to_registry_eta = 120

        # Get the file size of the url
        elif provider_type == "url":
            url_file_size = get_remote_file_size(model_uri)
            if url_file_size is None:
                url_file_size = 0
            model_download_total_size = url_file_size
            logger.debug("URL model size: %s", url_file_size)
            # Estimate download speed
            download_speed = estimate_download_speed(model_uri)
            try:
                model_download_eta = url_file_size / download_speed
                logger.debug("URL model download eta: %s", model_download_eta)
            except ZeroDivisionError as e:
                logger.exception("Error calculating URL model download eta: %s", e)
                model_download_eta = 120

            logger.debug("URL model download eta: %s", model_download_eta)

            # Check if the url is a zip file
            if is_zip_url(model_uri):
                is_archived = True
                model_download_total_files = 1
                logger.debug("URL is a zip file")

                # Estimate extraction speed
                model_archive_extraction_eta = url_file_size / extraction_bytes_per_second
                logger.debug("URL model extraction eta: %s", model_archive_extraction_eta)

                # Overall eta
                model_download_eta = model_download_eta + model_archive_extraction_eta
                logger.debug("URL model download and extraction eta: %s", model_download_eta)

            # Estimate minio upload speed
            minio_upload_speed = measure_minio_upload_speed()
            logger.debug("Minio upload speed: %s", minio_upload_speed)

            # Consider url_file_size need to be uploaded to minio
            try:
                save_to_registry_eta = url_file_size / minio_upload_speed
                logger.debug("Save to registry eta: %s", save_to_registry_eta)
            except ZeroDivisionError as e:
                logger.exception("Error calculating Save to registry eta: %s", e)
                save_to_registry_eta = 120

        # Disk download eta
        elif provider_type == "disk":
            # Check path exist
            model_uri_path = os.path.join(app_settings.add_model_dir, model_uri)
            logger.debug("Model URI path: %s", model_uri_path)

            if os.path.exists(model_uri_path):
                disk_model_size = get_size_in_bytes(model_uri_path)
                model_download_total_size = disk_model_size
                logger.debug("Disk model size: %s", disk_model_size)

                # Estimate transfer speed
                transfer_speed = measure_transfer_speed()
                model_download_eta = disk_model_size / transfer_speed
                logger.debug("Disk model download eta: %s", model_download_eta)

                # Check if the url is a zip file
                if is_zip_file(model_uri_path):
                    is_archived = True
                    model_download_total_files = 1
                    logger.debug("Disk model is a zip file")

                    # Estimate extraction speed
                    model_archive_extraction_eta = disk_model_size / extraction_bytes_per_second
                    logger.debug("Disk model extraction eta: %s", model_archive_extraction_eta)

                    # Overall eta
                    model_download_eta = model_download_eta + model_archive_extraction_eta
                    logger.debug("Disk model download and extraction eta: %s", model_download_eta)

                    # Estimate minio upload speed
                    minio_upload_speed = measure_minio_upload_speed()
                    logger.debug("Minio upload speed: %s", minio_upload_speed)

                    # Consider url_file_size need to be uploaded to minio
                    save_to_registry_eta = disk_model_size / minio_upload_speed
                    logger.debug("Save to registry eta: %s", save_to_registry_eta)
                elif os.path.isdir(model_uri_path):
                    model_files, _ = list_directory_files(model_uri_path)
                    if len(model_files) != 0:
                        model_download_total_files = len(model_files)
                        logger.debug("Model download total files: %s", model_download_total_files)

                        # Analyze large files
                        large_files_info = HuggingfaceUtils().analyze_large_files(model_files)
                        save_to_registry_total_files = large_files_info["large_file_count"]
                        save_to_registry_total_size = large_files_info["total_size_bytes"]
                        logger.debug("Save to registry total files: %s", save_to_registry_total_files)
                        logger.debug("Save to registry total size: %s", save_to_registry_total_size)

                        # Estimate minio upload speed
                        minio_upload_speed = measure_minio_upload_speed()
                        logger.debug("Minio upload speed: %s", minio_upload_speed)

                        try:
                            save_to_registry_eta = save_to_registry_total_size / minio_upload_speed
                            logger.debug("Save to registry eta: %s", save_to_registry_eta)
                        except ZeroDivisionError as e:
                            logger.exception("Error calculating Save to registry eta: %s", e)
                            save_to_registry_eta = 120

        if model_download_eta is None:
            # Assuming invalid/access denied model incase of HuggingFace
            # Setting a default eta of 120 seconds
            model_download_eta = 120
            logger.debug("Model download default eta: %s", model_download_eta)

        if save_to_registry_eta is None:
            # Assuming Unable to determine large file count and total size
            # Setting a default eta of 120 seconds
            save_to_registry_eta = 120
            logger.debug("Save to registry default eta: %s", save_to_registry_eta)

        # Calculate initial eta
        initial_eta = model_download_eta + save_to_registry_eta + model_extraction_eta + validation_eta
        logger.debug("Calculated initial eta: %s", initial_eta)

        # Update state store data
        state_store_data["initial_eta"] = initial_eta
        state_store_data["steps_data"]["validation"]["eta"] = validation_eta

        state_store_data["steps_data"]["model_download"]["eta"] = model_download_eta
        state_store_data["steps_data"]["model_download"]["extraction_eta"] = model_archive_extraction_eta
        state_store_data["steps_data"]["model_download"]["total_files"] = model_download_total_files
        state_store_data["steps_data"]["model_download"]["total_size"] = model_download_total_size
        state_store_data["steps_data"]["model_download"]["is_archived"] = is_archived
        if is_archived and model_archive_extraction_eta:
            state_store_data["steps_data"]["model_download"]["download_eta"] = (
                model_download_eta - model_archive_extraction_eta
            )
        else:
            state_store_data["steps_data"]["model_download"]["download_eta"] = model_download_eta

        state_store_data["steps_data"]["model_extraction"]["eta"] = model_extraction_eta

        state_store_data["steps_data"]["save_model"]["eta"] = save_to_registry_eta
        state_store_data["steps_data"]["save_model"]["total_files"] = save_to_registry_total_files
        state_store_data["steps_data"]["save_model"]["total_size"] = save_to_registry_total_size

        # Push state store data to dapr
        state_store_key = f"eta_{workflow_id}"
        eta_ttl = 86400  # 24 hours
        dapr_service = DaprService()

        logger.debug("State store name: %s", app_settings.statestore_name)
        dapr_service.save_to_statestore(
            store_name=app_settings.statestore_name,
            key=state_store_key,
            value=state_store_data,
            ttl=eta_ttl,
        )
        logger.debug("data pushed to dapr state store %s", state_store_data)

        return initial_eta

    @staticmethod
    def validate_model_info(model_info: ModelInfo, provider_type: str, model_path: str) -> None:
        """Validate the model info.

        Args:
            model_info (ModelInfo): The model info.
            provider_type (str): The provider type.
            model_path (Optional[str]): The model path.
        """
        # if provider_type == "hugging_face":
        #     # NOTE: Adapter, Quantization models not supported yet
        #     model_tree_dict = model_info.model_tree.model_dump()
        #     is_adapter = model_tree_dict.get("is_adapter")
        #     is_quantization = model_tree_dict.get("is_quantization")

        #     if is_adapter or is_quantization:
        #         model_path = os.path.join(app_settings.model_download_dir, model_path)
        #         if os.path.exists(model_path):
        #             safe_delete(model_path)
        #         if is_adapter:
        #             raise UnsupportedModelException("Adapter-based models are not supported yet")
        #         elif is_quantization:
        #             raise UnsupportedModelException("Quantized models are not supported yet")

        # Check modality has been set
        if not model_info.modality:
            raise UnsupportedModelException("Unable to determine the modality of the model")

    @staticmethod
    def validate_model_extraction(
        model_info: ModelInfo, model_evals: Optional[List[Dict]] = None, is_evals_required: bool = True
    ) -> None:
        """Validate the model extraction status based on presence and non-emptiness of required fields.

        Args:
            model_info (ModelInfo): The model information object.
            model_evals (Optional[dict]): The evaluated benchmarks and results.
            is_evals_required (bool): Whether evals are required for this model.
        """

        def is_missing(val):
            return val is None or val == "" or val == [] or val == {}

        if (
            is_missing(model_info.description)
            or is_missing(model_info.strengths)
            or is_missing(model_info.limitations)
            or is_missing(model_info.use_cases)
            or (is_evals_required and is_missing(model_evals))
            or is_missing(model_info.modality)
        ):
            model_info.extraction_status = ModelExtractionStatus.PARTIAL
        else:
            model_info.extraction_status = ModelExtractionStatus.COMPLETED

    def __call__(self, request: ModelExtractionRequest, workflow_id: Optional[str] = None) -> ModelExtractionResponse:
        """Execute the model extraction process based on the provided model URI.

        This method retrieves model information from a given model URI.

        Args:
            request (ModelExtractionRequest): The model extraction request containing
            the model URI.
            workflow_id (Optional[str]): An optional workflow ID for tracking the
            model extraction process.

        Raises:
            ValueError: If the model information is not available or empty.

        Returns:
            ModelExtractionResponse: The model extraction response containing the
            model information.
        """
        if not workflow_id:
            workflow_id = str(uuid.uuid4())

        workflow_name = "perform_model_extraction"
        notification_request = NotificationRequest.from_cloud_event(
            cloud_event=request,
            name=workflow_name,
            workflow_id=workflow_id,
        )
        hf_token = request.hf_token  # TODO: add decryption logic here

        # Validate the model URI
        self.validate_model_uri(
            workflow_id,
            notification_request,
            request.model_uri,
            request.provider_type,
            hf_token,
            request.source_topic,
            request.source,
        )

        # Download the model
        downloaded_path = self.download_model(
            workflow_id,
            request.model_name,
            request.model_uri,
            request.provider_type,
            notification_request,
            hf_token,
            request.source_topic,
            request.source,
        )

        # Extract the model info
        model_info = self.extract_model_info(
            workflow_id,
            downloaded_path,
            request.model_uri,
            request.provider_type,
            notification_request,
            hf_token,
            request.source_topic,
            request.source,
        )

        # Save the model to the registry
        _ = self.save_model_to_registry(
            workflow_id,
            downloaded_path,
            notification_request,
            request.source_topic,
            request.source,
        )

        response = ModelExtractionResponse(workflow_id=workflow_id, model_info=model_info, local_path=downloaded_path)

        notification_request.payload.event = "results"
        notification_request.payload.content = NotificationContent(
            title="Model Extraction Results",
            message="The model extraction results are ready",
            result=response.model_dump(),
            status=WorkflowStatus.COMPLETED,
        )

        dapr_workflow.publish_notification(
            workflow_id=workflow_id,
            notification=notification_request,
            target_topic_name=request.source_topic,
            target_name=request.source,
        )

        return response


class ModelSecurityScanService:
    """Service class for security scan."""

    @staticmethod
    def perform_security_scan(
        workflow_id: str,
        notification_request: NotificationRequest,
        model_path: str,
        target_topic_name: Optional[str] = None,
        target_name: Optional[str] = None,
    ) -> Dict:
        """Perform  security scan on a given model."""
        import subprocess
        import tempfile

        notification_req = notification_request.model_copy(deep=True)

        filtered_env = {
            "PSQL_PORT": str(app_settings.psql_port),
            "PSQL_DB_NAME": app_settings.psql_dbname,
            "PSQL_HOST": app_settings.psql_host,
            "CLAMD_HOST": app_settings.clamd_host,
            "CLAMD_PORT": str(app_settings.clamd_port),
        }

        scan_result = {
            "total_issues": 0,
            "total_scanned": 0,
            "total_issues_by_severity": {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0},
            "scanned_files": [],
            "total_skipped_files": 0,
            "model_issues": [],
        }

        try:
            logger.info("Performing security scan on the model: %s", model_path)

            # Start model security scan
            notification_req.payload.event = "security_scan"
            notification_req.payload.content = NotificationContent(
                title="Performing security scan",
                message="Performing security scan on the given model inside firejail sandbox",
                status=WorkflowStatus.STARTED,
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )

            # time.sleep(3)  # Added delay to avoid Blinking in frontend for smaller models

            with tempfile.TemporaryDirectory() as model_temp_dir:
                logger.info("Created temporary directory: %s", model_temp_dir)
                os.chmod(model_temp_dir, 0o555)  # Make the temperory directory readable by the clamav

                try:
                    download_success = ModelSecurityScanService.download_model_from_minio(
                        prefix=model_path,
                        local_destination=model_temp_dir,
                        workflow_id=workflow_id,
                    )
                except Exception as download_error:
                    logger.exception("Unable to download the model :%s", download_error)
                    raise ModelScanException("Unable to download the model") from download_error

                if not download_success:
                    raise ModelScanException("No files found in the registry")

                logger.info("Model downloaded successfully. Starting scan in directory: %s", model_temp_dir)

                # TODO : Actual eta implementation for individual security scans needs to be implemented.
                if workflow_id:
                    try:
                        state_store_key = f"eta_{workflow_id}"
                        dapr_service = DaprService()
                        state_store_data = dapr_service.get_state(
                            store_name=app_settings.statestore_name,
                            key=state_store_key,
                        ).json()
                        state_store_data["current_step"] = "security_scan"
                        dapr_service.save_to_statestore(
                            store_name=app_settings.statestore_name,
                            key=state_store_key,
                            value=state_store_data,
                            ttl=86400,
                        )
                    except Exception as e:
                        logger.exception("Error updating workflow eta in state store: %s", e)

                try:
                    scan_result = subprocess.run(
                        [
                            "firejail",
                            "--debug",
                            "--quiet",
                            "--net=none",
                            "python3",
                            "-m",
                            "budmodel.model_info.security",
                            model_temp_dir,
                        ],
                        capture_output=True,
                        text=True,
                        check=True,
                        env=filtered_env,
                    )
                except Exception as e:
                    logger.exception("Error while scanning inside sandbox: %s", e)
            notification_req.payload.content = NotificationContent(
                title="Security scan completed",
                message="Security scan on the given model is completed",
                status=WorkflowStatus.COMPLETED,
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )

            result_json = json.loads(scan_result.stdout)
            return result_json

        except ModelScanException as e:
            logger.error("Model security scan process failed: %s", str(e))
            notification_req.payload.event = "security_scan"
            notification_req.payload.content = NotificationContent(
                title="Security Scan Failed",
                message=f"Scan error: {str(e)}",
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )
            raise

        except Exception as e:
            logger.exception("Unexpected error in security scan: %s", str(e))
            notification_req.payload.event = "security_scan"
            error_message = str(e)
            notification_req.payload.content = NotificationContent(
                title="Failed to perform security scan",
                message=f"{error_message}. Fix: Retry the security scan"
                if error_message
                else "Fix: Retry the security scan",
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )
            raise

    @staticmethod
    def download_model_from_minio(prefix: str, local_destination: str, workflow_id: Optional[str] = None) -> List[str]:
        """Download all files under a prefix using `download_file` and set only `start_time` in state store."""
        store = ModelStore(model_download_dir=app_settings.model_download_dir)
        store_client = store.get_client()
        downloaded_files = []

        downloaded_size = 0

        # 1. List files
        try:
            objects = store_client.list_objects(app_settings.minio_bucket, prefix=prefix, recursive=True)
            object_names = [obj.object_name for obj in objects if not obj.object_name.endswith("/")]
        except S3Error as err:
            logger.error(f"Error listing objects: {err}")
            raise

        total_files = len(object_names)
        logger.info(f"Found {total_files} files to download under {prefix}")

        if not object_names:
            return downloaded_files
        if workflow_id:
            try:
                dapr_service = DaprService()
                state_store_key = f"eta_{workflow_id}"
                start_time = datetime.now(timezone.utc).isoformat()
                response = dapr_service.get_state(app_settings.statestore_name, key=state_store_key)
                if not response.data:
                    logger.warning("State store data is empty for key: %s", state_store_key)
                    return downloaded_files
                state = response.json()
                state["current_step"] = "minio_download"
                state["steps_data"]["minio_download"]["start_time"] = start_time
                state["steps_data"]["minio_download"]["download_path"] = local_destination
            except Exception as e:
                logger.exception("Statestore unavailable or error occurred while getting state: %s", e)

        for _index, object_name in enumerate(object_names):
            relative_path = object_name[len(prefix) :].lstrip("/")
            local_file_path = os.path.join(local_destination, relative_path)

            try:
                file_path, file_size = store.download_file(object_name, local_file_path)
                downloaded_files.append(file_path)
                downloaded_size += file_size
                if workflow_id:
                    try:
                        state["steps_data"]["minio_download"]["downloaded_size"] = downloaded_size
                        dapr_service.save_to_statestore(
                            store_name=app_settings.statestore_name,
                            key=state_store_key,
                            value=state,
                            ttl=86400,
                        )
                    except Exception as e:
                        logger.exception(f"Failed to update statestore for {object_name}: {e}")

            except S3Error as err:
                logger.error(f"Failed to download {object_name}: {err}")

        return downloaded_files

    @staticmethod
    def calculate_initial_eta(workflow_id: str, model_path: str):
        """Calculate the initial ETA for the security scan process."""
        steps_order = ["minio_download", "security_scan"]

        state_store_data = {
            "workflow_id": workflow_id,
            "initial_eta": None,
            "current_step": None,
            "steps_order": steps_order,
            "steps_data": {
                "minio_download": {
                    "start_time": None,
                    "total_size": None,
                    "downloaded_size": None,
                    "download_speed": None,
                    "download_path": None,
                    "eta": None,
                },
                "security_scan": {"eta": None},
            },
        }

        client = ModelStore(app_settings.model_download_dir)

        files_count, model_size_bytes = client.get_object_count_and_size(prefix=model_path)
        download_speed = measure_minio_download_speed()

        estimated_download_time = model_size_bytes / download_speed

        # Formulae: (6.76e-9 * Model Size (bytes)) + (4.46 * Files count)
        estimated_scan_time = max((6.76e-9 * model_size_bytes) + (4.46 * files_count) - 29.4, 20)

        initial_eta = estimated_download_time + estimated_scan_time
        state_store_data["initial_eta"] = initial_eta
        state_store_data["steps_data"]["minio_download"]["total_size"] = model_size_bytes
        state_store_data["steps_data"]["minio_download"]["download_speed"] = download_speed
        state_store_data["steps_data"]["minio_download"]["eta"] = estimated_download_time
        state_store_data["steps_data"]["security_scan"]["eta"] = estimated_scan_time

        # Push state store data to dapr
        state_store_key = f"eta_{workflow_id}"
        eta_ttl = 86400
        dapr_service = DaprService()

        logger.debug("State store name: %s", app_settings.statestore_name)
        dapr_service.save_to_statestore(
            store_name=app_settings.statestore_name,
            key=state_store_key,
            value=state_store_data,
            ttl=eta_ttl,
        )
        logger.debug("data pushed to dapr state store %s", state_store_data)

        return initial_eta

    def __call__(
        self, request: ModelSecurityScanRequest, workflow_id: Optional[str] = None
    ) -> ModelSecurityScanResponse:
        """Execute the model security scan process based on the provided model path.

        This method performs security scan on a given model path.

        Args:
            request (ModelSecurityScanRequest): The model security scan request containing
            the model path.
            workflow_id (Optional[str]): An optional workflow ID for tracking the
            model security scan process.

        Raises:
            ValueError: If the scan result is not available or empty.

        Returns:
            ModelSecurityScanResponse: The model security scan response containing the
            scan result.
        """
        if not workflow_id:
            workflow_id = str(uuid.uuid4())

        workflow_name = "perform_model_security_scan"
        notification_request = NotificationRequest.from_cloud_event(
            cloud_event=request,
            name=workflow_name,
            workflow_id=workflow_id,
        )

        # Perform the security scan
        scan_result = self.perform_security_scan(
            workflow_id,
            notification_request,
            request.model_path,
            request.source_topic,
            request.source,
        )

        response = ModelSecurityScanResponse(workflow_id=workflow_id, scan_result=scan_result)

        notification_request.payload.event = "results"
        notification_request.payload.content = NotificationContent(
            title="Model Security Scan Results",
            message="The model security scan results are ready",
            result=response.model_dump(),
            status=WorkflowStatus.COMPLETED,
        )

        dapr_workflow.publish_notification(
            workflow_id=workflow_id,
            notification=notification_request,
            target_topic_name=request.source_topic,
            target_name=request.source,
        )

        return response


class ModelDeleteService:
    """Service class for model delete."""

    @staticmethod
    def delete_model(model_path: str) -> bool:
        """Delete the model from the local filesystem."""
        logger.debug("Deleting model: %s", model_path)

        model_absolute_path = os.path.join(app_settings.model_download_dir, model_path)
        is_deleted = safe_delete(model_absolute_path)
        logger.debug("Model deleted from local filesystem")

        # Delete the model from the MinIO store
        store_client = ModelStore(model_download_dir=app_settings.model_download_dir)
        is_deleted = store_client.remove_objects(model_path, recursive=True)
        logger.debug("Model deleted from MinIO store")

        # Delete license file from MinIO store
        minio_license_object_name = f"{LICENSE_MINIO_OBJECT_NAME}/{model_path}"
        is_license_deleted = store_client.remove_objects(
            minio_license_object_name, recursive=True, bucket_name=app_settings.minio_model_bucket
        )
        logger.debug("License file delete status from MinIO store: %s", is_license_deleted)

        # Delete the model from download history
        DownloadHistory.delete_download_history(model_path)
        logger.debug("Model deleted from download history")

        return is_deleted


class LicenseFAQService:
    """Service class for fetching License FAQs."""

    @staticmethod
    def fetch_license_faqs(
        workflow_id: str,
        notification_request: NotificationRequest,
        license_source: str,
        target_topic_name: Optional[str] = None,
        target_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch the license FAQs."""
        notification_req = notification_request.model_copy(deep=True)
        try:
            logger.info("Fetching license FAQs from: %s", license_source)

            # Notify about the start of the process
            notification_req.payload.event = "fetch_license_faqs"
            notification_req.payload.content = NotificationContent(
                title="Fetching License FAQs",
                message="Retrieving FAQs from the provided source",
                status=WorkflowStatus.STARTED,
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )

            # Fetch FAQs from the license source (URL or file path)
            # faqs = license_QA(license_source)

            # Updated to use the new function
            # license_details = generate_license_details(license_source)

            # Extract licenses details from source
            if license_source.startswith(("http://", "https://")):
                license_text = LicenseExtractor().get_license_content_from_url(license_source)
            else:
                license_text = LicenseExtractor().get_license_content_from_minio(license_source)
            logger.debug("License text: %s", license_text)
            license_details = LicenseExtractor().generate_license_details(license_text)

            # Notify about completion
            notification_req.payload.content = NotificationContent(
                title="License FAQs Retrieved",
                message="Successfully retrieved FAQs from the license source",
                status=WorkflowStatus.COMPLETED,
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )

            return license_details

        except LicenseExtractionException as e:
            logger.exception("Error fetching license FAQs: %s", str(e))
            notification_req.payload.event = "fetch_license_faqs"
            notification_req.payload.content = NotificationContent(
                title="Failed to Fetch License FAQs",
                message=f"{e.message}",
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )
            raise e
        except Exception as e:
            logger.exception("Error fetching license FAQs: %s", str(e))
            notification_req.payload.event = "fetch_license_faqs"
            error_message = str(e)
            notification_req.payload.content = NotificationContent(
                title="Failed to Fetch License FAQs",
                message=f"{error_message}. Fix: Ensure the license source is correct and retry"
                if error_message
                else "Fix: Ensure the license source is correct and retry",
                status=WorkflowStatus.FAILED,
                primary_action="retry",
            )
            dapr_workflow.publish_notification(
                workflow_id=workflow_id,
                notification=notification_req,
                target_topic_name=target_topic_name,
                target_name=target_name,
            )
            raise e

    def __call__(self, request: LicenseFAQRequest, workflow_id: Optional[str] = None) -> LicenseFAQResponse:
        """Execute the license FAQ fetching process based on the provided license source.

        Args:
            request (LicenseFAQRequest): The request containing the license source.
            workflow_id (Optional[str]): An optional workflow ID for tracking the process.

        Returns:
            LicenseFAQResponse: The response containing the fetched FAQs.
        """
        if not workflow_id:
            workflow_id = str(uuid.uuid4())

        workflow_name = "fetch_license_faqs"
        notification_request = NotificationRequest.from_cloud_event(
            cloud_event=request,
            name=workflow_name,
            workflow_id=workflow_id,
        )

        # Fetch license FAQs
        license_details = self.fetch_license_faqs(
            workflow_id,
            notification_request,
            request.license_source,
            request.source_topic,
            request.source,
        )

        response = LicenseFAQResponse(workflow_id=workflow_id, license_details=license_details)

        notification_request.payload.event = "results"
        notification_request.payload.content = NotificationContent(
            title="License FAQs Results",
            message="The license FAQs have been retrieved successfully",
            result=response.model_dump(),
            status=WorkflowStatus.COMPLETED,
        )

        dapr_workflow.publish_notification(
            workflow_id=workflow_id,
            notification=notification_request,
            target_topic_name=request.source_topic,
            target_name=request.source,
        )

        return response


class ModelExtractionETAObserver:
    """Observer class for model extraction ETA."""

    @staticmethod
    def _calculate_validation_eta(state_store_data: Dict[str, Any]) -> int:
        """Calculate the ETA for the model validation process."""
        steps_data = state_store_data.get("steps_data", {})
        eta = 0
        for _step_name, step_data in steps_data.items():
            eta += step_data.get("eta", 0)
        return math.ceil(eta)

    @staticmethod
    def _calculate_model_download_eta(state_store_data: Dict[str, Any]) -> int:
        """Calculate the ETA for the model download process."""
        provider_type = state_store_data["provider_type"]

        # Calculate the ETA for remaining steps
        model_extraction_eta = state_store_data["steps_data"]["model_extraction"]["eta"]
        save_model_eta = state_store_data["steps_data"]["save_model"]["eta"]
        remaining_steps_eta = model_extraction_eta + save_model_eta

        is_archived = state_store_data["steps_data"]["model_download"]["is_archived"]
        current_process = state_store_data["steps_data"]["model_download"]["current_process"]
        output_path = state_store_data["steps_data"]["model_download"]["output_path"]
        total_size = state_store_data["steps_data"]["model_download"]["total_size"]
        start_time_utc = state_store_data["steps_data"]["model_download"]["start_time"]
        start_time = datetime.fromisoformat(start_time_utc)
        unarchive_eta = state_store_data["steps_data"]["model_download"]["extraction_eta"]

        if provider_type == "hugging_face":
            # Check if output_path is None (can happen after download failure)
            if output_path is None:
                logger.warning("Output path is None in ETA calculation, using fallback eta")
                eta = state_store_data["steps_data"]["model_download"]["eta"] + remaining_steps_eta
                return math.ceil(eta)

            current_size = get_size_in_bytes(os.path.join(app_settings.model_download_dir, output_path))
            current_time = datetime.now(timezone.utc)
            time_diff_seconds = (current_time - start_time).total_seconds()

            if time_diff_seconds > 0:
                try:
                    download_speed = current_size / time_diff_seconds
                    remaining_size = total_size - current_size
                    remaining_download_eta = remaining_size / download_speed
                    eta = remaining_download_eta + remaining_steps_eta
                    logger.debug("Hugging Face Model download workflow ETA: %s", eta)
                    return math.ceil(eta)
                except ZeroDivisionError:
                    eta = state_store_data["steps_data"]["model_download"]["eta"] + remaining_steps_eta
                    return math.ceil(eta)
            else:
                eta = state_store_data["steps_data"]["model_download"]["eta"] + remaining_steps_eta
                return math.ceil(eta)
        elif provider_type == "url":
            if not is_archived:
                eta = state_store_data["steps_data"]["model_download"]["download_eta"] + remaining_steps_eta
                return math.ceil(eta)
            else:
                if current_process == "download":
                    download_eta = state_store_data["steps_data"]["model_download"]["download_eta"]
                    eta = download_eta + unarchive_eta + remaining_steps_eta
                    logger.debug("URL Model download workflow ETA: %s", eta)
                    return math.ceil(eta)
                elif current_process == "extraction":
                    folder_name = os.path.basename(output_path)
                    output_path = os.path.join(app_settings.model_download_dir, folder_name)
                    current_size = get_size_in_bytes(output_path)
                    current_time = datetime.now(timezone.utc)
                    time_diff_seconds = (current_time - start_time).total_seconds()

                    if time_diff_seconds > 0:
                        try:
                            extraction_speed = current_size / time_diff_seconds
                            remaining_size = total_size - current_size
                            remaining_extraction_eta = remaining_size / extraction_speed
                            eta = remaining_extraction_eta + remaining_steps_eta
                            logger.debug("Hugging Face Model extraction workflow ETA: %s", eta)
                            return math.ceil(eta)
                        except ZeroDivisionError:
                            eta = unarchive_eta + remaining_steps_eta
                            logger.debug("Hugging Face Model extraction workflow ETA: %s", eta)
                            return math.ceil(eta)
                    else:
                        eta = unarchive_eta + remaining_steps_eta
                        return math.ceil(eta)

        elif provider_type == "disk":
            if not is_archived:
                folder_name = os.path.basename(output_path)
                output_path = os.path.join(app_settings.model_download_dir, folder_name)
                current_size = get_size_in_bytes(output_path)
                current_time = datetime.now(timezone.utc)
                time_diff_seconds = (current_time - start_time).total_seconds()

                if time_diff_seconds > 0:
                    try:
                        download_speed = current_size / time_diff_seconds
                        remaining_size = total_size - current_size
                        remaining_download_eta = remaining_size / download_speed
                        eta = remaining_download_eta + remaining_steps_eta
                        logger.debug("Hugging Face Model download workflow ETA: %s", eta)
                        return math.ceil(eta)
                    except ZeroDivisionError:
                        eta = state_store_data["steps_data"]["model_download"]["eta"] + remaining_steps_eta
                        return math.ceil(eta)
                else:
                    eta = state_store_data["steps_data"]["model_download"]["eta"] + remaining_steps_eta
                    return math.ceil(eta)
            else:
                if current_process == "download":
                    folder_name = os.path.basename(output_path)
                    output_path = os.path.join(app_settings.model_download_dir, folder_name)
                    current_size = get_size_in_bytes(output_path)
                    current_time = datetime.now(timezone.utc)
                    time_diff_seconds = (current_time - start_time).total_seconds()

                    if time_diff_seconds > 0:
                        try:
                            download_speed = current_size / time_diff_seconds
                            remaining_size = total_size - current_size
                            remaining_download_eta = remaining_size / download_speed
                            eta = remaining_download_eta + unarchive_eta + remaining_steps_eta
                            logger.debug("Hugging Face Model download workflow ETA: %s", eta)
                            return math.ceil(eta)
                        except ZeroDivisionError:
                            eta = state_store_data["steps_data"]["model_download"]["eta"] + remaining_steps_eta
                            logger.debug("Hugging Face Model download workflow ETA: %s", eta)
                            return math.ceil(eta)
                    else:
                        eta = state_store_data["steps_data"]["model_download"]["eta"] + remaining_steps_eta
                        return math.ceil(eta)
                elif current_process == "extraction":
                    folder_name = os.path.basename(output_path)
                    output_path = os.path.join(app_settings.model_download_dir, folder_name)
                    current_size = get_size_in_bytes(output_path)
                    current_time = datetime.now(timezone.utc)
                    time_diff_seconds = (current_time - start_time).total_seconds()

                    if time_diff_seconds > 0:
                        try:
                            extraction_speed = current_size / time_diff_seconds
                            remaining_size = total_size - current_size
                            remaining_extraction_eta = remaining_size / extraction_speed
                            eta = remaining_extraction_eta + remaining_steps_eta
                            logger.debug("Hugging Face Model extraction workflow ETA: %s", eta)
                            return math.ceil(eta)
                        except ZeroDivisionError:
                            eta = unarchive_eta + remaining_steps_eta
                            logger.debug("Hugging Face Model extraction workflow ETA: %s", eta)
                            return math.ceil(eta)
                    else:
                        eta = unarchive_eta + remaining_steps_eta
                        return math.ceil(eta)

    @staticmethod
    def _calculate_extraction_eta(state_store_data: Dict[str, Any]) -> int:
        """Calculate the ETA for the model extraction process."""
        extraction_eta = state_store_data["steps_data"]["model_extraction"]["eta"]
        save_model_eta = state_store_data["steps_data"]["save_model"]["eta"]
        eta = extraction_eta + save_model_eta
        logger.debug("Model extraction workflow ETA: %s", eta)
        return math.ceil(eta)

    @staticmethod
    def _calculate_save_model_eta(state_store_data: Dict[str, Any]) -> int:
        """Calculate the ETA for the model save process."""
        prefix = state_store_data["steps_data"]["model_download"]["directory_name"]
        store_client = ModelStore(model_download_dir=app_settings.model_download_dir)
        current_files, current_size = store_client.get_object_count_and_size(prefix)
        start_time_utc = state_store_data["steps_data"]["save_model"]["start_time"]
        total_size = state_store_data["steps_data"]["save_model"]["total_size"]
        start_time = datetime.fromisoformat(start_time_utc)
        current_time = datetime.now(timezone.utc)
        time_diff_seconds = (current_time - start_time).total_seconds()

        if time_diff_seconds > 0:
            try:
                upload_speed = current_size / time_diff_seconds
                remaining_size = total_size - current_size
                remaining_upload_eta = remaining_size / upload_speed
                eta = remaining_upload_eta
                logger.debug("Model save to MinIO workflow ETA: %s", eta)
                return math.ceil(eta)
            except ZeroDivisionError:
                eta = state_store_data["steps_data"]["save_model"]["eta"]
                return math.ceil(eta)
        else:
            eta = state_store_data["steps_data"]["save_model"]["eta"]
            return math.ceil(eta)

    def calculate_eta(
        self,
        workflow_id: str,
        notification_request: NotificationRequest,
        target_topic_name: Optional[str] = None,
        target_name: Optional[str] = None,
        model_uri: Optional[str] = None,
        provider_type: Optional[str] = None,
        hf_token: Optional[str] = None,
    ) -> int:
        """Calculate the ETA for the model extraction process."""
        try:
            # Get the state store data
            state_store_key = f"eta_{workflow_id}"
            dapr_service = DaprService()
            response = dapr_service.get_state(
                store_name=app_settings.statestore_name,
                key=state_store_key,
            )

            if not response.data:
                logger.warning(
                    "State store data is empty for key: %s. Attempting lazy initialization.", state_store_key
                )

                if model_uri and provider_type:
                    try:
                        logger.info("Lazy initializing ETA state for workflow: %s", workflow_id)
                        ModelExtractionService.calculate_initial_eta(
                            provider_type=provider_type,
                            model_uri=model_uri,
                            workflow_id=workflow_id,
                            hf_token=hf_token,
                        )
                        # Fetch the state again after initialization
                        response = dapr_service.get_state(
                            store_name=app_settings.statestore_name,
                            key=state_store_key,
                        )
                        if not response.data:
                            logger.error(
                                "State store data still empty after lazy initialization for key: %s", state_store_key
                            )
                            return
                    except Exception as e:
                        logger.exception("Error during lazy initialization of ETA state: %s", e)
                        return
                else:
                    logger.warning("Cannot lazy initialize ETA state: missing model_uri or provider_type")
                    return

            state_store_data = response.json()
        except Exception as e:
            logger.exception("Unable to get state store data while calculating ETA: %s", e)
            return

        calculated_eta = None
        current_step = state_store_data["current_step"]
        logger.info("Current step: %s in calculate_eta", current_step)
        if current_step == "validation":
            calculated_eta = self._calculate_validation_eta(state_store_data)
        elif current_step == "model_download":
            calculated_eta = self._calculate_model_download_eta(state_store_data)
        elif current_step == "model_extraction":
            calculated_eta = self._calculate_extraction_eta(state_store_data)
        elif current_step == "save_model":
            calculated_eta = self._calculate_save_model_eta(state_store_data)

        if not isinstance(calculated_eta, int):
            logger.error("Calculated ETA is not an integer: %s", calculated_eta)
            return

        # If the calculated ETA is negative, set it to 0
        if calculated_eta < 0:
            calculated_eta = 0

        # NOTE: Convert calculated ETA to minutes (frontend integration in minutes)
        calculated_eta = math.ceil(calculated_eta / 60)

        notification_request.payload.event = "eta"
        notification_request.payload.content = NotificationContent(
            title="Estimated time to completion",
            message=str(calculated_eta),
            status=WorkflowStatus.RUNNING,
        )

        # NOTE: eta observer payload type should match the main workflow name for successful frontend integration
        notification_request.payload.type = "perform_model_extraction"
        dapr_workflow.publish_notification(
            workflow_id=workflow_id,
            notification=notification_request,
            target_topic_name=target_topic_name,
            target_name=target_name,
        )
        logger.info("ETA calculated and published: %s", calculated_eta)

        return

    def __call__(self, request: ModelExtractionETAObserverRequest, workflow_id: Optional[str] = None):
        """Observer class for model extraction ETA."""
        if not workflow_id:
            workflow_id = str(uuid.uuid4())

        workflow_name = "perform_model_extraction_eta"
        notification_request = NotificationRequest.from_cloud_event(
            cloud_event=request,
            name=workflow_name,
            workflow_id=workflow_id,
        )

        # Calculate the ETA
        self.calculate_eta(request.workflow_id, notification_request, request.source_topic, request.source)

        return


class SecurityScanETAObserver:
    @staticmethod
    def calculate_model_download_eta(state_store_data: Dict[str, Any]):
        """Calculate the ETA for model download."""
        total_size = state_store_data["steps_data"]["minio_download"]["total_size"]
        downloaded_size = state_store_data["steps_data"]["minio_download"]["downloaded_size"] or 0
        start_time_utc = state_store_data["steps_data"]["minio_download"]["start_time"]
        start_time = datetime.fromisoformat(start_time_utc)
        current_time = datetime.now(timezone.utc)

        time_diff = (current_time - start_time).total_seconds()

        if time_diff > 0 and downloaded_size > 0:
            try:
                download_speed = downloaded_size / time_diff
                eta = (total_size - downloaded_size) / download_speed
                logger.debug("Minio download workflow ETA:%s", eta)
                return math.ceil(eta)
            except ZeroDivisionError:
                eta = state_store_data["steps_data"]["minio_download"]["eta"]
                logger.debug("Minio Model download workflow ETA: %s", eta)
                return math.ceil(eta)
        else:
            eta = state_store_data["steps_data"]["minio_download"]["eta"]
            return math.ceil(eta)

    @staticmethod
    def calculate_security_scan_eta(state_store_data: Dict[str, Any]):
        """Calculate the ETA for security scan."""
        eta = state_store_data["steps_data"]["security_scan"]["eta"]
        logger.debug("Security scan workflow ETA: %s", eta)
        return math.ceil(eta)

    def calculate_eta(
        self,
        workflow_id: str,
        notification_request: NotificationRequest,
        target_topic_name: Optional[str] = None,
        target_name: Optional[str] = None,
        model_path: Optional[str] = None,
    ) -> int:
        """Calculate estimated time of arrival for workflow completion."""
        try:
            # Get the state store data
            state_store_key = f"eta_{workflow_id}"
            dapr_service = DaprService()
            response = dapr_service.get_state(
                store_name=app_settings.statestore_name,
                key=state_store_key,
            )

            if not response.data:
                logger.warning(
                    "State store data is empty for key: %s. Attempting lazy initialization.", state_store_key
                )

                if model_path:
                    try:
                        logger.info("Lazy initializing ETA state for security scan workflow: %s", workflow_id)
                        ModelSecurityScanService.calculate_initial_eta(workflow_id=workflow_id, model_path=model_path)
                        # Fetch the state again after initialization
                        response = dapr_service.get_state(
                            store_name=app_settings.statestore_name,
                            key=state_store_key,
                        )
                        if not response.data:
                            logger.error(
                                "State store data still empty after lazy initialization for key: %s", state_store_key
                            )
                            return
                    except Exception as e:
                        logger.exception("Error during lazy initialization of ETA state: %s", e)
                        return
                else:
                    logger.warning("Cannot lazy initialize ETA state: missing model_path")
                    return

            state_store_data = response.json()
        except Exception as e:
            logger.exception("Unable to get state store data while calculating ETA: %s", e)
            return

        current_state = state_store_data["current_step"]
        if not current_state:
            return
        if current_state == "minio_download":
            calculated_eta = self.calculate_model_download_eta(state_store_data)
        else:
            calculated_eta = self.calculate_security_scan_eta(state_store_data)

        if not isinstance(calculated_eta, int):
            logger.error("Calculated ETA is not an integer: %s", calculated_eta)
            return
        if calculated_eta < 0:
            calculated_eta = 0

        # NOTE: Convert calculated ETA to minutes (frontend integration in minutes)
        calculated_eta = math.ceil(calculated_eta / 60)

        notification_request.payload.event = "eta"
        notification_request.payload.content = NotificationContent(
            title="Estimated time to completion",
            message=str(calculated_eta),
            status=WorkflowStatus.RUNNING,
        )

        # NOTE: eta observer payload type should match the main workflow name for successful frontend integration
        notification_request.payload.type = "perform_model_scanning"
        dapr_workflow.publish_notification(
            workflow_id=workflow_id,
            notification=notification_request,
            target_topic_name=target_topic_name,
            target_name=target_name,
        )
        logger.info("ETA calculated and published: %s", calculated_eta)

        return

    def __call__(self, request: ModelExtractionETAObserverRequest, workflow_id: Optional[str] = None):
        """Observer class for security ETA."""
        if not workflow_id:
            workflow_id = str(uuid.uuid4())

        workflow_name = "perform_security_scan_eta"
        notification_request = NotificationRequest.from_cloud_event(
            cloud_event=request,
            name=workflow_name,
            workflow_id=workflow_id,
        )

        # Calculate the ETA
        self.calculate_eta(request.workflow_id, notification_request, request.source_topic, request.source)

        return

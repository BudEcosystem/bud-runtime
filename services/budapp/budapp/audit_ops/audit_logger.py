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

"""Simple audit logging utility for direct, synchronous audit trail creation."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import Request
from sqlalchemy.orm import Session

from ..commons import logging
from ..commons.constants import AuditActionEnum, AuditResourceTypeEnum
from .services import AuditService


logger = logging.get_logger(__name__)


def log_audit(
    session: Session,
    action: AuditActionEnum,
    resource_type: AuditResourceTypeEnum,
    resource_id: Optional[UUID] = None,
    resource_name: Optional[str] = None,
    user_id: Optional[UUID] = None,
    details: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None,
    previous_state: Optional[Dict[str, Any]] = None,
    new_state: Optional[Dict[str, Any]] = None,
    success: bool = True,
) -> None:
    """Simple, synchronous function to log an audit entry.

    This function provides direct control to the caller about what gets logged,
    allowing resource APIs to decide exactly what information should be captured
    based on their context and business logic.

    Args:
        session: Database session for audit logging
        action: The action being performed (CREATE, UPDATE, DELETE, etc.)
        resource_type: The type of resource being acted upon
        resource_id: Optional ID of the resource
        resource_name: Optional name of the resource for display and search
        user_id: Optional ID of the user performing the action
        details: Optional dictionary with additional context/details
        request: Optional FastAPI request object for extracting IP and user agent
        previous_state: Optional previous state (for updates)
        new_state: Optional new state (for updates)
        success: Whether the action was successful

    Example usage in a service:
        ```python
        from budapp.audit_ops.audit_logger import log_audit


        def create_project(session, project_data, current_user_id, request):
            # Create the project
            project = crud.create_project(project_data)

            # Log the audit entry with full control
            log_audit(
                session=session,
                action=AuditActionEnum.CREATE,
                resource_type=AuditResourceTypeEnum.PROJECT,
                resource_id=project.id,
                user_id=current_user_id,
                details={"project_name": project.name, "project_type": project.type, "created_by": current_user_id},
                request=request,
            )

            return project
        ```
    """
    try:
        # Extract IP address and user agent from request if provided
        ip_address = None
        user_agent = None

        if request:
            # Try to get IP from X-Forwarded-For header first (for proxied requests)
            forwarded_for = request.headers.get("X-Forwarded-For")
            if forwarded_for:
                ip_address = forwarded_for.split(",")[0].strip()
            elif request.client:
                ip_address = request.client.host

            # Get user agent
            user_agent = request.headers.get("User-Agent", "Unknown")

        # Create audit service instance
        audit_service = AuditService(session)

        # Create a copy of details to avoid modifying the original
        audit_details = details.copy() if details else {}

        # Add user agent to details if captured
        if user_agent and "user_agent" not in audit_details:
            audit_details["user_agent"] = user_agent[:200]  # Limit length

        # Add success status to details for internal use
        audit_details["success"] = success

        # Choose the appropriate audit method based on action
        if action == AuditActionEnum.CREATE:
            audit_service.audit_create(
                resource_type=resource_type,
                resource_id=resource_id,
                resource_name=resource_name,
                resource_data=audit_details,
                user_id=user_id,
                ip_address=ip_address,
            )
        elif action == AuditActionEnum.UPDATE:
            audit_service.audit_update(
                resource_type=resource_type,
                resource_id=resource_id,
                resource_name=resource_name,
                previous_data=previous_state or {},
                new_data=new_state or {},
                user_id=user_id,
                ip_address=ip_address,
            )
        elif action == AuditActionEnum.DELETE:
            audit_service.audit_delete(
                resource_type=resource_type,
                resource_id=resource_id,
                resource_name=resource_name,
                resource_data=audit_details,
                user_id=user_id,
                ip_address=ip_address,
            )
        elif action in [
            AuditActionEnum.LOGIN,
            AuditActionEnum.LOGOUT,
            AuditActionEnum.LOGIN_FAILED,
            AuditActionEnum.TOKEN_REFRESH,
        ]:
            # Extract reason from audit_details if present
            reason = audit_details.get("reason") if audit_details else None
            audit_service.audit_authentication(
                action=action,
                user_id=user_id,
                ip_address=ip_address,
                success=success,
                reason=reason,
            )
        elif action in [AuditActionEnum.ACCESS_GRANTED, AuditActionEnum.ACCESS_DENIED]:
            # Extract access details
            access_type = audit_details.get("access_type", "unknown") if audit_details else "unknown"
            reason = audit_details.get("reason") if audit_details else None
            granted = action == AuditActionEnum.ACCESS_GRANTED

            audit_service.audit_access(
                resource_type=resource_type,
                resource_id=resource_id,
                resource_name=resource_name,
                access_type=access_type,
                granted=granted,
                user_id=user_id,
                ip_address=ip_address,
                reason=reason,
            )
        elif action in [
            AuditActionEnum.WORKFLOW_STARTED,
            AuditActionEnum.WORKFLOW_COMPLETED,
            AuditActionEnum.WORKFLOW_FAILED,
        ]:
            audit_service.audit_workflow(
                workflow_id=resource_id,
                workflow_type=audit_details.get("workflow_type", "UNKNOWN") if audit_details else "UNKNOWN",
                action=action,
                user_id=user_id,
                status=audit_details.get("status") if audit_details else None,
                error=audit_details.get("error") if audit_details else None,
                ip_address=ip_address,
            )
        else:
            # Generic audit for any other action
            from budapp.audit_ops.schemas import AuditRecordCreate

            audit_data = AuditRecordCreate(
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                resource_name=resource_name,
                user_id=user_id,
                ip_address=ip_address,
                details=audit_details,
                previous_state=previous_state,
                new_state=new_state,
                timestamp=datetime.now(timezone.utc),
            )
            audit_service.create_audit_record(audit_data)

        logger.debug(
            f"Audit logged: action={action}, resource_type={resource_type}, "
            f"resource_id={resource_id}, user_id={user_id}, success={success}"
        )

    except Exception as e:
        # Log the error but don't fail the main operation
        logger.error(
            f"Failed to log audit event: {e}. Action={action}, ResourceType={resource_type}, ResourceId={resource_id}"
        )
        # Don't raise - we don't want audit failures to break the main operation


def log_audit_async(
    session: Session,
    action: AuditActionEnum,
    resource_type: AuditResourceTypeEnum,
    resource_id: Optional[UUID] = None,
    resource_name: Optional[str] = None,
    user_id: Optional[UUID] = None,
    details: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None,
    previous_state: Optional[Dict[str, Any]] = None,
    new_state: Optional[Dict[str, Any]] = None,
    success: bool = True,
) -> None:
    """Async wrapper for audit logging that can be used with background tasks.

    This is the same as log_audit but designed to be used with FastAPI BackgroundTasks
    for non-blocking audit logging when performance is critical.

    Example usage:
        ```python
        from fastapi import BackgroundTasks
        from budapp.audit_ops.audit_logger import log_audit_async


        async def create_endpoint(
            session: Session,
            endpoint_data: dict,
            current_user_id: UUID,
            request: Request,
            background_tasks: BackgroundTasks,
        ):
            # Create endpoint
            endpoint = await crud.create_endpoint(endpoint_data)

            # Log audit in background (non-blocking)
            background_tasks.add_task(
                log_audit_async,
                session=session,
                action=AuditActionEnum.CREATE,
                resource_type=AuditResourceTypeEnum.ENDPOINT,
                resource_id=endpoint.id,
                resource_name=endpoint.name,
                user_id=current_user_id,
                details={"endpoint_name": endpoint.name},
                request=request,
            )

            return endpoint
        ```
    """
    # Simply call the synchronous version
    # FastAPI will handle running this in the background
    log_audit(
        session=session,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_name=resource_name,
        user_id=user_id,
        details=details,
        request=request,
        previous_state=previous_state,
        new_state=new_state,
        success=success,
    )

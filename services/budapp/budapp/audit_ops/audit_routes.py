"""API routes for audit trail functionality.

This module provides RESTful API endpoints for querying audit records.
Note: These routes are primarily for internal use and admin access.
Creating audit records should be done through the service layer, not via API.
"""

from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from budapp.audit_ops.schemas import (
    AuditRecordFilter,
    AuditRecordListResponse,
    AuditRecordResponse,
    AuditSummaryResponse,
)
from budapp.audit_ops.services import AuditService
from budapp.commons.constants import AuditActionEnum, AuditResourceTypeEnum, PermissionEnum
from budapp.commons.dependencies import get_current_active_user, get_session
from budapp.commons.permission_handler import require_permissions
from budapp.commons.schemas.pagination import PaginationQuery
from budapp.user_ops.models import User


audit_router = APIRouter(prefix="/audit", tags=["Audit"])


@audit_router.get(
    "/records",
    response_model=AuditRecordListResponse,
    summary="Get audit records",
    description="Retrieve paginated audit records with optional filtering",
)
@require_permissions(permissions=[PermissionEnum.ADMIN_ACCESS])
async def get_audit_records(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    pagination: Annotated[PaginationQuery, Depends()],
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    actioned_by: Optional[UUID] = Query(None, description="Filter by admin/user who performed action on behalf"),
    action: Optional[AuditActionEnum] = Query(None, description="Filter by action type"),
    resource_type: Optional[AuditResourceTypeEnum] = Query(None, description="Filter by resource type"),
    resource_id: Optional[UUID] = Query(None, description="Filter by resource ID"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date (inclusive)"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date (inclusive)"),
    ip_address: Optional[str] = Query(None, description="Filter by IP address"),
):
    """Get audit records with optional filtering and pagination.

    This endpoint requires admin access and returns audit records based on the provided filters.
    """
    try:
        service = AuditService(session)

        # Build filter parameters
        filter_params = AuditRecordFilter(
            user_id=user_id,
            actioned_by=actioned_by,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            start_date=start_date,
            end_date=end_date,
            ip_address=ip_address,
        )

        # Get audit records
        records, total = service.get_audit_records(
            filter_params=filter_params,
            offset=pagination.offset,
            limit=pagination.limit,
        )

        return AuditRecordListResponse(
            success=True,
            message="Audit records retrieved successfully",
            data=records,
            total=total,
            offset=pagination.offset,
            limit=pagination.limit,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve audit records: {str(e)}"
        )


@audit_router.get(
    "/records/{audit_id}",
    response_model=AuditRecordResponse,
    summary="Get audit record by ID",
    description="Retrieve a specific audit record by its ID",
)
@require_permissions(permissions=[PermissionEnum.ADMIN_ACCESS])
async def get_audit_record(
    audit_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Get a specific audit record by ID.

    This endpoint requires admin access and returns detailed information about a single audit record.
    """
    try:
        service = AuditService(session)

        # Get the audit record
        record = service.data_manager.get_audit_record_by_id(audit_id=audit_id, include_user=True)

        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Audit record with ID {audit_id} not found"
            )

        # Convert to response schema
        from budapp.audit_ops.schemas import AuditRecordEntry

        entry = AuditRecordEntry.model_validate(record)
        if record.user:
            entry.user_email = record.user.email
            entry.user_name = record.user.name
        if record.actioned_by_user:
            entry.actioned_by_email = record.actioned_by_user.email
            entry.actioned_by_name = record.actioned_by_user.name

        return AuditRecordResponse(
            success=True,
            message="Audit record retrieved successfully",
            data=entry,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve audit record: {str(e)}"
        )


@audit_router.get(
    "/user/{user_id}",
    response_model=AuditRecordListResponse,
    summary="Get audit records for a user",
    description="Retrieve audit records for a specific user",
)
@require_permissions(permissions=[PermissionEnum.ADMIN_ACCESS])
async def get_user_audit_records(
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    pagination: Annotated[PaginationQuery, Depends()],
    action: Optional[AuditActionEnum] = Query(None, description="Filter by action type"),
    resource_type: Optional[AuditResourceTypeEnum] = Query(None, description="Filter by resource type"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
):
    """Get audit records for a specific user.

    This endpoint requires admin access unless the user is querying their own audit records.
    """
    # Allow users to view their own audit records
    if user_id != current_user.id and PermissionEnum.ADMIN_ACCESS not in current_user.permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only view your own audit records")

    try:
        service = AuditService(session)

        # Get user's audit records
        records, total = service.data_manager.get_audit_records(
            user_id=user_id,
            offset=pagination.offset,
            limit=pagination.limit,
            start_date=start_date,
            end_date=end_date,
            action=action,
            resource_type=resource_type,
        )

        # Convert to response schemas
        from budapp.audit_ops.schemas import AuditRecordEntry

        entries = []
        for record in records:
            entry = AuditRecordEntry.model_validate(record)
            if record.user:
                entry.user_email = record.user.email
                entry.user_name = record.user.name
            if record.actioned_by_user:
                entry.actioned_by_email = record.actioned_by_user.email
                entry.actioned_by_name = record.actioned_by_user.name
            entries.append(entry)

        return AuditRecordListResponse(
            success=True,
            message=f"Audit records for user {user_id} retrieved successfully",
            data=entries,
            total=total,
            offset=pagination.offset,
            limit=pagination.limit,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve user audit records: {str(e)}",
        )


@audit_router.get(
    "/resource/{resource_type}/{resource_id}",
    response_model=AuditRecordListResponse,
    summary="Get audit records for a resource",
    description="Retrieve audit records for a specific resource",
)
@require_permissions(permissions=[PermissionEnum.ADMIN_ACCESS])
async def get_resource_audit_records(
    resource_type: AuditResourceTypeEnum,
    resource_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    pagination: Annotated[PaginationQuery, Depends()],
):
    """Get audit records for a specific resource.

    This endpoint requires admin access and returns all audit records related to a specific resource.
    """
    try:
        service = AuditService(session)

        # Get resource's audit records
        records, total = service.data_manager.get_audit_records(
            resource_type=resource_type,
            resource_id=resource_id,
            offset=pagination.offset,
            limit=pagination.limit,
            include_user=True,
        )

        # Convert to response schemas
        from budapp.audit_ops.schemas import AuditRecordEntry

        entries = []
        for record in records:
            entry = AuditRecordEntry.model_validate(record)
            if record.user:
                entry.user_email = record.user.email
                entry.user_name = record.user.name
            if record.actioned_by_user:
                entry.actioned_by_email = record.actioned_by_user.email
                entry.actioned_by_name = record.actioned_by_user.name
            entries.append(entry)

        return AuditRecordListResponse(
            success=True,
            message=f"Audit records for {resource_type} {resource_id} retrieved successfully",
            data=entries,
            total=total,
            offset=pagination.offset,
            limit=pagination.limit,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve resource audit records: {str(e)}",
        )


@audit_router.get(
    "/summary",
    response_model=AuditSummaryResponse,
    summary="Get audit summary",
    description="Retrieve summary statistics for audit records",
)
@require_permissions(permissions=[PermissionEnum.ADMIN_ACCESS])
async def get_audit_summary(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    start_date: Optional[datetime] = Query(None, description="Start date for summary"),
    end_date: Optional[datetime] = Query(None, description="End date for summary"),
):
    """Get summary statistics for audit records.

    This endpoint requires admin access and returns aggregated statistics about audit records.
    """
    try:
        service = AuditService(session)

        # Get audit summary
        summary = service.get_audit_summary(
            start_date=start_date,
            end_date=end_date,
        )

        return AuditSummaryResponse(
            success=True,
            message="Audit summary retrieved successfully",
            data=summary,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve audit summary: {str(e)}"
        )


@audit_router.get(
    "/records/{audit_id}/verify",
    summary="Verify audit record integrity",
    description="Verify the integrity of a specific audit record using its hash",
)
@require_permissions(permissions=[PermissionEnum.ADMIN_ACCESS])
async def verify_audit_record(
    audit_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Verify the integrity of an audit record.

    This endpoint requires admin access and checks if the audit record
    has been tampered with by verifying its hash.
    """
    try:
        service = AuditService(session)

        # Verify the audit record
        is_valid, message = service.verify_audit_record_integrity(audit_id)

        return {
            "success": True,
            "audit_id": str(audit_id),
            "is_valid": is_valid,
            "message": message,
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to verify audit record: {str(e)}"
        )


@audit_router.post(
    "/verify-batch",
    summary="Verify multiple audit records",
    description="Verify the integrity of multiple audit records",
)
@require_permissions(permissions=[PermissionEnum.ADMIN_ACCESS])
async def verify_audit_batch(
    audit_ids: List[UUID],
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Verify the integrity of multiple audit records.

    This endpoint requires admin access and checks multiple audit records
    for tampering.
    """
    try:
        service = AuditService(session)

        # Verify the batch
        results = service.verify_batch_integrity(audit_ids)

        # Format results
        verification_results = []
        for audit_id, (is_valid, message) in results.items():
            verification_results.append(
                {
                    "audit_id": str(audit_id),
                    "is_valid": is_valid,
                    "message": message,
                }
            )

        # Calculate summary statistics
        total_checked = len(results)
        valid_count = sum(1 for _, (is_valid, _) in results.items() if is_valid)
        invalid_count = total_checked - valid_count

        return {
            "success": True,
            "summary": {
                "total_checked": total_checked,
                "valid_count": valid_count,
                "invalid_count": invalid_count,
            },
            "results": verification_results,
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to verify audit records: {str(e)}"
        )


@audit_router.get(
    "/find-tampered",
    summary="Find potentially tampered audit records",
    description="Search for audit records that may have been tampered with",
)
@require_permissions(permissions=[PermissionEnum.ADMIN_ACCESS])
async def find_tampered_records(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    start_date: Optional[datetime] = Query(None, description="Start date for search"),
    end_date: Optional[datetime] = Query(None, description="End date for search"),
    limit: int = Query(100, description="Maximum number of records to check", le=1000),
):
    """Find audit records that may have been tampered with.

    This endpoint requires admin access and searches for audit records
    with hash mismatches, indicating potential tampering.
    """
    try:
        service = AuditService(session)

        # Find tampered records
        tampered = service.find_tampered_records(
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

        return {
            "success": True,
            "message": f"Checked {limit} records for tampering",
            "tampered_count": len(tampered),
            "tampered_records": tampered,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search for tampered records: {str(e)}",
        )

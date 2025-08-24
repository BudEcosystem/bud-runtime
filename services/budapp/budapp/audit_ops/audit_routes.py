"""API routes for audit trail functionality.

This module provides RESTful API endpoints for querying audit records.
Note: These routes are primarily for internal use and admin access.
Creating audit records should be done through the service layer, not via API.
"""

from datetime import datetime, timezone
from typing import Annotated, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from budapp.audit_ops.export_utils import generate_csv_from_audit_records, generate_export_filename
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
from budapp.user_ops.models import User


audit_router = APIRouter(prefix="/audit", tags=["Audit"])


@audit_router.get(
    "/records",
    summary="Get audit records",
    description="Retrieve paginated audit records with optional filtering or export as CSV",
)
async def get_audit_records(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 10,
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    actioned_by: Optional[UUID] = Query(None, description="Filter by admin/user who performed action on behalf"),
    action: Optional[AuditActionEnum] = Query(None, description="Filter by action type"),
    resource_type: Optional[AuditResourceTypeEnum] = Query(None, description="Filter by resource type"),
    resource_id: Optional[UUID] = Query(None, description="Filter by resource ID"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date (inclusive)"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date (inclusive)"),
    ip_address: Optional[str] = Query(None, description="Filter by IP address"),
    export_csv: bool = Query(False, description="Export results as CSV file"),
):
    """Get audit records with optional filtering and pagination.

    For CLIENT users, only their own audit records are returned.
    For ADMIN users, all audit records are accessible based on the provided filters.
    If export_csv is true, returns a CSV file download instead of JSON response.
    """
    try:
        service = AuditService(session)

        # For CLIENT users, force filter by their user_id
        from budapp.commons.constants import UserTypeEnum

        if current_user.user_type == UserTypeEnum.CLIENT.value:
            user_id = current_user.id

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

        # For CSV export, fetch all matching records (with a reasonable limit)
        if export_csv:
            # Set a higher limit for CSV exports
            export_limit = 10000  # Reasonable limit to prevent memory issues
            records, total = service.get_audit_records(
                filter_params=filter_params,
                offset=0,
                limit=export_limit,
            )

            # Generate CSV content
            csv_content = generate_csv_from_audit_records(records, include_user_info=True)

            # Generate filename with timestamp
            filename = generate_export_filename(prefix="audit_export", extension="csv")

            # Return CSV response
            return Response(
                content=csv_content,
                media_type="text/csv",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Content-Type": "text/csv; charset=utf-8",
                },
            )

        # Regular JSON response
        else:
            # Calculate offset from page and limit
            offset = (page - 1) * limit

            # Get audit records
            records, total = service.get_audit_records(
                filter_params=filter_params,
                offset=offset,
                limit=limit,
            )

            return AuditRecordListResponse(
                message="Audit records retrieved successfully",
                data=records,
                page=page,
                limit=limit,
                total_record=total,
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
async def get_audit_record(
    audit_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
):
    """Get a specific audit record by ID.

    For CLIENT users, only their own audit records can be accessed.
    For ADMIN users, all audit records are accessible.
    """
    try:
        service = AuditService(session)

        # Get the audit record
        record = service.data_manager.get_audit_record_by_id(audit_id=audit_id, include_user=True)

        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Audit record with ID {audit_id} not found"
            )

        # Check if CLIENT user is trying to access another user's audit record
        from budapp.commons.constants import UserTypeEnum

        if current_user.user_type == UserTypeEnum.CLIENT.value and record.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="You can only access your own audit records"
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
    "/summary",
    response_model=AuditSummaryResponse,
    summary="Get audit summary",
    description="Retrieve summary statistics for audit records",
)
async def get_audit_summary(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[Session, Depends(get_session)],
    start_date: Optional[datetime] = Query(None, description="Start date for summary"),
    end_date: Optional[datetime] = Query(None, description="End date for summary"),
):
    """Get summary statistics for audit records.

    For CLIENT users, only their own audit records are included in the summary.
    For ADMIN users, all audit records are included in the summary.
    """
    try:
        service = AuditService(session)

        # For CLIENT users, filter by their user_id
        from budapp.commons.constants import UserTypeEnum

        user_id = None
        if current_user.user_type == UserTypeEnum.CLIENT.value:
            user_id = current_user.id

        # Get audit summary
        summary = service.get_audit_summary(
            start_date=start_date,
            end_date=end_date,
            user_id=user_id,
        )

        return AuditSummaryResponse(
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
@require_permissions(permissions=[PermissionEnum.USER_MANAGE])
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
@require_permissions(permissions=[PermissionEnum.USER_MANAGE])
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
@require_permissions(permissions=[PermissionEnum.USER_MANAGE])
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

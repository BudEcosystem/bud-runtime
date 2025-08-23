"""Pydantic schemas for audit trail functionality.

This module defines the schemas for validating and serializing
audit trail data for API requests and responses.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.types import UUID4

from budapp.commons.constants import AuditActionEnum, AuditResourceTypeEnum
from budapp.commons.schemas import PaginatedSuccessResponse, SuccessResponse


class AuditRecordBase(BaseModel):
    """Base schema for audit record data.

    Contains common fields used across different audit record operations.
    """

    action: AuditActionEnum = Field(..., description="Type of action performed")
    resource_type: AuditResourceTypeEnum = Field(..., description="Type of resource affected")
    resource_id: Optional[UUID4] = Field(None, description="ID of the affected resource")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional context about the action")
    ip_address: Optional[str] = Field(
        None, description="IP address from which the action was performed", max_length=45
    )

    @field_validator("ip_address")
    @classmethod
    def validate_ip_address(cls, v: Optional[str]) -> Optional[str]:
        """Validate IP address format."""
        if v is None:
            return v
        try:
            import ipaddress

            ipaddress.ip_address(v)
        except ValueError:
            raise ValueError(f"'{v}' is not a valid IP address.")
        return v


class AuditRecordCreate(AuditRecordBase):
    """Schema for creating a new audit record.

    Used internally by the system to create audit entries.
    """

    user_id: Optional[UUID4] = Field(None, description="ID of the user who performed the action")
    actioned_by: Optional[UUID4] = Field(
        None, description="ID of the admin/user who performed the action on behalf of another user"
    )
    timestamp: Optional[datetime] = Field(None, description="When the action occurred (defaults to current time)")
    previous_state: Optional[Dict[str, Any]] = Field(None, description="State of the resource before the action")
    new_state: Optional[Dict[str, Any]] = Field(None, description="State of the resource after the action")


class AuditRecordEntry(BaseModel):
    """Schema for a single audit record in responses.

    Represents a complete audit record as returned from the database.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID4 = Field(..., description="Unique identifier for the audit record")
    user_id: Optional[UUID4] = Field(None, description="ID of the user who performed the action")
    actioned_by: Optional[UUID4] = Field(
        None, description="ID of the admin/user who performed the action on behalf of another user"
    )
    action: str = Field(..., description="Type of action performed")
    resource_type: str = Field(..., description="Type of resource affected")
    resource_id: Optional[UUID4] = Field(None, description="ID of the affected resource")
    timestamp: datetime = Field(..., description="When the action occurred")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional context about the action")
    ip_address: Optional[str] = Field(None, description="IP address from which the action was performed")
    previous_state: Optional[Dict[str, Any]] = Field(None, description="State of the resource before the action")
    new_state: Optional[Dict[str, Any]] = Field(None, description="State of the resource after the action")
    record_hash: str = Field(..., description="SHA256 hash of record data for integrity verification")
    created_at: datetime = Field(..., description="When the audit record was created")

    # Optional user information if expanded
    user_email: Optional[str] = Field(None, description="Email of the user who performed the action")
    user_name: Optional[str] = Field(None, description="Name of the user who performed the action")
    actioned_by_email: Optional[str] = Field(
        None, description="Email of the admin/user who performed the action on behalf"
    )
    actioned_by_name: Optional[str] = Field(
        None, description="Name of the admin/user who performed the action on behalf"
    )


class AuditRecordFilter(BaseModel):
    """Schema for filtering audit records in queries."""

    user_id: Optional[UUID4] = Field(None, description="Filter by user ID")
    actioned_by: Optional[UUID4] = Field(None, description="Filter by admin/user who performed action on behalf")
    action: Optional[AuditActionEnum] = Field(None, description="Filter by action type")
    resource_type: Optional[AuditResourceTypeEnum] = Field(None, description="Filter by resource type")
    resource_id: Optional[UUID4] = Field(None, description="Filter by resource ID")
    start_date: Optional[datetime] = Field(None, description="Filter by start date (inclusive)")
    end_date: Optional[datetime] = Field(None, description="Filter by end date (inclusive)")
    ip_address: Optional[str] = Field(None, description="Filter by IP address")


class AuditRecordResponse(SuccessResponse):
    """Response schema for a single audit record."""

    data: AuditRecordEntry = Field(..., description="The audit record data")
    object: str = Field(default="audit.record", description="Object type identifier")


class AuditRecordListResponse(PaginatedSuccessResponse):
    """Response schema for a paginated list of audit records."""

    data: List[AuditRecordEntry] = Field(default=[], description="List of audit records")
    object: str = Field(default="audit.record.list", description="Object type identifier")


class AuditSummaryResponse(SuccessResponse):
    """Response schema for audit summary statistics."""

    data: Dict[str, Any] = Field(..., description="Summary statistics data")
    object: str = Field(default="audit.summary", description="Object type identifier")

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Audit summary retrieved successfully",
                "data": {
                    "total_records": 1000,
                    "unique_users": 50,
                    "most_common_actions": [{"action": "read", "count": 500}, {"action": "update", "count": 300}],
                    "most_active_users": [{"user_id": "123e4567-e89b-12d3-a456-426614174000", "count": 100}],
                    "date_range": {"start": "2024-01-01T00:00:00Z", "end": "2024-01-31T23:59:59Z"},
                },
                "object": "audit.summary",
            }
        }

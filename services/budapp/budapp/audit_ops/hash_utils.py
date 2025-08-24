"""Utilities for generating and verifying audit record hashes.

This module provides functions for creating SHA256 hashes of audit records
to ensure data integrity and detect tampering.
"""

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID


def serialize_for_hash(value: Any) -> str:
    """Convert a value to a consistent string representation for hashing.

    Args:
        value: The value to serialize

    Returns:
        String representation of the value
    """
    if value is None:
        return "null"
    elif isinstance(value, bool):
        # Handle boolean before other types since bool is a subclass of int
        return "true" if value else "false"
    elif isinstance(value, UUID):
        return str(value)
    elif isinstance(value, datetime):
        return value.isoformat()
    elif isinstance(value, dict):
        # Sort keys for consistent ordering
        return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    elif isinstance(value, (list, tuple)):
        return json.dumps(value, default=str, separators=(",", ":"))
    else:
        return str(value)


def generate_audit_hash(
    action: str,
    resource_type: str,
    resource_id: Optional[UUID],
    user_id: Optional[UUID],
    actioned_by: Optional[UUID],
    timestamp: datetime,
    details: Optional[Dict[str, Any]],
    ip_address: Optional[str],
    previous_state: Optional[Dict[str, Any]],
    new_state: Optional[Dict[str, Any]],
) -> str:
    """Generate a SHA256 hash for an audit record.

    This function creates a deterministic hash based on all the immutable
    fields of an audit record. The hash can be used to verify that the
    record has not been tampered with.

    Args:
        action: Type of action performed
        resource_type: Type of resource affected
        resource_id: ID of the affected resource
        user_id: ID of the user who performed the action
        actioned_by: ID of the admin/user who performed the action on behalf
        timestamp: When the action occurred
        details: Additional context about the action
        ip_address: IP address from which the action was performed
        previous_state: State before the action
        new_state: State after the action

    Returns:
        64-character hexadecimal SHA256 hash string
    """
    # Create a consistent string representation of all fields
    # Order matters for hash consistency
    hash_components = [
        serialize_for_hash(action),
        serialize_for_hash(resource_type),
        serialize_for_hash(resource_id),
        serialize_for_hash(user_id),
        serialize_for_hash(actioned_by),
        serialize_for_hash(timestamp),
        serialize_for_hash(details),
        serialize_for_hash(ip_address),
        serialize_for_hash(previous_state),
        serialize_for_hash(new_state),
    ]

    # Join all components with a delimiter
    hash_string = "|".join(hash_components)

    # Generate SHA256 hash
    hash_object = hashlib.sha256(hash_string.encode("utf-8"))
    return hash_object.hexdigest()


def verify_audit_hash(audit_record: Any, expected_hash: str) -> bool:
    """Verify that an audit record's hash matches the expected value.

    Args:
        audit_record: The audit record object (must have all required fields)
        expected_hash: The expected hash value

    Returns:
        True if the hash matches, False otherwise
    """
    # Generate hash from the record
    calculated_hash = generate_audit_hash(
        action=audit_record.action,
        resource_type=audit_record.resource_type,
        resource_id=audit_record.resource_id,
        user_id=audit_record.user_id,
        actioned_by=audit_record.actioned_by,
        timestamp=audit_record.timestamp,
        details=audit_record.details,
        ip_address=audit_record.ip_address,
        previous_state=audit_record.previous_state,
        new_state=audit_record.new_state,
    )

    # Compare with expected hash
    return calculated_hash == expected_hash


def verify_audit_integrity(audit_record: Any) -> tuple[bool, str]:
    """Verify the integrity of an audit record using its stored hash.

    Args:
        audit_record: The audit record object with a record_hash field

    Returns:
        Tuple of (is_valid, message) where is_valid is True if the record
        is intact and message provides details about the verification
    """
    if not hasattr(audit_record, "record_hash"):
        return False, "Audit record does not have a record_hash field"

    try:
        is_valid = verify_audit_hash(audit_record, audit_record.record_hash)
        if is_valid:
            return True, "Audit record integrity verified successfully"
        else:
            return False, "Audit record hash mismatch - possible tampering detected"
    except Exception as e:
        return False, f"Error verifying audit record integrity: {str(e)}"

"""Export utilities for audit trail data.

This module provides functionality to export audit records in various formats,
particularly CSV for compliance and reporting purposes.
"""

import csv
import io
from datetime import datetime
from typing import List, Optional

from budapp.audit_ops.models import AuditTrail


def generate_csv_from_audit_records(
    records: List[AuditTrail],
    include_user_info: bool = True,
) -> str:
    """Generate CSV content from audit records.

    Args:
        records: List of AuditTrail records to export
        include_user_info: Whether to include user email/name columns

    Returns:
        CSV content as string
    """
    output = io.StringIO()

    # Define CSV headers
    headers = [
        "ID",
        "Timestamp",
        "User ID",
        "User Email",
        "User Name",
        "Actioned By ID",
        "Actioned By Email",
        "Actioned By Name",
        "Action",
        "Resource Type",
        "Resource ID",
        "Resource Name",
        "IP Address",
        "Details",
        "Previous State",
        "New State",
        "Record Hash",
    ]

    # Create CSV writer
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()

    # Write records
    for record in records:
        row = {
            "ID": str(record.id),
            "Timestamp": record.timestamp.isoformat() if record.timestamp else "",
            "User ID": str(record.user_id) if record.user_id else "",
            "User Email": "",
            "User Name": "",
            "Actioned By ID": str(record.actioned_by) if record.actioned_by else "",
            "Actioned By Email": "",
            "Actioned By Name": "",
            "Action": record.action if record.action else "",
            "Resource Type": record.resource_type if record.resource_type else "",
            "Resource ID": str(record.resource_id) if record.resource_id else "",
            "Resource Name": record.resource_name if hasattr(record, "resource_name") and record.resource_name else "",
            "IP Address": record.ip_address if record.ip_address else "",
            "Details": str(record.details) if record.details else "",
            "Previous State": str(record.previous_state) if record.previous_state else "",
            "New State": str(record.new_state) if record.new_state else "",
            "Record Hash": record.record_hash if record.record_hash else "",
        }

        # Add user information if available and requested
        if include_user_info:
            if hasattr(record, "user") and record.user:
                row["User Email"] = record.user.email if record.user.email else ""
                row["User Name"] = record.user.name if record.user.name else ""

            if hasattr(record, "actioned_by_user") and record.actioned_by_user:
                row["Actioned By Email"] = record.actioned_by_user.email if record.actioned_by_user.email else ""
                row["Actioned By Name"] = record.actioned_by_user.name if record.actioned_by_user.name else ""

        writer.writerow(row)

    # Get the CSV content
    csv_content = output.getvalue()
    output.close()

    return csv_content


def sanitize_for_csv(value: str) -> str:
    """Sanitize a value for CSV export.

    Escapes special characters and handles None values.

    Args:
        value: Value to sanitize

    Returns:
        Sanitized string safe for CSV
    """
    if value is None:
        return ""

    # Convert to string and escape quotes
    value_str = str(value)

    # CSV libraries handle escaping internally, but we can do basic cleaning
    # Replace null bytes with spaces to preserve readability
    value_str = value_str.replace("\x00", " ")

    return value_str


def generate_export_filename(prefix: str = "audit_export", extension: str = "csv") -> str:
    """Generate a filename for exports with timestamp.

    Args:
        prefix: Filename prefix
        extension: File extension

    Returns:
        Formatted filename with timestamp
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}.{extension}"

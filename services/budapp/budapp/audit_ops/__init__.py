"""Audit operations module for tracking user actions and system events.

This module provides functionality for creating and querying audit trails
to track all user actions and system events for compliance and security purposes.
"""

from .models import AuditTrail


__all__ = ["AuditTrail"]

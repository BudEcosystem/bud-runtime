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

"""Initialization module for the `commons` subpackage. Contains common utilities, configurations, constants, and helper functions that are shared across the project."""

# SQL validation utilities for preventing SQL injection
from .sql_validators import (
    ClusterUUID,
    ClusterUUIDList,
    OptionalSafeIdentifierList,
    SafeIdentifier,
    SafeIdentifierList,
    safe_sql_list,
    validate_cluster_id,
    validate_identifier,
    validate_identifiers,
)


__all__ = [
    # SQL validation functions
    "validate_identifier",
    "validate_identifiers",
    "validate_cluster_id",
    "safe_sql_list",
    # Pydantic validated types
    "SafeIdentifier",
    "SafeIdentifierList",
    "ClusterUUID",
    "ClusterUUIDList",
    "OptionalSafeIdentifierList",
]

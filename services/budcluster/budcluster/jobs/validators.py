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

"""Validation for Helm deployment job configurations."""

from __future__ import annotations

import re
from typing import Any


# Allowed chart source patterns
ALLOWED_CHART_PATTERNS = [
    r"^oci://[\w\-\.]+(/[\w\-\.]+)+$",  # OCI registry (oci://registry.example.com/charts/app)
    r"^https://[\w\-\.]+(/[\w\-\.]+)*$",  # HTTPS chart repo
    r"^charts/[\w\-]+$",  # Local bundled charts
]

# Allowed git repository URL patterns
ALLOWED_GIT_PATTERNS = [
    r"^https://[\w\-\.]+(/[\w\-\.]+)+\.git$",  # HTTPS git URL (https://github.com/org/repo.git)
    r"^https://github\.com/[\w\-]+/[\w\-\.]+$",  # GitHub short URL without .git
]

# Helm values keys that could escalate privileges
BLOCKED_VALUES_KEYS = frozenset(
    {
        "hostNetwork",
        "hostPID",
        "hostIPC",
        "privileged",
    }
)


def validate_helm_config(config: dict[str, Any]) -> list[str]:
    """Validate a Helm deploy job config for security and correctness.

    Args:
        config: Job config dict containing chart_ref, values, etc.

    Returns:
        List of error strings. Empty list means valid.
    """
    errors: list[str] = []

    # Validate chart_ref or git_repo (at least one must be provided)
    chart_ref = config.get("chart_ref", "")
    git_repo = config.get("git_repo", "")

    if not chart_ref and not git_repo:
        errors.append("Either chart_ref or git_repo is required")
    elif git_repo:
        if not any(re.match(pattern, git_repo) for pattern in ALLOWED_GIT_PATTERNS):
            errors.append(
                f"Git repository '{git_repo}' does not match any allowed pattern. "
                "Allowed: https://*.git or https://github.com/org/repo"
            )
    elif not any(re.match(pattern, chart_ref) for pattern in ALLOWED_CHART_PATTERNS):
        errors.append(
            f"Chart reference '{chart_ref}' does not match any allowed pattern. "
            "Allowed: oci://, https://, or charts/ (local)"
        )

    # Validate release_name if present
    release_name = config.get("release_name", "")
    if release_name and not re.match(r"^[a-z0-9][a-z0-9\-]*$", release_name):
        errors.append(f"Release name '{release_name}' is invalid. Must be lowercase alphanumeric with hyphens.")

    # Validate values for blocked security keys
    values = config.get("values", {})
    if isinstance(values, dict):
        _check_blocked_keys(values, "", errors)

    return errors


def _check_blocked_keys(
    obj: dict[str, Any],
    path: str,
    errors: list[str],
) -> None:
    """Recursively check for blocked security keys in Helm values."""
    for key, value in obj.items():
        full_path = f"{path}.{key}" if path else key
        if key in BLOCKED_VALUES_KEYS:
            errors.append(f"Blocked security key in Helm values: {full_path}")
        if isinstance(value, dict):
            _check_blocked_keys(value, full_path, errors)

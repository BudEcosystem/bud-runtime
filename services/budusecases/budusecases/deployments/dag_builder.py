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

"""DAG builder for converting BudUseCases deployments into BudPipeline DAGs.

This module converts a use case deployment definition (template + component
selections + parameters) into a BudPipeline-compatible DAG (Directed Acyclic
Graph) dict that can be submitted for orchestrated execution.
"""

import re
from typing import Any

_PARAM_PATTERN = re.compile(r"^\{\{\s*params\.(\w+)\s*\}\}$")
"""Regex matching ``{{ params.XXX }}`` placeholders for deep substitution."""


def _resolve_values(values: dict[str, Any], parameters: dict[str, Any]) -> dict[str, Any]:
    """Resolve ``{{ params.XXX }}`` placeholders in a Helm values dict.

    Performs *deep* substitution: recurses into nested dicts and replaces
    string entries that exactly match the ``{{ params.XXX }}`` pattern with the
    corresponding value from *parameters*.

    Jinja2 step-reference expressions such as
    ``{{ steps.llm.outputs.endpoint_url }}`` are left untouched because the
    BudPipeline engine resolves those at execution time.

    Args:
        values: Helm chart values dict (may contain template placeholders).
        parameters: User-supplied deployment parameters keyed by name.

    Returns:
        A new dict with parameter placeholders resolved.
    """
    resolved: dict[str, Any] = {}
    for key, value in values.items():
        if isinstance(value, dict):
            resolved[key] = _resolve_values(value, parameters)
        elif isinstance(value, str):
            match = _PARAM_PATTERN.match(value)
            if match:
                param_name = match.group(1)
                if param_name in parameters:
                    resolved[key] = parameters[param_name]
                else:
                    # Parameter not provided -- keep the original template so
                    # the pipeline engine can raise a clear validation error.
                    resolved[key] = value
            else:
                resolved[key] = value
        else:
            resolved[key] = value
    return resolved


def build_deployment_dag(
    deployment_id: str,
    deployment_name: str,
    cluster_id: str,
    user_id: str,
    template: dict[str, Any],
    component_selections: dict[str, str],
    parameters: dict[str, Any] | None = None,
    access_config: dict[str, Any] | None = None,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Build a BudPipeline DAG dict from a use case deployment definition.

    The resulting DAG contains:
    * A cluster health-check step (step 0).
    * One deployment step per component in ``deployment_order``.
    * A final notification step.

    All steps are chained sequentially so that each component is deployed only
    after the previous one succeeds.

    Args:
        deployment_id: Unique deployment identifier.
        deployment_name: Human-readable deployment name (used in release names).
        cluster_id: Target cluster UUID string.
        user_id: User initiating the deployment.
        template: Template dict with ``components``, ``parameters``, and
            ``deployment_order`` keys (as stored in the database / loaded from
            YAML).
        component_selections: Mapping of component slot name to the selected
            component identifier (e.g. model name or chart ref override).
        parameters: Optional user-supplied deployment parameters used to
            resolve ``{{ params.XXX }}`` placeholders in Helm values.

    Returns:
        A dict conforming to the BudPipeline DAG schema, ready to be submitted
        via the pipeline API.
    """
    params = parameters or {}

    # ------------------------------------------------------------------
    # 1. Build component lookup
    # ------------------------------------------------------------------
    components: list[dict[str, Any]] = template.get("components", [])
    comp_lookup: dict[str, dict[str, Any]] = {comp["name"]: comp for comp in components}

    # ------------------------------------------------------------------
    # 2. Determine deployment order
    # ------------------------------------------------------------------
    deployment_order: list[str] = template.get(
        "deployment_order",
        [comp["name"] for comp in components],
    )

    # ------------------------------------------------------------------
    # 3. Generate steps
    # ------------------------------------------------------------------
    steps: list[dict[str, Any]] = []

    # Step 0: Cluster health check
    steps.append(
        {
            "id": "cluster_health",
            "name": "Cluster Health Check",
            "action": "cluster_health",
            "params": {"cluster_id": cluster_id},
            "depends_on": [],
        }
    )

    previous_step_id: str = "cluster_health"

    # Per-component deployment steps
    for comp_name in deployment_order:
        comp_def = comp_lookup.get(comp_name)
        if comp_def is None:
            continue

        # Resolve which concrete component was selected for this slot
        selected_component: str = component_selections.get(
            comp_name,
            comp_def.get("default_component", ""),
        )

        step_id = f"deploy_{comp_name}"

        if comp_def.get("type") == "helm":
            chart_config: dict[str, Any] = comp_def.get("chart") or {}
            chart_ref = chart_config.get("ref", "")
            git_repo = chart_config.get("git_repo", "")
            if not chart_ref and not git_repo:
                raise ValueError(
                    f"Helm component '{comp_name}' is missing chart.ref or chart.git_repo. "
                    "Ensure the template includes chart configuration."
                )

            step_params: dict[str, Any] = {
                "cluster_id": cluster_id,
                "release_name": f"{deployment_name}-{comp_name}",
                "namespace": f"usecase-{deployment_id[:8]}",
                "values": _resolve_values(chart_config.get("values", {}), params),
                "deployment_id": deployment_id,
            }
            if access_config:
                step_params["access_config"] = access_config

            if git_repo:
                step_params["git_repo"] = git_repo
                step_params["git_ref"] = chart_config.get("git_ref", "main")
                step_params["chart_subpath"] = chart_config.get("chart_subpath", ".")
            else:
                step_params["chart_ref"] = chart_ref
                step_params["chart_version"] = chart_config.get("version")

            step: dict[str, Any] = {
                "id": step_id,
                "name": f"Deploy {comp_name}",
                "action": "helm_deploy",
                "params": step_params,
                "depends_on": [previous_step_id],
            }
        else:
            # Model types (model, llm, embedder, reranker)
            model_step_params: dict[str, Any] = {
                "cluster_id": cluster_id,
                "model_id": selected_component,
                "endpoint_name": f"{deployment_name}-{comp_name}",
            }
            if project_id:
                model_step_params["project_id"] = project_id
            if params:
                model_step_params["parameters"] = params

            step = {
                "id": step_id,
                "name": f"Deploy {comp_name}",
                "action": "deployment_create",
                "params": model_step_params,
                "depends_on": [previous_step_id],
            }

        steps.append(step)
        previous_step_id = step_id

    # Final step: log completion (lightweight, no external dependency)
    steps.append(
        {
            "id": "notify_complete",
            "name": "Log Completion",
            "action": "log",
            "params": {
                "message": f"Use case '{deployment_name}' deployment complete",
                "level": "info",
            },
            "depends_on": [previous_step_id],
        }
    )

    # ------------------------------------------------------------------
    # 4. Assemble full DAG dict
    # ------------------------------------------------------------------
    # parameters must be a list of WorkflowParameter objects for the DAG schema
    dag_parameters: list[dict[str, Any]] = [
        {"name": "deployment_id", "type": "string", "required": False, "default": deployment_id},
        {"name": "user_id", "type": "string", "required": False, "default": user_id},
    ]

    dag: dict[str, Any] = {
        "name": f"usecase-{deployment_name}",
        "version": "1.0.0",
        "settings": {
            "timeout_seconds": 7200,
            "on_failure": "fail",
        },
        "steps": steps,
        "parameters": dag_parameters,
    }

    return dag

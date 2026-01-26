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

"""BudPipeline actions for guardrail deployment workflow."""

from typing import Any
from uuid import UUID

from sqlalchemy.orm import selectinload
from sqlalchemy.sql import select

from budapp.commons.constants import ScannerTypeEnum
from budapp.commons.db_utils import SessionMixin
from budapp.guardrails.crud import GuardrailsDeploymentDataManager
from budapp.guardrails.models import GuardrailProbe, GuardrailRule


class GuardrailPipelineActions(SessionMixin):
    """Pipeline action handlers for guardrail deployment.

    These actions are designed to be called from BudPipeline steps:
    - guardrail.validate: Validate deployment request
    - guardrail.identify_models: Identify models needing onboarding/deployment
    - guardrail.build_config: Build guardrail config with endpoint URLs
    - guardrail.save_deployment: Save deployment and update Redis cache
    """

    async def validate_deployment(
        self,
        profile_id: UUID | None,
        probe_selections: list[dict],
        cluster_id: UUID | None,
        credential_id: UUID | None,
    ) -> dict[str, Any]:
        """Validate deployment request and return validated data.

        Checks:
        - Model probes require cluster_id
        - Gated models require credential_id

        Returns:
            dict with 'success' bool, 'errors' list (if failed), or 'probe_selections' and 'model_probes' (if success)
        """
        errors = []
        data_manager = GuardrailsDeploymentDataManager(self.session)

        # Get probe IDs from selections
        probe_ids = [
            UUID(s["probe_id"]) if isinstance(s["probe_id"], str) else s["probe_id"] for s in probe_selections
        ]

        # Check for model probes (model_scanner or custom types)
        model_probes = await data_manager.get_model_probes_from_selections(probe_ids)

        if model_probes:
            if not cluster_id:
                errors.append("cluster_id required when deploying model-based probes")

            # Check gated models that need credentials
            gated_probes = []
            for probe in model_probes:
                # Eagerly load rules to check gated status
                stmt = (
                    select(GuardrailProbe)
                    .where(GuardrailProbe.id == probe.id)
                    .options(selectinload(GuardrailProbe.rules))
                )
                probe_with_rules = self.session.execute(stmt).scalar_one_or_none()
                if probe_with_rules and probe_with_rules.rules:
                    for rule in probe_with_rules.rules:
                        if rule.is_gated:
                            gated_probes.append(probe.name)
                            break

            if gated_probes and not credential_id:
                errors.append(f"credential_id required for gated models: {', '.join(gated_probes)}")

        if errors:
            return {"success": False, "errors": errors}

        return {
            "success": True,
            "probe_selections": probe_selections,
            "model_probes": [{"id": str(p.id), "name": p.name} for p in model_probes],
            "has_model_probes": len(model_probes) > 0,
        }

    async def identify_model_requirements(
        self,
        probe_selections: list[dict],
        cluster_id: UUID,
    ) -> dict[str, Any]:
        """Identify which models need onboarding and deployment.

        For each model-based probe:
        - If model_id is None, the model needs onboarding first
        - If model_id exists, check if already deployed to target cluster

        Returns:
            dict with 'models_to_onboard' and 'models_to_deploy' lists
        """
        data_manager = GuardrailsDeploymentDataManager(self.session)

        probe_ids = [
            UUID(s["probe_id"]) if isinstance(s["probe_id"], str) else s["probe_id"] for s in probe_selections
        ]
        model_probes = await data_manager.get_model_probes_from_selections(probe_ids)

        models_to_onboard = []
        models_to_deploy = []

        for probe in model_probes:
            # Load rules for this probe
            stmt = (
                select(GuardrailProbe).where(GuardrailProbe.id == probe.id).options(selectinload(GuardrailProbe.rules))
            )
            probe_with_rules = self.session.execute(stmt).scalar_one_or_none()

            if not probe_with_rules or not probe_with_rules.rules:
                continue

            # Model probes have a single rule with model info
            rule = probe_with_rules.rules[0]
            selection = next((s for s in probe_selections if str(s.get("probe_id")) == str(probe.id)), {})

            if rule.model_id is None:
                # Model not onboarded yet - needs onboarding first
                models_to_onboard.append(
                    {
                        "rule_id": str(rule.id),
                        "probe_id": str(probe.id),
                        "probe_name": probe.name,
                        "model_uri": rule.model_uri,
                        "provider_type": rule.model_provider_type,
                        "is_gated": rule.is_gated,
                        "cluster_config": selection.get("cluster_config_override"),
                    }
                )
            else:
                # Model is onboarded - needs deployment to cluster
                # TODO: Check if already deployed to target cluster via endpoint lookup
                models_to_deploy.append(
                    {
                        "rule_id": str(rule.id),
                        "probe_id": str(probe.id),
                        "probe_name": probe.name,
                        "model_id": str(rule.model_id),
                        "model_uri": rule.model_uri,
                        "cluster_config": selection.get("cluster_config_override"),
                    }
                )

        return {
            "models_to_onboard": models_to_onboard,
            "models_to_deploy": models_to_deploy,
            "total_models": len(models_to_onboard) + len(models_to_deploy),
        }

    async def build_guardrail_config(
        self,
        profile_id: UUID,
        rule_deployments: list[dict],
    ) -> dict[str, Any]:
        """Build guardrail configuration with deployed endpoint URLs.

        This creates the config structure to be stored in Redis guardrail_table:{profile_id}

        Args:
            profile_id: The guardrail profile ID
            rule_deployments: List of dicts with rule_id, endpoint_url, endpoint_id, endpoint_name

        Returns:
            dict with 'custom_rules', 'metadata_json', and 'rule_overrides_json'
        """
        metadata: dict[str, Any] = {}
        custom_rules: list[dict[str, Any]] = []
        rule_overrides: dict[str, dict[str, str]] = {}

        for rd in rule_deployments:
            rule_id = UUID(rd["rule_id"]) if isinstance(rd["rule_id"], str) else rd["rule_id"]
            rule = self.session.get(GuardrailRule, rule_id)

            if not rule:
                continue

            endpoint_url = rd.get("endpoint_url", "")
            endpoint_name = rd.get("endpoint_name", "")
            model_config = rule.model_config_json or {}

            if rule.scanner_type == ScannerTypeEnum.LLM.value:
                # LLM scanner uses /v1 endpoint for chat completions
                metadata["llm"] = {
                    "url": f"{endpoint_url}/v1",
                    "api_key_header": "Authorization",
                    "timeout_ms": 30000,
                }
                custom_rules.append(
                    {
                        "id": rule.uri,
                        "name": rule.name,
                        "description": rule.description,
                        "kind": "llm",
                        "scanner": "llm",
                        "scanner_config_json": {
                            "model_id": rule.model_uri,
                            "handler": "gpt_safeguard",
                            "handler_config": {
                                "output_format": "structured_json",
                                "policy": model_config.get("policy", {}),
                            },
                            "target_labels": model_config.get("target_labels", []),
                        },
                    }
                )
                # Add rule override for deployed endpoint name
                if endpoint_name:
                    rule_overrides[rule.uri] = {"model_id": endpoint_name}

            elif rule.scanner_type == ScannerTypeEnum.CLASSIFIER.value:
                # Classifier scanner uses direct endpoint
                metadata["latentbud"] = {
                    "url": endpoint_url,
                    "api_key_header": "Authorization",
                    "timeout_ms": 30000,
                }
                # Build head_mappings with default head_name
                head_mappings = model_config.get("head_mappings", [])
                if head_mappings:
                    # Ensure head_name is set to "default"
                    head_mappings = [
                        {"head_name": "default", "target_labels": hm.get("target_labels", [])} for hm in head_mappings
                    ]
                else:
                    head_mappings = [{"head_name": "default", "target_labels": []}]

                custom_rule: dict[str, Any] = {
                    "id": rule.uri,
                    "name": rule.name,
                    "description": rule.description,
                    "kind": "classifier",
                    "scanner": "latentbud",
                    "scanner_config_json": {
                        "model_id": rule.model_uri,
                        "head_mappings": head_mappings,
                    },
                }
                # Add post_processing_json if present
                if model_config.get("post_processing"):
                    custom_rule["post_processing_json"] = model_config["post_processing"]

                custom_rules.append(custom_rule)

                # Add rule override for deployed endpoint name
                if endpoint_name:
                    rule_overrides[rule.uri] = {"model_id": endpoint_name}

        return {
            "custom_rules": custom_rules,
            "metadata_json": metadata,
            "rule_overrides_json": rule_overrides,
        }

    async def get_deployment_progress(
        self,
        guardrail_deployment_id: UUID,
    ) -> dict[str, Any]:
        """Get overall deployment progress for a guardrail deployment.

        Progress is derived from the linked endpoint statuses.

        Returns:
            dict with progress info and endpoint status breakdown
        """
        from budapp.endpoint_ops.models import Endpoint

        data_manager = GuardrailsDeploymentDataManager(self.session)

        rule_deployments = await data_manager.get_rule_deployments_for_guardrail(
            guardrail_deployment_id=guardrail_deployment_id
        )

        if not rule_deployments:
            return {
                "progress_percentage": 100.0,
                "status": "no_models",
                "endpoints": [],
            }

        # Get endpoint statuses
        endpoint_statuses = []
        for rd in rule_deployments:
            endpoint = self.session.get(Endpoint, rd.endpoint_id)
            if endpoint:
                endpoint_statuses.append(
                    {
                        "endpoint_id": str(endpoint.id),
                        "endpoint_name": endpoint.name,
                        "status": endpoint.status.value if hasattr(endpoint.status, "value") else str(endpoint.status),
                        "rule_id": str(rd.rule_id),
                    }
                )

        # Calculate overall status from endpoints
        status_counts: dict[str, int] = {}
        for es in endpoint_statuses:
            status = es["status"]
            status_counts[status] = status_counts.get(status, 0) + 1

        total = len(endpoint_statuses)
        running = status_counts.get("running", 0)
        failed = status_counts.get("failure", 0)
        deploying = status_counts.get("deploying", 0)

        # Calculate progress
        progress = ((running + failed) / total) * 100 if total > 0 else 100.0

        # Determine overall status
        if failed > 0:
            overall_status = "partial_failure" if running > 0 else "failed"
        elif running == total:
            overall_status = "running"
        elif deploying > 0:
            overall_status = "deploying"
        else:
            overall_status = "pending"

        return {
            "progress_percentage": round(progress, 2),
            "status": overall_status,
            "status_breakdown": status_counts,
            "total_endpoints": total,
            "endpoints": endpoint_statuses,
        }

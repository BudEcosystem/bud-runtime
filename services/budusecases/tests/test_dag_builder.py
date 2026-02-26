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

"""Tests for the DAG builder module.

Validates that ``build_deployment_dag`` correctly converts use case deployment
definitions (template + component selections + parameters) into BudPipeline-
compatible DAG dicts.
"""

from typing import Any
from uuid import uuid4

from budusecases.deployments.dag_builder import build_deployment_dag

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ids() -> tuple[str, str, str, str]:
    """Return (deployment_id, deployment_name, cluster_id, user_id)."""
    return str(uuid4()), "my-deployment", str(uuid4()), str(uuid4())


def _step_names(dag: dict[str, Any]) -> list[str]:
    """Extract ordered step IDs from a DAG dict."""
    return [s["id"] for s in dag["steps"]]


# ============================================================================
# Tests
# ============================================================================


class TestSingleModelDag:
    """Test 1: Template with one model component."""

    def test_single_model_dag(self) -> None:
        deployment_id, deployment_name, cluster_id, user_id = _make_ids()

        template: dict[str, Any] = {
            "components": [
                {
                    "name": "llm",
                    "type": "model",
                    "required": True,
                    "default_component": "llama-3-8b",
                },
            ],
            "deployment_order": ["llm"],
        }

        dag = build_deployment_dag(
            deployment_id=deployment_id,
            deployment_name=deployment_name,
            cluster_id=cluster_id,
            user_id=user_id,
            template=template,
            component_selections={"llm": "llama-3-8b"},
        )

        assert _step_names(dag) == ["cluster_health", "deploy_llm", "notify_complete"]
        assert len(dag["steps"]) == 3

        # cluster_health has no dependencies
        assert dag["steps"][0]["depends_on"] == []
        # deploy_llm depends on cluster_health
        assert dag["steps"][1]["depends_on"] == ["cluster_health"]
        assert dag["steps"][1]["action"] == "deployment_create"
        # notify_complete depends on deploy_llm
        assert dag["steps"][2]["depends_on"] == ["deploy_llm"]
        assert dag["steps"][2]["action"] == "log"


class TestMixedModelVectorDb:
    """Test 2: Template with model + vector_db."""

    def test_mixed_model_vectordb(self) -> None:
        deployment_id, deployment_name, cluster_id, user_id = _make_ids()

        template: dict[str, Any] = {
            "components": [
                {
                    "name": "vector_db",
                    "type": "vector_db",
                    "required": True,
                    "default_component": "qdrant",
                },
                {
                    "name": "llm",
                    "type": "model",
                    "required": True,
                    "default_component": "llama-3-8b",
                },
            ],
            "deployment_order": ["vector_db", "llm"],
        }

        dag = build_deployment_dag(
            deployment_id=deployment_id,
            deployment_name=deployment_name,
            cluster_id=cluster_id,
            user_id=user_id,
            template=template,
            component_selections={"vector_db": "qdrant", "llm": "llama-3-8b"},
        )

        expected_order = [
            "cluster_health",
            "deploy_vector_db",
            "deploy_llm",
            "notify_complete",
        ]
        assert _step_names(dag) == expected_order

        # Verify the sequential depends_on chain
        assert dag["steps"][0]["depends_on"] == []
        assert dag["steps"][1]["depends_on"] == ["cluster_health"]
        assert dag["steps"][2]["depends_on"] == ["deploy_vector_db"]
        assert dag["steps"][3]["depends_on"] == ["deploy_llm"]


class TestHelmComponentDag:
    """Test 3: Template with helm component."""

    def test_helm_component_dag(self) -> None:
        deployment_id, deployment_name, cluster_id, user_id = _make_ids()

        template: dict[str, Any] = {
            "components": [
                {
                    "name": "agent_runtime",
                    "type": "helm",
                    "required": True,
                    "chart": {
                        "ref": "oci://registry.example.com/agent-runtime",
                        "version": "1.2.0",
                        "values": {},
                    },
                },
            ],
            "deployment_order": ["agent_runtime"],
        }

        dag = build_deployment_dag(
            deployment_id=deployment_id,
            deployment_name=deployment_name,
            cluster_id=cluster_id,
            user_id=user_id,
            template=template,
            component_selections={"agent_runtime": "agent-runtime-v1"},
        )

        helm_step = dag["steps"][1]
        assert helm_step["id"] == "deploy_agent_runtime"
        assert helm_step["action"] == "helm_deploy"
        assert helm_step["params"]["chart_ref"] == "oci://registry.example.com/agent-runtime"
        assert helm_step["params"]["chart_version"] == "1.2.0"
        assert helm_step["params"]["namespace"] == f"usecase-{deployment_id[:8]}"
        assert helm_step["params"]["release_name"] == f"{deployment_name}-agent_runtime"


class TestMixedModelHelmDag:
    """Test 4: Template with model + helm."""

    def test_mixed_model_helm_dag(self) -> None:
        deployment_id, deployment_name, cluster_id, user_id = _make_ids()

        template: dict[str, Any] = {
            "components": [
                {
                    "name": "llm",
                    "type": "model",
                    "required": True,
                    "default_component": "llama-3-8b",
                },
                {
                    "name": "agent_runtime",
                    "type": "helm",
                    "required": True,
                    "chart": {
                        "ref": "oci://registry.example.com/agent-runtime",
                        "values": {},
                    },
                },
            ],
            "deployment_order": ["llm", "agent_runtime"],
        }

        dag = build_deployment_dag(
            deployment_id=deployment_id,
            deployment_name=deployment_name,
            cluster_id=cluster_id,
            user_id=user_id,
            template=template,
            component_selections={"llm": "llama-3-8b", "agent_runtime": "agent-runtime-v1"},
        )

        model_step = dag["steps"][1]
        helm_step = dag["steps"][2]

        # Model step uses deployment_create
        assert model_step["id"] == "deploy_llm"
        assert model_step["action"] == "deployment_create"
        assert model_step["params"]["model_id"] == "llama-3-8b"

        # Helm step uses helm_deploy
        assert helm_step["id"] == "deploy_agent_runtime"
        assert helm_step["action"] == "helm_deploy"
        assert helm_step["params"]["chart_ref"] == "oci://registry.example.com/agent-runtime"

        # Correct depends_on chain
        assert model_step["depends_on"] == ["cluster_health"]
        assert helm_step["depends_on"] == ["deploy_llm"]


class TestDeploymentOrderRespected:
    """Test 5: deployment_order controls step sequencing."""

    def test_deployment_order_respected(self) -> None:
        deployment_id, deployment_name, cluster_id, user_id = _make_ids()

        template: dict[str, Any] = {
            "components": [
                {
                    "name": "vector_db",
                    "type": "vector_db",
                    "required": True,
                    "default_component": "qdrant",
                },
                {
                    "name": "llm",
                    "type": "model",
                    "required": True,
                    "default_component": "llama-3-8b",
                },
                {
                    "name": "agent_runtime",
                    "type": "helm",
                    "required": True,
                    "chart": {
                        "ref": "oci://registry.example.com/agent-runtime",
                        "values": {},
                    },
                },
            ],
            "deployment_order": ["vector_db", "llm", "agent_runtime"],
        }

        dag = build_deployment_dag(
            deployment_id=deployment_id,
            deployment_name=deployment_name,
            cluster_id=cluster_id,
            user_id=user_id,
            template=template,
            component_selections={
                "vector_db": "qdrant",
                "llm": "llama-3-8b",
                "agent_runtime": "agent-runtime-v1",
            },
        )

        expected_order = [
            "cluster_health",
            "deploy_vector_db",
            "deploy_llm",
            "deploy_agent_runtime",
            "notify_complete",
        ]
        assert _step_names(dag) == expected_order

        # Full sequential chain
        for i in range(1, len(dag["steps"])):
            assert dag["steps"][i]["depends_on"] == [dag["steps"][i - 1]["id"]]


class TestJinja2ReferencesPreserved:
    """Test 6: Jinja2 step-reference expressions are NOT resolved."""

    def test_jinja2_references_preserved(self) -> None:
        deployment_id, deployment_name, cluster_id, user_id = _make_ids()

        jinja_ref = "{{ steps.deploy_llm.outputs.endpoint_url }}"

        template: dict[str, Any] = {
            "components": [
                {
                    "name": "agent_runtime",
                    "type": "helm",
                    "required": True,
                    "chart": {
                        "ref": "oci://registry.example.com/agent-runtime",
                        "values": {
                            "llm_endpoint": jinja_ref,
                        },
                    },
                },
            ],
            "deployment_order": ["agent_runtime"],
        }

        dag = build_deployment_dag(
            deployment_id=deployment_id,
            deployment_name=deployment_name,
            cluster_id=cluster_id,
            user_id=user_id,
            template=template,
            component_selections={"agent_runtime": "agent-runtime-v1"},
            parameters={},
        )

        helm_step = dag["steps"][1]
        # The Jinja2 step reference must be preserved verbatim for BudPipeline
        assert helm_step["params"]["values"]["llm_endpoint"] == jinja_ref


class TestParameterResolution:
    """Test 7: ``{{ params.XXX }}`` placeholders are resolved."""

    def test_parameter_resolution(self) -> None:
        deployment_id, deployment_name, cluster_id, user_id = _make_ids()

        template: dict[str, Any] = {
            "components": [
                {
                    "name": "agent_runtime",
                    "type": "helm",
                    "required": True,
                    "chart": {
                        "ref": "oci://registry.example.com/agent-runtime",
                        "values": {
                            "chunk_size": "{{ params.chunk_size }}",
                            "retrieval_k": "{{ params.retrieval_k }}",
                        },
                    },
                },
            ],
            "deployment_order": ["agent_runtime"],
        }

        dag = build_deployment_dag(
            deployment_id=deployment_id,
            deployment_name=deployment_name,
            cluster_id=cluster_id,
            user_id=user_id,
            template=template,
            component_selections={"agent_runtime": "agent-runtime-v1"},
            parameters={"chunk_size": 1024, "retrieval_k": 5},
        )

        helm_step = dag["steps"][1]
        assert helm_step["params"]["values"]["chunk_size"] == 1024
        assert helm_step["params"]["values"]["retrieval_k"] == 5

    def test_unresolved_parameter_kept(self) -> None:
        """Parameters not supplied are kept as the original template string."""
        deployment_id, deployment_name, cluster_id, user_id = _make_ids()

        template: dict[str, Any] = {
            "components": [
                {
                    "name": "runtime",
                    "type": "helm",
                    "required": True,
                    "chart": {
                        "ref": "oci://registry.example.com/runtime",
                        "values": {
                            "missing_param": "{{ params.not_provided }}",
                        },
                    },
                },
            ],
            "deployment_order": ["runtime"],
        }

        dag = build_deployment_dag(
            deployment_id=deployment_id,
            deployment_name=deployment_name,
            cluster_id=cluster_id,
            user_id=user_id,
            template=template,
            component_selections={"runtime": "runtime-v1"},
            parameters={},
        )

        helm_step = dag["steps"][1]
        assert helm_step["params"]["values"]["missing_param"] == "{{ params.not_provided }}"


class TestCallbackTopicsInDag:
    """Test 8: callback_topics are NOT part of the DAG dict itself.

    The DAG builder returns a pure pipeline definition. Callback topics
    are added by the orchestration layer when submitting the execution,
    not embedded in the DAG structure.
    """

    def test_dag_has_no_callback_topics(self) -> None:
        deployment_id, deployment_name, cluster_id, user_id = _make_ids()

        template: dict[str, Any] = {
            "components": [
                {
                    "name": "llm",
                    "type": "model",
                    "required": True,
                    "default_component": "llama-3-8b",
                },
            ],
            "deployment_order": ["llm"],
        }

        dag = build_deployment_dag(
            deployment_id=deployment_id,
            deployment_name=deployment_name,
            cluster_id=cluster_id,
            user_id=user_id,
            template=template,
            component_selections={"llm": "llama-3-8b"},
        )

        # callback_topics are handled at submission time, not in the DAG
        assert "callback_topics" not in dag


class TestDagSettings:
    """Test 9: DAG has settings with timeout and on_failure."""

    def test_dag_settings(self) -> None:
        deployment_id, deployment_name, cluster_id, user_id = _make_ids()

        template: dict[str, Any] = {
            "components": [
                {
                    "name": "llm",
                    "type": "model",
                    "required": True,
                    "default_component": "llama-3-8b",
                },
            ],
            "deployment_order": ["llm"],
        }

        dag = build_deployment_dag(
            deployment_id=deployment_id,
            deployment_name=deployment_name,
            cluster_id=cluster_id,
            user_id=user_id,
            template=template,
            component_selections={"llm": "llama-3-8b"},
        )

        assert "settings" in dag
        assert dag["settings"]["timeout_seconds"] == 7200
        assert dag["settings"]["on_failure"] == "fail"


class TestDagNameFormat:
    """Test 10: DAG name follows 'usecase-{deployment_name}' format."""

    def test_dag_name_format(self) -> None:
        deployment_id = str(uuid4())
        deployment_name = "rag-chatbot"
        cluster_id = str(uuid4())
        user_id = str(uuid4())

        template: dict[str, Any] = {
            "components": [
                {
                    "name": "llm",
                    "type": "model",
                    "required": True,
                    "default_component": "llama-3-8b",
                },
            ],
            "deployment_order": ["llm"],
        }

        dag = build_deployment_dag(
            deployment_id=deployment_id,
            deployment_name=deployment_name,
            cluster_id=cluster_id,
            user_id=user_id,
            template=template,
            component_selections={"llm": "llama-3-8b"},
        )

        assert dag["name"] == f"usecase-{deployment_name}"
        assert dag["name"] == "usecase-rag-chatbot"


class TestNamespaceFormat:
    """Test 11: Helm steps use namespace 'usecase-{deployment_id[:8]}'."""

    def test_namespace_format(self) -> None:
        deployment_id = "abcdef12-3456-7890-abcd-ef1234567890"
        deployment_name = "my-deployment"
        cluster_id = str(uuid4())
        user_id = str(uuid4())

        template: dict[str, Any] = {
            "components": [
                {
                    "name": "agent_runtime",
                    "type": "helm",
                    "required": True,
                    "chart": {
                        "ref": "oci://registry.example.com/agent-runtime",
                        "values": {},
                    },
                },
            ],
            "deployment_order": ["agent_runtime"],
        }

        dag = build_deployment_dag(
            deployment_id=deployment_id,
            deployment_name=deployment_name,
            cluster_id=cluster_id,
            user_id=user_id,
            template=template,
            component_selections={"agent_runtime": "agent-runtime-v1"},
        )

        helm_step = dag["steps"][1]
        assert helm_step["params"]["namespace"] == f"usecase-{deployment_id[:8]}"
        assert helm_step["params"]["namespace"] == "usecase-abcdef12"

"""Tests for DAG parser - TDD approach.

These tests define the expected behavior of the DAG parser before implementation.
"""

from typing import Any

import pytest

from budpipeline.commons.exceptions import DAGParseError, DAGValidationError
from budpipeline.engine.dag_parser import DAGParser
from budpipeline.engine.schemas import (
    OnFailureAction,
    WorkflowDAG,
)


class TestDAGParserBasicParsing:
    """Test basic DAG parsing functionality."""

    def test_parse_minimal_dag(self, simple_dag: dict[str, Any]) -> None:
        """Should parse a minimal valid DAG with just name and steps."""
        dag = DAGParser.parse(simple_dag)

        assert isinstance(dag, WorkflowDAG)
        assert dag.name == "simple-workflow"
        assert dag.version == "1.0"
        assert len(dag.steps) == 1
        assert dag.steps[0].id == "step1"

    def test_parse_dag_with_all_fields(self, complex_dag: dict[str, Any]) -> None:
        """Should parse a DAG with all optional fields."""
        dag = DAGParser.parse(complex_dag)

        assert dag.name == "complex-workflow"
        assert dag.description == "Complex workflow for testing"
        assert len(dag.parameters) == 3
        assert dag.settings.timeout_seconds == 3600
        assert dag.settings.fail_fast is True
        assert len(dag.steps) == 4
        assert len(dag.outputs) == 2

    def test_parse_dag_from_yaml_string(self) -> None:
        """Should parse DAG from YAML string."""
        yaml_str = """
        name: yaml-workflow
        version: "1.0"
        steps:
          - id: step1
            name: First Step
            action: test.action
            params:
              key: value
        """
        dag = DAGParser.parse_yaml(yaml_str)

        assert dag.name == "yaml-workflow"
        assert len(dag.steps) == 1
        assert dag.steps[0].params == {"key": "value"}

    def test_parse_dag_from_json_string(self) -> None:
        """Should parse DAG from JSON string."""
        json_str = """
        {
            "name": "json-workflow",
            "version": "1.0",
            "steps": [
                {
                    "id": "step1",
                    "name": "First Step",
                    "action": "test.action",
                    "params": {"key": "value"}
                }
            ]
        }
        """
        dag = DAGParser.parse_json(json_str)

        assert dag.name == "json-workflow"
        assert len(dag.steps) == 1


class TestDAGParserStepParsing:
    """Test step parsing within DAG."""

    def test_parse_step_with_dependencies(self, linear_dag: dict[str, Any]) -> None:
        """Should correctly parse step dependencies."""
        dag = DAGParser.parse(linear_dag)

        assert dag.steps[0].depends_on == []
        assert dag.steps[1].depends_on == ["step1"]
        assert dag.steps[2].depends_on == ["step2"]

    def test_parse_step_with_outputs(self, linear_dag: dict[str, Any]) -> None:
        """Should correctly parse step outputs."""
        dag = DAGParser.parse(linear_dag)

        assert dag.steps[0].outputs == ["result"]
        assert dag.steps[1].outputs == ["result"]
        assert dag.steps[2].outputs == []

    def test_parse_step_with_condition(self, conditional_dag: dict[str, Any]) -> None:
        """Should correctly parse step conditions."""
        dag = DAGParser.parse(conditional_dag)

        step2 = dag.get_step("step2")
        assert step2 is not None
        assert step2.condition == "{{ steps.step1.outputs.should_continue == true }}"

    def test_parse_step_with_retry_config(self, complex_dag: dict[str, Any]) -> None:
        """Should correctly parse step retry configuration."""
        dag = DAGParser.parse(complex_dag)

        deploy_step = dag.get_step("deploy")
        assert deploy_step is not None
        assert deploy_step.retry is not None
        assert deploy_step.retry.max_attempts == 2
        assert deploy_step.retry.backoff_seconds == 30

    def test_parse_step_with_on_failure(self, complex_dag: dict[str, Any]) -> None:
        """Should correctly parse step on_failure configuration."""
        dag = DAGParser.parse(complex_dag)

        simulate_step = dag.get_step("simulate")
        assert simulate_step is not None
        assert simulate_step.on_failure == OnFailureAction.CONTINUE

        notify_step = dag.get_step("notify")
        assert notify_step is not None
        assert notify_step.on_failure == OnFailureAction.CONTINUE

    def test_parse_step_with_timeout(self, complex_dag: dict[str, Any]) -> None:
        """Should correctly parse step timeout."""
        dag = DAGParser.parse(complex_dag)

        onboard_step = dag.get_step("onboard")
        assert onboard_step is not None
        assert onboard_step.timeout_seconds == 600


class TestDAGParserParameterParsing:
    """Test parameter parsing within DAG."""

    def test_parse_required_parameter(self, linear_dag: dict[str, Any]) -> None:
        """Should correctly parse required parameters."""
        dag = DAGParser.parse(linear_dag)

        assert len(dag.parameters) == 1
        param = dag.parameters[0]
        assert param.name == "input_value"
        assert param.type == "string"
        assert param.required is True

    def test_parse_parameter_with_default(self, complex_dag: dict[str, Any]) -> None:
        """Should correctly parse parameters with defaults."""
        dag = DAGParser.parse(complex_dag)

        replicas_param = next(p for p in dag.parameters if p.name == "replicas")
        assert replicas_param.default == 1
        assert replicas_param.type == "integer"

    def test_parse_parameter_types(self) -> None:
        """Should correctly parse different parameter types."""
        dag_dict = {
            "name": "param-types-workflow",
            "version": "1.0",
            "parameters": [
                {"name": "str_param", "type": "string", "required": True},
                {"name": "int_param", "type": "integer", "default": 10},
                {"name": "float_param", "type": "float", "default": 1.5},
                {"name": "bool_param", "type": "boolean", "default": False},
                {"name": "list_param", "type": "array", "default": []},
                {"name": "obj_param", "type": "object", "default": {}},
            ],
            "steps": [{"id": "step1", "name": "Step", "action": "test", "params": {}}],
        }
        dag = DAGParser.parse(dag_dict)

        assert len(dag.parameters) == 6
        types = {p.name: p.type for p in dag.parameters}
        assert types["str_param"] == "string"
        assert types["int_param"] == "integer"
        assert types["float_param"] == "float"
        assert types["bool_param"] == "boolean"
        assert types["list_param"] == "array"
        assert types["obj_param"] == "object"


class TestDAGParserSettingsParsing:
    """Test settings parsing within DAG."""

    def test_parse_default_settings(self, simple_dag: dict[str, Any]) -> None:
        """Should use default settings when not specified."""
        dag = DAGParser.parse(simple_dag)

        assert dag.settings is not None
        assert dag.settings.timeout_seconds == 7200  # Default
        assert dag.settings.fail_fast is True  # Default
        assert dag.settings.max_parallel_steps == 10  # Default

    def test_parse_custom_settings(self, complex_dag: dict[str, Any]) -> None:
        """Should correctly parse custom settings."""
        dag = DAGParser.parse(complex_dag)

        assert dag.settings.timeout_seconds == 3600
        assert dag.settings.fail_fast is True
        assert dag.settings.max_parallel_steps == 5


class TestDAGParserOutputsParsing:
    """Test outputs parsing within DAG."""

    def test_parse_outputs(self, linear_dag: dict[str, Any]) -> None:
        """Should correctly parse workflow outputs."""
        dag = DAGParser.parse(linear_dag)

        assert "final_result" in dag.outputs
        assert dag.outputs["final_result"] == "{{ steps.step3.outputs.result }}"

    def test_parse_multiple_outputs(self, complex_dag: dict[str, Any]) -> None:
        """Should correctly parse multiple outputs."""
        dag = DAGParser.parse(complex_dag)

        assert len(dag.outputs) == 2
        assert "endpoint_url" in dag.outputs
        assert "model_id" in dag.outputs


class TestDAGParserValidation:
    """Test DAG validation during parsing."""

    def test_reject_missing_name(self) -> None:
        """Should reject DAG without name."""
        dag_dict = {
            "version": "1.0",
            "steps": [{"id": "step1", "name": "Step", "action": "test", "params": {}}],
        }
        with pytest.raises(DAGValidationError) as exc_info:
            DAGParser.parse(dag_dict)

        assert "name" in str(exc_info.value).lower()

    def test_reject_missing_steps(self) -> None:
        """Should reject DAG without steps."""
        dag_dict = {"name": "no-steps", "version": "1.0"}

        with pytest.raises(DAGValidationError) as exc_info:
            DAGParser.parse(dag_dict)

        assert "steps" in str(exc_info.value).lower()

    def test_reject_empty_steps(self) -> None:
        """Should reject DAG with empty steps array."""
        dag_dict = {"name": "empty-steps", "version": "1.0", "steps": []}

        with pytest.raises(DAGValidationError) as exc_info:
            DAGParser.parse(dag_dict)

        assert "steps" in str(exc_info.value).lower()

    def test_reject_duplicate_step_ids(self) -> None:
        """Should reject DAG with duplicate step IDs."""
        dag_dict = {
            "name": "duplicate-ids",
            "version": "1.0",
            "steps": [
                {"id": "step1", "name": "Step 1", "action": "test", "params": {}},
                {"id": "step1", "name": "Step 1 Duplicate", "action": "test", "params": {}},
            ],
        }
        with pytest.raises(DAGValidationError) as exc_info:
            DAGParser.parse(dag_dict)

        assert "duplicate" in str(exc_info.value).lower()

    def test_reject_missing_step_id(self) -> None:
        """Should reject step without ID."""
        dag_dict = {
            "name": "missing-id",
            "version": "1.0",
            "steps": [{"name": "Step", "action": "test", "params": {}}],
        }
        with pytest.raises(DAGValidationError) as exc_info:
            DAGParser.parse(dag_dict)

        assert "id" in str(exc_info.value).lower()

    def test_reject_missing_step_action(self) -> None:
        """Should reject step without action."""
        dag_dict = {
            "name": "missing-action",
            "version": "1.0",
            "steps": [{"id": "step1", "name": "Step", "params": {}}],
        }
        with pytest.raises(DAGValidationError) as exc_info:
            DAGParser.parse(dag_dict)

        assert "action" in str(exc_info.value).lower()

    def test_reject_invalid_dependency_reference(self) -> None:
        """Should reject step with non-existent dependency."""
        dag_dict = {
            "name": "invalid-dep",
            "version": "1.0",
            "steps": [
                {
                    "id": "step1",
                    "name": "Step",
                    "action": "test",
                    "depends_on": ["nonexistent"],
                    "params": {},
                }
            ],
        }
        with pytest.raises(DAGValidationError) as exc_info:
            DAGParser.parse(dag_dict)

        assert "nonexistent" in str(exc_info.value).lower()

    def test_reject_self_dependency(self) -> None:
        """Should reject step that depends on itself."""
        dag_dict = {
            "name": "self-dep",
            "version": "1.0",
            "steps": [
                {
                    "id": "step1",
                    "name": "Step",
                    "action": "test",
                    "depends_on": ["step1"],
                    "params": {},
                }
            ],
        }
        with pytest.raises(DAGValidationError) as exc_info:
            DAGParser.parse(dag_dict)

        assert "self" in str(exc_info.value).lower() or "step1" in str(exc_info.value)


class TestDAGParserEdgeCases:
    """Test edge cases and error handling."""

    def test_parse_invalid_yaml(self) -> None:
        """Should raise error for invalid YAML."""
        invalid_yaml = "name: test\n  invalid: indentation"

        with pytest.raises(DAGParseError):
            DAGParser.parse_yaml(invalid_yaml)

    def test_parse_invalid_json(self) -> None:
        """Should raise error for invalid JSON."""
        invalid_json = '{"name": "test", invalid}'

        with pytest.raises(DAGParseError):
            DAGParser.parse_json(invalid_json)

    def test_parse_null_input(self) -> None:
        """Should raise error for null input."""
        with pytest.raises(DAGParseError):
            DAGParser.parse(None)  # type: ignore

    def test_parse_empty_dict(self) -> None:
        """Should raise error for empty dictionary."""
        with pytest.raises(DAGValidationError):
            DAGParser.parse({})

    def test_parse_with_extra_fields(self) -> None:
        """Should ignore unknown fields (forward compatibility)."""
        dag_dict = {
            "name": "extra-fields",
            "version": "1.0",
            "unknown_field": "should be ignored",
            "steps": [
                {
                    "id": "step1",
                    "name": "Step",
                    "action": "test",
                    "params": {},
                    "extra_step_field": "ignored",
                }
            ],
        }
        dag = DAGParser.parse(dag_dict)
        assert dag.name == "extra-fields"

    def test_parse_preserves_param_order(self) -> None:
        """Should preserve parameter order."""
        dag_dict = {
            "name": "param-order",
            "version": "1.0",
            "parameters": [
                {"name": "first", "type": "string", "required": True},
                {"name": "second", "type": "string", "required": True},
                {"name": "third", "type": "string", "required": True},
            ],
            "steps": [{"id": "step1", "name": "Step", "action": "test", "params": {}}],
        }
        dag = DAGParser.parse(dag_dict)

        param_names = [p.name for p in dag.parameters]
        assert param_names == ["first", "second", "third"]

    def test_parse_step_with_empty_params(self) -> None:
        """Should handle step with empty params."""
        dag_dict = {
            "name": "empty-params",
            "version": "1.0",
            "steps": [{"id": "step1", "name": "Step", "action": "test", "params": {}}],
        }
        dag = DAGParser.parse(dag_dict)
        assert dag.steps[0].params == {}

    def test_parse_step_without_params_key(self) -> None:
        """Should handle step without params key (default to empty)."""
        dag_dict = {
            "name": "no-params",
            "version": "1.0",
            "steps": [{"id": "step1", "name": "Step", "action": "test"}],
        }
        dag = DAGParser.parse(dag_dict)
        assert dag.steps[0].params == {}


class TestDAGParserHelperMethods:
    """Test helper methods on WorkflowDAG."""

    def test_get_step_by_id(self, linear_dag: dict[str, Any]) -> None:
        """Should find step by ID."""
        dag = DAGParser.parse(linear_dag)

        step = dag.get_step("step2")
        assert step is not None
        assert step.id == "step2"
        assert step.name == "Second Step"

    def test_get_step_returns_none_for_unknown(self, linear_dag: dict[str, Any]) -> None:
        """Should return None for unknown step ID."""
        dag = DAGParser.parse(linear_dag)

        step = dag.get_step("nonexistent")
        assert step is None

    def test_get_root_steps(self, parallel_dag: dict[str, Any]) -> None:
        """Should identify root steps (no dependencies)."""
        dag = DAGParser.parse(parallel_dag)

        root_steps = dag.get_root_steps()
        assert len(root_steps) == 1
        assert root_steps[0].id == "step1"

    def test_get_leaf_steps(self, parallel_dag: dict[str, Any]) -> None:
        """Should identify leaf steps (no dependents)."""
        dag = DAGParser.parse(parallel_dag)

        leaf_steps = dag.get_leaf_steps()
        assert len(leaf_steps) == 1
        assert leaf_steps[0].id == "step3"

    def test_get_step_dependents(self, parallel_dag: dict[str, Any]) -> None:
        """Should find all steps that depend on a given step."""
        dag = DAGParser.parse(parallel_dag)

        dependents = dag.get_dependents("step1")
        dependent_ids = {s.id for s in dependents}
        assert dependent_ids == {"step2a", "step2b"}

    def test_get_required_parameters(self, complex_dag: dict[str, Any]) -> None:
        """Should identify required parameters."""
        dag = DAGParser.parse(complex_dag)

        required = dag.get_required_parameters()
        required_names = {p.name for p in required}
        assert required_names == {"model_uri", "cluster_id"}

    def test_has_step(self, linear_dag: dict[str, Any]) -> None:
        """Should check if step exists."""
        dag = DAGParser.parse(linear_dag)

        assert dag.has_step("step1") is True
        assert dag.has_step("step2") is True
        assert dag.has_step("nonexistent") is False


class TestDAGParserPerformance:
    """Test performance with large DAGs."""

    def test_parse_large_dag(self, make_step, make_dag) -> None:
        """Should efficiently parse large DAG."""
        # Create DAG with 100 steps in a linear chain
        steps = []
        for i in range(100):
            step = make_step(
                f"step{i}",
                depends_on=[f"step{i - 1}"] if i > 0 else None,
            )
            steps.append(step)

        dag_dict = make_dag(name="large-workflow", steps=steps)
        dag = DAGParser.parse(dag_dict)

        assert len(dag.steps) == 100
        assert dag.steps[-1].depends_on == ["step98"]

    def test_parse_wide_dag(self, make_step, make_dag) -> None:
        """Should efficiently parse wide DAG with many parallel steps."""
        # Create DAG with 1 root -> 50 parallel -> 1 final
        steps = [make_step("root")]

        for i in range(50):
            steps.append(make_step(f"parallel{i}", depends_on=["root"]))

        parallel_ids = [f"parallel{i}" for i in range(50)]
        steps.append(make_step("final", depends_on=parallel_ids))

        dag_dict = make_dag(name="wide-workflow", steps=steps)
        dag = DAGParser.parse(dag_dict)

        assert len(dag.steps) == 52
        assert len(dag.get_step("final").depends_on) == 50

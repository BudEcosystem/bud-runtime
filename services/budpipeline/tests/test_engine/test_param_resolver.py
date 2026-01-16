"""Tests for Parameter Resolver - TDD approach.

Tests template resolution for workflow parameters and step outputs.
Supports Jinja2-style templates like:
- {{ params.model_uri }}
- {{ steps.step1.outputs.result }}
- {{ steps.step1.outputs.data | default({}) }}
"""

import pytest

from budpipeline.commons.exceptions import ParameterResolutionError
from budpipeline.engine.param_resolver import ParamResolver


class TestBasicTemplateResolution:
    """Test basic template resolution."""

    def test_resolve_simple_string(self) -> None:
        """Should resolve simple string without templates."""
        result = ParamResolver.resolve(
            value="hello world",
            params={},
            step_outputs={},
        )
        assert result == "hello world"

    def test_resolve_simple_param(self) -> None:
        """Should resolve simple parameter reference."""
        result = ParamResolver.resolve(
            value="{{ params.name }}",
            params={"name": "test-model"},
            step_outputs={},
        )
        assert result == "test-model"

    def test_resolve_param_in_string(self) -> None:
        """Should resolve parameter embedded in string."""
        result = ParamResolver.resolve(
            value="Model: {{ params.name }}",
            params={"name": "llama-7b"},
            step_outputs={},
        )
        assert result == "Model: llama-7b"

    def test_resolve_multiple_params(self) -> None:
        """Should resolve multiple parameters in one string."""
        result = ParamResolver.resolve(
            value="{{ params.model }} on {{ params.cluster }}",
            params={"model": "llama", "cluster": "gpu-1"},
            step_outputs={},
        )
        assert result == "llama on gpu-1"

    def test_resolve_step_output(self) -> None:
        """Should resolve step output reference."""
        result = ParamResolver.resolve(
            value="{{ steps.step1.outputs.model_id }}",
            params={},
            step_outputs={"step1": {"model_id": "model-123"}},
        )
        assert result == "model-123"

    def test_resolve_nested_output(self) -> None:
        """Should resolve nested step output."""
        result = ParamResolver.resolve(
            value="{{ steps.step1.outputs.config.replicas }}",
            params={},
            step_outputs={"step1": {"config": {"replicas": 3, "memory": "16Gi"}}},
        )
        assert result == 3


class TestComplexValueResolution:
    """Test resolution of complex values (dicts, lists)."""

    def test_resolve_dict_value(self, workflow_params: dict, step_outputs: dict) -> None:
        """Should resolve templates in dictionary values."""
        template = {
            "model_id": "{{ steps.onboard.outputs.model_id }}",
            "cluster": "{{ params.cluster_id }}",
            "replicas": "{{ params.replicas }}",
        }
        result = ParamResolver.resolve(
            value=template,
            params=workflow_params,
            step_outputs=step_outputs,
        )

        assert result["model_id"] == "model-abc-123"
        assert result["cluster"] == "cluster-123"
        assert result["replicas"] == 2

    def test_resolve_list_value(self) -> None:
        """Should resolve templates in list values."""
        template = [
            "{{ params.item1 }}",
            "{{ params.item2 }}",
            "static",
        ]
        result = ParamResolver.resolve(
            value=template,
            params={"item1": "a", "item2": "b"},
            step_outputs={},
        )

        assert result == ["a", "b", "static"]

    def test_resolve_nested_dict(self) -> None:
        """Should resolve templates in nested dictionaries."""
        template = {
            "outer": {
                "inner": {
                    "value": "{{ params.deep }}",
                }
            }
        }
        result = ParamResolver.resolve(
            value=template,
            params={"deep": "nested-value"},
            step_outputs={},
        )

        assert result["outer"]["inner"]["value"] == "nested-value"

    def test_resolve_mixed_types(self) -> None:
        """Should handle mixed static and template values."""
        template = {
            "static_str": "hello",
            "static_int": 42,
            "template_str": "{{ params.name }}",
            "list": ["{{ params.x }}", "static", 123],
        }
        result = ParamResolver.resolve(
            value=template,
            params={"name": "test", "x": "dynamic"},
            step_outputs={},
        )

        assert result["static_str"] == "hello"
        assert result["static_int"] == 42
        assert result["template_str"] == "test"
        assert result["list"] == ["dynamic", "static", 123]

    def test_preserve_non_string_types(self) -> None:
        """Should preserve non-string types when not templated."""
        template = {
            "number": 42,
            "float": 3.14,
            "bool": True,
            "null": None,
            "list": [1, 2, 3],
        }
        result = ParamResolver.resolve(
            value=template,
            params={},
            step_outputs={},
        )

        assert result["number"] == 42
        assert result["float"] == 3.14
        assert result["bool"] is True
        assert result["null"] is None
        assert result["list"] == [1, 2, 3]


class TestDefaultValues:
    """Test default value handling."""

    def test_default_for_missing_param(self) -> None:
        """Should use default when parameter is missing."""
        result = ParamResolver.resolve(
            value="{{ params.missing | default('fallback') }}",
            params={},
            step_outputs={},
        )
        assert result == "fallback"

    def test_default_for_missing_output(self) -> None:
        """Should use default when step output is missing."""
        result = ParamResolver.resolve(
            value="{{ steps.missing.outputs.x | default('none') }}",
            params={},
            step_outputs={},
        )
        assert result == "none"

    def test_default_dict_value(self) -> None:
        """Should support dict as default value."""
        result = ParamResolver.resolve(
            value="{{ steps.step1.outputs.config | default({}) }}",
            params={},
            step_outputs={},
        )
        assert result == {}

    def test_default_list_value(self) -> None:
        """Should support list as default value."""
        result = ParamResolver.resolve(
            value="{{ params.items | default([]) }}",
            params={},
            step_outputs={},
        )
        assert result == []

    def test_default_number_value(self) -> None:
        """Should support number as default value."""
        result = ParamResolver.resolve(
            value="{{ params.count | default(0) }}",
            params={},
            step_outputs={},
        )
        assert result == 0

    def test_default_not_used_when_value_exists(self) -> None:
        """Should not use default when value exists."""
        result = ParamResolver.resolve(
            value="{{ params.name | default('fallback') }}",
            params={"name": "actual"},
            step_outputs={},
        )
        assert result == "actual"


class TestTypeConversion:
    """Test type conversion in templates."""

    def test_integer_param_in_string_context(self) -> None:
        """Should convert integer to string when embedded in text."""
        result = ParamResolver.resolve(
            value="Replicas: {{ params.count }}",
            params={"count": 5},
            step_outputs={},
        )
        assert result == "Replicas: 5"

    def test_pure_integer_template(self) -> None:
        """Should preserve integer type for pure template."""
        result = ParamResolver.resolve(
            value="{{ params.count }}",
            params={"count": 5},
            step_outputs={},
        )
        assert result == 5
        assert isinstance(result, int)

    def test_pure_bool_template(self) -> None:
        """Should preserve boolean type for pure template."""
        result = ParamResolver.resolve(
            value="{{ params.enabled }}",
            params={"enabled": True},
            step_outputs={},
        )
        assert result is True
        assert isinstance(result, bool)

    def test_pure_dict_template(self) -> None:
        """Should preserve dict type for pure template."""
        config = {"key": "value", "count": 10}
        result = ParamResolver.resolve(
            value="{{ steps.step1.outputs.config }}",
            params={},
            step_outputs={"step1": {"config": config}},
        )
        assert result == config
        assert isinstance(result, dict)


class TestFilterOperations:
    """Test Jinja2 filter operations."""

    def test_upper_filter(self) -> None:
        """Should apply upper filter."""
        result = ParamResolver.resolve(
            value="{{ params.name | upper }}",
            params={"name": "test"},
            step_outputs={},
        )
        assert result == "TEST"

    def test_lower_filter(self) -> None:
        """Should apply lower filter."""
        result = ParamResolver.resolve(
            value="{{ params.name | lower }}",
            params={"name": "TEST"},
            step_outputs={},
        )
        assert result == "test"

    def test_length_filter(self) -> None:
        """Should apply length filter."""
        result = ParamResolver.resolve(
            value="{{ params.items | length }}",
            params={"items": [1, 2, 3, 4, 5]},
            step_outputs={},
        )
        assert result == 5

    def test_first_filter(self) -> None:
        """Should apply first filter."""
        result = ParamResolver.resolve(
            value="{{ params.items | first }}",
            params={"items": ["a", "b", "c"]},
            step_outputs={},
        )
        assert result == "a"

    def test_last_filter(self) -> None:
        """Should apply last filter."""
        result = ParamResolver.resolve(
            value="{{ params.items | last }}",
            params={"items": ["a", "b", "c"]},
            step_outputs={},
        )
        assert result == "c"

    def test_chained_filters(self) -> None:
        """Should support chained filters."""
        result = ParamResolver.resolve(
            value="{{ params.name | lower | default('unknown') }}",
            params={"name": "TEST"},
            step_outputs={},
        )
        assert result == "test"


class TestErrorHandling:
    """Test error handling for invalid templates."""

    def test_missing_required_param_raises(self) -> None:
        """Should raise error for missing required parameter."""
        with pytest.raises(ParameterResolutionError) as exc_info:
            ParamResolver.resolve(
                value="{{ params.required }}",
                params={},
                step_outputs={},
                strict=True,
            )

        assert "required" in str(exc_info.value).lower()

    def test_missing_required_step_output_raises(self) -> None:
        """Should raise error for missing required step output."""
        with pytest.raises(ParameterResolutionError) as exc_info:
            ParamResolver.resolve(
                value="{{ steps.missing_step.outputs.value }}",
                params={},
                step_outputs={},
                strict=True,
            )

        assert "missing" in str(exc_info.value).lower()

    def test_invalid_template_syntax(self) -> None:
        """Should raise error for invalid template syntax."""
        with pytest.raises(ParameterResolutionError):
            ParamResolver.resolve(
                value="{{ invalid syntax }}",
                params={},
                step_outputs={},
            )

    def test_unclosed_template(self) -> None:
        """Should raise error for unclosed template."""
        with pytest.raises(ParameterResolutionError):
            ParamResolver.resolve(
                value="{{ params.name",
                params={"name": "test"},
                step_outputs={},
            )

    def test_non_strict_mode_returns_empty(self) -> None:
        """Should return empty string for missing values in non-strict mode."""
        result = ParamResolver.resolve(
            value="{{ params.missing }}",
            params={},
            step_outputs={},
            strict=False,
        )
        assert result == ""


class TestSpecialCases:
    """Test special cases and edge conditions."""

    def test_empty_string_template(self) -> None:
        """Should handle empty string."""
        result = ParamResolver.resolve(
            value="",
            params={},
            step_outputs={},
        )
        assert result == ""

    def test_whitespace_only_template(self) -> None:
        """Should preserve whitespace."""
        result = ParamResolver.resolve(
            value="   ",
            params={},
            step_outputs={},
        )
        assert result == "   "

    def test_escaped_braces(self) -> None:
        """Should handle escaped braces (literal {{ }})."""
        result = ParamResolver.resolve(
            value="{% raw %}{{ not_a_template }}{% endraw %}",
            params={},
            step_outputs={},
        )
        assert "{{ not_a_template }}" in result

    def test_param_with_dots_in_name(self) -> None:
        """Should handle params with special characters in paths."""
        result = ParamResolver.resolve(
            value="{{ params.config }}",
            params={"config": {"sub.key": "value"}},
            step_outputs={},
        )
        assert result == {"sub.key": "value"}

    def test_none_value_param(self) -> None:
        """Should handle None parameter value."""
        result = ParamResolver.resolve(
            value="{{ params.nullable }}",
            params={"nullable": None},
            step_outputs={},
        )
        assert result is None

    def test_empty_dict_param(self) -> None:
        """Should handle empty dict parameter."""
        result = ParamResolver.resolve(
            value="{{ params.empty_dict }}",
            params={"empty_dict": {}},
            step_outputs={},
        )
        assert result == {}

    def test_array_index_access(self) -> None:
        """Should support array index access."""
        result = ParamResolver.resolve(
            value="{{ params.items[0] }}",
            params={"items": ["first", "second", "third"]},
            step_outputs={},
        )
        assert result == "first"


class TestResolveDict:
    """Test resolving entire dictionaries."""

    def test_resolve_all_params_in_dict(self, workflow_params: dict, step_outputs: dict) -> None:
        """Should resolve all parameters in a dictionary."""
        template = {
            "model": "{{ steps.onboard.outputs.model_id }}",
            "config": {
                "replicas": "{{ params.replicas }}",
                "cluster": "{{ params.cluster_id }}",
            },
            "static": "unchanged",
        }

        result = ParamResolver.resolve_dict(
            template=template,
            params=workflow_params,
            step_outputs=step_outputs,
        )

        assert result["model"] == "model-abc-123"
        assert result["config"]["replicas"] == 2
        assert result["config"]["cluster"] == "cluster-123"
        assert result["static"] == "unchanged"


class TestResolveList:
    """Test resolving entire lists."""

    def test_resolve_all_params_in_list(self) -> None:
        """Should resolve all parameters in a list."""
        template = [
            "{{ params.first }}",
            "{{ params.second }}",
            {"nested": "{{ params.third }}"},
        ]

        result = ParamResolver.resolve_list(
            template=template,
            params={"first": "a", "second": "b", "third": "c"},
            step_outputs={},
        )

        assert result[0] == "a"
        assert result[1] == "b"
        assert result[2]["nested"] == "c"


class TestHasTemplates:
    """Test template detection."""

    def test_detect_template_in_string(self) -> None:
        """Should detect template in string."""
        assert ParamResolver.has_templates("{{ params.x }}") is True
        assert ParamResolver.has_templates("hello {{ params.x }} world") is True

    def test_detect_no_template(self) -> None:
        """Should detect no template in plain string."""
        assert ParamResolver.has_templates("hello world") is False
        assert ParamResolver.has_templates("") is False

    def test_detect_template_in_dict(self) -> None:
        """Should detect template in dictionary."""
        assert ParamResolver.has_templates({"key": "{{ params.x }}"}) is True
        assert ParamResolver.has_templates({"key": "value"}) is False

    def test_detect_template_in_nested_structure(self) -> None:
        """Should detect template in nested structure."""
        nested = {"level1": {"level2": {"value": "{{ params.deep }}"}}}
        assert ParamResolver.has_templates(nested) is True


class TestExtractVariables:
    """Test variable extraction from templates."""

    def test_extract_param_variables(self) -> None:
        """Should extract parameter references."""
        template = "{{ params.model_uri }} - {{ params.cluster_id }}"
        variables = ParamResolver.extract_variables(template)

        assert "params.model_uri" in variables
        assert "params.cluster_id" in variables

    def test_extract_step_output_variables(self) -> None:
        """Should extract step output references."""
        template = "{{ steps.step1.outputs.result }}"
        variables = ParamResolver.extract_variables(template)

        assert "steps.step1.outputs.result" in variables

    def test_extract_from_dict(self) -> None:
        """Should extract variables from dictionary."""
        template = {
            "model": "{{ steps.onboard.outputs.model_id }}",
            "cluster": "{{ params.cluster_id }}",
        }
        variables = ParamResolver.extract_variables(template)

        assert "steps.onboard.outputs.model_id" in variables
        assert "params.cluster_id" in variables

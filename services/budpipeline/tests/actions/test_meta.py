"""Tests for action metadata definitions."""

from __future__ import annotations

from budpipeline.actions.base.meta import (
    ActionExample,
    ActionMeta,
    ConditionalVisibility,
    ExecutionMode,
    OutputDefinition,
    ParamDefinition,
    ParamType,
    RetryPolicy,
    SelectOption,
    ValidationRules,
)


class TestParamType:
    """Tests for ParamType enum."""

    def test_all_param_types_exist(self) -> None:
        """Verify all expected parameter types are defined."""
        expected_types = [
            "string",
            "number",
            "boolean",
            "select",
            "multiselect",
            "json",
            "template",
            "branches",
            "model_ref",
            "cluster_ref",
            "project_ref",
            "endpoint_ref",
            "provider_ref",
            "credential_ref",
        ]
        actual_types = [pt.value for pt in ParamType]
        assert sorted(actual_types) == sorted(expected_types)

    def test_param_type_is_string_enum(self) -> None:
        """ParamType should be a string enum."""
        assert ParamType.STRING == "string"
        assert ParamType.NUMBER == "number"
        assert isinstance(ParamType.STRING, str)


class TestExecutionMode:
    """Tests for ExecutionMode enum."""

    def test_execution_modes(self) -> None:
        """Verify execution modes."""
        assert ExecutionMode.SYNC == "sync"
        assert ExecutionMode.EVENT_DRIVEN == "event_driven"

    def test_execution_mode_is_string_enum(self) -> None:
        """ExecutionMode should be a string enum."""
        assert isinstance(ExecutionMode.SYNC, str)


class TestSelectOption:
    """Tests for SelectOption dataclass."""

    def test_select_option_creation(self) -> None:
        """Test creating a SelectOption."""
        option = SelectOption(label="My Label", value="my_value")
        assert option.label == "My Label"
        assert option.value == "my_value"


class TestValidationRules:
    """Tests for ValidationRules dataclass."""

    def test_validation_rules_defaults(self) -> None:
        """Test ValidationRules with default values."""
        rules = ValidationRules()
        assert rules.min is None
        assert rules.max is None
        assert rules.min_length is None
        assert rules.max_length is None
        assert rules.pattern is None
        assert rules.pattern_message is None

    def test_validation_rules_with_values(self) -> None:
        """Test ValidationRules with specified values."""
        rules = ValidationRules(
            min=0,
            max=100,
            min_length=1,
            max_length=255,
            pattern=r"^[a-z]+$",
            pattern_message="Must be lowercase letters",
        )
        assert rules.min == 0
        assert rules.max == 100
        assert rules.min_length == 1
        assert rules.max_length == 255
        assert rules.pattern == r"^[a-z]+$"
        assert rules.pattern_message == "Must be lowercase letters"


class TestConditionalVisibility:
    """Tests for ConditionalVisibility dataclass."""

    def test_conditional_visibility_equals(self) -> None:
        """Test ConditionalVisibility with equals condition."""
        cond = ConditionalVisibility(param="mode", equals="advanced")
        assert cond.param == "mode"
        assert cond.equals == "advanced"
        assert cond.not_equals is None

    def test_conditional_visibility_not_equals(self) -> None:
        """Test ConditionalVisibility with not_equals condition."""
        cond = ConditionalVisibility(param="mode", not_equals="simple")
        assert cond.param == "mode"
        assert cond.equals is None
        assert cond.not_equals == "simple"


class TestParamDefinition:
    """Tests for ParamDefinition dataclass."""

    def test_param_definition_minimal(self) -> None:
        """Test ParamDefinition with minimal fields."""
        param = ParamDefinition(
            name="my_param",
            label="My Parameter",
            type=ParamType.STRING,
        )
        assert param.name == "my_param"
        assert param.label == "My Parameter"
        assert param.type == ParamType.STRING
        assert param.required is False
        assert param.default is None
        assert param.description is None

    def test_param_definition_full(self) -> None:
        """Test ParamDefinition with all fields."""
        options = [
            SelectOption(label="Option 1", value="opt1"),
            SelectOption(label="Option 2", value="opt2"),
        ]
        validation = ValidationRules(min_length=1, max_length=100)
        show_when = ConditionalVisibility(param="enabled", equals=True)

        param = ParamDefinition(
            name="my_select",
            label="My Select",
            type=ParamType.SELECT,
            required=True,
            default="opt1",
            description="Select an option",
            placeholder="Choose...",
            options=options,
            validation=validation,
            group="Advanced",
            show_when=show_when,
        )

        assert param.name == "my_select"
        assert param.type == ParamType.SELECT
        assert param.required is True
        assert param.default == "opt1"
        assert param.description == "Select an option"
        assert param.placeholder == "Choose..."
        assert len(param.options or []) == 2
        assert param.validation is not None
        assert param.validation.min_length == 1
        assert param.group == "Advanced"
        assert param.show_when is not None
        assert param.show_when.param == "enabled"


class TestOutputDefinition:
    """Tests for OutputDefinition dataclass."""

    def test_output_definition(self) -> None:
        """Test OutputDefinition creation."""
        output = OutputDefinition(
            name="result",
            type="object",
            description="The result object",
        )
        assert output.name == "result"
        assert output.type == "object"
        assert output.description == "The result object"

    def test_output_definition_minimal(self) -> None:
        """Test OutputDefinition with minimal fields."""
        output = OutputDefinition(name="success", type="boolean")
        assert output.name == "success"
        assert output.type == "boolean"
        assert output.description is None


class TestRetryPolicy:
    """Tests for RetryPolicy dataclass."""

    def test_retry_policy_defaults(self) -> None:
        """Test RetryPolicy with default values."""
        policy = RetryPolicy()
        assert policy.max_attempts == 3
        assert policy.backoff_multiplier == 2.0
        assert policy.initial_interval_seconds == 1.0
        assert policy.max_interval_seconds == 60.0

    def test_retry_policy_custom(self) -> None:
        """Test RetryPolicy with custom values."""
        policy = RetryPolicy(
            max_attempts=5,
            backoff_multiplier=1.5,
            initial_interval_seconds=0.5,
            max_interval_seconds=30.0,
        )
        assert policy.max_attempts == 5
        assert policy.backoff_multiplier == 1.5
        assert policy.initial_interval_seconds == 0.5
        assert policy.max_interval_seconds == 30.0


class TestActionExample:
    """Tests for ActionExample dataclass."""

    def test_action_example(self) -> None:
        """Test ActionExample creation."""
        example = ActionExample(
            title="Basic Usage",
            params={"name": "test", "value": 123},
            description="Shows basic usage of the action",
        )
        assert example.title == "Basic Usage"
        assert example.params == {"name": "test", "value": 123}
        assert example.description == "Shows basic usage of the action"


class TestActionMeta:
    """Tests for ActionMeta dataclass."""

    def test_action_meta_minimal(self) -> None:
        """Test ActionMeta with minimal fields."""
        meta = ActionMeta(
            type="test_action",
            name="Test Action",
            category="Testing",
            description="A test action",
        )
        assert meta.type == "test_action"
        assert meta.name == "Test Action"
        assert meta.category == "Testing"
        assert meta.description == "A test action"
        assert meta.version == "1.0.0"
        assert meta.execution_mode == ExecutionMode.SYNC
        assert meta.idempotent is True
        assert meta.params == []
        assert meta.outputs == []

    def test_action_meta_full(self) -> None:
        """Test ActionMeta with all fields."""
        params = [
            ParamDefinition(
                name="input",
                label="Input",
                type=ParamType.STRING,
                required=True,
            )
        ]
        outputs = [
            OutputDefinition(name="output", type="string"),
        ]
        retry_policy = RetryPolicy(max_attempts=5)
        examples = [
            ActionExample(title="Example", params={"input": "test"}),
        ]

        meta = ActionMeta(
            type="full_action",
            name="Full Action",
            category="Testing",
            description="A fully configured action",
            version="2.0.0",
            icon="🧪",
            color="#ff0000",
            params=params,
            outputs=outputs,
            execution_mode=ExecutionMode.EVENT_DRIVEN,
            timeout_seconds=300,
            retry_policy=retry_policy,
            idempotent=False,
            required_services=["budapp", "budcluster"],
            required_permissions=["model:read", "cluster:write"],
            examples=examples,
            docs_url="https://docs.example.com/full_action",
        )

        assert meta.type == "full_action"
        assert meta.version == "2.0.0"
        assert meta.icon == "🧪"
        assert meta.color == "#ff0000"
        assert len(meta.params) == 1
        assert len(meta.outputs) == 1
        assert meta.execution_mode == ExecutionMode.EVENT_DRIVEN
        assert meta.timeout_seconds == 300
        assert meta.retry_policy is not None
        assert meta.retry_policy.max_attempts == 5
        assert meta.idempotent is False
        assert meta.required_services == ["budapp", "budcluster"]
        assert meta.required_permissions == ["model:read", "cluster:write"]
        assert len(meta.examples) == 1
        assert meta.docs_url == "https://docs.example.com/full_action"

    def test_action_meta_validation_valid(self) -> None:
        """Test ActionMeta.validate() with valid metadata."""
        meta = ActionMeta(
            type="valid_action",
            name="Valid Action",
            category="Testing",
            description="A valid action",
            params=[
                ParamDefinition(
                    name="param1",
                    label="Param 1",
                    type=ParamType.STRING,
                )
            ],
            outputs=[
                OutputDefinition(name="output1", type="string"),
            ],
        )
        errors = meta.validate()
        assert errors == []

    def test_action_meta_validation_missing_required(self) -> None:
        """Test ActionMeta.validate() with missing required fields."""
        meta = ActionMeta(
            type="",
            name="",
            category="",
            description="",
        )
        errors = meta.validate()
        assert "type is required" in errors
        assert "name is required" in errors
        assert "category is required" in errors
        assert "description is required" in errors

    def test_action_meta_validation_invalid_type_format(self) -> None:
        """Test ActionMeta.validate() with invalid type format."""
        meta = ActionMeta(
            type="invalid-type!",
            name="Invalid",
            category="Testing",
            description="Has invalid type",
        )
        errors = meta.validate()
        assert any("alphanumeric" in e for e in errors)

    def test_action_meta_validation_duplicate_params(self) -> None:
        """Test ActionMeta.validate() with duplicate param names."""
        meta = ActionMeta(
            type="duplicate_params",
            name="Duplicate Params",
            category="Testing",
            description="Has duplicate params",
            params=[
                ParamDefinition(name="same_name", label="First", type=ParamType.STRING),
                ParamDefinition(name="same_name", label="Second", type=ParamType.STRING),
            ],
        )
        errors = meta.validate()
        assert any("duplicate param name" in e for e in errors)

    def test_action_meta_validation_select_without_options(self) -> None:
        """Test ActionMeta.validate() with select param missing options."""
        meta = ActionMeta(
            type="select_no_options",
            name="Select No Options",
            category="Testing",
            description="Has select without options",
            params=[
                ParamDefinition(
                    name="my_select",
                    label="My Select",
                    type=ParamType.SELECT,
                    options=None,  # Missing options
                ),
            ],
        )
        errors = meta.validate()
        assert any("requires options" in e for e in errors)

    def test_action_meta_validation_duplicate_outputs(self) -> None:
        """Test ActionMeta.validate() with duplicate output names."""
        meta = ActionMeta(
            type="duplicate_outputs",
            name="Duplicate Outputs",
            category="Testing",
            description="Has duplicate outputs",
            outputs=[
                OutputDefinition(name="result", type="string"),
                OutputDefinition(name="result", type="object"),
            ],
        )
        errors = meta.validate()
        assert any("duplicate output name" in e for e in errors)

    def test_action_meta_get_required_params(self) -> None:
        """Test ActionMeta.get_required_params()."""
        meta = ActionMeta(
            type="test",
            name="Test",
            category="Testing",
            description="Test",
            params=[
                ParamDefinition(
                    name="required_param",
                    label="Required",
                    type=ParamType.STRING,
                    required=True,
                ),
                ParamDefinition(
                    name="optional_param",
                    label="Optional",
                    type=ParamType.STRING,
                    required=False,
                ),
            ],
        )
        required = meta.get_required_params()
        assert len(required) == 1
        assert required[0].name == "required_param"

    def test_action_meta_get_optional_params(self) -> None:
        """Test ActionMeta.get_optional_params()."""
        meta = ActionMeta(
            type="test",
            name="Test",
            category="Testing",
            description="Test",
            params=[
                ParamDefinition(
                    name="required_param",
                    label="Required",
                    type=ParamType.STRING,
                    required=True,
                ),
                ParamDefinition(
                    name="optional_param",
                    label="Optional",
                    type=ParamType.STRING,
                    required=False,
                ),
            ],
        )
        optional = meta.get_optional_params()
        assert len(optional) == 1
        assert optional[0].name == "optional_param"

    def test_action_meta_get_param(self) -> None:
        """Test ActionMeta.get_param()."""
        meta = ActionMeta(
            type="test",
            name="Test",
            category="Testing",
            description="Test",
            params=[
                ParamDefinition(
                    name="my_param",
                    label="My Param",
                    type=ParamType.STRING,
                ),
            ],
        )
        param = meta.get_param("my_param")
        assert param is not None
        assert param.name == "my_param"

        not_found = meta.get_param("nonexistent")
        assert not_found is None

    def test_action_meta_get_output(self) -> None:
        """Test ActionMeta.get_output()."""
        meta = ActionMeta(
            type="test",
            name="Test",
            category="Testing",
            description="Test",
            outputs=[
                OutputDefinition(name="my_output", type="string"),
            ],
        )
        output = meta.get_output("my_output")
        assert output is not None
        assert output.name == "my_output"

        not_found = meta.get_output("nonexistent")
        assert not_found is None

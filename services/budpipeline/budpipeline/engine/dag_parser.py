"""DAG Parser - parses and validates workflow DAG definitions."""

import json
from typing import Any

import yaml
from pydantic import ValidationError

from budpipeline.commons.exceptions import DAGParseError, DAGValidationError
from budpipeline.engine.schemas import WorkflowDAG


class DAGParser:
    """Parser for workflow DAG definitions.

    Supports parsing from:
    - Python dict
    - YAML string
    - JSON string

    Validates:
    - Required fields (name, steps)
    - Step structure and references
    - Dependency references
    - No duplicate step IDs
    - No self-dependencies
    """

    @classmethod
    def parse(cls, data: dict[str, Any] | None) -> WorkflowDAG:
        """Parse a DAG from a dictionary.

        Args:
            data: Dictionary containing DAG definition

        Returns:
            Validated WorkflowDAG instance

        Raises:
            DAGParseError: If input is invalid
            DAGValidationError: If DAG structure is invalid
        """
        if data is None:
            raise DAGParseError("DAG data cannot be None")

        if not isinstance(data, dict):
            raise DAGParseError(f"DAG data must be a dictionary, got {type(data)}")

        if not data:
            raise DAGValidationError("DAG data cannot be empty")

        # Pre-validation checks before Pydantic parsing
        cls._pre_validate(data)

        try:
            # Parse with Pydantic
            dag = WorkflowDAG(**data)

            # Post-validation checks
            cls._post_validate(dag)

            return dag

        except ValidationError as e:
            # Convert Pydantic errors to our exceptions
            errors = []
            for error in e.errors():
                loc = ".".join(str(x) for x in error["loc"])
                errors.append(f"{loc}: {error['msg']}")
            raise DAGValidationError(
                f"DAG validation failed: {errors[0]}",
                errors=errors,
            ) from e

    @classmethod
    def parse_yaml(cls, yaml_str: str) -> WorkflowDAG:
        """Parse a DAG from a YAML string.

        Args:
            yaml_str: YAML string containing DAG definition

        Returns:
            Validated WorkflowDAG instance

        Raises:
            DAGParseError: If YAML is invalid
            DAGValidationError: If DAG structure is invalid
        """
        try:
            data = yaml.safe_load(yaml_str)
        except yaml.YAMLError as e:
            raise DAGParseError(f"Invalid YAML: {e}") from e

        return cls.parse(data)

    @classmethod
    def parse_json(cls, json_str: str) -> WorkflowDAG:
        """Parse a DAG from a JSON string.

        Args:
            json_str: JSON string containing DAG definition

        Returns:
            Validated WorkflowDAG instance

        Raises:
            DAGParseError: If JSON is invalid
            DAGValidationError: If DAG structure is invalid
        """
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise DAGParseError(f"Invalid JSON: {e}") from e

        return cls.parse(data)

    @classmethod
    def _pre_validate(cls, data: dict[str, Any]) -> None:
        """Perform pre-validation before Pydantic parsing.

        Args:
            data: Raw DAG dictionary

        Raises:
            DAGValidationError: If basic structure is invalid
        """
        # Check required top-level fields
        if "name" not in data:
            raise DAGValidationError(
                "DAG validation failed: 'name' is required",
                errors=["name: Field required"],
            )

        if "steps" not in data:
            raise DAGValidationError(
                "DAG validation failed: 'steps' is required",
                errors=["steps: Field required"],
            )

        steps = data.get("steps", [])
        if not isinstance(steps, list):
            raise DAGValidationError(
                "DAG validation failed: 'steps' must be a list",
                errors=["steps: Must be a list"],
            )

        if len(steps) == 0:
            raise DAGValidationError(
                "DAG validation failed: 'steps' cannot be empty",
                errors=["steps: At least one step is required"],
            )

        # Validate step structure
        step_ids: set[str] = set()
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                raise DAGValidationError(
                    f"DAG validation failed: step[{i}] must be a dictionary",
                    errors=[f"steps.{i}: Must be a dictionary"],
                )

            # Check required step fields
            if "id" not in step:
                raise DAGValidationError(
                    f"DAG validation failed: step[{i}] missing 'id'",
                    errors=[f"steps.{i}.id: Field required"],
                )

            if "action" not in step:
                raise DAGValidationError(
                    f"DAG validation failed: step[{i}] missing 'action'",
                    errors=[f"steps.{i}.action: Field required"],
                )

            step_id = step["id"]

            # Check for duplicate IDs
            if step_id in step_ids:
                raise DAGValidationError(
                    f"DAG validation failed: duplicate step ID '{step_id}'",
                    errors=[f"steps: Duplicate step ID '{step_id}'"],
                )
            step_ids.add(step_id)

        # Validate dependency references
        for step in steps:
            step_id = step.get("id", "unknown")
            depends_on = step.get("depends_on", [])

            if not isinstance(depends_on, list):
                depends_on = [depends_on]

            for dep_id in depends_on:
                # Check for self-dependency
                if dep_id == step_id:
                    raise DAGValidationError(
                        f"DAG validation failed: step '{step_id}' cannot depend on itself",
                        errors=[f"steps.{step_id}: Self-dependency not allowed"],
                    )

                # Check if dependency exists
                if dep_id not in step_ids:
                    raise DAGValidationError(
                        f"DAG validation failed: step '{step_id}' depends on "
                        f"nonexistent step '{dep_id}'",
                        errors=[f"steps.{step_id}.depends_on: Unknown step '{dep_id}'"],
                    )

    @classmethod
    def _post_validate(cls, dag: WorkflowDAG) -> None:
        """Perform post-validation after Pydantic parsing.

        Args:
            dag: Parsed WorkflowDAG instance

        Raises:
            DAGValidationError: If DAG structure is invalid
        """
        # Additional validations can be added here
        # For example: validate action types, check for cycles (done in dependency resolver)
        pass

    @classmethod
    def to_dict(cls, dag: WorkflowDAG) -> dict[str, Any]:
        """Convert a WorkflowDAG back to a dictionary.

        Args:
            dag: WorkflowDAG instance

        Returns:
            Dictionary representation
        """
        return dag.model_dump(exclude_none=True)

    @classmethod
    def to_yaml(cls, dag: WorkflowDAG) -> str:
        """Convert a WorkflowDAG to YAML string.

        Args:
            dag: WorkflowDAG instance

        Returns:
            YAML string representation
        """
        return yaml.dump(cls.to_dict(dag), default_flow_style=False)

    @classmethod
    def to_json(cls, dag: WorkflowDAG, indent: int = 2) -> str:
        """Convert a WorkflowDAG to JSON string.

        Args:
            dag: WorkflowDAG instance
            indent: JSON indentation level

        Returns:
            JSON string representation
        """
        return json.dumps(cls.to_dict(dag), indent=indent)

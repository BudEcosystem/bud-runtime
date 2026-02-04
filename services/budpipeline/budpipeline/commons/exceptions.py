"""Custom exceptions for budpipeline service."""

from typing import Any


class WorkflowException(Exception):
    """Base exception for all workflow errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class DAGParseError(WorkflowException):
    """Error parsing DAG definition."""

    pass


class DAGValidationError(WorkflowException):
    """Error validating DAG structure."""

    def __init__(self, message: str, errors: list[str] | None = None, **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.errors = errors or []


class CyclicDependencyError(DAGValidationError):
    """DAG contains cyclic dependencies."""

    def __init__(self, cycle_path: list[str] | None = None) -> None:
        self.cycle_path = cycle_path or []
        path_str = " -> ".join(self.cycle_path) if self.cycle_path else "unknown"
        super().__init__(
            f"Cyclic dependency detected: {path_str}",
            details={"cycle_path": self.cycle_path},
        )


class StepExecutionError(WorkflowException):
    """Error executing a workflow step."""

    def __init__(
        self,
        message: str,
        step_id: str,
        execution_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.step_id = step_id
        self.execution_id = execution_id
        self.details["step_id"] = step_id
        if execution_id:
            self.details["execution_id"] = execution_id


class ActionNotFoundError(WorkflowException):
    """Action type not found in registry."""

    def __init__(self, action_type: str) -> None:
        super().__init__(
            f"Action type not found: {action_type}",
            details={"action_type": action_type},
        )
        self.action_type = action_type


class ActionValidationError(WorkflowException):
    """Action parameters validation failed."""

    def __init__(self, action_type: str, errors: list[str], **kwargs: Any) -> None:
        super().__init__(
            f"Action validation failed for {action_type}",
            details={"action_type": action_type, "validation_errors": errors},
            **kwargs,
        )
        self.action_type = action_type
        self.validation_errors = errors


class ParameterResolutionError(WorkflowException):
    """Error resolving parameter templates."""

    def __init__(self, message: str, template: str | None = None, **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.template = template
        if template:
            self.details["template"] = template


class ConditionEvaluationError(WorkflowException):
    """Error evaluating step condition."""

    def __init__(self, message: str, condition: str | None = None, **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.condition = condition
        if condition:
            self.details["condition"] = condition


class SchedulerError(WorkflowException):
    """Error in job scheduling."""

    def __init__(self, message: str, job_id: str | None = None, **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.job_id = job_id
        if job_id:
            self.details["job_id"] = job_id


class CronParseError(SchedulerError):
    """Error parsing cron expression."""

    def __init__(self, expression: str, error: str | None = None) -> None:
        super().__init__(
            f"Invalid cron expression: {expression}",
            details={"expression": expression, "error": error},
        )
        self.expression = expression


class WorkflowNotFoundError(WorkflowException):
    """Workflow not found."""

    def __init__(self, workflow_id: str) -> None:
        super().__init__(
            f"Workflow not found: {workflow_id}",
            details={"workflow_id": workflow_id},
        )
        self.workflow_id = workflow_id


class DuplicatePipelineNameError(WorkflowException):
    """Pipeline with this name already exists for the user."""

    def __init__(self, name: str, user_id: str | None = None) -> None:
        details: dict[str, Any] = {"name": name}
        if user_id:
            details["user_id"] = user_id
        super().__init__(
            f"A pipeline with the name '{name}' already exists",
            details=details,
        )
        self.name = name
        self.user_id = user_id


class ExecutionNotFoundError(WorkflowException):
    """Execution not found."""

    def __init__(self, execution_id: str) -> None:
        super().__init__(
            f"Execution not found: {execution_id}",
            details={"execution_id": execution_id},
        )
        self.execution_id = execution_id


class ExecutionAlreadyExistsError(WorkflowException):
    """Execution already exists."""

    def __init__(self, execution_id: str) -> None:
        super().__init__(
            f"Execution already exists: {execution_id}",
            details={"execution_id": execution_id},
        )
        self.execution_id = execution_id


class StepNotFoundError(WorkflowException):
    """Step not found in workflow."""

    def __init__(self, step_id: str, workflow_name: str | None = None) -> None:
        msg = f"Step not found: {step_id}"
        if workflow_name:
            msg += f" in workflow {workflow_name}"
        super().__init__(msg, details={"step_id": step_id})
        self.step_id = step_id


class DependencyNotMetError(WorkflowException):
    """Step dependencies not satisfied."""

    def __init__(self, step_id: str, unmet_dependencies: list[str]) -> None:
        super().__init__(
            f"Dependencies not met for step {step_id}",
            details={
                "step_id": step_id,
                "unmet_dependencies": unmet_dependencies,
            },
        )
        self.step_id = step_id
        self.unmet_dependencies = unmet_dependencies


class TimeoutError(WorkflowException):
    """Execution or step timeout."""

    def __init__(
        self,
        message: str,
        timeout_seconds: int,
        execution_id: str | None = None,
        step_id: str | None = None,
    ) -> None:
        details: dict[str, Any] = {"timeout_seconds": timeout_seconds}
        if execution_id:
            details["execution_id"] = execution_id
        if step_id:
            details["step_id"] = step_id
        super().__init__(message, details=details)
        self.timeout_seconds = timeout_seconds


class RetryExhaustedError(StepExecutionError):
    """All retry attempts exhausted."""

    def __init__(
        self,
        step_id: str,
        max_attempts: int,
        last_error: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            f"Retry attempts exhausted for step {step_id} after {max_attempts} attempts",
            step_id=step_id,
            **kwargs,
        )
        self.max_attempts = max_attempts
        self.last_error = last_error
        self.details["max_attempts"] = max_attempts
        if last_error:
            self.details["last_error"] = last_error

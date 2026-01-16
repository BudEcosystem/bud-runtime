"""Constants and enums for budpipeline service."""

from enum import Enum


class ExecutionStatus(str, Enum):
    """Status of a workflow execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class StepStatus(str, Enum):
    """Status of a workflow step."""

    PENDING = "pending"
    WAITING = "waiting"  # Waiting for dependencies
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class TriggerType(str, Enum):
    """Type of execution trigger."""

    MANUAL = "manual"
    SCHEDULED = "scheduled"
    WEBHOOK = "webhook"
    EVENT = "event"
    API = "api"
    CHAIN = "chain"  # Triggered by another workflow


class ActionCategory(str, Enum):
    """Category of action types."""

    INTERNAL = "internal"  # Platform actions via Dapr
    EXTERNAL_K8S = "external_k8s"  # Kubernetes Jobs
    EXTERNAL_HELM = "external_helm"  # Helm deployments
    EXTERNAL_GIT = "external_git"  # Git-based deployments
    UTILITY = "utility"  # Built-in utility actions


class ScheduleType(str, Enum):
    """Type of schedule."""

    CRON = "cron"
    INTERVAL = "interval"
    ONE_TIME = "one_time"
    MANUAL = "manual"


class OnFailureAction(str, Enum):
    """Action to take when a step fails."""

    FAIL = "fail"  # Fail entire workflow
    CONTINUE = "continue"  # Continue to next steps
    RETRY = "retry"  # Retry this step


class ConditionOperator(str, Enum):
    """Operators for conditional expressions."""

    # Comparison
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"

    # String
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    MATCHES = "matches"  # Regex

    # Collection
    IN = "in"
    NOT_IN = "not_in"

    # Existence
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"

    # Logical
    AND = "and"
    OR = "or"
    NOT = "not"


# Default values
DEFAULT_WORKFLOW_TIMEOUT_SECONDS = 7200  # 2 hours
DEFAULT_STEP_TIMEOUT_SECONDS = 300  # 5 minutes
DEFAULT_RETRY_MAX_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 60
DEFAULT_MAX_PARALLEL_STEPS = 10

# State store keys
STATE_KEY_PREFIX = "budpipeline"
EXECUTION_STATE_PREFIX = f"{STATE_KEY_PREFIX}:execution"
STEP_STATE_PREFIX = f"{STATE_KEY_PREFIX}:step"

# Pub/sub topics
TOPIC_EXECUTION_STATUS = "workflow.execution.status"
TOPIC_STEP_STATUS = "workflow.step.status"
TOPIC_EXECUTION_LOGS = "workflow.execution.logs"

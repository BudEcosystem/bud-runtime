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

"""Defines constant values used throughout the project, including application-specific constants."""

import random
from enum import Enum, StrEnum, auto
from typing import Any, Dict, List

from .helpers import create_dynamic_enum


class LogLevel(Enum):
    """Define logging levels with associated priority values.

    Inherit from `str` and `Enum` to create a logging level enumeration. Each level has a string representation and a
    corresponding priority value, which aligns with Python's built-in `logging` module levels.

    Attributes:
        DEBUG (LogLevel): Represents debug-level logging with a priority value of `logging.DEBUG`.
        INFO (LogLevel): Represents info-level logging with a priority value of `logging.INFO`.
        WARNING (LogLevel): Represents warning-level logging with a priority value of `logging.WARNING`.
        ERROR (LogLevel): Represents error-level logging with a priority value of `logging.ERROR`.
        CRITICAL (LogLevel): Represents critical-level logging with a priority value of `logging.CRITICAL`.
        NOTSET (LogLevel): Represents no logging level with a priority value of `logging.NOTSET`.
    """

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    NOTSET = "NOTSET"


class Environment(str, Enum):
    """Enumerate application environments and provide utilities for environment-specific settings.

    Inherit from `str` and `Enum` to define application environments with associated string values. The class also
    includes utility methods to convert string representations to `Environment` values and determine logging and
    debugging settings based on the environment.

    Attributes:
        PRODUCTION (Environment): Represents the production environment.
        DEVELOPMENT (Environment): Represents the development environment.
        TESTING (Environment): Represents the testing environment.
    """

    PRODUCTION = "PRODUCTION"
    DEVELOPMENT = "DEVELOPMENT"
    TESTING = "TESTING"

    @staticmethod
    def from_string(value: str) -> "Environment":
        """Convert a string representation to an `Environment` instance.

        Use regular expressions to match and identify the environment from a string. Raise a `ValueError` if the string
        does not correspond to a valid environment.

        Args:
            value (str): The string representation of the environment.

        Returns:
            Environment: The corresponding `Environment` instance.

        Raises:
            ValueError: If the string does not match any valid environment.
        """
        import re

        matches = re.findall(r"(?i)\b(dev|prod|test)(elop|elopment|uction|ing|er)?\b", value)

        env = matches[0][0].lower() if len(matches) else ""
        if env == "dev":
            return Environment.DEVELOPMENT
        elif env == "prod":
            return Environment.PRODUCTION
        elif env == "test":
            return Environment.TESTING
        else:
            raise ValueError(
                f"Invalid environment: {value}. Only the following environments are allowed: "
                f"{', '.join(map(str, Environment.__members__))}"
            )

    @property
    def log_level(self) -> LogLevel:
        """Return the appropriate logging level for the current environment.

        Returns:
            LogLevel: The logging level for the current environment.
        """
        return {"PRODUCTION": LogLevel.INFO}.get(self.value, LogLevel.DEBUG)

    @property
    def debug(self) -> bool:
        """Return whether debugging is enabled for the current environment.

        Returns:
            bool: `True` if debugging is enabled, `False` otherwise.
        """
        return {"PRODUCTION": False}.get(self.value, True)


class ModalityEnum(Enum):
    """Enumeration of model modalities.

    This enum represents different types of AI model modalities or capabilities.

    Attributes:
        TEXT_INPUT (str): Represents text input modality.
        TEXT_OUTPUT (str): Represents text output modality.
        IMAGE_INPUT (str): Represents image input modality.
        IMAGE_OUTPUT (str): Represents image output modality.
        AUDIO_INPUT (str): Represents audio input modality.
        AUDIO_OUTPUT (str): Represents audio output modality.
    """

    TEXT_INPUT = "text_input"
    TEXT_OUTPUT = "text_output"
    IMAGE_INPUT = "image_input"
    IMAGE_OUTPUT = "image_output"
    AUDIO_INPUT = "audio_input"
    AUDIO_OUTPUT = "audio_output"

    @classmethod
    def serialize_modality(cls, selected_modalities: List["ModalityEnum"]) -> Dict[str, Any]:
        """Serialize a list of selected modality enums into a nested dictionary by modality type.

        The returned dictionary organizes modalities by their type (text, image, audio) with
        nested 'input' and 'output' boolean flags.

        Args:
            selected_modalities (List[ModalityEnum]): A list of selected modality enum values.

        Returns:
            Dict[str, Dict[str, bool]]: A nested dictionary with modality types and their input/output status.
        """
        # Initialize result dictionary
        result = {}

        # Define labels for each modality type
        modality_labels = {"text": "Text", "image": "Image", "audio": "Audio"}

        # Get all selected modality values
        selected_values = [m.value for m in selected_modalities]

        # Process each modality type (text, image, audio)
        for modality_type in modality_labels:
            input_key = f"{modality_type}_input"
            output_key = f"{modality_type}_output"

            result[modality_type] = {
                "input": input_key in selected_values,
                "output": output_key in selected_values,
                "label": modality_labels[modality_type],
            }

        return result


class ModelModalityEnum(Enum):
    """Enumeration of model modalities.

    This enum represents different types of AI model modalities or capabilities.

    Attributes:
        LLM (str): Represents Large Language Models for text generation and processing.
        IMAGE (str): Represents image-related models for tasks like generation or analysis.
        EMBEDDING (str): Represents models that create vector embeddings of input data.
        TEXT_TO_SPEECH (str): Represents models that convert text to spoken audio.
        SPEECH_TO_TEXT (str): Represents models that transcribe spoken audio to text.
    """

    LLM = "llm"
    MLLM = "mllm"
    IMAGE = "image"
    EMBEDDING = "embedding"
    TEXT_TO_SPEECH = "text_to_speech"
    SPEECH_TO_TEXT = "speech_to_text"
    LLM_EMBEDDING = "llm_embedding"
    MLLM_EMBEDDING = "mllm_embedding"


class AddModelModalityEnum(Enum):
    """Enumeration of model modalities when adding a model.

    This enum represents different types of AI model modalities or capabilities.

    Attributes:
        LLM (str): Represents Large Language Models for text generation and processing.
        MLLM (str): Represents Multi-Modal Large Language Models for text generation and processing.
        IMAGE (str): Represents image-related models for tasks like generation or analysis.
        EMBEDDING (str): Represents models that create vector embeddings of input data.
        TEXT_TO_SPEECH (str): Represents models that convert text to spoken audio.
        SPEECH_TO_TEXT (str): Represents models that transcribe spoken audio to text.
    """

    LLM = "llm"
    MLLM = "mllm"
    IMAGE = "image"
    EMBEDDING = "embedding"
    TEXT_TO_SPEECH = "text_to_speech"
    SPEECH_TO_TEXT = "speech_to_text"


ModelSourceEnum = create_dynamic_enum(
    "ModelSourceEnum",
    [
        "local",
        "nlp_cloud",
        "deepinfra",
        "anthropic",
        "vertex_ai-vision-models",
        "vertex_ai-ai21_models",
        "cerebras",
        "watsonx",
        "predibase",
        "volcengine",
        "clarifai",
        "baseten",
        "sambanova",
        "github",
        "petals",
        "replicate",
        "vertex_ai-chat-models",
        "azure_ai",
        "perplexity",
        "vertex_ai-code-text-models",
        "vertex_ai-text-models",
        "cohere_chat",
        "vertex_ai-embedding-models",
        "text-completion-openai",
        "groq",
        "openai",
        "aleph_alpha",
        "sagemaker",
        "databricks",
        "fireworks_ai",
        "vertex_ai-anthropic_models",
        "vertex_ai-mistral_models",
        "voyage",
        "vertex_ai-language-models",
        "anyscale",
        "deepseek",
        "vertex_ai-image-models",
        "mistral",
        "ollama",
        "cohere",
        "gemini",
        "friendliai",
        "vertex_ai-code-chat-models",
        "azure",
        "codestral",
        "vertex_ai-llama_models",
        "together_ai",
        "cloudflare",
        "ai21",
        "openrouter",
        "bedrock",
        "text-completion-codestral",
        "huggingface",
    ],
)

# Keep the old CredentialTypeEnum for ProprietaryCredential compatibility
ProprietaryCredentialTypeEnum = Enum(
    "ProprietaryCredentialTypeEnum",
    {
        name: member.value
        for name, member in ModelSourceEnum.__members__.items()
        if member not in [ModelSourceEnum.LOCAL]
    },
)

# Alias for backward compatibility
CredentialTypeEnum = ProprietaryCredentialTypeEnum


class ApiCredentialTypeEnum(str, Enum):
    """Enumeration of API credential types.

    This enum defines the types of API credentials that can be created.

    Attributes:
        CLIENT_APP (str): Client application credentials for external API access.
        ADMIN_APP (str): Administrative application credentials with elevated permissions.
    """

    CLIENT_APP = "client_app"
    ADMIN_APP = "admin_app"


class ModelProviderTypeEnum(Enum):
    """Enumeration of model provider types.

    This enum represents different types of model providers or sources.

    Attributes:
        CLOUD_MODEL (str): Represents cloud-based model providers.
        HUGGING_FACE (str): Represents models from the Hugging Face platform.
        URL (str): Represents models accessible via a URL.
        DISK (str): Represents locally stored models on disk.
    """

    CLOUD_MODEL = "cloud_model"
    HUGGING_FACE = "hugging_face"
    URL = "url"
    DISK = "disk"


class UserRoleEnum(Enum):
    """Enumeration of user roles in the system.

    This enum defines the various roles that a user can have in the application.
    Each role represents a different level of access and permissions.

    Attributes:
        ADMIN (str): Administrator role with high-level permissions.
        SUPER_ADMIN (str): Super administrator role with the highest level of permissions.
        DEVELOPER (str): Role for software developers.
        DEVOPS (str): Role for DevOps engineers.
        TESTER (str): Role for quality assurance testers.
    """

    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"
    DEVELOPER = "developer"
    DEVOPS = "devops"
    TESTER = "tester"


class UserStatusEnum(StrEnum):
    """Enumeration of user statuses in the system.

    This enum defines the possible statuses that a user account can have.
    It uses auto() to automatically assign string values equal to the member names.

    Attributes:
        ACTIVE: Represents an active user account.
        DELETED: Represents an deleted or disabled user account.
        INVITED: Represents a user who has been invited but hasn't yet activated their account.
    """

    ACTIVE = auto()
    DELETED = auto()
    INVITED = auto()


class UserColorEnum(Enum):
    """Enumeration of predefined user colors.

    This enum defines a set of color options that can be assigned to users.
    Each color is represented by its hexadecimal code.

    Attributes:
        COLOR_1 (str): color (#E57333).
        COLOR_2 (str): color (#FFC442).
        COLOR_3 (str): color (#61A560).
        COLOR_4 (str): color (#3F8EF7).
        COLOR_5 (str): color (#C64C9C).
        COLOR_6 (str): color (#95E0FB).
    """

    COLOR_1 = "#E57333"
    COLOR_2 = "#FFC442"
    COLOR_3 = "#61A560"
    COLOR_4 = "#3F8EF7"
    COLOR_5 = "#C64C9C"
    COLOR_6 = "#95E0FB"

    @classmethod
    def get_random_color(cls) -> str:
        """Get a random color."""
        colors = list(cls)
        return random.choice(colors).value


class UserTypeEnum(StrEnum):
    """Enumeration of user types in the system.

    This enum defines the different types of users that can exist in the application.
    It helps differentiate between administrative users and regular client users.

    Attributes:
        ADMIN: Administrative user with elevated privileges.
        CLIENT: Regular client user with standard privileges.
    """

    ADMIN = auto()
    CLIENT = auto()


class PermissionEnum(Enum):
    """Enumeration of system permissions.

    This enum defines various permission levels for different aspects of the system,
    including models, projects, endpoints, clusters, user management, and benchmarks.

    Attributes:
        MODEL_VIEW (str): Permission to view models.
        MODEL_MANAGE (str): Permission to manage models.
        MODEL_BENCHMARK (str): Permission to benchmark models.
        PROJECT_VIEW (str): Permission to view projects.
        PROJECT_MANAGE (str): Permission to manage projects.
        ENDPOINT_VIEW (str): Permission to view endpoints.
        ENDPOINT_MANAGE (str): Permission to manage endpoints.
        CLUSTER_VIEW (str): Permission to view clusters.
        CLUSTER_MANAGE (str): Permission to manage clusters.
        USER_VIEW (str): Permission to view users.
        USER_MANAGE (str): Permission to manage users.
        BENCHMARK_VIEW (str): Permission to view benchmarks.
        BENCHMARK_MANAGE (str): Permission to manage benchmarks.
        CLIENT_ACCESS (str): Permission for client user access to the system.
    """

    MODEL_VIEW = "model:view"
    MODEL_MANAGE = "model:manage"
    MODEL_BENCHMARK = "model:benchmark"

    PROJECT_VIEW = "project:view"
    PROJECT_MANAGE = "project:manage"

    ENDPOINT_VIEW = "endpoint:view"
    ENDPOINT_MANAGE = "endpoint:manage"

    CLUSTER_VIEW = "cluster:view"
    CLUSTER_MANAGE = "cluster:manage"

    USER_VIEW = "user:view"
    USER_MANAGE = "user:manage"

    BENCHMARK_VIEW = "benchmark:view"
    BENCHMARK_MANAGE = "benchmark:manage"
    CLIENT_ACCESS = "client:access"

    @classmethod
    def get_global_permissions(cls) -> List[str]:
        """Return all permission values in a list."""
        return [
            cls.MODEL_VIEW.value,
            cls.MODEL_MANAGE.value,
            cls.MODEL_BENCHMARK.value,
            cls.PROJECT_VIEW.value,
            cls.PROJECT_MANAGE.value,
            cls.CLUSTER_VIEW.value,
            cls.CLUSTER_MANAGE.value,
            cls.USER_VIEW.value,
            cls.USER_MANAGE.value,
            cls.BENCHMARK_VIEW.value,
            cls.BENCHMARK_MANAGE.value,
        ]

    @classmethod
    def get_manage_to_view_mapping(cls) -> Dict[str, str]:
        """Return mapping of manage permissions to their corresponding view permissions."""
        return {
            cls.MODEL_MANAGE.value: cls.MODEL_VIEW.value,
            cls.PROJECT_MANAGE.value: cls.PROJECT_VIEW.value,
            cls.CLUSTER_MANAGE.value: cls.CLUSTER_VIEW.value,
            cls.USER_MANAGE.value: cls.USER_VIEW.value,
            cls.ENDPOINT_MANAGE.value: cls.ENDPOINT_VIEW.value,
            cls.BENCHMARK_MANAGE.value: cls.BENCHMARK_VIEW.value,
        }

    @classmethod
    def get_default_permissions(cls) -> List[str]:
        """Return default permission values in a list."""
        return [
            cls.MODEL_VIEW.value,
            cls.MODEL_MANAGE.value,
            cls.PROJECT_VIEW.value,
            cls.CLUSTER_VIEW.value,
        ]

    @classmethod
    def get_protected_permissions(cls) -> List[str]:
        """Return restrictive permission values in a list."""
        return [
            cls.MODEL_VIEW.value,
            cls.PROJECT_VIEW.value,
            cls.CLUSTER_VIEW.value,
        ]

    @classmethod
    def get_project_default_permissions(cls) -> List[str]:
        """Return default permission values in a list."""
        return [
            cls.ENDPOINT_VIEW.value,
        ]

    @classmethod
    def get_project_level_scopes(cls) -> List[str]:
        """Return project-level scope values in a list."""
        return [
            cls.ENDPOINT_VIEW.value,
            cls.ENDPOINT_MANAGE.value,
        ]

    @classmethod
    def get_project_protected_scopes(cls) -> List[str]:
        """Return project-level protected scope values in a list."""
        return [
            cls.ENDPOINT_VIEW.value,
        ]

    @classmethod
    def get_client_permissions(cls) -> List[str]:
        """Return client-specific permission values in a list."""
        return [
            cls.CLIENT_ACCESS.value,
        ]


class TokenTypeEnum(Enum):
    """Enumeration of token types used in the application.

    This enum defines the different types of authentication tokens
    that can be used within the application.

    Attributes:
        ACCESS (str): Represents an access token.
        REFRESH (str): Represents a refresh token.
    """

    ACCESS = "access"
    REFRESH = "refresh"


# Algorithm used for signing tokens
JWT_ALGORITHM = "HS256"


class WorkflowStatusEnum(StrEnum):
    """Enumeration of workflow statuses."""

    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()
    # Cancelled status not required since workflow delete api delete record


class WorkflowTypeEnum(StrEnum):
    """Enumeration of workflow types."""

    MODEL_DEPLOYMENT = auto()
    MODEL_SECURITY_SCAN = auto()
    CLUSTER_ONBOARDING = auto()
    CLUSTER_DELETION = auto()
    ENDPOINT_DELETION = auto()
    ENDPOINT_WORKER_DELETION = auto()
    CLOUD_MODEL_ONBOARDING = auto()
    LOCAL_MODEL_ONBOARDING = auto()
    ADD_WORKER_TO_ENDPOINT = auto()
    LICENSE_FAQ_FETCH = auto()
    LOCAL_MODEL_QUANTIZATION = auto()
    MODEL_BENCHMARK = auto()
    ADD_ADAPTER = auto()
    DELETE_ADAPTER = auto()
    EVALUATION_CREATION = auto()


class NotificationType(Enum):
    """Represents the type of a notification.

    Attributes:
        EVENT: Notification triggered by an event.
        TOPIC: Notification related to a specific topic.
        BROADCAST: Notification triggered by a broadcast.
    """

    EVENT = "event"
    TOPIC = "topic"
    BROADCAST = "broadcast"


class NotificationCategory(str, Enum):
    """Represents the type of an internal notification.

    Attributes:
        INAPP: Represents the in-app notification type.
        INTERNAL: Represents the internal notification type.
    """

    INAPP = "inapp"
    INTERNAL = "internal"


class PayloadType(str, Enum):
    """Represents the type of a payload.

    Attributes:
        DEPLOYMENT_RECOMMENDATION: Represents the deployment recommendation payload type.
        DEPLOY_MODEL: Represents the model deployment payload type.
    """

    DEPLOYMENT_RECOMMENDATION = "get_cluster_recommendations"
    DEPLOY_MODEL = "deploy_model"
    REGISTER_CLUSTER = "register_cluster"
    DELETE_CLUSTER = "delete_cluster"
    DELETE_DEPLOYMENT = "delete_deployment"
    PERFORM_MODEL_EXTRACTION = "perform_model_extraction"
    PERFORM_MODEL_SECURITY_SCAN = "perform_model_security_scan"
    CLUSTER_STATUS_UPDATE = "cluster-status-update"
    DEPLOYMENT_STATUS_UPDATE = "deployment-status-update"
    DELETE_WORKER = "delete_worker"
    ADD_WORKER = "add_worker"
    FETCH_LICENSE_FAQS = "fetch_license_faqs"
    DEPLOY_QUANTIZATION = "deploy_quantization"
    RUN_BENCHMARK = "performance_benchmark"
    ADD_ADAPTER = "add_adapter"
    DELETE_ADAPTER = "delete_adapter"


class BudServeWorkflowStepEventName(str, Enum):
    """Represents the name of a workflow step event.

    Attributes:
        BUD_SIMULATOR_EVENTS: Represents the Bud simulator workflow step event name.
        BUDSERVE_CLUSTER_EVENTS: Represents the Budserve cluster workflow step event name.
        CREATE_CLUSTER_EVENTS: Represents the create cluster workflow step event name.
        MODEL_EXTRACTION_EVENTS: Represents the model extraction workflow step event name.
        MODEL_SECURITY_SCAN_EVENTS: Represents the model security scan workflow step event name.
    """

    BUD_SIMULATOR_EVENTS = "bud_simulator_events"
    BUDSERVE_CLUSTER_EVENTS = "budserve_cluster_events"
    CREATE_CLUSTER_EVENTS = "create_cluster_events"
    MODEL_EXTRACTION_EVENTS = "model_extraction_events"
    MODEL_SECURITY_SCAN_EVENTS = "model_security_scan_events"
    DELETE_CLUSTER_EVENTS = "delete_cluster_events"
    DELETE_ENDPOINT_EVENTS = "delete_endpoint_events"
    DELETE_WORKER_EVENTS = "delete_worker_events"
    LICENSE_FAQ_EVENTS = "license_faq_events"
    QUANTIZATION_SIMULATION_EVENTS = "bud_simulator_events"
    QUANTIZATION_DEPLOYMENT_EVENTS = "quantization_deployment_events"
    ADAPTER_DEPLOYMENT_EVENTS = "adapter_deployment_events"
    ADAPTER_DELETE_EVENTS = "adapter_delete_events"


# Mapping between payload types and workflow step event names.
# This mapping is used when processing asynchronous notifications to
# determine which workflow step should be updated based on the incoming
# payload type.
PAYLOAD_TO_WORKFLOW_STEP_EVENT: dict[PayloadType, BudServeWorkflowStepEventName] = {
    PayloadType.DEPLOYMENT_RECOMMENDATION: BudServeWorkflowStepEventName.BUD_SIMULATOR_EVENTS,
    PayloadType.DEPLOY_MODEL: BudServeWorkflowStepEventName.BUDSERVE_CLUSTER_EVENTS,
    PayloadType.REGISTER_CLUSTER: BudServeWorkflowStepEventName.CREATE_CLUSTER_EVENTS,
    PayloadType.PERFORM_MODEL_EXTRACTION: BudServeWorkflowStepEventName.MODEL_EXTRACTION_EVENTS,
    PayloadType.PERFORM_MODEL_SECURITY_SCAN: BudServeWorkflowStepEventName.MODEL_SECURITY_SCAN_EVENTS,
    PayloadType.DELETE_CLUSTER: BudServeWorkflowStepEventName.DELETE_CLUSTER_EVENTS,
    PayloadType.DELETE_DEPLOYMENT: BudServeWorkflowStepEventName.DELETE_ENDPOINT_EVENTS,
    PayloadType.DELETE_WORKER: BudServeWorkflowStepEventName.DELETE_WORKER_EVENTS,
    PayloadType.ADD_WORKER: BudServeWorkflowStepEventName.BUDSERVE_CLUSTER_EVENTS,
    PayloadType.FETCH_LICENSE_FAQS: BudServeWorkflowStepEventName.LICENSE_FAQ_EVENTS,
    PayloadType.DEPLOY_QUANTIZATION: BudServeWorkflowStepEventName.QUANTIZATION_DEPLOYMENT_EVENTS,
    PayloadType.RUN_BENCHMARK: BudServeWorkflowStepEventName.BUDSERVE_CLUSTER_EVENTS,
    PayloadType.ADD_ADAPTER: BudServeWorkflowStepEventName.ADAPTER_DEPLOYMENT_EVENTS,
    PayloadType.DELETE_ADAPTER: BudServeWorkflowStepEventName.ADAPTER_DELETE_EVENTS,
}


class ClusterStatusEnum(StrEnum):
    """Cluster status types.

    Attributes:
        AVAILABLE: Represents the available cluster status.
        NOT_AVAILABLE: Represents the not available cluster status.
        REGISTERING: Represents the registering cluster status.
        ERROR: Represents the error cluster status.
    """

    AVAILABLE = auto()
    NOT_AVAILABLE = auto()
    ERROR = auto()
    DELETING = auto()
    DELETED = auto()


class EndpointStatusEnum(StrEnum):
    """Status for endpoint.

    Attributes:
        RUNNING: Represents the running endpoint status.
        FAILURE: Represents the failure endpoint status.
        DEPLOYING: Represents the deploying endpoint status.
        UNHEALTHY: Represents the unhealthy endpoint status.
        DELETING: Represents the deleting endpoint status.
        DELETED: Represents the deleted endpoint status.
        PENDING: Represents the pending endpoint status.
    """

    RUNNING = auto()
    FAILURE = auto()
    DEPLOYING = auto()
    UNHEALTHY = auto()
    DELETING = auto()
    DELETED = auto()
    PENDING = auto()


class AdapterStatusEnum(StrEnum):
    """Adapter status types.

    Attributes:
        RUNNING: Represents the running endpoint status.
        FAILURE: Represents the failure endpoint status.
        DEPLOYING: Represents the deploying endpoint status.
        UNHEALTHY: Represents the unhealthy endpoint status.
        DELETING: Represents the deleting endpoint status.
        DELETED: Represents the deleted endpoint status.
        PENDING: Represents the pending endpoint status.
    """

    RUNNING = auto()
    FAILURE = auto()
    DEPLOYING = auto()
    UNHEALTHY = auto()
    DELETING = auto()
    DELETED = auto()
    PENDING = auto()


class ScalingTypeEnum(StrEnum):
    """Scaling type types."""

    METRIC = auto()
    OPTIMIZER = auto()


class ScalingMetricEnum(StrEnum):
    """Scaling metric types."""

    TIME_TO_FIRST_TOKENS_SECONDS = "bud:time_to_first_token_seconds_average"
    E2E_REQUEST_LATENCY_SECONDS = "bud:e2e_request_latency_seconds_average"
    GPU_CACHE_USAGE_PERC = "bud:gpu_cache_usage_perc_average"
    TIME_PER_OUTPUT_TOKEN_SECONDS = "bud:time_per_output_token_seconds_average"


class ProxyProviderEnum(StrEnum):
    """Proxy provider types."""

    VLLM = "vllm"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AWS_BEDROCK = "aws-bedrock"
    AWS_SAGEMAKER = "aws-sagemaker"
    AZURE = "azure"
    DEEPSEEK = "deepseek"
    FIREWORKS = "fireworks"
    GCP_VERTEX = "gcp-vertex"
    GOOGLE_AI_STUDIO = "google-ai-studio"
    HYPERBOLIC = "hyperbolic"
    MISTRAL = "mistral"
    TOGETHER = "together"
    XAI = "xai"


# class ModelTemplateTypeEnum(StrEnum):
#     """Model template types."""

#     SUMMARIZATION = auto()
#     CHAT = auto()
#     QUESTION_ANSWERING = auto()
#     RAG = auto()
#     CODE_GEN = auto()
#     CODE_TRANSLATION = auto()
#     ENTITY_EXTRACTION = auto()
#     SENTIMENT_ANALYSIS = auto()
#     DOCUMENT_ANALYSIS = auto()
#     OTHER = auto()


class DropdownBackgroundColor(str, Enum):
    """Background hex color for dropdown."""

    COLOR_1 = "#EEEEEE"
    COLOR_2 = "#965CDE"
    COLOR_3 = "#EC7575"
    COLOR_4 = "#479D5F"
    COLOR_5 = "#D1B854"
    COLOR_6 = "#ECAE75"
    COLOR_7 = "#42CACF"
    COLOR_8 = "#DE5CD1"
    COLOR_9 = "#4077E6"
    COLOR_10 = "#8DE640"
    COLOR_11 = "#8E5EFF"
    COLOR_12 = "#FF895E"
    COLOR_13 = "#FF5E99"
    COLOR_14 = "#F4FF5E"
    COLOR_15 = "#FF5E5E"
    COLOR_16 = "#5EA3FF"
    COLOR_17 = "#5EFFBE"

    @classmethod
    def get_random_color(cls) -> str:
        """Get a random color."""
        colors = list(cls)
        return random.choice(colors).value


class BaseModelRelationEnum(StrEnum):
    """Base model relation types."""

    ADAPTER = "adapter"
    MERGE = "merge"
    QUANTIZED = "quantized"
    FINETUNE = "finetune"


class ModelSecurityScanStatusEnum(StrEnum):
    """Model security scan status types."""

    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    CRITICAL = auto()
    SAFE = auto()


LICENSE_DIR = "licenses"


class ModelStatusEnum(StrEnum):
    """Enumeration of entity statuses in the system.

    Attributes:
        ACTIVE: Represents an active entity.
        DELETED: Represents an deleted entity.
    """

    ACTIVE = auto()
    DELETED = auto()


class CloudModelStatusEnum(StrEnum):
    """Enumeration of entity statuses in the system.

    Attributes:
        ACTIVE: Represents an active entity.
        DELETED: Represents an deleted entity.
    """

    ACTIVE = auto()
    DELETED = auto()


class ProjectStatusEnum(StrEnum):
    """Enumeration of entity statuses in the system.

    Attributes:
        ACTIVE: Represents an active entity.
        DELETED: Represents an deleted entity.
    """

    ACTIVE = auto()
    DELETED = auto()


class ProjectTypeEnum(StrEnum):
    """Enumeration of project types in the system.

    This enum defines the different types of projects that can exist in the Bud ecosystem.

    Attributes:
        CLIENT_APP: Represents a client application project.
        ADMIN_APP: Represents an admin application project.
    """

    CLIENT_APP = auto()
    ADMIN_APP = auto()


# Bud Notify Workflow
BUD_NOTIFICATION_WORKFLOW = "bud-notification"
BUD_INTERNAL_WORKFLOW = "bud-internal"
PROJECT_INVITATION_WORKFLOW = "bud-project-invite"
BUD_RESET_PASSWORD_WORKFLOW = "bud-reset-password"


class NotificationStatus(Enum):
    """Enumerate notification statuses."""

    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PENDING = "PENDING"


class VisibilityEnum(Enum):
    """Enumeration of visibility statuses in the system.

    Attributes:
        PUBLIC: Represents an publicly visible entity.
        INERNAL: Represents an internal entity.
    """

    PUBLIC = "public"
    INTERNAL = "internal"


class FeedbackEnum(Enum):
    """Enumeration of Feedback types in the system.

    Attributes:
        UPVOTE: Represents an upvote entity.
        DOWNVOTE: Represents an downvote entity.
    """

    UPVOTE = "upvote"
    DOWNVOTE = "downvote"


APP_ICONS = {
    "general": {
        "model_mono": "icons/general/model_mono.png",
        "cluster_mono": "icons/general/cluster_mono.png",
        "deployment_mono": "icons/general/deployment_mono.png",
        "default_url_model": "icons/general/default_url_model.png",
        "default_disk_model": "icons/general/default_disk_model.png",
    },
    "providers": {"default_hugging_face_model": "icons/providers/huggingface.png"},
}

HF_AUTHORS_DIR = "hf_authors"

EMOJIS = [
    "😀",
    "😃",
    "😄",
    "😁",
    "😆",
    "😅",
    "🤣",
    "😂",
    "🙂",
    "🙃",
    "🫠",
    "😉",
    "😊",
    "😇",
    "🥰",
    "😍",
    "🤩",
    "😘",
    "😗",
    "☺️",
    "😚",
    "😙",
    "🥲",
    "😋",
    "😛",
    "😜",
    "🤪",
    "😝",
    "🤑",
    "🤗",
    "🤭",
    "🫢",
    "🫣",
    "🤫",
    "🤔",
    "🫡",
    "🤐",
    "🤨",
    "😐",
    "😑",
    "😶",
    "🫥",
    "😶‍🌫️",
    "😏",
    "😒",
    "🙄",
    "😬",
    "😮‍💨",
    "🤥",
    "😌",
    "😔",
    "😪",
    "🤤",
    "😴",
    "😷",
    "🤒",
    "🤕",
    "🤢",
    "🤮",
    "🤧",
    "🥵",
    "🥶",
    "🥴",
    "😵",
    "😵‍💫",
    "🤯",
    "🤠",
    "🥳",
    "🥸",
    "😎",
    "🤓",
    "🧐",
    "😕",
    "🫤",
    "😟",
    "🙁",
    "☹️",
    "😮",
    "😯",
    "😲",
    "😳",
    "🥺",
    "🥹",
    "😦",
    "😧",
    "😨",
    "😰",
    "😥",
    "😢",
    "😭",
    "😱",
    "😖",
    "😣",
    "😞",
    "😓",
    "😩",
    "😫",
    "🥱",
    "😤",
    "😡",
    "😠",
    "🤬",
    "😈",
    "👿",
    "💀",
    "☠️",
    "💩",
    "🤡",
    "👹",
    "👺",
    "👻",
    "👽",
    "👾",
    "🤖",
    "😺",
    "😸",
    "😹",
    "😻",
    "😼",
    "😽",
    "🙀",
    "😿",
    "😾",
    "🙈",
    "🙉",
    "🙊",
    "💋",
    "💌",
    "💘",
    "💝",
    "💖",
    "💗",
    "💓",
    "💞",
    "💕",
    "💟",
    "❣️",
    "💔",
    "❤️‍🔥",
    "❤️‍🩹",
    "❤️",
    "🧡",
    "💛",
    "💚",
    "💙",
    "💜",
    "🤎",
    "🖤",
    "🤍",
    "💯",
    "💢",
    "💥",
    "💫",
    "💦",
    "💨",
    "🕳️",
    "💣",
    "💬",
    "👁️‍🗨️",
    "🗨️",
    "🗯️",
    "💭",
    "💤",
    "👋",
    "🤚",
    "🖐️",
    "✋",
    "🖖",
    "🫱",
    "🫲",
    "🫳",
    "🫴",
    "👌",
    "🤌",
    "🤏",
    "✌️",
    "🤞",
    "🫰",
    "🤟",
    "🤘",
    "🤙",
    "👈",
    "👉",
    "👆",
    "🖕",
    "👇",
    "☝️",
    "🫵",
    "👍",
    "👎",
    "✊",
    "👊",
    "🤛",
    "🤜",
    "👏",
    "🙌",
    "🫶",
    "👐",
    "🤲",
    "🤝",
    "🙏",
    "✍️",
    "💅",
    "🤳",
    "💪",
    "🦾",
    "🦿",
    "🦵",
    "🦶",
    "👂",
    "🦻",
    "👃",
    "🧠",
    "🫀",
    "🫁",
    "🦷",
    "🦴",
    "👀",
    "👁️",
    "👅",
    "👄",
    "🫦",
    "👶",
    "🧒",
    "👦",
    "👧",
    "🧑",
    "👱",
    "👨",
    "🧔",
    "🧔‍♂️",
    "🧔‍♀️",
    "👨‍🦰",
    "👨‍🦱",
    "👨‍🦳",
    "👨‍🦲",
    "👩",
    "👩‍🦰",
    "🧑‍🦰",
    "👩‍🦱",
    "🧑‍🦱",
    "👩‍🦳",
    "🧑‍🦳",
    "👩‍🦲",
    "🧑‍🦲",
    "👱‍♀️",
    "👱‍♂️",
    "🧓",
    "👴",
    "👵",
    "🙍",
    "🙍‍♂️",
    "🙍‍♀️",
    "🙎",
    "🙎‍♂️",
    "🙎‍♀️",
    "🙅",
    "🙅‍♂️",
    "🙅‍♀️",
    "🙆",
    "🙆‍♂️",
    "🙆‍♀️",
    "💁",
    "💁‍♂️",
    "💁‍♀️",
    "🙋",
    "🙋‍♂️",
    "🙋‍♀️",
    "🧏",
    "🧏‍♂️",
    "🧏‍♀️",
    "🙇",
    "🙇‍♂️",
    "🙇‍♀️",
    "🤦",
    "🤦‍♂️",
    "🤦‍♀️",
    "🤷",
    "🤷‍♂️",
    "🤷‍♀️",
    "🧑‍⚕️",
    "👨‍⚕️",
    "👩‍⚕️",
    "🧑‍🎓",
    "👨‍🎓",
    "👩‍🎓",
    "🧑‍🏫",
    "👨‍🏫",
    "👩‍🏫",
    "🧑‍⚖️",
    "👨‍⚖️",
    "👩‍⚖️",
    "🧑‍🌾",
    "👨‍🌾",
    "👩‍🌾",
    "🧑‍🍳",
    "👨‍🍳",
    "👩‍🍳",
    "🧑‍🔧",
    "👨‍🔧",
    "👩‍🔧",
    "🧑‍🏭",
    "👨‍🏭",
    "👩‍🏭",
    "🧑‍💼",
    "👨‍💼",
    "👩‍💼",
    "🧑‍🔬",
    "👨‍🔬",
    "👩‍🔬",
    "🧑‍💻",
    "👨‍💻",
    "👩‍💻",
    "🧑‍🎤",
    "👨‍🎤",
    "👩‍🎤",
    "🧑‍🎨",
    "👨‍🎨",
    "👩‍🎨",
    "🧑‍✈️",
    "👨‍✈️",
    "👩‍✈️",
    "🧑‍🚀",
    "👨‍🚀",
    "👩‍🚀",
    "🧑‍🚒",
    "👨‍🚒",
    "👩‍🚒",
    "👮",
    "👮‍♂️",
    "👮‍♀️",
    "🕵️",
    "🕵️‍♂️",
    "🕵️‍♀️",
    "💂",
    "💂‍♂️",
    "💂‍♀️",
    "🥷",
    "👷",
    "👷‍♂️",
    "👷‍♀️",
    "🫅",
    "🤴",
    "👸",
    "👳",
    "👳‍♂️",
    "👳‍♀️",
    "👲",
    "🧕",
    "🤵",
    "🤵‍♂️",
    "🤵‍♀️",
    "👰",
    "👰‍♂️",
    "👰‍♀️",
    "🤰",
    "🫃",
    "🫄",
    "🤱",
    "👩‍🍼",
    "👨‍🍼",
    "🧑‍🍼",
    "👼",
    "🎅",
    "🤶",
    "🧑‍🎄",
    "🦸",
    "🦸‍♂️",
    "🦸‍♀️",
    "🦹",
    "🦹‍♂️",
    "🦹‍♀️",
    "🧙",
    "🧙‍♂️",
    "🧙‍♀️",
    "🧚",
    "🧚‍♂️",
    "🧚‍♀️",
    "🧛",
    "🧛‍♂️",
    "🧛‍♀️",
    "🧜",
    "🧜‍♂️",
    "🧜‍♀️",
    "🧝",
    "🧝‍♂️",
    "🧝‍♀️",
    "🧞",
    "🧞‍♂️",
    "🧞‍♀️",
    "🧟",
    "🧟‍♂️",
    "🧟‍♀️",
    "🧌",
    "💆",
    "💆‍♂️",
    "💆‍♀️",
    "💇",
    "💇‍♂️",
    "💇‍♀️",
    "🚶",
    "🚶‍♂️",
    "🚶‍♀️",
    "🧍",
    "🧍‍♂️",
    "🧍‍♀️",
    "🧎",
    "🧎‍♂️",
    "🧎‍♀️",
    "🧑‍🦯",
    "👨‍🦯",
    "👩‍🦯",
    "🧑‍🦼",
    "👨‍🦼",
    "👩‍🦼",
    "🧑‍🦽",
    "👨‍🦽",
    "👩‍🦽",
    "🏃",
    "🏃‍♂️",
    "🏃‍♀️",
    "💃",
    "🕺",
    "🕴️",
    "👯",
    "👯‍♂️",
    "👯‍♀️",
    "🧖",
    "🧖‍♂️",
    "🧖‍♀️",
    "🧗",
    "🧗‍♂️",
    "🧗‍♀️",
    "🤺",
    "🏇",
    "⛷️",
    "🏂",
    "🏌️",
    "🏌️‍♂️",
    "🏌️‍♀️",
    "🏄",
    "🏄‍♂️",
    "🏄‍♀️",
    "🚣",
    "🚣‍♂️",
    "🚣‍♀️",
    "🏊",
    "🏊‍♂️",
    "🏊‍♀️",
    "⛹️",
    "⛹️‍♂️",
    "⛹️‍♀️",
    "🏋️",
    "🏋️‍♂️",
    "🏋️‍♀️",
    "🚴",
    "🚴‍♂️",
    "🚴‍♀️",
    "🚵",
    "🚵‍♂️",
    "🚵‍♀️",
    "🤸",
    "🤸‍♂️",
    "🤸‍♀️",
    "🤼",
    "🤼‍♂️",
    "🤼‍♀️",
    "🤽",
    "🤽‍♂️",
    "🤽‍♀️",
    "🤾",
    "🤾‍♂️",
    "🤾‍♀️",
    "🤹",
    "🤹‍♂️",
    "🤹‍♀️",
    "🧘",
    "🧘‍♂️",
    "🧘‍♀️",
    "🛀",
    "🛌",
    "🧑‍🤝‍🧑",
    "👭",
    "👫",
    "👬",
    "💏",
    "👩‍❤️‍💋‍👨",
    "👨‍❤️‍💋‍👨",
    "👩‍❤️‍💋‍👩",
    "💑",
    "👩‍❤️‍👨",
    "👨‍❤️‍👨",
    "👩‍❤️‍👩",
    "👪",
    "👨‍👩‍👦",
    "👨‍👩‍👧",
    "👨‍👩‍👧‍👦",
    "👨‍👩‍👦‍👦",
    "👨‍👩‍👧‍👧",
    "👨‍👨‍👦",
    "👨‍👨‍👧",
    "👨‍👨‍👧‍👦",
    "👨‍👨‍👦‍👦",
    "👨‍👨‍👧‍👧",
    "👩‍👩‍👦",
    "👩‍👩‍👧",
    "👩‍👩‍👧‍👦",
    "👩‍👩‍👦‍👦",
    "👩‍👩‍👧‍👧",
    "👨‍👦",
    "👨‍👦‍👦",
    "👨‍👧",
    "👨‍👧‍👦",
    "👨‍👧‍👧",
    "👩‍👦",
    "👩‍👦‍👦",
    "👩‍👧",
    "👩‍👧‍👦",
    "👩‍👧‍👧",
    "🗣️",
    "👤",
    "👥",
    "🫂",
    "👣",
    "🐵",
    "🐒",
    "🦍",
    "🦧",
    "🐶",
    "🐕",
    "🦮",
    "🐕‍🦺",
    "🐩",
    "🐺",
    "🦊",
    "🦝",
    "🐱",
    "🐈",
    "🐈‍⬛",
    "🦁",
    "🐯",
    "🐅",
    "🐆",
    "🐴",
    "🐎",
    "🦄",
    "🦓",
    "🦌",
    "🦬",
    "🐮",
    "🐂",
    "🐃",
    "🐄",
    "🐷",
    "🐖",
    "🐗",
    "🐽",
    "🐏",
    "🐑",
    "🐐",
    "🐪",
    "🐫",
    "🦙",
    "🦒",
    "🐘",
    "🦣",
    "🦏",
    "🦛",
    "🐭",
    "🐁",
    "🐀",
    "🐹",
    "🐰",
    "🐇",
    "🐿️",
    "🦫",
    "🦔",
    "🦇",
    "🐻",
    "🐻‍❄️",
    "🐨",
    "🐼",
    "🦥",
    "🦦",
    "🦨",
    "🦘",
    "🦡",
    "🐾",
    "🦃",
    "🐔",
    "🐓",
    "🐣",
    "🐤",
    "🐥",
    "🐦",
    "🐧",
    "🕊️",
    "🦅",
    "🦆",
    "🦢",
    "🦉",
    "🦤",
    "🪶",
    "🦩",
    "🦚",
    "🦜",
    "🐸",
    "🐊",
    "🐢",
    "🦎",
    "🐍",
    "🐲",
    "🐉",
    "🦕",
    "🦖",
    "🐳",
    "🐋",
    "🐬",
    "🦭",
    "🐟",
    "🐠",
    "🐡",
    "🦈",
    "🐙",
    "🐚",
    "🪸",
    "🐌",
    "🦋",
    "🐛",
    "🐜",
    "🐝",
    "🪲",
    "🐞",
    "🦗",
    "🪳",
    "🕷️",
    "🕸️",
    "🦂",
    "🦟",
    "🪰",
    "🪱",
    "🦠",
    "💐",
    "🌸",
    "💮",
    "🪷",
    "🏵️",
    "🌹",
    "🥀",
    "🌺",
    "🌻",
    "🌼",
    "🌷",
    "🌱",
    "🪴",
    "🌲",
    "🌳",
    "🌴",
    "🌵",
    "🌾",
    "🌿",
    "☘️",
    "🍀",
    "🍁",
    "🍂",
    "🍃",
    "🪹",
    "🪺",
    "🍇",
    "🍈",
    "🍉",
    "🍊",
    "🍋",
    "🍌",
    "🍍",
    "🥭",
    "🍎",
    "🍏",
    "🍐",
    "🍑",
    "🍒",
    "🍓",
    "🫐",
    "🥝",
    "🍅",
    "🫒",
    "🥥",
    "🥑",
    "🍆",
    "🥔",
    "🥕",
    "🌽",
    "🌶️",
    "🫑",
    "🥒",
    "🥬",
    "🥦",
    "🧄",
    "🧅",
    "🍄",
    "🥜",
    "🫘",
    "🌰",
    "🍞",
    "🥐",
    "🥖",
    "🫓",
    "🥨",
    "🥯",
    "🥞",
    "🧇",
    "🧀",
    "🍖",
    "🍗",
    "🥩",
    "🥓",
    "🍔",
    "🍟",
    "🍕",
    "🌭",
    "🥪",
    "🌮",
    "🌯",
    "🫔",
    "🥙",
    "🧆",
    "🥚",
    "🍳",
    "🥘",
    "🍲",
    "🫕",
    "🥣",
    "🥗",
    "🍿",
    "🧈",
    "🧂",
    "🥫",
    "🍱",
    "🍘",
    "🍙",
    "🍚",
    "🍛",
    "🍜",
    "🍝",
    "🍠",
    "🍢",
    "🍣",
    "🍤",
    "🍥",
    "🥮",
    "🍡",
    "🥟",
    "🥠",
    "🥡",
    "🦀",
    "🦞",
    "🦐",
    "🦑",
    "🦪",
    "🍦",
    "🍧",
    "🍨",
    "🍩",
    "🍪",
    "🎂",
    "🍰",
    "🧁",
    "🥧",
    "🍫",
    "🍬",
    "🍭",
    "🍮",
    "🍯",
    "🍼",
    "🥛",
    "☕",
    "🫖",
    "🍵",
    "🍶",
    "🍾",
    "🍷",
    "🍸",
    "🍹",
    "🍺",
    "🍻",
    "🥂",
    "🥃",
    "🫗",
    "🥤",
    "🧋",
    "🧃",
    "🧉",
    "🧊",
    "🥢",
    "🍽️",
    "🍴",
    "🥄",
    "🔪",
    "🫙",
    "🏺",
    "🌍",
    "🌎",
    "🌏",
    "🌐",
    "🗺️",
    "🗾",
    "🧭",
    "🏔️",
    "⛰️",
    "🌋",
    "🗻",
    "🏕️",
    "🏖️",
    "🏜️",
    "🏝️",
    "🏞️",
    "🏟️",
    "🏛️",
    "🏗️",
    "🧱",
    "🪨",
    "🪵",
    "🛖",
    "🏘️",
    "🏚️",
    "🏠",
    "🏡",
    "🏢",
    "🏣",
    "🏤",
    "🏥",
    "🏦",
    "🏨",
    "🏩",
    "🏪",
    "🏫",
    "🏬",
    "🏭",
    "🏯",
    "🏰",
    "💒",
    "🗼",
    "🗽",
    "⛪",
    "🕌",
    "🛕",
    "🕍",
    "⛩️",
    "🕋",
    "⛲",
    "⛺",
    "🌁",
    "🌃",
    "🏙️",
    "🌄",
    "🌅",
    "🌆",
    "🌇",
    "🌉",
    "♨️",
    "🎠",
    "🛝",
    "🎡",
    "🎢",
    "💈",
    "🎪",
    "🚂",
    "🚃",
    "🚄",
    "🚅",
    "🚆",
    "🚇",
    "🚈",
    "🚉",
    "🚊",
    "🚝",
    "🚞",
    "🚋",
    "🚌",
    "🚍",
    "🚎",
    "🚐",
    "🚑",
    "🚒",
    "🚓",
    "🚔",
    "🚕",
    "🚖",
    "🚗",
    "🚘",
    "🚙",
    "🛻",
    "🚚",
    "🚛",
    "🚜",
    "🏎️",
    "🏍️",
    "🛵",
    "🦽",
    "🦼",
    "🛺",
    "🚲",
    "🛴",
    "🛹",
    "🛼",
    "🚏",
    "🛣️",
    "🛤️",
    "🛢️",
    "⛽",
    "🛞",
    "🚨",
    "🚥",
    "🚦",
    "🛑",
    "🚧",
    "⚓",
    "🛟",
    "⛵",
    "🛶",
    "🚤",
    "🛳️",
    "⛴️",
    "🛥️",
    "🚢",
    "✈️",
    "🛩️",
    "🛫",
    "🛬",
    "🪂",
    "💺",
    "🚁",
    "🚟",
    "🚠",
    "🚡",
    "🛰️",
    "🚀",
    "🛸",
    "🛎️",
    "🧳",
    "⌛",
    "⏳",
    "⌚",
    "⏰",
    "⏱️",
    "⏲️",
    "🕰️",
    "🕛",
    "🕧",
    "🕐",
    "🕜",
    "🕑",
    "🕝",
    "🕒",
    "🕞",
    "🕓",
    "🕟",
    "🕔",
    "🕠",
    "🕕",
    "🕡",
    "🕖",
    "🕢",
    "🕗",
    "🕣",
    "🕘",
    "🕤",
    "🕙",
    "🕥",
    "🕚",
    "🕦",
    "🌑",
    "🌒",
    "🌓",
    "🌔",
    "🌕",
    "🌖",
    "🌗",
    "🌘",
    "🌙",
    "🌚",
    "🌛",
    "🌜",
    "🌡️",
    "☀️",
    "🌝",
    "🌞",
    "🪐",
    "⭐",
    "🌟",
    "🌠",
    "🌌",
    "☁️",
    "⛅",
    "⛈️",
    "🌤️",
    "🌥️",
    "🌦️",
    "🌧️",
    "🌨️",
    "🌩️",
    "🌪️",
    "🌫️",
    "🌬️",
    "🌀",
    "🌈",
    "🌂",
    "☂️",
    "☔",
    "⛱️",
    "⚡",
    "❄️",
    "☃️",
    "⛄",
    "☄️",
    "🔥",
    "💧",
    "🌊",
    "🎃",
    "🎄",
    "🎆",
    "🎇",
    "🧨",
    "✨",
    "🎈",
    "🎉",
    "🎊",
    "🎋",
    "🎍",
    "🎎",
    "🎏",
    "🎐",
    "🎑",
    "🧧",
    "🎀",
    "🎁",
    "🎗️",
    "🎟️",
    "🎫",
    "🎖️",
    "🏆",
    "🏅",
    "🥇",
    "🥈",
    "🥉",
    "⚽",
    "⚾",
    "🥎",
    "🏀",
    "🏐",
    "🏈",
    "🏉",
    "🎾",
    "🥏",
    "🎳",
    "🏏",
    "🏑",
    "🏒",
    "🥍",
    "🏓",
    "🏸",
    "🥊",
    "🥋",
    "🥅",
    "⛳",
    "⛸️",
    "🎣",
    "🤿",
    "🎽",
    "🎿",
    "🛷",
    "🥌",
    "🎯",
    "🪀",
    "🪁",
    "🎱",
    "🔮",
    "🪄",
    "🧿",
    "🪬",
    "🎮",
    "🕹️",
    "🎰",
    "🎲",
    "🧩",
    "🧸",
    "🪅",
    "🪩",
    "🪆",
    "♠️",
    "♥️",
    "♦️",
    "♣️",
    "♟️",
    "🃏",
    "🀄",
    "🎴",
    "🎭",
    "🖼️",
    "🎨",
    "🧵",
    "🪡",
    "🧶",
    "🪢",
    "👓",
    "🕶️",
    "🥽",
    "🥼",
    "🦺",
    "👔",
    "👕",
    "👖",
    "🧣",
    "🧤",
    "🧥",
    "🧦",
    "👗",
    "👘",
    "🥻",
    "🩱",
    "🩲",
    "🩳",
    "👙",
    "👚",
    "👛",
    "👜",
    "👝",
    "🛍️",
    "🎒",
    "🩴",
    "👞",
    "👟",
    "🥾",
    "🥿",
    "👠",
    "👡",
    "🩰",
    "👢",
    "👑",
    "👒",
    "🎩",
    "🎓",
    "🧢",
    "🪖",
    "⛑️",
    "📿",
    "💄",
    "💍",
    "💎",
    "🔇",
    "🔈",
    "🔉",
    "🔊",
    "📢",
    "📣",
    "📯",
    "🔔",
    "🔕",
    "🎼",
    "🎵",
    "🎶",
    "🎙️",
    "🎚️",
    "🎛️",
    "🎤",
    "🎧",
    "📻",
    "🎷",
    "🪗",
    "🎸",
    "🎹",
    "🎺",
    "🎻",
    "🪕",
    "🥁",
    "🪘",
    "📱",
    "📲",
    "☎️",
    "📞",
    "📟",
    "📠",
    "🔋",
    "🪫",
    "🔌",
    "💻",
    "🖥️",
    "🖨️",
    "⌨️",
    "🖱️",
    "🖲️",
    "💽",
    "💾",
    "💿",
    "📀",
    "🧮",
    "🎥",
    "🎞️",
    "📽️",
    "🎬",
    "📺",
    "📷",
    "📸",
    "📹",
    "📼",
    "🔍",
    "🔎",
    "🕯️",
    "💡",
    "🔦",
    "🏮",
    "🪔",
    "📔",
    "📕",
    "📖",
    "📗",
    "📘",
    "📙",
    "📚",
    "📓",
    "📒",
    "📃",
    "📜",
    "📄",
    "📰",
    "🗞️",
    "📑",
    "🔖",
    "🏷️",
    "💰",
    "🪙",
    "💴",
    "💵",
    "💶",
    "💷",
    "💸",
    "💳",
    "🧾",
    "💹",
    "✉️",
    "📧",
    "📨",
    "📩",
    "📤",
    "📥",
    "📦",
    "📫",
    "📪",
    "📬",
    "📭",
    "📮",
    "🗳️",
    "✏️",
    "✒️",
    "🖋️",
    "🖊️",
    "🖌️",
    "🖍️",
    "📝",
    "💼",
    "📁",
    "📂",
    "🗂️",
    "📅",
    "📆",
    "🗒️",
    "🗓️",
    "📇",
    "📈",
    "📉",
    "📊",
    "📋",
    "📌",
    "📍",
    "📎",
    "🖇️",
    "📏",
    "📐",
    "✂️",
    "🗃️",
    "🗄️",
    "🗑️",
    "🔒",
    "🔓",
    "🔏",
    "🔐",
    "🔑",
    "🗝️",
    "🔨",
    "🪓",
    "⛏️",
    "⚒️",
    "🛠️",
    "🗡️",
    "⚔️",
    "🔫",
    "🪃",
    "🏹",
    "🛡️",
    "🪚",
    "🔧",
    "🪛",
    "🔩",
    "⚙️",
    "🗜️",
    "⚖️",
    "🦯",
    "🔗",
    "⛓️",
    "🪝",
    "🧰",
    "🧲",
    "🪜",
    "⚗️",
    "🧪",
    "🧫",
    "🧬",
    "🔬",
    "🔭",
    "📡",
    "💉",
    "🩸",
    "💊",
    "🩹",
    "🩼",
    "🩺",
    "🩻",
    "🚪",
    "🛗",
    "🪞",
    "🪟",
    "🛏️",
    "🛋️",
    "🪑",
    "🚽",
    "🪠",
    "🚿",
    "🛁",
    "🪤",
    "🪒",
    "🧴",
    "🧷",
    "🧹",
    "🧺",
    "🧻",
    "🪣",
    "🧼",
    "🫧",
    "🪥",
    "🧽",
    "🧯",
    "🛒",
    "🚬",
    "⚰️",
    "🪦",
    "⚱️",
    "🗿",
    "🪧",
    "🪪",
    "🏧",
    "🚮",
    "🚰",
    "♿",
    "🚹",
    "🚺",
    "🚻",
    "🚼",
    "🚾",
    "🛂",
    "🛃",
    "🛄",
    "🛅",
    "⚠️",
    "🚸",
    "⛔",
    "🚫",
    "🚳",
    "🚭",
    "🚯",
    "🚱",
    "🚷",
    "📵",
    "🔞",
    "☢️",
    "☣️",
    "⬆️",
    "↗️",
    "➡️",
    "↘️",
    "⬇️",
    "↙️",
    "⬅️",
    "↖️",
    "↕️",
    "↔️",
    "↩️",
    "↪️",
    "⤴️",
    "⤵️",
    "🔃",
    "🔄",
    "🔙",
    "🔚",
    "🔛",
    "🔜",
    "🔝",
    "🛐",
    "⚛️",
    "🕉️",
    "✡️",
    "☸️",
    "☯️",
    "✝️",
    "☦️",
    "☪️",
    "☮️",
    "🕎",
    "🔯",
    "♈",
    "♉",
    "♊",
    "♋",
    "♌",
    "♍",
    "♎",
    "♏",
    "♐",
    "♑",
    "♒",
    "♓",
    "⛎",
    "🔀",
    "🔁",
    "🔂",
    "▶️",
    "⏩",
    "⏭️",
    "⏯️",
    "◀️",
    "⏪",
    "⏮️",
    "🔼",
    "⏫",
    "🔽",
    "⏬",
    "⏸️",
    "⏹️",
    "⏺️",
    "⏏️",
    "🎦",
    "🔅",
    "🔆",
    "📶",
    "📳",
    "📴",
    "♀️",
    "♂️",
    "⚧️",
    "✖️",
    "➕",
    "➖",
    "➗",
    "🟰",
    "♾️",
    "‼️",
    "⁉️",
    "❓",
    "❔",
    "❕",
    "❗",
    "〰️",
    "💱",
    "💲",
    "⚕️",
    "♻️",
    "⚜️",
    "🔱",
    "📛",
    "🔰",
    "⭕",
    "✅",
    "☑️",
    "✔️",
    "❌",
    "❎",
    "➰",
    "➿",
    "〽️",
    "✳️",
    "✴️",
    "❇️",
    "©️",
    "®️",
    "™️",
    "#️⃣",
    "*️⃣",
    "0️⃣",
    "1️⃣",
    "2️⃣",
    "3️⃣",
    "4️⃣",
    "5️⃣",
    "6️⃣",
    "7️⃣",
    "8️⃣",
    "9️⃣",
    "🔟",
    "🔠",
    "🔡",
    "🔢",
    "🔣",
    "🔤",
    "🅰️",
    "🆎",
    "🅱️",
    "🆑",
    "🆒",
    "🆓",
    "ℹ️",
    "🆔",
    "Ⓜ️",
    "🆕",
    "🆖",
    "🅾️",
    "🆗",
    "🅿️",
    "🆘",
    "🆙",
    "🆚",
    "🈁",
    "🈂️",
    "🈷️",
    "🈶",
    "🈯",
    "🉐",
    "🈹",
    "🈚",
    "🈲",
    "🉑",
    "🈸",
    "🈴",
    "🈳",
    "㊗️",
    "㊙️",
    "🈺",
    "🈵",
    "🔴",
    "🟠",
    "🟡",
    "🟢",
    "🔵",
    "🟣",
    "🟤",
    "⚫",
    "⚪",
    "🟥",
    "🟧",
    "🟨",
    "🟩",
    "🟦",
    "🟪",
    "🟫",
    "⬛",
    "⬜",
    "◼️",
    "◻️",
    "◾",
    "◽",
    "▪️",
    "▫️",
    "🔶",
    "🔷",
    "🔸",
    "🔹",
    "🔺",
    "🔻",
    "💠",
    "🔘",
    "🔳",
    "🔲",
    "🏁",
    "🚩",
    "🎌",
    "🏴",
    "🏳️",
    "🏳️‍🌈",
    "🏳️‍⚧️",
    "🏴‍☠️",
    "🇦🇨",
    "🇦🇩",
    "🇦🇪",
    "🇦🇫",
    "🇦🇬",
    "🇦🇮",
    "🇦🇱",
    "🇦🇲",
    "🇦🇴",
    "🇦🇶",
    "🇦🇷",
    "🇦🇸",
    "🇦🇹",
    "🇦🇺",
    "🇦🇼",
    "🇦🇽",
    "🇦🇿",
    "🇧🇦",
    "🇧🇧",
    "🇧🇩",
    "🇧🇪",
    "🇧🇫",
    "🇧🇬",
    "🇧🇭",
    "🇧🇮",
    "🇧🇯",
    "🇧🇱",
    "🇧🇲",
    "🇧🇳",
    "🇧🇴",
    "🇧🇶",
    "🇧🇷",
    "🇧🇸",
    "🇧🇹",
    "🇧🇻",
    "🇧🇼",
    "🇧🇾",
    "🇧🇿",
    "🇨🇦",
    "🇨🇨",
    "🇨🇩",
    "🇨🇫",
    "🇨🇬",
    "🇨🇭",
    "🇨🇮",
    "🇨🇰",
    "🇨🇱",
    "🇨🇲",
    "🇨🇳",
    "🇨🇴",
    "🇨🇵",
    "🇨🇷",
    "🇨🇺",
    "🇨🇻",
    "🇨🇼",
    "🇨🇽",
    "🇨🇾",
    "🇨🇿",
    "🇩🇪",
    "🇩🇬",
    "🇩🇯",
    "🇩🇰",
    "🇩🇲",
    "🇩🇴",
    "🇩🇿",
    "🇪🇦",
    "🇪🇨",
    "🇪🇪",
    "🇪🇬",
    "🇪🇭",
    "🇪🇷",
    "🇪🇸",
    "🇪🇹",
    "🇪🇺",
    "🇫🇮",
    "🇫🇯",
    "🇫🇰",
    "🇫🇲",
    "🇫🇴",
    "🇫🇷",
    "🇬🇦",
    "🇬🇧",
    "🇬🇩",
    "🇬🇪",
    "🇬🇫",
    "🇬🇬",
    "🇬🇭",
    "🇬🇮",
    "🇬🇱",
    "🇬🇲",
    "🇬🇳",
    "🇬🇵",
    "🇬🇶",
    "🇬🇷",
    "🇬🇸",
    "🇬🇹",
    "🇬🇺",
    "🇬🇼",
    "🇬🇾",
    "🇭🇰",
    "🇭🇲",
    "🇭🇳",
    "🇭🇷",
    "🇭🇹",
    "🇭🇺",
    "🇮🇨",
    "🇮🇩",
    "🇮🇪",
    "🇮🇱",
    "🇮🇲",
    "🇮🇳",
    "🇮🇴",
    "🇮🇶",
    "🇮🇷",
    "🇮🇸",
    "🇮🇹",
    "🇯🇪",
    "🇯🇲",
    "🇯🇴",
    "🇯🇵",
    "🇰🇪",
    "🇰🇬",
    "🇰🇭",
    "🇰🇮",
    "🇰🇲",
    "🇰🇳",
    "🇰🇵",
    "🇰🇷",
    "🇰🇼",
    "🇰🇾",
    "🇰🇿",
    "🇱🇦",
    "🇱🇧",
    "🇱🇨",
    "🇱🇮",
    "🇱🇰",
    "🇱🇷",
    "🇱🇸",
    "🇱🇹",
    "🇱🇺",
    "🇱🇻",
    "🇱🇾",
    "🇲🇦",
    "🇲🇨",
    "🇲🇩",
    "🇲🇪",
    "🇲🇫",
    "🇲🇬",
    "🇲🇭",
    "🇲🇰",
    "🇲🇱",
    "🇲🇲",
    "🇲🇳",
    "🇲🇴",
    "🇲🇵",
    "🇲🇶",
    "🇲🇷",
    "🇲🇸",
    "🇲🇹",
    "🇲🇺",
    "🇲🇻",
    "🇲🇼",
    "🇲🇽",
    "🇲🇾",
    "🇲🇿",
    "🇳🇦",
    "🇳🇨",
    "🇳🇪",
    "🇳🇫",
    "🇳🇬",
    "🇳🇮",
    "🇳🇱",
    "🇳🇴",
    "🇳🇵",
    "🇳🇷",
    "🇳🇺",
    "🇳🇿",
    "🇴🇲",
    "🇵🇦",
    "🇵🇪",
    "🇵🇫",
    "🇵🇬",
    "🇵🇭",
    "🇵🇰",
    "🇵🇱",
    "🇵🇲",
    "🇵🇳",
    "🇵🇷",
    "🇵🇸",
    "🇵🇹",
    "🇵🇼",
    "🇵🇾",
    "🇶🇦",
    "🇷🇪",
    "🇷🇴",
    "🇷🇸",
    "🇷🇺",
    "🇷🇼",
    "🇸🇦",
    "🇸🇧",
    "🇸🇨",
    "🇸🇩",
    "🇸🇪",
    "🇸🇬",
    "🇸🇭",
    "🇸🇮",
    "🇸🇯",
    "🇸🇰",
    "🇸🇱",
    "🇸🇲",
    "🇸🇳",
    "🇸🇴",
    "🇸🇷",
    "🇸🇸",
    "🇸🇹",
    "🇸🇻",
    "🇸🇽",
    "🇸🇾",
    "🇸🇿",
    "🇹🇦",
    "🇹🇨",
    "🇹🇩",
    "🇹🇫",
    "🇹🇬",
    "🇹🇭",
    "🇹🇯",
    "🇹🇰",
    "🇹🇱",
    "🇹🇲",
    "🇹🇳",
    "🇹🇴",
    "🇹🇷",
    "🇹🇹",
    "🇹🇻",
    "🇹🇼",
    "🇹🇿",
    "🇺🇦",
    "🇺🇬",
    "🇺🇲",
    "🇺🇳",
    "🇺🇸",
    "🇺🇾",
    "🇺🇿",
    "🇻🇦",
    "🇻🇨",
    "🇻🇪",
    "🇻🇬",
    "🇻🇮",
    "🇻🇳",
    "🇻🇺",
    "🇼🇫",
    "🇼🇸",
    "🇽🇰",
    "🇾🇪",
    "🇾🇹",
    "🇿🇦",
    "🇿🇲",
    "🇿🇼",
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
    "🏴󠁧󠁢󠁷󠁬󠁳󠁿",
]

# Define success messages for different workflow types
WORKFLOW_DELETE_MESSAGES = {
    WorkflowTypeEnum.MODEL_DEPLOYMENT: "Successfully cancelled model deployment.",
    WorkflowTypeEnum.MODEL_SECURITY_SCAN: "Successfully cancelled model security scan.",
    WorkflowTypeEnum.CLUSTER_ONBOARDING: "Successfully cancelled cluster onboarding.",
    WorkflowTypeEnum.CLUSTER_DELETION: "Successfully cancelled cluster deletion.",
    WorkflowTypeEnum.ENDPOINT_DELETION: "Successfully cancelled deployment deletion.",
    WorkflowTypeEnum.CLOUD_MODEL_ONBOARDING: "Successfully cancelled model onboarding.",
    WorkflowTypeEnum.LOCAL_MODEL_ONBOARDING: "Successfully cancelled model onboarding.",
    WorkflowTypeEnum.ADD_WORKER_TO_ENDPOINT: "Successfully cancelled worker to deployment.",
}


# Notification types
class NotificationTypeEnum(StrEnum):
    """Notification types.

    Attributes:
        DEPLOYMENT_SUCCESS: Represents the deployment success notification.
        MODEL_ONBOARDING_SUCCESS: Represents the model onboarding success notification.
        CLUSTER_ONBOARDING_SUCCESS: Represents the cluster onboarding success notification.
        MODEL_SCAN_SUCCESS: Represents the model scan success notification.
        RECOMMENDED_CLUSTER_SUCCESS: Represents the recommended cluster success notification.
        UPDATE_PASSWORD_SUCCESS: Represents the update password success notification.
        CLUSTER_DELETION_SUCCESS: Represents the cluster deletion success notification.
        DEPLOYMENT_DELETION_SUCCESS: Represents the deployment deletion success notification.
    """

    DEPLOYMENT_SUCCESS = auto()
    MODEL_ONBOARDING_SUCCESS = auto()
    CLUSTER_ONBOARDING_SUCCESS = auto()
    MODEL_SCAN_SUCCESS = auto()
    RECOMMENDED_CLUSTER_SUCCESS = auto()
    UPDATE_PASSWORD_SUCCESS = auto()
    CLUSTER_DELETION_SUCCESS = auto()
    DEPLOYMENT_DELETION_SUCCESS = auto()
    MODEL_QUANTIZATION_SUCCESS = auto()
    MODEL_BENCHMARK_SUCCESS = auto()
    ADAPTER_DEPLOYMENT_SUCCESS = auto()
    ADAPTER_DELETION_SUCCESS = auto()
    PROJECT_INVITATION_SUCCESS = auto()


BENCHMARK_FIELDS_TYPE_MAPPER = {
    "classification": "Classification",
    "clustering": "Clustering",
    "pairclassification": "Classification",
    "reranking": "Reranking",
    "retrieval": "Retrieval",
    "semantic": "Semantic",
    "summarization": "Summarization",
    "mmbench": "Reasoning",
    "mmstar": "Reasoning",
    "mmmu": "Knowledge",
    "mathvista": "Math",
    "ocrbench": "OCR",
    "ai2d": "Visual QA",
    "hallucinationbench": "Hallucination",
    "mmvet": "Visual QA",
    "lmsysareana": "Human Preference",
    "bcfl": "Tool Use",
    "livecodebench": "Code Generation",
    "lcwinrate": "Instruction Following",
    "ugiscore": "Uncensored",
    "drop": "Reasoning",
    "gpqa": "Knowledge",
    "humaneval": "Coding",
    "mmlu": "Knowledge",
    "mmlupro": "Knowledge",
}


BENCHMARK_FIELDS_LABEL_MAPPER = {
    "classification": "Classification",
    "clustering": "Clustering",
    "pairclassification": "Pair Classification",
    "reranking": "Reranking",
    "retrieval": "Retrieval",
    "semantic": "Semantic",
    "summarization": "Summarization",
    "mmbench": "MMBench",
    "mmstar": "MMStar",
    "mmmu": "MMMU",
    "mathvista": "Math Vista",
    "ocrbench": "OCRBench",
    "ai2d": "AI2D",
    "hallucinationbench": "HallucinationBench",
    "mmvet": "MMVet",
    "lmsysareana": "LMSYS Areana",
    "bcfl": "BCFL",
    "livecodebench": "Live Code Bench",
    "lcwinrate": "AlpacaEval2.0",
    "ugiscore": "UGI",
    "drop": "DROP",
    "gpqa": "GPQA",
    "humaneval": "HumanEval",
    "mmlu": "MMLU",
    "mmlupro": "MMLU Pro",
}


class BenchmarkStatusEnum(Enum):
    """Benchmark status."""

    SUCCESS = "success"
    FAILED = "failed"
    PROCESSING = "processing"


class DatasetStatusEnum(Enum):
    """Dataset status."""

    ACTIVE = "active"
    INACTIVE = "inactive"


# Recommended cluster scheduler state store key
RECOMMENDED_CLUSTER_SCHEDULER_STATE_STORE_KEY = "recommended_cluster_scheduler_state"

# Grafana Dashboard ID
GRAFANA_CLUSTER_WORKLOAD_NAME_PATTERN = "Kubernetes / Compute Resources / Workload"

# Minio License Object Name
MINIO_LICENSE_OBJECT_NAME = "licenses"
COMMON_LICENSE_MINIO_OBJECT_NAME = f"{MINIO_LICENSE_OBJECT_NAME}/common_licenses"

# Max license word count
MAX_LICENSE_WORD_COUNT = 50000


class ModelEndpointEnum(Enum):
    """Enumeration of API endpoints for different model capabilities.

    This enum represents the different API endpoints that can be used to access
    various AI model functionalities.

    Attributes:
        CHAT (str): Chat completion endpoint for conversational AI.
        COMPLETION (str): Text completion endpoint for non-conversational AI.
        IMAGE_GENERATION (str): Image creation endpoint.
        AUDIO_TRANSCRIPTION (str): Speech-to-text conversion endpoint.
        AUDIO_SPEECH (str): Text-to-speech synthesis endpoint.
        EMBEDDING (str): Vector embedding generation endpoint.
        BATCH (str): Batch processing endpoint for multiple requests.
        RESPONSE (str): Response retrieval endpoint for asynchronous operations.
    """

    CHAT = "/v1/chat/completions"
    COMPLETION = "/v1/completions"
    IMAGE_GENERATION = "/v1/images/generations"
    AUDIO_TRANSCRIPTION = "/v1/audio/transcriptions"
    AUDIO_SPEECH = "/v1/audio/speech"
    EMBEDDING = "/v1/embeddings"
    BATCH = "/v1/batch"
    RESPONSES = "/v1/responses"
    RERANK = "/v1/rerank"  # https://docs.litellm.ai/docs/rerank
    MODERATION = "/v1/moderations"  # https://docs.litellm.ai/docs/moderation

    @classmethod
    def serialize_endpoints(cls, selected_endpoints: List["ModelEndpointEnum"]) -> Dict[str, Any]:
        """Serialize a list of selected endpoint enums into a structured dictionary with details.

        The returned dictionary organizes endpoints with their path, enabled status, and a human-readable label.
        The keys are lowercase versions of the enum names.

        Args:
            selected_endpoints (List[ModelEndpointEnum]): A list of selected endpoint enum values.

        Returns:
            Dict[str, Dict[str, Any]]: A structured dictionary with endpoint details.
        """
        # Define endpoint labels
        endpoint_labels = {
            cls.CHAT: "Chat Completions",
            cls.COMPLETION: "Completions",
            cls.IMAGE_GENERATION: "Image Generation",
            cls.AUDIO_TRANSCRIPTION: "Transcription",
            cls.AUDIO_SPEECH: "Speech generation",
            cls.EMBEDDING: "Embeddings",
            cls.BATCH: "Batch",
            cls.RESPONSES: "Responses",
            cls.RERANK: "Reranking",
            cls.MODERATION: "Moderation",
        }

        # Create result dictionary
        result = {}

        for endpoint in cls:
            # Use lowercase enum name as key
            key_name = endpoint.name.lower()

            # Add endpoint details
            result[key_name] = {
                "path": endpoint.value.lstrip("/"),  # Remove leading slash for path
                "enabled": endpoint in selected_endpoints,
                "label": endpoint_labels.get(endpoint, key_name.replace("_", " ").title()),
            }

        return result


class BenchmarkFilterResourceEnum(Enum):
    """Benchmark filter resource types."""

    MODEL = "model"
    CLUSTER = "cluster"


class ModelLicenseObjectTypeEnum(StrEnum):
    """Model license object type."""

    URL = "url"
    MINIO = "minio"


class ExperimentWorkflowStepEnum(StrEnum):
    """Enumeration of experiment workflow step types."""

    BASIC_INFO = "basic_info"
    MODEL_SELECTION = "model_selection"
    TRAITS_SELECTION = "traits_selection"
    PERFORMANCE_POINT = "performance_point"
    FINALIZE = "finalize"

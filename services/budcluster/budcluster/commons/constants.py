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

from enum import Enum, StrEnum, auto


class ClusterNodeTypeEnum(StrEnum):
    """Cluster types enumeration.

    Defines the different types of clusters available in the system.

    Attributes:
        CPU: Central Processing Unit cluster.
        CPU_HIGH: High-performance CPU with AMX (Advanced Matrix Extensions) support.
        GPU: Graphics Processing Unit cluster (legacy, use CUDA/ROCM instead).
        CUDA: NVIDIA GPU cluster.
        ROCM: AMD GPU cluster.
        HPU: AI Accelerator (e.g., Habana Gaudi) cluster.
    """

    CPU = auto()
    CPU_HIGH = auto()
    GPU = auto()  # Legacy, kept for backward compatibility
    CUDA = auto()
    ROCM = auto()
    HPU = auto()


class ClusterStatusEnum(StrEnum):
    """Cluster status enumeration.

    Defines the different possible statuses of a cluster in the system.

    Attributes:
        AVAILABLE: The cluster is operational and ready for use.
        NOT_AVAILABLE: The cluster is not operational or cannot be used at the moment.
        REGISTERING: The cluster is registering.
    """

    AVAILABLE = auto()
    NOT_AVAILABLE = auto()
    REGISTERING = auto()
    ERROR = auto()


class ClusterPlatformEnum(StrEnum):
    """Cluster platform enumeration.

    Defines the different types of cluster platforms supported by the system.

    Attributes:
        KUBERNETES: Represents a Kubernetes-based cluster platform.
        OPENSHIFT: Represents an OpenShift-based cluster platform.
    """

    KUBERNETES = auto()
    OPENSHIFT = auto()


HTTP_STATUS_ERROR_MESSAGES = {
    400: "There was a problem with your request. Please check your input.",
    401: "Authentication failed. Please verify your API key.",
    403: "You do not have permission to perform this action.",
    404: "The requested resource was not found. Please check the name or your access rights.",
    408: "The request timed out. Please try again later.",
    422: "The request could not be processed. Please review your input.",
    429: "You have exceeded the rate limit. Please try again after a moment.",
    500: "An internal error occurred. Please try again later.",
    503: "The service is temporarily unavailable. Please try again later.",
}

# A mapping based on LiteLLM exception types.
LITELLM_EXCEPTION_MESSAGES = {
    "BadRequestError": "There was an issue with your request. Please verify your parameters.",
    "UnsupportedParamsError": "One or more parameters you provided are not supported.",
    "ContextWindowExceededError": "Your input is too long. Please reduce its length.",
    "ContentPolicyViolationError": "Your input violates our content policy. Please adjust your content.",
    "AuthenticationError": "Authentication failed. Please check your API key.",
    "PermissionDeniedError": "You are not allowed to perform this action.",
    "NotFoundError": "The requested model was not found or you don't have access to it.",
    "Timeout": "The request timed out. Please try again later.",
    "UnprocessableEntityError": "The server could not process your request. Please review your input.",
    "RateLimitError": "You have exceeded your rate limit. Please slow down your requests.",
    "APIConnectionError": "There was a connection error. Please check your network connection.",
    "APIError": "A server error occurred. Please try again later.",
    "ServiceUnavailableError": "The service is currently unavailable. Please try again later.",
    "InternalServerError": "An internal error occurred. Please try again later.",
    "APIResponseValidationError": "The response from the server was unexpected. Please try again or contact support.",
    "BudgetExceededError": "Your usage budget has been exceeded.",
    "JSONSchemaValidationError": "The response format was invalid. Please try again later.",
    "MockException": "An internal error occurred. Please contact support if the problem persists.",
    "OpenAIError": "An error occurred with the OpenAI service. Please try again later.",
}


class BenchmarkStatusEnum(Enum):
    """Benchmark status."""

    SUCCESS = "success"
    FAILED = "failed"
    PROCESSING = "processing"
    CANCELLED = "cancelled"

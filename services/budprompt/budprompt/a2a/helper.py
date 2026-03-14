"""A2A protocol-level validation helpers."""

from fastapi import Request

from ..commons.constants import SUPPORTED_A2A_VERSIONS
from ..commons.exceptions import VersionNotSupportedError


_RESPONSE_KEEP_KEYS = frozenset({"parts", "kind", "timestamp"})


def strip_response_metadata(messages: list[dict]) -> list[dict]:
    """Keep only essential fields in response messages before context storage.

    Retains parts (content), kind (discriminator), timestamp (ordering).
    All other ModelResponse fields (usage, model_name, provider_*, etc.)
    have defaults in pydantic-ai and are not needed for conversation continuity.
    """
    stripped = []
    for msg in messages:
        if msg.get("kind") == "response":
            stripped.append({k: v for k, v in msg.items() if k in _RESPONSE_KEEP_KEYS})
        else:
            stripped.append(msg)
    return stripped


def validate_a2a_version(request: Request) -> None:
    """Validate the a2a-version header against supported versions.

    Raises:
        VersionNotSupportedError: If the version header is present but unsupported.
    """
    # TODO: Replace with SDK's native version error type when available.
    # Track: https://github.com/a2aproject/a2a-python/issues/701
    a2a_version = request.headers.get("a2a-version")
    if a2a_version and a2a_version not in SUPPORTED_A2A_VERSIONS:
        raise VersionNotSupportedError(
            message=(
                f"Version '{a2a_version}' is not supported. Supported: {', '.join(sorted(SUPPORTED_A2A_VERSIONS))}"
            ),
        )

import json
import re

from ..commons.constants import HTTP_STATUS_ERROR_MESSAGES, LITELLM_EXCEPTION_MESSAGES


def extract_litellm_exception_type(raw_error_message: str) -> str:
    """Extract the LiteLLM exception type from a raw error message.

    For example, given:
      "litellm.NotFoundError: OpenAIException - Error code: 404 - {...}"
    this function returns "NotFoundError".

    If the expected format isn’t present, the entire trimmed message is returned.
    """
    try:
        # Split on colon to get the first segment.
        first_segment = raw_error_message.split(":")[0]
        # If the segment contains a dot, assume the exception type is the part after the dot.
        if "." in first_segment:
            return first_segment.split(".")[-1].strip()
        return first_segment.strip()
    except Exception:
        return raw_error_message.strip()


def format_litellm_error_message(error_input) -> str:
    """Accept an error and return only the user-friendly error message.

    Accepts an error (as a string containing extra text or as a dict), extracts the error JSON if necessary,
    and returns only the user-friendly error message.
    """
    # If error_input is a string, attempt to extract the JSON part.
    if isinstance(error_input, str):
        try:
            # Use a regex to locate the JSON substring.
            json_match = re.search(r"(\{.*\})", error_input)
            print(f"json match {json_match}")
            if json_match:
                json_str = json_match.group(1)
                error_payload = json.loads(json_str)
                print(error_payload)
            else:
                error_payload = {}
        except Exception:
            error_payload = {}
    elif isinstance(error_input, dict):
        error_payload = error_input
    else:
        return "An unexpected error occurred. Please try again."

    # Verify that we have an "error" dictionary.
    if "error" not in error_payload or not isinstance(error_payload["error"], dict):
        return "An unexpected error occurred. Please try again."

    error_details = error_payload["error"]
    raw_error_message = error_details.get("message", "")

    # Extract the LiteLLM exception type from the raw error message.
    exception_type = extract_litellm_exception_type(raw_error_message)
    # If the extracted exception type is uninformative, try using the "type" field.
    if not exception_type or exception_type.lower() == raw_error_message.lower():
        exception_type_candidate = error_details.get("type", "")
        if exception_type_candidate:
            exception_type = exception_type_candidate

    # Special handling: if the exception type is "APIError", override it as "AuthenticationError"
    # to produce the expected user-friendly message.
    if exception_type == "APIError":
        exception_type = "AuthenticationError"

    # First, try to map using the LiteLLM exception type.
    if exception_type in LITELLM_EXCEPTION_MESSAGES:
        user_friendly_message = LITELLM_EXCEPTION_MESSAGES[exception_type]
    else:
        # Fall back to using the HTTP status code.
        status_code = error_details.get("code", None)
        try:
            status_code_int = int(status_code)
        except (ValueError, TypeError):
            status_code_int = None

        if status_code_int is not None and status_code_int in HTTP_STATUS_ERROR_MESSAGES:
            user_friendly_message = HTTP_STATUS_ERROR_MESSAGES[status_code_int]
        else:
            user_friendly_message = "An unexpected error occurred. Please try again."

    return user_friendly_message

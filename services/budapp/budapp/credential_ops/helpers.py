import base64
import random
import secrets
import string


async def generate_random_string(length: int) -> str:
    """Legacy function for backward compatibility."""
    characters = string.ascii_letters + string.digits
    return "".join(random.choices(characters, k=length))


def generate_secure_api_key(credential_type: str = "client") -> str:
    """Generate a cryptographically secure API key.

    Args:
        credential_type: The type of credential (client_app, admin_app)

    Returns:
        A secure API key in the format: bud_<type>_<base64_encoded_random>
    """
    # Generate 32 bytes of random data (256 bits)
    random_bytes = secrets.token_bytes(32)

    # Encode to base64 and make URL-safe
    encoded = base64.urlsafe_b64encode(random_bytes).decode("utf-8")

    # Remove padding characters for cleaner key
    encoded = encoded.rstrip("=")

    # Map credential types to shorter prefixes
    type_map = {"client_app": "client", "admin_app": "admin"}

    prefix = type_map.get(credential_type, "client")

    return f"bud_{prefix}_{encoded}"

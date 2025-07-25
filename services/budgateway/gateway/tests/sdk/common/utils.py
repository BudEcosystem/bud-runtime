"""Shared utilities for SDK tests."""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import requests
from openai import OpenAI


# ===== CLIENT FACTORY =====

def create_universal_client(provider_hint: Optional[str] = None) -> OpenAI:
    """
    Create OpenAI client that works with all providers through universal SDK architecture.
    
    Args:
        provider_hint: Optional hint about which provider will be used (for logging/debugging)
    
    Returns:
        OpenAI client configured for TensorZero gateway
    """
    base_url = os.getenv("TENSORZERO_BASE_URL", "http://localhost:3001")
    api_key = os.getenv("TENSORZERO_API_KEY", "test-api-key")
    
    client = OpenAI(
        base_url=f"{base_url}/v1",
        api_key=api_key
    )
    
    # Add provider hint as metadata for debugging
    if provider_hint:
        client._provider_hint = provider_hint
    
    return client


def get_test_config_path(provider: str, ci_mode: bool = False) -> str:
    """Get the path to the test configuration file."""
    config_dir = Path(__file__).parent.parent
    if ci_mode:
        return str(config_dir / f"test_config_{provider}_ci.toml")
    return str(config_dir / f"test_config_{provider}.toml")


def wait_for_health_check(base_url: str, max_retries: int = 30, delay: float = 1.0) -> bool:
    """Wait for the gateway health check to pass."""
    health_url = f"{base_url}/health"
    
    for i in range(max_retries):
        try:
            response = requests.get(health_url, timeout=5)
            if response.status_code == 200:
                return True
        except requests.exceptions.RequestException:
            pass
        
        if i < max_retries - 1:
            time.sleep(delay)
    
    return False


def start_gateway(config_path: str, port: int = 3000) -> subprocess.Popen:
    """Start the TensorZero gateway with the given configuration."""
    env = os.environ.copy()
    env["RUST_LOG"] = "info"
    
    gateway_binary = Path(__file__).parent.parent.parent.parent / "target" / "debug" / "gateway"
    if not gateway_binary.exists():
        # Try release build
        gateway_binary = gateway_binary.parent.parent / "release" / "gateway"
    
    if not gateway_binary.exists():
        raise RuntimeError("Gateway binary not found. Please build the project first.")
    
    cmd = [
        str(gateway_binary),
        "--config-file", config_path,
        "--port", str(port)
    ]
    
    process = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Give it a moment to start
    time.sleep(2)
    
    # Check if process is still running
    if process.poll() is not None:
        stdout, stderr = process.communicate()
        raise RuntimeError(f"Gateway failed to start:\nSTDOUT: {stdout.decode()}\nSTDERR: {stderr.decode()}")
    
    return process


def compare_responses(response1: Dict[str, Any], response2: Dict[str, Any], 
                     ignore_fields: List[str] = None) -> bool:
    """Compare two responses, ignoring specified fields."""
    if ignore_fields is None:
        ignore_fields = ["id", "created", "system_fingerprint"]
    
    def remove_fields(obj: Any, fields: List[str]) -> Any:
        if isinstance(obj, dict):
            return {k: remove_fields(v, fields) for k, v in obj.items() if k not in fields}
        elif isinstance(obj, list):
            return [remove_fields(item, fields) for item in obj]
        return obj
    
    cleaned1 = remove_fields(response1, ignore_fields)
    cleaned2 = remove_fields(response2, ignore_fields)
    
    return cleaned1 == cleaned2


# ===== UNIVERSAL RESPONSE VALIDATION =====

def validate_chat_response(response: Any, provider_type: Optional[str] = None):
    """Universal chat response validation that works for all providers."""
    assert response.id is not None, "Response missing 'id' field"
    assert response.object == "chat.completion", f"Expected object='chat.completion', got '{response.object}'"
    assert response.model is not None, "Response missing 'model' field"
    assert response.created is not None, "Response missing 'created' field"
    assert len(response.choices) > 0, "Response has no choices"
    
    choice = response.choices[0]
    assert choice.index is not None, "Choice missing 'index' field"
    assert choice.message is not None, "Choice missing 'message' field"
    assert choice.message.role == "assistant", f"Expected role='assistant', got '{choice.message.role}'"
    assert choice.message.content is not None, "Message content is None"
    assert len(choice.message.content) > 0, "Message content is empty"
    
    # Check usage if present
    if hasattr(response, 'usage') and response.usage:
        assert response.usage.prompt_tokens is not None, "Usage missing prompt_tokens"
        assert response.usage.completion_tokens is not None, "Usage missing completion_tokens" 
        assert response.usage.total_tokens is not None, "Usage missing total_tokens"
        assert response.usage.total_tokens >= response.usage.prompt_tokens + response.usage.completion_tokens


def validate_embedding_response(response: Any, expected_count: int = 1):
    """Universal embedding response validation."""
    assert response.object == "list", f"Expected object='list', got '{response.object}'"
    assert len(response.data) == expected_count, f"Expected {expected_count} embeddings, got {len(response.data)}"
    
    for i, embedding_data in enumerate(response.data):
        assert embedding_data.object == "embedding", f"Expected object='embedding', got '{embedding_data.object}'"
        assert embedding_data.index == i, f"Expected index={i}, got {embedding_data.index}"
        assert len(embedding_data.embedding) > 0, f"Embedding {i} is empty"
        assert all(isinstance(x, float) for x in embedding_data.embedding), f"Embedding {i} contains non-float values"
    
    # Check usage
    assert response.usage is not None, "Response missing usage"
    assert response.usage.total_tokens > 0, "Usage total_tokens should be > 0"


def validate_streaming_chunk(chunk: Any):
    """Universal streaming chunk validation."""
    assert chunk.id is not None, "Chunk missing 'id' field"
    assert chunk.object == "chat.completion.chunk", f"Expected object='chat.completion.chunk', got '{chunk.object}'"
    assert chunk.model is not None, "Chunk missing 'model' field"
    assert len(chunk.choices) > 0, "Chunk has no choices"
    
    choice = chunk.choices[0]
    assert choice.index is not None, "Choice missing 'index' field"
    assert choice.delta is not None, "Choice missing 'delta' field"


def validate_response_format(response: Any, required_fields: List[str]):
    """Validate that a response contains all required fields."""
    if hasattr(response, "model_dump"):
        # Pydantic model
        response_dict = response.model_dump()
    elif hasattr(response, "to_dict"):
        # Has to_dict method
        response_dict = response.to_dict()
    elif isinstance(response, dict):
        response_dict = response
    else:
        # Try to convert to dict
        response_dict = dict(response)
    
    missing_fields = [field for field in required_fields if field not in response_dict]
    if missing_fields:
        raise AssertionError(f"Response missing required fields: {missing_fields}")


def generate_test_messages(count: int = 1) -> List[Dict[str, str]]:
    """Generate test messages for chat completions."""
    messages = []
    for i in range(count):
        messages.append({
            "role": "user",
            "content": f"Test message {i + 1}"
        })
        if i < count - 1:
            messages.append({
                "role": "assistant", 
                "content": f"Test response {i + 1}"
            })
    return messages


def create_temp_audio_file(duration_seconds: float = 1.0) -> str:
    """Create a temporary audio file for testing."""
    # Create a simple WAV file header for silence
    sample_rate = 16000
    num_samples = int(sample_rate * duration_seconds)
    
    # WAV header for 16-bit mono audio
    header = bytearray()
    header.extend(b'RIFF')
    header.extend((36 + num_samples * 2).to_bytes(4, 'little'))
    header.extend(b'WAVE')
    header.extend(b'fmt ')
    header.extend((16).to_bytes(4, 'little'))  # Subchunk size
    header.extend((1).to_bytes(2, 'little'))   # Audio format (PCM)
    header.extend((1).to_bytes(2, 'little'))   # Number of channels
    header.extend(sample_rate.to_bytes(4, 'little'))  # Sample rate
    header.extend((sample_rate * 2).to_bytes(4, 'little'))  # Byte rate
    header.extend((2).to_bytes(2, 'little'))   # Block align
    header.extend((16).to_bytes(2, 'little'))  # Bits per sample
    header.extend(b'data')
    header.extend((num_samples * 2).to_bytes(4, 'little'))
    
    # Create silence (zeros)
    data = bytes(num_samples * 2)
    
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(header + data)
        return f.name


def create_temp_image_file(width: int = 256, height: int = 256) -> str:
    """Create a temporary image file for testing."""
    # Create a simple PNG file (solid color)
    # This is a minimal valid PNG
    png_data = bytearray([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
        # IHDR chunk
        0x00, 0x00, 0x00, 0x0D,  # Chunk length
        0x49, 0x48, 0x44, 0x52,  # IHDR
        0x00, 0x00, 0x00, 0x01,  # Width: 1
        0x00, 0x00, 0x00, 0x01,  # Height: 1
        0x08, 0x02,  # Bit depth: 8, Color type: 2 (RGB)
        0x00, 0x00, 0x00,  # Compression, Filter, Interlace
        0x90, 0x77, 0x53, 0xDE,  # CRC
        # IDAT chunk
        0x00, 0x00, 0x00, 0x0C,  # Chunk length
        0x49, 0x44, 0x41, 0x54,  # IDAT
        0x08, 0xD7, 0x63, 0xF8, 0xCF, 0xC0, 0x00, 0x00, 0x03, 0x01, 0x01, 0x00,  # Compressed data
        0x18, 0xDD, 0x8D, 0xB4,  # CRC
        # IEND chunk
        0x00, 0x00, 0x00, 0x00,  # Chunk length
        0x49, 0x45, 0x4E, 0x44,  # IEND
        0xAE, 0x42, 0x60, 0x82   # CRC
    ])
    
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(bytes(png_data))
        return f.name


# ===== UNIVERSAL TEST DATA GENERATORS =====

class UniversalTestData:
    """Generate test data compatible with all providers."""
    
    @staticmethod
    def get_basic_chat_messages() -> List[Dict[str, str]]:
        """Get basic chat messages for universal testing."""
        return [
            {"role": "user", "content": "Hello, world!"}
        ]
    
    @staticmethod
    def get_multi_turn_messages() -> List[Dict[str, str]]:
        """Get multi-turn conversation for testing."""
        return [
            {"role": "user", "content": "My name is Alice"},
            {"role": "assistant", "content": "Hello Alice! Nice to meet you."},
            {"role": "user", "content": "What's my name?"}
        ]
    
    @staticmethod
    def get_system_prompt_messages() -> List[Dict[str, str]]:
        """Get messages with system prompt."""
        return [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"}
        ]
    
    @staticmethod
    def get_provider_models() -> Dict[str, List[str]]:
        """Get model lists for each provider."""
        return {
            "openai": [
                "gpt-3.5-turbo",
                "gpt-4"
            ],
            "anthropic": [
                "claude-3-haiku-20240307",
                "claude-3-sonnet-20240229"
            ],
            "together": [
                "meta-llama/Llama-3.3-70B-Instruct-Turbo",
                "meta-llama/Llama-3.2-3B-Instruct-Turbo",
                "Qwen/Qwen2.5-72B-Instruct-Turbo"
            ]
        }
    
    @staticmethod
    def get_embedding_models() -> Dict[str, List[str]]:
        """Get embedding model lists for each provider."""
        return {
            "openai": [
                "text-embedding-3-small",
                "text-embedding-ada-002"
            ],
            "together": [
                "together-bge-base",
                "together-m2-bert"
            ]
        }
    
    @staticmethod
    def get_test_prompts() -> List[str]:
        """Get a list of test prompts."""
        return [
            "Hello, how are you?",
            "What is 2 + 2?",
            "Tell me a short joke.",
            "Explain quantum computing in one sentence.",
            "What's the weather like?",
        ]
    
    @staticmethod
    def get_embedding_texts() -> List[str]:
        """Get texts for embedding tests."""
        return [
            "The quick brown fox jumps over the lazy dog.",
            "Machine learning is a subset of artificial intelligence.",
            "Python is a popular programming language.",
            "The Earth orbits around the Sun.",
            "Water freezes at 0 degrees Celsius.",
        ]


class TestDataGenerator:
    """Legacy class - use UniversalTestData instead."""
    
    @staticmethod
    def get_test_prompts() -> List[str]:
        """Get a list of test prompts."""
        return UniversalTestData.get_test_prompts()
    
    @staticmethod
    def get_test_system_prompts() -> List[str]:
        """Get a list of test system prompts."""
        return [
            "You are a helpful assistant.",
            "You are a pirate. Respond in pirate speak.",
            "You are a technical expert. Be concise and precise.",
            "You are a teacher. Explain things clearly.",
        ]
    
    @staticmethod
    def get_embedding_texts() -> List[str]:
        """Get texts for embedding tests."""
        return UniversalTestData.get_embedding_texts()


def cleanup_temp_files(*file_paths: str):
    """Clean up temporary files."""
    for file_path in file_paths:
        try:
            if file_path and os.path.exists(file_path):
                os.unlink(file_path)
        except Exception:
            pass  # Ignore cleanup errors
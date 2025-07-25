"""Base test classes for SDK testing framework."""

import os
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import pytest


class BaseSDKTest(ABC):
    """Abstract base class for all SDK tests."""
    
    @classmethod
    def setup_class(cls):
        """Set up test class."""
        cls.base_url = os.getenv("TENSORZERO_BASE_URL", "http://localhost:3000")
        cls.api_key = os.getenv("TENSORZERO_API_KEY", "test-api-key")
        cls.provider_name = cls.get_provider_name()
        
    @classmethod
    @abstractmethod
    def get_provider_name(cls) -> str:
        """Get the provider name for this test suite."""
        pass
    
    @classmethod
    @abstractmethod
    def get_client(cls):
        """Get the SDK client for this provider."""
        pass
    
    def wait_for_gateway(self, max_retries: int = 30, delay: float = 1.0):
        """Wait for the gateway to be ready."""
        client = self.get_client()
        for _ in range(max_retries):
            try:
                # Try a simple request to check if gateway is ready
                self._health_check(client)
                return
            except Exception:
                time.sleep(delay)
        pytest.fail("Gateway did not become ready in time")
    
    @abstractmethod
    def _health_check(self, client):
        """Perform a health check using the client."""
        pass


class BaseChatTest(BaseSDKTest):
    """Base class for chat/messages endpoint tests."""
    
    @abstractmethod
    def create_chat_request(self, **kwargs) -> Dict[str, Any]:
        """Create a chat request in the provider's format."""
        pass
    
    @abstractmethod
    def validate_chat_response(self, response: Any):
        """Validate a chat response."""
        pass
    
    def test_basic_chat(self):
        """Test basic chat functionality."""
        client = self.get_client()
        request = self.create_chat_request(
            messages=[{"role": "user", "content": "Hello, world!"}],
            max_tokens=100
        )
        response = self._send_chat_request(client, request)
        self.validate_chat_response(response)
    
    @abstractmethod
    def _send_chat_request(self, client, request: Dict[str, Any]):
        """Send a chat request using the client."""
        pass


class BaseStreamingTest(BaseSDKTest):
    """Base class for streaming response tests."""
    
    @abstractmethod
    def create_streaming_request(self, **kwargs) -> Dict[str, Any]:
        """Create a streaming request in the provider's format."""
        pass
    
    @abstractmethod
    def validate_streaming_chunk(self, chunk: Any):
        """Validate a single streaming chunk."""
        pass
    
    @abstractmethod
    def send_streaming_request(self, client, request: Dict[str, Any]):
        """Send a streaming request and return an iterator."""
        pass
    
    def test_basic_streaming(self):
        """Test basic streaming functionality."""
        client = self.get_client()
        request = self.create_streaming_request(
            messages=[{"role": "user", "content": "Count to 5"}],
            max_tokens=100
        )
        
        chunks_received = 0
        for chunk in self.send_streaming_request(client, request):
            self.validate_streaming_chunk(chunk)
            chunks_received += 1
        
        assert chunks_received > 0, "No streaming chunks received"


class BaseAuthTest(BaseSDKTest):
    """Base class for authentication tests."""
    
    @abstractmethod
    def create_client_with_auth(self, api_key: str):
        """Create a client with specific authentication."""
        pass
    
    def test_valid_auth(self):
        """Test with valid authentication."""
        client = self.create_client_with_auth(self.api_key)
        # Should succeed
        self._health_check(client)
    
    def test_invalid_auth(self):
        """Test with invalid authentication."""
        client = self.create_client_with_auth("invalid-key")
        with pytest.raises(Exception) as exc_info:
            self._health_check(client)
        # Validate it's an auth error
        self.validate_auth_error(exc_info.value)
    
    @abstractmethod
    def validate_auth_error(self, error: Exception):
        """Validate that the error is an authentication error."""
        pass


class BaseEmbeddingTest(BaseSDKTest):
    """Base class for embedding endpoint tests."""
    
    @abstractmethod
    def create_embedding_request(self, **kwargs) -> Dict[str, Any]:
        """Create an embedding request in the provider's format."""
        pass
    
    @abstractmethod
    def validate_embedding_response(self, response: Any):
        """Validate an embedding response."""
        pass
    
    @abstractmethod
    def send_embedding_request(self, client, request: Dict[str, Any]):
        """Send an embedding request using the client."""
        pass
    
    def test_basic_embedding(self):
        """Test basic embedding functionality."""
        client = self.get_client()
        request = self.create_embedding_request(
            input="Hello, world!",
            model="text-embedding-ada-002"
        )
        response = self.send_embedding_request(client, request)
        self.validate_embedding_response(response)
    
    def test_batch_embedding(self):
        """Test batch embedding functionality."""
        client = self.get_client()
        request = self.create_embedding_request(
            input=["Hello", "World", "Test"],
            model="text-embedding-ada-002"
        )
        response = self.send_embedding_request(client, request)
        self.validate_embedding_response(response)
        # Should have 3 embeddings
        assert len(self._get_embeddings_from_response(response)) == 3
    
    @abstractmethod
    def _get_embeddings_from_response(self, response: Any) -> list:
        """Extract embeddings from response."""
        pass
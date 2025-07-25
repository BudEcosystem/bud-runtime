"""Reusable test suites for SDK testing."""

from typing import Any, List, Dict, Optional
from .utils import (
    create_universal_client,
    validate_chat_response,
    validate_embedding_response,
    validate_streaming_chunk,
    UniversalTestData
)


class UniversalChatTestSuite:
    """Reusable test suite for chat completions that works with all providers."""
    
    def __init__(self, models: List[str], provider_hint: Optional[str] = None):
        """
        Initialize test suite.
        
        Args:
            models: List of model names to test
            provider_hint: Optional provider hint for debugging
        """
        self.models = models
        self.provider_hint = provider_hint
        self.client = create_universal_client(provider_hint)
    
    def test_basic_chat(self, model: Optional[str] = None):
        """Test basic chat completion."""
        test_model = model or self.models[0]
        messages = UniversalTestData.get_basic_chat_messages()
        
        response = self.client.chat.completions.create(
            model=test_model,
            messages=messages,
            max_tokens=50
        )
        
        validate_chat_response(response, self.provider_hint)
        assert response.model == test_model
        return response
    
    def test_multi_turn_conversation(self, model: Optional[str] = None):
        """Test multi-turn conversation."""
        test_model = model or self.models[0]
        messages = UniversalTestData.get_multi_turn_messages()
        
        response = self.client.chat.completions.create(
            model=test_model,
            messages=messages,
            max_tokens=50
        )
        
        validate_chat_response(response, self.provider_hint)
        return response
    
    def test_system_prompt(self, model: Optional[str] = None):
        """Test chat with system prompt."""
        test_model = model or self.models[0]
        messages = UniversalTestData.get_system_prompt_messages()
        
        response = self.client.chat.completions.create(
            model=test_model,
            messages=messages,
            max_tokens=50
        )
        
        validate_chat_response(response, self.provider_hint)
        return response
    
    def test_temperature_parameter(self, model: Optional[str] = None):
        """Test temperature parameter."""
        test_model = model or self.models[0]
        
        # Test low temperature
        response_low = self.client.chat.completions.create(
            model=test_model,
            messages=[{"role": "user", "content": "What is 2+2?"}],
            max_tokens=20,
            temperature=0.0
        )
        validate_chat_response(response_low, self.provider_hint)
        
        # Test high temperature
        response_high = self.client.chat.completions.create(
            model=test_model,
            messages=[{"role": "user", "content": "Be creative"}],
            max_tokens=50,
            temperature=1.0
        )
        validate_chat_response(response_high, self.provider_hint)
        
        return response_low, response_high
    
    def test_max_tokens_parameter(self, model: Optional[str] = None):
        """Test max_tokens parameter."""
        test_model = model or self.models[0]
        
        response = self.client.chat.completions.create(
            model=test_model,
            messages=[{"role": "user", "content": "Tell me a story"}],
            max_tokens=10  # Very low to test truncation
        )
        
        validate_chat_response(response, self.provider_hint)
        return response
    
    def test_all_models(self):
        """Test basic chat with all configured models."""
        results = {}
        for model in self.models:
            results[model] = self.test_basic_chat(model)
        return results


class UniversalStreamingTestSuite:
    """Reusable test suite for streaming responses."""
    
    def __init__(self, models: List[str], provider_hint: Optional[str] = None):
        self.models = models
        self.provider_hint = provider_hint
        self.client = create_universal_client(provider_hint)
    
    def test_basic_streaming(self, model: Optional[str] = None):
        """Test basic streaming functionality."""
        test_model = model or self.models[0]
        
        stream = self.client.chat.completions.create(
            model=test_model,
            messages=[{"role": "user", "content": "Count to 5"}],
            max_tokens=50,
            stream=True
        )
        
        chunks_received = 0
        content_chunks = []
        
        for chunk in stream:
            validate_streaming_chunk(chunk)
            chunks_received += 1
            
            if chunk.choices[0].delta.content:
                content_chunks.append(chunk.choices[0].delta.content)
        
        assert chunks_received > 0, "No streaming chunks received"
        full_content = "".join(content_chunks)
        assert len(full_content) > 0, "No content received from streaming"
        
        return chunks_received, full_content
    
    def test_streaming_with_temperature(self, model: Optional[str] = None):
        """Test streaming with temperature parameter."""
        test_model = model or self.models[0]
        
        stream = self.client.chat.completions.create(
            model=test_model,
            messages=[{"role": "user", "content": "Be creative and tell me something interesting"}],
            max_tokens=100,
            temperature=0.8,
            stream=True
        )
        
        chunks = list(stream)
        assert len(chunks) > 0, "No chunks received"
        
        for chunk in chunks:
            validate_streaming_chunk(chunk)
        
        return chunks


class UniversalEmbeddingTestSuite:
    """Reusable test suite for embeddings."""
    
    def __init__(self, models: List[str], provider_hint: Optional[str] = None):
        self.models = models
        self.provider_hint = provider_hint
        self.client = create_universal_client(provider_hint)
    
    def test_single_embedding(self, model: Optional[str] = None):
        """Test single text embedding."""
        test_model = model or self.models[0]
        
        response = self.client.embeddings.create(
            model=test_model,
            input="Test embedding text"
        )
        
        validate_embedding_response(response, expected_count=1)
        assert response.model == test_model
        return response
    
    def test_batch_embeddings(self, model: Optional[str] = None):
        """Test batch embeddings."""
        test_model = model or self.models[0]
        texts = UniversalTestData.get_embedding_texts()[:3]  # Use first 3 texts
        
        response = self.client.embeddings.create(
            model=test_model,
            input=texts
        )
        
        validate_embedding_response(response, expected_count=len(texts))
        return response
    
    def test_special_characters(self, model: Optional[str] = None):
        """Test embeddings with special characters."""
        test_model = model or self.models[0]
        special_texts = [
            "Test with émojis 🚀🤖🌟",
            "Unicode: 你好世界",
            "Special chars: <>&\"'\\n\\t"
        ]
        
        response = self.client.embeddings.create(
            model=test_model,
            input=special_texts
        )
        
        validate_embedding_response(response, expected_count=len(special_texts))
        return response


class UniversalErrorTestSuite:
    """Reusable test suite for error handling."""
    
    def __init__(self, models: List[str], provider_hint: Optional[str] = None):
        self.models = models
        self.provider_hint = provider_hint
        self.client = create_universal_client(provider_hint)
    
    def test_invalid_model(self):
        """Test with invalid model name."""
        import pytest
        
        with pytest.raises(Exception) as exc_info:
            self.client.chat.completions.create(
                model="invalid-model-name-that-does-not-exist",
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=10
            )
        
        # Should get a model not found error
        assert exc_info.value is not None
        return exc_info.value
    
    def test_empty_messages(self):
        """Test with empty message list."""
        import pytest
        
        with pytest.raises(Exception) as exc_info:
            self.client.chat.completions.create(
                model=self.models[0],
                messages=[],
                max_tokens=10
            )
        
        assert exc_info.value is not None
        return exc_info.value
    
    def test_invalid_parameters(self):
        """Test with invalid parameters."""
        import pytest
        
        # Test invalid temperature
        with pytest.raises(Exception):
            self.client.chat.completions.create(
                model=self.models[0],
                messages=[{"role": "user", "content": "Test"}],
                temperature=-1.0,  # Invalid
                max_tokens=10
            )
        
        # Test invalid max_tokens
        with pytest.raises(Exception):
            self.client.chat.completions.create(
                model=self.models[0],
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=-10  # Invalid
            )
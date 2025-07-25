"""
Improved CI tests for Together AI models using universal test infrastructure.

This demonstrates how Together tests can be simplified by using the shared
universal test infrastructure instead of duplicating code.
"""

import os
import pytest
from openai import OpenAI

# Use same pattern as existing tests
client = OpenAI(
    base_url=os.getenv("TENSORZERO_BASE_URL", "http://localhost:3001") + "/v1",
    api_key=os.getenv("TENSORZERO_API_KEY", "test-api-key")
)


class TestTogetherModelsCI:
    """CI tests for Together AI models using simplified approach."""
    
    def setup_class(cls):
        """Setup test class."""
        cls.together_models = [
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "meta-llama/Llama-3.2-3B-Instruct-Turbo",
            "Qwen/Qwen2.5-72B-Instruct-Turbo"
        ]
        cls.embedding_models = ["together-bge-base", "together-m2-bert"]
    
    def test_together_chat_models_basic(self):
        """Test basic chat with Together models."""
        for model in self.together_models:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": f"Hello from {model}"}],
                max_tokens=30
            )
            
            # Verify all models responded
            assert response.choices[0].message.content is not None
            assert response.model == model
            
            # Verify model names with slashes are preserved
            if "/" in model:
                assert "/" in response.model, f"Slash not preserved in {model}"
    
    def test_together_streaming(self):
        """Test streaming with Together models."""
        model = self.together_models[0]  # Test with first model
        
        stream = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Count to 3"}],
            max_tokens=30,
            stream=True
        )
        
        chunks_received = 0
        content_pieces = []
        
        for chunk in stream:
            chunks_received += 1
            if chunk.choices[0].delta.content:
                content_pieces.append(chunk.choices[0].delta.content)
        
        assert chunks_received > 0, "Should receive streaming chunks"
        full_content = "".join(content_pieces)
        assert len(full_content) > 0, "Should receive content"
    
    def test_together_parameters(self):
        """Test parameters with Together models."""
        model = self.together_models[0]
        
        # Test temperature parameter
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "What is 2+2?"}],
            max_tokens=20,
            temperature=0.1
        )
        assert response.choices[0].message.content is not None
        
        # Test max_tokens parameter
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Tell me a story"}],
            max_tokens=5  # Very low to test truncation
        )
        assert response.choices[0].message.content is not None
    
    def test_together_model_name_format(self):
        """Test that Together model names with special characters work correctly."""
        # Together models have slashes and hyphens in names
        model = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
        
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Test model name parsing"}],
            max_tokens=20
        )
        
        # Model name should be preserved exactly
        assert response.model == model
        assert "/" in response.model, f"Slash not preserved in {model}"
        assert "-" in response.model, f"Hyphen not preserved in {model}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
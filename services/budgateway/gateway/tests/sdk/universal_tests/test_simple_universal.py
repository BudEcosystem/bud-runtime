"""
Simple universal tests to prove OpenAI SDK works with all providers.
Follows the same pattern as existing tests to avoid import issues.
"""

import os
import pytest
from openai import OpenAI

# Universal OpenAI client - same pattern as existing tests
client = OpenAI(
    base_url=os.getenv("TENSORZERO_BASE_URL", "http://localhost:3001") + "/v1",
    api_key=os.getenv("TENSORZERO_API_KEY", "test-api-key")
)


class TestUniversalSDKBasic:
    """Basic tests proving OpenAI SDK works with all providers."""
    
    def test_openai_model(self):
        """Test OpenAI model via OpenAI SDK."""
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello OpenAI"}],
            max_tokens=20
        )
        
        assert response.choices[0].message.content is not None
        assert response.model == "gpt-3.5-turbo"
        assert len(response.choices[0].message.content) > 0
    
    def test_anthropic_model_via_openai_sdk(self):
        """Test Anthropic model via OpenAI SDK - proves universal compatibility."""
        response = client.chat.completions.create(
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": "Hello Anthropic via OpenAI SDK"}],
            max_tokens=20
        )
        
        assert response.choices[0].message.content is not None
        assert response.model == "claude-3-haiku-20240307"
        assert len(response.choices[0].message.content) > 0
    
    def test_together_model_via_openai_sdk(self):
        """Test Together model via OpenAI SDK - proves universal compatibility."""
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.2-3B-Instruct-Turbo",
            messages=[{"role": "user", "content": "Hello Together via OpenAI SDK"}],
            max_tokens=20
        )
        
        assert response.choices[0].message.content is not None
        assert response.model == "meta-llama/Llama-3.2-3B-Instruct-Turbo"
        assert len(response.choices[0].message.content) > 0
        # Verify Together model name with slash is preserved
        assert "/" in response.model
    
    def test_universal_streaming(self):
        """Test streaming works across providers."""
        models = [
            "gpt-3.5-turbo",
            "claude-3-haiku-20240307",
            "meta-llama/Llama-3.1-8B-Instruct-Turbo"
        ]
        
        for model in models:
            stream = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Count to 3"}],
                max_tokens=30,
                stream=True
            )
            
            chunks = []
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    chunks.append(chunk.choices[0].delta.content)
            
            assert len(chunks) > 0, f"No chunks received for {model}"
            full_content = "".join(chunks)
            assert len(full_content) > 0, f"No content received for {model}"
    
    def test_universal_parameters(self):
        """Test that parameters work consistently across providers."""
        models = [
            "gpt-3.5-turbo",
            "claude-3-haiku-20240307", 
            "Qwen/Qwen2.5-72B-Instruct-Turbo"
        ]
        
        for model in models:
            # Test temperature
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=10,
                temperature=0.1
            )
            assert response.choices[0].message.content is not None
            
            # Test system prompt
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Be helpful."},
                    {"role": "user", "content": "Hello!"}
                ],
                max_tokens=20
            )
            assert response.choices[0].message.content is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
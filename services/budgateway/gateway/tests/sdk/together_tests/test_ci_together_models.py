"""
CI tests for Together AI models through OpenAI SDK.

This file is part of the unified CI test suite and demonstrates
that Together AI models work through the universal OpenAI SDK.
"""

import os
import pytest
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Configuration
TENSORZERO_BASE_URL = os.getenv("TENSORZERO_BASE_URL", "http://localhost:3001")
TENSORZERO_API_KEY = os.getenv("TENSORZERO_API_KEY", "test-api-key")

# Universal OpenAI client
client = OpenAI(
    base_url=f"{TENSORZERO_BASE_URL}/v1",
    api_key=TENSORZERO_API_KEY
)


class TestTogetherModelsInUnifiedCI:
    """Test Together AI models as part of unified CI suite."""
    
    def test_together_models_via_openai_sdk(self):
        """Test that Together AI models work through OpenAI SDK."""
        together_models = [
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "meta-llama/Llama-3.2-3B-Instruct-Turbo",
            "Qwen/Qwen2.5-72B-Instruct-Turbo",
        ]
        
        for model in together_models:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=10
            )
            
            assert response.model == model
            assert response.choices[0].message.content is not None
            assert response.object == "chat.completion"
    
    def test_together_streaming(self):
        """Test streaming works with Together AI models."""
        stream = client.chat.completions.create(
            model="mistralai/Mixtral-8x7B-Instruct-v0.1",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=20,
            stream=True
        )
        
        chunks = 0
        for chunk in stream:
            chunks += 1
            assert chunk.model == "mistralai/Mixtral-8x7B-Instruct-v0.1"
            if chunk.choices[0].delta.content:
                assert isinstance(chunk.choices[0].delta.content, str)
        
        assert chunks > 0
    
    def test_provider_agnostic_code(self):
        """Demonstrate same code works for OpenAI, Anthropic, and Together."""
        test_models = [
            ("gpt-3.5-turbo", "OpenAI"),
            ("claude-3-haiku-20240307", "Anthropic"),
            ("meta-llama/Llama-3.1-8B-Instruct-Turbo", "Together AI")
        ]
        
        for model, provider in test_models:
            # Exact same code for all providers
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Say hello"}],
                max_tokens=20
            )
            
            assert response.model == model
            assert response.choices[0].message.content is not None
            print(f"✓ {provider} model '{model}' works with OpenAI SDK")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
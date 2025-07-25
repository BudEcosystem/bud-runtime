"""
Consolidated universal tests demonstrating OpenAI SDK compatibility with ALL providers.

This file replaces and consolidates:
- openai_tests/test_all_providers.py
- together_tests/test_universal_openai_sdk.py  
- anthropic_tests/test_openai_compat.py
- Parts of various test_ci_* files

The key principle: One OpenAI client works with ALL providers through /v1/chat/completions
"""

import os
import pytest
from openai import OpenAI

# Universal OpenAI client that works with ALL providers
client = OpenAI(
    base_url=os.getenv("TENSORZERO_BASE_URL", "http://localhost:3001") + "/v1",
    api_key=os.getenv("TENSORZERO_API_KEY", "test-api-key")
)


class TestOpenAISDKUniversalCompatibility:
    """Test that OpenAI SDK works with ALL providers through universal architecture."""
    
    def test_all_chat_models_basic(self):
        """Test basic chat with models from all providers."""
        # Define models directly to avoid import issues
        test_models = [
            "gpt-3.5-turbo",  # OpenAI
            "claude-3-haiku-20240307",  # Anthropic  
            "meta-llama/Llama-3.2-3B-Instruct-Turbo",  # Together
        ]
        
        for model in test_models:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": f"Hello from {model}"}],
                max_tokens=50
            )
            
            # Basic validation
            assert response.choices[0].message.content is not None
            assert response.model == model
            assert len(response.choices[0].message.content) > 0
    
    def test_cross_provider_streaming(self):
        """Test that streaming works uniformly across all providers."""
        models_to_test = [
            "gpt-3.5-turbo",  # OpenAI
            "claude-3-haiku-20240307",  # Anthropic  
            "meta-llama/Llama-3.2-3B-Instruct-Turbo"  # Together
        ]
        
        for model in models_to_test:
            print(f"\n--- Testing streaming with {model} ---")
            
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
            full_response = "".join(chunks)
            assert len(full_response) > 0
            print(f"✅ {model}: {len(chunks)} chunks, {len(full_response)} chars")
    
    def test_cross_provider_parameters(self):
        """Test that common parameters work across providers."""
        test_cases = [
            ("gpt-3.5-turbo", "OpenAI"),
            ("claude-3-haiku-20240307", "Anthropic"),
            ("Qwen/Qwen2.5-72B-Instruct-Turbo", "Together")
        ]
        
        for model, provider in test_cases:
            print(f"\n--- Testing parameters with {provider} ({model}) ---")
            
            # Test temperature
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "What is 2+2?"}],
                max_tokens=20,
                temperature=0.1
            )
            assert response.choices[0].message.content is not None
            
            # Test system prompts
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are helpful."},
                    {"role": "user", "content": "Hello!"}
                ],
                max_tokens=30
            )
            assert response.choices[0].message.content is not None
            print(f"✅ {provider}: Parameters work correctly")
    
    def test_response_format_consistency(self):
        """Test that all providers return consistent OpenAI-format responses."""
        models = [
            "gpt-4",  # OpenAI
            "claude-3-haiku-20240307",  # Anthropic
            "meta-llama/Llama-3.1-8B-Instruct-Turbo"  # Together
        ]
        
        for model in models:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Test response format"}],
                max_tokens=20
            )
            
            # All should have consistent OpenAI response structure
            assert hasattr(response, 'id')
            assert hasattr(response, 'object')
            assert response.object == "chat.completion"
            assert hasattr(response, 'created')
            assert hasattr(response, 'model')
            assert hasattr(response, 'choices')
            assert hasattr(response, 'usage')
            
            # Check choice structure
            choice = response.choices[0]
            assert hasattr(choice, 'index')
            assert hasattr(choice, 'message')
            assert hasattr(choice, 'finish_reason')
            
            # Check message structure
            message = choice.message
            assert hasattr(message, 'role')
            assert message.role == "assistant"
            assert hasattr(message, 'content')
            
            print(f"✅ {model}: Consistent OpenAI format")


class TestProviderSpecificFeatures:
    """Test provider-specific features via OpenAI SDK."""
    
    def test_anthropic_via_openai_sdk(self):
        """Test Anthropic-specific scenarios via OpenAI SDK."""
        # Test longer context - Anthropic models handle this well
        long_message = "Please summarize this: " + "test " * 500
        
        response = client.chat.completions.create(
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": long_message}],
            max_tokens=100
        )
        
        assert response.choices[0].message.content is not None
        assert len(response.choices[0].message.content) > 0
    
    def test_together_models_via_openai_sdk(self):
        """Test Together-specific models via OpenAI SDK."""
        together_models = [
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "mistralai/Mixtral-8x7B-Instruct-v0.1",
            "deepseek-ai/deepseek-v2.5"
        ]
        
        for model in together_models:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": f"Hello from {model.split('/')[-1]}"}],
                max_tokens=50
            )
            
            assert response.choices[0].message.content is not None
            assert response.model == model
            # Together models should preserve the full model name including slash
            assert "/" in response.model
    
    def test_openai_models_via_openai_sdk(self):
        """Test OpenAI models via OpenAI SDK (baseline)."""
        openai_models = ["gpt-3.5-turbo", "gpt-4"]
        
        for model in openai_models:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Hello from OpenAI"}],
                max_tokens=50
            )
            
            assert response.choices[0].message.content is not None
            assert response.model == model


class TestUniversalTestSuites:
    """Test using the universal test suites with different providers."""
    
    def test_universal_chat_suite_openai(self):
        """Test universal chat suite with OpenAI models."""
        models = ["gpt-3.5-turbo", "gpt-4"]
        suite = UniversalChatTestSuite(models, provider_hint="openai")
        
        # Test basic functionality
        suite.test_basic_chat()
        suite.test_multi_turn_conversation()
        suite.test_system_prompt()
        
        # Test all models
        results = suite.test_all_models()
        assert len(results) == len(models)
    
    def test_universal_chat_suite_anthropic(self):
        """Test universal chat suite with Anthropic models."""
        models = ["claude-3-haiku-20240307"]
        suite = UniversalChatTestSuite(models, provider_hint="anthropic")
        
        suite.test_basic_chat()
        suite.test_temperature_parameter()
        suite.test_max_tokens_parameter()
    
    def test_universal_chat_suite_together(self):
        """Test universal chat suite with Together models."""
        models = ["meta-llama/Llama-3.2-3B-Instruct-Turbo"]
        suite = UniversalChatTestSuite(models, provider_hint="together")
        
        suite.test_basic_chat()
        suite.test_multi_turn_conversation()
    
    def test_universal_streaming_suite(self):
        """Test universal streaming suite across providers."""
        models = [
            "gpt-3.5-turbo",
            "claude-3-haiku-20240307", 
            "meta-llama/Llama-3.1-8B-Instruct-Turbo"
        ]
        
        for model in models:
            suite = UniversalStreamingTestSuite([model])
            chunks_count, content = suite.test_basic_streaming()
            assert chunks_count > 0
            assert len(content) > 0
    
    def test_universal_error_suite(self):
        """Test universal error handling across providers."""
        models = ["gpt-3.5-turbo"]  # Use one model for error tests
        suite = UniversalErrorTestSuite(models)
        
        # Test invalid model
        error = suite.test_invalid_model()
        assert error is not None
        
        # Test empty messages
        error = suite.test_empty_messages()
        assert error is not None


class TestEmbeddingsUniversal:
    """Test embeddings across providers that support them."""
    
    def test_universal_embeddings(self):
        """Test embeddings with providers that support them."""
        embedding_models = UniversalTestData.get_embedding_models()
        
        for provider, models in embedding_models.items():
            print(f"\n--- Testing {provider.upper()} embeddings ---")
            
            for model in models:
                suite = UniversalEmbeddingTestSuite([model], provider_hint=provider)
                
                # Test single embedding
                response = suite.test_single_embedding()
                assert len(response.data) == 1
                
                # Test batch embeddings
                response = suite.test_batch_embeddings()
                assert len(response.data) > 1
                
                print(f"✅ {model}: Embeddings working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
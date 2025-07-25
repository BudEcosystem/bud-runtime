"""
Test OpenAI SDK compatibility with all providers through /v1/chat/completions endpoint.

This demonstrates that the OpenAI SDK can work with any provider that supports
the chat completions endpoint, making it a universal SDK for TensorZero.
"""

import os
import pytest
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Configuration
TENSORZERO_BASE_URL = os.getenv("TENSORZERO_BASE_URL", "http://localhost:3001")
TENSORZERO_API_KEY = os.getenv("TENSORZERO_API_KEY", "test-api-key")

# Universal OpenAI client that works with all providers
client = OpenAI(
    base_url=f"{TENSORZERO_BASE_URL}/v1",
    api_key=TENSORZERO_API_KEY
)


class TestOpenAISDKUniversalCompatibility:
    """Test OpenAI SDK with all provider models through /v1/chat/completions."""
    
    def test_openai_models(self):
        """Test OpenAI SDK with OpenAI models."""
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello from OpenAI model"}],
            max_tokens=50
        )
        
        assert response.choices[0].message.content is not None
        assert response.model == "gpt-3.5-turbo"
        assert len(response.choices[0].message.content) > 0
    
    def test_anthropic_models_via_openai_sdk(self):
        """Test OpenAI SDK with Anthropic models through /v1/chat/completions."""
        response = client.chat.completions.create(
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": "Hello from Anthropic model via OpenAI SDK"}],
            max_tokens=50
        )
        
        assert response.choices[0].message.content is not None
        assert response.model == "claude-3-haiku-20240307"
        assert len(response.choices[0].message.content) > 0
    
    def test_anthropic_claude_35_sonnet(self):
        """Test OpenAI SDK with Claude 3.5 Sonnet."""
        response = client.chat.completions.create(
            model="claude-3-5-sonnet-20241022",
            messages=[{"role": "user", "content": "Hello from Claude 3.5 Sonnet"}],
            max_tokens=50
        )
        
        assert response.choices[0].message.content is not None
        assert response.model == "claude-3-5-sonnet-20241022"
        assert len(response.choices[0].message.content) > 0
    
    def test_anthropic_opus(self):
        """Test OpenAI SDK with Claude Opus."""
        response = client.chat.completions.create(
            model="claude-3-opus-20240229",
            messages=[{"role": "user", "content": "Hello from Claude Opus"}],
            max_tokens=50
        )
        
        assert response.choices[0].message.content is not None
        assert response.model == "claude-3-opus-20240229"
        assert len(response.choices[0].message.content) > 0
    
    def test_streaming_with_all_providers(self):
        """Test streaming compatibility across different providers."""
        # Test with OpenAI model
        stream = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Count to 3"}],
            max_tokens=30,
            stream=True
        )
        
        chunks = []
        for chunk in stream:
            if chunk.choices[0].delta.content:
                chunks.append(chunk.choices[0].delta.content)
        
        assert len(chunks) > 0
        
        # Test with Anthropic model
        stream = client.chat.completions.create(
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": "Count to 3"}],
            max_tokens=30,
            stream=True
        )
        
        chunks = []
        for chunk in stream:
            if chunk.choices[0].delta.content:
                chunks.append(chunk.choices[0].delta.content)
        
        assert len(chunks) > 0
    
    def test_system_prompts_cross_provider(self):
        """Test system prompts work across different providers."""
        system_prompt = "You are a helpful assistant. Always start responses with 'Assistant:'"
        
        # Test with OpenAI
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Hello"}
            ],
            max_tokens=50
        )
        
        assert response.choices[0].message.content is not None
        
        # Test with Anthropic  
        response = client.chat.completions.create(
            model="claude-3-haiku-20240307",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Hello"}
            ],
            max_tokens=50
        )
        
        assert response.choices[0].message.content is not None
    
    def test_temperature_parameter_cross_provider(self):
        """Test temperature parameter works across providers."""
        for model in ["gpt-3.5-turbo", "claude-3-haiku-20240307"]:
            # Low temperature
            response1 = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "What is 2+2?"}],
                max_tokens=20,
                temperature=0.0
            )
            
            # High temperature
            response2 = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "What is 2+2?"}],
                max_tokens=20,
                temperature=1.0
            )
            
            assert response1.choices[0].message.content is not None
            assert response2.choices[0].message.content is not None
    
    def test_multi_turn_conversation_cross_provider(self):
        """Test multi-turn conversations work across providers."""
        for model in ["gpt-3.5-turbo", "claude-3-haiku-20240307"]:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": "My name is Alice"},
                    {"role": "assistant", "content": "Hello Alice! Nice to meet you."},
                    {"role": "user", "content": "What's my name?"}
                ],
                max_tokens=50
            )
            
            assert response.choices[0].message.content is not None
            # For dummy provider, just verify we got a response
            assert len(response.choices[0].message.content) > 0


class TestOpenAISDKEndpointCoverage:
    """Test that OpenAI SDK works with all supported endpoints across providers."""
    
    def test_chat_completions_universal(self):
        """Chat completions should work with all chat-capable models."""
        chat_models = [
            # OpenAI models
            "gpt-3.5-turbo",
            "gpt-4", 
            # Anthropic models
            "claude-3-haiku-20240307",
            "claude-3-sonnet-20240229",
            "claude-3-5-sonnet-20241022",
            "claude-3-opus-20240229",
            # Together AI models
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "meta-llama/Llama-3.2-3B-Instruct-Turbo",
            "Qwen/Qwen2.5-72B-Instruct-Turbo",
            "mistralai/Mixtral-8x7B-Instruct-v0.1"
        ]
        
        for model in chat_models:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": f"Testing {model}"}],
                max_tokens=20
            )
            
            assert response.choices[0].message.content is not None
            assert response.model == model
    
    def test_embeddings_openai_models(self):
        """Embeddings should work with OpenAI embedding models."""
        embedding_models = [
            "text-embedding-ada-002",
            "text-embedding-3-small", 
            "text-embedding-3-large"
        ]
        
        for model in embedding_models:
            response = client.embeddings.create(
                model=model,
                input="Test embedding text"
            )
            
            assert len(response.data) > 0
            assert len(response.data[0].embedding) > 0
            assert response.model == model
    
    def test_moderation_openai_models(self):
        """Moderation should work with OpenAI moderation models."""
        moderation_models = [
            "text-moderation-latest",
            "omni-moderation-latest"
        ]
        
        for model in moderation_models:
            response = client.moderations.create(
                model=model,
                input="This is a test message"
            )
            
            assert len(response.results) > 0
            assert hasattr(response.results[0], 'flagged')
            assert response.model == model
    
    def test_audio_openai_models(self):
        """Audio endpoints should work with OpenAI audio models."""
        # Text-to-speech
        response = client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input="Hello world"
        )
        
        assert response.content is not None
        assert len(response.content) > 0
    
    def test_image_generation_openai_models(self):
        """Image generation should work with OpenAI image models."""
        image_models = ["dall-e-2", "dall-e-3"]
        
        for model in image_models:
            response = client.images.generate(
                model=model,
                prompt="A simple test image",
                n=1,
                size="256x256"
            )
            
            assert len(response.data) > 0
            assert response.data[0].url is not None or response.data[0].b64_json is not None


class TestOpenAISDKVsNativeSDK:
    """Compare OpenAI SDK usage vs native SDK usage for the same provider."""
    
    def test_anthropic_comparison_demo(self):
        """Demonstrate that Anthropic models work with OpenAI SDK."""
        # Using OpenAI SDK with Anthropic model through /v1/chat/completions
        openai_sdk_response = client.chat.completions.create(
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": "Hello from OpenAI SDK"}],
            max_tokens=50
        )
        
        # Verify the response
        assert openai_sdk_response.choices[0].message.content is not None
        assert openai_sdk_response.model == "claude-3-haiku-20240307"
        
        # Note: Native Anthropic SDK would use /v1/messages endpoint
        # Both approaches work, but OpenAI SDK provides universal compatibility
    
    def test_openai_model_native_usage(self):
        """Demonstrate OpenAI models work naturally with OpenAI SDK."""
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello from native OpenAI usage"}],
            max_tokens=50
        )
        
        assert response.choices[0].message.content is not None
        assert response.model == "gpt-3.5-turbo"


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
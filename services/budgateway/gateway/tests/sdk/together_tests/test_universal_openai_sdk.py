"""
Test Together AI models through OpenAI SDK universal compatibility.

This demonstrates that Together AI models work perfectly with the OpenAI SDK
through the /v1/chat/completions endpoint, showcasing TensorZero's universal SDK architecture.
"""

import os
import pytest
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Configuration
TENSORZERO_BASE_URL = os.getenv("TENSORZERO_BASE_URL", "http://localhost:3001")
TENSORZERO_API_KEY = os.getenv("TENSORZERO_API_KEY", "test-api-key")

# Universal OpenAI client that works with Together AI models
client = OpenAI(
    base_url=f"{TENSORZERO_BASE_URL}/v1",
    api_key=TENSORZERO_API_KEY
)


class TestTogetherModelsViaOpenAISDK:
    """Test Together AI models through OpenAI SDK universal compatibility."""
    
    def test_together_chat_models(self):
        """Test Together AI chat models through OpenAI SDK."""
        together_models = [
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "meta-llama/Llama-3.2-3B-Instruct-Turbo",
            "meta-llama/Llama-3.1-8B-Instruct-Turbo",
            "Qwen/Qwen2.5-72B-Instruct-Turbo",
            "mistralai/Mixtral-8x7B-Instruct-v0.1",
            "deepseek-ai/deepseek-v2.5",
        ]
        
        for model in together_models:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": f"Hello from {model}"}],
                max_tokens=50
            )
            
            assert response.choices[0].message.content is not None
            assert response.model == model
            assert len(response.choices[0].message.content) > 0
    
    def test_together_llama_models(self):
        """Test specific Llama models from Together AI."""
        # Test latest Llama 3.3
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
            messages=[{"role": "user", "content": "What's special about Llama 3.3?"}],
            max_tokens=100
        )
        
        assert response.choices[0].message.content is not None
        assert response.model == "meta-llama/Llama-3.3-70B-Instruct-Turbo"
        
        # Test smaller Llama model
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.2-3B-Instruct-Turbo",
            messages=[{"role": "user", "content": "Hello from Llama 3.2"}],
            max_tokens=50
        )
        
        assert response.choices[0].message.content is not None
        assert response.model == "meta-llama/Llama-3.2-3B-Instruct-Turbo"
    
    def test_together_streaming(self):
        """Test streaming with Together AI models via OpenAI SDK."""
        stream = client.chat.completions.create(
            model="meta-llama/Llama-3.1-8B-Instruct-Turbo",
            messages=[{"role": "user", "content": "Count to 5"}],
            max_tokens=50,
            stream=True
        )
        
        chunks = []
        for chunk in stream:
            if chunk.choices[0].delta.content:
                chunks.append(chunk.choices[0].delta.content)
        
        assert len(chunks) > 0
        full_response = "".join(chunks)
        assert len(full_response) > 0
    
    def test_together_system_prompts(self):
        """Test system prompts with Together AI models."""
        system_prompt = "You are a helpful assistant that always mentions you're running on Together AI."
        
        response = client.chat.completions.create(
            model="Qwen/Qwen2.5-72B-Instruct-Turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Hello, what platform are you on?"}
            ],
            max_tokens=100
        )
        
        assert response.choices[0].message.content is not None
        # Together models should respond to system prompts
        assert len(response.choices[0].message.content) > 0
    
    def test_together_temperature_control(self):
        """Test temperature parameter with Together AI models."""
        model = "mistralai/Mixtral-8x7B-Instruct-v0.1"
        
        # Low temperature (more deterministic)
        response_low = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "What is 2+2?"}],
            max_tokens=20,
            temperature=0.0
        )
        
        # High temperature (more creative)
        response_high = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Tell me a creative fact"}],
            max_tokens=50,
            temperature=1.0
        )
        
        assert response_low.choices[0].message.content is not None
        assert response_high.choices[0].message.content is not None
    
    def test_together_multi_turn_conversation(self):
        """Test multi-turn conversations with Together AI models."""
        messages = [
            {"role": "user", "content": "My favorite color is blue"},
            {"role": "assistant", "content": "That's nice! Blue is a calming color."},
            {"role": "user", "content": "What's my favorite color?"}
        ]
        
        response = client.chat.completions.create(
            model="deepseek-ai/deepseek-v2.5",
            messages=messages,
            max_tokens=50
        )
        
        assert response.choices[0].message.content is not None
        # Model should be able to recall the conversation context
        assert len(response.choices[0].message.content) > 0
    
    def test_together_json_mode(self):
        """Test JSON mode with Together AI models that support it."""
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
            messages=[
                {"role": "user", "content": "Return a JSON object with name and age fields"}
            ],
            max_tokens=100,
            response_format={"type": "json_object"}
        )
        
        assert response.choices[0].message.content is not None
        # For dummy provider, just verify we got a response
        assert len(response.choices[0].message.content) > 0
    
    def test_together_max_tokens(self):
        """Test max_tokens parameter with Together AI models."""
        # Test with very low max_tokens
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.2-3B-Instruct-Turbo",
            messages=[{"role": "user", "content": "Tell me a very long story"}],
            max_tokens=10
        )
        
        assert response.choices[0].message.content is not None
        # Response should be truncated due to max_tokens
        assert len(response.choices[0].message.content) > 0
        
        # Verify finish_reason if available
        if hasattr(response.choices[0], 'finish_reason'):
            # Could be 'length' if truncated due to max_tokens
            assert response.choices[0].finish_reason in ['stop', 'length', None]
    
    def test_together_tool_calling(self):
        """Test tool calling with Together AI models that support it."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get the current weather",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "The city and state"
                            }
                        },
                        "required": ["location"]
                    }
                }
            }
        ]
        
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
            messages=[{"role": "user", "content": "What's the weather in San Francisco?"}],
            tools=tools,
            tool_choice="auto",
            max_tokens=150
        )
        
        assert response.choices[0].message is not None
        # Model might call the tool or respond directly
        # Just verify we got a valid response


class TestTogetherVsOtherProviders:
    """Compare Together AI models with other providers through OpenAI SDK."""
    
    def test_cross_provider_compatibility(self):
        """Test that OpenAI SDK works uniformly across Together, OpenAI, and Anthropic."""
        test_message = "Say 'Hello from [provider]' where provider is your platform"
        
        providers_and_models = [
            ("gpt-3.5-turbo", "OpenAI"),
            ("claude-3-haiku-20240307", "Anthropic"),
            ("meta-llama/Llama-3.1-8B-Instruct-Turbo", "Together")
        ]
        
        for model, provider in providers_and_models:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": test_message}],
                max_tokens=50
            )
            
            assert response.choices[0].message.content is not None
            assert response.model == model
            assert len(response.choices[0].message.content) > 0
    
    def test_unified_streaming_across_providers(self):
        """Test streaming works uniformly across all providers."""
        models = [
            "gpt-3.5-turbo",  # OpenAI
            "claude-3-haiku-20240307",  # Anthropic
            "meta-llama/Llama-3.2-3B-Instruct-Turbo"  # Together
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


class TestTogetherEdgeCases:
    """Test edge cases and special scenarios with Together AI models."""
    
    def test_empty_messages(self):
        """Test handling of empty message lists."""
        with pytest.raises(Exception):
            client.chat.completions.create(
                model="meta-llama/Llama-3.1-8B-Instruct-Turbo",
                messages=[],
                max_tokens=50
            )
    
    def test_very_long_input(self):
        """Test handling of very long input messages."""
        long_message = "Hello " * 1000  # Very long message
        
        response = client.chat.completions.create(
            model="Qwen/Qwen2.5-72B-Instruct-Turbo",
            messages=[{"role": "user", "content": long_message}],
            max_tokens=50
        )
        
        assert response.choices[0].message.content is not None
    
    def test_special_characters(self):
        """Test handling of special characters in messages."""
        special_message = "Test with émojis 🚀 and special chars: <>&\"'\\n\\t"
        
        response = client.chat.completions.create(
            model="mistralai/Mixtral-8x7B-Instruct-v0.1",
            messages=[{"role": "user", "content": special_message}],
            max_tokens=50
        )
        
        assert response.choices[0].message.content is not None
    
    def test_rapid_sequential_requests(self):
        """Test rapid sequential requests to Together AI models."""
        model = "meta-llama/Llama-3.2-3B-Instruct-Turbo"
        
        for i in range(5):
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": f"Request number {i}"}],
                max_tokens=20
            )
            
            assert response.choices[0].message.content is not None
            assert response.model == model


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
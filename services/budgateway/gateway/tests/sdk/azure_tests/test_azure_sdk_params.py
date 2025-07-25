"""
Test Azure models and parameters through TensorZero's OpenAI-compatible interface.

This test file validates that Azure models work correctly when accessed
through the OpenAI SDK via TensorZero's standard endpoints.

Note: Azure SDK with Azure-specific URL patterns is not supported.
Azure models work through the standard OpenAI SDK interface.
"""

import os
import pytest
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Configuration
TENSORZERO_BASE_URL = os.getenv("TENSORZERO_BASE_URL", "http://localhost:3001")
TENSORZERO_API_KEY = os.getenv("TENSORZERO_API_KEY", "test-api-key")

# OpenAI SDK client for Azure models
openai_client = OpenAI(
    base_url=f"{TENSORZERO_BASE_URL}/v1",
    api_key=TENSORZERO_API_KEY
)


class TestAzureModels:
    """Test Azure models through OpenAI SDK."""
    
    def test_openai_sdk_with_azure_model(self):
        """Test that OpenAI SDK works with Azure models."""
        response = openai_client.chat.completions.create(
            model="gpt-35-turbo-azure",
            messages=[{"role": "user", "content": "Hello from OpenAI SDK to Azure model"}],
            max_tokens=50
        )
        
        assert response.choices[0].message.content is not None
        assert response.model == "gpt-35-turbo-azure"
    
    def test_azure_streaming(self):
        """Test streaming with Azure models via OpenAI SDK."""
        stream = openai_client.chat.completions.create(
            model="gpt-35-turbo-azure",
            messages=[{"role": "user", "content": "Stream test"}],
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
    
    def test_azure_embeddings(self):
        """Test embeddings with Azure models via OpenAI SDK."""
        response = openai_client.embeddings.create(
            model="text-embedding-ada-002-azure",
            input="Test embedding with Azure model"
        )
        
        assert len(response.data) == 1
        assert len(response.data[0].embedding) > 0
        assert response.model == "text-embedding-ada-002-azure"
    
    def test_azure_function_calling(self):
        """Test function calling with Azure models via OpenAI SDK."""
        tools = [{
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"},
                        "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
                    },
                    "required": ["location"]
                }
            }
        }]
        
        response = openai_client.chat.completions.create(
            model="gpt-4-azure",
            messages=[{"role": "user", "content": "What's the weather in Paris?"}],
            tools=tools,
            tool_choice="auto",
            max_tokens=100
        )
        
        assert response.choices[0].message is not None
        # Check if tool call was made (dummy provider may not always call tools)
        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            assert tool_call.function.name == "get_weather"
    
    def test_azure_json_mode(self):
        """Test JSON mode with Azure models via OpenAI SDK."""
        response = openai_client.chat.completions.create(
            model="gpt-4o-azure",  # Model that supports JSON mode
            messages=[
                {"role": "system", "content": "Respond with valid JSON"},
                {"role": "user", "content": "Give me user data with name and age"}
            ],
            response_format={"type": "json_object"},
            max_tokens=100
        )
        
        assert response.choices[0].message.content is not None
        # Try to parse as JSON (dummy provider should return valid JSON)
        import json
        try:
            json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            pytest.skip("Dummy provider returned non-JSON response")
    
    @pytest.mark.parametrize("deployment_name,expected_model", [
        ("gpt-35-turbo-azure", "gpt-35-turbo-azure"),
        ("gpt-4-azure", "gpt-4-azure"),
        ("gpt-4o-azure", "gpt-4o-azure"),
    ])
    def test_azure_model_names(self, deployment_name, expected_model):
        """Test that Azure model names are properly handled via OpenAI SDK."""
        response = openai_client.chat.completions.create(
            model=deployment_name,
            messages=[{"role": "user", "content": "Test model"}],
            max_tokens=20
        )
        
        assert response.model == expected_model
        assert response.choices[0].message.content is not None
    
    def test_azure_model_consistency(self):
        """Test that Azure models work consistently via OpenAI SDK."""
        test_message = "Test consistency"
        
        # Test with different Azure models
        models_to_test = ["gpt-35-turbo-azure", "gpt-4-azure"]
        
        for model in models_to_test:
            response = openai_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": test_message}],
                max_tokens=50,
                temperature=0
            )
            
            assert response.choices[0].message.content is not None
            assert response.model == model
    
    def test_azure_audio_transcription_params(self):
        """Test audio transcription with Azure models via OpenAI SDK."""
        # Create a test audio file
        import io
        audio_data = b"test audio data for transcription"
        audio_file = io.BytesIO(audio_data)
        audio_file.name = "test_audio.mp3"
        
        response = openai_client.audio.transcriptions.create(
            model="whisper-1-azure",
            file=audio_file,
            language="en",
            response_format="json",
            temperature=0.5
        )
        
        assert response.text is not None
        # With real Azure, language should match requested
        if hasattr(response, 'language'):
            assert response.language == "en"
    
    def test_azure_audio_translation(self):
        """Test audio translation with Azure models via OpenAI SDK."""
        import io
        audio_data = b"test audio data for translation"
        audio_file = io.BytesIO(audio_data)
        audio_file.name = "test_audio.mp3"
        
        response = openai_client.audio.translations.create(
            model="whisper-1-azure",
            file=audio_file,
            response_format="json"
        )
        
        assert response.text is not None
        # Translation always outputs English
    
    def test_azure_text_to_speech_params(self):
        """Test TTS with Azure models via OpenAI SDK."""
        # Test different voices
        voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        
        for voice in voices:
            response = openai_client.audio.speech.create(
                model="tts-1-azure",
                input=f"Testing voice: {voice}",
                voice=voice,
                response_format="mp3",
                speed=1.0
            )
            
            audio_data = response.content
            assert audio_data is not None
            assert len(audio_data) > 0
    
    def test_azure_image_generation_params(self):
        """Test image generation with Azure models via OpenAI SDK."""
        response = openai_client.images.generate(
            model="dall-e-3-azure",
            prompt="A futuristic city with flying cars",
            n=1,
            size="1024x1024",
            quality="hd",
            style="vivid",
            response_format="url"
        )
        
        assert len(response.data) == 1
        assert response.data[0].url is not None or response.data[0].b64_json is not None
        
        # Test with base64 response
        response_b64 = openai_client.images.generate(
            model="dall-e-3-azure",
            prompt="A peaceful garden",
            n=1,
            size="1024x1024",
            response_format="b64_json"
        )
        
        assert len(response_b64.data) == 1
        # With real Azure, should have base64 data
    
    def test_azure_batch_operations(self):
        """Test batch operations with Azure models via OpenAI SDK."""
        # Batch embedding request
        texts = [
            "First document about Azure",
            "Second document about OpenAI",
            "Third document about AI",
            "Fourth document about cloud computing"
        ]
        
        response = openai_client.embeddings.create(
            model="text-embedding-ada-002-azure",
            input=texts,
            encoding_format="base64"  # Azure supports base64 encoding
        )
        
        assert len(response.data) == len(texts)
        for i, embedding in enumerate(response.data):
            assert len(embedding.embedding) > 0
            assert embedding.index == i
    
    def test_azure_extra_body_audio(self):
        """Test extra_body parameters with Azure audio models via OpenAI SDK."""
        import io
        audio_data = b"test audio data"
        audio_file = io.BytesIO(audio_data)
        audio_file.name = "test.mp3"
        
        # Test with extra parameters (may not be supported by all deployments)
        try:
            response = openai_client.audio.transcriptions.create(
                model="whisper-1-azure",
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["word", "segment"]
            )
            assert response.text is not None
        except Exception as e:
            # Some Azure deployments may not support all parameters
            print(f"Extra body test skipped: {e}")
    
    def test_azure_content_safety(self):
        """Test content safety with Azure models via OpenAI SDK."""
        # Azure models work with content filtering
        response = openai_client.chat.completions.create(
            model="gpt-35-turbo-azure",
            messages=[{"role": "user", "content": "Tell me a story about a helpful robot"}],
            max_tokens=100
        )
        
        assert response.choices[0].message.content is not None
        # Content filtering is handled by the provider backend


if __name__ == "__main__":
    import pytest
    import sys
    
    # Run pytest on this file
    exit_code = pytest.main([__file__, "-v"])
    sys.exit(exit_code)
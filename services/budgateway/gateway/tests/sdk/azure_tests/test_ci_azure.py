"""
CI tests for Azure models through OpenAI SDK (no API keys required).

These tests use the dummy provider to validate Azure model support
through TensorZero's OpenAI-compatible endpoints without requiring 
actual Azure OpenAI API credentials.

Note: Azure SDK with Azure-specific URL patterns is not supported.
Azure models work through the standard OpenAI SDK interface.
"""

import os
import pytest
from openai import OpenAI

# Configuration
TENSORZERO_BASE_URL = os.getenv("TENSORZERO_BASE_URL", "http://localhost:3001")
TENSORZERO_API_KEY = "dummy-api-key"  # CI uses dummy provider

# OpenAI SDK client for Azure models
openai_client = OpenAI(
    base_url=f"{TENSORZERO_BASE_URL}/v1",
    api_key=TENSORZERO_API_KEY
)


class TestAzureSDKCI:
    """CI tests for Azure models through OpenAI SDK."""
    def test_azure_embeddings_ci(self):
        """Test embeddings with Azure models in CI using OpenAI SDK."""
        # Note: Azure SDK uses different URL patterns that TensorZero doesn't support
        # Using OpenAI SDK to test Azure models through TensorZero
        response = openai_client.embeddings.create(
            model="text-embedding-ada-002-azure",
            input="Test text"
        )
        
        assert len(response.data) == 1
        assert len(response.data[0].embedding) == 1536  # ada-002 dimension
        assert response.model == "text-embedding-ada-002-azure"
    
    def test_openai_sdk_with_azure_models(self):
        """Test that OpenAI SDK works with Azure models in CI."""
        response = openai_client.chat.completions.create(
            model="gpt-35-turbo-azure",
            messages=[{"role": "user", "content": "Test OpenAI SDK"}],
            max_tokens=10
        )
        
        assert response.choices[0].message.content is not None
        assert response.model == "gpt-35-turbo-azure"
    
    def test_azure_error_handling_openai_sdk(self):
        """Test error handling with OpenAI SDK using Azure models in CI."""
        with pytest.raises(Exception) as exc_info:
            # Try to use a non-existent model
            openai_client.chat.completions.create(
                model="non-existent-model",
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=10
            )
        
        # Should raise an appropriate error
        assert exc_info.value is not None
    
    def test_azure_audio_transcription_ci(self):
        """Test audio transcription with Azure models in CI using OpenAI SDK."""
        # Create a dummy audio file for testing
        audio_data = b"dummy audio data"
        
        response = openai_client.audio.transcriptions.create(
            model="whisper-1-azure",
            file=("test.mp3", audio_data, "audio/mpeg")
        )
        
        assert response.text is not None
        assert len(response.text) > 0
    
    def test_azure_audio_translation_ci(self):
        """Test audio translation with Azure models in CI using OpenAI SDK."""
        # Create a dummy audio file for testing
        audio_data = b"dummy audio data"
        
        response = openai_client.audio.translations.create(
            model="whisper-1-azure",
            file=("test.mp3", audio_data, "audio/mpeg")
        )
        
        assert response.text is not None
        assert len(response.text) > 0
    
    def test_azure_text_to_speech_ci(self):
        """Test text-to-speech with Azure models in CI using OpenAI SDK."""
        response = openai_client.audio.speech.create(
            model="tts-1-azure",
            input="Hello, this is a test of Azure TTS.",
            voice="alloy"
        )
        
        # Response should contain audio data
        audio_data = response.content
        assert audio_data is not None
        assert len(audio_data) > 0
    
    def test_azure_image_generation_ci(self):
        """Test image generation with Azure models in CI using OpenAI SDK."""
        response = openai_client.images.generate(
            model="dall-e-3-azure",
            prompt="A beautiful sunset over mountains",
            n=1,
            size="1024x1024"
        )
        
        assert len(response.data) == 1
        # Dummy provider should return URL or base64 data
        assert response.data[0].url is not None or response.data[0].b64_json is not None
    
    def test_azure_batch_embeddings_ci(self):
        """Test batch embeddings with Azure models in CI using OpenAI SDK."""
        response = openai_client.embeddings.create(
            model="text-embedding-ada-002-azure",
            input=["First text", "Second text", "Third text"]
        )
        
        assert len(response.data) == 3
        for embedding in response.data:
            assert len(embedding.embedding) == 1536  # ada-002 dimension


if __name__ == "__main__":
    import pytest
    import sys
    
    # Run pytest on this file
    exit_code = pytest.main([__file__, "-v"])
    sys.exit(exit_code)
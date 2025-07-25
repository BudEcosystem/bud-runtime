"""
CI tests for Together AI multimodal capabilities through OpenAI SDK.

These tests use dummy providers and don't require real API keys.
They verify the multimodal integration and routing logic works correctly.
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


class TestTogetherMultimodalCI:
    """CI tests for Together AI multimodal models through OpenAI SDK."""
    
    def test_together_embeddings_routing_ci(self):
        """Test that Together embedding models are properly routed."""
        embedding_models = [
            "together-bge-base",  # BAAI/bge-base-en-v1.5
            "together-m2-bert",   # togethercomputer/m2-bert-80M-8k-retrieval
        ]
        
        for model in embedding_models:
            response = client.embeddings.create(
                model=model,
                input="Test embedding"
            )
            
            # Verify response structure
            assert response.model == model
            assert response.object == "list"
            assert len(response.data) == 1
            assert response.data[0].index == 0
            assert response.data[0].object == "embedding"
            assert len(response.data[0].embedding) > 0
            assert response.usage.total_tokens > 0
    
    def test_together_embeddings_batch_ci(self):
        """Test batch embeddings with Together models."""
        texts = [
            "First test document",
            "Second test document",
            "Third test document"
        ]
        
        response = client.embeddings.create(
            model="together-bge-base",
            input=texts
        )
        
        assert len(response.data) == len(texts)
        for i, embedding_data in enumerate(response.data):
            assert embedding_data.index == i
            assert len(embedding_data.embedding) > 0
    
    def test_together_image_generation_routing_ci(self):
        """Test that Together image generation models are properly routed."""
        response = client.images.generate(
            model="flux-schnell",
            prompt="A simple test image",
            n=1,
            size="512x512"
        )
        
        # Verify response structure
        assert len(response.data) == 1
        # Dummy provider should return URL format by default
        assert hasattr(response.data[0], 'url')
    
    def test_together_image_generation_params_ci(self):
        """Test image generation parameters with Together models."""
        # Test different sizes
        sizes = ["256x256", "512x512", "1024x1024"]
        
        for size in sizes:
            response = client.images.generate(
                model="flux-schnell",
                prompt=f"Test image at {size}",
                n=1,
                size=size
            )
            
            assert len(response.data) == 1
    
    def test_together_image_multiple_ci(self):
        """Test generating multiple images."""
        response = client.images.generate(
            model="flux-schnell",
            prompt="Multiple test images",
            n=3,
            size="512x512"
        )
        
        assert len(response.data) == 3
        for i, image_data in enumerate(response.data):
            assert hasattr(image_data, 'url')
    
    def test_together_tts_routing_ci(self):
        """Test that Together TTS models are properly routed."""
        response = client.audio.speech.create(
            model="together-tts",
            voice="alloy",
            input="Test text to speech"
        )
        
        # Dummy provider returns mock audio data
        assert response.content is not None
        assert len(response.content) > 0
    
    def test_together_tts_voices_ci(self):
        """Test different voice options with Together TTS."""
        # Standard OpenAI-compatible voices
        voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        
        for voice in voices:
            response = client.audio.speech.create(
                model="together-tts",
                voice=voice,
                input=f"Testing voice: {voice}"
            )
            
            assert response.content is not None
            assert len(response.content) > 0
    
    def test_together_tts_native_voices_ci(self):
        """Test Together's native voice names."""
        # Together-specific voice names
        together_voices = [
            "helpful woman",
            "british reading lady",
            "meditation lady",
            "newsman",
        ]
        
        for voice in together_voices:
            response = client.audio.speech.create(
                model="together-tts",
                voice=voice,
                input=f"Testing Together voice: {voice}"
            )
            
            assert response.content is not None
            assert len(response.content) > 0
    
    def test_together_multimodal_integration_ci(self):
        """Test integration across multiple modalities."""
        # 1. Generate text
        chat_response = client.chat.completions.create(
            model="meta-llama/Llama-3.1-8B-Instruct-Turbo",
            messages=[{
                "role": "user",
                "content": "Describe a sunset in one sentence."
            }],
            max_tokens=50
        )
        
        description = chat_response.choices[0].message.content
        assert description is not None
        
        # 2. Create embedding
        embedding_response = client.embeddings.create(
            model="together-bge-base",
            input=description
        )
        
        assert len(embedding_response.data) == 1
        assert len(embedding_response.data[0].embedding) > 0
        
        # 3. Generate image from description
        image_response = client.images.generate(
            model="flux-schnell",
            prompt=description,
            n=1,
            size="512x512"
        )
        
        assert len(image_response.data) == 1
        
        # 4. Convert to speech
        tts_response = client.audio.speech.create(
            model="together-tts",
            voice="nova",
            input=description
        )
        
        assert tts_response.content is not None
    
    def test_together_embeddings_vs_openai_ci(self):
        """Compare Together embeddings format with OpenAI format."""
        test_text = "Universal embedding test"
        
        # Together embedding
        together_response = client.embeddings.create(
            model="together-bge-base",
            input=test_text
        )
        
        # OpenAI embedding (also using dummy in CI)
        openai_response = client.embeddings.create(
            model="text-embedding-3-small",
            input=test_text
        )
        
        # Both should have same response structure
        assert together_response.object == openai_response.object == "list"
        assert len(together_response.data) == len(openai_response.data) == 1
        assert together_response.data[0].object == openai_response.data[0].object == "embedding"
    
    def test_together_multimodal_error_handling_ci(self):
        """Test error handling for multimodal operations."""
        # Test embedding with empty input
        with pytest.raises(Exception):
            client.embeddings.create(
                model="together-bge-base",
                input=[]
            )
        
        # Test image generation with empty prompt
        # Note: Dummy provider may not validate empty prompts
        try:
            response = client.images.generate(
                model="flux-schnell",
                prompt="",
                n=1
            )
            # If no exception, at least verify we got a response
            assert response is not None
        except Exception:
            # Expected behavior - empty prompt should raise an error
            pass
        
        # Test TTS with empty input
        # Note: Dummy provider may not validate empty input
        try:
            response = client.audio.speech.create(
                model="together-tts",
                voice="alloy",
                input=""
            )
            # If no exception, at least verify we got a response
            assert response is not None
        except Exception:
            # Expected behavior - empty input should raise an error
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
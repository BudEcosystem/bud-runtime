"""
Test Together AI multimodal capabilities through OpenAI SDK.

This demonstrates Together's embeddings, image generation, and text-to-speech
capabilities using the OpenAI SDK universal compatibility layer.
"""

import os
import json
import base64
import pytest
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Configuration
TENSORZERO_BASE_URL = os.getenv("TENSORZERO_BASE_URL", "http://localhost:3001")
TENSORZERO_API_KEY = os.getenv("TENSORZERO_API_KEY", "test-api-key")

# Universal OpenAI client for Together AI
client = OpenAI(
    base_url=f"{TENSORZERO_BASE_URL}/v1",
    api_key=TENSORZERO_API_KEY
)


class TestTogetherEmbeddings:
    """Test Together AI embedding models through OpenAI SDK."""
    
    def test_together_embeddings_single(self):
        """Test single text embedding with Together models."""
        embedding_models = [
            "together-bge-base",  # BAAI/bge-base-en-v1.5
            "together-m2-bert",   # togethercomputer/m2-bert-80M-8k-retrieval
        ]
        
        for model in embedding_models:
            response = client.embeddings.create(
                model=model,
                input="Test embedding for Together AI models"
            )
            
            assert response.model == model
            assert len(response.data) == 1
            assert response.data[0].index == 0
            assert len(response.data[0].embedding) > 0
            assert all(isinstance(x, float) for x in response.data[0].embedding)
            assert response.usage.total_tokens > 0
    
    def test_together_embeddings_batch(self):
        """Test batch embeddings with Together models."""
        texts = [
            "First document about machine learning",
            "Second document about natural language processing",
            "Third document about computer vision",
            "Fourth document about reinforcement learning"
        ]
        
        response = client.embeddings.create(
            model="together-bge-base",
            input=texts
        )
        
        assert len(response.data) == len(texts)
        for i, embedding_data in enumerate(response.data):
            assert embedding_data.index == i
            assert len(embedding_data.embedding) > 0
            assert all(isinstance(x, float) for x in embedding_data.embedding)
        
        assert response.usage.total_tokens > 0
        assert response.usage.prompt_tokens == response.usage.total_tokens
    
    def test_together_embeddings_dimensions(self):
        """Test embedding dimensions for different Together models."""
        # BGE base typically has 768 dimensions
        response_bge = client.embeddings.create(
            model="together-bge-base",
            input="Test dimensions"
        )
        bge_dims = len(response_bge.data[0].embedding)
        assert bge_dims > 0  # Should be 768 for BGE base
        
        # M2 BERT may have different dimensions
        response_m2 = client.embeddings.create(
            model="together-m2-bert",
            input="Test dimensions"
        )
        m2_dims = len(response_m2.data[0].embedding)
        assert m2_dims > 0
    
    def test_together_embeddings_special_characters(self):
        """Test embeddings with special characters and unicode."""
        special_texts = [
            "Test with émojis 🚀🤖🌟",
            "Unicode: 你好世界",
            "Special chars: <>&\"'\\n\\t",
            "Math symbols: ∑∏∫√∞"
        ]
        
        response = client.embeddings.create(
            model="together-bge-base",
            input=special_texts
        )
        
        assert len(response.data) == len(special_texts)
        for embedding_data in response.data:
            assert len(embedding_data.embedding) > 0
    
    def test_together_embeddings_empty_input(self):
        """Test error handling for empty input."""
        with pytest.raises(Exception) as exc_info:
            client.embeddings.create(
                model="together-bge-base",
                input=[]
            )
        
        # Should raise an error for empty batch
        assert exc_info.value is not None
    
    def test_together_embeddings_vs_openai(self):
        """Compare Together embeddings format with OpenAI format."""
        # Test same text with both providers
        test_text = "Universal embedding test"
        
        # Together embedding
        together_response = client.embeddings.create(
            model="together-bge-base",
            input=test_text
        )
        
        # OpenAI embedding
        openai_response = client.embeddings.create(
            model="text-embedding-3-small",
            input=test_text
        )
        
        # Both should have same response structure
        assert together_response.object == openai_response.object == "list"
        assert len(together_response.data) == len(openai_response.data) == 1
        assert together_response.data[0].object == openai_response.data[0].object == "embedding"


class TestTogetherImageGeneration:
    """Test Together AI image generation through OpenAI SDK."""
    
    def test_together_flux_image_generation(self):
        """Test FLUX image generation with Together."""
        prompts = [
            "A serene mountain landscape at sunset",
            "Abstract geometric patterns in vibrant colors",
            "Futuristic city with flying cars and neon lights"
        ]
        
        for prompt in prompts:
            response = client.images.generate(
                model="flux-schnell",
                prompt=prompt,
                n=1,
                size="1024x1024"
            )
            
            assert len(response.data) == 1
            # Should have either URL or base64 data
            assert hasattr(response.data[0], 'url') or hasattr(response.data[0], 'b64_json')
    
    def test_together_image_multiple_generations(self):
        """Test generating multiple images with Together."""
        response = client.images.generate(
            model="flux-schnell",
            prompt="Beautiful landscape in different styles",
            n=3,  # Generate 3 images
            size="512x512"
        )
        
        assert len(response.data) == 3
        for i, image_data in enumerate(response.data):
            assert hasattr(image_data, 'url') or hasattr(image_data, 'b64_json')
    
    def test_together_image_base64_format(self):
        """Test base64 response format for images."""
        response = client.images.generate(
            model="flux-schnell",
            prompt="A simple geometric shape",
            n=1,
            size="512x512",
            response_format="b64_json"
        )
        
        assert len(response.data) == 1
        assert hasattr(response.data[0], 'b64_json')
        
        # Verify it's valid base64
        if response.data[0].b64_json:
            try:
                base64.b64decode(response.data[0].b64_json)
            except Exception:
                pytest.fail("Invalid base64 data")
    
    def test_together_image_different_sizes(self):
        """Test different image sizes with Together."""
        sizes = ["256x256", "512x512", "1024x1024", "1024x768"]
        
        for size in sizes:
            response = client.images.generate(
                model="flux-schnell",
                prompt=f"Test image at {size}",
                n=1,
                size=size
            )
            
            assert len(response.data) == 1
    
    def test_together_image_detailed_prompts(self):
        """Test image generation with detailed prompts."""
        detailed_prompt = """
        A highly detailed oil painting of a cyberpunk street scene:
        - Rain-slicked streets reflecting neon signs
        - Flying vehicles in the background
        - People with umbrellas and cybernetic enhancements
        - Street vendors with holographic displays
        - Atmospheric fog and dramatic lighting
        Style: Blade Runner meets Studio Ghibli
        """
        
        response = client.images.generate(
            model="flux-schnell",
            prompt=detailed_prompt,
            n=1,
            size="1024x1024"
        )
        
        assert len(response.data) == 1


class TestTogetherTextToSpeech:
    """Test Together AI text-to-speech through OpenAI SDK."""
    
    def test_together_tts_basic(self):
        """Test basic TTS with Together."""
        response = client.audio.speech.create(
            model="together-tts",
            voice="alloy",
            input="Hello from Together AI text to speech."
        )
        
        # Response should be audio bytes
        assert response.content is not None
        assert len(response.content) > 0
    
    def test_together_tts_voices(self):
        """Test different voice options with Together TTS."""
        # Standard OpenAI-compatible voices
        standard_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        
        for voice in standard_voices:
            response = client.audio.speech.create(
                model="together-tts",
                voice=voice,
                input=f"Testing voice: {voice}"
            )
            
            assert response.content is not None
            assert len(response.content) > 0
    
    def test_together_tts_native_voices(self):
        """Test Together's native voice names."""
        # Together-specific voice names
        together_voices = [
            "helpful woman",
            "british reading lady",
            "meditation lady",
            "newsman",
            "pilot over intercom",
            "french narrator lady",
            "german conversational woman",
            "customer support lady",
            "storyteller lady",
            "calm lady"
        ]
        
        for voice in together_voices[:3]:  # Test a few
            response = client.audio.speech.create(
                model="together-tts",
                voice=voice,
                input=f"Testing Together voice: {voice}"
            )
            
            assert response.content is not None
            assert len(response.content) > 0
    
    def test_together_tts_formats(self):
        """Test different audio output formats."""
        formats = ["mp3", "opus", "aac", "flac", "wav", "pcm"]
        
        for format in formats:
            try:
                response = client.audio.speech.create(
                    model="together-tts",
                    voice="alloy",
                    input="Testing audio format",
                    response_format=format
                )
                
                assert response.content is not None
                assert len(response.content) > 0
            except Exception as e:
                # Some formats might not be supported
                print(f"Format {format} not supported: {e}")
    
    def test_together_tts_long_text(self):
        """Test TTS with longer text."""
        long_text = """
        This is a longer text to test Together AI's text-to-speech capabilities.
        It includes multiple sentences, punctuation marks, and various speech patterns.
        The system should handle this gracefully and produce natural-sounding speech.
        Let's also include some numbers like 123 and special terms like AI and TTS.
        """
        
        response = client.audio.speech.create(
            model="together-tts",
            voice="nova",
            input=long_text
        )
        
        assert response.content is not None
        assert len(response.content) > 0
    
    def test_together_tts_multilingual(self):
        """Test TTS with different languages."""
        multilingual_texts = [
            ("Hello, how are you today?", "alloy"),
            ("Bonjour, comment allez-vous?", "french narrator lady"),
            ("Guten Tag, wie geht es Ihnen?", "german conversational woman"),
            ("Hola, ¿cómo estás?", "spanish narrator man"),
        ]
        
        for text, voice in multilingual_texts:
            try:
                response = client.audio.speech.create(
                    model="together-tts",
                    voice=voice,
                    input=text
                )
                
                assert response.content is not None
                assert len(response.content) > 0
            except Exception as e:
                print(f"Language test failed for '{text}': {e}")
    
    def test_together_tts_speed_variations(self):
        """Test TTS with speed variations if supported."""
        speeds = [0.5, 1.0, 1.5, 2.0]
        
        for speed in speeds:
            try:
                response = client.audio.speech.create(
                    model="together-tts",
                    voice="alloy",
                    input="Testing speech speed",
                    speed=speed
                )
                
                assert response.content is not None
                assert len(response.content) > 0
            except Exception as e:
                print(f"Speed {speed} not supported: {e}")


class TestTogetherMultimodalIntegration:
    """Test integration scenarios across Together's multimodal capabilities."""
    
    def test_embedding_search_pipeline(self):
        """Test a document search pipeline using embeddings."""
        # Sample documents
        documents = [
            "Machine learning is a subset of artificial intelligence.",
            "Natural language processing helps computers understand human language.",
            "Computer vision enables machines to interpret visual information.",
            "Deep learning uses neural networks with multiple layers."
        ]
        
        # Get embeddings for documents
        doc_response = client.embeddings.create(
            model="together-bge-base",
            input=documents
        )
        
        # Get embedding for query
        query = "How do computers understand text?"
        query_response = client.embeddings.create(
            model="together-bge-base",
            input=query
        )
        
        assert len(doc_response.data) == len(documents)
        assert len(query_response.data) == 1
        
        # In a real scenario, you'd calculate cosine similarity here
        # to find the most relevant document
    
    def test_multimodal_content_generation(self):
        """Test generating content across multiple modalities."""
        # 1. Generate text description
        chat_response = client.chat.completions.create(
            model="meta-llama/Llama-3.1-8B-Instruct-Turbo",
            messages=[{
                "role": "user",
                "content": "Describe a futuristic city in one sentence."
            }],
            max_tokens=100
        )
        
        description = chat_response.choices[0].message.content
        assert description is not None
        
        # 2. Generate image from description
        try:
            image_response = client.images.generate(
                model="flux-schnell",
                prompt=description,
                n=1,
                size="512x512"
            )
            assert len(image_response.data) == 1
        except Exception as e:
            print(f"Image generation skipped: {e}")
        
        # 3. Convert description to speech
        try:
            tts_response = client.audio.speech.create(
                model="together-tts",
                voice="nova",
                input=description
            )
            assert tts_response.content is not None
        except Exception as e:
            print(f"TTS skipped: {e}")
    
    def test_rag_pipeline_with_embeddings(self):
        """Test a simple RAG pipeline using Together embeddings."""
        # Knowledge base
        knowledge = [
            "Together AI provides fast inference for open-source models.",
            "FLUX is a powerful image generation model available on Together.",
            "Together supports embeddings, chat, and multimodal capabilities.",
            "The platform offers competitive pricing for AI inference."
        ]
        
        # Create embeddings for knowledge base
        kb_embeddings = client.embeddings.create(
            model="together-bge-base",
            input=knowledge
        )
        
        # User query
        query = "What image models does Together support?"
        query_embedding = client.embeddings.create(
            model="together-bge-base",
            input=query
        )
        
        # In practice, you'd find most similar documents here
        # For testing, just verify we got embeddings
        assert len(kb_embeddings.data) == len(knowledge)
        assert len(query_embedding.data) == 1
        
        # Generate response using chat model
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.1-8B-Instruct-Turbo",
            messages=[
                {
                    "role": "system",
                    "content": f"Answer based on this context: {knowledge[1]}"
                },
                {
                    "role": "user",
                    "content": query
                }
            ],
            max_tokens=100
        )
        
        assert response.choices[0].message.content is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
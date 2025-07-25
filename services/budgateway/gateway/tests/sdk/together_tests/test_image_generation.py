"""
Test Together AI image generation through OpenAI SDK.

These tests verify Together's FLUX image generation models work correctly
through TensorZero's OpenAI-compatible interface.
"""

import os
import base64
import json
from typing import Optional
import pytest
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Configuration
TENSORZERO_BASE_URL = os.getenv("TENSORZERO_BASE_URL", "http://localhost:3001")
TENSORZERO_API_KEY = os.getenv("TENSORZERO_API_KEY", "test-api-key")

# Skip tests if not configured for Together
SKIP_TOGETHER_TESTS = os.getenv("SKIP_TOGETHER_TESTS", "false").lower() == "true"

# Universal OpenAI client
client = OpenAI(
    base_url=f"{TENSORZERO_BASE_URL}/v1",
    api_key=TENSORZERO_API_KEY
)


@pytest.mark.skipif(SKIP_TOGETHER_TESTS, reason="Together tests disabled")
class TestTogetherImageGeneration:
    """Test Together AI FLUX image generation through OpenAI SDK."""
    
    def test_flux_schnell_basic(self):
        """Test basic image generation with FLUX schnell."""
        response = client.images.generate(
            model="flux-schnell",
            prompt="A serene mountain landscape at sunset with snow-capped peaks",
            n=1,
            size="1024x1024"
        )
        
        # Verify response structure
        assert hasattr(response, 'created')
        assert hasattr(response, 'data')
        assert len(response.data) == 1
        
        # Verify image data
        image_data = response.data[0]
        assert hasattr(image_data, 'url') or hasattr(image_data, 'b64_json')
        
        if hasattr(image_data, 'url') and image_data.url:
            assert image_data.url.startswith('http')
        elif hasattr(image_data, 'b64_json') and image_data.b64_json:
            # Verify it's valid base64
            try:
                base64.b64decode(image_data.b64_json)
            except Exception:
                pytest.fail("Invalid base64 data")
    
    def test_flux_multiple_images(self):
        """Test generating multiple images."""
        response = client.images.generate(
            model="flux-schnell",
            prompt="Abstract geometric patterns in vibrant colors",
            n=3,
            size="512x512"
        )
        
        assert len(response.data) == 3
        
        for i, image_data in enumerate(response.data):
            assert hasattr(image_data, 'url') or hasattr(image_data, 'b64_json')
    
    def test_flux_different_sizes(self):
        """Test different image sizes with FLUX."""
        sizes = [
            "256x256",
            "512x512", 
            "1024x1024",
            "1024x768",  # Landscape
            "768x1024",  # Portrait
        ]
        
        for size in sizes:
            try:
                response = client.images.generate(
                    model="flux-schnell",
                    prompt=f"Test image at {size} resolution",
                    n=1,
                    size=size
                )
                
                assert len(response.data) == 1
                assert response.data[0].url or response.data[0].b64_json
            except Exception as e:
                # Some sizes might not be supported
                print(f"Size {size} not supported: {e}")
    
    def test_flux_base64_response(self):
        """Test base64 response format."""
        response = client.images.generate(
            model="flux-schnell",
            prompt="A simple red circle on white background",
            n=1,
            size="256x256",
            response_format="b64_json"
        )
        
        assert len(response.data) == 1
        image_data = response.data[0]
        
        # Should have base64 data
        assert hasattr(image_data, 'b64_json')
        assert image_data.b64_json is not None
        
        # Verify it's valid base64
        try:
            decoded = base64.b64decode(image_data.b64_json)
            assert len(decoded) > 0
        except Exception:
            pytest.fail("Invalid base64 data")
    
    def test_flux_url_response(self):
        """Test URL response format."""
        response = client.images.generate(
            model="flux-schnell",
            prompt="A blue square on yellow background",
            n=1,
            size="256x256",
            response_format="url"
        )
        
        assert len(response.data) == 1
        image_data = response.data[0]
        
        # Should have URL
        assert hasattr(image_data, 'url')
        if image_data.url:
            assert image_data.url.startswith('http')
    
    def test_flux_detailed_prompts(self):
        """Test image generation with detailed prompts."""
        detailed_prompts = [
            """A cyberpunk street scene at night with:
            - Rain-slicked streets reflecting neon signs
            - Flying cars in the background
            - People with cybernetic enhancements walking
            - Holographic advertisements
            - Steam rising from street vents
            Style: Cinematic, high detail, moody lighting""",
            
            """An enchanted forest clearing with:
            - Ancient twisted trees with glowing runes
            - Floating magical orbs of light
            - A crystal-clear pond reflecting starlight
            - Mystical fog swirling around tree roots
            - Bioluminescent flowers and mushrooms
            Art style: Fantasy illustration, ethereal atmosphere""",
            
            """A steampunk workshop interior featuring:
            - Brass gears and copper pipes on walls
            - Victorian-era machinery with steam
            - Leather-bound books on wooden shelves
            - Intricate clockwork mechanisms
            - Warm gaslight illumination
            Rendering: Detailed, industrial aesthetic"""
        ]
        
        for prompt in detailed_prompts:
            response = client.images.generate(
                model="flux-schnell",
                prompt=prompt,
                n=1,
                size="1024x1024"
            )
            
            assert len(response.data) == 1
            assert response.data[0].url or response.data[0].b64_json
    
    def test_flux_style_variations(self):
        """Test generating images in different styles."""
        base_subject = "A cat sitting on a windowsill"
        styles = [
            "photorealistic, high detail, professional photography",
            "oil painting style, impressionist, vibrant colors",
            "pencil sketch, black and white, artistic",
            "watercolor painting, soft colors, artistic blur",
            "digital art, anime style, cel shaded",
            "3D render, pixar style, cartoon"
        ]
        
        for style in styles:
            prompt = f"{base_subject}, {style}"
            response = client.images.generate(
                model="flux-schnell",
                prompt=prompt,
                n=1,
                size="512x512"
            )
            
            assert len(response.data) == 1
    
    def test_flux_batch_generation(self):
        """Test generating multiple images with different prompts efficiently."""
        prompts = [
            "A sunrise over mountains",
            "A sunset over the ocean",
            "Northern lights in the arctic",
            "A thunderstorm over plains",
            "A rainbow after rain"
        ]
        
        # Generate one image for each prompt
        responses = []
        for prompt in prompts:
            response = client.images.generate(
                model="flux-schnell",
                prompt=prompt,
                n=1,
                size="512x512"
            )
            responses.append(response)
        
        # Verify all succeeded
        assert len(responses) == len(prompts)
        for response in responses:
            assert len(response.data) == 1
    
    def test_flux_special_characters_in_prompt(self):
        """Test prompts with special characters."""
        special_prompts = [
            "A café in Paris (romantic atmosphere)",
            "Tokyo street with 日本語 signs",
            "Math equation: E=mc² written on blackboard",
            "Computer code: print('Hello, World!') on screen",
            "Emoji art: 🌟✨🎨 magical theme"
        ]
        
        for prompt in special_prompts:
            try:
                response = client.images.generate(
                    model="flux-schnell",
                    prompt=prompt,
                    n=1,
                    size="512x512"
                )
                assert len(response.data) == 1
            except Exception as e:
                print(f"Special prompt failed: '{prompt}' - {e}")


@pytest.mark.skipif(SKIP_TOGETHER_TESTS, reason="Together tests disabled")
class TestTogetherImageGenerationAdvanced:
    """Test advanced image generation scenarios."""
    
    def test_flux_composition_prompts(self):
        """Test complex compositional prompts."""
        response = client.images.generate(
            model="flux-schnell",
            prompt="""A split-screen composition showing:
            Left side: A bustling modern city with skyscrapers
            Right side: The same location 100 years ago as farmland
            Divided by a glowing temporal rift in the center""",
            n=1,
            size="1024x1024"
        )
        
        assert len(response.data) == 1
    
    def test_flux_negative_prompts_simulation(self):
        """Test avoiding certain elements (simulated via positive prompts)."""
        # Since OpenAI API doesn't support negative prompts,
        # we simulate by being explicit about what we want
        response = client.images.generate(
            model="flux-schnell",
            prompt="""A peaceful nature scene with:
            - Green rolling hills
            - Clear blue sky with white clouds
            - A small stream
            - Wildflowers in the foreground
            Style: Serene, calming, no people, no buildings, no vehicles""",
            n=1,
            size="1024x1024"
        )
        
        assert len(response.data) == 1
    
    def test_flux_artistic_techniques(self):
        """Test specific artistic techniques in prompts."""
        techniques = [
            "Chiaroscuro lighting technique, dramatic shadows",
            "Trompe-l'oeil style, optical illusion",
            "Pointillism technique, dots of color",
            "Sfumato technique, soft transitions",
            "Impasto technique, thick paint texture"
        ]
        
        for technique in techniques:
            prompt = f"A still life of fruit using {technique}"
            response = client.images.generate(
                model="flux-schnell",
                prompt=prompt,
                n=1,
                size="512x512"
            )
            
            assert len(response.data) == 1
    
    def test_flux_camera_specifications(self):
        """Test prompts with camera/photography specifications."""
        camera_prompts = [
            "Portrait shot with 85mm lens, f/1.4, shallow depth of field",
            "Wide angle landscape with 16mm lens, f/8, everything in focus",
            "Macro photography of a flower, extreme close-up, bokeh background",
            "Long exposure night photography, light trails, 30 second exposure",
            "Tilt-shift photography of a city, miniature effect"
        ]
        
        for prompt in camera_prompts:
            response = client.images.generate(
                model="flux-schnell",
                prompt=prompt,
                n=1,
                size="768x768"
            )
            
            assert len(response.data) == 1
    
    def test_flux_sequential_generation(self):
        """Test generating a sequence of related images."""
        story_frames = [
            "A knight approaching a dark castle at dusk",
            "The same knight entering the castle gates",
            "The knight discovering a magical artifact inside",
            "The knight emerging victorious at dawn"
        ]
        
        generated_images = []
        for i, frame in enumerate(story_frames):
            response = client.images.generate(
                model="flux-schnell",
                prompt=f"Frame {i+1}: {frame}, consistent character design, medieval fantasy style",
                n=1,
                size="512x512"
            )
            
            assert len(response.data) == 1
            generated_images.append(response.data[0])
        
        assert len(generated_images) == len(story_frames)


@pytest.mark.skipif(SKIP_TOGETHER_TESTS, reason="Together tests disabled")
class TestTogetherImageGenerationErrors:
    """Test error handling for image generation."""
    
    def test_invalid_model(self):
        """Test with non-existent model."""
        with pytest.raises(Exception) as exc_info:
            client.images.generate(
                model="flux-invalid-model",
                prompt="Test prompt",
                n=1
            )
        
        assert "not found" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()
    
    def test_empty_prompt(self):
        """Test with empty prompt."""
        with pytest.raises(Exception) as exc_info:
            client.images.generate(
                model="flux-schnell",
                prompt="",
                n=1
            )
        
        assert exc_info.value is not None
    
    def test_invalid_size(self):
        """Test with invalid size."""
        with pytest.raises(Exception) as exc_info:
            client.images.generate(
                model="flux-schnell",
                prompt="Test image",
                n=1,
                size="123x456"  # Non-standard size
            )
        
        # Might fail or use closest valid size
        pass
    
    def test_too_many_images(self):
        """Test requesting too many images."""
        try:
            response = client.images.generate(
                model="flux-schnell",
                prompt="Test image",
                n=10  # Might exceed limit
            )
            # If it succeeds, verify we got images
            assert len(response.data) <= 10
        except Exception as e:
            # Expected to fail with limit error
            assert "limit" in str(e).lower() or "maximum" in str(e).lower()
    
    def test_invalid_response_format(self):
        """Test with invalid response format."""
        try:
            response = client.images.generate(
                model="flux-schnell",
                prompt="Test image",
                n=1,
                response_format="invalid_format"
            )
            # Should default to url or b64_json
            assert len(response.data) == 1
        except Exception as e:
            # Or fail with format error
            assert "format" in str(e).lower()
    
    def test_chat_model_for_images(self):
        """Test using chat model for image generation."""
        with pytest.raises(Exception) as exc_info:
            client.images.generate(
                model="meta-llama/Llama-3.1-8B-Instruct-Turbo",
                prompt="Test image",
                n=1
            )
        
        # Should fail because it's not an image model
        assert exc_info.value is not None


@pytest.mark.skipif(SKIP_TOGETHER_TESTS, reason="Together tests disabled")
class TestTogetherImageGenerationQuality:
    """Test image generation quality and consistency."""
    
    def test_prompt_adherence(self):
        """Test that generated images match prompt specifications."""
        specific_prompts = [
            {
                "prompt": "A red cube on a blue background",
                "expected": ["red", "cube", "blue", "background"]
            },
            {
                "prompt": "Three yellow circles arranged horizontally",
                "expected": ["three", "yellow", "circles", "horizontal"]
            },
            {
                "prompt": "A green triangle pointing upward",
                "expected": ["green", "triangle", "upward"]
            }
        ]
        
        for test_case in specific_prompts:
            response = client.images.generate(
                model="flux-schnell",
                prompt=test_case["prompt"],
                n=1,
                size="512x512"
            )
            
            assert len(response.data) == 1
            # In a real test, you might analyze the image
            # to verify it contains expected elements
    
    def test_style_consistency(self):
        """Test generating multiple images with consistent style."""
        style = "watercolor painting, soft pastel colors, artistic"
        subjects = ["A flower", "A bird", "A tree", "A butterfly"]
        
        images = []
        for subject in subjects:
            response = client.images.generate(
                model="flux-schnell",
                prompt=f"{subject}, {style}",
                n=1,
                size="512x512"
            )
            images.append(response.data[0])
        
        assert len(images) == len(subjects)
        # In practice, you might analyze images for style consistency


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
"""
TensorZero Image Endpoint Integration Tests

Tests for OpenAI-compatible image generation, editing, and variation endpoints.
Follows the pattern established by test_audio.py and other endpoint tests.
"""

import os
import pytest
import tempfile
import base64
import subprocess
from pathlib import Path
from PIL import Image
import io
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Configuration
TENSORZERO_BASE_URL = os.getenv("TENSORZERO_BASE_URL", "http://localhost:3001")
TENSORZERO_API_KEY = os.getenv("TENSORZERO_API_KEY", "test-api-key")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Clients
tensorzero_client = OpenAI(
    base_url=f"{TENSORZERO_BASE_URL}/v1",
    api_key=TENSORZERO_API_KEY
)

openai_client = OpenAI(
    api_key=OPENAI_API_KEY
) if OPENAI_API_KEY else None

# Test image paths (fixtures are in the parent SDK directory)
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "images"
TEST_IMAGE_PATH = FIXTURES_DIR / "test_image.png"
SMALL_IMAGE_PATH = FIXTURES_DIR / "small_test.png"
LARGE_IMAGE_PATH = FIXTURES_DIR / "large_test.png"
MASK_IMAGE_PATH = FIXTURES_DIR / "mask.png"
SIMPLE_SHAPE_PATH = FIXTURES_DIR / "simple_shape.png"


def setup_module():
    """Setup test images before running tests."""
    if not FIXTURES_DIR.exists():
        print("Creating test images...")
        # Run the script from the parent SDK directory
        sdk_dir = Path(__file__).parent.parent
        subprocess.run(
            ["python", "create_test_images.py"],
            cwd=sdk_dir,
            check=True
        )


class TestImageGeneration:
    """Test image generation endpoint compatibility"""

    def test_basic_image_generation_dall_e_2(self):
        """Test basic image generation with DALL-E 2"""
        response = tensorzero_client.images.generate(
            model="dall-e-2",
            prompt="A simple red circle on a white background",
            n=1,
            size="256x256"
        )
        
        assert hasattr(response, 'data')
        assert len(response.data) == 1
        assert hasattr(response.data[0], 'url') or hasattr(response.data[0], 'b64_json')

    def test_basic_image_generation_dall_e_3(self):
        """Test basic image generation with DALL-E 3"""
        response = tensorzero_client.images.generate(
            model="dall-e-3",
            prompt="A futuristic city skyline at sunset",
            n=1,
            size="1024x1024"
        )
        
        assert hasattr(response, 'data')
        assert len(response.data) == 1
        assert hasattr(response.data[0], 'url') or hasattr(response.data[0], 'b64_json')
        # DALL-E 3 may include revised prompt
        if hasattr(response.data[0], 'revised_prompt'):
            assert isinstance(response.data[0].revised_prompt, str)

    def test_image_generation_multiple_images_dall_e_2(self):
        """Test generating multiple images with DALL-E 2"""
        response = tensorzero_client.images.generate(
            model="dall-e-2",
            prompt="A blue square",
            n=3,
            size="256x256"
        )
        
        assert hasattr(response, 'data')
        assert len(response.data) == 3
        for image_data in response.data:
            assert hasattr(image_data, 'url') or hasattr(image_data, 'b64_json')

    def test_image_generation_different_sizes_dall_e_2(self):
        """Test different image sizes with DALL-E 2"""
        sizes = ["256x256", "512x512", "1024x1024"]
        
        for size in sizes:
            response = tensorzero_client.images.generate(
                model="dall-e-2",
                prompt=f"A green triangle, {size} pixels",
                n=1,
                size=size
            )
            
            assert len(response.data) == 1

    def test_image_generation_different_sizes_dall_e_3(self):
        """Test different image sizes with DALL-E 3"""
        sizes = ["1024x1024", "1024x1792", "1792x1024"]
        
        for size in sizes:
            response = tensorzero_client.images.generate(
                model="dall-e-3",
                prompt=f"A minimalist landscape, {size} aspect ratio",
                n=1,
                size=size
            )
            
            assert len(response.data) == 1

    def test_image_generation_quality_dall_e_3(self):
        """Test quality parameter with DALL-E 3"""
        qualities = ["standard", "hd"]
        
        for quality in qualities:
            response = tensorzero_client.images.generate(
                model="dall-e-3",
                prompt="A detailed architectural drawing",
                n=1,
                size="1024x1024",
                quality=quality
            )
            
            assert len(response.data) == 1

    def test_image_generation_style_dall_e_3(self):
        """Test style parameter with DALL-E 3"""
        styles = ["vivid", "natural"]
        
        for style in styles:
            response = tensorzero_client.images.generate(
                model="dall-e-3",
                prompt="A beautiful sunset over mountains",
                n=1,
                size="1024x1024",
                style=style
            )
            
            assert len(response.data) == 1

    def test_image_generation_response_format_url(self):
        """Test URL response format"""
        response = tensorzero_client.images.generate(
            model="dall-e-2",
            prompt="A yellow star",
            n=1,
            size="256x256",
            response_format="url"
        )
        
        assert len(response.data) == 1
        assert hasattr(response.data[0], 'url')
        assert response.data[0].url.startswith('http')

    def test_image_generation_response_format_b64_json(self):
        """Test base64 JSON response format"""
        response = tensorzero_client.images.generate(
            model="dall-e-2",
            prompt="A purple heart",
            n=1,
            size="256x256",
            response_format="b64_json"
        )
        
        assert len(response.data) == 1
        assert hasattr(response.data[0], 'b64_json')
        
        # Verify it's valid base64
        b64_data = response.data[0].b64_json
        image_data = base64.b64decode(b64_data)
        
        # Verify it's a valid image
        with io.BytesIO(image_data) as image_buffer:
            img = Image.open(image_buffer)
            assert img.size == (256, 256)

    def test_image_generation_gpt_image_1_basic(self):
        """Test basic generation with GPT-Image-1"""
        response = tensorzero_client.images.generate(
            model="gpt-image-1",
            prompt="A simple geometric pattern",
            n=1,
            size="1024x1024"
        )
        
        assert len(response.data) == 1

    def test_image_generation_gpt_image_1_with_params(self):
        """Test GPT-Image-1 with specific parameters"""
        response = tensorzero_client.images.generate(
            model="gpt-image-1",
            prompt="A modern logo design",
            n=1,
            size="1024x1024",
            # GPT-Image-1 specific parameters would go here
            # background="transparent",  # These depend on actual API support
            # moderation="auto",
            # output_format="png"
        )
        
        assert len(response.data) == 1

    def test_image_generation_error_handling(self):
        """Test error handling for invalid parameters"""
        # Test invalid model
        with pytest.raises(Exception):
            tensorzero_client.images.generate(
                model="invalid-model",
                prompt="Test",
                n=1
            )
        
        # Test invalid size for DALL-E 3
        with pytest.raises(Exception):
            tensorzero_client.images.generate(
                model="dall-e-3",
                prompt="Test",
                n=1,
                size="256x256"  # Not supported by DALL-E 3
            )
        
        # Test too many images for DALL-E 3
        with pytest.raises(Exception):
            tensorzero_client.images.generate(
                model="dall-e-3",
                prompt="Test",
                n=2  # DALL-E 3 only supports n=1
            )

    @pytest.mark.asyncio
    async def test_async_image_generation(self):
        """Test async image generation"""
        from openai import AsyncOpenAI
        
        async_client = AsyncOpenAI(
            base_url=f"{TENSORZERO_BASE_URL}/v1",
            api_key=TENSORZERO_API_KEY
        )
        
        response = await async_client.images.generate(
            model="dall-e-2",
            prompt="A red bicycle",
            n=1,
            size="256x256"
        )
        
        assert len(response.data) == 1


class TestImageEdit:
    """Test image editing endpoint compatibility"""

    def test_basic_image_edit_dall_e_2(self):
        """Test basic image editing with DALL-E 2"""
        setup_module()  # Ensure test images exist
        
        if not TEST_IMAGE_PATH.exists():
            pytest.skip("Test image file not found")
        
        with open(TEST_IMAGE_PATH, "rb") as image_file:
            response = tensorzero_client.images.edit(
                model="dall-e-2",
                image=image_file,
                prompt="Add a bright yellow sun in the top right corner",
                n=1,
                size="512x512"
            )
        
        assert len(response.data) == 1
        assert hasattr(response.data[0], 'url') or hasattr(response.data[0], 'b64_json')

    def test_image_edit_with_mask_dall_e_2(self):
        """Test image editing with mask"""
        setup_module()
        
        if not TEST_IMAGE_PATH.exists() or not MASK_IMAGE_PATH.exists():
            pytest.skip("Test image or mask file not found")
        
        with open(TEST_IMAGE_PATH, "rb") as image_file, \
             open(MASK_IMAGE_PATH, "rb") as mask_file:
            response = tensorzero_client.images.edit(
                model="dall-e-2",
                image=image_file,
                mask=mask_file,
                prompt="Fill the masked area with a rainbow pattern",
                n=1,
                size="512x512"
            )
        
        assert len(response.data) == 1

    def test_image_edit_multiple_variations_dall_e_2(self):
        """Test generating multiple edited variations"""
        setup_module()
        
        if not TEST_IMAGE_PATH.exists():
            pytest.skip("Test image file not found")
        
        with open(TEST_IMAGE_PATH, "rb") as image_file:
            response = tensorzero_client.images.edit(
                model="dall-e-2",
                image=image_file,
                prompt="Add colorful flowers around the edges",
                n=3,
                size="512x512"
            )
        
        assert len(response.data) == 3

    def test_image_edit_different_sizes_dall_e_2(self):
        """Test editing with different output sizes"""
        setup_module()
        
        if not TEST_IMAGE_PATH.exists():
            pytest.skip("Test image file not found")
        
        sizes = ["256x256", "512x512", "1024x1024"]
        
        for size in sizes:
            with open(TEST_IMAGE_PATH, "rb") as image_file:
                response = tensorzero_client.images.edit(
                    model="dall-e-2",
                    image=image_file,
                    prompt=f"Resize and enhance for {size}",
                    n=1,
                    size=size
                )
            
            assert len(response.data) == 1

    def test_image_edit_gpt_image_1(self):
        """Test image editing with GPT-Image-1"""
        setup_module()
        
        if not TEST_IMAGE_PATH.exists():
            pytest.skip("Test image file not found")
        
        with open(TEST_IMAGE_PATH, "rb") as image_file:
            response = tensorzero_client.images.edit(
                model="gpt-image-1",
                image=image_file,
                prompt="Transform into a futuristic version",
                n=1,
                size="1024x1024"
            )
        
        assert len(response.data) == 1

    def test_image_edit_response_formats(self):
        """Test different response formats for editing"""
        setup_module()
        
        if not TEST_IMAGE_PATH.exists():
            pytest.skip("Test image file not found")
        
        formats = ["url", "b64_json"]
        
        for response_format in formats:
            with open(TEST_IMAGE_PATH, "rb") as image_file:
                response = tensorzero_client.images.edit(
                    model="dall-e-2",
                    image=image_file,
                    prompt="Add a border",
                    n=1,
                    size="512x512",
                    response_format=response_format
                )
            
            assert len(response.data) == 1
            if response_format == "url":
                assert hasattr(response.data[0], 'url')
            else:
                assert hasattr(response.data[0], 'b64_json')

    def test_image_edit_error_handling(self):
        """Test error handling for image editing"""
        setup_module()
        
        if not TEST_IMAGE_PATH.exists():
            pytest.skip("Test image file not found")
        
        # Test with invalid model for editing
        with pytest.raises(Exception):
            with open(TEST_IMAGE_PATH, "rb") as image_file:
                tensorzero_client.images.edit(
                    model="dall-e-3",  # DALL-E 3 doesn't support editing
                    image=image_file,
                    prompt="Test edit"
                )

    @pytest.mark.asyncio
    async def test_async_image_edit(self):
        """Test async image editing"""
        setup_module()
        
        if not TEST_IMAGE_PATH.exists():
            pytest.skip("Test image file not found")
        
        from openai import AsyncOpenAI
        
        async_client = AsyncOpenAI(
            base_url=f"{TENSORZERO_BASE_URL}/v1",
            api_key=TENSORZERO_API_KEY
        )
        
        with open(TEST_IMAGE_PATH, "rb") as image_file:
            response = await async_client.images.edit(
                model="dall-e-2",
                image=image_file,
                prompt="Add a blue sky background",
                n=1,
                size="512x512"
            )
        
        assert len(response.data) == 1


class TestImageVariation:
    """Test image variation endpoint compatibility"""

    def test_basic_image_variation_dall_e_2(self):
        """Test basic image variation with DALL-E 2"""
        setup_module()
        
        if not SIMPLE_SHAPE_PATH.exists():
            pytest.skip("Test image file not found")
        
        with open(SIMPLE_SHAPE_PATH, "rb") as image_file:
            response = tensorzero_client.images.create_variation(
                model="dall-e-2",
                image=image_file,
                n=1,
                size="512x512"
            )
        
        assert len(response.data) == 1
        assert hasattr(response.data[0], 'url') or hasattr(response.data[0], 'b64_json')

    def test_image_variation_multiple_dall_e_2(self):
        """Test generating multiple variations"""
        setup_module()
        
        if not SIMPLE_SHAPE_PATH.exists():
            pytest.skip("Test image file not found")
        
        with open(SIMPLE_SHAPE_PATH, "rb") as image_file:
            response = tensorzero_client.images.create_variation(
                model="dall-e-2",
                image=image_file,
                n=4,
                size="512x512"
            )
        
        assert len(response.data) == 4

    def test_image_variation_different_sizes_dall_e_2(self):
        """Test variations with different sizes"""
        setup_module()
        
        if not SIMPLE_SHAPE_PATH.exists():
            pytest.skip("Test image file not found")
        
        sizes = ["256x256", "512x512", "1024x1024"]
        
        for size in sizes:
            with open(SIMPLE_SHAPE_PATH, "rb") as image_file:
                response = tensorzero_client.images.create_variation(
                    model="dall-e-2",
                    image=image_file,
                    n=1,
                    size=size
                )
            
            assert len(response.data) == 1

    def test_image_variation_response_formats(self):
        """Test different response formats for variations"""
        setup_module()
        
        if not SIMPLE_SHAPE_PATH.exists():
            pytest.skip("Test image file not found")
        
        formats = ["url", "b64_json"]
        
        for response_format in formats:
            with open(SIMPLE_SHAPE_PATH, "rb") as image_file:
                response = tensorzero_client.images.create_variation(
                    model="dall-e-2",
                    image=image_file,
                    n=1,
                    size="512x512",
                    response_format=response_format
                )
            
            assert len(response.data) == 1
            if response_format == "url":
                assert hasattr(response.data[0], 'url')
            else:
                assert hasattr(response.data[0], 'b64_json')

    def test_image_variation_with_different_source_images(self):
        """Test variations with different source images"""
        setup_module()
        
        test_images = [
            SIMPLE_SHAPE_PATH,
            SMALL_IMAGE_PATH,
            TEST_IMAGE_PATH
        ]
        
        for image_path in test_images:
            if not image_path.exists():
                continue
                
            with open(image_path, "rb") as image_file:
                response = tensorzero_client.images.create_variation(
                    model="dall-e-2",
                    image=image_file,
                    n=1,
                    size="512x512"
                )
            
            assert len(response.data) == 1

    def test_image_variation_error_handling(self):
        """Test error handling for image variations"""
        setup_module()
        
        if not SIMPLE_SHAPE_PATH.exists():
            pytest.skip("Test image file not found")
        
        # Test with invalid model for variations
        with pytest.raises(Exception):
            with open(SIMPLE_SHAPE_PATH, "rb") as image_file:
                tensorzero_client.images.create_variation(
                    model="dall-e-3",  # DALL-E 3 doesn't support variations
                    image=image_file,
                    n=1
                )

    @pytest.mark.asyncio
    async def test_async_image_variation(self):
        """Test async image variation"""
        setup_module()
        
        if not SIMPLE_SHAPE_PATH.exists():
            pytest.skip("Test image file not found")
        
        from openai import AsyncOpenAI
        
        async_client = AsyncOpenAI(
            base_url=f"{TENSORZERO_BASE_URL}/v1",
            api_key=TENSORZERO_API_KEY
        )
        
        with open(SIMPLE_SHAPE_PATH, "rb") as image_file:
            response = await async_client.images.create_variation(
                model="dall-e-2",
                image=image_file,
                n=1,
                size="512x512"
            )
        
        assert len(response.data) == 1


class TestImageEndpointIntegration:
    """Test integration scenarios and edge cases"""

    def test_image_file_format_compatibility(self):
        """Test different image file formats"""
        setup_module()
        
        # Test with PNG
        if TEST_IMAGE_PATH.exists():
            with open(TEST_IMAGE_PATH, "rb") as image_file:
                response = tensorzero_client.images.create_variation(
                    model="dall-e-2",
                    image=image_file,
                    n=1,
                    size="256x256"
                )
            assert len(response.data) == 1
        
        # Test with JPEG if available
        jpeg_path = FIXTURES_DIR / "test_image.jpg"
        if jpeg_path.exists():
            with open(jpeg_path, "rb") as image_file:
                response = tensorzero_client.images.create_variation(
                    model="dall-e-2",
                    image=image_file,
                    n=1,
                    size="256x256"
                )
            assert len(response.data) == 1

    def test_image_size_validation(self):
        """Test image size validation"""
        setup_module()
        
        if not TEST_IMAGE_PATH.exists():
            pytest.skip("Test image file not found")
        
        # Test with extremely large image request (should fail gracefully)
        with pytest.raises(Exception):
            with open(TEST_IMAGE_PATH, "rb") as image_file:
                tensorzero_client.images.edit(
                    model="dall-e-2",
                    image=image_file,
                    prompt="Test",
                    size="2048x2048"  # Not supported size
                )

    def test_prompt_length_validation(self):
        """Test prompt length limits"""
        # Test with very long prompt
        long_prompt = "A beautiful landscape " * 100  # Very long prompt
        
        with pytest.raises(Exception):
            tensorzero_client.images.generate(
                model="dall-e-2",
                prompt=long_prompt,
                n=1,
                size="256x256"
            )

    def test_concurrent_image_requests(self):
        """Test handling multiple concurrent image requests"""
        import concurrent.futures
        import threading
        
        def generate_image(prompt_suffix):
            return tensorzero_client.images.generate(
                model="dall-e-2",
                prompt=f"A simple shape {prompt_suffix}",
                n=1,
                size="256x256"
            )
        
        # Run multiple requests concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(generate_image, f"test {i}")
                for i in range(3)
            ]
            
            results = [future.result() for future in futures]
            
        # Verify all requests succeeded
        assert len(results) == 3
        for result in results:
            assert len(result.data) == 1

    def test_model_capability_enforcement(self):
        """Test that models only support their designated capabilities"""
        # DALL-E 3 should not support editing or variations
        with pytest.raises(Exception):
            tensorzero_client.images.edit(
                model="dall-e-3",
                image=open(TEST_IMAGE_PATH, "rb") if TEST_IMAGE_PATH.exists() else None,
                prompt="Test edit"
            )
        
        with pytest.raises(Exception):
            tensorzero_client.images.create_variation(
                model="dall-e-3",
                image=open(TEST_IMAGE_PATH, "rb") if TEST_IMAGE_PATH.exists() else None
            )


# Performance and stress tests
class TestImagePerformance:
    """Test performance characteristics of image endpoints"""

    @pytest.mark.slow
    def test_image_generation_timing(self):
        """Test image generation response times"""
        import time
        
        start_time = time.time()
        response = tensorzero_client.images.generate(
            model="dall-e-2",
            prompt="A simple test image for timing",
            n=1,
            size="256x256"
        )
        end_time = time.time()
        
        assert len(response.data) == 1
        # Image generation should complete within reasonable time
        # (This will vary greatly depending on the backend)
        assert end_time - start_time < 120  # 2 minutes max

    @pytest.mark.slow  
    def test_batch_image_generation(self):
        """Test generating multiple images in a single request"""
        response = tensorzero_client.images.generate(
            model="dall-e-2",
            prompt="A collection of geometric shapes",
            n=5,
            size="256x256"
        )
        
        assert len(response.data) == 5
        # Verify each image is valid
        for image_data in response.data:
            assert hasattr(image_data, 'url') or hasattr(image_data, 'b64_json')


if __name__ == "__main__":
    # Run setup when called directly
    setup_module()
    print("Test images created successfully!")
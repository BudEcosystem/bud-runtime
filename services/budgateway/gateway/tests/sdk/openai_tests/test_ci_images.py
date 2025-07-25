"""
CI-friendly image endpoint tests using dummy providers.
These tests don't require real OpenAI API keys and can run in CI environments.
"""

import os
import pytest
import base64
import subprocess
from pathlib import Path
from PIL import Image
import io
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Configuration for CI
TENSORZERO_BASE_URL = os.getenv("TENSORZERO_BASE_URL", "http://localhost:3001")
TENSORZERO_API_KEY = os.getenv("TENSORZERO_API_KEY", "test-api-key")

# Client configured for dummy provider testing
tensorzero_client = OpenAI(
    base_url=f"{TENSORZERO_BASE_URL}/v1",
    api_key=TENSORZERO_API_KEY
)

# Test image paths (fixtures are in the parent SDK directory)
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "images"
TEST_IMAGE_PATH = FIXTURES_DIR / "test_image.png"


def setup_module():
    """Setup test images before running tests."""
    if not FIXTURES_DIR.exists():
        # Run the script from the parent SDK directory
        sdk_dir = Path(__file__).parent.parent
        subprocess.run(
            ["python", "create_test_images.py"],
            cwd=sdk_dir,
            check=True
        )


class TestImageGenerationCI:
    """Test image generation with dummy provider"""

    def test_basic_image_generation_dall_e_2(self):
        """Test basic image generation with DALL-E 2 (dummy provider)"""
        response = tensorzero_client.images.generate(
            model="dall-e-2",
            prompt="A simple red circle on a white background",
            n=1,
            size="256x256"
        )
        
        # Dummy provider returns URL by default
        assert hasattr(response, 'data')
        assert len(response.data) == 1
        
        # Should have either URL or b64_json (dummy provider returns URL by default)
        image_data = response.data[0]
        assert hasattr(image_data, 'url') or hasattr(image_data, 'b64_json')
        
        if hasattr(image_data, 'url') and image_data.url:
            assert image_data.url.startswith('https://example.com/dummy-image-')
        elif hasattr(image_data, 'b64_json') and image_data.b64_json:
            # If base64 is provided, verify it's valid
            decoded_data = base64.b64decode(image_data.b64_json)
            with io.BytesIO(decoded_data) as image_buffer:
                img = Image.open(image_buffer)
                assert img.format == 'PNG'

    def test_image_generation_multiple_images(self):
        """Test generating multiple images"""
        response = tensorzero_client.images.generate(
            model="dall-e-2",
            prompt="A blue square",
            n=3,
            size="256x256"
        )
        
        assert len(response.data) == 3
        for image_data in response.data:
            assert hasattr(image_data, 'url') or hasattr(image_data, 'b64_json')
            if hasattr(image_data, 'url') and image_data.url:
                assert image_data.url.startswith('https://example.com/dummy-image-')

    def test_image_generation_dall_e_3(self):
        """Test DALL-E 3 generation (dummy provider)"""
        response = tensorzero_client.images.generate(
            model="dall-e-3",
            prompt="A futuristic city",
            n=1,
            size="1024x1024"
        )
        
        assert len(response.data) == 1
        image_data = response.data[0]
        assert hasattr(image_data, 'url') or hasattr(image_data, 'b64_json')
        if hasattr(image_data, 'url') and image_data.url:
            assert image_data.url.startswith('https://example.com/dummy-image-')

    def test_image_generation_gpt_image_1(self):
        """Test GPT-Image-1 generation (dummy provider)"""
        response = tensorzero_client.images.generate(
            model="gpt-image-1",
            prompt="A logo design",
            n=1,
            size="1024x1024"
        )
        
        assert len(response.data) == 1
        image_data = response.data[0]
        assert hasattr(image_data, 'url') or hasattr(image_data, 'b64_json')
        if hasattr(image_data, 'url') and image_data.url:
            assert image_data.url.startswith('https://example.com/dummy-image-')


class TestImageEditCI:
    """Test image editing with dummy provider"""

    def test_basic_image_edit(self):
        """Test basic image editing (dummy provider)"""
        setup_module()
        
        if not TEST_IMAGE_PATH.exists():
            pytest.skip("Test image file not found")
        
        with open(TEST_IMAGE_PATH, "rb") as image_file:
            response = tensorzero_client.images.edit(
                model="dall-e-2",
                image=image_file,
                prompt="Add a bright yellow sun",
                n=1,
                size="512x512",
                response_format="b64_json"
            )
        
        assert len(response.data) == 1
        image_data = response.data[0]
        # We requested b64_json format, so should get base64 data
        assert hasattr(image_data, 'b64_json')
        assert image_data.b64_json is not None

    def test_image_edit_gpt_image_1(self):
        """Test image editing with GPT-Image-1 (dummy provider)"""
        setup_module()
        
        if not TEST_IMAGE_PATH.exists():
            pytest.skip("Test image file not found")
        
        with open(TEST_IMAGE_PATH, "rb") as image_file:
            response = tensorzero_client.images.edit(
                model="gpt-image-1",
                image=image_file,
                prompt="Transform into futuristic version",
                n=1,
                size="1024x1024"
            )
        
        assert len(response.data) == 1
        image_data = response.data[0]
        assert hasattr(image_data, 'url') or hasattr(image_data, 'b64_json')
        if hasattr(image_data, 'url') and image_data.url:
            assert image_data.url.startswith('https://example.com/dummy-edited-image-')


class TestImageVariationCI:
    """Test image variations with dummy provider"""

    def test_basic_image_variation(self):
        """Test basic image variation (dummy provider)"""
        setup_module()
        
        if not TEST_IMAGE_PATH.exists():
            pytest.skip("Test image file not found")
        
        with open(TEST_IMAGE_PATH, "rb") as image_file:
            response = tensorzero_client.images.create_variation(
                model="dall-e-2",
                image=image_file,
                n=1,
                size="512x512"
            )
        
        assert len(response.data) == 1
        image_data = response.data[0]
        assert hasattr(image_data, 'url') or hasattr(image_data, 'b64_json')
        if hasattr(image_data, 'url') and image_data.url:
            assert image_data.url.startswith('https://example.com/dummy-variation-')

    def test_multiple_variations(self):
        """Test generating multiple variations (dummy provider)"""
        setup_module()
        
        if not TEST_IMAGE_PATH.exists():
            pytest.skip("Test image file not found")
        
        with open(TEST_IMAGE_PATH, "rb") as image_file:
            response = tensorzero_client.images.create_variation(
                model="dall-e-2",
                image=image_file,
                n=4,
                size="512x512"
            )
        
        assert len(response.data) == 4
        for image_data in response.data:
            assert hasattr(image_data, 'url') or hasattr(image_data, 'b64_json')
            if hasattr(image_data, 'url') and image_data.url:
                assert image_data.url.startswith('https://example.com/dummy-variation-')


class TestImageAPIStructure:
    """Test that the API structure matches OpenAI's interface"""

    def test_images_response_structure(self):
        """Test that response structure matches OpenAI format"""
        response = tensorzero_client.images.generate(
            model="dall-e-2",
            prompt="Test image",
            n=1,
            size="256x256"
        )
        
        # Check top-level structure
        assert hasattr(response, 'data')
        assert isinstance(response.data, list)
        assert len(response.data) == 1
        
        # Check individual image data structure
        image_data = response.data[0]
        # Should have either url or b64_json (dummy provider returns b64_json)
        assert hasattr(image_data, 'b64_json') or hasattr(image_data, 'url')

    def test_parameter_validation(self):
        """Test parameter validation"""
        # Test that the API accepts valid parameters without errors
        try:
            response = tensorzero_client.images.generate(
                model="dall-e-2",
                prompt="Test",
                n=1,
                size="256x256",
                response_format="b64_json"
            )
            assert len(response.data) == 1
            # When requesting b64_json format, should get base64 data
            assert response.data[0].b64_json is not None
        except Exception as e:
            pytest.fail(f"Valid parameters should not raise exception: {e}")


if __name__ == "__main__":
    # Run setup when called directly
    setup_module()
    print("CI image tests ready to run!")
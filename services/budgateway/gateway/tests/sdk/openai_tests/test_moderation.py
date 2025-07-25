import os
import pytest
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Configuration
TENSORZERO_BASE_URL = os.getenv("TENSORZERO_BASE_URL", "http://localhost:3000")
TENSORZERO_API_KEY = os.getenv("TENSORZERO_API_KEY", "test-api-key")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Clients
tensorzero_client = OpenAI(
    base_url=f"{TENSORZERO_BASE_URL}/v1",
    api_key=TENSORZERO_API_KEY
)

openai_client = OpenAI(
    api_key=OPENAI_API_KEY
)


class TestModeration:
    """Test moderation endpoint compatibility"""

    def test_basic_moderation(self):
        """Test basic content moderation"""
        text = "I love programming and building cool applications!"
        
        # TensorZero request
        tz_response = tensorzero_client.moderations.create(
            model="omni-moderation-latest",
            input=text
        )
        
        # Verify response structure
        assert tz_response.id
        assert tz_response.model == "omni-moderation-latest"
        assert len(tz_response.results) == 1
        
        result = tz_response.results[0]
        assert isinstance(result.flagged, bool)
        assert hasattr(result, 'categories')
        assert hasattr(result, 'category_scores')
        
        # Check category structure
        categories = result.categories
        assert hasattr(categories, 'sexual')
        assert hasattr(categories, 'hate')
        assert hasattr(categories, 'harassment')
        assert hasattr(categories, 'self_harm')
        assert hasattr(categories, 'violence')
        
        # Check scores structure
        scores = result.category_scores
        assert isinstance(scores.sexual, float)
        assert isinstance(scores.hate, float)
        assert isinstance(scores.harassment, float)
        assert isinstance(scores.self_harm, float)
        assert isinstance(scores.violence, float)
        
        # Safe content should not be flagged
        assert result.flagged is False

    def test_batch_moderation(self):
        """Test batch content moderation"""
        texts = [
            "This is a normal message",
            "Another harmless text",
            "Programming is fun"
        ]
        
        response = tensorzero_client.moderations.create(
            model="omni-moderation-latest",
            input=texts
        )
        
        assert len(response.results) == 3
        for i, result in enumerate(response.results):
            assert isinstance(result.flagged, bool)
            assert hasattr(result.categories, 'sexual')
            assert hasattr(result.category_scores, 'sexual')

    def test_empty_input_handling(self):
        """Test handling of empty input"""
        # Empty string
        response = tensorzero_client.moderations.create(
            model="omni-moderation-latest",
            input=""
        )
        assert len(response.results) == 1
        assert response.results[0].flagged is False
        
        # Empty list should raise error
        with pytest.raises(Exception):
            tensorzero_client.moderations.create(
                model="omni-moderation-latest",
                input=[]
            )

    def test_unicode_and_special_chars(self):
        """Test moderation with unicode and special characters"""
        texts = [
            "Hello world! 🌍",
            "Testing with @#$%^&*() special chars",
            "Unicode test: 你好世界",
            "Multi-line\ntext\ntest"
        ]
        
        response = tensorzero_client.moderations.create(
            model="omni-moderation-latest",
            input=texts
        )
        
        assert len(response.results) == len(texts)
        for result in response.results:
            assert isinstance(result.flagged, bool)
            assert all(0 <= score <= 1 for score in [
                result.category_scores.sexual,
                result.category_scores.hate,
                result.category_scores.harassment,
                result.category_scores.self_harm,
                result.category_scores.violence
            ])

    def test_category_scores_range(self):
        """Test that category scores are in valid range"""
        text = "This is a test of the moderation system"
        
        response = tensorzero_client.moderations.create(
            model="omni-moderation-latest",
            input=text
        )
        
        result = response.results[0]
        scores = result.category_scores
        
        # All scores should be between 0 and 1
        assert 0 <= scores.sexual <= 1
        assert 0 <= scores.hate <= 1
        assert 0 <= scores.harassment <= 1
        assert 0 <= scores.self_harm <= 1
        assert 0 <= scores.violence <= 1
        assert 0 <= scores.sexual_minors <= 1
        assert 0 <= scores.hate_threatening <= 1
        assert 0 <= scores.harassment_threatening <= 1
        assert 0 <= scores.self_harm_intent <= 1
        assert 0 <= scores.self_harm_instructions <= 1
        assert 0 <= scores.violence_graphic <= 1

    def test_large_batch_moderation(self):
        """Test moderation with large batch"""
        texts = [f"This is test message number {i}" for i in range(50)]
        
        response = tensorzero_client.moderations.create(
            model="omni-moderation-latest",
            input=texts
        )
        
        assert len(response.results) == 50
        for i, result in enumerate(response.results):
            assert isinstance(result.flagged, bool)

    def test_long_text_moderation(self):
        """Test moderation with long text"""
        # Create a long text (but within reasonable limits)
        long_text = " ".join(["This is a long text for testing." for _ in range(100)])
        
        response = tensorzero_client.moderations.create(
            model="omni-moderation-latest",
            input=long_text
        )
        
        assert len(response.results) == 1
        assert isinstance(response.results[0].flagged, bool)

    @pytest.mark.asyncio
    async def test_async_moderation(self):
        """Test async moderation"""
        from openai import AsyncOpenAI
        
        async_client = AsyncOpenAI(
            base_url=f"{TENSORZERO_BASE_URL}/v1",
            api_key=TENSORZERO_API_KEY
        )
        
        text = "Async moderation test"
        
        response = await async_client.moderations.create(
            model="omni-moderation-latest",
            input=text
        )
        
        assert len(response.results) == 1
        assert isinstance(response.results[0].flagged, bool)

    def test_compare_with_openai(self):
        """Compare TensorZero moderation with direct OpenAI moderation"""
        if not OPENAI_API_KEY:
            pytest.skip("OpenAI API key not configured")
        
        text = "This is a test comparison text for moderation"
        
        # Get moderation from TensorZero
        tz_response = tensorzero_client.moderations.create(
            model="omni-moderation-latest",
            input=text
        )
        
        # Get moderation from OpenAI directly
        oai_response = openai_client.moderations.create(
            model="omni-moderation-latest",
            input=text
        )
        
        # Response structure should be identical
        assert tz_response.model == oai_response.model
        assert len(tz_response.results) == len(oai_response.results)
        
        # Results should be very similar (allowing for minor differences)
        tz_result = tz_response.results[0]
        oai_result = oai_response.results[0]
        
        assert tz_result.flagged == oai_result.flagged
        
        # Category flags should match exactly
        assert tz_result.categories.sexual == oai_result.categories.sexual
        assert tz_result.categories.hate == oai_result.categories.hate
        assert tz_result.categories.harassment == oai_result.categories.harassment
        assert tz_result.categories.self_harm == oai_result.categories.self_harm
        assert tz_result.categories.violence == oai_result.categories.violence
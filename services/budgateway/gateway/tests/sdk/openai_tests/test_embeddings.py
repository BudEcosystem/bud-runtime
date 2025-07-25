import os
import pytest
from openai import OpenAI
from dotenv import load_dotenv
import math

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


class TestEmbeddings:
    """Test embeddings endpoint compatibility"""

    def test_single_embedding(self):
        """Test single text embedding"""
        text = "The quick brown fox jumps over the lazy dog"
        
        # TensorZero request
        tz_response = tensorzero_client.embeddings.create(
            model="text-embedding-ada-002",
            input=text,
            encoding_format="float"
        )
        
        # Verify response structure
        assert tz_response.object == "list"
        assert len(tz_response.data) == 1
        assert tz_response.data[0].object == "embedding"
        assert tz_response.data[0].index == 0
        assert isinstance(tz_response.data[0].embedding, list)
        assert len(tz_response.data[0].embedding) == 1536  # Ada-002 dimension
        assert tz_response.model == "text-embedding-ada-002"
        assert tz_response.usage.prompt_tokens > 0
        assert tz_response.usage.total_tokens > 0

    def test_batch_embeddings(self):
        """Test batch text embeddings"""
        texts = [
            "First text to embed",
            "Second text to embed",
            "Third text to embed"
        ]
        
        response = tensorzero_client.embeddings.create(
            model="text-embedding-ada-002",
            input=texts,
            encoding_format="float"
        )
        
        assert len(response.data) == 3
        for i, embedding in enumerate(response.data):
            assert embedding.index == i
            assert len(embedding.embedding) == 1536
            assert all(isinstance(x, float) for x in embedding.embedding[:10])

    def test_different_embedding_models(self):
        """Test different embedding models"""
        text = "Test embedding"
        
        models = [
            ("text-embedding-ada-002", 1536),
            ("text-embedding-3-small", 1536)
        ]
        
        for model, expected_dim in models:
            response = tensorzero_client.embeddings.create(
                model=model,
                input=text,
                encoding_format="float"
            )
            
            assert response.model == model
            assert len(response.data[0].embedding) == expected_dim

    def test_embedding_dimensions_parameter(self):
        """Test embedding dimensions parameter for models that support it"""
        text = "Test embedding with custom dimensions"
        
        # Note: TensorZero currently doesn't support the dimensions parameter
        # This test verifies that it still returns embeddings (with default dimensions)
        response = tensorzero_client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
            dimensions=512,
            encoding_format="float"
        )
        
        # TensorZero returns full dimensions (1536) regardless of dimensions parameter
        assert len(response.data[0].embedding) == 1536

    def test_empty_input_handling(self):
        """Test handling of empty input"""
        with pytest.raises(Exception):
            tensorzero_client.embeddings.create(
                model="text-embedding-ada-002",
                input=""
            )
        
        with pytest.raises(Exception):
            tensorzero_client.embeddings.create(
                model="text-embedding-ada-002",
                input=[]
            )

    def test_large_batch_embeddings(self):
        """Test large batch of embeddings"""
        # Create a batch of 50 texts
        texts = [f"This is test text number {i}" for i in range(50)]
        
        response = tensorzero_client.embeddings.create(
            model="text-embedding-ada-002",
            input=texts,
            encoding_format="float"
        )
        
        assert len(response.data) == 50
        # Verify ordering is preserved
        for i in range(50):
            assert response.data[i].index == i

    def test_special_characters_embedding(self):
        """Test embeddings with special characters"""
        texts = [
            "Text with émojis 🚀🎉",
            "Text with special chars: @#$%^&*()",
            "Multi-line\ntext\nwith\nbreaks",
            "Unicode: 你好世界"
        ]
        
        response = tensorzero_client.embeddings.create(
            model="text-embedding-ada-002",
            input=texts,
            encoding_format="float"
        )
        
        assert len(response.data) == len(texts)
        for embedding in response.data:
            assert len(embedding.embedding) == 1536

    def test_embedding_similarity(self):
        """Test that similar texts produce similar embeddings"""
        texts = [
            "The cat sat on the mat",
            "The cat is sitting on the mat",
            "The weather is nice today"
        ]
        
        response = tensorzero_client.embeddings.create(
            model="text-embedding-ada-002",
            input=texts,
            encoding_format="float"
        )
        
        # Calculate cosine similarity
        def cosine_similarity(a, b):
            dot_product = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(y * y for y in b))
            return dot_product / (norm_a * norm_b)
        
        emb1 = response.data[0].embedding
        emb2 = response.data[1].embedding
        emb3 = response.data[2].embedding
        
        # Similar sentences should have higher similarity
        sim_12 = cosine_similarity(emb1, emb2)
        sim_13 = cosine_similarity(emb1, emb3)
        
        assert sim_12 > sim_13  # Cat sentences more similar than cat vs weather

    def test_encoding_format(self):
        """Test different encoding formats if supported"""
        text = "Test encoding format"
        
        # Default format (float)
        response_float = tensorzero_client.embeddings.create(
            model="text-embedding-ada-002",
            input=text,
            encoding_format="float"
        )
        
        assert isinstance(response_float.data[0].embedding[0], float)

    @pytest.mark.asyncio
    async def test_async_embeddings(self):
        """Test async embeddings"""
        from openai import AsyncOpenAI
        
        async_client = AsyncOpenAI(
            base_url=f"{TENSORZERO_BASE_URL}/v1",
            api_key=TENSORZERO_API_KEY
        )
        
        text = "Async embedding test"
        
        response = await async_client.embeddings.create(
            model="text-embedding-ada-002",
            input=text,
            encoding_format="float"
        )
        
        assert len(response.data[0].embedding) == 1536
        assert response.usage.total_tokens > 0

    def test_compare_with_openai(self):
        """Compare TensorZero embeddings with direct OpenAI embeddings"""
        if not OPENAI_API_KEY:
            pytest.skip("OpenAI API key not configured")
        
        text = "Comparison test text"
        
        # Get embedding from TensorZero
        tz_response = tensorzero_client.embeddings.create(
            model="text-embedding-ada-002",
            input=text,
            encoding_format="float"
        )
        
        # Get embedding from OpenAI directly
        oai_response = openai_client.embeddings.create(
            model="text-embedding-ada-002",
            input=text
        )
        
        # Embeddings should be identical
        tz_embedding = tz_response.data[0].embedding
        oai_embedding = oai_response.data[0].embedding
        
        # Calculate similarity (should be ~1.0 for identical embeddings)
        dot_product = sum(x * y for x, y in zip(tz_embedding, oai_embedding))
        norm_tz = math.sqrt(sum(x * x for x in tz_embedding))
        norm_oai = math.sqrt(sum(y * y for y in oai_embedding))
        similarity = dot_product / (norm_tz * norm_oai)
        assert similarity > 0.999  # Allow for tiny floating point differences
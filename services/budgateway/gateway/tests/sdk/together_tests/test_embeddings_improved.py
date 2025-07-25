"""
Improved Together embeddings tests using universal test infrastructure.

This demonstrates how embedding tests can be simplified by using the shared
universal test infrastructure instead of duplicating validation logic.
"""

import os
import pytest
from openai import OpenAI

# Use same pattern as existing tests
client = OpenAI(
    base_url=os.getenv("TENSORZERO_BASE_URL", "http://localhost:3001") + "/v1",
    api_key=os.getenv("TENSORZERO_API_KEY", "test-api-key")
)


class TestTogetherEmbeddingsImproved:
    """Improved Together embeddings tests using simplified approach."""
    
    def setup_class(cls):
        """Setup test class."""
        cls.embedding_models = ["together-bge-base", "together-m2-bert"]
    
    def test_together_single_embedding(self):
        """Test single text embedding with Together models."""
        for model in self.embedding_models:
            response = client.embeddings.create(
                model=model,
                input="Test embedding for Together AI models"
            )
            
            # Basic validation
            assert response.model == model
            assert len(response.data) == 1
            assert response.data[0].index == 0
            assert len(response.data[0].embedding) > 0
            assert all(isinstance(x, float) for x in response.data[0].embedding)
            
            # BGE base typically has good dimensions
            if "bge-base" in model:
                embedding_dims = len(response.data[0].embedding)
                assert embedding_dims > 100, f"BGE model {model} should have reasonable dimensions"
    
    def test_together_batch_embeddings(self):
        """Test batch embeddings with Together models."""
        texts = [
            "First document about machine learning",
            "Second document about natural language processing",
            "Third document about computer vision"
        ]
        
        for model in self.embedding_models:
            response = client.embeddings.create(
                model=model,
                input=texts
            )
            
            # Should have multiple embeddings
            assert len(response.data) == len(texts)
            assert response.model == model
            
            # All embeddings should have same dimensions
            first_dims = len(response.data[0].embedding)
            for i, embedding_data in enumerate(response.data):
                assert embedding_data.index == i
                assert len(embedding_data.embedding) == first_dims, f"Inconsistent dimensions in batch for {model}"
    
    def test_together_embedding_format(self):
        """Test Together embeddings format compatibility."""
        model = self.embedding_models[0]
        test_text = "Format compatibility test"
        
        response = client.embeddings.create(
            model=model,
            input=test_text
        )
        
        # Should match OpenAI embedding response format exactly
        assert response.object == "list"
        assert len(response.data) == 1
        
        embedding_data = response.data[0]
        assert embedding_data.object == "embedding"
        assert embedding_data.index == 0
        assert len(embedding_data.embedding) > 0
        assert all(isinstance(x, float) for x in embedding_data.embedding)
        
        # Should have usage information
        assert response.usage is not None
        assert response.usage.total_tokens > 0
        
        # Model name should be preserved
        assert response.model == model


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
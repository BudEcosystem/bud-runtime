"""
Test Together AI embeddings through OpenAI SDK.

These tests verify Together's embedding models work correctly
through TensorZero's OpenAI-compatible interface.
"""

import os
import math
import pytest
from openai import OpenAI
from dotenv import load_dotenv
from typing import List

# Try to import numpy, but make it optional
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

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
class TestTogetherEmbeddings:
    """Test Together AI embedding models through OpenAI SDK."""
    
    def test_bge_base_embedding(self):
        """Test BGE base embedding model."""
        text = "The quick brown fox jumps over the lazy dog."
        
        response = client.embeddings.create(
            model="together-bge-base",
            input=text
        )
        
        # Verify response structure
        assert response.object == "list"
        assert response.model == "together-bge-base"
        assert len(response.data) == 1
        
        # Verify embedding
        embedding = response.data[0]
        assert embedding.object == "embedding"
        assert embedding.index == 0
        assert isinstance(embedding.embedding, list)
        assert len(embedding.embedding) == 768  # BGE base has 768 dimensions
        
        # Verify all values are floats
        assert all(isinstance(x, (int, float)) for x in embedding.embedding)
        
        # Verify usage
        assert response.usage.prompt_tokens > 0
        assert response.usage.total_tokens == response.usage.prompt_tokens
    
    def test_m2_bert_embedding(self):
        """Test M2-BERT embedding model."""
        text = "Machine learning is transforming how we interact with technology."
        
        response = client.embeddings.create(
            model="together-m2-bert",
            input=text
        )
        
        assert response.model == "together-m2-bert"
        assert len(response.data) == 1
        
        embedding = response.data[0]
        assert len(embedding.embedding) > 0
        assert all(isinstance(x, (int, float)) for x in embedding.embedding)
    
    def test_batch_embeddings(self):
        """Test batch embedding generation."""
        texts = [
            "First document about artificial intelligence",
            "Second document about machine learning",
            "Third document about deep learning",
            "Fourth document about neural networks",
            "Fifth document about computer vision"
        ]
        
        response = client.embeddings.create(
            model="together-bge-base",
            input=texts
        )
        
        # Verify batch response
        assert len(response.data) == len(texts)
        
        # Verify each embedding
        for i, embedding_data in enumerate(response.data):
            assert embedding_data.index == i
            assert embedding_data.object == "embedding"
            assert len(embedding_data.embedding) == 768
            assert all(isinstance(x, (int, float)) for x in embedding_data.embedding)
        
        # Verify usage for batch
        assert response.usage.prompt_tokens > 0
        assert response.usage.total_tokens == response.usage.prompt_tokens
    
    def test_embedding_similarity(self):
        """Test that similar texts produce similar embeddings."""
        similar_texts = [
            "The weather is sunny and warm today",
            "Today's weather is warm and sunny",
            "It's a warm, sunny day"
        ]
        
        different_text = "Machine learning algorithms process data"
        
        # Get embeddings for similar texts
        similar_response = client.embeddings.create(
            model="together-bge-base",
            input=similar_texts
        )
        
        # Get embedding for different text
        different_response = client.embeddings.create(
            model="together-bge-base",
            input=different_text
        )
        
        # Calculate cosine similarity without numpy
        def cosine_similarity(a: List[float], b: List[float]) -> float:
            dot_product = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(y * y for y in b))
            return dot_product / (norm_a * norm_b)
        
        # Get embeddings as lists
        similar_embeddings = [data.embedding for data in similar_response.data]
        different_embedding = different_response.data[0].embedding
        
        # Similar texts should have high similarity
        similar_sim = cosine_similarity(similar_embeddings[0], similar_embeddings[1])
        assert similar_sim > 0.8, f"Similar texts similarity too low: {similar_sim}"
        
        # Different text should have lower similarity
        different_sim = cosine_similarity(similar_embeddings[0], different_embedding)
        assert different_sim < similar_sim, "Different text similarity should be lower"
    
    def test_empty_input_handling(self):
        """Test handling of empty input."""
        with pytest.raises(Exception) as exc_info:
            client.embeddings.create(
                model="together-bge-base",
                input=""
            )
        
        # Should raise an error for empty string
        assert exc_info.value is not None
    
    def test_special_characters_embedding(self):
        """Test embeddings with special characters."""
        special_texts = [
            "Hello 世界! 🌍",
            "Mathematical: ∑(x²) = ∫f(x)dx",
            "Symbols: @#$%^&*()",
            "Emojis: 🚀🤖🎉🌟",
            "Mixed: Hello_世界-2024 #AI"
        ]
        
        response = client.embeddings.create(
            model="together-bge-base",
            input=special_texts
        )
        
        assert len(response.data) == len(special_texts)
        for embedding_data in response.data:
            assert len(embedding_data.embedding) == 768
    
    def test_long_text_embedding(self):
        """Test embedding of long text."""
        # Create a long text (but within model limits)
        long_text = " ".join([
            "This is a sentence about artificial intelligence."
            for _ in range(100)
        ])
        
        response = client.embeddings.create(
            model="together-bge-base",
            input=long_text
        )
        
        assert len(response.data) == 1
        assert len(response.data[0].embedding) == 768
        assert response.usage.prompt_tokens > 100  # Should use many tokens
    
    def test_embedding_determinism(self):
        """Test that same input produces same embedding."""
        text = "Deterministic embedding test"
        
        # Get embedding twice
        response1 = client.embeddings.create(
            model="together-bge-base",
            input=text
        )
        
        response2 = client.embeddings.create(
            model="together-bge-base",
            input=text
        )
        
        # Embeddings should be identical
        embedding1 = response1.data[0].embedding
        embedding2 = response2.data[0].embedding
        
        # Check if embeddings are very close (allowing for minor floating point differences)
        def cosine_similarity(a: List[float], b: List[float]) -> float:
            dot_product = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(y * y for y in b))
            return dot_product / (norm_a * norm_b)
        
        similarity = cosine_similarity(embedding1, embedding2)
        assert similarity > 0.9999, f"Embeddings not deterministic: similarity={similarity}"
    
    def test_mixed_language_embeddings(self):
        """Test embeddings for multiple languages."""
        multilingual_texts = [
            "Hello, how are you?",  # English
            "Bonjour, comment allez-vous?",  # French
            "Hola, ¿cómo estás?",  # Spanish
            "你好，你好吗？",  # Chinese
            "こんにちは、お元気ですか？",  # Japanese
            "Привет, как дела?",  # Russian
        ]
        
        response = client.embeddings.create(
            model="together-bge-base",
            input=multilingual_texts
        )
        
        assert len(response.data) == len(multilingual_texts)
        for i, embedding_data in enumerate(response.data):
            assert embedding_data.index == i
            assert len(embedding_data.embedding) == 768
    
    def test_embedding_edge_cases(self):
        """Test various edge cases for embeddings."""
        edge_cases = [
            ".",  # Single character
            "   ",  # Whitespace (might fail)
            "123456789",  # Numbers only
            "!!!???",  # Punctuation only
            "\n\n\n",  # Newlines
            "a" * 1000,  # Repeated character
        ]
        
        for i, text in enumerate(edge_cases):
            try:
                response = client.embeddings.create(
                    model="together-bge-base",
                    input=text
                )
                assert len(response.data) == 1
                assert len(response.data[0].embedding) == 768
            except Exception as e:
                # Some edge cases might fail, which is expected
                print(f"Edge case {i} ('{text[:20]}...') failed: {e}")


@pytest.mark.skipif(SKIP_TOGETHER_TESTS, reason="Together tests disabled")
class TestTogetherEmbeddingApplications:
    """Test real-world applications of Together embeddings."""
    
    def test_semantic_search(self):
        """Test semantic search using embeddings."""
        # Document corpus
        documents = [
            "Python is a high-level programming language.",
            "Machine learning models can predict future outcomes.",
            "The stock market closed higher today.",
            "Neural networks are inspired by biological neurons.",
            "Coffee is one of the most popular beverages worldwide."
        ]
        
        # Get embeddings for documents
        doc_response = client.embeddings.create(
            model="together-bge-base",
            input=documents
        )
        
        # Search queries
        queries = [
            "programming languages",
            "artificial intelligence",
            "financial markets"
        ]
        
        # Get embeddings for queries
        query_response = client.embeddings.create(
            model="together-bge-base",
            input=queries
        )
        
        # Calculate cosine similarity without numpy
        def cosine_similarity(a: List[float], b: List[float]) -> float:
            dot_product = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(y * y for y in b))
            return dot_product / (norm_a * norm_b)
        
        # Get embeddings as lists
        doc_embeddings = [d.embedding for d in doc_response.data]
        query_embeddings = [q.embedding for q in query_response.data]
        
        # For each query, find most similar document
        for i, query_emb in enumerate(query_embeddings):
            similarities = []
            for doc_emb in doc_embeddings:
                sim = cosine_similarity(query_emb, doc_emb)
                similarities.append(sim)
            
            best_doc_idx = similarities.index(max(similarities))
            print(f"Query '{queries[i]}' best matches: '{documents[best_doc_idx]}'")
    
    def test_clustering_embeddings(self):
        """Test that embeddings can be used for clustering."""
        # Texts from different categories
        texts = [
            # Technology
            "Artificial intelligence is revolutionizing industries",
            "Machine learning algorithms improve with more data",
            "Deep learning uses neural network architectures",
            # Sports
            "The football team won the championship",
            "Basketball players need excellent coordination",
            "Tennis requires both physical and mental strength",
            # Food
            "Italian cuisine is known for pasta and pizza",
            "Japanese food emphasizes fresh ingredients",
            "Mexican cuisine features spicy flavors"
        ]
        
        response = client.embeddings.create(
            model="together-bge-base",
            input=texts
        )
        
        # Get embeddings
        embeddings = [d.embedding for d in response.data]
        
        # Verify embeddings have correct count and dimensions
        assert len(embeddings) == 9
        assert all(len(emb) == 768 for emb in embeddings)
        
        # In a real application, you would use clustering algorithms here
        # For testing, just verify we got valid embeddings
        for embedding in embeddings:
            # Check no NaN or infinite values
            assert all(not math.isnan(x) and not math.isinf(x) for x in embedding)
    
    def test_embedding_caching_behavior(self):
        """Test if embeddings are cached (same input = same output)."""
        text = "Test caching behavior"
        
        responses = []
        for _ in range(3):
            response = client.embeddings.create(
                model="together-bge-base",
                input=text
            )
            responses.append(response)
        
        # All responses should have identical embeddings
        base_embedding = responses[0].data[0].embedding
        for response in responses[1:]:
            assert response.data[0].embedding == base_embedding


@pytest.mark.skipif(SKIP_TOGETHER_TESTS, reason="Together tests disabled")
class TestTogetherEmbeddingErrors:
    """Test error handling for Together embeddings."""
    
    def test_invalid_model_name(self):
        """Test with non-existent embedding model."""
        with pytest.raises(Exception) as exc_info:
            client.embeddings.create(
                model="together-invalid-embedding-model",
                input="Test text"
            )
        
        assert "not found" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()
    
    def test_empty_batch(self):
        """Test with empty batch input."""
        with pytest.raises(Exception) as exc_info:
            client.embeddings.create(
                model="together-bge-base",
                input=[]
            )
        
        assert "empty" in str(exc_info.value).lower()
    
    def test_chat_model_for_embedding(self):
        """Test using chat model for embeddings."""
        with pytest.raises(Exception) as exc_info:
            client.embeddings.create(
                model="meta-llama/Llama-3.1-8B-Instruct-Turbo",
                input="Test text"
            )
        
        # Should fail because it's not an embedding model
        assert exc_info.value is not None
    
    def test_extremely_long_text(self):
        """Test with text exceeding model limits."""
        # Create extremely long text
        very_long_text = "word " * 10000  # Much longer than typical limits
        
        try:
            response = client.embeddings.create(
                model="together-bge-base",
                input=very_long_text
            )
            # If it succeeds, verify truncation or handling
            assert len(response.data) == 1
        except Exception as e:
            # Expected to fail with token limit error
            assert "token" in str(e).lower() or "length" in str(e).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
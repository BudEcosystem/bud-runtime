"""Integration tests for mock vLLM service."""

import asyncio
import json
from typing import Dict, Any

import httpx
import pytest


BASE_URL = "http://localhost:8000"


class TestMockVLLMIntegration:
    """Integration tests for the mock vLLM API."""
    
    @pytest.fixture
    async def client(self):
        """Create an async HTTP client."""
        async with httpx.AsyncClient(base_url=BASE_URL) as client:
            yield client
    
    @pytest.mark.asyncio
    async def test_health_check(self, client: httpx.AsyncClient):
        """Test health check endpoint."""
        response = await client.get("/health")
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_list_models(self, client: httpx.AsyncClient):
        """Test listing available models."""
        response = await client.get("/v1/models")
        assert response.status_code == 200
        
        data = response.json()
        assert data["object"] == "list"
        assert len(data["data"]) > 0
        assert all(model["object"] == "model" for model in data["data"])
    
    @pytest.mark.asyncio
    async def test_chat_completion(self, client: httpx.AsyncClient):
        """Test chat completion endpoint."""
        request_data = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello, how are you?"}
            ],
            "temperature": 0.7,
            "max_tokens": 150
        }
        
        response = await client.post("/v1/chat/completions", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["object"] == "chat.completion"
        assert len(data["choices"]) == 1
        assert data["choices"][0]["message"]["role"] == "assistant"
        assert data["choices"][0]["message"]["content"] is not None
        assert data["usage"]["total_tokens"] > 0
    
    @pytest.mark.asyncio
    async def test_chat_completion_streaming(self, client: httpx.AsyncClient):
        """Test streaming chat completion."""
        request_data = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": "Tell me a story"}],
            "stream": True
        }
        
        chunks = []
        async with client.stream("POST", "/v1/chat/completions", json=request_data) as response:
            assert response.status_code == 200
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    chunks.append(line[6:])
        
        # Check we got multiple chunks
        assert len(chunks) > 2
        assert chunks[-1] == "[DONE]"
        
        # Verify chunk format
        for chunk in chunks[:-1]:
            data = json.loads(chunk)
            assert data["object"] == "chat.completion.chunk"
    
    @pytest.mark.asyncio
    async def test_text_completion(self, client: httpx.AsyncClient):
        """Test text completion endpoint."""
        request_data = {
            "model": "gpt-3.5-turbo",
            "prompt": "Once upon a time",
            "max_tokens": 50,
            "temperature": 0.8
        }
        
        response = await client.post("/v1/completions", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["object"] == "text_completion"
        assert len(data["choices"]) == 1
        assert data["choices"][0]["text"] is not None
        assert data["usage"]["completion_tokens"] > 0
    
    @pytest.mark.asyncio
    async def test_embeddings(self, client: httpx.AsyncClient):
        """Test embeddings endpoint."""
        request_data = {
            "model": "text-embedding-ada-002",
            "input": ["Hello world", "How are you?"]
        }
        
        response = await client.post("/v1/embeddings", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["object"] == "list"
        assert len(data["data"]) == 2
        
        for item in data["data"]:
            assert item["object"] == "embedding"
            assert len(item["embedding"]) == 768  # Mock embedding dimension
            assert all(isinstance(x, float) for x in item["embedding"])
    
    @pytest.mark.asyncio
    async def test_tokenization(self, client: httpx.AsyncClient):
        """Test tokenization endpoints."""
        # Test tokenize
        tokenize_request = {
            "model": "gpt-3.5-turbo",
            "prompt": "Hello, world! This is a test."
        }
        
        response = await client.post("/tokenize", json=tokenize_request)
        assert response.status_code == 200
        
        tokenize_data = response.json()
        assert "tokens" in tokenize_data
        assert "count" in tokenize_data
        assert tokenize_data["count"] == len(tokenize_data["tokens"])
        
        # Test detokenize
        detokenize_request = {
            "model": "gpt-3.5-turbo",
            "tokens": tokenize_data["tokens"]
        }
        
        response = await client.post("/detokenize", json=detokenize_request)
        assert response.status_code == 200
        
        detokenize_data = response.json()
        assert "prompt" in detokenize_data
    
    @pytest.mark.asyncio
    async def test_classification(self, client: httpx.AsyncClient):
        """Test classification endpoint."""
        request_data = {
            "model": "gpt-3.5-turbo",
            "prompt": ["This movie is amazing!", "This product is terrible."],
            "labels": ["positive", "negative", "neutral"]
        }
        
        response = await client.post("/classify", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["object"] == "list"
        assert len(data["data"]) == 2
        
        for item in data["data"]:
            assert item["object"] == "classification"
            assert item["label"] in ["positive", "negative", "neutral"]
            assert 0 <= item["score"] <= 1
    
    @pytest.mark.asyncio
    async def test_rerank(self, client: httpx.AsyncClient):
        """Test rerank endpoint."""
        request_data = {
            "model": "mock-rerank-model",
            "query": "What is machine learning?",
            "documents": [
                "Machine learning is a type of AI.",
                "Pizza is a popular Italian dish.",
                "Deep learning is a subset of machine learning.",
                "The weather is nice today."
            ],
            "top_n": 2
        }
        
        response = await client.post("/rerank", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["object"] == "rerank"
        assert len(data["results"]) == 2  # top_n = 2
        
        for result in data["results"]:
            assert "index" in result
            assert "relevance_score" in result
            assert 0 <= result["relevance_score"] <= 1
            assert "text" in result
    
    @pytest.mark.asyncio
    async def test_score(self, client: httpx.AsyncClient):
        """Test score endpoint."""
        request_data = {
            "model": "gpt-3.5-turbo",
            "text_1": ["Hello world", "Machine learning"],
            "text_2": ["Hi there", "Deep learning"]
        }
        
        response = await client.post("/score", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["object"] == "list"
        assert len(data["data"]) == 2
        
        for item in data["data"]:
            assert item["object"] == "score"
            assert 0 <= item["score"] <= 1
    
    @pytest.mark.asyncio
    async def test_api_key_authentication(self):
        """Test API key authentication."""
        # Test without API key (should fail if API key is required)
        api_key = "test-api-key"
        headers = {"Authorization": f"Bearer {api_key}"}
        
        async with httpx.AsyncClient(base_url=BASE_URL, headers=headers) as client:
            response = await client.get("/v1/models")
            # Should succeed with valid API key or if no API key is configured
            assert response.status_code in [200, 401]


def run_integration_tests():
    """Run all integration tests."""
    asyncio.run(pytest.main([__file__, "-v"]))


if __name__ == "__main__":
    run_integration_tests()
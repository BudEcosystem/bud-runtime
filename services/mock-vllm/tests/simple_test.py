#!/usr/bin/env python3
"""Simple test script for mock vLLM service."""

import json
import requests
import sys
from typing import Dict, Any


BASE_URL = "http://localhost:8000"


def test_endpoint(method: str, endpoint: str, data: Dict[str, Any] = None) -> bool:
    """Test a single endpoint."""
    url = f"{BASE_URL}{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url, json=data)
        else:
            print(f"Unsupported method: {method}")
            return False
        
        print(f"\n{'='*60}")
        print(f"Testing: {method} {endpoint}")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                print(f"Response: {json.dumps(result, indent=2)[:500]}...")
                return True
            except:
                print(f"Response: {response.text[:200]}...")
                return True
        else:
            print(f"Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"Exception: {e}")
        return False


def main():
    """Run simple integration tests."""
    print("Testing Mock vLLM Service")
    print("=" * 60)
    
    tests = [
        # Health check
        ("GET", "/health", None),
        
        # Version
        ("GET", "/version", None),
        
        # List models
        ("GET", "/v1/models", None),
        
        # Chat completion
        ("POST", "/v1/chat/completions", {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "user", "content": "Hello, how are you?"}
            ]
        }),
        
        # Text completion
        ("POST", "/v1/completions", {
            "model": "gpt-3.5-turbo",
            "prompt": "Once upon a time"
        }),
        
        # Embeddings
        ("POST", "/v1/embeddings", {
            "model": "text-embedding-ada-002",
            "input": "Hello world"
        }),
        
        # Tokenization
        ("POST", "/tokenize", {
            "model": "gpt-3.5-turbo",
            "prompt": "Hello, world!"
        }),
        
        # Classification
        ("POST", "/classify", {
            "model": "gpt-3.5-turbo",
            "prompt": "This is amazing!",
            "labels": ["positive", "negative", "neutral"]
        }),
        
        # Rerank
        ("POST", "/rerank", {
            "model": "mock-rerank-model",
            "query": "machine learning",
            "documents": ["ML is great", "Pizza is tasty", "AI and ML"]
        }),
    ]
    
    passed = 0
    failed = 0
    
    for method, endpoint, data in tests:
        if test_endpoint(method, endpoint, data):
            passed += 1
        else:
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
"""
Cross-provider comparison tests to demonstrate universal SDK architecture.

This file shows how the same OpenAI SDK code works identically across all providers,
with the only difference being the model name.
"""

import os
import sys
import pytest
from typing import Dict, List, Tuple

# Add parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from common.utils import create_universal_client, validate_chat_response


class TestCrossProviderComparison:
    """Compare providers using identical OpenAI SDK code."""
    
    def __init__(self):
        self.client = create_universal_client()
    
    def setup_method(self):
        """Setup for each test method."""
        self.client = create_universal_client()
    
    def test_identical_code_different_providers(self):
        """Demonstrate that identical code works across all providers."""
        
        # Define provider-model pairs
        provider_models = [
            ("OpenAI", "gpt-3.5-turbo"),
            ("Anthropic", "claude-3-haiku-20240307"),
            ("Together", "meta-llama/Llama-3.2-3B-Instruct-Turbo")
        ]
        
        results = {}
        
        for provider_name, model in provider_models:
            print(f"\n--- Testing {provider_name} with identical code ---")
            
            # IDENTICAL CODE FOR ALL PROVIDERS - only model name changes
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "What is the capital of France?"}
                ],
                max_tokens=50,
                temperature=0.1
            )
            
            # IDENTICAL VALIDATION FOR ALL PROVIDERS
            validate_chat_response(response)
            assert response.model == model
            assert "Paris" in response.choices[0].message.content or "paris" in response.choices[0].message.content.lower()
            
            results[provider_name] = {
                "model": response.model,
                "content": response.choices[0].message.content,
                "usage": response.usage
            }
            
            print(f"✅ {provider_name} ({model}): {response.choices[0].message.content[:50]}...")
        
        # All should have responded successfully
        assert len(results) == len(provider_models)
        
        # All should mention Paris
        for provider, result in results.items():
            assert "paris" in result["content"].lower(), f"{provider} didn't mention Paris"
        
        return results
    
    def test_streaming_comparison(self):
        """Compare streaming across providers with identical code."""
        
        provider_models = [
            ("OpenAI", "gpt-3.5-turbo"),
            ("Anthropic", "claude-3-haiku-20240307"), 
            ("Together", "meta-llama/Llama-3.1-8B-Instruct-Turbo")
        ]
        
        streaming_results = {}
        
        for provider_name, model in provider_models:
            print(f"\n--- Testing {provider_name} streaming ---")
            
            # IDENTICAL STREAMING CODE FOR ALL PROVIDERS
            stream = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Count from 1 to 5"}],
                max_tokens=50,
                stream=True
            )
            
            chunks = []
            content_pieces = []
            
            # IDENTICAL STREAMING PROCESSING FOR ALL PROVIDERS
            for chunk in stream:
                chunks.append(chunk)
                if chunk.choices[0].delta.content:
                    content_pieces.append(chunk.choices[0].delta.content)
            
            full_content = "".join(content_pieces)
            
            streaming_results[provider_name] = {
                "chunk_count": len(chunks),
                "content_length": len(full_content),
                "content": full_content
            }
            
            print(f"✅ {provider_name}: {len(chunks)} chunks, content: {full_content[:50]}...")
        
        # All should have streamed successfully
        for provider, result in streaming_results.items():
            assert result["chunk_count"] > 0, f"{provider} sent no chunks"
            assert result["content_length"] > 0, f"{provider} sent no content"
        
        return streaming_results
    
    def test_parameter_consistency(self):
        """Test that parameters work consistently across providers."""
        
        models = [
            "gpt-3.5-turbo",
            "claude-3-haiku-20240307",
            "Qwen/Qwen2.5-72B-Instruct-Turbo"
        ]
        
        # Test various parameters with each model
        parameter_tests = [
            # (description, parameters)
            ("Low temperature", {"temperature": 0.1}),
            ("High temperature", {"temperature": 0.9}),  
            ("Low max_tokens", {"max_tokens": 10}),
            ("System prompt", {"messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello!"}
            ]}),
            ("Multi-turn", {"messages": [
                {"role": "user", "content": "My name is Alice"},
                {"role": "assistant", "content": "Hello Alice!"},
                {"role": "user", "content": "What's my name?"}
            ]})
        ]
        
        results = {}
        
        for model in models:
            model_results = {}
            print(f"\n--- Testing parameters with {model} ---")
            
            for test_desc, params in parameter_tests:
                # Prepare default parameters
                default_params = {
                    "model": model,
                    "messages": [{"role": "user", "content": "Test"}],
                    "max_tokens": 30
                }
                
                # Override with test-specific parameters
                test_params = {**default_params, **params}
                
                # IDENTICAL PARAMETER TEST FOR ALL MODELS
                response = self.client.chat.completions.create(**test_params)
                
                validate_chat_response(response)
                model_results[test_desc] = {
                    "success": True,
                    "content_length": len(response.choices[0].message.content)
                }
                
                print(f"  ✅ {test_desc}: OK")
            
            results[model] = model_results
        
        # All models should handle all parameter tests
        for model, model_results in results.items():
            assert len(model_results) == len(parameter_tests), f"{model} failed some parameter tests"
            for test_desc, result in model_results.items():
                assert result["success"], f"{model} failed {test_desc}"
        
        return results
    
    def test_error_handling_consistency(self):
        """Test that error handling is consistent across providers."""
        
        models = ["gpt-3.5-turbo", "claude-3-haiku-20240307", "meta-llama/Llama-3.2-3B-Instruct-Turbo"]
        error_results = {}
        
        for model in models:
            print(f"\n--- Testing error handling with {model} ---")
            model_errors = {}
            
            # Test 1: Empty messages
            try:
                self.client.chat.completions.create(
                    model=model,
                    messages=[],
                    max_tokens=10
                )
                model_errors["empty_messages"] = "No error raised"
            except Exception as e:
                model_errors["empty_messages"] = type(e).__name__
            
            # Test 2: Invalid temperature
            try:
                self.client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "Test"}],
                    temperature=-1.0,
                    max_tokens=10
                )
                model_errors["invalid_temperature"] = "No error raised"
            except Exception as e:
                model_errors["invalid_temperature"] = type(e).__name__
            
            error_results[model] = model_errors
            print(f"  ✅ {model}: Consistent error handling")
        
        # All models should raise errors for invalid inputs
        for model, errors in error_results.items():
            # Should raise error for empty messages
            assert errors["empty_messages"] != "No error raised", f"{model} didn't raise error for empty messages"
            # Should raise error for invalid temperature  
            assert errors["invalid_temperature"] != "No error raised", f"{model} didn't raise error for invalid temperature"
        
        return error_results
    
    def test_universal_sdk_architecture_proof(self):
        """
        Definitive proof that OpenAI SDK is universal across all providers.
        
        This test uses IDENTICAL code with only the model name changing.
        """
        
        # The Universal SDK Test: Same code, different models, all providers
        test_scenarios = [
            {
                "provider": "OpenAI",
                "model": "gpt-3.5-turbo",
                "description": "OpenAI's flagship model"
            },
            {
                "provider": "Anthropic", 
                "model": "claude-3-haiku-20240307",
                "description": "Anthropic's fastest model"
            },
            {
                "provider": "Together",
                "model": "meta-llama/Llama-3.2-3B-Instruct-Turbo", 
                "description": "Meta's Llama model via Together"
            },
            {
                "provider": "Together",
                "model": "Qwen/Qwen2.5-72B-Instruct-Turbo",
                "description": "Qwen model via Together"
            },
            {
                "provider": "Together", 
                "model": "mistralai/Mixtral-8x7B-Instruct-v0.1",
                "description": "Mistral model via Together"
            }
        ]
        
        universal_results = []
        
        print("\n" + "="*80)
        print("UNIVERSAL SDK ARCHITECTURE PROOF")
        print("Same OpenAI SDK code works with ALL providers")
        print("="*80)
        
        for scenario in test_scenarios:
            provider = scenario["provider"]
            model = scenario["model"] 
            description = scenario["description"]
            
            print(f"\nTesting: {provider} - {model}")
            print(f"Description: {description}")
            print("-" * 60)
            
            # THIS EXACT SAME CODE WORKS WITH ALL PROVIDERS
            # Only the model name changes - everything else is identical
            response = self.client.chat.completions.create(
                model=model,  # <-- ONLY THIS CHANGES
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant."},
                    {"role": "user", "content": "What is artificial intelligence?"}
                ],
                max_tokens=100,
                temperature=0.7
            )
            
            # IDENTICAL VALIDATION FOR ALL PROVIDERS  
            validate_chat_response(response)
            assert response.model == model
            assert len(response.choices[0].message.content) > 0
            
            result = {
                "provider": provider,
                "model": model,
                "success": True,
                "content_preview": response.choices[0].message.content[:100] + "...",
                "response_id": response.id,
                "usage": response.usage.__dict__ if response.usage else None
            }
            
            universal_results.append(result)
            
            print(f"✅ SUCCESS: {model}")
            print(f"Response preview: {result['content_preview']}")
        
        print("\n" + "="*80)
        print("UNIVERSAL SDK ARCHITECTURE PROVEN!")
        print(f"✅ {len(universal_results)} different models from {len(set(r['provider'] for r in universal_results))} providers")
        print("✅ Same OpenAI SDK code works perfectly with all of them")
        print("✅ Only model name changes - everything else identical")
        print("="*80)
        
        # Final assertion: All providers worked
        assert len(universal_results) == len(test_scenarios)
        
        # All different providers represented
        providers_tested = set(result["provider"] for result in universal_results)
        assert len(providers_tested) >= 2, "Should test multiple providers"
        
        return universal_results


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
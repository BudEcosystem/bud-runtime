"""
Focused demonstration of OpenAI SDK Universal Compatibility.

This test demonstrates the key architectural principle that the user requested:
- OpenAI SDK works universally with ALL providers through /v1/chat/completions
- Native provider SDKs (like Anthropic) work only with their specific endpoints

This is the core insight: One SDK (OpenAI) can work with every provider!
"""

import os
import pytest
from openai import OpenAI
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

# Configuration
TENSORZERO_BASE_URL = os.getenv("TENSORZERO_BASE_URL", "http://localhost:3001")
TENSORZERO_API_KEY = os.getenv("TENSORZERO_API_KEY", "test-api-key")

# Universal OpenAI client that works with ALL providers
universal_client = OpenAI(
    base_url=f"{TENSORZERO_BASE_URL}/v1",
    api_key=TENSORZERO_API_KEY
)

# Native Anthropic client that only works with /v1/messages
native_anthropic_client = Anthropic(
    base_url=TENSORZERO_BASE_URL,
    api_key=TENSORZERO_API_KEY,
    default_headers={"anthropic-version": "2023-06-01"}
)


class TestUniversalSDKCompatibility:
    """Demonstrate that OpenAI SDK works with ALL providers."""
    
    def test_anthropic_models_via_universal_openai_sdk(self):
        """✅ OpenAI SDK working with Anthropic models - Universal Compatibility!"""
        response = universal_client.chat.completions.create(
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": "Hello from Anthropic model via OpenAI SDK"}],
            max_tokens=50
        )
        
        # This works! OpenAI SDK + Anthropic model through /v1/chat/completions
        assert response.choices[0].message.content is not None
        assert response.model == "claude-3-haiku-20240307"
        assert len(response.choices[0].message.content) > 0
        print(f"✅ OpenAI SDK successfully used Anthropic model: {response.model}")
    
    def test_claude_35_sonnet_via_universal_openai_sdk(self):
        """✅ OpenAI SDK working with Claude 3.5 Sonnet - Universal Compatibility!"""
        response = universal_client.chat.completions.create(
            model="claude-3-5-sonnet-20241022",
            messages=[{"role": "user", "content": "Hello from Claude 3.5 Sonnet via OpenAI SDK"}],
            max_tokens=50
        )
        
        # This works! OpenAI SDK + Claude 3.5 Sonnet through /v1/chat/completions
        assert response.choices[0].message.content is not None
        assert response.model == "claude-3-5-sonnet-20241022"
        assert len(response.choices[0].message.content) > 0
        print(f"✅ OpenAI SDK successfully used Claude 3.5 Sonnet: {response.model}")
    
    def test_openai_models_via_universal_openai_sdk(self):
        """✅ OpenAI SDK working with OpenAI models - Native usage!"""
        response = universal_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello from OpenAI model via OpenAI SDK"}],
            max_tokens=50
        )
        
        # This works! OpenAI SDK + OpenAI model through /v1/chat/completions
        assert response.choices[0].message.content is not None
        assert response.model == "gpt-3.5-turbo"
        assert len(response.choices[0].message.content) > 0
        print(f"✅ OpenAI SDK successfully used OpenAI model: {response.model}")


class TestNativeSDKSpecificEndpoints:
    """Demonstrate that native SDKs work with their specific endpoints."""
    
    def test_anthropic_native_sdk_with_messages_endpoint(self):
        """✅ Native Anthropic SDK working with /v1/messages endpoint!"""
        response = native_anthropic_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=50,
            messages=[{"role": "user", "content": "Hello from native Anthropic SDK"}]
        )
        
        # This works! Native Anthropic SDK through /v1/messages
        assert len(response.content) > 0
        assert response.content[0].text is not None
        assert len(response.content[0].text) > 0
        print(f"✅ Native Anthropic SDK successfully used: {response.model}")


class TestSDKArchitectureSummary:
    """Summary demonstrating the architectural principle."""
    
    def test_architecture_demonstration(self):
        """
        🏗️ Architecture Demonstration:
        
        1. ✅ OpenAI SDK works with Anthropic models (universal compatibility)
        2. ✅ OpenAI SDK works with OpenAI models (native usage)  
        3. ✅ Native Anthropic SDK works with /v1/messages endpoint
        
        KEY INSIGHT: OpenAI SDK is UNIVERSAL - works with ALL providers!
        """
        # Test 1: OpenAI SDK + Anthropic model
        anthropic_via_openai = universal_client.chat.completions.create(
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": "Test 1: Anthropic via OpenAI SDK"}],
            max_tokens=20
        )
        
        # Test 2: OpenAI SDK + OpenAI model
        openai_via_openai = universal_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Test 2: OpenAI via OpenAI SDK"}],
            max_tokens=20
        )
        
        # Test 3: Native Anthropic SDK + /v1/messages
        anthropic_via_native = native_anthropic_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=20,
            messages=[{"role": "user", "content": "Test 3: Native Anthropic SDK"}]
        )
        
        # All should work
        assert anthropic_via_openai.choices[0].message.content is not None
        assert openai_via_openai.choices[0].message.content is not None  
        assert anthropic_via_native.content[0].text is not None
        
        print("\n" + "="*60)
        print("🏗️  ARCHITECTURE DEMONSTRATION COMPLETE")
        print("="*60)
        print("✅ OpenAI SDK + Anthropic models: WORKS (Universal)")
        print("✅ OpenAI SDK + OpenAI models: WORKS (Native)")
        print("✅ Native Anthropic SDK + /v1/messages: WORKS (Specific)")
        print("="*60)
        print("🎯 KEY INSIGHT: OpenAI SDK is UNIVERSAL!")
        print("   One SDK to rule them all providers! 🔥")
        print("="*60)


if __name__ == "__main__":
    # Run with verbose output to see the architecture demonstration
    pytest.main([__file__, "-v", "-s"])
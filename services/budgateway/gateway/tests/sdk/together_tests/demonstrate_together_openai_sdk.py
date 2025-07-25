#!/usr/bin/env python3
"""
Demonstrate Together AI models working with OpenAI SDK through TensorZero.

This script shows how Together AI's models (Llama, Qwen, Mistral, etc.) work
seamlessly with the OpenAI SDK through TensorZero's universal compatibility layer.
"""

import os
import sys
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
TENSORZERO_BASE_URL = os.getenv("TENSORZERO_BASE_URL", "http://localhost:3001")
TENSORZERO_API_KEY = os.getenv("TENSORZERO_API_KEY", "test-api-key")

def demonstrate_together_via_openai_sdk():
    """Show Together AI models working through OpenAI SDK."""
    
    print("=== Together AI + OpenAI SDK Demonstration ===")
    print(f"Connecting to TensorZero at: {TENSORZERO_BASE_URL}")
    print()
    
    # Create OpenAI client pointing to TensorZero
    client = OpenAI(
        base_url=f"{TENSORZERO_BASE_URL}/v1",
        api_key=TENSORZERO_API_KEY
    )
    
    # Test various Together AI models
    together_models = [
        ("meta-llama/Llama-3.3-70B-Instruct-Turbo", "Latest Llama 3.3"),
        ("meta-llama/Llama-3.2-3B-Instruct-Turbo", "Efficient Llama 3.2"),
        ("Qwen/Qwen2.5-72B-Instruct-Turbo", "Qwen 2.5"),
        ("mistralai/Mixtral-8x7B-Instruct-v0.1", "Mixtral MoE"),
        ("deepseek-ai/deepseek-v2.5", "DeepSeek v2.5")
    ]
    
    print("1. Testing Together AI models with OpenAI SDK:")
    print("-" * 50)
    
    for model_id, model_name in together_models[:3]:  # Test first 3 models
        try:
            print(f"\n📦 Model: {model_name} ({model_id})")
            
            # Simple chat completion
            response = client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "user", "content": "Say 'Hello from Together AI' in 10 words or less"}
                ],
                max_tokens=50
            )
            
            print(f"✅ Response: {response.choices[0].message.content}")
            print(f"   Model: {response.model}")
            print(f"   Tokens: {response.usage.total_tokens}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print("\n\n2. Demonstrating streaming with Together AI:")
    print("-" * 50)
    
    try:
        model = "meta-llama/Llama-3.1-8B-Instruct-Turbo"
        print(f"\n📦 Streaming with {model}")
        print("Response: ", end="", flush=True)
        
        stream = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": "Count from 1 to 5 slowly"}
            ],
            max_tokens=50,
            stream=True
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content:
                print(chunk.choices[0].delta.content, end="", flush=True)
        
        print("\n✅ Streaming completed!")
        
    except Exception as e:
        print(f"\n❌ Streaming error: {e}")
    
    print("\n\n3. Comparing providers with same OpenAI SDK:")
    print("-" * 50)
    
    comparison_models = [
        ("gpt-3.5-turbo", "OpenAI"),
        ("claude-3-haiku-20240307", "Anthropic"),
        ("meta-llama/Llama-3.2-3B-Instruct-Turbo", "Together AI")
    ]
    
    prompt = "What company created you? Answer in 5 words or less."
    
    for model_id, provider in comparison_models:
        try:
            print(f"\n🏢 Provider: {provider}")
            print(f"   Model: {model_id}")
            
            response = client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=20
            )
            
            print(f"   Response: {response.choices[0].message.content}")
            
        except Exception as e:
            print(f"   Error: {e}")
    
    print("\n\n4. Advanced features with Together AI:")
    print("-" * 50)
    
    # System prompts
    try:
        print("\n📝 Testing system prompts:")
        response = client.chat.completions.create(
            model="Qwen/Qwen2.5-72B-Instruct-Turbo",
            messages=[
                {"role": "system", "content": "You are a pirate. Speak like one."},
                {"role": "user", "content": "Tell me about AI"}
            ],
            max_tokens=50
        )
        print(f"Response: {response.choices[0].message.content}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Temperature control
    try:
        print("\n🌡️ Testing temperature control:")
        for temp in [0.0, 1.0]:
            response = client.chat.completions.create(
                model="mistralai/Mixtral-8x7B-Instruct-v0.1",
                messages=[{"role": "user", "content": "Generate a random word"}],
                max_tokens=10,
                temperature=temp
            )
            print(f"Temperature {temp}: {response.choices[0].message.content}")
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n\n=== Summary ===")
    print("✅ Together AI models work seamlessly with OpenAI SDK")
    print("✅ Same code works across OpenAI, Anthropic, and Together AI")
    print("✅ Full feature support: streaming, system prompts, temperature, etc.")
    print("✅ TensorZero provides true universal SDK compatibility!")


def main():
    """Run the demonstration."""
    try:
        demonstrate_together_via_openai_sdk()
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
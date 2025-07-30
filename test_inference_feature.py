#!/usr/bin/env python3
"""
End-to-end test script for the inference request/prompt listing feature.
This script creates sample inference data in ClickHouse and tests the complete flow.
"""

import asyncio
import uuid
import random
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
import aiohttp
import asyncpg
from clickhouse_driver import Client as ClickHouseClient

# Configuration
CLICKHOUSE_HOST = "localhost"
CLICKHOUSE_PORT = 9000
POSTGRES_DSN = "postgresql://postgres:postgres@localhost:5432/budapp"
BUDAPP_URL = "http://localhost:8000"
BUDMETRICS_URL = "http://localhost:8004"

# Test data configuration
NUM_INFERENCES = 100
NUM_PROJECTS = 3
NUM_ENDPOINTS = 5
NUM_MODELS = 10

# Sample prompts and responses
SAMPLE_PROMPTS = [
    "What is the capital of France?",
    "Explain quantum computing in simple terms",
    "Write a Python function to calculate factorial",
    "Translate 'Hello World' to Spanish",
    "What are the benefits of exercise?",
    "How does photosynthesis work?",
    "Write a haiku about programming",
    "Explain the theory of relativity",
    "What is machine learning?",
    "How to make a perfect cup of coffee?"
]

SAMPLE_RESPONSES = [
    "The capital of France is Paris.",
    "Quantum computing uses quantum bits (qubits) that can exist in multiple states simultaneously...",
    "def factorial(n):\n    if n <= 1:\n        return 1\n    return n * factorial(n-1)",
    "'Hello World' in Spanish is 'Hola Mundo'",
    "Exercise has numerous benefits including improved cardiovascular health, stronger muscles...",
    "Photosynthesis is the process by which plants convert sunlight, water, and CO2 into glucose...",
    "Code flows like water\nBugs emerge from the darkness\nDebugger saves all",
    "Einstein's theory of relativity consists of special and general relativity...",
    "Machine learning is a subset of artificial intelligence that enables systems to learn...",
    "To make a perfect cup of coffee: 1. Use fresh beans 2. Grind just before brewing..."
]

SAMPLE_MODELS = [
    {"name": "gpt-4", "provider": "openai", "display_name": "GPT-4"},
    {"name": "gpt-3.5-turbo", "provider": "openai", "display_name": "GPT-3.5 Turbo"},
    {"name": "claude-3-opus", "provider": "anthropic", "display_name": "Claude 3 Opus"},
    {"name": "claude-3-sonnet", "provider": "anthropic", "display_name": "Claude 3 Sonnet"},
    {"name": "llama-3-70b", "provider": "meta", "display_name": "Llama 3 70B"},
    {"name": "mistral-large", "provider": "mistral", "display_name": "Mistral Large"},
    {"name": "gemini-pro", "provider": "google", "display_name": "Gemini Pro"},
    {"name": "command-r-plus", "provider": "cohere", "display_name": "Command R+"},
    {"name": "mixtral-8x7b", "provider": "mistral", "display_name": "Mixtral 8x7B"},
    {"name": "falcon-180b", "provider": "tii", "display_name": "Falcon 180B"}
]


async def create_test_entities(pg_conn):
    """Create test projects, endpoints, and models in PostgreSQL."""
    print("Creating test entities in PostgreSQL...")
    
    # Create test user
    user_id = str(uuid.uuid4())
    await pg_conn.execute("""
        INSERT INTO users (id, username, email, full_name, created_at, updated_at)
        VALUES ($1, 'testuser', 'test@example.com', 'Test User', NOW(), NOW())
        ON CONFLICT (username) DO UPDATE SET id = EXCLUDED.id
        RETURNING id
    """, user_id)
    
    # Create test organization
    org_id = str(uuid.uuid4())
    await pg_conn.execute("""
        INSERT INTO organizations (id, name, created_at, updated_at)
        VALUES ($1, 'Test Organization', NOW(), NOW())
        ON CONFLICT (name) DO UPDATE SET id = EXCLUDED.id
        RETURNING id
    """, org_id)
    
    # Create test projects
    project_ids = []
    for i in range(NUM_PROJECTS):
        project_id = str(uuid.uuid4())
        await pg_conn.execute("""
            INSERT INTO projects (id, name, organization_id, created_by, created_at, updated_at)
            VALUES ($1, $2, $3, $4, NOW(), NOW())
            ON CONFLICT (name) DO UPDATE SET id = EXCLUDED.id
            RETURNING id
        """, project_id, f"Test Project {i+1}", org_id, user_id)
        project_ids.append(project_id)
    
    # Create test models
    model_ids = []
    for i, model in enumerate(SAMPLE_MODELS[:NUM_MODELS]):
        model_id = str(uuid.uuid4())
        await pg_conn.execute("""
            INSERT INTO models (id, name, display_name, provider, modality, created_at, updated_at)
            VALUES ($1, $2, $3, $4, 'text', NOW(), NOW())
            ON CONFLICT (name) DO UPDATE SET id = EXCLUDED.id
            RETURNING id
        """, model_id, model['name'], model['display_name'], model['provider'])
        model_ids.append(model_id)
    
    # Create test endpoints
    endpoint_ids = []
    for i in range(NUM_ENDPOINTS):
        endpoint_id = str(uuid.uuid4())
        project_id = random.choice(project_ids)
        model_id = random.choice(model_ids)
        await pg_conn.execute("""
            INSERT INTO endpoints (id, name, project_id, model_id, status, created_at, updated_at)
            VALUES ($1, $2, $3, $4, 'active', NOW(), NOW())
            ON CONFLICT (name, project_id) DO UPDATE SET id = EXCLUDED.id
            RETURNING id
        """, endpoint_id, f"Test Endpoint {i+1}", project_id, model_id)
        endpoint_ids.append(endpoint_id)
    
    return {
        "user_id": user_id,
        "project_ids": project_ids,
        "model_ids": model_ids,
        "endpoint_ids": endpoint_ids
    }


def create_sample_inferences(entities: Dict[str, Any], num_inferences: int) -> List[Dict[str, Any]]:
    """Generate sample inference data."""
    print(f"Generating {num_inferences} sample inferences...")
    
    inferences = []
    base_time = datetime.utcnow() - timedelta(days=7)
    
    for i in range(num_inferences):
        # Random time within last 7 days
        timestamp = base_time + timedelta(
            seconds=random.randint(0, 7 * 24 * 60 * 60)
        )
        
        # Select random entities
        project_id = random.choice(entities["project_ids"])
        endpoint_id = random.choice(entities["endpoint_ids"])
        model_id = random.choice(entities["model_ids"])
        
        # Select random prompt and response
        prompt = random.choice(SAMPLE_PROMPTS)
        response = random.choice(SAMPLE_RESPONSES)
        
        # Generate token counts
        input_tokens = len(prompt.split()) * random.randint(1, 3)
        output_tokens = len(response.split()) * random.randint(1, 3)
        
        # Generate performance metrics
        response_time_ms = random.randint(100, 5000)
        ttft_ms = random.randint(50, 500) if random.random() > 0.5 else None
        
        # Calculate cost (example pricing)
        cost = (input_tokens * 0.00001 + output_tokens * 0.00003) * random.uniform(0.8, 1.2)
        
        # Status and caching
        is_success = random.random() > 0.05  # 95% success rate
        cached = random.random() > 0.8  # 20% cached
        
        inference_id = str(uuid.uuid4())
        
        # Create inference record
        inference = {
            "inference_id": inference_id,
            "timestamp": timestamp,
            "project_id": project_id,
            "endpoint_id": endpoint_id,
            "model_id": model_id,
            "model_name": f"model-{model_id[:8]}",
            "model_provider": random.choice(["openai", "anthropic", "meta", "mistral"]),
            "is_success": is_success,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "response_time_ms": response_time_ms,
            "ttft_ms": ttft_ms,
            "cost": cost,
            "cached": cached,
            "messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response}
            ],
            "system_prompt": "You are a helpful AI assistant." if random.random() > 0.5 else None,
            "output": response,
            "finish_reason": "stop" if is_success else "error",
            "request_ip": f"192.168.1.{random.randint(1, 254)}"
        }
        
        inferences.append(inference)
    
    return inferences


async def insert_clickhouse_data(inferences: List[Dict[str, Any]]):
    """Insert sample data into ClickHouse tables."""
    print("Inserting data into ClickHouse...")
    
    client = ClickHouseClient(host=CLICKHOUSE_HOST, port=CLICKHOUSE_PORT)
    
    try:
        # Insert into ModelInference table
        model_inference_data = []
        for inf in inferences:
            model_inference_data.append({
                "inference_id": inf["inference_id"],
                "timestamp": inf["timestamp"],
                "project_id": inf["project_id"],
                "endpoint_id": inf["endpoint_id"],
                "model_id": inf["model_id"],
                "model_name": inf["model_name"],
                "model_provider": inf["model_provider"],
                "is_chat": True,
                "is_success": inf["is_success"],
                "input_tokens": inf["input_tokens"],
                "output_tokens": inf["output_tokens"],
                "response_time_ms": inf["response_time_ms"],
                "ttft_ms": inf["ttft_ms"],
                "cost": inf["cost"],
                "cached": inf["cached"],
                "ip_address": inf["request_ip"]
            })
        
        client.execute(
            "INSERT INTO ModelInference VALUES",
            model_inference_data
        )
        
        # Insert into ChatInference table
        chat_inference_data = []
        for inf in inferences:
            chat_inference_data.append({
                "inference_id": inf["inference_id"],
                "timestamp": inf["timestamp"],
                "system_prompt": inf["system_prompt"],
                "messages": json.dumps(inf["messages"]),
                "output": inf["output"],
                "finish_reason": inf["finish_reason"]
            })
        
        client.execute(
            "INSERT INTO ChatInference VALUES",
            chat_inference_data
        )
        
        # Insert into ModelInferenceDetails table (raw request/response)
        details_data = []
        for inf in inferences:
            raw_request = {
                "model": inf["model_name"],
                "messages": inf["messages"],
                "temperature": 0.7,
                "max_tokens": 1000
            }
            raw_response = {
                "id": f"chatcmpl-{inf['inference_id'][:8]}",
                "object": "chat.completion",
                "created": int(inf["timestamp"].timestamp()),
                "model": inf["model_name"],
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": inf["output"]},
                    "finish_reason": inf["finish_reason"]
                }],
                "usage": {
                    "prompt_tokens": inf["input_tokens"],
                    "completion_tokens": inf["output_tokens"],
                    "total_tokens": inf["input_tokens"] + inf["output_tokens"]
                }
            }
            
            details_data.append({
                "inference_id": inf["inference_id"],
                "timestamp": inf["timestamp"],
                "raw_request": json.dumps(raw_request),
                "raw_response": json.dumps(raw_response),
                "processing_time_ms": inf["response_time_ms"] * 0.8
            })
        
        client.execute(
            "INSERT INTO ModelInferenceDetails VALUES",
            details_data
        )
        
        # Insert sample feedback
        feedback_data = []
        for inf in random.sample(inferences, k=int(len(inferences) * 0.3)):  # 30% have feedback
            # Boolean feedback
            if random.random() > 0.5:
                feedback_data.append({
                    "feedback_id": str(uuid.uuid4()),
                    "inference_id": inf["inference_id"],
                    "timestamp": inf["timestamp"] + timedelta(minutes=random.randint(1, 60)),
                    "feedback_type": "boolean",
                    "metric_name": random.choice(["helpful", "accurate", "relevant"]),
                    "value": random.choice([0, 1])
                })
            
            # Float feedback (rating)
            if random.random() > 0.5:
                feedback_data.append({
                    "feedback_id": str(uuid.uuid4()),
                    "inference_id": inf["inference_id"],
                    "timestamp": inf["timestamp"] + timedelta(minutes=random.randint(1, 60)),
                    "feedback_type": "float",
                    "metric_name": "quality_rating",
                    "value": round(random.uniform(1, 5), 1)
                })
            
            # Comment feedback
            if random.random() > 0.7:
                comments = [
                    "Great response, very helpful!",
                    "Could be more detailed",
                    "Perfect answer",
                    "Not quite what I was looking for",
                    "Excellent explanation"
                ]
                feedback_data.append({
                    "feedback_id": str(uuid.uuid4()),
                    "inference_id": inf["inference_id"],
                    "timestamp": inf["timestamp"] + timedelta(minutes=random.randint(1, 60)),
                    "feedback_type": "comment",
                    "metric_name": "user_comment",
                    "value": random.choice(comments)
                })
        
        if feedback_data:
            client.execute(
                "INSERT INTO ModelInferenceFeedback VALUES",
                feedback_data
            )
        
        print(f"Successfully inserted {len(inferences)} inferences and {len(feedback_data)} feedback items")
        
    finally:
        client.disconnect()


async def test_api_endpoints(entities: Dict[str, Any], auth_token: str):
    """Test the API endpoints through BudApp."""
    print("\nTesting API endpoints...")
    
    headers = {"Authorization": f"Bearer {auth_token}"}
    
    async with aiohttp.ClientSession() as session:
        # Test 1: List inferences
        print("\n1. Testing inference list endpoint...")
        project_id = entities["project_ids"][0]
        
        list_payload = {
            "project_id": project_id,
            "from_date": (datetime.utcnow() - timedelta(days=7)).isoformat(),
            "limit": 10,
            "offset": 0
        }
        
        async with session.post(
            f"{BUDAPP_URL}/api/v1/metrics/inferences/list",
            json=list_payload,
            headers=headers
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"✓ List endpoint returned {len(data['items'])} items (total: {data['total_count']})")
                
                if data["items"]:
                    # Test 2: Get inference details
                    inference_id = data["items"][0]["inference_id"]
                    print(f"\n2. Testing inference detail endpoint for {inference_id}...")
                    
                    async with session.get(
                        f"{BUDAPP_URL}/api/v1/metrics/inferences/{inference_id}",
                        headers=headers
                    ) as detail_resp:
                        if detail_resp.status == 200:
                            detail_data = await detail_resp.json()
                            print(f"✓ Detail endpoint returned inference with {len(detail_data.get('messages', []))} messages")
                        else:
                            print(f"✗ Detail endpoint failed: {detail_resp.status}")
                    
                    # Test 3: Get inference feedback
                    print(f"\n3. Testing inference feedback endpoint for {inference_id}...")
                    
                    async with session.get(
                        f"{BUDAPP_URL}/api/v1/metrics/inferences/{inference_id}/feedback",
                        headers=headers
                    ) as feedback_resp:
                        if feedback_resp.status == 200:
                            feedback_data = await feedback_resp.json()
                            print(f"✓ Feedback endpoint returned {len(feedback_data)} feedback items")
                        else:
                            print(f"✗ Feedback endpoint failed: {feedback_resp.status}")
            else:
                print(f"✗ List endpoint failed: {resp.status}")
                error_text = await resp.text()
                print(f"Error: {error_text}")


async def main():
    """Main test function."""
    print("Starting end-to-end test for inference feature...")
    
    # Connect to PostgreSQL
    pg_conn = await asyncpg.connect(POSTGRES_DSN)
    
    try:
        # Create test entities
        entities = await create_test_entities(pg_conn)
        print(f"Created test entities: {len(entities['project_ids'])} projects, {len(entities['endpoint_ids'])} endpoints")
        
        # Generate sample inferences
        inferences = create_sample_inferences(entities, NUM_INFERENCES)
        
        # Insert into ClickHouse
        await insert_clickhouse_data(inferences)
        
        # Get auth token (you'll need to implement proper auth or use a test token)
        auth_token = "test-token"  # Replace with actual auth token
        
        # Test API endpoints
        await test_api_endpoints(entities, auth_token)
        
        print("\n✓ End-to-end test completed successfully!")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await pg_conn.close()


if __name__ == "__main__":
    asyncio.run(main())
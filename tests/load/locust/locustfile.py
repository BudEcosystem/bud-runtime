"""
Locust load test for inference API.

Usage:
    locust -f locustfile.py --host http://localhost:8000
    locust -f locustfile.py --host http://localhost:8000 --users 100 --spawn-rate 10 --run-time 5m
"""

import json
import random
import time
from typing import Dict, List

from locust import HttpUser, task, between, events
from locust.env import Environment
import gevent

# Test configuration
MODEL = "test-model"  # Change this to your model
MAX_TOKENS = 100


class InferenceUser(HttpUser):
    """Simulated user making inference requests."""
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between requests
    
    # Test prompts
    simple_prompts = [
        "Hello, how are you?",
        "What is the capital of France?",
        "Explain photosynthesis briefly.",
        "What is 2 + 2?",
        "Tell me a short joke.",
    ]
    
    medium_prompts = [
        "Explain the concept of machine learning in simple terms.",
        "What are the main causes of climate change?",
        "How does a computer processor work?",
        "Describe the process of making coffee.",
        "What are the benefits of regular exercise?",
    ]
    
    complex_prompts = [
        "Write a detailed explanation of quantum computing, including its principles and potential applications.",
        "Analyze the economic impacts of artificial intelligence on the job market.",
        "Compare and contrast different programming paradigms: functional, object-oriented, and procedural.",
        "Explain the theory of evolution and provide evidence supporting it.",
        "Discuss the ethical implications of genetic engineering in humans.",
    ]
    
    def on_start(self):
        """Called when a user starts."""
        # Test health endpoint
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"Health check failed: {response.status_code}")
    
    @task(60)
    def simple_inference(self):
        """Simple inference request (60% of traffic)."""
        prompt = random.choice(self.simple_prompts)
        self._make_inference_request(prompt, max_tokens=50)
    
    @task(30)
    def medium_inference(self):
        """Medium complexity inference (30% of traffic)."""
        prompt = random.choice(self.medium_prompts)
        self._make_inference_request(prompt, max_tokens=100)
    
    @task(10)
    def complex_inference(self):
        """Complex inference request (10% of traffic)."""
        prompt = random.choice(self.complex_prompts)
        self._make_inference_request(prompt, max_tokens=200)
    
    def _make_inference_request(self, prompt: str, max_tokens: int):
        """Make an inference request and validate response."""
        payload = {
            "model": MODEL,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": random.uniform(0.7, 1.0),
        }
        
        headers = {
            "Content-Type": "application/json",
        }
        
        start_time = time.time()
        
        with self.client.post(
            "/v1/completions",
            json=payload,
            headers=headers,
            catch_response=True,
            name=f"/v1/completions [{max_tokens} tokens]"
        ) as response:
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    
                    # Validate response structure
                    if "choices" not in data:
                        response.failure("Response missing 'choices' field")
                    elif len(data["choices"]) == 0:
                        response.failure("No choices in response")
                    elif "text" not in data["choices"][0]:
                        response.failure("No text in response")
                    else:
                        # Calculate tokens per second if available
                        if "usage" in data and data["usage"].get("completion_tokens"):
                            elapsed = time.time() - start_time
                            tokens = data["usage"]["completion_tokens"]
                            tokens_per_sec = tokens / elapsed if elapsed > 0 else 0
                            
                            # Record custom metrics
                            events.request.fire(
                                request_type="CUSTOM",
                                name="tokens_per_second",
                                response_time=tokens_per_sec * 1000,  # Convert to ms for consistency
                                response_length=tokens,
                                exception=None,
                                context={}
                            )
                        
                        response.success()
                
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
                except Exception as e:
                    response.failure(f"Response validation failed: {str(e)}")
            
            elif response.status_code == 429:
                response.failure("Rate limited")
            elif response.status_code == 503:
                response.failure("Service unavailable")
            else:
                response.failure(f"Unexpected status code: {response.status_code}")


class StressTestUser(InferenceUser):
    """User for stress testing with more aggressive patterns."""
    
    wait_time = between(0.1, 0.5)  # Much shorter wait times
    
    @task
    def burst_requests(self):
        """Send burst of requests."""
        for _ in range(5):
            prompt = random.choice(self.simple_prompts)
            self._make_inference_request(prompt, max_tokens=20)
            gevent.sleep(0.1)


class ModelComparisonUser(HttpUser):
    """User for comparing different models."""
    
    wait_time = between(2, 4)
    models = ["test-model", "llama2-7b", "mistral-7b"]  # Configure your models
    
    @task
    def compare_models(self):
        """Test different models with same prompt."""
        prompt = "Explain artificial intelligence in one sentence."
        
        for model in self.models:
            payload = {
                "model": model,
                "prompt": prompt,
                "max_tokens": 50,
                "temperature": 0.7,
            }
            
            with self.client.post(
                "/v1/completions",
                json=payload,
                catch_response=True,
                name=f"/v1/completions [{model}]"
            ) as response:
                if response.status_code == 200:
                    response.success()
                elif response.status_code == 404:
                    response.failure(f"Model {model} not found")
                else:
                    response.failure(f"Failed with status {response.status_code}")


# Event handlers for custom reporting
@events.test_start.add_listener
def on_test_start(environment: Environment, **kwargs):
    """Called when test starts."""
    print(f"Starting load test against {environment.host}")
    print(f"Target model: {MODEL}")


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Custom request handler for additional metrics."""
    if exception:
        print(f"Request failed: {name} - {exception}")


@events.test_stop.add_listener
def on_test_stop(environment: Environment, **kwargs):
    """Called when test stops."""
    print("\nTest completed!")
    print(f"Total requests: {environment.stats.total.num_requests}")
    print(f"Failed requests: {environment.stats.total.num_failures}")
    print(f"Median response time: {environment.stats.total.median_response_time}ms")
    print(f"95th percentile: {environment.stats.total.get_response_time_percentile(0.95)}ms")


# Custom shapes for different test scenarios
class StagesShape:
    """Custom load shape for staged testing."""
    
    stages = [
        {"duration": 60, "users": 10, "spawn_rate": 1},     # Warm up
        {"duration": 300, "users": 50, "spawn_rate": 2},    # Normal load
        {"duration": 120, "users": 100, "spawn_rate": 5},   # High load
        {"duration": 60, "users": 10, "spawn_rate": 5},     # Cool down
    ]
    
    def tick(self):
        run_time = self.get_run_time()
        
        for stage in self.stages:
            if run_time < stage["duration"]:
                tick_data = (stage["users"], stage["spawn_rate"])
                return tick_data
        
        return None
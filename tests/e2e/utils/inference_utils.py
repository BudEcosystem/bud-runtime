"""Inference utilities for E2E tests."""

import time
import json
import logging
import asyncio
import statistics
from typing import Dict, List, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

import requests
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


@dataclass
class InferenceResult:
    """Inference result with metadata."""
    success: bool
    response: Optional[Dict[str, Any]]
    latency_ms: float
    model: str
    prompt: str
    error: Optional[str] = None
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


def make_inference_request(
    endpoint: str,
    model: str,
    prompt: str,
    max_tokens: int = 50,
    temperature: float = 0.7,
    timeout: int = 30,
    **kwargs
) -> InferenceResult:
    """Make a single inference request."""
    start_time = time.time()
    
    payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": temperature,
        **kwargs
    }
    
    try:
        response = requests.post(
            f"{endpoint}/v1/completions",
            json=payload,
            timeout=timeout
        )
        response.raise_for_status()
        
        latency_ms = (time.time() - start_time) * 1000
        
        return InferenceResult(
            success=True,
            response=response.json(),
            latency_ms=latency_ms,
            model=model,
            prompt=prompt
        )
    
    except requests.exceptions.RequestException as e:
        latency_ms = (time.time() - start_time) * 1000
        logger.error(f"Inference request failed: {e}")
        
        return InferenceResult(
            success=False,
            response=None,
            latency_ms=latency_ms,
            model=model,
            prompt=prompt,
            error=str(e)
        )


async def make_async_inference_request(
    session: aiohttp.ClientSession,
    endpoint: str,
    model: str,
    prompt: str,
    max_tokens: int = 50,
    temperature: float = 0.7,
    timeout: int = 30,
    **kwargs
) -> InferenceResult:
    """Make an async inference request."""
    start_time = time.time()
    
    payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": temperature,
        **kwargs
    }
    
    try:
        async with session.post(
            f"{endpoint}/v1/completions",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=timeout)
        ) as response:
            response.raise_for_status()
            result = await response.json()
            
            latency_ms = (time.time() - start_time) * 1000
            
            return InferenceResult(
                success=True,
                response=result,
                latency_ms=latency_ms,
                model=model,
                prompt=prompt
            )
    
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        logger.error(f"Async inference request failed: {e}")
        
        return InferenceResult(
            success=False,
            response=None,
            latency_ms=latency_ms,
            model=model,
            prompt=prompt,
            error=str(e)
        )


def batch_inference(
    endpoint: str,
    model: str,
    prompts: List[str],
    max_tokens: int = 50,
    temperature: float = 0.7,
    max_workers: int = 10,
    timeout: int = 30
) -> List[InferenceResult]:
    """Perform batch inference with concurrent requests."""
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                make_inference_request,
                endpoint, model, prompt, max_tokens, temperature, timeout
            ): prompt
            for prompt in prompts
        }
        
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
    
    return results


async def async_batch_inference(
    endpoint: str,
    model: str,
    prompts: List[str],
    max_tokens: int = 50,
    temperature: float = 0.7,
    max_concurrent: int = 10,
    timeout: int = 30
) -> List[InferenceResult]:
    """Perform async batch inference."""
    results = []
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def bounded_inference(session, prompt):
        async with semaphore:
            return await make_async_inference_request(
                session, endpoint, model, prompt,
                max_tokens, temperature, timeout
            )
    
    async with aiohttp.ClientSession() as session:
        tasks = [
            bounded_inference(session, prompt)
            for prompt in prompts
        ]
        results = await asyncio.gather(*tasks)
    
    return results


def measure_latency(
    inference_func: Callable,
    iterations: int = 10,
    **kwargs
) -> Dict[str, float]:
    """Measure latency statistics."""
    latencies = []
    
    for _ in range(iterations):
        start_time = time.time()
        result = inference_func(**kwargs)
        latency = (time.time() - start_time) * 1000
        
        if hasattr(result, 'latency_ms'):
            latencies.append(result.latency_ms)
        else:
            latencies.append(latency)
    
    return {
        "min": min(latencies),
        "max": max(latencies),
        "mean": statistics.mean(latencies),
        "median": statistics.median(latencies),
        "p95": statistics.quantiles(latencies, n=20)[18] if len(latencies) > 20 else max(latencies),
        "p99": statistics.quantiles(latencies, n=100)[98] if len(latencies) > 100 else max(latencies),
        "stdev": statistics.stdev(latencies) if len(latencies) > 1 else 0
    }


def validate_response(
    response: Dict[str, Any],
    expected_fields: List[str] = None
) -> Tuple[bool, List[str]]:
    """Validate inference response structure."""
    errors = []
    
    # Default expected fields for OpenAI-compatible response
    if expected_fields is None:
        expected_fields = ["id", "object", "created", "model", "choices"]
    
    # Check required fields
    for field in expected_fields:
        if field not in response:
            errors.append(f"Missing required field: {field}")
    
    # Validate choices structure
    if "choices" in response:
        if not isinstance(response["choices"], list):
            errors.append("'choices' should be a list")
        elif len(response["choices"]) == 0:
            errors.append("'choices' list is empty")
        else:
            # Check first choice
            choice = response["choices"][0]
            if "text" not in choice and "message" not in choice:
                errors.append("Choice missing 'text' or 'message' field")
            if "index" not in choice:
                errors.append("Choice missing 'index' field")
    
    # Validate usage if present
    if "usage" in response:
        usage = response["usage"]
        for field in ["prompt_tokens", "completion_tokens", "total_tokens"]:
            if field not in usage:
                errors.append(f"Usage missing '{field}'")
    
    return len(errors) == 0, errors


def generate_test_prompt(
    category: str = "general",
    length: str = "short"
) -> str:
    """Generate test prompts by category."""
    prompts = {
        "general": {
            "short": [
                "Hello!",
                "How are you?",
                "What's the weather like?"
            ],
            "medium": [
                "Explain the concept of machine learning.",
                "What are the benefits of renewable energy?",
                "Describe the process of photosynthesis."
            ],
            "long": [
                "Write a detailed explanation of how neural networks work, including the mathematics behind backpropagation.",
                "Analyze the economic impacts of artificial intelligence on the job market over the next decade.",
                "Discuss the ethical implications of genetic engineering in humans."
            ]
        },
        "code": {
            "short": [
                "Write a hello world program.",
                "Create a for loop in Python.",
                "Define a function that adds two numbers."
            ],
            "medium": [
                "Write a Python function to check if a string is a palindrome.",
                "Create a JavaScript class for a simple calculator.",
                "Implement a binary search algorithm in Java."
            ],
            "long": [
                "Implement a complete REST API in Python using FastAPI with CRUD operations for a user management system.",
                "Create a React component for a todo list application with add, edit, delete, and filter functionality.",
                "Write a SQL schema and queries for an e-commerce database with products, orders, and customers."
            ]
        },
        "math": {
            "short": [
                "What is 15 + 27?",
                "Calculate 20% of 150.",
                "Solve for x: 2x + 5 = 15"
            ],
            "medium": [
                "Find the derivative of f(x) = 3x^2 + 2x - 5",
                "Calculate the area of a circle with radius 7.",
                "Solve the quadratic equation: x^2 - 5x + 6 = 0"
            ],
            "long": [
                "Prove that the sum of angles in a triangle equals 180 degrees.",
                "Derive the formula for the volume of a sphere using calculus.",
                "Explain and solve a system of linear equations using matrix methods."
            ]
        }
    }
    
    import random
    category_prompts = prompts.get(category, prompts["general"])
    length_prompts = category_prompts.get(length, category_prompts["short"])
    
    return random.choice(length_prompts)


def calculate_throughput(
    results: List[InferenceResult],
    duration_seconds: float
) -> Dict[str, float]:
    """Calculate throughput metrics."""
    successful_requests = sum(1 for r in results if r.success)
    failed_requests = sum(1 for r in results if not r.success)
    
    return {
        "total_requests": len(results),
        "successful_requests": successful_requests,
        "failed_requests": failed_requests,
        "success_rate": successful_requests / len(results) if results else 0,
        "requests_per_second": len(results) / duration_seconds if duration_seconds > 0 else 0,
        "successful_rps": successful_requests / duration_seconds if duration_seconds > 0 else 0
    }
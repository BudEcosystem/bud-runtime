#!/usr/bin/env python3
"""Examples of using the Bud Serve Metrics Analytics API.

This script demonstrates various use cases for querying metrics data.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone

import aiohttp


# API Configuration
API_BASE_URL = "http://localhost:8000"
ANALYTICS_ENDPOINT = f"{API_BASE_URL}/observability/analytics"


async def example_1_simple_daily_metrics():
    """Example 1: Simple daily request count for the last 7 days."""
    print("\n=== Example 1: Simple Daily Metrics ===")

    payload = {
        "metrics": ["request_count"],
        "from_date": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
        "frequency_unit": "day",
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(ANALYTICS_ENDPOINT, json=payload) as response:
            result = await response.json()

            print(f"Request: {json.dumps(payload, indent=2)}")
            print(f"Response: {json.dumps(result, indent=2)}")


async def example_2_multiple_metrics_with_grouping():
    """Example 2: Multiple metrics grouped by model with deltas."""
    print("\n=== Example 2: Multiple Metrics with Grouping ===")

    payload = {
        "metrics": ["request_count", "latency", "success_request"],
        "from_date": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
        "frequency_unit": "week",
        "group_by": ["model"],
        "return_delta": True,
        "topk": 5,  # Top 5 models by request count
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(ANALYTICS_ENDPOINT, json=payload) as response:
            result = await response.json()

            print(f"Request: {json.dumps(payload, indent=2)}")
            print("\nTop 5 models by request count (weekly):")

            if result.get("items"):
                for period in result["items"][:2]:  # Show first 2 periods
                    print(f"\nWeek: {period['time_period']}")
                    for item in period["items"]:
                        print(f"  Model: {item['model_id']}")
                        data = item["data"]
                        if "request_count" in data:
                            rc = data["request_count"]
                            print(f"    Requests: {rc['count']:,} (Δ {rc.get('delta_percent', 0):.1f}%)")
                        if "latency" in data:
                            lat = data["latency"]
                            print(f"    Avg Latency: {lat['avg_latency_ms']:.1f}ms")


async def example_3_custom_time_intervals():
    """Example 3: Custom 7-day intervals aligned to specific start date."""
    print("\n=== Example 3: Custom Time Intervals ===")

    # Start from a specific Sunday
    from_date = datetime(2024, 1, 7, 0, 0, 0, tzinfo=timezone.utc)  # Sunday
    to_date = from_date + timedelta(days=28)  # 4 weeks

    payload = {
        "metrics": ["request_count", "concurrent_requests"],
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "frequency_unit": "day",
        "frequency_interval": 7,  # 7-day buckets
        "fill_time_gaps": False,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(ANALYTICS_ENDPOINT, json=payload) as response:
            result = await response.json()

            print(f"Request: Custom 7-day intervals from {from_date.date()}")
            print("\nTime buckets (aligned to Sunday):")

            if result.get("items"):
                for period in result["items"]:
                    print(
                        f"  {period['time_period']} - Requests: {period['items'][0]['data']['request_count']['count']:,}"
                    )


async def example_4_filtered_metrics():
    """Example 4: Metrics filtered by specific projects and endpoints."""
    print("\n=== Example 4: Filtered Metrics ===")

    payload = {
        "metrics": ["request_count", "success_request", "failure_request"],
        "from_date": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        "frequency_unit": "hour",
        "filters": {
            "project": ["550e8400-e29b-41d4-a716-446655440000"],  # Specific project
            # Can also filter by model or endpoint
            # "model": "550e8400-e29b-41d4-a716-446655440001",
            # "endpoint": ["uuid1", "uuid2"]
        },
        "return_delta": True,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(ANALYTICS_ENDPOINT, json=payload) as response:
            result = await response.json()

            print("Request: Hourly metrics for specific project")
            print(f"Response contains {len(result.get('items', []))} time periods")


async def example_5_performance_metrics():
    """Example 5: Performance metrics (latency, TTFT, throughput)."""
    print("\n=== Example 5: Performance Metrics ===")

    payload = {
        "metrics": ["latency", "ttft", "throughput"],
        "from_date": (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(),
        "frequency_unit": "hour",
        "group_by": ["endpoint"],
        "topk": 10,  # Top 10 endpoints by latency
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(ANALYTICS_ENDPOINT, json=payload) as response:
            result = await response.json()

            print("Request: Hourly performance metrics by endpoint")

            if result.get("items") and result["items"][0]["items"]:
                latest = result["items"][0]
                print(f"\nLatest hour ({latest['time_period']}):")
                for item in latest["items"][:5]:  # Top 5
                    print(f"\n  Endpoint: {item['endpoint_id']}")
                    data = item["data"]

                    if "latency" in data:
                        lat = data["latency"]
                        print(
                            f"    Latency - Avg: {lat['avg_latency_ms']:.1f}ms, P95: {lat.get('latency_p95', 0):.1f}ms"
                        )

                    if "ttft" in data:
                        ttft = data["ttft"]
                        print(f"    TTFT - Avg: {ttft['avg_ttft_ms']:.1f}ms")

                    if "throughput" in data:
                        tp = data["throughput"]
                        print(f"    Throughput: {tp['avg_throughput_tokens_per_sec']:.1f} tokens/sec")


async def example_6_cache_metrics():
    """Example 6: Cache performance metrics."""
    print("\n=== Example 6: Cache Metrics ===")

    payload = {
        "metrics": ["cache"],
        "from_date": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
        "frequency_unit": "day",
        "group_by": ["model"],
        "fill_time_gaps": True,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(ANALYTICS_ENDPOINT, json=payload) as response:
            result = await response.json()

            print("Request: Daily cache metrics by model")

            if result.get("items"):
                # Show summary for all models
                total_hits = 0
                total_count = 0

                for period in result["items"]:
                    for item in period["items"]:
                        if item["data"].get("cache"):
                            cache_data = item["data"]["cache"]
                            total_hits += cache_data.get("cache_hit_count", 0)
                            total_count += cache_data.get("cache_hit_count", 0)
                            # Note: You'd need to track total requests separately

                print(f"\nTotal cache hits over 7 days: {total_hits:,}")


async def example_7_token_metrics():
    """Example 7: Token usage metrics for cost analysis."""
    print("\n=== Example 7: Token Usage Metrics ===")

    payload = {
        "metrics": ["input_token", "output_token"],
        "from_date": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
        "frequency_unit": "day",
        "group_by": ["project", "model"],
        "topk": 20,  # Top 20 project-model combinations
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(ANALYTICS_ENDPOINT, json=payload) as response:
            result = await response.json()

            print("Request: Daily token usage by project and model")

            # Calculate total tokens for the period
            total_input = 0
            total_output = 0

            if result.get("items"):
                for period in result["items"]:
                    for item in period["items"]:
                        data = item["data"]
                        total_input += data.get("input_token", {}).get("input_token_count", 0)
                        total_output += data.get("output_token", {}).get("output_token_count", 0)

                print("\nTotal tokens over 30 days:")
                print(f"  Input: {total_input:,}")
                print(f"  Output: {total_output:,}")
                print(f"  Total: {total_input + total_output:,}")


async def example_8_error_analysis():
    """Example 8: Analyze failure patterns."""
    print("\n=== Example 8: Error Analysis ===")

    payload = {
        "metrics": ["failure_request", "success_request"],
        "from_date": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
        "frequency_unit": "hour",
        "frequency_interval": 6,  # 6-hour buckets
        "group_by": ["endpoint"],
        "return_delta": True,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(ANALYTICS_ENDPOINT, json=payload) as response:
            result = await response.json()

            print("Request: 6-hourly error rates by endpoint")

            if result.get("items"):
                # Find endpoints with high failure rates
                problematic_endpoints = []

                for period in result["items"][:4]:  # Last day
                    for item in period["items"]:
                        failure_data = item["data"].get("failure_request", {})
                        failure_rate = failure_data.get("failure_rate", 0)

                        if failure_rate > 5:  # More than 5% failure rate
                            problematic_endpoints.append(
                                {
                                    "endpoint": item["endpoint_id"],
                                    "time": period["time_period"],
                                    "failure_rate": failure_rate,
                                }
                            )

                if problematic_endpoints:
                    print("\nEndpoints with high failure rates (>5%):")
                    for ep in problematic_endpoints[:5]:
                        print(f"  {ep['time']}: Endpoint {ep['endpoint'][:8]}... - {ep['failure_rate']:.1f}%")


async def main():
    """Run all examples."""
    examples = [
        example_1_simple_daily_metrics,
        example_2_multiple_metrics_with_grouping,
        example_3_custom_time_intervals,
        example_4_filtered_metrics,
        example_5_performance_metrics,
        example_6_cache_metrics,
        example_7_token_metrics,
        example_8_error_analysis,
    ]

    for example in examples:
        try:
            await example()
            await asyncio.sleep(0.5)  # Small delay between examples
        except Exception as e:
            print(f"Error in {example.__name__}: {e}")

    print("\n=== All examples completed ===")


if __name__ == "__main__":
    print("Bud Serve Metrics - Analytics API Examples")
    print("==========================================")
    print(f"API Endpoint: {ANALYTICS_ENDPOINT}")

    asyncio.run(main())

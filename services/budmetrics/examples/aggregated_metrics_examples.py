#!/usr/bin/env python3
"""Examples demonstrating how to use the new aggregated metrics endpoints.

These examples show different use cases for the server-side aggregated metrics API
that leverages ClickHouse's powerful aggregation capabilities.
"""

import asyncio
from datetime import datetime, timedelta

import httpx


# Base URL for the budmetrics service
BASE_URL = "http://localhost:8003"  # Adjust as needed


async def example_aggregated_metrics():
    """Get pre-calculated aggregated metrics example."""
    print("📊 Example: Aggregated Metrics")
    print("-" * 40)

    # Request aggregated metrics grouped by model
    request_data = {
        "from_date": (datetime.now() - timedelta(days=7)).isoformat(),
        "to_date": datetime.now().isoformat(),
        "metrics": [
            "total_requests",
            "success_rate",
            "avg_latency",
            "p95_latency",
            "total_tokens",
            "avg_cost",
            "cache_hit_rate",
        ],
        "group_by": ["model", "project"],
        "filters": {
            "project_id": ["550e8400-e29b-41d4-a716-446655440000"]  # Example project ID
        },
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{BASE_URL}/observability/metrics/aggregated", json=request_data, timeout=30.0
            )

            if response.status_code == 200:
                data = response.json()
                print(f"✅ Found {data['total_groups']} groups")

                for group in data["groups"][:3]:  # Show first 3 groups
                    print(f"\n🎯 Model: {group.get('model_name', 'Unknown')}")
                    print(f"   Project: {group.get('project_id', 'N/A')}")

                    for metric, value in group["metrics"].items():
                        print(f"   {metric}: {value['formatted_value']}")

                print(f"\n📈 Summary metrics available: {list(data['summary'].keys())}")
            else:
                print(f"❌ Request failed: {response.status_code}")
                print(response.text)

        except Exception as e:
            print(f"❌ Error: {e}")


async def example_time_series():
    """Get time-series data for charts example."""
    print("\n📈 Example: Time Series Data")
    print("-" * 40)

    request_data = {
        "from_date": (datetime.now() - timedelta(hours=24)).isoformat(),
        "to_date": datetime.now().isoformat(),
        "interval": "1h",  # Hourly buckets
        "metrics": ["requests", "success_rate", "avg_latency", "cache_hit_rate"],
        "group_by": ["model"],
        "fill_gaps": True,
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{BASE_URL}/observability/metrics/time-series", json=request_data, timeout=30.0
            )

            if response.status_code == 200:
                data = response.json()
                print(f"✅ Time series data with {data['interval']} intervals")
                print(f"📊 Found {len(data['groups'])} model groups")

                for group in data["groups"][:2]:  # Show first 2 groups
                    print(f"\n🎯 Model: {group.get('model_name', 'Unknown')}")
                    print(f"   Data points: {len(group['data_points'])}")

                    # Show a few recent data points
                    for point in group["data_points"][-3:]:
                        print(f"   {point['timestamp'][:16]}: {point['values']}")

            else:
                print(f"❌ Request failed: {response.status_code}")
                print(response.text)

        except Exception as e:
            print(f"❌ Error: {e}")


async def example_geographic_data():
    """Get geographic distribution example."""
    print("\n🌍 Example: Geographic Distribution")
    print("-" * 40)

    params = {
        "from_date": (datetime.now() - timedelta(days=30)).isoformat(),
        "to_date": datetime.now().isoformat(),
        "group_by": "country",
        "limit": 10,
        # "project_id": "550e8400-e29b-41d4-a716-446655440000",  # Optional filter
        # "country_codes": "US,UK,DE"  # Optional filter
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/observability/metrics/geography", params=params, timeout=30.0)

            if response.status_code == 200:
                data = response.json()
                print(f"✅ Geographic data for {data['total_locations']} locations")
                print(f"📈 Total requests: {data['total_requests']:,}")

                print("\n🏆 Top locations by request count:")
                for location in data["locations"][:5]:
                    country = location["country_code"]
                    requests = location["request_count"]
                    success_rate = location["success_rate"]
                    percentage = location["percentage"]

                    print(f"   {country}: {requests:,} requests ({percentage:.1f}%, {success_rate:.1f}% success)")

            else:
                print(f"❌ Request failed: {response.status_code}")
                print(response.text)

        except Exception as e:
            print(f"❌ Error: {e}")


def example_use_cases():
    """Show common use cases for the aggregated metrics API."""
    print("\n💡 Common Use Cases")
    print("-" * 40)

    use_cases = [
        {
            "title": "Dashboard Overview",
            "description": "Get high-level metrics for dashboard cards",
            "endpoint": "/metrics/aggregated",
            "params": "No grouping, summary metrics only",
        },
        {
            "title": "Model Comparison",
            "description": "Compare performance across models",
            "endpoint": "/metrics/aggregated",
            "params": "Group by model, include latency and success rate",
        },
        {
            "title": "Performance Trends",
            "description": "Track metrics over time for charts",
            "endpoint": "/metrics/time-series",
            "params": "Hourly/daily intervals, fill gaps for smooth charts",
        },
        {
            "title": "Geographic Analysis",
            "description": "Understand global usage patterns",
            "endpoint": "/metrics/geography",
            "params": "Group by country/city, include latency by location",
        },
        {
            "title": "Cost Analysis",
            "description": "Track spending by project/model",
            "endpoint": "/metrics/aggregated",
            "params": "Focus on cost metrics, group by project",
        },
        {
            "title": "Real-time Monitoring",
            "description": "Monitor current system performance",
            "endpoint": "/metrics/time-series",
            "params": "Short intervals (1-5m), recent time range",
        },
    ]

    for i, use_case in enumerate(use_cases, 1):
        print(f"{i}. {use_case['title']}")
        print(f"   📝 {use_case['description']}")
        print(f"   🔗 {use_case['endpoint']}")
        print(f"   ⚙️  {use_case['params']}")
        print()


async def main():
    """Run all examples."""
    print("🚀 Aggregated Metrics API Examples")
    print("=" * 50)
    print("These examples demonstrate the new server-side aggregated metrics endpoints")
    print("that leverage ClickHouse's aggregation capabilities for high performance.\n")

    # Show use cases
    example_use_cases()

    print("🔧 Live API Examples (requires running budmetrics service)")
    print("-" * 60)

    # Run live examples (will show errors if service isn't running)
    await example_aggregated_metrics()
    await example_time_series()
    await example_geographic_data()

    print("\n" + "=" * 50)
    print("✨ Key Benefits of Server-Side Aggregation:")
    print("• Faster response times - calculations done in ClickHouse")
    print("• Reduced network transfer - only aggregated results sent")
    print("• Consistent formatting - human-readable values with units")
    print("• Efficient grouping - supports multiple grouping dimensions")
    print("• Flexible filtering - filter by project, model, endpoint, etc.")
    print("• Chart-ready data - time series with configurable intervals")


if __name__ == "__main__":
    asyncio.run(main())

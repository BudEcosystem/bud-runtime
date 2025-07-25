"""Test fixtures and sample data for unit tests."""

from datetime import datetime, timezone
from typing import Dict, List, Any
from uuid import uuid4

# Create stable UUIDs for testing
TEST_PROJECT_IDS = [uuid4() for _ in range(3)]
TEST_MODEL_IDS = [uuid4() for _ in range(4)]
TEST_ENDPOINT_IDS = [uuid4() for _ in range(2)]

SAMPLE_INFERENCE_DATA = {
    "inference_id": uuid4(),
    "project_id": TEST_PROJECT_IDS[0],
    "endpoint_id": TEST_ENDPOINT_IDS[0],
    "model_id": TEST_MODEL_IDS[0],
    "cost": 0.001234,
    "response_analysis": {"sentiment": "positive", "confidence": 0.95},
    "is_success": True,
    "request_arrival_time": datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
    "request_forward_time": datetime(2024, 1, 15, 10, 30, 1, tzinfo=timezone.utc),
}

SAMPLE_BULK_INFERENCE_DATA = [
    {
        "inference_id": str(uuid4()),
        "project_id": str(TEST_PROJECT_IDS[i % 3]),
        "endpoint_id": str(TEST_ENDPOINT_IDS[i % 2]),
        "model_id": str(TEST_MODEL_IDS[i % 4]),
        "cost": 0.001 * (i + 1),
        "response_analysis": {"sentiment": ["positive", "negative", "neutral"][i % 3]},
        "is_success": i % 5 != 0,  # Every 5th request fails
        "request_arrival_time": datetime(2024, 1, 15, 10, 30, i, tzinfo=timezone.utc).isoformat(),
        "request_forward_time": datetime(2024, 1, 15, 10, 30, i + 1, tzinfo=timezone.utc).isoformat(),
    }
    for i in range(50)
]

SAMPLE_MODEL_INFERENCE_DATA = {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "inference_id": "test-inference-123",
    "input_token": 150,
    "output_token": 200,
    "response_time_ms": 1234.56,
    "ttft_ms": 234.56,
    "prompt_eval_count": 150,
    "eval_count": 200,
    "model": "gpt-4",
    "tags": {"user": "test-user", "session": "test-session"},
    "cached": "hit",
    "request_arrival_time": datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
}

ANALYTICS_REQUEST_SAMPLES = {
    "basic": {
        "project_id": "project-001",
        "model_id": "model-001",
        "from_date": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "to_date": datetime(2024, 1, 31, tzinfo=timezone.utc),
        "frequency": "daily",
        "metrics": ["request_count", "success_request"],
    },
    "with_filters": {
        "project_id": "project-001",
        "model_id": "model-001",
        "endpoint_id": "endpoint-001",
        "from_date": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "to_date": datetime(2024, 1, 31, tzinfo=timezone.utc),
        "frequency": "hourly",
        "metrics": ["latency", "throughput", "ttft"],
    },
    "with_groupby": {
        "project_id": "project-001",
        "from_date": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "to_date": datetime(2024, 1, 31, tzinfo=timezone.utc),
        "frequency": "daily",
        "metrics": ["request_count"],
        "group_by": ["model_id", "endpoint_id"],
    },
    "with_topk": {
        "project_id": "project-001",
        "from_date": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "to_date": datetime(2024, 1, 31, tzinfo=timezone.utc),
        "frequency": "daily",
        "metrics": ["request_count"],
        "group_by": ["model_id"],
        "top_k": 5,
    },
    "custom_interval": {
        "project_id": "project-001",
        "model_id": "model-001",
        "from_date": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "to_date": datetime(2024, 2, 29, tzinfo=timezone.utc),
        "frequency": "7 days",
        "metrics": ["request_count", "cost"],
    },
}

EXPECTED_QUERY_PATTERNS = {
    "basic_request_count": [
        "SELECT",
        "toStartOfDay(request_arrival_time)",
        "COUNT(*) AS request_count",
        "FROM ModelInferenceDetails",
        "WHERE project_id = 'project-001'",
        "GROUP BY time_bucket",
        "ORDER BY time_bucket",
    ],
    "with_model_filter": [
        "model_id = 'model-001'",
    ],
    "with_groupby": [
        "GROUP BY time_bucket, model_id, endpoint_id",
    ],
    "with_topk": [
        "ROW_NUMBER() OVER",
        "PARTITION BY time_bucket",
        "ORDER BY request_count DESC",
    ],
}

def get_mock_clickhouse_response(metric_type: str, num_periods: int = 5) -> List[Dict[str, Any]]:
    """Generate mock ClickHouse response data for different metric types."""
    base_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    
    if metric_type == "request_count":
        return [
            {
                "time_bucket": base_date.replace(day=i+1),
                "request_count": 100 + i * 10
            }
            for i in range(num_periods)
        ]
    elif metric_type == "success_failure":
        return [
            {
                "time_bucket": base_date.replace(day=i+1),
                "success_request": 90 + i * 8,
                "failure_request": 10 + i * 2
            }
            for i in range(num_periods)
        ]
    elif metric_type == "latency":
        return [
            {
                "time_bucket": base_date.replace(day=i+1),
                "latency": 250.5 + i * 25.5
            }
            for i in range(num_periods)
        ]
    elif metric_type == "grouped":
        models = ["model-001", "model-002"]
        result = []
        for i in range(num_periods):
            for model in models:
                result.append({
                    "time_bucket": base_date.replace(day=i+1),
                    "model_id": model,
                    "request_count": 50 + i * 5 if model == "model-001" else 40 + i * 4
                })
        return result
    else:
        return []

def get_mock_cache_data() -> Dict[str, Any]:
    """Get sample data for cache-related tests."""
    return {
        "cache_hit": {"time_bucket": datetime(2024, 1, 1), "cache": 150},
        "cache_miss": {"time_bucket": datetime(2024, 1, 2), "cache": 50},
        "cache_skip": {"time_bucket": datetime(2024, 1, 3), "cache": 20},
        "cache_error": {"time_bucket": datetime(2024, 1, 4), "cache": 5},
    }
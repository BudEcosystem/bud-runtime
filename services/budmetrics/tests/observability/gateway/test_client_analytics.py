"""Tests for GET /observability/gateway/client-analytics endpoint.

These tests validate the gateway client analytics API by:
1. Testing all query parameters (from_date, to_date, group_by, project_id)
2. Verifying response structure matches expected schema
3. Comparing values against InferenceFact ground truth

Run with: pytest tests/observability/gateway/test_client_analytics.py -v -s
"""

import asyncio
from datetime import datetime
from uuid import UUID

import pytest

from budmetrics.observability.models import ClickHouseClient, ClickHouseConfig


pytestmark = pytest.mark.integration


TEST_PROJECT_ID = UUID("019787c1-3de1-7b50-969b-e0a58514b6a1")
TEST_FROM_DATE = datetime(2026, 1, 7, 0, 0, 0)
TEST_TO_DATE = datetime(2026, 1, 7, 23, 59, 59)
TEST_NONEXISTENT_ID = UUID("00000000-0000-0000-0000-000000000000")

CLIENT_ANALYTICS_URL = "/observability/gateway/client-analytics"


async def _fetch_client_analytics_ground_truth():
    """Async helper to query ClickHouse for client analytics ground truth values."""
    config = ClickHouseConfig()
    client = ClickHouseClient(config)
    await client.initialize()

    async def _fetch_distribution(field: str, project_id: UUID | None = None):
        date_filter = f"timestamp >= '{TEST_FROM_DATE}' AND timestamp <= '{TEST_TO_DATE}'"
        project_filter = f"AND project_id = '{project_id}'" if project_id else ""

        result = await client.execute_query(f"""
            SELECT
                {field},
                count(*) as count
            FROM InferenceFact
            WHERE {date_filter}
                {project_filter}
                AND {field} IS NOT NULL
            GROUP BY {field}
            ORDER BY count DESC
        """)

        distribution = [
            {"name": row[0], "count": row[1]}
            for row in result
        ] if result else []
        total = sum(item["count"] for item in distribution)

        for item in distribution:
            item["percent"] = round((item["count"] / total * 100), 2) if total > 0 else 0

        return {"distribution": distribution, "total": total}

    try:
        ground_truth = {
            "device_type": await _fetch_distribution("device_type"),
            "browser": await _fetch_distribution("browser_name"),
            "os": await _fetch_distribution("os_name"),
            "project_device_type": await _fetch_distribution("device_type", TEST_PROJECT_ID),
            "project_browser": await _fetch_distribution("browser_name", TEST_PROJECT_ID),
            "project_os": await _fetch_distribution("os_name", TEST_PROJECT_ID),
        }
        return ground_truth
    finally:
        await client.close()


@pytest.fixture(scope="session")
def client_analytics_ground_truth(seed_test_data):
    """Fetch ground truth from InferenceFact (seeding done by shared fixture)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_fetch_client_analytics_ground_truth())
    finally:
        loop.close()


def get_base_url(**kwargs) -> str:
    """Build URL with query parameters."""
    params = {"from_date": TEST_FROM_DATE.isoformat()}
    params.update(kwargs)

    query_parts = []
    for key, value in params.items():
        if value is not None:
            query_parts.append(f"{key}={value}")

    if query_parts:
        return f"{CLIENT_ANALYTICS_URL}?{'&'.join(query_parts)}"
    return CLIENT_ANALYTICS_URL


def _assert_distribution_matches(actual_distribution, expected_distribution):
    expected_by_name = {item["name"]: item for item in expected_distribution}
    actual_by_name = {item["name"]: item for item in actual_distribution}

    assert set(actual_by_name.keys()) == set(expected_by_name.keys())
    for name, actual_item in actual_by_name.items():
        expected_item = expected_by_name[name]
        assert actual_item["count"] == expected_item["count"], f"Count mismatch for {name}"
        assert actual_item["percent"] == expected_item["percent"], f"Percent mismatch for {name}"


@pytest.mark.usefixtures("seed_test_data")
class TestBasicRequests:
    """Basic request tests for /observability/gateway/client-analytics."""

    def test_basic_request_minimal(self, sync_client):
        """Test minimal request with only from_date."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert "distribution" in data
        assert isinstance(data["distribution"], list)
        print(f"\n[basic_minimal] Got {len(data['distribution'])} items")

    def test_basic_request_with_date_range(self, sync_client):
        """Test request with from_date and to_date."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert "distribution" in data
        print(f"\n[basic_date_range] Got {len(data['distribution'])} items")

    def test_response_structure(self, sync_client):
        """Test that response has all expected fields."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        expected_fields = ["distribution", "total", "group_by"]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"

        if data["distribution"]:
            item = data["distribution"][0]
            expected_item_fields = ["name", "count", "percent"]
            for field in expected_item_fields:
                assert field in item, f"Missing field: {field}"
        print("\n[response_structure] All expected fields present")


class TestGroupByAccuracy:
    """Group-by data accuracy tests comparing API response with ground truth."""

    @pytest.mark.usefixtures("seed_test_data")
    def test_group_by_device_type(self, sync_client, client_analytics_ground_truth):
        """Test group_by=device_type matches database values."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat(), group_by="device_type")
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        expected = client_analytics_ground_truth["device_type"]
        assert data["total"] == expected["total"]
        _assert_distribution_matches(data["distribution"], expected["distribution"])

    @pytest.mark.usefixtures("seed_test_data")
    def test_group_by_browser(self, sync_client, client_analytics_ground_truth):
        """Test group_by=browser matches database values."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat(), group_by="browser")
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        expected = client_analytics_ground_truth["browser"]
        assert data["total"] == expected["total"]
        _assert_distribution_matches(data["distribution"], expected["distribution"])

    @pytest.mark.usefixtures("seed_test_data")
    def test_group_by_os(self, sync_client, client_analytics_ground_truth):
        """Test group_by=os matches database values."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat(), group_by="os")
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        expected = client_analytics_ground_truth["os"]
        assert data["total"] == expected["total"]
        _assert_distribution_matches(data["distribution"], expected["distribution"])

    @pytest.mark.usefixtures("seed_test_data")
    def test_invalid_group_by_falls_back_to_device_type(self, sync_client, client_analytics_ground_truth):
        """Test invalid group_by uses device_type distribution."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat(), group_by="invalid-value")
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        expected = client_analytics_ground_truth["device_type"]
        assert data["total"] == expected["total"]
        _assert_distribution_matches(data["distribution"], expected["distribution"])


class TestFilters:
    """Filter tests."""

    @pytest.mark.usefixtures("seed_test_data")
    def test_filter_by_project_id(self, sync_client, client_analytics_ground_truth):
        """Test filtering by project_id."""
        url = get_base_url(
            to_date=TEST_TO_DATE.isoformat(),
            project_id=str(TEST_PROJECT_ID),
            group_by="device_type",
        )
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        expected = client_analytics_ground_truth["project_device_type"]
        assert data["total"] == expected["total"]
        _assert_distribution_matches(data["distribution"], expected["distribution"])

    @pytest.mark.usefixtures("seed_test_data")
    def test_filter_by_project_id_browser(self, sync_client, client_analytics_ground_truth):
        """Test filtering by project_id with browser grouping."""
        url = get_base_url(
            to_date=TEST_TO_DATE.isoformat(),
            project_id=str(TEST_PROJECT_ID),
            group_by="browser",
        )
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        expected = client_analytics_ground_truth["project_browser"]
        assert data["total"] == expected["total"]
        _assert_distribution_matches(data["distribution"], expected["distribution"])

    @pytest.mark.usefixtures("seed_test_data")
    def test_filter_by_project_id_os(self, sync_client, client_analytics_ground_truth):
        """Test filtering by project_id with OS grouping."""
        url = get_base_url(
            to_date=TEST_TO_DATE.isoformat(),
            project_id=str(TEST_PROJECT_ID),
            group_by="os",
        )
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        expected = client_analytics_ground_truth["project_os"]
        assert data["total"] == expected["total"]
        _assert_distribution_matches(data["distribution"], expected["distribution"])

    @pytest.mark.usefixtures("seed_test_data")
    def test_filter_by_nonexistent_project(self, sync_client):
        """Test filtering by nonexistent project returns no data."""
        url = get_base_url(
            to_date=TEST_TO_DATE.isoformat(),
            project_id=str(TEST_NONEXISTENT_ID),
            group_by="device_type",
        )
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["distribution"] == []


class TestValidation:
    """Validation error tests."""

    def test_missing_from_date_rejected(self, sync_client):
        """Test that missing from_date returns 422."""
        response = sync_client.get(CLIENT_ANALYTICS_URL)
        assert response.status_code == 422, \
            f"Expected 422 for missing from_date, got {response.status_code}"
        print("\n[validation] Missing from_date correctly rejected")

    def test_invalid_date_format_rejected(self, sync_client):
        """Test that invalid date format returns 422."""
        url = f"{CLIENT_ANALYTICS_URL}?from_date=invalid-date"
        response = sync_client.get(url)
        assert response.status_code == 422, \
            f"Expected 422 for invalid date format, got {response.status_code}"
        print("\n[validation] Invalid date format correctly rejected")

    def test_invalid_project_id_rejected(self, sync_client):
        """Test that invalid project_id format returns 422."""
        url = get_base_url(project_id="not-a-uuid")
        response = sync_client.get(url)
        assert response.status_code == 422, \
            f"Expected 422 for invalid project_id, got {response.status_code}"
        print("\n[validation] Invalid project_id correctly rejected")

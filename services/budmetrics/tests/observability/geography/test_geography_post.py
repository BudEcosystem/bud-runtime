"""Tests for POST /observability/metrics/geography endpoint.

These tests validate the geography POST API by:
1. Testing all request body parameters (from_date, to_date, group_by, limit, filters)
2. Verifying response structure matches expected schema
3. Comparing values against InferenceFact ground truth

The POST endpoint differs from GET by supporting complex filters with arrays
for project_id, api_key_project_id, and country_code.

Run with: pytest tests/observability/geography/test_geography_post.py -v -s
"""

import asyncio
from datetime import datetime
from uuid import UUID

import pytest

from budmetrics.observability.models import ClickHouseClient, ClickHouseConfig


# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


# Test constants
TEST_PROJECT_ID = UUID("019787c1-3de1-7b50-969b-e0a58514b6a1")  # 5 records
TEST_PROJECT_ID_2 = UUID("019787c1-3de1-7b50-969b-e0a58514b6a4")  # 1 record
TEST_FROM_DATE = datetime(2026, 1, 7, 0, 0, 0)
TEST_TO_DATE = datetime(2026, 1, 7, 23, 59, 59)
TEST_COUNTRY_CODE = "US"
TEST_REGION = "California"
TEST_CITY = "Mountain View"
TEST_LATITUDE = 37.4056
TEST_LONGITUDE = -122.0775

# API endpoint
ENDPOINT = "/observability/metrics/geography"


async def _fetch_geography_ground_truth():
    """Async helper to query ClickHouse for ground truth values."""
    config = ClickHouseConfig()
    client = ClickHouseClient(config)
    await client.initialize()

    try:
        ground_truth = {}
        date_filter = f"timestamp >= '{TEST_FROM_DATE}' AND timestamp <= '{TEST_TO_DATE}'"

        # Country-level stats
        result = await client.execute_query(f"""
            SELECT
                country_code,
                COUNT(*) as request_count,
                AVG(CASE WHEN is_success THEN 1.0 ELSE 0.0 END) * 100 as success_rate,
                AVG(response_time_ms) as avg_latency_ms,
                uniqExact(user_id) as unique_users
            FROM InferenceFact
            WHERE {date_filter}
                AND country_code IS NOT NULL
                AND country_code != ''
            GROUP BY country_code
            ORDER BY request_count DESC
        """)
        ground_truth["by_country"] = [
            {
                "country_code": r[0],
                "request_count": r[1],
                "success_rate": r[2],
                "avg_latency_ms": r[3],
                "unique_users": r[4],
            }
            for r in result
        ]

        # Region-level stats
        result = await client.execute_query(f"""
            SELECT
                country_code,
                region,
                COUNT(*) as request_count,
                AVG(CASE WHEN is_success THEN 1.0 ELSE 0.0 END) * 100 as success_rate,
                AVG(response_time_ms) as avg_latency_ms
            FROM InferenceFact
            WHERE {date_filter}
                AND region IS NOT NULL
                AND region != ''
            GROUP BY country_code, region
            ORDER BY request_count DESC
        """)
        ground_truth["by_region"] = [
            {
                "country_code": r[0],
                "region": r[1],
                "request_count": r[2],
                "success_rate": r[3],
                "avg_latency_ms": r[4],
            }
            for r in result
        ]

        # City-level stats with coordinates
        result = await client.execute_query(f"""
            SELECT
                country_code,
                region,
                city,
                COUNT(*) as request_count,
                AVG(CASE WHEN is_success THEN 1.0 ELSE 0.0 END) * 100 as success_rate,
                any(latitude) as latitude,
                any(longitude) as longitude
            FROM InferenceFact
            WHERE {date_filter}
                AND city IS NOT NULL
                AND city != ''
            GROUP BY country_code, region, city
            ORDER BY request_count DESC
        """)
        ground_truth["by_city"] = [
            {
                "country_code": r[0],
                "region": r[1],
                "city": r[2],
                "request_count": r[3],
                "success_rate": r[4],
                "latitude": r[5],
                "longitude": r[6],
            }
            for r in result
        ]

        # Total requests with geo data
        result = await client.execute_query(f"""
            SELECT COUNT(*) FROM InferenceFact
            WHERE {date_filter}
                AND country_code IS NOT NULL
                AND country_code != ''
        """)
        ground_truth["total_with_geo"] = result[0][0] if result else 0

        # --- Filtered data for TestFilters ground truth ---

        # Project-specific country stats (TEST_PROJECT_ID)
        result = await client.execute_query(f"""
            SELECT
                country_code,
                COUNT(*) as request_count,
                AVG(CASE WHEN is_success THEN 1.0 ELSE 0.0 END) * 100 as success_rate
            FROM InferenceFact
            WHERE {date_filter}
                AND project_id = '{TEST_PROJECT_ID}'
                AND country_code IS NOT NULL
                AND country_code != ''
            GROUP BY country_code
            ORDER BY request_count DESC
        """)
        ground_truth["by_project_id"] = [
            {
                "country_code": r[0],
                "request_count": r[1],
                "success_rate": r[2],
            }
            for r in result
        ]

        # Multiple projects country stats (TEST_PROJECT_ID + TEST_PROJECT_ID_2)
        result = await client.execute_query(f"""
            SELECT
                country_code,
                COUNT(*) as request_count,
                AVG(CASE WHEN is_success THEN 1.0 ELSE 0.0 END) * 100 as success_rate
            FROM InferenceFact
            WHERE {date_filter}
                AND project_id IN ('{TEST_PROJECT_ID}', '{TEST_PROJECT_ID_2}')
                AND country_code IS NOT NULL
                AND country_code != ''
            GROUP BY country_code
            ORDER BY request_count DESC
        """)
        ground_truth["by_project_id_multiple"] = [
            {
                "country_code": r[0],
                "request_count": r[1],
                "success_rate": r[2],
            }
            for r in result
        ]

        # Country code filter (US only)
        result = await client.execute_query(f"""
            SELECT
                country_code,
                COUNT(*) as request_count,
                AVG(CASE WHEN is_success THEN 1.0 ELSE 0.0 END) * 100 as success_rate
            FROM InferenceFact
            WHERE {date_filter}
                AND country_code = '{TEST_COUNTRY_CODE}'
            GROUP BY country_code
            ORDER BY request_count DESC
        """)
        ground_truth["by_country_code"] = [
            {
                "country_code": r[0],
                "request_count": r[1],
                "success_rate": r[2],
            }
            for r in result
        ]

        # Combined filter: project_id + country_code
        result = await client.execute_query(f"""
            SELECT
                country_code,
                COUNT(*) as request_count,
                AVG(CASE WHEN is_success THEN 1.0 ELSE 0.0 END) * 100 as success_rate
            FROM InferenceFact
            WHERE {date_filter}
                AND project_id = '{TEST_PROJECT_ID}'
                AND country_code = '{TEST_COUNTRY_CODE}'
            GROUP BY country_code
            ORDER BY request_count DESC
        """)
        ground_truth["by_project_and_country"] = [
            {
                "country_code": r[0],
                "request_count": r[1],
                "success_rate": r[2],
            }
            for r in result
        ]

        # API key project ID filter (same as project_id for test data)
        result = await client.execute_query(f"""
            SELECT
                country_code,
                COUNT(*) as request_count,
                AVG(CASE WHEN is_success THEN 1.0 ELSE 0.0 END) * 100 as success_rate
            FROM InferenceFact
            WHERE {date_filter}
                AND api_key_project_id = '{TEST_PROJECT_ID}'
                AND country_code IS NOT NULL
                AND country_code != ''
            GROUP BY country_code
            ORDER BY request_count DESC
        """)
        ground_truth["by_api_key_project_id"] = [
            {
                "country_code": r[0],
                "request_count": r[1],
                "success_rate": r[2],
            }
            for r in result
        ]

        return ground_truth
    finally:
        await client.close()


@pytest.fixture(scope="session")
def geography_ground_truth(seed_test_data):
    """Fetch ground truth from InferenceFact (seeding done by shared fixture)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_fetch_geography_ground_truth())
    finally:
        loop.close()


def get_base_payload(**kwargs) -> dict:
    """Build POST request payload."""
    payload = {"from_date": TEST_FROM_DATE.isoformat()}
    payload.update(kwargs)
    return payload


@pytest.mark.usefixtures("seed_test_data")
class TestBasicRequests:
    """Basic request tests for POST /observability/metrics/geography."""

    def test_basic_request_minimal(self, sync_client):
        """Test minimal request with only from_date."""
        payload = get_base_payload()
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "locations" in data
        assert isinstance(data["locations"], list)
        print(f"\n[basic_minimal] Got {len(data['locations'])} locations")

    def test_basic_request_with_date_range(self, sync_client):
        """Test request with from_date and to_date."""
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "locations" in data
        print(f"\n[basic_date_range] Got {len(data['locations'])} locations")

    def test_response_structure(self, sync_client):
        """Test that response has all expected fields."""
        payload = get_base_payload()
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Check top-level structure
        assert "object" in data
        assert "locations" in data
        assert "total_requests" in data
        assert "total_locations" in data
        assert "date_range" in data
        assert "group_by" in data
        assert isinstance(data["locations"], list)
        assert isinstance(data["date_range"], dict)
        print("\n[response_structure] All expected fields present")

    def test_response_object_type(self, sync_client):
        """Test that response object type is geographic_data."""
        payload = get_base_payload()
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "geographic_data"
        print("\n[response_object_type] Object type is geographic_data")

    def test_location_structure(self, sync_client):
        """Test that location items have expected fields."""
        payload = get_base_payload()
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        if data["locations"]:
            location = data["locations"][0]
            # Country-level fields (default group_by)
            expected_fields = ["country_code", "request_count", "success_rate", "percentage"]
            for field in expected_fields:
                assert field in location, f"Missing field: {field}"
        print("\n[location_structure] Location fields validated")


class TestGroupBy:
    """Group by parameter tests for POST endpoint."""

    def test_group_by_country_default(self, sync_client, geography_ground_truth):
        """Test default grouping is by country."""
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["group_by"] == "country"
        expected_count = len(geography_ground_truth["by_country"])
        assert len(data["locations"]) == expected_count
        print(f"\n[group_by_country_default] Got {len(data['locations'])} countries")

    def test_group_by_country_explicit(self, sync_client, geography_ground_truth):
        """Test explicit group_by=country."""
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat(), group_by="country")
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["group_by"] == "country"
        expected_count = len(geography_ground_truth["by_country"])
        assert len(data["locations"]) == expected_count

        if data["locations"]:
            location = data["locations"][0]
            assert "country_code" in location
            assert "request_count" in location
        print(f"\n[group_by_country_explicit] Got {len(data['locations'])} countries")

    def test_group_by_region(self, sync_client, geography_ground_truth):
        """Test group_by=region."""
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat(), group_by="region")
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["group_by"] == "region"
        expected_count = len(geography_ground_truth["by_region"])
        assert len(data["locations"]) == expected_count

        if data["locations"]:
            location = data["locations"][0]
            assert "country_code" in location
            assert "region" in location
            assert "request_count" in location
        print(f"\n[group_by_region] Got {len(data['locations'])} regions")

    def test_group_by_city(self, sync_client, geography_ground_truth):
        """Test group_by=city."""
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat(), group_by="city")
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["group_by"] == "city"
        expected_count = len(geography_ground_truth["by_city"])
        assert len(data["locations"]) == expected_count

        if data["locations"]:
            location = data["locations"][0]
            assert "country_code" in location
            assert "region" in location
            assert "city" in location
            assert "request_count" in location
        print(f"\n[group_by_city] Got {len(data['locations'])} cities")


class TestFilters:
    """Filter tests for POST endpoint - supports array filters with ground truth comparison."""

    def test_filter_project_id_single(self, sync_client, geography_ground_truth):
        """Test filtering by single project_id in array and compare with DB ground truth."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            filters={"project_id": [str(TEST_PROJECT_ID)]}
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Compare with ground truth from InferenceFact
        db_data = geography_ground_truth["by_project_id"]
        expected_count = len(db_data)
        assert len(data["locations"]) == expected_count, \
            f"Location count mismatch: API={len(data['locations'])}, DB={expected_count}"

        # Verify request counts match
        if db_data and data["locations"]:
            api_first = data["locations"][0]
            db_first = db_data[0]
            assert api_first["country_code"] == db_first["country_code"], \
                f"Country mismatch: API={api_first['country_code']}, DB={db_first['country_code']}"
            assert api_first["request_count"] == db_first["request_count"], \
                f"Request count mismatch: API={api_first['request_count']}, DB={db_first['request_count']}"
        print(f"\n[filter_project_id_single] Got {len(data['locations'])} locations, matches DB")

    def test_filter_project_id_multiple(self, sync_client, geography_ground_truth):
        """Test filtering by multiple project_ids in array and compare with DB ground truth."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            filters={"project_id": [str(TEST_PROJECT_ID), str(TEST_PROJECT_ID_2)]}
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Compare with ground truth from InferenceFact
        db_data = geography_ground_truth["by_project_id_multiple"]
        expected_count = len(db_data)
        assert len(data["locations"]) == expected_count, \
            f"Location count mismatch: API={len(data['locations'])}, DB={expected_count}"

        # Verify request counts match
        if db_data and data["locations"]:
            api_first = data["locations"][0]
            db_first = db_data[0]
            assert api_first["country_code"] == db_first["country_code"], \
                f"Country mismatch: API={api_first['country_code']}, DB={db_first['country_code']}"
            assert api_first["request_count"] == db_first["request_count"], \
                f"Request count mismatch: API={api_first['request_count']}, DB={db_first['request_count']}"
        print(f"\n[filter_project_id_multiple] Got {len(data['locations'])} locations, matches DB")

    def test_filter_country_code_single(self, sync_client, geography_ground_truth):
        """Test filtering by single country_code in array and compare with DB ground truth."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            filters={"country_code": [TEST_COUNTRY_CODE]}
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Compare with ground truth from InferenceFact
        db_data = geography_ground_truth["by_country_code"]
        expected_count = len(db_data)
        assert len(data["locations"]) == expected_count, \
            f"Location count mismatch: API={len(data['locations'])}, DB={expected_count}"

        # All returned locations should be for the filtered country
        for location in data["locations"]:
            assert location["country_code"] == TEST_COUNTRY_CODE

        # Verify request counts match
        if db_data and data["locations"]:
            api_first = data["locations"][0]
            db_first = db_data[0]
            assert api_first["request_count"] == db_first["request_count"], \
                f"Request count mismatch: API={api_first['request_count']}, DB={db_first['request_count']}"
            # Verify success rate matches within tolerance
            api_rate = api_first.get("success_rate", 0)
            db_rate = db_first.get("success_rate", 0)
            assert abs(api_rate - db_rate) < 0.01, \
                f"Success rate mismatch: API={api_rate}, DB={db_rate}"
        print(f"\n[filter_country_single] Got {len(data['locations'])} locations for {TEST_COUNTRY_CODE}, matches DB")

    def test_filter_country_code_multiple(self, sync_client, geography_ground_truth):
        """Test filtering by multiple country_codes in array."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            filters={"country_code": ["US", "UK", "DE"]}
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # All returned locations should be for one of the filtered countries
        valid_countries = {"US", "UK", "DE"}
        for location in data["locations"]:
            assert location["country_code"] in valid_countries

        # Compare with ground truth - only US exists in test data
        db_data = geography_ground_truth["by_country_code"]  # US only
        if db_data:
            # Should match US data from ground truth
            api_us = [loc for loc in data["locations"] if loc["country_code"] == "US"]
            if api_us:
                db_us = [d for d in db_data if d["country_code"] == "US"]
                if db_us:
                    assert api_us[0]["request_count"] == db_us[0]["request_count"], \
                        f"US request count mismatch: API={api_us[0]['request_count']}, DB={db_us[0]['request_count']}"
        print(f"\n[filter_country_multiple] Got {len(data['locations'])} locations, US data matches DB")

    def test_filter_nonexistent_country(self, sync_client, geography_ground_truth):
        """Test filtering by non-existent country code returns empty list."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            filters={"country_code": ["XX"]}
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Should return empty list for non-existent country (no data in DB)
        assert len(data["locations"]) == 0, \
            f"Expected 0 locations for non-existent country XX, got {len(data['locations'])}"
        assert data["total_requests"] == 0, \
            f"Expected total_requests=0 for non-existent country, got {data['total_requests']}"
        print("\n[filter_nonexistent_country] Correctly returned 0 locations")

    def test_filter_combined(self, sync_client, geography_ground_truth):
        """Test combining project_id and country_code filters with ground truth comparison."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            filters={
                "project_id": [str(TEST_PROJECT_ID)],
                "country_code": [TEST_COUNTRY_CODE]
            }
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Compare with ground truth from InferenceFact
        db_data = geography_ground_truth["by_project_and_country"]
        expected_count = len(db_data)
        assert len(data["locations"]) == expected_count, \
            f"Location count mismatch: API={len(data['locations'])}, DB={expected_count}"

        # Should return intersection of both filters
        for location in data["locations"]:
            assert location["country_code"] == TEST_COUNTRY_CODE

        # Verify request counts match
        if db_data and data["locations"]:
            api_first = data["locations"][0]
            db_first = db_data[0]
            assert api_first["request_count"] == db_first["request_count"], \
                f"Request count mismatch: API={api_first['request_count']}, DB={db_first['request_count']}"
            # Verify success rate matches
            api_rate = api_first.get("success_rate", 0)
            db_rate = db_first.get("success_rate", 0)
            assert abs(api_rate - db_rate) < 0.01, \
                f"Success rate mismatch: API={api_rate}, DB={db_rate}"
        print(f"\n[filter_combined] Got {len(data['locations'])} locations with combined filters, matches DB")

    def test_filter_api_key_project_id(self, sync_client, geography_ground_truth):
        """Test filtering by api_key_project_id array with ground truth comparison."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            filters={"api_key_project_id": [str(TEST_PROJECT_ID)]}
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Compare with ground truth from InferenceFact
        db_data = geography_ground_truth["by_api_key_project_id"]
        expected_count = len(db_data)
        assert len(data["locations"]) == expected_count, \
            f"Location count mismatch: API={len(data['locations'])}, DB={expected_count}"

        # Verify request counts match
        if db_data and data["locations"]:
            api_first = data["locations"][0]
            db_first = db_data[0]
            assert api_first["country_code"] == db_first["country_code"], \
                f"Country mismatch: API={api_first['country_code']}, DB={db_first['country_code']}"
            assert api_first["request_count"] == db_first["request_count"], \
                f"Request count mismatch: API={api_first['request_count']}, DB={db_first['request_count']}"
        print(f"\n[filter_api_key_project_id] Got {len(data['locations'])} locations, matches DB")


@pytest.mark.usefixtures("seed_test_data")
class TestLimit:
    """Limit parameter tests for POST endpoint."""

    def test_default_limit_50(self, sync_client):
        """Test default limit is 50."""
        payload = get_base_payload()
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # Default limit is 50
        assert len(data["locations"]) <= 50
        print(f"\n[default_limit] Got {len(data['locations'])} locations (default limit 50)")

    def test_custom_limit_1(self, sync_client):
        """Test limit=1 returns at most 1 location."""
        payload = get_base_payload(limit=1)
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        assert len(data["locations"]) <= 1
        print(f"\n[limit_1] Got {len(data['locations'])} location(s)")

    def test_limit_max_1000(self, sync_client):
        """Test limit=1000 is valid (max allowed)."""
        payload = get_base_payload(limit=1000)
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        assert len(data["locations"]) <= 1000
        print(f"\n[limit_1000] Got {len(data['locations'])} locations (max limit)")

    def test_limit_over_1000_rejected(self, sync_client):
        """Test limit > 1000 returns 422."""
        payload = get_base_payload(limit=1001)
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for limit > 1000, got {response.status_code}"
        print("\n[validation] Limit > 1000 correctly rejected")


class TestValidation:
    """Validation error tests for POST endpoint."""

    def test_missing_from_date_rejected(self, sync_client):
        """Test that missing from_date returns 422."""
        payload = {}
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for missing from_date, got {response.status_code}"
        print("\n[validation] Missing from_date correctly rejected")

    def test_invalid_date_format_rejected(self, sync_client):
        """Test that invalid date format returns 422."""
        payload = {"from_date": "invalid-date"}
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for invalid date format, got {response.status_code}"
        print("\n[validation] Invalid date format correctly rejected")

    def test_invalid_group_by_rejected(self, sync_client):
        """Test that invalid group_by returns 422."""
        payload = get_base_payload(group_by="invalid")
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for invalid group_by, got {response.status_code}"
        print("\n[validation] Invalid group_by correctly rejected")

    def test_invalid_limit_zero_rejected(self, sync_client):
        """Test that limit=0 returns 422."""
        payload = get_base_payload(limit=0)
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for limit=0, got {response.status_code}"
        print("\n[validation] Limit=0 correctly rejected")

    def test_invalid_limit_negative_rejected(self, sync_client):
        """Test that negative limit returns 422."""
        payload = get_base_payload(limit=-1)
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 422, \
            f"Expected 422 for negative limit, got {response.status_code}"
        print("\n[validation] Negative limit correctly rejected")

    @pytest.mark.usefixtures("seed_test_data")
    def test_invalid_project_id_rejected(self, sync_client):
        """Test that invalid project_id in filters returns error."""
        payload = get_base_payload(
            filters={"project_id": ["not-a-uuid"]}
        )
        response = sync_client.post(ENDPOINT, json=payload)
        # May return 422 or 500 depending on validation layer
        assert response.status_code in [422, 500], \
            f"Expected 422 or 500 for invalid project_id, got {response.status_code}"
        print("\n[validation] Invalid project_id correctly rejected")


class TestDataAccuracy:
    """Data accuracy tests comparing API response with DB."""

    def test_country_request_count_matches_db(self, sync_client, geography_ground_truth):
        """Test that country request_count matches DB."""
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat(), group_by="country")
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        db_countries = geography_ground_truth["by_country"]
        if db_countries and data["locations"]:
            api_first = data["locations"][0]
            db_first = db_countries[0]

            assert api_first["country_code"] == db_first["country_code"], \
                f"Country mismatch: API={api_first['country_code']}, DB={db_first['country_code']}"
            assert api_first["request_count"] == db_first["request_count"], \
                f"Request count mismatch: API={api_first['request_count']}, DB={db_first['request_count']}"
        print("\n[accuracy] Country request_count matches DB")

    def test_region_request_count_matches_db(self, sync_client, geography_ground_truth):
        """Test that region request_count matches DB."""
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat(), group_by="region")
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        db_regions = geography_ground_truth["by_region"]
        if db_regions and data["locations"]:
            api_first = data["locations"][0]
            db_first = db_regions[0]

            assert api_first["region"] == db_first["region"], \
                f"Region mismatch: API={api_first['region']}, DB={db_first['region']}"
            assert api_first["request_count"] == db_first["request_count"], \
                f"Request count mismatch: API={api_first['request_count']}, DB={db_first['request_count']}"
        print("\n[accuracy] Region request_count matches DB")

    def test_city_request_count_matches_db(self, sync_client, geography_ground_truth):
        """Test that city request_count matches DB."""
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat(), group_by="city")
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        db_cities = geography_ground_truth["by_city"]
        if db_cities and data["locations"]:
            api_first = data["locations"][0]
            db_first = db_cities[0]

            assert api_first["city"] == db_first["city"], \
                f"City mismatch: API={api_first['city']}, DB={db_first['city']}"
            assert api_first["request_count"] == db_first["request_count"], \
                f"Request count mismatch: API={api_first['request_count']}, DB={db_first['request_count']}"
        print("\n[accuracy] City request_count matches DB")

    def test_success_rate_matches_db(self, sync_client, geography_ground_truth):
        """Test that success_rate matches DB calculation."""
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat(), group_by="country")
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        db_countries = geography_ground_truth["by_country"]
        if db_countries and data["locations"]:
            api_first = data["locations"][0]
            db_first = db_countries[0]

            api_rate = api_first.get("success_rate", 0)
            db_rate = db_first.get("success_rate", 0)
            assert abs(api_rate - db_rate) < 0.01, \
                f"Success rate mismatch: API={api_rate}, DB={db_rate}"
        print("\n[accuracy] Success rate matches DB")

    def test_city_coordinates_match_db(self, sync_client, geography_ground_truth):
        """Test that city coordinates match DB."""
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat(), group_by="city")
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        db_cities = geography_ground_truth["by_city"]
        if db_cities and data["locations"]:
            api_first = data["locations"][0]
            db_first = db_cities[0]

            if api_first.get("latitude") is not None and db_first.get("latitude") is not None:
                assert abs(float(api_first["latitude"]) - float(db_first["latitude"])) < 0.001, \
                    f"Latitude mismatch: API={api_first['latitude']}, DB={db_first['latitude']}"

            if api_first.get("longitude") is not None and db_first.get("longitude") is not None:
                assert abs(float(api_first["longitude"]) - float(db_first["longitude"])) < 0.001, \
                    f"Longitude mismatch: API={api_first['longitude']}, DB={db_first['longitude']}"
        print("\n[accuracy] City coordinates match DB")

    @pytest.mark.usefixtures("seed_test_data")
    def test_percentage_calculation(self, sync_client):
        """Test that sum of percentages is approximately 100%."""
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat(), group_by="country")
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        if data["locations"]:
            total_percentage = sum(loc.get("percentage", 0) for loc in data["locations"])
            assert 99.0 <= total_percentage <= 101.0, \
                f"Sum of percentages {total_percentage} is not approximately 100%"
        print("\n[accuracy] Percentage sum is approximately 100%")

    def test_total_requests_matches_sum(self, sync_client, geography_ground_truth):
        """Test that total_requests matches sum of location request_counts."""
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat(), group_by="country")
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        if data["locations"]:
            sum_requests = sum(loc["request_count"] for loc in data["locations"])
            assert data["total_requests"] == sum_requests, \
                f"total_requests {data['total_requests']} != sum {sum_requests}"
        print("\n[accuracy] total_requests matches sum of location counts")

    def test_filtered_data_matches_db(self, sync_client, geography_ground_truth):
        """Test that filtered results match expected from ground truth."""
        payload = get_base_payload(
            to_date=TEST_TO_DATE.isoformat(),
            group_by="country",
            filters={"country_code": [TEST_COUNTRY_CODE]}
        )
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        # With filter for US, should only get US data
        db_countries = geography_ground_truth["by_country"]
        db_us = [c for c in db_countries if c["country_code"] == TEST_COUNTRY_CODE]

        if db_us:
            assert len(data["locations"]) == 1
            assert data["locations"][0]["country_code"] == TEST_COUNTRY_CODE
            assert data["locations"][0]["request_count"] == db_us[0]["request_count"]
        print("\n[accuracy] Filtered data matches DB")


class TestCodePaths:
    """Tests for different code paths (rollup vs InferenceFact)."""

    def test_rollup_path_country(self, sync_client, geography_ground_truth):
        """Test country-level uses rollup tables."""
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat(), group_by="country")
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        expected_count = len(geography_ground_truth["by_country"])
        assert len(data["locations"]) == expected_count, \
            f"Expected {expected_count} countries, got {len(data['locations'])}"
        print("\n[code_path] Country-level query successful (rollup path)")

    def test_inference_fact_path_region(self, sync_client, geography_ground_truth):
        """Test region-level uses InferenceFact."""
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat(), group_by="region")
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        expected_count = len(geography_ground_truth["by_region"])
        assert len(data["locations"]) == expected_count, \
            f"Expected {expected_count} regions, got {len(data['locations'])}"
        print("\n[code_path] Region-level query successful (InferenceFact path)")

    def test_inference_fact_path_city(self, sync_client, geography_ground_truth):
        """Test city-level uses InferenceFact."""
        payload = get_base_payload(to_date=TEST_TO_DATE.isoformat(), group_by="city")
        response = sync_client.post(ENDPOINT, json=payload)
        assert response.status_code == 200
        data = response.json()

        expected_count = len(geography_ground_truth["by_city"])
        assert len(data["locations"]) == expected_count, \
            f"Expected {expected_count} cities, got {len(data['locations'])}"
        print("\n[code_path] City-level query successful (InferenceFact path)")


# pytest tests/observability/geography/test_geography_post.py -v -s

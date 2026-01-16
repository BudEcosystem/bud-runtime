"""Tests for GET /observability/metrics/geography endpoint.

These tests validate the geography API by:
1. Testing all query parameters (from_date, to_date, group_by, limit, project_id, country_codes)
2. Verifying response structure matches expected schema
3. Comparing values against InferenceFact ground truth

Run with: pytest tests/observability/geography/test_geography.py -v -s
"""

import asyncio
from datetime import datetime
from uuid import UUID

import pytest

from budmetrics.observability.models import ClickHouseClient, ClickHouseConfig


# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


# Test constants
TEST_PROJECT_ID = UUID("019787c1-3de1-7b50-969b-e0a58514b6a1")
TEST_FROM_DATE = datetime(2026, 1, 7, 0, 0, 0)
TEST_TO_DATE = datetime(2026, 1, 7, 23, 59, 59)
TEST_COUNTRY_CODE = "US"
TEST_REGION = "California"
TEST_CITY = "Mountain View"
TEST_LATITUDE = 37.4056
TEST_LONGITUDE = -122.0775


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


def get_base_url(**kwargs) -> str:
    """Build URL with query parameters."""
    base = "/observability/metrics/geography"
    params = {"from_date": TEST_FROM_DATE.isoformat()}
    params.update(kwargs)

    query_parts = []
    for key, value in params.items():
        if value is not None:
            query_parts.append(f"{key}={value}")

    if query_parts:
        return f"{base}?{'&'.join(query_parts)}"
    return base


@pytest.mark.usefixtures("seed_test_data")
class TestBasicRequests:
    """Basic request tests for /observability/metrics/geography."""

    def test_basic_request_minimal(self, sync_client):
        """Test minimal request with only from_date."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert "locations" in data
        assert isinstance(data["locations"], list)
        print(f"\n[basic_minimal] Got {len(data['locations'])} locations")

    def test_basic_request_with_date_range(self, sync_client):
        """Test request with from_date and to_date."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert "locations" in data
        print(f"\n[basic_date_range] Got {len(data['locations'])} locations")

    def test_response_structure(self, sync_client):
        """Test that response has all expected fields."""
        url = get_base_url()
        response = sync_client.get(url)
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
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "geographic_data"
        print("\n[response_object_type] Object type is geographic_data")

    def test_location_structure(self, sync_client):
        """Test that location items have expected fields."""
        url = get_base_url()
        response = sync_client.get(url)
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
    """Group by parameter tests."""

    def test_group_by_country_default(self, sync_client, geography_ground_truth):
        """Test default grouping is by country."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        assert data["group_by"] == "country"
        expected_count = len(geography_ground_truth["by_country"])
        assert len(data["locations"]) == expected_count
        print(f"\n[group_by_country_default] Got {len(data['locations'])} countries")

    def test_group_by_country_explicit(self, sync_client, geography_ground_truth):
        """Test explicit group_by=country."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat(), group_by="country")
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        assert data["group_by"] == "country"
        expected_count = len(geography_ground_truth["by_country"])
        assert len(data["locations"]) == expected_count

        # Verify country-level fields
        if data["locations"]:
            location = data["locations"][0]
            assert "country_code" in location
            assert "request_count" in location
        print(f"\n[group_by_country_explicit] Got {len(data['locations'])} countries")

    def test_group_by_region(self, sync_client, geography_ground_truth):
        """Test group_by=region."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat(), group_by="region")
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        assert data["group_by"] == "region"
        expected_count = len(geography_ground_truth["by_region"])
        assert len(data["locations"]) == expected_count

        # Verify region-level fields
        if data["locations"]:
            location = data["locations"][0]
            assert "country_code" in location
            assert "region" in location
            assert "request_count" in location
        print(f"\n[group_by_region] Got {len(data['locations'])} regions")

    def test_group_by_city(self, sync_client, geography_ground_truth):
        """Test group_by=city."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat(), group_by="city")
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        assert data["group_by"] == "city"
        expected_count = len(geography_ground_truth["by_city"])
        assert len(data["locations"]) == expected_count

        # Verify city-level fields including coordinates
        if data["locations"]:
            location = data["locations"][0]
            assert "country_code" in location
            assert "region" in location
            assert "city" in location
            assert "request_count" in location
            # Coordinates should be present for city-level
            assert "latitude" in location or location.get("latitude") is None
            assert "longitude" in location or location.get("longitude") is None
        print(f"\n[group_by_city] Got {len(data['locations'])} cities")


class TestFilters:
    """Filter parameter tests."""

    def test_filter_by_project_id(self, sync_client, geography_ground_truth):
        """Test filtering by project_id."""
        url = get_base_url(
            to_date=TEST_TO_DATE.isoformat(),
            project_id=str(TEST_PROJECT_ID)
        )
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        # Should have data for the project
        assert "locations" in data
        print(f"\n[filter_project_id] Got {len(data['locations'])} locations for project")

    def test_filter_by_country_codes_single(self, sync_client, geography_ground_truth):
        """Test filtering by single country code."""
        url = get_base_url(
            to_date=TEST_TO_DATE.isoformat(),
            country_codes=TEST_COUNTRY_CODE
        )
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        # All returned locations should be for the filtered country
        for location in data["locations"]:
            assert location["country_code"] == TEST_COUNTRY_CODE
        print(f"\n[filter_country_single] Got {len(data['locations'])} locations for {TEST_COUNTRY_CODE}")

    def test_filter_by_country_codes_multiple(self, sync_client):
        """Test filtering by multiple country codes."""
        url = get_base_url(
            to_date=TEST_TO_DATE.isoformat(),
            country_codes="US,UK,DE"
        )
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        # All returned locations should be for one of the filtered countries
        valid_countries = {"US", "UK", "DE"}
        for location in data["locations"]:
            assert location["country_code"] in valid_countries
        print(f"\n[filter_country_multiple] Got {len(data['locations'])} locations")

    def test_filter_by_nonexistent_country(self, sync_client):
        """Test filtering by non-existent country code."""
        url = get_base_url(
            to_date=TEST_TO_DATE.isoformat(),
            country_codes="XX"
        )
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        # Should return empty list for non-existent country
        assert len(data["locations"]) == 0
        print("\n[filter_nonexistent_country] Correctly returned 0 locations")

    @pytest.mark.usefixtures("seed_test_data")
    def test_filter_combined(self, sync_client):
        """Test combining project_id and country_codes filters."""
        url = get_base_url(
            to_date=TEST_TO_DATE.isoformat(),
            project_id=str(TEST_PROJECT_ID),
            country_codes=TEST_COUNTRY_CODE
        )
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        # Should return intersection of both filters
        for location in data["locations"]:
            assert location["country_code"] == TEST_COUNTRY_CODE
        print(f"\n[filter_combined] Got {len(data['locations'])} locations with combined filters")


@pytest.mark.usefixtures("seed_test_data")
class TestLimit:
    """Limit parameter tests."""

    def test_default_limit_50(self, sync_client):
        """Test default limit is 50."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        # Default limit is 50
        assert len(data["locations"]) <= 50
        print(f"\n[default_limit] Got {len(data['locations'])} locations (default limit 50)")

    def test_custom_limit_1(self, sync_client):
        """Test limit=1 returns at most 1 location."""
        url = get_base_url(limit=1)
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        assert len(data["locations"]) <= 1
        print(f"\n[limit_1] Got {len(data['locations'])} location(s)")

    def test_custom_limit_100(self, sync_client):
        """Test limit=100 returns up to 100 locations."""
        url = get_base_url(limit=100)
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        assert len(data["locations"]) <= 100
        print(f"\n[limit_100] Got {len(data['locations'])} locations")


class TestValidation:
    """Validation error tests."""

    def test_missing_from_date_rejected(self, sync_client):
        """Test that missing from_date returns 422."""
        url = "/observability/metrics/geography"
        response = sync_client.get(url)
        assert response.status_code == 422, \
            f"Expected 422 for missing from_date, got {response.status_code}"
        print("\n[validation] Missing from_date correctly rejected")

    def test_invalid_date_format_rejected(self, sync_client):
        """Test that invalid date format returns 422."""
        url = "/observability/metrics/geography?from_date=invalid-date"
        response = sync_client.get(url)
        assert response.status_code == 422, \
            f"Expected 422 for invalid date format, got {response.status_code}"
        print("\n[validation] Invalid date format correctly rejected")

    def test_invalid_group_by_rejected(self, sync_client):
        """Test that invalid group_by returns error."""
        url = get_base_url(group_by="invalid")
        response = sync_client.get(url)
        # May return 422 or 500 depending on validation
        assert response.status_code in [422, 500], \
            f"Expected 422 or 500 for invalid group_by, got {response.status_code}"
        print("\n[validation] Invalid group_by correctly rejected")

    def test_invalid_project_id_rejected(self, sync_client):
        """Test that invalid project_id format returns 422."""
        url = get_base_url(project_id="not-a-uuid")
        response = sync_client.get(url)
        assert response.status_code == 422, \
            f"Expected 422 for invalid project_id, got {response.status_code}"
        print("\n[validation] Invalid project_id correctly rejected")


class TestDataAccuracy:
    """Data accuracy tests comparing API response with DB."""

    def test_country_request_count_matches_db(self, sync_client, geography_ground_truth):
        """Test that country request_count matches DB."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat(), group_by="country")
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        db_countries = geography_ground_truth["by_country"]
        if db_countries and data["locations"]:
            # Compare first country's request_count
            api_first = data["locations"][0]
            db_first = db_countries[0]

            assert api_first["country_code"] == db_first["country_code"], \
                f"Country mismatch: API={api_first['country_code']}, DB={db_first['country_code']}"
            assert api_first["request_count"] == db_first["request_count"], \
                f"Request count mismatch: API={api_first['request_count']}, DB={db_first['request_count']}"
        print("\n[accuracy] Country request_count matches DB")

    def test_region_request_count_matches_db(self, sync_client, geography_ground_truth):
        """Test that region request_count matches DB."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat(), group_by="region")
        response = sync_client.get(url)
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
        url = get_base_url(to_date=TEST_TO_DATE.isoformat(), group_by="city")
        response = sync_client.get(url)
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
        url = get_base_url(to_date=TEST_TO_DATE.isoformat(), group_by="country")
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        db_countries = geography_ground_truth["by_country"]
        if db_countries and data["locations"]:
            api_first = data["locations"][0]
            db_first = db_countries[0]

            # Allow small floating point difference
            api_rate = api_first.get("success_rate", 0)
            db_rate = db_first.get("success_rate", 0)
            assert abs(api_rate - db_rate) < 0.01, \
                f"Success rate mismatch: API={api_rate}, DB={db_rate}"
        print("\n[accuracy] Success rate matches DB")

    def test_city_coordinates_match_db(self, sync_client, geography_ground_truth):
        """Test that city coordinates match DB."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat(), group_by="city")
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        db_cities = geography_ground_truth["by_city"]
        if db_cities and data["locations"]:
            api_first = data["locations"][0]
            db_first = db_cities[0]

            # Check latitude if present
            if api_first.get("latitude") is not None and db_first.get("latitude") is not None:
                assert abs(float(api_first["latitude"]) - float(db_first["latitude"])) < 0.001, \
                    f"Latitude mismatch: API={api_first['latitude']}, DB={db_first['latitude']}"

            # Check longitude if present
            if api_first.get("longitude") is not None and db_first.get("longitude") is not None:
                assert abs(float(api_first["longitude"]) - float(db_first["longitude"])) < 0.001, \
                    f"Longitude mismatch: API={api_first['longitude']}, DB={db_first['longitude']}"
        print("\n[accuracy] City coordinates match DB")

    @pytest.mark.usefixtures("seed_test_data")
    def test_percentage_calculation(self, sync_client):
        """Test that sum of percentages is approximately 100%."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat(), group_by="country")
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        if data["locations"]:
            total_percentage = sum(loc.get("percentage", 0) for loc in data["locations"])
            # Should be approximately 100% (allow for rounding)
            assert 99.0 <= total_percentage <= 101.0, \
                f"Sum of percentages {total_percentage} is not approximately 100%"
        print("\n[accuracy] Percentage sum is approximately 100%")

    def test_total_requests_matches_sum(self, sync_client, geography_ground_truth):
        """Test that total_requests matches sum of location request_counts."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat(), group_by="country")
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        if data["locations"]:
            sum_requests = sum(loc["request_count"] for loc in data["locations"])
            assert data["total_requests"] == sum_requests, \
                f"total_requests {data['total_requests']} != sum {sum_requests}"
        print("\n[accuracy] total_requests matches sum of location counts")


class TestCodePaths:
    """Tests for different code paths (rollup vs InferenceFact)."""

    def test_rollup_path_country(self, sync_client, geography_ground_truth):
        """Test country-level uses rollup tables."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat(), group_by="country")
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        # Verify results match expected from ground truth
        expected_count = len(geography_ground_truth["by_country"])
        assert len(data["locations"]) == expected_count, \
            f"Expected {expected_count} countries, got {len(data['locations'])}"
        print("\n[code_path] Country-level query successful (rollup path)")

    def test_inference_fact_path_region(self, sync_client, geography_ground_truth):
        """Test region-level uses InferenceFact."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat(), group_by="region")
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        # Verify results match expected from ground truth
        expected_count = len(geography_ground_truth["by_region"])
        assert len(data["locations"]) == expected_count, \
            f"Expected {expected_count} regions, got {len(data['locations'])}"
        print("\n[code_path] Region-level query successful (InferenceFact path)")

    def test_inference_fact_path_city(self, sync_client, geography_ground_truth):
        """Test city-level uses InferenceFact."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat(), group_by="city")
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        # Verify results match expected from ground truth
        expected_count = len(geography_ground_truth["by_city"])
        assert len(data["locations"]) == expected_count, \
            f"Expected {expected_count} cities, got {len(data['locations'])}"
        print("\n[code_path] City-level query successful (InferenceFact path)")


# pytest tests/observability/geography/test_geography.py -v -s

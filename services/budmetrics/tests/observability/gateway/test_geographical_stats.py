"""Tests for GET /observability/gateway/geographical-stats endpoint.

These tests validate the gateway geographical stats API by:
1. Testing all query parameters (from_date, to_date, project_id)
2. Verifying response structure matches expected schema
3. Comparing values against InferenceFact ground truth

Ground Truth Data:
- Only data_6 has geo data: country_code="US", city="Mountain View"
- data_1 through data_5 have NULL geo fields

Run with: pytest tests/observability/gateway/test_geographical_stats.py -v -s
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
TEST_NONEXISTENT_ID = UUID("00000000-0000-0000-0000-000000000000")

# Expected geo data from data_6 seeder
EXPECTED_COUNTRY_CODE = "US"
EXPECTED_CITY = "Mountain View"
EXPECTED_LATITUDE = 37.4056
EXPECTED_LONGITUDE = -122.0775

# API URL
GEO_STATS_URL = "/observability/gateway/geographical-stats"


async def _fetch_geo_ground_truth():
    """Async helper to query ClickHouse for geographical ground truth values.

    Note: The API includes ALL country_codes (including NULL) in the response,
    so our ground truth matches that behavior.
    """
    config = ClickHouseConfig()
    client = ClickHouseClient(config)
    await client.initialize()

    try:
        ground_truth = {}
        date_filter = f"timestamp >= '{TEST_FROM_DATE}' AND timestamp <= '{TEST_TO_DATE}'"

        # 1. Country stats (including NULL country_code - matches API behavior)
        result = await client.execute_query(f"""
            SELECT
                country_code,
                count(*) as count
            FROM InferenceFact
            WHERE {date_filter}
            GROUP BY country_code
            ORDER BY count DESC
        """)
        ground_truth["countries"] = [
            {"country_code": r[0], "count": r[1]}
            for r in result
        ] if result else []
        ground_truth["unique_countries"] = len(ground_truth["countries"])

        # 2. City stats (only non-null city - API filters these)
        result = await client.execute_query(f"""
            SELECT
                city,
                country_code,
                count(*) as count,
                any(latitude) as latitude,
                any(longitude) as longitude
            FROM InferenceFact
            WHERE {date_filter}
                AND city IS NOT NULL
            GROUP BY city, country_code
            ORDER BY count DESC
        """)
        ground_truth["cities"] = [
            {
                "city": r[0],
                "country_code": r[1],
                "count": r[2],
                "latitude": float(r[3]) if r[3] else None,
                "longitude": float(r[4]) if r[4] else None,
            }
            for r in result
        ] if result else []
        ground_truth["unique_cities"] = len(ground_truth["cities"])

        # 3. Total requests (sum of all country counts - matches API total_requests)
        ground_truth["total_requests"] = sum(c["count"] for c in ground_truth["countries"])

        # 4. Project-specific counts (non-null country_code only for geo filtering)
        result = await client.execute_query(f"""
            SELECT count(*) as count
            FROM InferenceFact
            WHERE {date_filter}
                AND project_id = '{TEST_PROJECT_ID}'
                AND country_code IS NOT NULL
        """)
        ground_truth["project_geo_count"] = result[0][0] if result else 0

        return ground_truth
    finally:
        await client.close()


@pytest.fixture(scope="session")
def geo_ground_truth(seed_test_data):
    """Fetch ground truth from InferenceFact (seeding done by shared fixture)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_fetch_geo_ground_truth())
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
        return f"{GEO_STATS_URL}?{'&'.join(query_parts)}"
    return GEO_STATS_URL


@pytest.mark.usefixtures("seed_test_data")
class TestBasicRequests:
    """Basic request tests for /observability/gateway/geographical-stats."""

    def test_basic_request_returns_200(self, sync_client):
        """Test minimal request with only from_date returns 200."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"\n[basic] Status: {response.status_code}")

    def test_basic_request_with_date_range(self, sync_client):
        """Test request with from_date and to_date returns 200."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert "countries" in data
        print(f"\n[date_range] Status: 200, countries: {len(data.get('countries', []))}")

    def test_response_structure(self, sync_client):
        """Test that response has all expected fields."""
        url = get_base_url()
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        # Check top-level structure
        expected_fields = ["object", "total_requests", "unique_countries", "unique_cities", "countries", "cities"]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"

        assert data["object"] == "gateway_geographical_stats"
        assert isinstance(data["countries"], list)
        assert isinstance(data["cities"], list)
        print("\n[structure] All expected fields present")


class TestDataAccuracy:
    """Data accuracy tests comparing API response with ground truth."""

    def test_total_requests_matches_db(self, sync_client, geo_ground_truth):
        """Test that total_requests matches database count."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        expected = geo_ground_truth["total_requests"]
        actual = data["total_requests"]
        assert actual == expected, f"total_requests mismatch: API={actual}, DB={expected}"
        print(f"\n[accuracy] total_requests: API={actual}, DB={expected}")

    def test_unique_countries_matches_db(self, sync_client, geo_ground_truth):
        """Test that unique_countries matches database count."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        expected = geo_ground_truth["unique_countries"]
        actual = data["unique_countries"]
        assert actual == expected, f"unique_countries mismatch: API={actual}, DB={expected}"
        print(f"\n[accuracy] unique_countries: API={actual}, DB={expected}")

    def test_unique_cities_matches_db(self, sync_client, geo_ground_truth):
        """Test that unique_cities matches database count."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        expected = geo_ground_truth["unique_cities"]
        actual = data["unique_cities"]
        assert actual == expected, f"unique_cities mismatch: API={actual}, DB={expected}"
        print(f"\n[accuracy] unique_cities: API={actual}, DB={expected}")

    def test_country_code_matches_db(self, sync_client, geo_ground_truth):
        """Test that country codes match database."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        if geo_ground_truth["countries"]:
            expected_codes = {c["country_code"] for c in geo_ground_truth["countries"]}
            actual_codes = {c["country_code"] for c in data["countries"]}
            assert actual_codes == expected_codes, f"Country codes mismatch: API={actual_codes}, DB={expected_codes}"

            # Verify expected US from data_6
            assert EXPECTED_COUNTRY_CODE in actual_codes, f"Expected {EXPECTED_COUNTRY_CODE} in countries"
        print(f"\n[accuracy] country_codes match DB")

    def test_city_name_matches_db(self, sync_client, geo_ground_truth):
        """Test that city names match database."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        if geo_ground_truth["cities"]:
            expected_cities = {c["city"] for c in geo_ground_truth["cities"]}
            actual_cities = {c["city"] for c in data["cities"]}
            assert actual_cities == expected_cities, f"Cities mismatch: API={actual_cities}, DB={expected_cities}"

            # Verify expected Mountain View from data_6
            assert EXPECTED_CITY in actual_cities, f"Expected {EXPECTED_CITY} in cities"
        print(f"\n[accuracy] city names match DB")

    def test_city_coordinates_match_db(self, sync_client, geo_ground_truth):
        """Test that city coordinates match database."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        if data["cities"]:
            # Find Mountain View city
            mv_city = next((c for c in data["cities"] if c["city"] == EXPECTED_CITY), None)
            if mv_city:
                lat = mv_city.get("latitude")
                lng = mv_city.get("longitude")
                if lat is not None:
                    assert abs(lat - EXPECTED_LATITUDE) < 0.01, f"Latitude mismatch: {lat} vs {EXPECTED_LATITUDE}"
                if lng is not None:
                    assert abs(lng - EXPECTED_LONGITUDE) < 0.01, f"Longitude mismatch: {lng} vs {EXPECTED_LONGITUDE}"
                print(f"\n[accuracy] coordinates: lat={lat}, lng={lng}")
            else:
                print(f"\n[accuracy] {EXPECTED_CITY} not found in response")
        else:
            print("\n[accuracy] No cities in response")

    def test_country_count_matches_db(self, sync_client, geo_ground_truth):
        """Test that per-country counts match database."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        if geo_ground_truth["countries"] and data["countries"]:
            # Build lookup
            db_counts = {c["country_code"]: c["count"] for c in geo_ground_truth["countries"]}
            api_counts = {c["country_code"]: c["count"] for c in data["countries"]}

            for code, expected_count in db_counts.items():
                actual_count = api_counts.get(code, 0)
                assert actual_count == expected_count, \
                    f"Count mismatch for {code}: API={actual_count}, DB={expected_count}"
        print("\n[accuracy] per-country counts match DB")


class TestFilters:
    """Filter tests."""

    def test_filter_by_project_id(self, sync_client, geo_ground_truth):
        """Test filtering by project_id."""
        url = get_base_url(
            to_date=TEST_TO_DATE.isoformat(),
            project_id=str(TEST_PROJECT_ID)
        )
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        # Should have data since data_6 uses TEST_PROJECT_ID
        expected_count = geo_ground_truth["project_geo_count"]
        if expected_count > 0:
            assert data["total_requests"] > 0, "Expected data for project filter"
        print(f"\n[filter] project_id filter: total_requests={data['total_requests']}")

    def test_filter_nonexistent_project_returns_empty(self, sync_client):
        """Test that non-existent project_id returns empty results."""
        url = get_base_url(
            to_date=TEST_TO_DATE.isoformat(),
            project_id=str(TEST_NONEXISTENT_ID)
        )
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        assert data["total_requests"] == 0, f"Expected 0 requests, got {data['total_requests']}"
        assert data["unique_countries"] == 0
        assert data["unique_cities"] == 0
        assert data["countries"] == []
        assert data["cities"] == []
        print("\n[filter] non-existent project returns empty")


class TestEdgeCases:
    """Edge case tests."""

    def test_future_date_returns_empty(self, sync_client):
        """Test that future date range returns empty results."""
        future_date = datetime(2030, 1, 1, 0, 0, 0)
        url = get_base_url(from_date=future_date.isoformat())
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        assert data["total_requests"] == 0
        assert data["countries"] == []
        assert data["cities"] == []
        print("\n[edge] future date returns empty")

    def test_percent_values_sum_to_100(self, sync_client, geo_ground_truth):
        """Test that percent values sum to approximately 100."""
        url = get_base_url(to_date=TEST_TO_DATE.isoformat())
        response = sync_client.get(url)
        assert response.status_code == 200
        data = response.json()

        if data["countries"]:
            total_percent = sum(c.get("percent", 0) for c in data["countries"])
            # Allow some floating point tolerance
            assert abs(total_percent - 100.0) < 0.1, f"Country percents sum to {total_percent}, not 100"
            print(f"\n[edge] country percents sum to {total_percent}")
        else:
            print("\n[edge] no countries to check percent sum")


class TestValidation:
    """Validation error tests."""

    def test_missing_from_date_rejected(self, sync_client):
        """Test that missing from_date returns 422."""
        response = sync_client.get(GEO_STATS_URL)
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("\n[validation] Missing from_date correctly rejected")

    def test_invalid_date_format_rejected(self, sync_client):
        """Test that invalid date format returns 422."""
        url = f"{GEO_STATS_URL}?from_date=invalid-date"
        response = sync_client.get(url)
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("\n[validation] Invalid date format correctly rejected")

    def test_invalid_project_id_rejected(self, sync_client):
        """Test that invalid project_id format returns 422."""
        url = get_base_url(project_id="not-a-uuid")
        response = sync_client.get(url)
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("\n[validation] Invalid project_id correctly rejected")

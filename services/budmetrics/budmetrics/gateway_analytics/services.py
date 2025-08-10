"""Gateway Analytics Services for budmetrics service."""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from budmetrics.gateway_analytics.models import GatewayAnalyticsQueryBuilder, get_clickhouse_client
from budmetrics.gateway_analytics.schemas import (
    GatewayAnalyticsRequest,
    GatewayAnalyticsResponse,
    GatewayBlockingRuleStats,
    GatewayCountMetric,
    GatewayGeographicalStats,
    GatewayMetricsData,
    GatewayPerformanceMetric,
    GatewayPeriodBin,
    GatewayRateMetric,
)


class GatewayAnalyticsService:
    """Service for handling gateway analytics operations."""

    def __init__(self):
        """Initialize the Gateway Analytics Service."""
        self.query_builder = GatewayAnalyticsQueryBuilder()

    async def get_gateway_metrics(self, request: GatewayAnalyticsRequest) -> GatewayAnalyticsResponse:
        """Get gateway analytics metrics based on request parameters."""
        async with get_clickhouse_client() as client:
            # Build and execute query
            query = self.query_builder.build_query(request)
            result = await client.query(query)

            # Process results into response format
            items = await self._process_metrics_results(result, request)

            # Calculate summary statistics if requested
            summary = None
            if len(items) > 0:
                summary = self._calculate_summary_stats(items, request)

            return GatewayAnalyticsResponse(object="gateway_analytics", code=200, items=items, summary=summary)

    async def get_geographical_stats(
        self, from_date: datetime, to_date: Optional[datetime], project_id: Optional[UUID]
    ) -> GatewayGeographicalStats:
        """Get geographical distribution statistics."""
        async with get_clickhouse_client() as client:
            # Build queries for country and city stats
            country_query = self._build_geographical_query(from_date, to_date, project_id, "country")
            city_query = self._build_geographical_query(from_date, to_date, project_id, "city")

            # Execute queries in parallel
            country_result, city_result = await asyncio.gather(client.query(country_query), client.query(city_query))

            # Process results
            total_requests = sum(row["count"] for row in country_result.rows)

            countries = [
                {
                    "country_code": row["country_code"],
                    "count": row["count"],
                    "percent": round((row["count"] / total_requests) * 100, 2) if total_requests > 0 else 0,
                }
                for row in country_result.rows
            ]

            cities = [
                {
                    "city": row["city"],
                    "country_code": row["country_code"],
                    "count": row["count"],
                    "percent": round((row["count"] / total_requests) * 100, 2) if total_requests > 0 else 0,
                    "latitude": row.get("latitude"),
                    "longitude": row.get("longitude"),
                }
                for row in city_result.rows
                if row["city"] is not None
            ]

            # Create heatmap data for visualization
            heatmap_data = [
                {
                    "lat": city["latitude"],
                    "lng": city["longitude"],
                    "count": city["count"],
                    "city": city["city"],
                    "country_code": city["country_code"],
                }
                for city in cities
                if city.get("latitude") and city.get("longitude")
            ]

            return GatewayGeographicalStats(
                total_requests=total_requests,
                unique_countries=len(countries),
                unique_cities=len(cities),
                countries=countries[:50],  # Top 50 countries
                cities=cities[:100],  # Top 100 cities
                heatmap_data=heatmap_data[:1000] if heatmap_data else None,
            )

    async def get_blocking_stats(
        self, from_date: datetime, to_date: Optional[datetime], project_id: Optional[UUID]
    ) -> GatewayBlockingRuleStats:
        """Get blocking rule statistics."""
        async with get_clickhouse_client() as client:
            # Build queries
            blocking_query = self._build_blocking_stats_query(from_date, to_date, project_id)
            time_series_query = self._build_blocking_time_series_query(from_date, to_date, project_id)

            # Execute queries
            blocking_result, time_series_result = await asyncio.gather(
                client.query(blocking_query), client.query(time_series_query)
            )

            # Process results
            if blocking_result.rows:
                stats = blocking_result.rows[0]
                total_blocked = stats["total_blocked"]
                total_requests = stats["total_requests"]
                block_rate = (total_blocked / total_requests * 100) if total_requests > 0 else 0

                # Parse JSON fields
                blocked_by_rule = stats.get("blocked_by_rule", {})
                blocked_by_reason = stats.get("blocked_by_reason", {})
                top_blocked_ips = stats.get("top_blocked_ips", [])
            else:
                total_blocked = 0
                block_rate = 0.0
                blocked_by_rule = {}
                blocked_by_reason = {}
                top_blocked_ips = []

            # Process time series
            time_series = [
                {
                    "timestamp": row["timestamp"],
                    "blocked_count": row["blocked_count"],
                    "total_count": row["total_count"],
                    "block_rate": round((row["blocked_count"] / row["total_count"] * 100), 2)
                    if row["total_count"] > 0
                    else 0,
                }
                for row in time_series_result.rows
            ]

            return GatewayBlockingRuleStats(
                total_blocked=total_blocked,
                block_rate=round(block_rate, 2),
                blocked_by_rule=blocked_by_rule,
                blocked_by_reason=blocked_by_reason,
                top_blocked_ips=top_blocked_ips,
                time_series=time_series,
            )

    async def get_top_routes(
        self, from_date: datetime, to_date: Optional[datetime], limit: int, project_id: Optional[UUID]
    ) -> Dict[str, Any]:
        """Get top API routes by request count."""
        async with get_clickhouse_client() as client:
            query = self._build_top_routes_query(from_date, to_date, limit, project_id)
            result = await client.query(query)

            routes = [
                {
                    "path": row["path"],
                    "method": row["method"],
                    "request_count": row["request_count"],
                    "avg_response_time_ms": round(row["avg_response_time"], 2),
                    "p99_response_time_ms": round(row["p99_response_time"], 2),
                    "error_rate": round(row["error_rate"], 2),
                    "success_rate": round(100 - row["error_rate"], 2),
                }
                for row in result.rows
            ]

            return {"object": "top_routes", "routes": routes, "total_routes": len(routes)}

    async def get_client_analytics(
        self, from_date: datetime, to_date: Optional[datetime], group_by: str, project_id: Optional[UUID]
    ) -> Dict[str, Any]:
        """Get client analytics (device, browser, OS distribution)."""
        async with get_clickhouse_client() as client:
            query = self._build_client_analytics_query(from_date, to_date, group_by, project_id)
            result = await client.query(query)

            total_requests = sum(row["count"] for row in result.rows)

            distribution = [
                {
                    group_by: row[group_by] or "Unknown",
                    "count": row["count"],
                    "percent": round((row["count"] / total_requests) * 100, 2) if total_requests > 0 else 0,
                }
                for row in result.rows
            ]

            return {
                "object": "client_analytics",
                "group_by": group_by,
                "total_requests": total_requests,
                "distribution": distribution,
            }

    async def _process_metrics_results(self, result: Any, request: GatewayAnalyticsRequest) -> List[GatewayPeriodBin]:
        """Process raw query results into structured response."""
        # Group results by time period
        time_bins = {}

        for row in result.rows:
            time_period = row["time_bucket"]
            if time_period not in time_bins:
                time_bins[time_period] = []

            # Build metrics data
            metrics_data = GatewayMetricsData(data={})

            # Add grouping dimensions if present
            if request.group_by:
                for group in request.group_by:
                    if group in row:
                        setattr(metrics_data, group, row[group])

            # Process each requested metric
            for metric in request.metrics:
                if metric == "request_count":
                    metrics_data.data[metric] = GatewayCountMetric(
                        count=row.get("request_count", 0),
                        delta=row.get("request_count_delta"),
                        delta_percent=row.get("request_count_delta_percent"),
                    )
                elif metric in ["avg_response_time", "p99_response_time", "p95_response_time"]:
                    metrics_data.data[metric] = GatewayPerformanceMetric(
                        avg=row.get("avg_response_time", 0),
                        p99=row.get("p99_response_time"),
                        p95=row.get("p95_response_time"),
                        delta=row.get(f"{metric}_delta"),
                        delta_percent=row.get(f"{metric}_delta_percent"),
                    )
                elif metric in ["success_rate", "error_rate"]:
                    metrics_data.data[metric] = GatewayRateMetric(
                        rate=row.get(metric, 0),
                        count=row.get(f"{metric}_count", 0),
                        total=row.get("request_count", 0),
                        delta=row.get(f"{metric}_delta"),
                        delta_percent=row.get(f"{metric}_delta_percent"),
                    )
                # Add more metric processing as needed

            time_bins[time_period].append(metrics_data)

        # Convert to sorted list of PeriodBins
        sorted_bins = sorted(time_bins.items(), key=lambda x: x[0])
        return [GatewayPeriodBin(time_period=time_period, items=items) for time_period, items in sorted_bins]

    def _calculate_summary_stats(
        self, items: List[GatewayPeriodBin], request: GatewayAnalyticsRequest
    ) -> Dict[str, Any]:
        """Calculate summary statistics across all time periods."""
        summary = {}

        # Aggregate metrics across all periods
        total_requests = 0
        total_errors = 0
        response_times = []

        for period in items:
            if period.items:
                for item in period.items:
                    if "request_count" in item.data:
                        total_requests += item.data["request_count"].count
                    if "error_rate" in item.data:
                        total_errors += item.data["error_rate"].count
                    if "avg_response_time" in item.data:
                        response_times.append(item.data["avg_response_time"].avg)

        summary["total_requests"] = total_requests
        summary["total_errors"] = total_errors
        summary["overall_error_rate"] = round((total_errors / total_requests * 100), 2) if total_requests > 0 else 0

        if response_times:
            summary["avg_response_time"] = round(sum(response_times) / len(response_times), 2)

        return summary

    def _build_geographical_query(
        self, from_date: datetime, to_date: Optional[datetime], project_id: Optional[UUID], group_by: str
    ) -> str:
        """Build query for geographical statistics."""
        to_date = to_date or datetime.now(timezone.utc)

        where_conditions = [
            f"request_timestamp >= '{from_date.isoformat()}'",
            f"request_timestamp <= '{to_date.isoformat()}'",
        ]

        if project_id:
            where_conditions.append(f"project_id = '{project_id}'")

        if group_by == "country":
            return f"""
                SELECT
                    country_code,
                    COUNT(*) as count
                FROM GatewayAnalytics
                WHERE {" AND ".join(where_conditions)}
                    AND country_code IS NOT NULL
                GROUP BY country_code
                ORDER BY count DESC
                LIMIT 50
            """
        else:  # city
            return f"""
                SELECT
                    city,
                    country_code,
                    AVG(latitude) as latitude,
                    AVG(longitude) as longitude,
                    COUNT(*) as count
                FROM GatewayAnalytics
                WHERE {" AND ".join(where_conditions)}
                    AND city IS NOT NULL
                GROUP BY city, country_code
                ORDER BY count DESC
                LIMIT 100
            """

    def _build_blocking_stats_query(
        self, from_date: datetime, to_date: Optional[datetime], project_id: Optional[UUID]
    ) -> str:
        """Build query for blocking statistics."""
        to_date = to_date or datetime.now(timezone.utc)

        where_conditions = [
            f"request_timestamp >= '{from_date.isoformat()}'",
            f"request_timestamp <= '{to_date.isoformat()}'",
        ]

        if project_id:
            where_conditions.append(f"project_id = '{project_id}'")

        return f"""
            SELECT
                COUNT(*) as total_requests,
                SUM(CASE WHEN is_blocked = 1 THEN 1 ELSE 0 END) as total_blocked,
                groupArray((client_ip, blocked_count)) as top_blocked_ips_raw
            FROM (
                SELECT
                    client_ip,
                    SUM(CASE WHEN is_blocked = 1 THEN 1 ELSE 0 END) as blocked_count
                FROM GatewayAnalytics
                WHERE {" AND ".join(where_conditions)}
                GROUP BY client_ip
                HAVING blocked_count > 0
                ORDER BY blocked_count DESC
                LIMIT 20
            ) as blocked_ips
            CROSS JOIN (
                SELECT 1
            ) as dummy
        """

    def _build_blocking_time_series_query(
        self, from_date: datetime, to_date: Optional[datetime], project_id: Optional[UUID]
    ) -> str:
        """Build query for blocking time series."""
        to_date = to_date or datetime.now(timezone.utc)

        where_conditions = [
            f"request_timestamp >= '{from_date.isoformat()}'",
            f"request_timestamp <= '{to_date.isoformat()}'",
        ]

        if project_id:
            where_conditions.append(f"project_id = '{project_id}'")

        return f"""
            SELECT
                toStartOfHour(request_timestamp) as timestamp,
                SUM(CASE WHEN is_blocked = 1 THEN 1 ELSE 0 END) as blocked_count,
                COUNT(*) as total_count
            FROM GatewayAnalytics
            WHERE {" AND ".join(where_conditions)}
            GROUP BY timestamp
            ORDER BY timestamp
        """

    def _build_top_routes_query(
        self, from_date: datetime, to_date: Optional[datetime], limit: int, project_id: Optional[UUID]
    ) -> str:
        """Build query for top routes."""
        to_date = to_date or datetime.now(timezone.utc)

        where_conditions = [
            f"request_timestamp >= '{from_date.isoformat()}'",
            f"request_timestamp <= '{to_date.isoformat()}'",
        ]

        if project_id:
            where_conditions.append(f"project_id = '{project_id}'")

        return f"""
            SELECT
                path,
                method,
                COUNT(*) as request_count,
                AVG(total_duration_ms) as avg_response_time,
                quantile(0.99)(total_duration_ms) as p99_response_time,
                (SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) / COUNT(*)) * 100 as error_rate
            FROM GatewayAnalytics
            WHERE {" AND ".join(where_conditions)}
            GROUP BY path, method
            ORDER BY request_count DESC
            LIMIT {limit}
        """

    def _build_client_analytics_query(
        self, from_date: datetime, to_date: Optional[datetime], group_by: str, project_id: Optional[UUID]
    ) -> str:
        """Build query for client analytics."""
        to_date = to_date or datetime.now(timezone.utc)

        where_conditions = [
            f"request_timestamp >= '{from_date.isoformat()}'",
            f"request_timestamp <= '{to_date.isoformat()}'",
        ]

        if project_id:
            where_conditions.append(f"project_id = '{project_id}'")

        return f"""
            SELECT
                {group_by},
                COUNT(*) as count
            FROM GatewayAnalytics
            WHERE {" AND ".join(where_conditions)}
            GROUP BY {group_by}
            ORDER BY count DESC
            LIMIT 50
        """

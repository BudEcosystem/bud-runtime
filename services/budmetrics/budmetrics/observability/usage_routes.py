"""Usage tracking endpoints for billing and analytics."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from budmicroframe.commons import logging
from budmicroframe.commons.schemas import ErrorResponse, SuccessResponse
from fastapi import APIRouter, Body, Query
from fastapi.responses import Response

from budmetrics.observability.services import ObservabilityMetricsService


logger = logging.get_logger(__name__)

usage_router = APIRouter()
service = ObservabilityMetricsService()


@usage_router.get("/usage/summary", tags=["Usage"])
async def get_usage_summary(
    user_id: Optional[UUID] = Query(None, description="User ID to filter by"),
    project_id: Optional[UUID] = Query(None, description="Project ID to filter by"),
    start_date: datetime = Query(..., description="Start date for usage period"),
    end_date: datetime = Query(..., description="End date for usage period"),
) -> Response:
    """Get usage summary for billing purposes.

    This endpoint queries InferenceFact table to calculate:
    - Total tokens used (input + output)
    - Total cost incurred
    - Total request count
    - Success rate

    The data is filtered by user_id and/or project_id and aggregated for the specified date range.
    """
    try:
        # Build the query to get usage data using InferenceFact (no JOINs needed)
        query = """
        SELECT
            COUNT(*) as request_count,
            SUM(CASE WHEN is_success THEN 1 ELSE 0 END) as success_count,
            SUM(COALESCE(cost, 0)) as total_cost,
            SUM(COALESCE(input_tokens, 0)) as total_input_tokens,
            SUM(COALESCE(output_tokens, 0)) as total_output_tokens
        FROM InferenceFact
        WHERE timestamp >= %(start_date)s
        AND timestamp <= %(end_date)s
        """

        params = {
            "start_date": start_date,
            "end_date": end_date,
        }

        # Add filters
        if user_id:
            query += " AND user_id = %(user_id)s"
            params["user_id"] = str(user_id)

        if project_id:
            query += " AND api_key_project_id = %(project_id)s"
            params["project_id"] = str(project_id)

        # Execute query
        result = await service.clickhouse_client.execute_query(query, params)

        # Process results
        if result and len(result) > 0:
            row = result[0]
            request_count = row[0] or 0
            success_count = row[1] or 0
            total_cost = float(row[2] or 0)
            total_input_tokens = row[3] or 0
            total_output_tokens = row[4] or 0

            total_tokens = total_input_tokens + total_output_tokens
            success_rate = (success_count / request_count * 100) if request_count > 0 else 0.0

            response_data = {
                "total_tokens": total_tokens,
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "total_cost": total_cost,
                "request_count": request_count,
                "success_count": success_count,
                "success_rate": success_rate,
            }
        else:
            response_data = {
                "total_tokens": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cost": 0.0,
                "request_count": 0,
                "success_count": 0,
                "success_rate": 0.0,
            }

        response = SuccessResponse(
            message="Usage summary retrieved successfully",
            param=response_data,
        )

    except Exception as e:
        logger.error(f"Error getting usage summary: {e}")
        response = ErrorResponse(message=f"Error getting usage summary: {str(e)}")

    return response.to_http_response()


@usage_router.get("/usage/history", tags=["Usage"])
async def get_usage_history(
    user_id: Optional[UUID] = Query(None, description="User ID to filter by"),
    project_id: Optional[UUID] = Query(None, description="Project ID to filter by"),
    start_date: datetime = Query(..., description="Start date for usage period"),
    end_date: datetime = Query(..., description="End date for usage period"),
    granularity: str = Query("daily", description="Granularity: hourly, daily, weekly, monthly"),
) -> Response:
    """Get historical usage data with specified granularity.

    Returns time-series data showing usage metrics over time, grouped by the specified granularity.
    Uses InferenceFact table (no JOINs needed).
    """
    try:
        # Map granularity to ClickHouse date function using InferenceFact.timestamp
        date_trunc_map = {
            "hourly": "toStartOfHour(timestamp)",
            "daily": "toDate(timestamp)",
            "weekly": "toMonday(timestamp)",
            "monthly": "toStartOfMonth(timestamp)",
        }

        date_trunc = date_trunc_map.get(granularity, "toDate(timestamp)")

        # Build the query using InferenceFact (no JOINs needed)
        query = f"""
        SELECT
            {date_trunc} as period,
            COUNT(*) as request_count,
            SUM(COALESCE(cost, 0)) as total_cost,
            SUM(COALESCE(input_tokens, 0)) as total_input_tokens,
            SUM(COALESCE(output_tokens, 0)) as total_output_tokens
        FROM InferenceFact
        WHERE timestamp >= %(start_date)s
        AND timestamp <= %(end_date)s
        """

        params = {
            "start_date": start_date,
            "end_date": end_date,
        }

        # Add filters
        if user_id:
            query += " AND user_id = %(user_id)s"
            params["user_id"] = str(user_id)

        if project_id:
            query += " AND api_key_project_id = %(project_id)s"
            params["project_id"] = str(project_id)

        query += " GROUP BY period ORDER BY period ASC"

        # Execute query
        result = await service.clickhouse_client.execute_query(query, params)

        # Process results
        history_data = []
        if result:
            for row in result:
                period = row[0]
                request_count = row[1] or 0
                total_cost = float(row[2] or 0)
                total_input_tokens = row[3] or 0
                total_output_tokens = row[4] or 0
                total_tokens = total_input_tokens + total_output_tokens

                history_data.append(
                    {
                        "date": period.isoformat() if hasattr(period, "isoformat") else str(period),
                        "tokens": total_tokens,
                        "input_tokens": total_input_tokens,
                        "output_tokens": total_output_tokens,
                        "requests": request_count,
                        "cost": total_cost,
                    }
                )

        response = SuccessResponse(
            message="Usage history retrieved successfully",
            param={"data": history_data, "granularity": granularity},
        )

    except Exception as e:
        logger.error(f"Error getting usage history: {e}")
        response = ErrorResponse(message=f"Error getting usage history: {str(e)}")

    return response.to_http_response()


@usage_router.get("/usage/by-project", tags=["Usage"])
async def get_usage_by_project(
    user_id: UUID = Query(..., description="User ID to get projects for"),
    start_date: datetime = Query(..., description="Start date for usage period"),
    end_date: datetime = Query(..., description="End date for usage period"),
) -> Response:
    """Get usage breakdown by project for a specific user.

    Returns usage metrics grouped by project, useful for understanding which projects
    are consuming the most resources. Uses InferenceFact table (no JOINs needed).
    """
    try:
        # Build the query using InferenceFact (no JOINs needed)
        query = """
        SELECT
            api_key_project_id,
            COUNT(*) as request_count,
            SUM(COALESCE(cost, 0)) as total_cost,
            SUM(COALESCE(input_tokens, 0)) as total_input_tokens,
            SUM(COALESCE(output_tokens, 0)) as total_output_tokens
        FROM InferenceFact
        WHERE user_id = %(user_id)s
        AND timestamp >= %(start_date)s
        AND timestamp <= %(end_date)s
        GROUP BY api_key_project_id
        ORDER BY total_cost DESC
        """

        params = {
            "user_id": str(user_id),
            "start_date": start_date,
            "end_date": end_date,
        }

        # Execute query
        result = await service.clickhouse_client.execute_query(query, params)

        # Process results
        projects_data = []
        if result:
            for row in result:
                project_id = row[0]
                request_count = row[1] or 0
                total_cost = float(row[2] or 0)
                total_input_tokens = row[3] or 0
                total_output_tokens = row[4] or 0
                total_tokens = total_input_tokens + total_output_tokens

                projects_data.append(
                    {
                        "project_id": str(project_id),
                        "tokens": total_tokens,
                        "requests": request_count,
                        "cost": total_cost,
                    }
                )

        response = SuccessResponse(
            message="Usage by project retrieved successfully",
            param={"projects": projects_data},
        )

    except Exception as e:
        logger.error(f"Error getting usage by project: {e}")
        response = ErrorResponse(message=f"Error getting usage by project: {str(e)}")

    return response.to_http_response()


@usage_router.post("/usage/summary/bulk", tags=["Usage"])
async def get_bulk_usage_summary(
    request_data: dict = Body(...),
) -> Response:
    """Get usage summary for multiple users in a single request.

    This endpoint efficiently queries InferenceFact for multiple users at once,
    returning usage data for each user. This is significantly more efficient than
    making individual API calls for each user.

    Request body should contain:
    {
        "user_ids": ["uuid1", "uuid2", "uuid3"],
        "start_date": "2025-01-01T00:00:00Z",
        "end_date": "2025-01-31T23:59:59Z",
        "project_id": "optional_project_uuid"
    }

    Returns:
    {
        "message": "Bulk usage summary retrieved successfully",
        "param": {
            "users": [
                {
                    "user_id": "uuid1",
                    "total_tokens": 50000,
                    "total_input_tokens": 30000,
                    "total_output_tokens": 20000,
                    "total_cost": 125.50,
                    "request_count": 1500,
                    "success_count": 1485,
                    "success_rate": 99.0
                },
                ...
            ],
            "summary": {
                "total_users": 3,
                "total_tokens_all": 150000,
                "total_cost_all": 350.25,
                "total_requests_all": 4500
            }
        }
    }
    """
    try:
        # Validate request data
        user_ids = request_data.get("user_ids", [])
        start_date_str = request_data.get("start_date")
        end_date_str = request_data.get("end_date")
        project_id_str = request_data.get("project_id")

        if not user_ids:
            return ErrorResponse(message="user_ids list cannot be empty").to_http_response()

        if not start_date_str or not end_date_str:
            return ErrorResponse(message="start_date and end_date are required").to_http_response()

        # Convert to proper types
        try:
            user_uuids = [UUID(uid) for uid in user_ids]
            start_date = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
            end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
            project_id = UUID(project_id_str) if project_id_str else None
        except (ValueError, TypeError) as e:
            return ErrorResponse(message=f"Invalid date format or UUID: {str(e)}").to_http_response()

        # Limit to reasonable batch size
        if len(user_uuids) > 1000:
            return ErrorResponse(message="Maximum 1000 users per batch request").to_http_response()

        # Build bulk query for all users using InferenceFact (no JOINs needed)
        query = """
        SELECT
            user_id,
            COUNT(*) as request_count,
            SUM(CASE WHEN is_success THEN 1 ELSE 0 END) as success_count,
            SUM(COALESCE(cost, 0)) as total_cost,
            SUM(COALESCE(input_tokens, 0)) as total_input_tokens,
            SUM(COALESCE(output_tokens, 0)) as total_output_tokens
        FROM InferenceFact
        WHERE timestamp >= %(start_date)s
        AND timestamp <= %(end_date)s
        AND user_id IS NOT NULL
        """

        params = {
            "start_date": start_date,
            "end_date": end_date,
        }

        # Add user IDs filter with proper parameterization
        placeholders = [f"%(user_{i})s" for i in range(len(user_uuids))]
        query += f" AND user_id IN ({','.join(placeholders)})"
        for i, user_id in enumerate(user_uuids):
            params[f"user_{i}"] = str(user_id)

        # Add project filter if specified
        if project_id:
            query += " AND api_key_project_id = %(project_id)s"
            params["project_id"] = str(project_id)

        query += " GROUP BY user_id ORDER BY total_cost DESC"

        # Execute the bulk query
        result = await service.clickhouse_client.execute_query(query, params)

        # Process results into user-specific summaries
        users_data = []
        total_tokens_all = 0
        total_cost_all = 0.0
        total_requests_all = 0

        # Create lookup for faster processing
        result_lookup = {}
        if result:
            for row in result:
                user_id_str = str(row[0])
                request_count = row[1] or 0
                success_count = row[2] or 0
                total_cost = float(row[3] or 0)
                total_input_tokens = row[4] or 0
                total_output_tokens = row[5] or 0

                result_lookup[user_id_str] = {
                    "request_count": request_count,
                    "success_count": success_count,
                    "total_cost": total_cost,
                    "total_input_tokens": total_input_tokens,
                    "total_output_tokens": total_output_tokens,
                }

        # Ensure we have data for all requested users (even if they have 0 usage)
        for user_id in user_uuids:
            user_id_str = str(user_id)
            user_data = result_lookup.get(
                user_id_str,
                {
                    "request_count": 0,
                    "success_count": 0,
                    "total_cost": 0.0,
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                },
            )

            total_tokens = user_data["total_input_tokens"] + user_data["total_output_tokens"]
            success_rate = (
                (user_data["success_count"] / user_data["request_count"] * 100)
                if user_data["request_count"] > 0
                else 0.0
            )

            user_summary = {
                "user_id": user_id_str,
                "total_tokens": total_tokens,
                "total_input_tokens": user_data["total_input_tokens"],
                "total_output_tokens": user_data["total_output_tokens"],
                "total_cost": user_data["total_cost"],
                "request_count": user_data["request_count"],
                "success_count": user_data["success_count"],
                "success_rate": success_rate,
            }

            users_data.append(user_summary)

            # Add to totals
            total_tokens_all += total_tokens
            total_cost_all += user_data["total_cost"]
            total_requests_all += user_data["request_count"]

        # Create summary data
        response_data = {
            "users": users_data,
            "summary": {
                "total_users": len(user_uuids),
                "total_tokens_all": total_tokens_all,
                "total_cost_all": total_cost_all,
                "total_requests_all": total_requests_all,
                "date_range": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                },
                "project_id": str(project_id) if project_id else None,
            },
        }

        response = SuccessResponse(
            message="Bulk usage summary retrieved successfully",
            param=response_data,
        )

    except Exception as e:
        logger.error(f"Error getting bulk usage summary: {e}")
        response = ErrorResponse(message=f"Error getting bulk usage summary: {str(e)}")

    return response.to_http_response()

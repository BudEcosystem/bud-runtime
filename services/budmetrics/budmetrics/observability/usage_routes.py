"""Usage tracking endpoints for billing and analytics."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from budmicroframe.commons import logging
from fastapi import APIRouter, Query
from fastapi.responses import Response

from budmetrics.observability.schemas import ErrorResponse, SuccessResponse
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

    This endpoint queries ModelInferenceDetails and related tables to calculate:
    - Total tokens used (input + output)
    - Total cost incurred
    - Total request count
    - Success rate

    The data is filtered by user_id and/or project_id and aggregated for the specified date range.
    """
    try:
        # Build the query to get usage data
        query = """
        SELECT
            COUNT(*) as request_count,
            SUM(CASE WHEN is_success THEN 1 ELSE 0 END) as success_count,
            SUM(COALESCE(cost, 0)) as total_cost,
            SUM(COALESCE(mi.input_tokens, 0)) as total_input_tokens,
            SUM(COALESCE(mi.output_tokens, 0)) as total_output_tokens
        FROM ModelInferenceDetails mid
        LEFT JOIN ModelInference mi ON mid.inference_id = mi.inference_id
        WHERE mid.request_arrival_time >= %(start_date)s
        AND mid.request_arrival_time <= %(end_date)s
        """

        params = {
            "start_date": start_date,
            "end_date": end_date,
        }

        # Add filters
        if user_id:
            query += " AND mid.user_id = %(user_id)s"
            params["user_id"] = str(user_id)

        if project_id:
            query += " AND mid.api_key_project_id = %(project_id)s"
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
    """
    try:
        # Map granularity to ClickHouse date function
        date_trunc_map = {
            "hourly": "toStartOfHour(mid.request_arrival_time)",
            "daily": "toDate(mid.request_arrival_time)",
            "weekly": "toMonday(mid.request_arrival_time)",
            "monthly": "toStartOfMonth(mid.request_arrival_time)",
        }

        date_trunc = date_trunc_map.get(granularity, "toDate(mid.request_arrival_time)")

        # Build the query
        query = f"""
        SELECT
            {date_trunc} as period,
            COUNT(*) as request_count,
            SUM(COALESCE(cost, 0)) as total_cost,
            SUM(COALESCE(mi.input_tokens, 0)) as total_input_tokens,
            SUM(COALESCE(mi.output_tokens, 0)) as total_output_tokens
        FROM ModelInferenceDetails mid
        LEFT JOIN ModelInference mi ON mid.inference_id = mi.inference_id
        WHERE mid.request_arrival_time >= %(start_date)s
        AND mid.request_arrival_time <= %(end_date)s
        """

        params = {
            "start_date": start_date,
            "end_date": end_date,
        }

        # Add filters
        if user_id:
            query += " AND mid.user_id = %(user_id)s"
            params["user_id"] = str(user_id)

        if project_id:
            query += " AND mid.api_key_project_id = %(project_id)s"
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
    are consuming the most resources.
    """
    try:
        # Build the query
        query = """
        SELECT
            mid.api_key_project_id,
            COUNT(*) as request_count,
            SUM(COALESCE(cost, 0)) as total_cost,
            SUM(COALESCE(mi.input_tokens, 0)) as total_input_tokens,
            SUM(COALESCE(mi.output_tokens, 0)) as total_output_tokens
        FROM ModelInferenceDetails mid
        LEFT JOIN ModelInference mi ON mid.inference_id = mi.inference_id
        WHERE mid.user_id = %(user_id)s
        AND mid.request_arrival_time >= %(start_date)s
        AND mid.request_arrival_time <= %(end_date)s
        GROUP BY mid.api_key_project_id
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

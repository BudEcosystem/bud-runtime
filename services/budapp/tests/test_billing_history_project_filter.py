#!/usr/bin/env python3
"""Test script to verify project_id filter in billing/history API."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest
from budapp.billing_ops.routes import get_usage_history
from budapp.billing_ops.schemas import UsageHistoryRequest
from budapp.billing_ops.services import BillingService


@pytest.mark.asyncio
async def test_billing_history_with_project_id_filter():
    """Test that project_id filter is properly passed through the billing/history API."""

    # Setup test data
    user_id = uuid4()
    project_id = uuid4()
    start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2024, 1, 31, tzinfo=timezone.utc)

    # Create mock user
    mock_user = Mock()
    mock_user.id = user_id
    mock_user.user_type = "USER"

    # Create mock database session
    mock_db = MagicMock()

    # Create request with project_id
    request = UsageHistoryRequest(
        start_date=start_date,
        end_date=end_date,
        granularity="daily",
        project_id=project_id
    )

    # Mock the service and its method
    mock_history_data = {
        "data": [
            {
                "date": "2024-01-15",
                "tokens": 1000,
                "input_tokens": 600,
                "output_tokens": 400,
                "requests": 10,
                "cost": 5.50
            },
            {
                "date": "2024-01-16",
                "tokens": 1500,
                "input_tokens": 900,
                "output_tokens": 600,
                "requests": 15,
                "cost": 7.25
            }
        ],
        "granularity": "daily"
    }

    with patch.object(BillingService, 'get_usage_history', new_callable=AsyncMock) as mock_get_history:
        mock_get_history.return_value = mock_history_data

        # Call the route handler
        response = await get_usage_history(
            request=request,
            current_user=mock_user,
            db=mock_db
        )

        # Verify the service was called with project_id
        mock_get_history.assert_called_once_with(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            granularity="daily",
            project_id=project_id
        )

        # Verify the response
        assert response.result == mock_history_data
        assert response.message == "Usage history retrieved successfully"

    print("✅ Test passed: project_id filter is properly passed to the service")


@pytest.mark.asyncio
async def test_billing_history_without_project_id():
    """Test that billing/history API works without project_id filter."""

    # Setup test data
    user_id = uuid4()
    start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2024, 1, 31, tzinfo=timezone.utc)

    # Create mock user
    mock_user = Mock()
    mock_user.id = user_id
    mock_user.user_type = "USER"

    # Create mock database session
    mock_db = MagicMock()

    # Create request without project_id
    request = UsageHistoryRequest(
        start_date=start_date,
        end_date=end_date,
        granularity="monthly"
    )

    # Mock the service and its method
    mock_history_data = {
        "data": [
            {
                "date": "2024-01-01",
                "tokens": 10000,
                "input_tokens": 6000,
                "output_tokens": 4000,
                "requests": 100,
                "cost": 55.00
            }
        ],
        "granularity": "monthly"
    }

    with patch.object(BillingService, 'get_usage_history', new_callable=AsyncMock) as mock_get_history:
        mock_get_history.return_value = mock_history_data

        # Call the route handler
        response = await get_usage_history(
            request=request,
            current_user=mock_user,
            db=mock_db
        )

        # Verify the service was called with project_id=None
        mock_get_history.assert_called_once_with(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            granularity="monthly",
            project_id=None
        )

        # Verify the response
        assert response.result == mock_history_data
        assert response.message == "Usage history retrieved successfully"

    print("✅ Test passed: billing/history works without project_id filter")


@pytest.mark.asyncio
async def test_service_passes_project_id_to_budmetrics():
    """Test that BillingService properly passes project_id to budmetrics API."""

    # Setup test data
    user_id = uuid4()
    project_id = uuid4()
    start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2024, 1, 31, tzinfo=timezone.utc)

    # Create mock database session
    mock_db = MagicMock()

    # Create service instance
    service = BillingService(mock_db)

    # Mock the httpx client
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "param": {
            "data": [
                {"date": "2024-01-15", "tokens": 500, "cost": 2.50}
            ]
        }
    }
    mock_response.raise_for_status = Mock()

    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client.get.return_value = mock_response

        # Call the service method with project_id
        result = await service.get_usage_history(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            granularity="daily",
            project_id=project_id
        )

        # Verify the HTTP request was made with correct params
        expected_url = f"{service.budmetrics_base_url}/observability/usage/history"
        expected_params = {
            "user_id": str(user_id),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "granularity": "daily",
            "project_id": str(project_id)
        }

        mock_client.get.assert_called_once_with(
            expected_url,
            params=expected_params,
            timeout=30.0
        )

        # Verify the result
        assert result == {"data": [{"date": "2024-01-15", "tokens": 500, "cost": 2.50}]}

    print("✅ Test passed: BillingService passes project_id to budmetrics API")


@pytest.mark.asyncio
async def test_service_omits_project_id_when_none():
    """Test that BillingService omits project_id param when None."""

    # Setup test data
    user_id = uuid4()
    start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2024, 1, 31, tzinfo=timezone.utc)

    # Create mock database session
    mock_db = MagicMock()

    # Create service instance
    service = BillingService(mock_db)

    # Mock the httpx client
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "param": {
            "data": []
        }
    }
    mock_response.raise_for_status = Mock()

    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client.get.return_value = mock_response

        # Call the service method without project_id
        result = await service.get_usage_history(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            granularity="weekly"
        )

        # Verify the HTTP request was made without project_id param
        expected_url = f"{service.budmetrics_base_url}/observability/usage/history"
        expected_params = {
            "user_id": str(user_id),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "granularity": "weekly"
        }

        mock_client.get.assert_called_once_with(
            expected_url,
            params=expected_params,
            timeout=30.0
        )

        # Verify project_id was not included in params
        call_args = mock_client.get.call_args
        assert "project_id" not in call_args[1]["params"]

    print("✅ Test passed: BillingService omits project_id when None")


def run_tests():
    """Run all tests."""
    asyncio.run(test_billing_history_with_project_id_filter())
    asyncio.run(test_billing_history_without_project_id())
    asyncio.run(test_service_passes_project_id_to_budmetrics())
    asyncio.run(test_service_omits_project_id_when_none())
    print("\n✅ All tests passed! The project_id filter is working correctly.")


if __name__ == "__main__":
    run_tests()

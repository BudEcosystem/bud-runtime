# Credential Last Used Implementation Summary

## Overview
Implemented functionality to track and display the last usage time of API credentials (API keys) across the bud-stack platform.

## Architecture
The implementation tracks credential usage by:
1. **budgateway** validates API keys and includes `api_key_id` in requests
2. **budmetrics** stores all API request analytics in ClickHouse with `api_key_id`
3. **budapp** periodically syncs usage data from budmetrics and updates credentials
4. **budapp** credential listing API returns the `last_used_at` field

## Changes Made

### 1. BudMetrics Service (`services/budmetrics/`)

#### `budmetrics/observability/schemas.py`
- Added `CredentialUsageRequest` schema for querying usage data
- Added `CredentialUsageItem` schema for individual credential usage
- Added `CredentialUsageResponse` schema with proper ResponseBase inheritance
- Fixed datetime serialization with `ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})`

#### `budmetrics/observability/services.py`
- Added `get_credential_usage()` method to query ClickHouse for credential usage
- Queries `ModelInferenceDetails` table grouping by `api_key_id`
- Fixed UUID handling to support both UUID objects and strings from ClickHouse
- Returns last usage time and request count per credential

#### `budmetrics/observability/routes.py`
- Added `POST /credential-usage` endpoint to expose usage data
- Returns usage statistics for specified time window

### 2. BudApp Service (`services/budapp/`)

#### `budapp/credential_ops/crud.py`
- Added `batch_update_last_used()` method for efficient batch updates
- Updates multiple credentials' `last_used_at` field in a single transaction

#### `budapp/credential_ops/services.py`
- Added `fetch_recent_credential_usage()` to query budmetrics via Dapr
- Added `update_credential_last_used()` to process and store usage data
- Added `sync_credential_usage_from_metrics()` to orchestrate the sync process
- Fixed merge conflicts and removed webhook-related code

#### `budapp/main.py`
- Added background task `schedule_credential_usage_sync()`
- Runs every 5 minutes (300 seconds) to sync usage data
- Starts automatically when the application launches

## Key Features

### Background Sync Task
- Runs every 5 minutes
- Queries last 10 minutes of data (with overlap for reliability)
- Updates only credentials that have been used
- Logs results for monitoring

### Error Handling
- Graceful error handling in all service methods
- Returns empty results on errors to prevent cascading failures
- Comprehensive logging for debugging

### UUID and DateTime Handling
- Proper UUID conversion supporting both objects and strings
- DateTime serialization to ISO format for JSON compatibility
- Robust parsing of ClickHouse query results

## Removed Features
- Webhook functionality was completely removed as it was designed for billing notifications, not credential usage tracking
- All webhook-related code, schemas, and routes were deleted

## Testing
Created integration test script (`test_credential_last_used_integration.py`) that verifies:
- UUID handling with different input types
- DateTime serialization and deserialization
- JSON response serialization

## API Usage

### Query Credential Usage (BudMetrics)
```bash
POST /observability/credential-usage
{
  "since": "2025-01-24T12:00:00Z",
  "credential_ids": ["uuid1", "uuid2"]  // optional
}
```

### Get Credentials with Last Used (BudApp)
```bash
GET /credentials?page=1&limit=20
# Response includes last_used_at field for each credential
```

## Database Schema
- BudApp: `credentials` table has `last_used_at` column (datetime, nullable)
- BudMetrics: `ModelInferenceDetails` table has `api_key_id` column (UUID)

## Performance Considerations
- Batch updates reduce database load
- 5-minute sync interval balances freshness vs. resource usage
- ClickHouse queries are optimized with proper indexing
- Background task doesn't block main application

## Security
- No plain text API keys are stored or transmitted
- Uses hashed API key IDs for tracking
- Row-level security ensures users only see their own data
- Dapr service invocation provides secure inter-service communication

# Metrics API Migration Guide

## Overview

This guide documents the migration from the old `/metrics/*` endpoints to the new `/metrics/analytics` API.

## ✅ Completed Migrations

### 1. Analytics Endpoints
The following endpoints have been migrated to use `/metrics/analytics`:

| Old Endpoint | New Endpoint | Updated In |
|--------------|--------------|------------|
| `POST /metrics/analytics/request-counts` | `POST /metrics/analytics` | `useCharts.tsx`, `useProjects.tsx` |
| `POST /metrics/analytics/request-performance` | `POST /metrics/analytics` | `useCharts.tsx` |

### 2. Migration Approach
- Created `metricsAdapter.ts` utility for backward compatibility
- Converts old request parameters to new format
- Transforms new response format to match old format
- No changes required in UI components

## ⚠️ Endpoints Requiring Further Action

### 1. Dashboard Count Metrics
- **Current**: `GET /metrics/count`
- **Used In**: `useCharts.tsx` - `getDashboardCountData()`
- **Action Required**: Confirm if this endpoint will be part of observability API or remain separate

### 2. Cache Metrics
- **Current**: `POST /metrics/analytics/cache-metrics/{deploymentId}`
- **Used In**: `useEndPoint.tsx` - `getReusedPrompts()`
- **Action Required**: Determine if cache metrics will be available through observability API

### 3. Inference Quality Metrics
- **Current**: 
  - `POST /metrics/analytics/inference-quality/{deploymentId}`
  - `POST /metrics/analytics/inference-quality-prompts/{id}/{scoreType}`
- **Used In**: `useEndPoint.tsx`
- **Action Required**: These specialized metrics may need custom handling

### 4. Cluster Metrics
- **Current**: 
  - `GET /clusters/{id}/metrics`
  - `GET /clusters/{id}/node-metrics`
  - `GET /clusters/{id}/grafana-dashboard`
- **Used In**: `useCluster.tsx`
- **Action Required**: Infrastructure metrics may remain under cluster endpoints

### 5. Model Leaderboards
- **Current**: `POST /models/top-leaderboards`
- **Used In**: `useCharts.tsx` - `getAccuracyChart()`
- **Action Required**: Not a metrics endpoint but used for accuracy charts

## 📝 Parameter Mapping Reference

### Request Parameters

| Old Parameter | New Parameter | Notes |
|---------------|---------------|-------|
| `frequency: "daily"/"weekly"/"monthly"` | `frequency_unit: "day"/"week"/"month"` | Direct mapping |
| `filter_by` + `filter_conditions` | `filters: { project: [], model: "", endpoint: "" }` | Restructured |
| `metrics` (query param) | `metrics` (array in body) | Now supports multiple metrics |
| `top_k` | `topk` | Simple rename |
| N/A | `return_delta: true` | New feature, always enabled |
| N/A | `fill_time_gaps: true` | New feature, always enabled |
| N/A | `group_by` | Derived from `filter_by` |

### Metrics Name Mapping

| Old Metric | New Metric | Description |
|------------|------------|-------------|
| `"overall"` | `["request_count"]` | Total request counts |
| `"throughput"` | `["throughput"]` | Tokens per second |
| `"latency"` | `["latency"]` | Response latency |
| `"input_output_tokens"` | `["input_token", "output_token"]` | Token usage |
| `"concurrency"` | `["concurrent_requests"]` | Concurrent requests |
| `"queuing_time"` | `["queuing_time"]` | Queue wait time |

## 🔧 Implementation Pattern

For any new endpoint migrations, follow this pattern:

```typescript
// 1. Import the adapter
import { convertToObservabilityRequest, convertObservabilityResponse } from "@/utils/metricsAdapter";

// 2. Update the API call
const observabilityRequest = convertToObservabilityRequest(oldParams);
const response = await AppRequest.Post(`${tempApiBaseUrl}/metrics/analytics`, observabilityRequest);

// 3. Convert the response
const convertedData = convertObservabilityResponse(
  response.data,
  oldParams.metrics,
  oldParams.filter_by
);
```

## 🚨 Testing Checklist

When testing the migration:

1. [ ] Verify all charts display data correctly
2. [ ] Check time period filters (daily/weekly/monthly)
3. [ ] Test entity filters (project/model/endpoint)
4. [ ] Confirm delta percentages show correctly
5. [ ] Validate token metrics display
6. [ ] Test performance metrics (throughput/latency)
7. [ ] Verify error handling for failed requests

## 📊 Response Format Changes

### Old Format Example
```json
{
  "overall_metrics": {
    "summary_metrics": {
      "total_value": 1000,
      "delta_percentage": 10.5,
      "items": [
        {
          "name": "model-123",
          "total_value": 500
        }
      ]
    }
  }
}
```

### New Format Example
```json
{
  "object": "observability_metrics",
  "items": [
    {
      "time_period": "2024-01-01T00:00:00",
      "items": [
        {
          "model_id": "model-123",
          "data": {
            "request_count": {
              "count": 500,
              "delta_percent": 10.5
            }
          }
        }
      ]
    }
  ]
}
```

## 🔄 Next Steps

1. Confirm which endpoints will be migrated to observability API
2. Update remaining endpoints based on backend decisions
3. Remove backward compatibility layer once all components are updated
4. Update CLAUDE.md with final API structure
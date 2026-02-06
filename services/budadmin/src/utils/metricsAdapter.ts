import { tempApiBaseUrl } from "@/components/environment";

// Types for the new observability API
export interface ObservabilityMetricsRequest {
  metrics: string[];
  from_date: string;
  to_date?: string;
  frequency_unit?: "hour" | "day" | "week" | "month" | "quarter" | "year";
  frequency_interval?: number;
  filters?: {
    project?: string[];
    model?: string[];
    endpoint?: string[];
  };
  group_by?: Array<"project" | "model" | "endpoint">;
  return_delta?: boolean;
  fill_time_gaps?: boolean;
  topk?: number;
}

export interface ObservabilityMetricsResponse {
  object: "observability_metrics";
  items: Array<{
    time_period: string;
    items: Array<{
      model_id?: string;
      model_name?: string;
      project_id?: string;
      project_name?: string;
      endpoint_id?: string;
      endpoint_name?: string;
      data: {
        [metric: string]: {
          count?: number;
          value?: number;
          rate?: number;
          delta?: number;
          delta_percent?: number;
          // General average
          avg?: number;
          // For latency and TTFT metrics
          avg_latency_ms?: number;
          latency_p95?: number;
          latency_p99?: number;
          p95?: number;
          p99?: number;
          avg_ttft_ms?: number;
          ttft_p95?: number;
          ttft_p99?: number;
          // For success/failure metrics
          success_rate?: number;
          failure_rate?: number;
          // For throughput
          avg_throughput?: number;
          // For cache metrics
          hit_rate?: number;
          avg_latency?: number;
        };
      };
    }>;
  }>;
}

// Map old frequency to new frequency_unit
const mapFrequency = (
  oldFrequency: string,
): "hour" | "day" | "week" | "month" => {
  switch (oldFrequency) {
    case "hourly":
      return "hour";
    case "daily":
      return "day";
    case "weekly":
      return "week";
    case "monthly":
      return "month";
    default:
      return "day";
  }
};

// Map old metrics parameter to new metrics array
const mapMetrics = (oldMetrics?: string | null): string[] => {
  if (!oldMetrics) return ["request_count"];

  switch (oldMetrics) {
    case "overall":
      return ["request_count"];
    case "throughput":
      return ["throughput"];
    case "latency":
      return ["latency"];
    case "ttft":
      return ["ttft"];
    case "input_output_tokens":
      return ["input_token", "output_token"];
    case "concurrency":
      return ["concurrent_requests"];
    case "queuing_time":
      return ["queuing_time"];
    case "global":
      return ["request_count"];
    default:
      return ["request_count"];
  }
};

// Convert old API parameters to new format
export const convertToObservabilityRequest = (params: {
  frequency: string;
  filter_by: string;
  filter_conditions?: string[] | null;
  from_date: string;
  to_date?: string | null;
  top_k?: number | null;
  metrics?: string | null;
  project_id?: string | null;
}): ObservabilityMetricsRequest => {
  const request: ObservabilityMetricsRequest = {
    metrics: mapMetrics(params.metrics),
    from_date: params.from_date,
    to_date: params.to_date || undefined,
    frequency_unit: mapFrequency(params.frequency),
    frequency_interval: 1, // Always set to 1 for consistent data points
    return_delta: true,
    fill_time_gaps: true,
  };

  // Handle filters
  request.filters = {};

  // Add project_id filter if provided
  if (params.project_id) {
    request.filters.project = [params.project_id];
  }

  // Add other filters from filter_conditions
  if (params.filter_conditions && params.filter_conditions.length > 0) {
    if (params.filter_by === "project" && !params.project_id) {
      request.filters.project = params.filter_conditions;
    } else if (params.filter_by === "model") {
      request.filters.model = params.filter_conditions;
    } else if (params.filter_by === "endpoint") {
      request.filters.endpoint = params.filter_conditions;
    }
  }

  // Remove empty filters object if no filters were added
  if (Object.keys(request.filters).length === 0) {
    delete request.filters;
  }

  // Handle group_by
  if (
    params.filter_by &&
    params.filter_by !== "global" &&
    params.metrics !== "global"
  ) {
    request.group_by = [params.filter_by as "project" | "model" | "endpoint"];
  }

  // Handle top_k - only add if no filters are present
  if (params.top_k && !request.filters) {
    request.topk = params.top_k;
  }

  return request;
};

// Convert new observability response to old format for backward compatibility
export const convertObservabilityResponse = (
  response: ObservabilityMetricsResponse,
  oldMetrics?: string | null,
  filterBy?: string,
): any => {
  // Handle empty response
  if (!response.items || response.items.length === 0) {
    // Return empty structure based on metric type
    if (oldMetrics === "input_output_tokens") {
      return {
        input_output_tokens_metrics: {
          summary_metrics: {
            input_tokens_delta_value: 0,
            output_tokens_delta_value: 0,
            input_tokens_delta_percentage: 0,
            output_tokens_delta_percentage: 0,
          },
          items: [],
        },
      };
    }

    if (
      oldMetrics === "throughput" ||
      oldMetrics === "latency" ||
      oldMetrics === "ttft"
    ) {
      const metricKey =
        oldMetrics === "throughput"
          ? "throughput_metrics"
          : oldMetrics === "latency"
            ? "latency_metrics"
            : "ttft_metrics";
      return {
        [metricKey]: {
          summary_metrics: {
            total_value: 0,
            delta_percentage: 0,
            items: [],
          },
          items: [],
        },
      };
    }

    if (oldMetrics === "queuing_time") {
      return {
        queuing_time_metrics: {
          summary_metrics: {
            total_value: 0,
            delta_percentage: 0,
            items: [],
          },
          items: [],
        },
      };
    }

    if (oldMetrics === "concurrency") {
      return {
        concurrency_metrics: {
          summary_metrics: {
            total_value: 0,
            delta_percentage: 0,
            items: [],
          },
          items: [],
        },
      };
    }

    if (oldMetrics === "global") {
      return {
        global_metrics: {
          summary_metrics: {
            total_value: 0,
            delta_percentage: 0,
          },
          items: [],
        },
      };
    }

    // Default empty response
    return {
      overall_metrics: {
        summary_metrics: {
          total_value: 0,
          delta_percentage: 0,
          items: [],
        },
        items: [],
      },
    };
  }

  const metricsArray = mapMetrics(oldMetrics);
  const primaryMetric = metricsArray[0];

  // Calculate summary metrics
  let totalValue = 0;
  let deltaPercentage = 0;
  const itemsMap = new Map<string, number>();

  // When we have multiple periods (for delta calculation), only use the first half for display
  // The API returns data sorted with latest at index 0
  const periodsToDisplay =
    response.items.length >= 2
      ? Math.ceil(response.items.length / 2)
      : response.items.length;

  // Process only the display periods (latest half of the data)
  for (let i = 0; i < periodsToDisplay; i++) {
    const timePeriod = response.items[i];
    // Check if items exists and is an array
    if (timePeriod.items && Array.isArray(timePeriod.items)) {
      timePeriod.items.forEach((item) => {
        const metricData = item.data[primaryMetric];
        const value = metricData?.count || metricData?.value || 0;
        totalValue += value;

        // Group by entity for summary
        let entityName = "Unknown";
        if (filterBy === "project") {
          entityName = item.project_name || item.project_id || "Unknown";
        } else if (filterBy === "model") {
          entityName = item.model_name || item.model_id || "Unknown";
        } else if (filterBy === "endpoint") {
          entityName = item.endpoint_name || item.endpoint_id || "Unknown";
        }

        itemsMap.set(entityName, (itemsMap.get(entityName) || 0) + value);
      });
    }
  }

  // Get delta from the API response directly
  // The latest period (index 0) should have the delta calculated by the API
  if (
    response.items.length > 0 &&
    response.items[0].items &&
    response.items[0].items.length > 0
  ) {
    // Try to get delta from the first item's metric data
    const firstItem = response.items[0].items[0];
    const metricData = firstItem.data[primaryMetric];
    if (metricData?.delta_percent !== undefined) {
      deltaPercentage = metricData.delta_percent;
    } else if (metricData?.delta !== undefined && totalValue > 0) {
      // Calculate percentage from delta value if percentage not provided
      deltaPercentage =
        (metricData.delta / (totalValue - metricData.delta)) * 100;
    }
  }

  // Convert map to array for summary items
  const summaryItems = Array.from(itemsMap.entries()).map(
    ([name, total_value]) => ({
      name,
      total_value,
    }),
  );

  // Handle special cases for different metrics
  if (oldMetrics === "input_output_tokens") {
    return convertTokenMetricsResponse(response);
  }

  if (
    oldMetrics === "throughput" ||
    oldMetrics === "latency" ||
    oldMetrics === "ttft"
  ) {
    return convertPerformanceMetricsResponse(response, oldMetrics);
  }

  if (oldMetrics === "global") {
    return convertGlobalMetricsResponse(response);
  }

  // Default response format
  return {
    overall_metrics: {
      summary_metrics: {
        total_value: totalValue,
        delta_percentage: deltaPercentage,
        items: summaryItems,
      },
      items: response.items.slice(0, periodsToDisplay).map((timePeriod) => ({
        time_period: timePeriod.time_period,
        items:
          timePeriod.items && Array.isArray(timePeriod.items)
            ? timePeriod.items.map((item) => {
                const metricData = item.data[primaryMetric];
                return {
                  name:
                    item.model_name ||
                    item.project_name ||
                    item.endpoint_name ||
                    item.model_id ||
                    item.project_id ||
                    item.endpoint_id ||
                    "Unknown",
                  total_requests: metricData?.count || metricData?.value || 0,
                  // Add other fields as needed
                };
              })
            : [],
      })),
    },
  };
};

// Special converter for token metrics
const convertTokenMetricsResponse = (
  response: ObservabilityMetricsResponse,
): any => {
  let totalInputTokens = 0;
  let totalOutputTokens = 0;
  let inputDeltaPercentage = 0;
  let outputDeltaPercentage = 0;

  // When we have multiple periods (for delta calculation), only use the first half for display
  const periodsToDisplay =
    response.items.length >= 2
      ? Math.ceil(response.items.length / 2)
      : response.items.length;

  // Calculate totals only from display periods
  for (let i = 0; i < periodsToDisplay; i++) {
    const timePeriod = response.items[i];
    if (timePeriod.items && Array.isArray(timePeriod.items)) {
      timePeriod.items.forEach((item) => {
        totalInputTokens += item.data.input_token?.count || 0;
        totalOutputTokens += item.data.output_token?.count || 0;
      });
    }
  }

  // Get delta from the API response directly
  if (
    response.items.length > 0 &&
    response.items[0].items &&
    response.items[0].items.length > 0
  ) {
    const firstItem = response.items[0].items[0];
    const inputMetricData = firstItem.data.input_token;
    const outputMetricData = firstItem.data.output_token;

    if (inputMetricData?.delta_percent !== undefined) {
      inputDeltaPercentage = inputMetricData.delta_percent;
    }

    if (outputMetricData?.delta_percent !== undefined) {
      outputDeltaPercentage = outputMetricData.delta_percent;
    }
  }

  return {
    input_output_tokens_metrics: {
      summary_metrics: {
        input_tokens_delta_value: totalInputTokens,
        output_tokens_delta_value: totalOutputTokens,
        input_tokens_delta_percentage: inputDeltaPercentage,
        output_tokens_delta_percentage: outputDeltaPercentage,
      },
      items: response.items.slice(0, periodsToDisplay).map((timePeriod) => ({
        time_period: timePeriod.time_period,
        items:
          timePeriod.items && Array.isArray(timePeriod.items)
            ? timePeriod.items.map((item) => ({
                name:
                  item.model_name ||
                  item.project_name ||
                  item.endpoint_name ||
                  item.model_id ||
                  item.project_id ||
                  item.endpoint_id ||
                  "Unknown",
                input_tokens: item.data.input_token?.count || 0,
                output_tokens: item.data.output_token?.count || 0,
              }))
            : [],
      })),
    },
  };
};

// Special converter for performance metrics (throughput/latency/ttft)
const convertPerformanceMetricsResponse = (
  response: ObservabilityMetricsResponse,
  metricType: "throughput" | "latency" | "ttft",
): any => {
  // Calculate summary metrics across all time periods
  const summaryMap = new Map<
    string,
    { total: number; count: number; delta: number }
  >();
  let overallTotal = 0;
  let overallCount = 0;
  let overallDelta = 0;

  // When we have multiple periods (for delta calculation), only use the first half for display
  const periodsToDisplay =
    response.items.length >= 2
      ? Math.ceil(response.items.length / 2)
      : response.items.length;

  for (let i = 0; i < periodsToDisplay; i++) {
    const timePeriod = response.items[i];
    if (timePeriod.items && Array.isArray(timePeriod.items)) {
      timePeriod.items.forEach((item) => {
        const entityName =
          item.project_name ||
          item.model_name ||
          item.endpoint_name ||
          item.model_id ||
          item.project_id ||
          item.endpoint_id ||
          "Unknown";
        const metricData = item.data[metricType];

        let value = 0;
        let delta = metricData?.delta_percent || 0;

        if (metricType === "throughput") {
          value =
            metricData?.avg ||
            metricData?.avg_throughput ||
            metricData?.value ||
            0;
        } else if (metricType === "latency") {
          value =
            metricData?.avg ||
            metricData?.avg_latency_ms ||
            metricData?.value ||
            0;
        } else if (metricType === "ttft") {
          value =
            metricData?.avg ||
            metricData?.avg_ttft_ms ||
            metricData?.value ||
            0;
        }

        if (!summaryMap.has(entityName)) {
          summaryMap.set(entityName, { total: 0, count: 0, delta: 0 });
        }

        const summary = summaryMap.get(entityName)!;
        summary.total += value;
        summary.count += 1;
        summary.delta = delta; // Use the latest delta

        overallTotal += value;
        overallCount += 1;
      });
    }
  }

  // Get delta from the API response directly
  if (
    response.items.length > 0 &&
    response.items[0].items &&
    response.items[0].items.length > 0
  ) {
    // Try to get delta from the first item's metric data
    const firstItem = response.items[0].items[0];
    const metricData = firstItem.data[metricType];
    if (metricData?.delta_percent !== undefined) {
      overallDelta = metricData.delta_percent;
    }
  }

  // Convert summary map to array
  const summaryItems = Array.from(summaryMap.entries()).map(([name, data]) => ({
    name,
    total_value: data.count > 0 ? data.total / data.count : 0, // Average value
    delta_percentage: data.delta,
  }));

  // Calculate overall average
  const overallAverage = overallCount > 0 ? overallTotal / overallCount : 0;

  if (metricType === "throughput") {
    return {
      throughput_metrics: {
        summary_metrics: {
          total_value: overallAverage,
          delta_percentage: overallDelta,
          items: summaryItems,
        },
        items: response.items.slice(0, periodsToDisplay).map((timePeriod) => ({
          time_period: timePeriod.time_period,
          items:
            timePeriod.items && Array.isArray(timePeriod.items)
              ? timePeriod.items.map((item) => ({
                  name:
                    item.project_name ||
                    item.model_name ||
                    item.endpoint_name ||
                    item.model_id ||
                    item.project_id ||
                    item.endpoint_id ||
                    "Unknown",
                  avg_throughput:
                    item.data.throughput?.avg ||
                    item.data.throughput?.avg_throughput ||
                    item.data.throughput?.value ||
                    0,
                  total_value:
                    item.data.throughput?.avg ||
                    item.data.throughput?.avg_throughput ||
                    item.data.throughput?.value ||
                    0,
                }))
              : [],
        })),
      },
    };
  }

  if (metricType === "ttft") {
    return {
      ttft_metrics: {
        summary_metrics: {
          total_value: overallAverage,
          delta_percentage: overallDelta,
          items: summaryItems,
        },
        items: response.items.slice(0, periodsToDisplay).map((timePeriod) => ({
          time_period: timePeriod.time_period,
          items:
            timePeriod.items && Array.isArray(timePeriod.items)
              ? timePeriod.items.map((item) => ({
                  name:
                    item.project_name ||
                    item.model_name ||
                    item.endpoint_name ||
                    item.model_id ||
                    item.project_id ||
                    item.endpoint_id ||
                    "Unknown",
                  avg_ttft_ms:
                    item.data.ttft?.avg ||
                    item.data.ttft?.avg_ttft_ms ||
                    item.data.ttft?.value ||
                    0,
                  total_value:
                    item.data.ttft?.avg ||
                    item.data.ttft?.avg_ttft_ms ||
                    item.data.ttft?.value ||
                    0,
                  ttft_p95:
                    item.data.ttft?.p95 || item.data.ttft?.ttft_p95 || 0,
                  ttft_p99:
                    item.data.ttft?.p99 || item.data.ttft?.ttft_p99 || 0,
                }))
              : [],
        })),
      },
    };
  }

  // Latency response
  return {
    latency_metrics: {
      summary_metrics: {
        total_value: overallAverage,
        delta_percentage: overallDelta,
        items: summaryItems,
      },
      items: response.items.map((timePeriod) => ({
        time_period: timePeriod.time_period,
        items:
          timePeriod.items && Array.isArray(timePeriod.items)
            ? timePeriod.items.map((item) => ({
                name:
                  item.project_name ||
                  item.model_name ||
                  item.endpoint_name ||
                  item.model_id ||
                  item.project_id ||
                  item.endpoint_id ||
                  "Unknown",
                avg_latency_ms:
                  item.data.latency?.avg ||
                  item.data.latency?.avg_latency_ms ||
                  item.data.latency?.value ||
                  0,
                total_value:
                  item.data.latency?.avg ||
                  item.data.latency?.avg_latency_ms ||
                  item.data.latency?.value ||
                  0,
                latency_p95:
                  item.data.latency?.p95 || item.data.latency?.latency_p95 || 0,
                latency_p99:
                  item.data.latency?.p99 || item.data.latency?.latency_p99 || 0,
              }))
            : [],
      })),
    },
  };
};

// Special converter for global metrics
const convertGlobalMetricsResponse = (
  response: ObservabilityMetricsResponse,
): any => {
  // Calculate total value and delta across all items and time periods
  let totalValue = 0;
  let deltaPercentage = 0;

  // When we have multiple periods (for delta calculation), only use the first half for display
  const periodsToDisplay =
    response.items.length >= 2
      ? Math.ceil(response.items.length / 2)
      : response.items.length;

  // For weekly view with daily data, calculate week-over-week change
  if (response.items.length >= 14) {
    // Items are sorted with newest first (index 0)
    // This week: first 7 items (indices 0-6)
    let thisWeekTotal = 0;
    for (let i = 0; i < 7; i++) {
      const timePeriod = response.items[i];
      if (timePeriod.items && Array.isArray(timePeriod.items)) {
        timePeriod.items.forEach((item) => {
          thisWeekTotal += item.data.request_count?.count || 0;
        });
      }
    }

    // Last week: items from index 7 to 13
    let lastWeekTotal = 0;
    for (let i = 7; i < 14; i++) {
      const timePeriod = response.items[i];
      if (timePeriod.items && Array.isArray(timePeriod.items)) {
        timePeriod.items.forEach((item) => {
          lastWeekTotal += item.data.request_count?.count || 0;
        });
      }
    }

    // Calculate week-over-week percentage change
    if (lastWeekTotal > 0) {
      deltaPercentage = ((thisWeekTotal - lastWeekTotal) / lastWeekTotal) * 100;
    } else if (thisWeekTotal > 0) {
      // If last week was 0 but this week has data, show 100% increase
      deltaPercentage = 100;
    }

    totalValue = thisWeekTotal;
  } else {
    // For other cases, get delta from API response if available
    if (
      response.items.length > 0 &&
      response.items[0].items &&
      response.items[0].items.length > 0
    ) {
      const firstItem = response.items[0].items[0];
      const metricData = firstItem.data.request_count;
      if (metricData?.delta_percent !== undefined) {
        deltaPercentage = metricData.delta_percent;
      }
    }

    // Sum only the display periods
    for (let i = 0; i < periodsToDisplay; i++) {
      const timePeriod = response.items[i];
      if (timePeriod.items && Array.isArray(timePeriod.items)) {
        timePeriod.items.forEach((item) => {
          totalValue += item.data.request_count?.count || 0;
        });
      }
    }
  }

  return {
    global_metrics: {
      summary_metrics: {
        total_value: totalValue,
        delta_percentage: deltaPercentage,
      },
      items: response.items.map((timePeriod) => ({
        time_period: timePeriod.time_period,
        items:
          timePeriod.items && Array.isArray(timePeriod.items)
            ? timePeriod.items.map((item) => ({
                total_requests: item.data.request_count?.count || 0,
              }))
            : [],
      })),
    },
  };
};

// Dashboard count metrics converter (for /metrics/count replacement)
export const convertDashboardCountResponse = (response: any): any => {
  // This will need to be adjusted based on the actual new API response format
  // For now, return as-is since /metrics/count might not be part of observability API
  return response;
};

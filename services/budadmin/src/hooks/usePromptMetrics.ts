import { useState, useCallback } from "react";
import { AppRequest } from "../pages/api/requests";
import { tempApiBaseUrl } from "@/components/environment";
import dayjs from "dayjs";

// Types for prompt metrics time-series API
export interface PromptMetricsFilters {
  prompt_id?: string[];
  model_id?: string[];
  project_id?: string[];
  endpoint_id?: string[];
  [key: string]: any;
}

export interface TimeSeriesDataPoint {
  timestamp: string;
  values: Record<string, number>;
}

export interface TimeSeriesGroup {
  model_id?: string;
  model_name?: string;
  project_id?: string;
  project_name?: string;
  endpoint_id?: string;
  endpoint_name?: string;
  api_key_project_id?: string;
  api_key_project_name?: string;
  data_points: TimeSeriesDataPoint[];
}

export interface TimeSeriesResponse {
  object: string;
  message: string;
  groups: TimeSeriesGroup[];
  interval: string;
  date_range: {
    from_date: string;
    to_date: string;
  };
}

export interface PromptMetricsRequest {
  from_date: string;
  to_date: string;
  interval: string;
  metrics: string[];
  filters?: PromptMetricsFilters;
  data_source: "prompt" | "inference";
  fill_gaps?: boolean;
  group_by?: string[];
}

// Types for distribution API
export interface DistributionRequest {
  from_date: string;
  to_date: string;
  bucket_by: "concurrency" | "input_tokens" | "output_tokens";
  metric: string;
  filters?: PromptMetricsFilters;
}

export interface DistributionBucket {
  range: string;
  bucket_start: number;
  bucket_end: number;
  count: number;
  avg_value: number;
  min_value?: number;
  max_value?: number;
  p50_value?: number;
  p95_value?: number;
  p99_value?: number;
}

export interface DistributionResponse {
  object: string;
  message: string;
  bucket_by: string;
  metric: string;
  total_count: number;
  buckets: DistributionBucket[];
  date_range: {
    from_date: string;
    to_date: string;
  };
}

// Available metrics for different chart types
export const PROMPT_METRICS = {
  requests: "requests",
  latency: "avg_latency",
  latency_p95: "p95_latency",
  latency_p99: "p99_latency",
  tokens: "tokens",
  input_tokens: "input_tokens",
  output_tokens: "output_tokens",
  throughput: "throughput",
  ttft: "ttft_avg",
  success_rate: "success_rate",
  error_rate: "error_rate",
  cost: "cost",
  unique_users: "unique_users",
  error_count: "error_count",
  success_count: "success_count",
} as const;

// Distribution metrics for distribution API
export const DISTRIBUTION_METRICS = {
  total_duration_ms: "total_duration_ms",
  ttft_ms: "ttft_ms",
  throughput_per_user: "throughput_per_user",
} as const;

// Bucket types for distribution API
export const DISTRIBUTION_BUCKET_BY = {
  concurrency: "concurrency",
  input_tokens: "input_tokens",
  output_tokens: "output_tokens",
} as const;

// Hook for fetching prompt-specific metrics
export const usePromptMetrics = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Get optimal interval based on time range
  const getOptimalInterval = useCallback(
    (fromDate: dayjs.Dayjs, toDate: dayjs.Dayjs): string => {
      const hoursDiff = toDate.diff(fromDate, "hours");

      if (hoursDiff <= 1) {
        return "1m"; // 1 minute for <= 1 hour
      } else if (hoursDiff <= 6) {
        return "5m"; // 5 minutes for <= 6 hours
      } else if (hoursDiff <= 24) {
        return "1h"; // Hourly for <= 24 hours
      } else if (hoursDiff <= 24 * 7) {
        return "6h"; // 6-hourly for <= 7 days
      } else if (hoursDiff <= 24 * 30) {
        return "1d"; // Daily for <= 30 days
      } else {
        return "1w"; // Weekly for longer periods
      }
    },
    []
  );

  // Fetch time-series data for prompt metrics
  const fetchPromptTimeSeries = useCallback(
    async (
      fromDate: dayjs.Dayjs | string,
      toDate: dayjs.Dayjs | string,
      metrics: string[],
      filters?: PromptMetricsFilters,
      options?: {
        interval?: string;
        dataSource?: "prompt" | "inference";
        fillGaps?: boolean;
        groupBy?: string[];
      }
    ): Promise<TimeSeriesResponse | null> => {
      setIsLoading(true);
      setError(null);

      try {
        const from = dayjs.isDayjs(fromDate) ? fromDate : dayjs(fromDate);
        const to = dayjs.isDayjs(toDate) ? toDate : dayjs(toDate);

        const request: PromptMetricsRequest = {
          from_date: from.toISOString(),
          to_date: to.toISOString(),
          interval: options?.interval || getOptimalInterval(from, to),
          metrics,
          filters,
          data_source: options?.dataSource || "prompt",
          fill_gaps: options?.fillGaps ?? true,
        };

        if (options?.groupBy) {
          request.group_by = options.groupBy;
        }

        const response = await AppRequest.Post(
          `${tempApiBaseUrl}/metrics/time-series`,
          request
        );

        return response.data as TimeSeriesResponse;
      } catch (err: any) {
        console.error("Error fetching prompt time-series data:", err);
        setError(err.message || "Failed to fetch time-series data");
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [getOptimalInterval]
  );

  // Fetch distribution data for prompt metrics
  const fetchDistribution = useCallback(
    async (
      fromDate: dayjs.Dayjs | string,
      toDate: dayjs.Dayjs | string,
      bucketBy: "concurrency" | "input_tokens" | "output_tokens",
      metric: string,
      filters?: PromptMetricsFilters
    ): Promise<DistributionResponse | null> => {
      setIsLoading(true);
      setError(null);

      try {
        const from = dayjs.isDayjs(fromDate) ? fromDate : dayjs(fromDate);
        const to = dayjs.isDayjs(toDate) ? toDate : dayjs(toDate);

        const request: DistributionRequest = {
          from_date: from.toISOString(),
          to_date: to.toISOString(),
          bucket_by: bucketBy,
          metric,
          filters,
        };

        const response = await AppRequest.Post(
          `${tempApiBaseUrl}/metrics/distribution`,
          request
        );

        return response.data as DistributionResponse;
      } catch (err: any) {
        console.error("Error fetching distribution data:", err);
        setError(err.message || "Failed to fetch distribution data");
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  // Helper to transform time-series data for ECharts bar/line chart
  const transformForChart = useCallback(
    (
      response: TimeSeriesResponse | null,
      metricKey: string
    ): { labels: string[]; data: number[]; timestamps: number[] } => {
      if (!response || !response.groups || response.groups.length === 0) {
        return { labels: [], data: [], timestamps: [] };
      }

      // Aggregate data points from all groups
      const aggregatedData: Map<string, number> = new Map();
      const timestampMap: Map<string, number> = new Map();

      response.groups.forEach((group) => {
        group.data_points.forEach((point) => {
          const timestamp = point.timestamp;
          const value = point.values[metricKey] || 0;
          const existing = aggregatedData.get(timestamp) || 0;
          aggregatedData.set(timestamp, existing + value);
          timestampMap.set(timestamp, new Date(timestamp).getTime());
        });
      });

      // Sort by timestamp
      const sortedEntries = Array.from(aggregatedData.entries()).sort(
        (a, b) => new Date(a[0]).getTime() - new Date(b[0]).getTime()
      );

      // Format labels based on interval
      const labels = sortedEntries.map(([timestamp]) => {
        const date = new Date(timestamp);
        const now = new Date();
        const hoursDiff = (now.getTime() - date.getTime()) / (1000 * 60 * 60);

        if (hoursDiff <= 24) {
          // Show HH:mm for data within 24 hours
          return date.toLocaleTimeString("en-US", {
            hour12: false,
            hour: "2-digit",
            minute: "2-digit",
          });
        } else if (hoursDiff <= 24 * 7) {
          // Show day + time for data within 7 days
          return (
            date.toLocaleDateString("en-US", {
              weekday: "short",
            }) +
            " " +
            date.toLocaleTimeString("en-US", {
              hour12: false,
              hour: "2-digit",
              minute: "2-digit",
            })
          );
        } else {
          // Show date for older data
          return date.toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
          });
        }
      });

      const data = sortedEntries.map(([, value]) => value);
      const timestamps = sortedEntries.map(
        ([timestamp]) => new Date(timestamp).getTime()
      );

      return { labels, data, timestamps };
    },
    []
  );

  // Convenience method to fetch requests chart data
  const fetchRequestsChartData = useCallback(
    async (
      promptId: string,
      fromDate: dayjs.Dayjs | string,
      toDate: dayjs.Dayjs | string,
      interval?: string
    ) => {
      const response = await fetchPromptTimeSeries(
        fromDate,
        toDate,
        [PROMPT_METRICS.requests],
        { prompt_id: [promptId] },
        { interval, dataSource: "prompt", fillGaps: true }
      );

      return {
        response,
        chartData: transformForChart(response, PROMPT_METRICS.requests),
      };
    },
    [fetchPromptTimeSeries, transformForChart]
  );

  // Convenience method to fetch latency chart data
  const fetchLatencyChartData = useCallback(
    async (
      promptId: string,
      fromDate: dayjs.Dayjs | string,
      toDate: dayjs.Dayjs | string,
      interval?: string
    ) => {
      const response = await fetchPromptTimeSeries(
        fromDate,
        toDate,
        [PROMPT_METRICS.latency, PROMPT_METRICS.latency_p95],
        { prompt_id: [promptId] },
        { interval, dataSource: "prompt", fillGaps: true }
      );

      return {
        response,
        avgLatency: transformForChart(response, PROMPT_METRICS.latency),
        p95Latency: transformForChart(response, PROMPT_METRICS.latency_p95),
      };
    },
    [fetchPromptTimeSeries, transformForChart]
  );

  // Convenience method to fetch tokens chart data
  const fetchTokensChartData = useCallback(
    async (
      promptId: string,
      fromDate: dayjs.Dayjs | string,
      toDate: dayjs.Dayjs | string,
      interval?: string
    ) => {
      const response = await fetchPromptTimeSeries(
        fromDate,
        toDate,
        [PROMPT_METRICS.tokens, PROMPT_METRICS.input_tokens, PROMPT_METRICS.output_tokens],
        { prompt_id: [promptId] },
        { interval, dataSource: "prompt", fillGaps: true }
      );

      return {
        response,
        totalTokens: transformForChart(response, PROMPT_METRICS.tokens),
        inputTokens: transformForChart(response, PROMPT_METRICS.input_tokens),
        outputTokens: transformForChart(response, PROMPT_METRICS.output_tokens),
      };
    },
    [fetchPromptTimeSeries, transformForChart]
  );

  return {
    fetchPromptTimeSeries,
    fetchDistribution,
    transformForChart,
    fetchRequestsChartData,
    fetchLatencyChartData,
    fetchTokensChartData,
    getOptimalInterval,
    isLoading,
    error,
    PROMPT_METRICS,
    DISTRIBUTION_METRICS,
    DISTRIBUTION_BUCKET_BY,
  };
};

export default usePromptMetrics;

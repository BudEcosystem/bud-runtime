import { useState, useCallback } from 'react';
import { AppRequest } from '@/services/api/requests';
import { tempApiBaseUrl } from '@/components/environment';
import dayjs from 'dayjs';

// Types for aggregated metrics
interface AggregatedMetricsRequest {
  from_date: string;
  to_date?: string;
  group_by?: string[];
  filters?: Record<string, any>;
  metrics: string[];
}

interface TimeSeriesRequest {
  from_date: string;
  to_date?: string;
  interval: string;
  metrics: string[];
  filters?: Record<string, any>;
  group_by?: string[];
  fill_gaps?: boolean;
}

interface GeographyRequest {
  from_date: string;
  to_date?: string;
  filters?: Record<string, any>;
}

interface LatencyDistributionRequest {
  from_date: string;
  to_date?: string;
  filters?: Record<string, any>;
  group_by?: string[];
  buckets?: Array<{min: number; max: number | string; label: string}>;
}

// Hook for fetching aggregated metrics
export const useAggregatedMetrics = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch aggregated metrics (for summary cards, top lists, etc.)
  const fetchAggregatedMetrics = useCallback(async (
    timeRange: [dayjs.Dayjs, dayjs.Dayjs],
    metrics: string[],
    viewBy?: 'model' | 'deployment' | 'project' | 'user',
    filters?: Record<string, any>
  ) => {
    setIsLoading(true);
    setError(null);

    try {
      // Remove date fields from filters to avoid conflicts with root-level dates
      const { from_date, to_date, ...cleanFilters } = filters || {};

      const request: AggregatedMetricsRequest = {
        from_date: timeRange[0].toISOString(),
        to_date: timeRange[1].toISOString(),
        metrics,
        filters: cleanFilters
      };

      // Add grouping based on viewBy
      if (viewBy) {
        const groupByMap = {
          'model': ['model'],
          'deployment': ['endpoint'],
          'project': ['project'],
          'user': ['user']
        };
        request.group_by = groupByMap[viewBy];
      }

      const response = await AppRequest.Post(
        `${tempApiBaseUrl}/metrics/observability/metrics/aggregated`,
        request
      );

      return response.data;
    } catch (err: any) {
      console.error('Error fetching aggregated metrics:', err);
      setError(err.message || 'Failed to fetch aggregated metrics');
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Fetch time-series data (for line charts, temporal data)
  const fetchTimeSeriesData = useCallback(async (
    timeRange: [dayjs.Dayjs, dayjs.Dayjs],
    metrics: string[],
    interval: string = '1h',
    viewBy?: 'model' | 'deployment' | 'project' | 'user',
    filters?: Record<string, any>
  ) => {
    setIsLoading(true);
    setError(null);

    try {
      // Remove date fields from filters to avoid conflicts with root-level dates
      const { from_date, to_date, ...cleanFilters } = filters || {};

      const request: TimeSeriesRequest = {
        from_date: timeRange[0].toISOString(),
        to_date: timeRange[1].toISOString(),
        interval,
        metrics,
        filters: cleanFilters,
        fill_gaps: true
      };

      // Add grouping based on viewBy
      if (viewBy) {
        const groupByMap = {
          'model': ['model'],
          'deployment': ['endpoint'],
          'project': ['project'],
          'user': ['user']
        };
        request.group_by = groupByMap[viewBy];
      }

      const response = await AppRequest.Post(
        `${tempApiBaseUrl}/metrics/observability/metrics/time-series`,
        request
      );

      return response.data;
    } catch (err: any) {
      console.error('Error fetching time-series data:', err);
      setError(err.message || 'Failed to fetch time-series data');
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Fetch geographic distribution data
  const fetchGeographicData = useCallback(async (
    timeRange: [dayjs.Dayjs, dayjs.Dayjs],
    filters?: Record<string, any>
  ) => {
    setIsLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({
        from_date: timeRange[0].toISOString(),
        to_date: timeRange[1].toISOString()
      });

      // Add filters to query params if provided
      if (filters) {
        Object.entries(filters).forEach(([key, value]) => {
          if (Array.isArray(value)) {
            value.forEach(v => params.append(key, v));
          } else {
            params.append(key, value);
          }
        });
      }

      const response = await AppRequest.Get(
        `${tempApiBaseUrl}/metrics/observability/metrics/geography?${params.toString()}`
      );

      return response.data;
    } catch (err: any) {
      console.error('Error fetching geographic data:', err);
      setError(err.message || 'Failed to fetch geographic data');
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Fetch latency distribution data
  const fetchLatencyDistribution = useCallback(async (
    timeRange: [dayjs.Dayjs, dayjs.Dayjs],
    viewBy?: 'model' | 'deployment' | 'project' | 'user',
    filters?: Record<string, any>
  ) => {
    setIsLoading(true);
    setError(null);

    try {
      // Remove date fields from filters to avoid conflicts with root-level dates
      const { from_date, to_date, ...cleanFilters } = filters || {};

      const request: LatencyDistributionRequest = {
        from_date: timeRange[0].toISOString(),
        to_date: timeRange[1].toISOString(),
        filters: cleanFilters
      };

      // Add grouping based on viewBy
      if (viewBy) {
        const groupByMap = {
          'model': ['model'],
          'deployment': ['endpoint'],
          'project': ['project'],
          'user': ['user']
        };
        request.group_by = groupByMap[viewBy];
      }

      const response = await AppRequest.Post(
        `${tempApiBaseUrl}/metrics/latency-distribution`,
        request
      );

      return response.data;
    } catch (err: any) {
      console.error('Error fetching latency distribution:', err);
      setError(err.message || 'Failed to fetch latency distribution');
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Helper function to determine the best interval based on time range
  const getOptimalInterval = (timeRange: [dayjs.Dayjs, dayjs.Dayjs]): string => {
    const hoursDiff = timeRange[1].diff(timeRange[0], 'hours');

    if (hoursDiff <= 24) {
      return '1h';  // Hourly for last 24 hours
    } else if (hoursDiff <= 24 * 7) {
      return '6h';  // 6-hourly for last week
    } else if (hoursDiff <= 24 * 30) {
      return '1d';  // Daily for last month
    } else {
      return '1w';  // Weekly for longer periods
    }
  };

  // Fetch all metrics needed for MetricsTab
  const fetchMetricsTabData = useCallback(async (
    timeRange: [dayjs.Dayjs, dayjs.Dayjs],
    viewBy: 'model' | 'deployment' | 'project' | 'user',
    filters?: Record<string, any>
  ) => {
    setIsLoading(true);
    setError(null);

    try {
      const interval = getOptimalInterval(timeRange);

      // Parallel fetch all required data
      const [
        summaryMetrics,
        requestsTimeSeries,
        latencyTimeSeries,
        tokensTimeSeries,
        throughputTimeSeries,
        ttftTimeSeries,
        topEntities,
        latencyDistribution,
        geographicData
      ] = await Promise.all([
        // Summary metrics for cards
        fetchAggregatedMetrics(
          timeRange,
          ['total_requests', 'success_rate', 'avg_latency', 'p95_latency', 'p99_latency',
           'total_tokens', 'avg_cost', 'throughput_avg', 'ttft_avg', 'ttft_p95'],
          undefined, // No grouping for summary
          filters
        ),
        // Time series for request volume
        fetchTimeSeriesData(timeRange, ['requests'], interval, viewBy, filters),
        // Time series for latency
        fetchTimeSeriesData(timeRange, ['avg_latency', 'p95_latency', 'p99_latency'], interval, viewBy, filters),
        // Time series for tokens
        fetchTimeSeriesData(timeRange, ['tokens'], interval, viewBy, filters),
        // Time series for throughput
        fetchTimeSeriesData(timeRange, ['throughput'], interval, viewBy, filters),
        // Time series for TTFT
        fetchTimeSeriesData(timeRange, ['ttft_avg'], interval, viewBy, filters),
        // Top entities (models/projects/endpoints)
        fetchAggregatedMetrics(timeRange, ['total_requests'], viewBy, filters),
        // Latency distribution using new dedicated endpoint
        fetchLatencyDistribution(timeRange, viewBy, filters),
        // Geographic distribution
        fetchGeographicData(timeRange, filters)
      ]);

      return {
        summaryMetrics,
        requestsTimeSeries,
        latencyTimeSeries,
        tokensTimeSeries,
        throughputTimeSeries,
        ttftTimeSeries,
        topEntities,
        latencyDistribution,
        geographicData
      };
    } catch (err: any) {
      console.error('Error fetching metrics tab data:', err);
      setError(err.message || 'Failed to fetch metrics data');
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [fetchAggregatedMetrics, fetchTimeSeriesData, fetchGeographicData, fetchLatencyDistribution]);

  return {
    fetchAggregatedMetrics,
    fetchTimeSeriesData,
    fetchGeographicData,
    fetchLatencyDistribution,
    fetchMetricsTabData,
    isLoading,
    error
  };
};

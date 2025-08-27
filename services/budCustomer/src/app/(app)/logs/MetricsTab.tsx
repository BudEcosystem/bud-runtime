import React, { useEffect, useState, useMemo } from 'react';
import { Row, Col, Empty, Progress, List, Typography, Tooltip } from 'antd';
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  DollarOutlined,
  RocketOutlined,
  ApiOutlined,
  GlobalOutlined,
  ThunderboltOutlined
} from '@ant-design/icons';
import * as echarts from 'echarts';
import { InferenceListItem } from '@/stores/useInferences';
import {
  Text_12_400_EEEEEE,
  Text_14_600_EEEEEE,
  Text_16_600_FFFFFF,
  Text_12_400_B3B3B3,
  Text_12_500_FFFFFF,
  Text_19_600_EEEEEE,
  Text_26_400_EEEEEE,
  Text_22_700_EEEEEE,
  Text_14_400_EEEEEE,
  Text_13_400_757575
} from '@/components/ui/text';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';

// Extend dayjs with UTC and timezone support
dayjs.extend(utc);
dayjs.extend(timezone);
import BarChart from '@/components/charts/barChart';
import LineChartCustom from '@/components/charts/lineChart/LineChartCustom';
import MultiSeriesLineChart from '@/components/charts/MultiSeriesLineChart';
import GroupedBarChart from '@/components/charts/GroupedBarChart';
import GeoMapChart from '@/components/charts/GeoMapChart';
import { Flex } from '@radix-ui/themes';
import { useAggregatedMetrics } from '@/hooks/useAggregatedMetrics';
import { useTheme } from '@/context/themeContext';

const { Text } = Typography;

// Custom chart component wrapper for consistent styling
function ChartCard({ title, subtitle, children, height = '23.664375rem' }: { title: string; subtitle?: string; children: React.ReactNode; height?: string }) {
  return (
    <div
      className={`p-[1.55rem] py-[2rem] rounded-[6.403px] border-[1.067px] w-full h-[${height}] flex items-center justify-between flex-col`}
      style={{
        backgroundColor: 'var(--bg-card)',
        borderColor: 'var(--border-color)',
        boxShadow: 'var(--shadow-sm)',
      }}
    >
      <div className="flex items-center w-full flex-col">
        <Text_19_600_EEEEEE className="mb-[1.3rem] w-full !text-[var(--text-primary)]">
          {title}
        </Text_19_600_EEEEEE>
        {subtitle && (
          <Text_13_400_757575 className='w-full mb-4 !text-[var(--text-muted)]'>
            {subtitle}
          </Text_13_400_757575>
        )}
      </div>
      <div className="flex-1 w-full">
        {children}
      </div>
    </div>
  );
}

// Metric card component for key metrics
function MetricCard({ icon, title, value, subtitle, valueColor = 'var(--text-primary)', showProgress = false, progressValue = 0, progressColor = '#3F8EF7' }: any) {
  return (
    <div
      className="p-[1.45rem] pb-[1.2rem] rounded-[6.403px] border-[1.067px] min-h-[7.8125rem] flex flex-col items-start justify-between"
      style={{
        backgroundColor: 'var(--bg-card)',
        borderColor: 'var(--border-color)',
        boxShadow: 'var(--shadow-sm)',
      }}
    >
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <Text_12_500_FFFFFF className="!text-[var(--text-primary)]">{title}</Text_12_500_FFFFFF>
      </div>
      <div className="flex flex-col w-full">
        <Text_22_700_EEEEEE style={{ color: valueColor }} className="!text-[var(--text-primary)]">
          {value}
        </Text_22_700_EEEEEE>
        {subtitle && (
          <Text_12_400_B3B3B3 className="mt-2 !text-[var(--text-muted)]">{subtitle}</Text_12_400_B3B3B3>
        )}
        {showProgress && (
          <Progress
            percent={progressValue}
            showInfo={false}
            strokeColor={progressColor}
            trailColor="var(--border-secondary)"
            className="mt-2"
          />
        )}
      </div>
    </div>
  );
}

interface MetricsTabProps {
  timeRange: [dayjs.Dayjs, dayjs.Dayjs];
  inferences: InferenceListItem[];
  isLoading: boolean;
  viewBy: 'model' | 'deployment' | 'project' | 'user';
  isActive?: boolean;
  filters?: Record<string, any>;
}

interface MetricStats {
  totalRequests: number;
  successRate: number;
  failureRate: number;
  avgLatency: number;
  p95Latency: number;
  p99Latency: number;
  totalCost: number;
  totalTokens: number;
  totalInputTokens: number;
  totalOutputTokens: number;
  requestsPerHour: number;
  avgTTFT: number;
  p95TTFT: number;
  topModels: { model: string; count: number; percentage: number }[];
  topProjects: { project: string; count: number; percentage: number }[];
  topEndpoints: { endpoint: string; count: number; percentage: number }[];
  hourlyDistribution: { hour: string; count: number }[];
  latencyDistribution: { range: string; count: number }[];
  errorTypes: { type: string; count: number }[];
  // Grouped data for charts based on viewBy selection
  groupedHourlyData: { [key: string]: { hour: string; count: number }[] };
  groupedLatencyData: { [key: string]: { range: string; count: number }[] };
  // Time series data for new charts (aggregated)
  latencyOverTime: { time: string; avg: number; p95: number; p99: number }[];
  tokensOverTime: { time: string; input: number; output: number }[];
  requestsPerSecond: { time: string; rps: number }[];
  ttftOverTime: { time: string; avg: number; p95: number }[];
  // Grouped time series data based on viewBy
  groupedLatencyOverTime: { [key: string]: { time: string; avg: number; p95: number; p99: number }[] };
  groupedTokensOverTime: { [key: string]: { time: string; input: number; output: number }[] };
  groupedRequestsPerSecond: { [key: string]: { time: string; rps: number }[] };
  groupedTTFTOverTime: { [key: string]: { time: string; value: number }[] };
}


const MetricsTab: React.FC<MetricsTabProps> = ({ timeRange, inferences, isLoading, viewBy, isActive, filters }) => {
  const { effectiveTheme } = useTheme();
  const { fetchMetricsTabData, isLoading: metricsLoading, error: metricsError } = useAggregatedMetrics();
  const [serverMetrics, setServerMetrics] = useState<any>(null);
  const [geographicData, setGeographicData] = useState<any>(null);

  // Trigger ECharts resize when tab becomes active
  useEffect(() => {
    let timeoutId: NodeJS.Timeout;

    if (isActive) {
      // Small delay to ensure the tab content is fully visible
      timeoutId = setTimeout(() => {
        // Trigger resize event to force all ECharts instances to recalculate
        window.dispatchEvent(new Event('resize'));
      }, 100);
    }

    // Cleanup timeout on unmount or when isActive changes
    return () => {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, [isActive]);

  // Fetch server-side aggregated metrics with cleanup
  useEffect(() => {
    let isMounted = true;

    const fetchMetrics = async () => {
      if (timeRange && viewBy) {
        try {
          // Only pass non-date filters to avoid conflicts
          const { from_date, to_date, sort_by, sort_order, ...relevantFilters } = filters || {};
          const data = await fetchMetricsTabData(timeRange, viewBy, relevantFilters);
          // Only update state if component is still mounted
          if (isMounted && data) {
            setServerMetrics(data);
            setGeographicData(data.geographicData || null);
          }
        } catch (error) {
          // Only log error if component is still mounted
          if (isMounted) {
            console.error('Error fetching metrics:', error);
            // Don't clear data on error to prevent UI flashing
          }
        }
      }
    };

    fetchMetrics();

    // Cleanup function to prevent state updates on unmounted component
    return () => {
      isMounted = false;
    };
  }, [timeRange, viewBy, filters]);

  // Color palette for consistent colors across charts
  const colorPalette = [
    '#3F8EF7', '#965CDE', '#FFC442', '#52C41A', '#FF6B6B',
    '#4ECDC4', '#A8E6CF', '#FFD93D', '#FF8CC6', '#95E1D3',
    '#6B5B95', '#88B0D3', '#FF6F61', '#5B9BD5', '#70AD47'
  ];

  // Create a consistent color mapping for entities
  const getEntityColor = useMemo(() => {
    const colorMap = new Map<string, string>();
    let colorIndex = 0;

    return (entityName: string): string => {
      if (!colorMap.has(entityName)) {
        colorMap.set(entityName, colorPalette[colorIndex % colorPalette.length]);
        colorIndex++;
      }
      return colorMap.get(entityName)!;
    };
  }, []);

  // Function to process server metrics into the format expected by charts
  const processServerMetrics = (data: any, viewBy: string, inferenceData?: InferenceListItem[]): MetricStats => {
    const {
      summaryMetrics,
      requestsTimeSeries,
      latencyTimeSeries,
      tokensTimeSeries,
      throughputTimeSeries,
      ttftTimeSeries,
      topEntities,
      latencyDistribution,
      geographicData
    } = data;

    // Extract summary values
    const totalRequests = summaryMetrics?.summary?.total_requests?.value || 0;
    const successRate = summaryMetrics?.summary?.success_rate?.value || 0;
    const failureRate = 100 - successRate;
    const avgLatency = summaryMetrics?.summary?.avg_latency?.value || 0;
    const p95Latency = summaryMetrics?.summary?.p95_latency?.value || 0;
    const p99Latency = summaryMetrics?.summary?.p99_latency?.value || 0;
    const totalCost = summaryMetrics?.summary?.total_cost?.value || 0;
    const totalTokens = summaryMetrics?.summary?.total_tokens?.value || 0;
    const avgTTFT = summaryMetrics?.summary?.ttft_avg?.value || 0;
    const p95TTFT = summaryMetrics?.summary?.ttft_p95?.value || 0;
    const throughputAvg = summaryMetrics?.summary?.throughput_avg?.value || 0;

    // Calculate requests per hour from time range
    const hoursInRange = timeRange[1].diff(timeRange[0], 'hours') || 1;
    const requestsPerHour = totalRequests / hoursInRange;

    // Process time series data for charts
    const processTimeSeries = (tsData: any, metricName: string) => {
      // Check if we have grouped data
      if (tsData?.groups && tsData.groups.length > 0) {
        // Aggregate all groups' data points
        const allPoints: any[] = [];
        const pointsMap = new Map<string, { sum: number; count: number }>();

        // Determine the format based on interval
        const interval = tsData.interval || '1h';
        let timeFormat: string;
        if (interval === '1w') {
          timeFormat = 'MMM DD';  // Week: "Jan 15"
        } else if (interval === '1d') {
          timeFormat = 'MM/DD';   // Day: "01/15"
        } else if (interval === '6h' || interval === '12h') {
          timeFormat = 'MM/DD HH:mm';  // 6h/12h: "01/15 18:00"
        } else if (interval === '1h' || interval === '30m' || interval === '15m' || interval === '5m' || interval === '1m') {
          timeFormat = 'HH:mm';   // Hour or less: "18:30"
        } else {
          timeFormat = 'HH:mm';   // Default format
        }

        tsData.groups.forEach((group: any) => {
          group.data_points?.forEach((point: any) => {
            // Parse as UTC and convert to local time for display
            const time = dayjs.utc(point.timestamp).local().format(timeFormat);
            const value = point.values?.[metricName];

            // Only process non-null values
            if (value !== null && value !== undefined) {
              if (pointsMap.has(time)) {
                const existing = pointsMap.get(time)!;
                pointsMap.set(time, {
                  sum: existing.sum + value,
                  count: existing.count + 1
                });
              } else {
                pointsMap.set(time, { sum: value, count: 1 });
              }
            }
          });
        });

        // Convert map to array, calculating averages
        return Array.from(pointsMap.entries()).map(([time, data]) => ({
          time,
          value: data.count > 0 ? data.sum / data.count : 0
        })).sort((a, b) => a.time.localeCompare(b.time));
      }

      // Fallback to old structure if it exists
      if (tsData?.series && tsData.series.length > 0) {
        // Determine the format based on interval
        const interval = tsData.interval || '1h';
        let timeFormat: string;
        if (interval === '1w') {
          timeFormat = 'MMM DD';
        } else if (interval === '1d') {
          timeFormat = 'MM/DD';
        } else if (interval === '6h' || interval === '12h') {
          timeFormat = 'MM/DD HH:mm';
        } else {
          timeFormat = 'HH:mm';
        }

        return tsData.series.map((point: any) => ({
          time: dayjs.utc(point.timestamp).local().format(timeFormat),
          value: point.values?.[metricName] || 0
        }));
      }

      return [];
    };

    // Helper function to generate all time points in a range
    const generateTimePoints = (startTime: dayjs.Dayjs, endTime: dayjs.Dayjs, interval: string) => {
      const timePoints: string[] = [];

      // Determine the format based on interval
      let timeFormat: string;
      let unitToAdd: any;
      let amountToAdd: number;
      let startUnit: any;

      if (interval === '1w') {
        timeFormat = 'MMM DD';
        unitToAdd = 'week';
        amountToAdd = 1;
        startUnit = 'week';
      } else if (interval === '1d') {
        timeFormat = 'MM/DD';
        unitToAdd = 'day';
        amountToAdd = 1;
        startUnit = 'day';
      } else if (interval === '6h') {
        timeFormat = 'MM/DD HH:mm';
        unitToAdd = 'hour';
        amountToAdd = 6;
        startUnit = 'hour';
      } else if (interval === '12h') {
        timeFormat = 'MM/DD HH:mm';
        unitToAdd = 'hour';
        amountToAdd = 12;
        startUnit = 'hour';
      } else {
        timeFormat = 'HH:mm';
        unitToAdd = 'hour';
        amountToAdd = 1;
        startUnit = 'hour';
      }

      let current = startTime.startOf(startUnit);

      while (current.isBefore(endTime) || current.isSame(endTime)) {
        timePoints.push(current.format(timeFormat));
        current = current.add(amountToAdd, unitToAdd);
      }

      return timePoints;
    };

    // Process grouped time series for multi-series charts
    const processGroupedTimeSeries = (tsData: any, metricName: string) => {
      const grouped: { [key: string]: any[] } = {};

      // Check if we have groups in the new structure
      if (tsData?.groups && tsData.groups.length > 0) {
        // Determine the format based on interval
        const interval = tsData.interval || '1h';
        let timeFormat: string;
        if (interval === '1w') {
          timeFormat = 'MMM DD';  // Week: "Jan 15"
        } else if (interval === '1d') {
          timeFormat = 'MM/DD';   // Day: "01/15"
        } else if (interval === '6h' || interval === '12h') {
          timeFormat = 'MM/DD HH:mm';  // 6h/12h: "01/15 18:00"
        } else if (interval === '1h' || interval === '30m' || interval === '15m' || interval === '5m' || interval === '1m') {
          timeFormat = 'HH:mm';   // Hour or less: "18:30"
        } else {
          timeFormat = 'HH:mm';   // Default format
        }

        // Collect all actual time points from the data
        // This ensures we use the exact times that exist in the data
        const uniqueTimes = new Set<string>();
        tsData.groups.forEach((group: any) => {
          group.data_points?.forEach((point: any) => {
            uniqueTimes.add(dayjs.utc(point.timestamp).local().format(timeFormat));
          });
        });
        const allTimePoints = Array.from(uniqueTimes).sort();

        tsData.groups.forEach((group: any) => {
          // Create a key for the group based on available identifiers
          const groupKey = group.model_name || group.project_name || group.endpoint_name || 'Unknown';

          // Create a map of existing data points
          const dataMap = new Map<string, number>();
          group.data_points?.forEach((point: any) => {
            const time = dayjs.utc(point.timestamp).local().format(timeFormat);
            const value = point.values?.[metricName];
            // Only set if value is not null
            if (value !== null && value !== undefined) {
              dataMap.set(time, value);
            }
          });

          // Fill in all time points with data or 0
          grouped[groupKey] = allTimePoints.map(time => ({
            time,
            value: dataMap.get(time) || 0
          }));
        });

        return grouped;
      }

      // Fallback to old structure if it exists
      if (tsData?.grouped_series) {
        // Determine the format based on interval
        const interval = tsData.interval || '1h';
        let timeFormat: string;
        if (interval === '1w') {
          timeFormat = 'MMM DD';
        } else if (interval === '1d') {
          timeFormat = 'MM/DD';
        } else if (interval === '6h' || interval === '12h') {
          timeFormat = 'MM/DD HH:mm';
        } else {
          timeFormat = 'HH:mm';
        }

        Object.entries(tsData.grouped_series).forEach(([groupKey, series]: [string, any]) => {
          grouped[groupKey] = series.map((point: any) => ({
            time: dayjs(point.timestamp).format(timeFormat),
            value: point.values[metricName] || 0
          }));
        });
      }

      return grouped;
    };

    // Process top entities
    const processTopEntities = (entitiesData: any) => {
      if (!entitiesData?.groups || entitiesData.groups.length === 0) return [];

      return entitiesData.groups
        .map((group: any) => {
          // Get the name based on what's available in the group
          const name = group.model_name || group.project_name || group.endpoint_name || 'Unknown';
          const count = group.metrics?.total_requests?.value || 0;

          return {
            name,
            count,
            percentage: totalRequests > 0 ? (count / totalRequests * 100) : 0
          };
        })
        .sort((a: any, b: any) => b.count - a.count)
        .slice(0, 5);
    };

    // Build top lists based on viewBy
    let topModels: any[] = [];
    let topProjects: any[] = [];
    let topEndpoints: any[] = [];

    const topList = processTopEntities(topEntities);

    if (viewBy === 'model') {
      topModels = topList.map((item: any) => ({ model: item.name, ...item }));
    } else if (viewBy === 'project') {
      topProjects = topList.map((item: any) => ({ project: item.name, ...item }));
    } else if (viewBy === 'deployment') {
      topEndpoints = topList.map((item: any) => ({ endpoint: item.name, ...item }));
    }

    // Process hourly distribution - always show 24-hour view for Request Volume Over Time
    // This chart should always show hourly distribution regardless of the time range
    let hourlyDistribution: { hour: string; count: number }[] = [];

    if (requestsTimeSeries?.groups && requestsTimeSeries.groups.length > 0) {
      // Aggregate by hour of day (0-23) across all days in the range
      const hourlyMap = new Map<number, number>();

      requestsTimeSeries.groups.forEach((group: any) => {
        group.data_points?.forEach((point: any) => {
          const hour = dayjs.utc(point.timestamp).local().hour();
          const count = point.values?.requests || 0;
          hourlyMap.set(hour, (hourlyMap.get(hour) || 0) + count);
        });
      });

      // Create array for all 24 hours
      hourlyDistribution = Array.from({ length: 24 }, (_, hour) => ({
        hour: `${hour.toString().padStart(2, '0')}:00`,
        count: hourlyMap.get(hour) || 0
      }));
    } else if (requestsTimeSeries?.series) {
      // Fallback to old structure
      const hourlyMap = new Map<number, number>();

      requestsTimeSeries.series.forEach((point: any) => {
        const hour = dayjs(point.timestamp).hour();
        const count = point.values?.requests || 0;
        hourlyMap.set(hour, (hourlyMap.get(hour) || 0) + count);
      });

      hourlyDistribution = Array.from({ length: 24 }, (_, hour) => ({
        hour: `${hour.toString().padStart(2, '0')}:00`,
        count: hourlyMap.get(hour) || 0
      }));
    }

    // Ensure we always have 24 hours
    const allHours = hourlyDistribution.length > 0 ? hourlyDistribution :
      Array.from({ length: 24 }, (_, i) => ({
        hour: `${i.toString().padStart(2, '0')}:00`,
        count: 0
      }));

    // Process latency distribution from new API response
    let simpleLatencyDistribution;
    if (latencyDistribution?.overall_distribution && latencyDistribution.overall_distribution.length > 0) {
      // Use data from the new latency distribution endpoint
      simpleLatencyDistribution = latencyDistribution.overall_distribution.map((bucket: any) => ({
        range: bucket.range,
        count: bucket.count
      }));
    } else if (inferenceData && inferenceData.length > 0) {
      // Fallback to client-side calculation if API data not available
      const latencyRanges = [
        { min: 0, max: 100, label: '0-100ms' },
        { min: 100, max: 500, label: '100-500ms' },
        { min: 500, max: 1000, label: '500ms-1s' },
        { min: 1000, max: 2000, label: '1-2s' },
        { min: 2000, max: 5000, label: '2-5s' },
        { min: 5000, max: 10000, label: '5-10s' },
        { min: 10000, max: Infinity, label: '>10s' },
      ];

      const latencies = inferenceData
        .map(i => i.response_time_ms)
        .filter(l => l != null);

      simpleLatencyDistribution = latencyRanges.map(range => ({
        range: range.label,
        count: latencies.filter(l => l >= range.min && l < range.max).length
      }));
    } else {
      // Default empty distribution with new bucket structure
      simpleLatencyDistribution = [
        { range: '0-100ms', count: 0 },
        { range: '100-500ms', count: 0 },
        { range: '500ms-1s', count: 0 },
        { range: '1-2s', count: 0 },
        { range: '2-5s', count: 0 },
        { range: '5-10s', count: 0 },
        { range: '>10s', count: 0 },
      ];
    }

    // Process grouped hourly data - always aggregate by hour of day for Request Volume Over Time
    const groupedHourlyData: { [key: string]: any[] } = {};

    if (requestsTimeSeries?.groups && requestsTimeSeries.groups.length > 0) {
      requestsTimeSeries.groups.forEach((group: any) => {
        const groupKey = group.model_name || group.project_name || group.endpoint_name || 'Unknown';
        const hourlyMap = new Map<number, number>();

        group.data_points?.forEach((point: any) => {
          const hour = dayjs.utc(point.timestamp).local().hour();
          const count = point.values?.requests || 0;
          hourlyMap.set(hour, (hourlyMap.get(hour) || 0) + count);
        });

        // Create array for all 24 hours for this group
        groupedHourlyData[groupKey] = Array.from({ length: 24 }, (_, hour) => ({
          hour: `${hour.toString().padStart(2, '0')}:00`,
          count: hourlyMap.get(hour) || 0
        }));
      });
    }

    // Process grouped latency distribution from new API response
    const groupedLatencyData: { [key: string]: { range: string; count: number }[] } = {};

    if (latencyDistribution?.groups && latencyDistribution.groups.length > 0) {
      // Use data from the new latency distribution endpoint
      latencyDistribution.groups.forEach((group: any) => {
        // Determine group key based on available identifiers
        let groupKey = 'Unknown';
        if (group.model_name) {
          groupKey = group.model_name;
        } else if (group.project_name) {
          groupKey = group.project_name;
        } else if (group.endpoint_name) {
          groupKey = group.endpoint_name;
        } else if (group.user_id) {
          groupKey = group.user_id;
        }

        groupedLatencyData[groupKey] = group.buckets.map((bucket: any) => ({
          range: bucket.range,
          count: bucket.count
        }));
      });
    } else if (inferenceData && inferenceData.length > 0 && viewBy) {
      // Fallback to client-side calculation if API data not available
      const latencyRanges = [
        { min: 0, max: 100, label: '0-100ms' },
        { min: 100, max: 500, label: '100-500ms' },
        { min: 500, max: 1000, label: '500ms-1s' },
        { min: 1000, max: 2000, label: '1-2s' },
        { min: 2000, max: 5000, label: '2-5s' },
        { min: 5000, max: 10000, label: '5-10s' },
        { min: 10000, max: Infinity, label: '>10s' },
      ];

      // Group inferences by the selected viewBy dimension
      const groupedInferences: { [key: string]: InferenceListItem[] } = {};

      inferenceData.forEach(inference => {
        let groupKey = 'Unknown';
        switch (viewBy) {
          case 'model':
            groupKey = inference.model_display_name || inference.model_name || 'Unknown';
            break;
          case 'deployment':
            groupKey = inference.endpoint_name || 'Unknown';
            break;
          case 'project':
            groupKey = inference.project_name || 'Unknown';
            break;
          case 'user':
            groupKey = inference.project_name || 'Unknown'; // Using project as proxy for user
            break;
        }

        if (!groupedInferences[groupKey]) {
          groupedInferences[groupKey] = [];
        }
        groupedInferences[groupKey].push(inference);
      });

      // Calculate distribution for each group
      Object.entries(groupedInferences).forEach(([groupKey, inferences]) => {
        const latencies = inferences
          .map(i => i.response_time_ms)
          .filter(l => l != null);

        groupedLatencyData[groupKey] = latencyRanges.map(range => ({
          range: range.label,
          count: latencies.filter(l => l >= range.min && l < range.max).length
        }));
      });
    }

    // Process time series for new charts
    // For latency, we need to handle the multi-metric response
    let latencyOverTime: any[] = [];
    if (latencyTimeSeries?.groups && latencyTimeSeries.groups.length > 0) {
      // Aggregate latency data across all groups
      const timeMap = new Map<string, { avg: number[], p95: number[], p99: number[] }>();

      // Determine the format based on interval
      const interval = latencyTimeSeries.interval || '1h';
      let timeFormat: string;
      if (interval === '1w') {
        timeFormat = 'MMM DD';
      } else if (interval === '1d') {
        timeFormat = 'MM/DD';
      } else if (interval === '6h' || interval === '12h') {
        timeFormat = 'MM/DD HH:mm';
      } else {
        timeFormat = 'HH:mm';
      }

      latencyTimeSeries.groups.forEach((group: any) => {
        group.data_points?.forEach((point: any) => {
          const time = dayjs.utc(point.timestamp).local().format(timeFormat);
          if (!timeMap.has(time)) {
            timeMap.set(time, { avg: [], p95: [], p99: [] });
          }
          const data = timeMap.get(time)!;
          if (point.values?.avg_latency != null) data.avg.push(point.values.avg_latency);
          if (point.values?.p95_latency != null) data.p95.push(point.values.p95_latency);
          if (point.values?.p99_latency != null) data.p99.push(point.values.p99_latency);
        });
      });

      latencyOverTime = Array.from(timeMap.entries()).map(([time, data]) => ({
        time,
        avg: data.avg.length > 0 ? data.avg.reduce((a, b) => a + b, 0) / data.avg.length : 0,
        p95: data.p95.length > 0 ? Math.max(...data.p95) : 0,
        p99: data.p99.length > 0 ? Math.max(...data.p99) : 0
      })).sort((a, b) => a.time.localeCompare(b.time));
    }

    // Process tokens data - might be empty if metric not available
    const tokensOverTime = processTimeSeries(tokensTimeSeries, 'tokens')
      .map((item: any) => ({
        time: item.time,
        input: item.value / 2, // Approximate split
        output: item.value / 2
      }));

    // Process requests per second - might be empty if metric not available
    const requestsPerSecond = processTimeSeries(throughputTimeSeries, 'throughput')
      .map((item: any) => ({
        time: item.time,
        rps: item.value || 0
      }));

    // Process TTFT data - might be empty if metric not available
    const ttftOverTime = processTimeSeries(ttftTimeSeries, 'ttft_avg')
      .map((item: any, idx: any) => ({
        time: item.time,
        avg: item.value || 0,
        p95: ttftTimeSeries?.series?.[idx]?.values?.ttft_p95 || 0
      }));

    // Process grouped time series
    const groupedLatencyOverTime = processGroupedTimeSeries(latencyTimeSeries, 'avg_latency');
    const groupedTokensOverTime = processGroupedTimeSeries(tokensTimeSeries, 'tokens');
    const groupedRequestsPerSecondRaw = processGroupedTimeSeries(throughputTimeSeries, 'throughput');
    const groupedTTFTOverTime = processGroupedTimeSeries(ttftTimeSeries, 'ttft_avg');

    // Transform grouped RPS data to have 'rps' property instead of 'value'
    const groupedRequestsPerSecond: { [key: string]: any[] } = {};
    Object.entries(groupedRequestsPerSecondRaw).forEach(([key, data]) => {
      groupedRequestsPerSecond[key] = data.map((item: any) => ({
        time: item.time,
        rps: item.value || 0
      }));
    });

    return {
      totalRequests,
      successRate,
      failureRate,
      avgLatency,
      p95Latency,
      p99Latency,
      totalCost,
      totalTokens,
      totalInputTokens: totalTokens / 2, // Approximate
      totalOutputTokens: totalTokens / 2,
      requestsPerHour,
      avgTTFT,
      p95TTFT,
      topModels,
      topProjects,
      topEndpoints,
      hourlyDistribution: allHours,
      latencyDistribution: simpleLatencyDistribution,
      errorTypes: [],
      groupedHourlyData,
      groupedLatencyData,
      latencyOverTime,
      tokensOverTime,
      requestsPerSecond,
      ttftOverTime,
      groupedLatencyOverTime,
      groupedTokensOverTime,
      groupedRequestsPerSecond,
      groupedTTFTOverTime,
    };
  };

  // Calculate metrics from server data or fallback to client-side calculation
  const metrics = useMemo<MetricStats>(() => {
    // If we have server-side metrics, use those
    if (serverMetrics) {
      const processed = processServerMetrics(serverMetrics, viewBy);
      return processed;
    }

    // Fallback to client-side calculation from inferences
    if (!inferences || inferences.length === 0) {
      return {
        totalRequests: 0,
        successRate: 0,
        failureRate: 0,
        avgLatency: 0,
        p95Latency: 0,
        p99Latency: 0,
        totalCost: 0,
        totalTokens: 0,
        totalInputTokens: 0,
        totalOutputTokens: 0,
        requestsPerHour: 0,
        avgTTFT: 0,
        p95TTFT: 0,
        topModels: [],
        topProjects: [],
        topEndpoints: [],
        hourlyDistribution: [],
        latencyDistribution: [],
        errorTypes: [],
        groupedHourlyData: {},
        groupedLatencyData: {},
        latencyOverTime: [],
        tokensOverTime: [],
        requestsPerSecond: [],
        ttftOverTime: [],
        groupedLatencyOverTime: {},
        groupedTokensOverTime: {},
        groupedRequestsPerSecond: {},
        groupedTTFTOverTime: {},
      };
    }

    const totalRequests = inferences.length;
    const successfulRequests = inferences.filter(i => i.is_success).length;
    const failedRequests = totalRequests - successfulRequests;
    const successRate = (successfulRequests / totalRequests) * 100;
    const failureRate = (failedRequests / totalRequests) * 100;

    // Calculate latency metrics
    const latencies = inferences
      .map(i => i.response_time_ms)
      .filter(l => l != null)
      .sort((a, b) => a - b);

    const avgLatency = latencies.length > 0
      ? latencies.reduce((a, b) => a + b, 0) / latencies.length
      : 0;

    const p95Index = Math.floor(latencies.length * 0.95);
    const p99Index = Math.floor(latencies.length * 0.99);
    const p95Latency = latencies[p95Index] || 0;
    const p99Latency = latencies[p99Index] || 0;

    // Calculate cost and tokens
    const totalCost = inferences.reduce((sum, i) => sum + (i.cost || 0), 0);
    const totalTokens = inferences.reduce((sum, i) => sum + i.input_tokens + i.output_tokens, 0);
    const totalInputTokens = inferences.reduce((sum, i) => sum + i.input_tokens, 0);
    const totalOutputTokens = inferences.reduce((sum, i) => sum + i.output_tokens, 0);

    // Calculate requests per hour
    const hoursInRange = timeRange[1].diff(timeRange[0], 'hours') || 1;
    const requestsPerHour = totalRequests / hoursInRange;

    // Dynamic top items based on viewBy selection
    let topModels: any[] = [];
    let topProjects: any[] = [];
    let topEndpoints: any[] = [];

    // Always calculate all three, but prioritize based on viewBy
    if (viewBy === 'model') {
      const modelCounts = inferences.reduce((acc, i) => {
        const model = i.model_display_name || i.model_name || 'Unknown';
        acc[model] = (acc[model] || 0) + 1;
        return acc;
      }, {} as Record<string, number>);

      topModels = Object.entries(modelCounts)
        .map(([model, count]) => ({
          model,
          count,
          percentage: (count / totalRequests) * 100
        }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 5);
    } else if (viewBy === 'project') {
      const projectCounts = inferences.reduce((acc, i) => {
        const project = i.project_name || 'Unknown';
        acc[project] = (acc[project] || 0) + 1;
        return acc;
      }, {} as Record<string, number>);

      topProjects = Object.entries(projectCounts)
        .map(([project, count]) => ({
          project,
          count,
          percentage: (count / totalRequests) * 100
        }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 5);
    } else if (viewBy === 'deployment') {
      const endpointCounts = inferences.reduce((acc, i) => {
        const endpoint = i.endpoint_name || 'Unknown';
        acc[endpoint] = (acc[endpoint] || 0) + 1;
        return acc;
      }, {} as Record<string, number>);

      topEndpoints = Object.entries(endpointCounts)
        .map(([endpoint, count]) => ({
          endpoint,
          count,
          percentage: (count / totalRequests) * 100
        }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 5);
    } else if (viewBy === 'user') {
      // For user view, group by user (this would need user data in inferences)
      // For now, using projects as placeholder since user data is not available
      const userCounts = inferences.reduce((acc, i) => {
        const user = i.project_name || 'Unknown';
        acc[user] = (acc[user] || 0) + 1;
        return acc;
      }, {} as Record<string, number>);

      topProjects = Object.entries(userCounts)
        .map(([project, count]) => ({
          project,
          count,
          percentage: (count / totalRequests) * 100
        }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 5);
    }

    // Fallback calculations for other views
    if (topModels.length === 0 && viewBy !== 'model') {
      const modelCounts = inferences.reduce((acc, i) => {
        const model = i.model_display_name || i.model_name || 'Unknown';
        acc[model] = (acc[model] || 0) + 1;
        return acc;
      }, {} as Record<string, number>);
      topModels = Object.entries(modelCounts)
        .map(([model, count]) => ({
          model,
          count,
          percentage: (count / totalRequests) * 100
        }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 5);
    }

    if (topProjects.length === 0 && viewBy !== 'project' && viewBy !== 'user') {
      const projectCounts = inferences.reduce((acc, i) => {
        const project = i.project_name || 'Unknown';
        acc[project] = (acc[project] || 0) + 1;
        return acc;
      }, {} as Record<string, number>);
      topProjects = Object.entries(projectCounts)
        .map(([project, count]) => ({
          project,
          count,
          percentage: (count / totalRequests) * 100
        }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 5);
    }

    if (topEndpoints.length === 0 && viewBy !== 'deployment') {
      const endpointCounts = inferences.reduce((acc, i) => {
        const endpoint = i.endpoint_name || 'Unknown';
        acc[endpoint] = (acc[endpoint] || 0) + 1;
        return acc;
      }, {} as Record<string, number>);
      topEndpoints = Object.entries(endpointCounts)
        .map(([endpoint, count]) => ({
          endpoint,
          count,
          percentage: (count / totalRequests) * 100
        }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 5);
    }

    // Hourly distribution
    const hourlyData = inferences.reduce((acc, i) => {
      const hour = dayjs(i.timestamp).format('HH:00');
      acc[hour] = (acc[hour] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);

    const hourlyDistribution = Array.from({ length: 24 }, (_, i) => {
      const hour = `${i.toString().padStart(2, '0')}:00`;
      return {
        hour,
        count: hourlyData[hour] || 0
      };
    });

    // Latency distribution
    const latencyRanges = [
      { min: 0, max: 100, label: '0-100ms' },
      { min: 100, max: 500, label: '100-500ms' },
      { min: 500, max: 1000, label: '500ms-1s' },
      { min: 1000, max: 5000, label: '1-5s' },
      { min: 5000, max: Infinity, label: '>5s' },
    ];

    const latencyDistribution = latencyRanges.map(range => ({
      range: range.label,
      count: latencies.filter(l => l >= range.min && l < range.max).length
    }));

    // Calculate grouped data based on viewBy selection
    const groupedHourlyData: { [key: string]: { hour: string; count: number }[] } = {};
    const groupedLatencyData: { [key: string]: { range: string; count: number }[] } = {};

    // Determine the grouping field based on viewBy
    const getGroupKey = (item: InferenceListItem): string => {
      switch (viewBy) {
        case 'model':
          return item.model_display_name || item.model_name || 'Unknown';
        case 'deployment':
          return item.endpoint_name || 'Unknown';
        case 'project':
          return item.project_name || 'Unknown';
        case 'user':
          // For now using project as proxy for user since user data is not available
          return item.project_name || 'Unknown';
        default:
          return 'Unknown';
      }
    };

    // Group hourly data
    const hourlyGrouped: { [key: string]: { [hour: string]: number } } = {};
    inferences.forEach(inference => {
      const groupKey = getGroupKey(inference);
      const hour = dayjs(inference.timestamp).format('HH:00');

      if (!hourlyGrouped[groupKey]) {
        hourlyGrouped[groupKey] = {};
      }
      hourlyGrouped[groupKey][hour] = (hourlyGrouped[groupKey][hour] || 0) + 1;
    });

    // Convert to the required format
    Object.keys(hourlyGrouped).forEach(groupKey => {
      groupedHourlyData[groupKey] = Array.from({ length: 24 }, (_, i) => {
        const hour = `${i.toString().padStart(2, '0')}:00`;
        return {
          hour,
          count: hourlyGrouped[groupKey][hour] || 0
        };
      });
    });

    // Group latency data
    const latencyGrouped: { [key: string]: number[] } = {};
    inferences.forEach(inference => {
      const groupKey = getGroupKey(inference);
      if (!latencyGrouped[groupKey]) {
        latencyGrouped[groupKey] = [];
      }
      if (inference.response_time_ms != null) {
        latencyGrouped[groupKey].push(inference.response_time_ms);
      }
    });

    // Convert to distribution format
    Object.keys(latencyGrouped).forEach(groupKey => {
      groupedLatencyData[groupKey] = latencyRanges.map(range => ({
        range: range.label,
        count: latencyGrouped[groupKey].filter(l => l >= range.min && l < range.max).length
      }));
    });

    // Calculate time series data for new charts
    // Group data by hour and viewBy dimension for time series
    const groupedTimeSeriesData: { [groupKey: string]: { [hour: string]: InferenceListItem[] } } = {};

    inferences.forEach(inference => {
      const groupKey = getGroupKey(inference);
      const hour = dayjs(inference.timestamp).format('YYYY-MM-DD HH:00');

      if (!groupedTimeSeriesData[groupKey]) {
        groupedTimeSeriesData[groupKey] = {};
      }
      if (!groupedTimeSeriesData[groupKey][hour]) {
        groupedTimeSeriesData[groupKey][hour] = [];
      }
      groupedTimeSeriesData[groupKey][hour].push(inference);
    });

    // Get all unique hours for consistent x-axis
    const allHours = new Set<string>();
    Object.values(groupedTimeSeriesData).forEach(groupData => {
      Object.keys(groupData).forEach(hour => allHours.add(hour));
    });
    const sortedHours = Array.from(allHours).sort();

    // Calculate grouped latency over time
    const groupedLatencyOverTime: { [key: string]: { time: string; avg: number; p95: number; p99: number }[] } = {};
    Object.entries(groupedTimeSeriesData).forEach(([groupKey, timeData]) => {
      groupedLatencyOverTime[groupKey] = sortedHours.map(hour => {
        const items = timeData[hour] || [];
        const latencies = items
          .map(i => i.response_time_ms)
          .filter(l => l != null)
          .sort((a, b) => a - b);

        const avg = latencies.length > 0
          ? latencies.reduce((a, b) => a + b, 0) / latencies.length
          : 0;
        const p95Index = Math.floor(latencies.length * 0.95);
        const p99Index = Math.floor(latencies.length * 0.99);

        return {
          time: dayjs(hour).format('HH:00'),
          avg: Math.round(avg),
          p95: latencies[p95Index] || 0,
          p99: latencies[p99Index] || 0
        };
      });
    });

    // Calculate grouped tokens over time
    const groupedTokensOverTime: { [key: string]: { time: string; input: number; output: number }[] } = {};
    Object.entries(groupedTimeSeriesData).forEach(([groupKey, timeData]) => {
      groupedTokensOverTime[groupKey] = sortedHours.map(hour => {
        const items = timeData[hour] || [];
        return {
          time: dayjs(hour).format('HH:00'),
          input: items.reduce((sum, i) => sum + i.input_tokens, 0),
          output: items.reduce((sum, i) => sum + i.output_tokens, 0)
        };
      });
    });

    // Calculate grouped requests per second
    const groupedRequestsPerSecond: { [key: string]: { time: string; rps: number }[] } = {};
    Object.entries(groupedTimeSeriesData).forEach(([groupKey, timeData]) => {
      groupedRequestsPerSecond[groupKey] = sortedHours.map(hour => {
        const items = timeData[hour] || [];
        return {
          time: dayjs(hour).format('HH:00'),
          rps: items.length / 3600 // Convert hourly count to per second
        };
      });
    });

    // Calculate aggregate metrics (for fallback when no grouping)
    const allTimeSeriesData: { [hour: string]: InferenceListItem[] } = {};
    inferences.forEach(inference => {
      const hour = dayjs(inference.timestamp).format('YYYY-MM-DD HH:00');
      if (!allTimeSeriesData[hour]) {
        allTimeSeriesData[hour] = [];
      }
      allTimeSeriesData[hour].push(inference);
    });

    const latencyOverTime = sortedHours.map(hour => {
      const items = allTimeSeriesData[hour] || [];
      const latencies = items
        .map(i => i.response_time_ms)
        .filter(l => l != null)
        .sort((a, b) => a - b);

      const avg = latencies.length > 0
        ? latencies.reduce((a, b) => a + b, 0) / latencies.length
        : 0;
      const p95Index = Math.floor(latencies.length * 0.95);
      const p99Index = Math.floor(latencies.length * 0.99);

      return {
        time: dayjs(hour).format('HH:00'),
        avg: Math.round(avg),
        p95: latencies[p95Index] || 0,
        p99: latencies[p99Index] || 0
      };
    });

    const tokensOverTime = sortedHours.map(hour => {
      const items = allTimeSeriesData[hour] || [];
      return {
        time: dayjs(hour).format('HH:00'),
        input: items.reduce((sum, i) => sum + i.input_tokens, 0),
        output: items.reduce((sum, i) => sum + i.output_tokens, 0)
      };
    });

    const requestsPerSecond = sortedHours.map(hour => {
      const items = allTimeSeriesData[hour] || [];
      return {
        time: dayjs(hour).format('HH:00'),
        rps: items.length / 3600
      };
    });

    // TTFT placeholder (since ttft_ms is not in InferenceListItem)
    const avgTTFT = 0; // Would need ttft_ms data
    const p95TTFT = 0; // Would need ttft_ms data
    const ttftOverTime = sortedHours.map(hour => ({
      time: dayjs(hour).format('HH:00'),
      avg: 0, // Placeholder
      p95: 0  // Placeholder
    }));

    return {
      totalRequests,
      successRate,
      failureRate,
      avgLatency,
      p95Latency,
      p99Latency,
      totalCost,
      totalTokens,
      totalInputTokens,
      totalOutputTokens,
      requestsPerHour,
      avgTTFT,
      p95TTFT,
      topModels,
      topProjects,
      topEndpoints,
      hourlyDistribution,
      latencyDistribution,
      errorTypes: [],
      groupedHourlyData,
      groupedLatencyData,
      latencyOverTime,
      tokensOverTime,
      requestsPerSecond,
      ttftOverTime,
      groupedLatencyOverTime,
      groupedTokensOverTime,
      groupedRequestsPerSecond,
      groupedTTFTOverTime: {},
    };
  }, [serverMetrics, inferences, timeRange, viewBy]);


  // Show empty state if no data
  if (!serverMetrics && (!inferences || inferences.length === 0)) {
    return (
      <div className="flex justify-center items-center h-96">
        <Empty description="No data available for the selected time range" />
      </div>
    );
  }

  // Create a stable key based on time range to help React track component updates
  const metricsKey = `${timeRange[0].unix()}-${timeRange[1].unix()}-${viewBy}`;

  return (
    <div className="metrics-container theme-aware-metrics" key={metricsKey}>
      <style jsx global>{`
        .theme-aware-metrics *,
        .theme-aware-metrics div,
        .theme-aware-metrics span,
        .theme-aware-metrics p,
        .theme-aware-metrics h1,
        .theme-aware-metrics h2,
        .theme-aware-metrics h3,
        .theme-aware-metrics h4,
        .theme-aware-metrics h5,
        .theme-aware-metrics h6 {
          color: var(--text-primary) !important;
        }

        /* Override specific hardcoded text components */
        .theme-aware-metrics [class*="Text_"][class*="_FFFFFF"],
        .theme-aware-metrics [class*="Text_"][class*="_EEEEEE"],
        .theme-aware-metrics [class*="Text_"][class*="_26_400_EEEEEE"],
        .theme-aware-metrics [class*="Text_"][class*="_22_700_EEEEEE"],
        .theme-aware-metrics [class*="Text_"][class*="_19_600_EEEEEE"],
        .theme-aware-metrics [class*="Text_"][class*="_16_600_FFFFFF"],
        .theme-aware-metrics [class*="Text_"][class*="_14_600_EEEEEE"],
        .theme-aware-metrics [class*="Text_"][class*="_14_400_EEEEEE"],
        .theme-aware-metrics [class*="Text_"][class*="_12_500_FFFFFF"],
        .theme-aware-metrics [class*="Text_"][class*="_12_400_EEEEEE"] {
          color: var(--text-primary) !important;
        }

        .theme-aware-metrics [class*="Text_"][class*="_B3B3B3"],
        .theme-aware-metrics [class*="Text_"][class*="_12_400_B3B3B3"],
        .theme-aware-metrics [class*="Text_"][class*="_13_400_757575"] {
          color: var(--text-muted) !important;
        }

        /* Ant Design components */
        .theme-aware-metrics .ant-list-item {
          color: var(--text-primary) !important;
        }
        .theme-aware-metrics .ant-progress-text {
          color: var(--text-primary) !important;
        }
        .theme-aware-metrics .ant-empty-description {
          color: var(--text-muted) !important;
        }
        .theme-aware-metrics .ant-row {
          color: var(--text-primary) !important;
        }
      `}</style>
      {/* Key Metrics Cards */}
      <Row gutter={[16, 16]} className="mb-6">
        <Col xs={24} sm={12} md={6}>
          <MetricCard
            icon={<ApiOutlined style={{ color: '#3F8EF7', fontSize: '1.25rem' }} />}
            title="Total Requests"
            value={metrics.totalRequests.toLocaleString()}
            subtitle={`${metrics.requestsPerHour.toFixed(1)} req/hour`}
          />
        </Col>

        <Col xs={24} sm={12} md={6}>
          <MetricCard
            icon={<CheckCircleOutlined style={{ color: metrics.successRate >= 95 ? '#22c55e' : '#f59e0b', fontSize: '1.25rem' }} />}
            title="Success Rate"
            value={`${metrics.successRate.toFixed(1)}%`}
            valueColor={metrics.successRate >= 95 ? '#22c55e' : '#f59e0b'}
            showProgress={true}
            progressValue={metrics.successRate}
            progressColor={metrics.successRate >= 95 ? '#22c55e' : '#f59e0b'}
          />
        </Col>

        <Col xs={24} sm={12} md={6}>
          <MetricCard
            icon={<ClockCircleOutlined style={{ color: '#3F8EF7', fontSize: '1.25rem' }} />}
            title="Avg Latency"
            value={`${metrics.avgLatency.toFixed(0)}ms`}
            subtitle={`P95: ${Math.round(metrics.p95Latency)}ms | P99: ${Math.round(metrics.p99Latency)}ms`}
          />
        </Col>

        <Col xs={24} sm={12} md={6}>
          <MetricCard
            icon={<ThunderboltOutlined style={{ color: '#FFC442', fontSize: '1.25rem' }} />}
            title="Total Tokens"
            value={metrics.totalTokens.toLocaleString()}
            subtitle={`${metrics.totalInputTokens.toLocaleString()} input / ${metrics.totalOutputTokens.toLocaleString()} output`}
          />
        </Col>
      </Row>

      {/* Charts Row */}
      <Row gutter={[16, 16]} className="mb-6">
        <Col xs={24} lg={12}>
          <ChartCard
            title="Request Volume Over Time"
            subtitle={`Hourly distribution by ${viewBy}`}
          >
            {Object.keys(metrics.groupedHourlyData).length > 0 ? (
              <MultiSeriesLineChart
                key={`hourly-multi-${metricsKey}`}
                data={{
                  categories: Array.from({ length: 24 }, (_, i) =>
                    `${i.toString().padStart(2, '0')}:00`
                  ),
                  series: Object.entries(metrics.groupedHourlyData)
                    .slice(0, 10) // Limit to top 10 series for readability
                    .map(([name, data]) => ({
                      name,
                      data: data.map(d => d.count),
                      color: getEntityColor(name)
                    }))
                }}
              />
            ) : (
              <LineChartCustom
                key={`hourly-single-${metricsKey}`}
                data={{
                  categories: metrics.hourlyDistribution.map(d => d.hour),
                  data: metrics.hourlyDistribution.map(d => d.count),
                  label1: 'Requests',
                  label2: 'Hour of Day',
                  color: '#3F8EF7',
                  smooth: true
                }}
              />
            )}
          </ChartCard>
        </Col>

        <Col xs={24} lg={12}>
          <ChartCard
            title="Latency Distribution"
            subtitle={`Response time ranges by ${viewBy}`}
          >
            {Object.keys(metrics.groupedLatencyData).length > 0 ? (
              <GroupedBarChart
                data={{
                  categories: ['0-100ms', '100-500ms', '500ms-1s', '1-2s', '2-5s', '5-10s', '>10s'],
                  series: Object.entries(metrics.groupedLatencyData)
                    .slice(0, 10) // Limit to top 10 series for readability
                    .map(([name, data]) => ({
                      name,
                      data: data.map(d => d.count),
                      color: getEntityColor(name)
                    }))
                }}
              />
            ) : (
              <BarChart
                data={{
                  categories: metrics.latencyDistribution.map(d => d.range),
                  data: metrics.latencyDistribution.map(d => d.count),
                  barColor: '#3F8EF7'
                }}
              />
            )}
          </ChartCard>
        </Col>
      </Row>

      {/* Geographic Distribution Row */}
      <Row gutter={[16, 16]} className="mb-6">
        <Col xs={24}>
          <div
            className="p-[2.55rem] py-[2rem] rounded-[6.403px] border-[1.067px] w-full"
            style={{
              backgroundColor: 'var(--bg-card)',
              borderColor: 'var(--border-color)',
              boxShadow: 'var(--shadow-sm)',
            }}
          >
            <div className="flex items-center w-full flex-col mb-4">
              <Text_19_600_EEEEEE className="w-full !text-[var(--text-primary)]">
                Geographic Distribution
              </Text_19_600_EEEEEE>
              <Text_13_400_757575 className='w-full mt-2 !text-[var(--text-muted)]'>
                Request origins by country
              </Text_13_400_757575>
            </div>
            <GeoMapChart key={`geo-${metricsKey}`} data={geographicData} />
          </div>
        </Col>
      </Row>

      {/* Performance Metrics Row */}
      <Row gutter={[16, 16]} className="mb-6">
        <Col xs={24} md={12}>
          <ChartCard
            title="Request Latency Over Time"
            subtitle={`Average latency by ${viewBy}`}
          >
            {Object.keys(metrics.groupedLatencyOverTime).length > 0 ? (
              <MultiSeriesLineChart
                key={`latency-grouped-${metricsKey}`}
                data={{
                  categories: Array.from(new Set(Object.values(metrics.groupedLatencyOverTime).flat().map((d: any) => d.time))).sort(),
                  series: Object.entries(metrics.groupedLatencyOverTime)
                    .slice(0, 10) // Limit to top 10 for readability
                    .map(([name, data]) => {
                      // Create a map for quick lookup
                      const dataMap = new Map(data.map((d: any) => [d.time, d.value || 0]));
                      // Ensure all categories have a value (0 if missing)
                      const categories = Array.from(new Set(Object.values(metrics.groupedLatencyOverTime).flat().map((d: any) => d.time))).sort();
                      return {
                        name,
                        data: categories.map(cat => dataMap.get(cat) || 0),
                        color: getEntityColor(name)
                      };
                    })
                }}
              />
            ) : (
              <MultiSeriesLineChart
                key={`latency-single-${metricsKey}`}
                data={{
                  categories: metrics.latencyOverTime.map(d => d.time),
                  series: [
                    {
                      name: 'Average',
                      data: metrics.latencyOverTime.map(d => d.avg),
                      color: '#3F8EF7'
                    },
                    {
                      name: 'P95',
                      data: metrics.latencyOverTime.map(d => d.p95),
                      color: '#FFC442'
                    },
                    {
                      name: 'P99',
                      data: metrics.latencyOverTime.map(d => d.p99),
                      color: '#FF6B6B'
                    }
                  ]
                }}
              />
            )}
          </ChartCard>
        </Col>

        <Col xs={24} md={12}>
          <ChartCard
            title="Token Usage Over Time"
            subtitle={`Total tokens by ${viewBy}`}
          >
            {Object.keys(metrics.groupedTokensOverTime).length > 0 ? (
              <MultiSeriesLineChart
                data={{
                  categories: Array.from(new Set(Object.values(metrics.groupedTokensOverTime).flat().map((d: any) => d.time))).sort(),
                  series: Object.entries(metrics.groupedTokensOverTime)
                    .slice(0, 10) // Limit to top 10 for readability
                    .map(([name, data]) => {
                      // Create a map for quick lookup
                      const dataMap = new Map(data.map((d: any) => [d.time, d.value || 0]));
                      // Ensure all categories have a value (0 if missing)
                      const categories = Array.from(new Set(Object.values(metrics.groupedTokensOverTime).flat().map((d: any) => d.time))).sort();
                      return {
                        name,
                        data: categories.map(cat => dataMap.get(cat) || 0),
                        color: getEntityColor(name)
                      };
                    })
                }}
              />
            ) : (
              <MultiSeriesLineChart
                data={{
                  categories: metrics.tokensOverTime.map(d => d.time),
                  series: [
                    {
                      name: 'Input Tokens',
                      data: metrics.tokensOverTime.map(d => d.input),
                      color: '#52C41A'
                    },
                    {
                      name: 'Output Tokens',
                      data: metrics.tokensOverTime.map(d => d.output),
                      color: '#965CDE'
                    }
                  ]
                }}
              />
            )}
          </ChartCard>
        </Col>
      </Row>

      {/* Additional Performance Metrics */}
      <Row gutter={[16, 16]} className="mb-6">
        <Col xs={24} md={12}>
          <ChartCard
            title="Requests Per Second"
            subtitle={`Throughput by ${viewBy}`}
          >
            {Object.keys(metrics.groupedRequestsPerSecond).length > 0 ? (
              <MultiSeriesLineChart
                data={{
                  categories: Array.from(new Set(Object.values(metrics.groupedRequestsPerSecond).flat().map((d: any) => d.time))).sort(),
                  series: Object.entries(metrics.groupedRequestsPerSecond)
                    .slice(0, 10) // Limit to top 10 for readability
                    .map(([name, data]) => {
                      // Create a map for quick lookup
                      const dataMap = new Map(data.map((d: any) => [d.time, d.rps || 0]));
                      // Ensure all categories have a value (0 if missing)
                      const categories = Array.from(new Set(Object.values(metrics.groupedRequestsPerSecond).flat().map((d: any) => d.time))).sort();
                      return {
                        name,
                        data: categories.map(cat => dataMap.get(cat) != null ? parseFloat(dataMap.get(cat).toFixed(3)) : 0),
                        color: getEntityColor(name)
                      };
                    })
                }}
              />
            ) : (
              <LineChartCustom
                data={{
                  categories: metrics.requestsPerSecond.map(d => d.time),
                  data: metrics.requestsPerSecond.map(d => d.rps != null ? parseFloat(d.rps.toFixed(2)) : 0),
                  label1: 'RPS',
                  label2: 'Time',
                  color: '#4ECDC4',
                  smooth: true
                }}
              />
            )}
          </ChartCard>
        </Col>

        <Col xs={24} md={12}>
          <ChartCard title="Time to First Token (TTFT)" subtitle={`Stream response metrics by ${viewBy}`}>
            {Object.keys(metrics.groupedTTFTOverTime).length > 0 ? (
              <MultiSeriesLineChart
                data={{
                  categories: Array.from(new Set(Object.values(metrics.groupedTTFTOverTime).flat().map((d: any) => d.time))).sort(),
                  series: Object.entries(metrics.groupedTTFTOverTime)
                    .slice(0, 10) // Limit to top 10 for readability
                    .map(([name, data]) => {
                      // Create a map for quick lookup
                      const dataMap = new Map(data.map((d: any) => [d.time, d.value || 0]));
                      // Ensure all categories have a value (0 if missing)
                      const categories = Array.from(new Set(Object.values(metrics.groupedTTFTOverTime).flat().map((d: any) => d.time))).sort();
                      return {
                        name,
                        data: categories.map(cat => dataMap.get(cat) != null ? parseFloat(dataMap.get(cat).toFixed(2)) : 0),
                        color: getEntityColor(name)
                      };
                    })
                }}
              />
            ) : metrics.ttftOverTime && metrics.ttftOverTime.length > 0 ? (
              <MultiSeriesLineChart
                data={{
                  categories: metrics.ttftOverTime.map(d => d.time),
                  series: [
                    {
                      name: 'Average TTFT',
                      data: metrics.ttftOverTime.map(d => d.avg || 0),
                      color: '#52C41A'
                    },
                    {
                      name: 'P95 TTFT',
                      data: metrics.ttftOverTime.map(d => d.p95 || 0),
                      color: '#FFC442'
                    }
                  ]
                }}
              />
            ) : (
              <div className="flex flex-col items-center justify-center h-full gap-2">
                <ThunderboltOutlined style={{ fontSize: '32px', color: '#757575' }} />
                <Text_12_400_B3B3B3 className="text-center !text-[var(--text-muted)]">
                  No TTFT data available
                </Text_12_400_B3B3B3>
                <Text_12_400_B3B3B3 className="text-center text-xs opacity-60 !text-[var(--text-muted)]">
                  TTFT metrics will appear when streaming endpoints are used
                </Text_12_400_B3B3B3>
              </div>
            )}
          </ChartCard>
        </Col>
      </Row>

      {/* Top Statistics Row - Dynamic based on viewBy */}
      <Row gutter={[16, 16]} className="mb-6">
        {viewBy === 'model' && (
          <Col xs={24} md={12}>
            <div
              className="p-[1.55rem] py-[2rem] rounded-[6.403px] border-[1.067px] h-[22rem]"
              style={{
                backgroundColor: 'var(--bg-card)',
                borderColor: 'var(--border-color)',
                boxShadow: 'var(--shadow-sm)',
              }}
            >
              <Text_19_600_EEEEEE className="mb-4 !text-[var(--text-primary)]">Top Models</Text_19_600_EEEEEE>
              <List
                dataSource={metrics.topModels}
                renderItem={(item, index) => (
                  <List.Item
                    className="border-[var(--border-secondary)] py-2"
                    style={{
                      borderColor: 'var(--border-color)',
                    }}
                  >
                    <div className="w-full">
                      <div className="flex justify-between mb-1">
                        <Text_12_400_EEEEEE className="truncate max-w-[60%] !text-[var(--text-primary)]">{item.model}</Text_12_400_EEEEEE>
                        <Text_12_400_B3B3B3 className="!text-[var(--text-muted)]">{item.count} ({item.percentage.toFixed(1)}%)</Text_12_400_B3B3B3>
                      </div>
                      <Progress
                        percent={item.percentage}
                        showInfo={false}
                        strokeColor={getEntityColor(item.model)}
                        trailColor="var(--border-secondary)"
                        size="small"
                      />
                    </div>
                  </List.Item>
                )}
              />
            </div>
          </Col>
        )}

        {viewBy === 'deployment' && (
          <Col xs={24} md={12}>
            <div
              className="p-[1.55rem] py-[2rem] rounded-[6.403px] border-[1.067px] h-[22rem]"
              style={{
                backgroundColor: 'var(--bg-card)',
                borderColor: 'var(--border-color)',
                boxShadow: 'var(--shadow-sm)',
              }}
            >
              <Text_19_600_EEEEEE className="mb-4 !text-[var(--text-primary)]">Top Deployments</Text_19_600_EEEEEE>
              <List
                dataSource={metrics.topEndpoints}
                renderItem={(item, index) => (
                  <List.Item
                    className="border-[var(--border-secondary)] py-2"
                    style={{
                      borderColor: 'var(--border-color)',
                    }}
                  >
                    <div className="w-full">
                      <div className="flex justify-between mb-1">
                        <Text_12_400_EEEEEE className="truncate max-w-[60%] !text-[var(--text-primary)]">{item.endpoint}</Text_12_400_EEEEEE>
                        <Text_12_400_B3B3B3 className="!text-[var(--text-muted)]">{item.count} ({item.percentage.toFixed(1)}%)</Text_12_400_B3B3B3>
                      </div>
                      <Progress
                        percent={item.percentage}
                        showInfo={false}
                        strokeColor={getEntityColor(item.endpoint)}
                        trailColor="var(--border-secondary)"
                        size="small"
                      />
                    </div>
                  </List.Item>
                )}
              />
            </div>
          </Col>
        )}

        {(viewBy === 'project' || viewBy === 'user') && (
          <Col xs={24} md={12}>
            <div
              className="p-[1.55rem] py-[2rem] rounded-[6.403px] border-[1.067px] h-[22rem]"
              style={{
                backgroundColor: 'var(--bg-card)',
                borderColor: 'var(--border-color)',
                boxShadow: 'var(--shadow-sm)',
              }}
            >
              <Text_19_600_EEEEEE className="mb-4 !text-[var(--text-primary)]">
                {viewBy === 'user' ? 'Top Users' : 'Top Projects'}
              </Text_19_600_EEEEEE>
              <List
                dataSource={metrics.topProjects}
                renderItem={(item, index) => (
                  <List.Item
                    className="border-[var(--border-secondary)] py-2"
                    style={{
                      borderColor: 'var(--border-color)',
                    }}
                  >
                    <div className="w-full">
                      <div className="flex justify-between mb-1">
                        <Text_12_400_EEEEEE className="truncate max-w-[60%] !text-[var(--text-primary)]">{item.project}</Text_12_400_EEEEEE>
                        <Text_12_400_B3B3B3 className="!text-[var(--text-muted)]">{item.count} ({item.percentage.toFixed(1)}%)</Text_12_400_B3B3B3>
                      </div>
                      <Progress
                        percent={item.percentage}
                        showInfo={false}
                        strokeColor={getEntityColor(item.project)}
                        trailColor="var(--border-secondary)"
                        size="small"
                      />
                    </div>
                  </List.Item>
                )}
              />
            </div>
          </Col>
        )}

        {/* Secondary stats - show complementary data */}
        {viewBy !== 'model' && metrics.topModels.length > 0 && (
          <Col xs={24} md={12}>
            <div
              className="p-[1.55rem] py-[2rem] rounded-[6.403px] border-[1.067px] h-[22rem]"
              style={{
                backgroundColor: 'var(--bg-card)',
                borderColor: 'var(--border-color)',
                boxShadow: 'var(--shadow-sm)',
              }}
            >
              <Text_19_600_EEEEEE className="mb-4 !text-[var(--text-primary)]">Models Used</Text_19_600_EEEEEE>
              <List
                dataSource={metrics.topModels}
                renderItem={(item, index) => (
                  <List.Item
                    className="border-[var(--border-secondary)] py-2"
                    style={{
                      borderColor: 'var(--border-color)',
                    }}
                  >
                    <div className="w-full">
                      <div className="flex justify-between mb-1">
                        <Text_12_400_EEEEEE className="truncate max-w-[60%] !text-[var(--text-primary)]">{item.model}</Text_12_400_EEEEEE>
                        <Text_12_400_B3B3B3 className="!text-[var(--text-muted)]">{item.count} ({item.percentage.toFixed(1)}%)</Text_12_400_B3B3B3>
                      </div>
                      <Progress
                        percent={item.percentage}
                        showInfo={false}
                        strokeColor={getEntityColor(item.model)}
                        trailColor="var(--border-secondary)"
                        size="small"
                      />
                    </div>
                  </List.Item>
                )}
              />
            </div>
          </Col>
        )}

        {viewBy !== 'deployment' && metrics.topEndpoints.length > 0 && (
          <Col xs={24} md={12}>
            <div
              className="p-[1.55rem] py-[2rem] rounded-[6.403px] border-[1.067px] h-[22rem]"
              style={{
                backgroundColor: 'var(--bg-card)',
                borderColor: 'var(--border-color)',
                boxShadow: 'var(--shadow-sm)',
              }}
            >
              <Text_19_600_EEEEEE className="mb-4 !text-[var(--text-primary)]">Active Deployments</Text_19_600_EEEEEE>
              <List
                dataSource={metrics.topEndpoints}
                renderItem={(item, index) => (
                  <List.Item
                    className="border-[var(--border-secondary)] py-2"
                    style={{
                      borderColor: 'var(--border-color)',
                    }}
                  >
                    <div className="w-full">
                      <div className="flex justify-between mb-1">
                        <Text_12_400_EEEEEE className="truncate max-w-[60%] !text-[var(--text-primary)]">{item.endpoint}</Text_12_400_EEEEEE>
                        <Text_12_400_B3B3B3 className="!text-[var(--text-muted)]">{item.count} ({item.percentage.toFixed(1)}%)</Text_12_400_B3B3B3>
                      </div>
                      <Progress
                        percent={item.percentage}
                        showInfo={false}
                        strokeColor={getEntityColor(item.endpoint)}
                        trailColor="var(--border-secondary)"
                        size="small"
                      />
                    </div>
                  </List.Item>
                )}
              />
            </div>
          </Col>
        )}

        <Col xs={24} md={12}>
          <ChartCard title="Success/Failure Ratio" height="22rem">
            <div className="flex justify-around items-center h-full">
              <div className="text-center">
                <CheckCircleOutlined style={{ color: '#22c55e', fontSize: '48px' }} />
                <div className="mt-4">
                  <Text_22_700_EEEEEE style={{ color: '#22c55e' }}>
                    {metrics.successRate.toFixed(1)}%
                  </Text_22_700_EEEEEE>
                </div>
                <Text_12_400_B3B3B3 className="!text-[var(--text-muted)]">Success</Text_12_400_B3B3B3>
              </div>
              <div
                className="w-px h-32"
                style={{
                  backgroundColor: 'var(--border-color)',
                }}
              ></div>
              <div className="text-center">
                <CloseCircleOutlined style={{ color: '#ef4444', fontSize: '48px' }} />
                <div className="mt-4">
                  <Text_22_700_EEEEEE style={{ color: '#ef4444' }}>
                    {metrics.failureRate.toFixed(1)}%
                  </Text_22_700_EEEEEE>
                </div>
                <Text_12_400_B3B3B3 className="!text-[var(--text-muted)]">Failed</Text_12_400_B3B3B3>
              </div>
            </div>
          </ChartCard>
        </Col>
      </Row>
    </div>
  );
};

export default MetricsTab;

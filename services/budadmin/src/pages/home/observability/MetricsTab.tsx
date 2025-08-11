import React, { useEffect, useState, useMemo } from 'react';
import { Row, Col, Spin, Empty, Progress, List, Typography, Tooltip } from 'antd';
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
import BarChart from '@/components/charts/barChart';
import LineChartCustom from '@/components/charts/lineChart/LineChartCustom';
import MultiSeriesLineChart from '@/components/charts/MultiSeriesLineChart';
import GroupedBarChart from '@/components/charts/GroupedBarChart';
import GeoMapChart from '@/components/charts/GeoMapChart';
import { Flex } from '@radix-ui/themes';

const { Text } = Typography;

// Custom chart component wrapper for consistent styling
function ChartCard({ title, subtitle, children, height = '23.664375rem' }: { title: string; subtitle?: string; children: React.ReactNode; height?: string }) {
  return (
    <div className={`bg-[#101010] p-[1.55rem] py-[2rem] rounded-[6.403px] border-[1.067px] border-[#1F1F1F] w-full h-[${height}] flex items-center justify-between flex-col`}>
      <div className="flex items-center w-full flex-col">
        <Text_19_600_EEEEEE className="mb-[1.3rem] w-full">
          {title}
        </Text_19_600_EEEEEE>
        {subtitle && (
          <Text_13_400_757575 className='w-full mb-4'>
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
function MetricCard({ icon, title, value, subtitle, valueColor = '#EEEEEE', showProgress = false, progressValue = 0, progressColor = '#3F8EF7' }: any) {
  return (
    <div className="bg-[#101010] p-[1.45rem] pb-[1.2rem] rounded-[6.403px] border-[1.067px] border-[#1F1F1F] min-h-[7.8125rem] flex flex-col items-start justify-between">
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <Text_12_500_FFFFFF>{title}</Text_12_500_FFFFFF>
      </div>
      <div className="flex flex-col w-full">
        <Text_22_700_EEEEEE style={{ color: valueColor }}>
          {value}
        </Text_22_700_EEEEEE>
        {subtitle && (
          <Text_12_400_B3B3B3 className="mt-2">{subtitle}</Text_12_400_B3B3B3>
        )}
        {showProgress && (
          <Progress
            percent={progressValue}
            showInfo={false}
            strokeColor={progressColor}
            trailColor="#212225"
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
}


const MetricsTab: React.FC<MetricsTabProps> = ({ timeRange, inferences, isLoading, viewBy, isActive }) => {

  // Trigger ECharts resize when tab becomes active
  useEffect(() => {
    if (isActive) {
      // Small delay to ensure the tab content is fully visible
      setTimeout(() => {
        // Trigger resize event to force all ECharts instances to recalculate
        window.dispatchEvent(new Event('resize'));
      }, 100);
    }
  }, [isActive]);

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

  // Calculate metrics from inferences data
  const metrics = useMemo<MetricStats>(() => {
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
        .slice(0, 3);
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
        .slice(0, 3);
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
        .slice(0, 3);
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
    };
  }, [inferences, timeRange, viewBy]);


  // Remove the loader here since parent component already handles it with useLoaderOnLoding
  if (!isLoading && (!inferences || inferences.length === 0)) {
    return (
      <div className="flex justify-center items-center h-96">
        <Empty description="No data available for the selected time range" />
      </div>
    );
  }

  return (
    <div className="metrics-container">
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
            subtitle={`P95: ${metrics.p95Latency}ms | P99: ${metrics.p99Latency}ms`}
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
                data={{
                  categories: metrics.hourlyDistribution.map(d => d.hour),
                  data: metrics.hourlyDistribution.map(d => d.count),
                  label1: 'Requests',
                  label2: 'Time',
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
                  categories: ['0-100ms', '100-500ms', '500ms-1s', '1-5s', '>5s'],
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
          <ChartCard title="Geographic Distribution" subtitle="Request origins by country">
            <GeoMapChart />
          </ChartCard>
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
                data={{
                  categories: metrics.latencyOverTime.map(d => d.time),
                  series: Object.entries(metrics.groupedLatencyOverTime)
                    .slice(0, 10) // Limit to top 10 for readability
                    .map(([name, data]) => ({
                      name,
                      data: data.map(d => d.avg),
                      color: getEntityColor(name)
                    }))
                }}
              />
            ) : (
              <MultiSeriesLineChart
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
                  categories: metrics.tokensOverTime.map(d => d.time),
                  series: Object.entries(metrics.groupedTokensOverTime)
                    .slice(0, 10) // Limit to top 10 for readability
                    .map(([name, data]) => ({
                      name,
                      data: data.map(d => d.input + d.output),
                      color: getEntityColor(name)
                    }))
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
                  categories: metrics.requestsPerSecond.map(d => d.time),
                  series: Object.entries(metrics.groupedRequestsPerSecond)
                    .slice(0, 10) // Limit to top 10 for readability
                    .map(([name, data]) => ({
                      name,
                      data: data.map(d => parseFloat(d.rps.toFixed(3))),
                      color: getEntityColor(name)
                    }))
                }}
              />
            ) : (
              <LineChartCustom
                data={{
                  categories: metrics.requestsPerSecond.map(d => d.time),
                  data: metrics.requestsPerSecond.map(d => parseFloat(d.rps.toFixed(2))),
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
          <ChartCard title="Time to First Token (TTFT)" subtitle="Stream response metrics">
            <div className="flex flex-col items-center justify-center h-full gap-2">
              <ThunderboltOutlined style={{ fontSize: '32px', color: '#757575' }} />
              <Text_12_400_B3B3B3 className="text-center">
                TTFT metrics are available for streaming responses only
              </Text_12_400_B3B3B3>
              <Text_12_400_B3B3B3 className="text-center text-xs opacity-60">
                This data will appear when streaming endpoints are used
              </Text_12_400_B3B3B3>
            </div>
          </ChartCard>
        </Col>
      </Row>

      {/* Top Statistics Row - Dynamic based on viewBy */}
      <Row gutter={[16, 16]}>
        {viewBy === 'model' && (
          <Col xs={24} md={8}>
            <div className="bg-[#101010] p-[1.55rem] py-[2rem] rounded-[6.403px] border-[1.067px] border-[#1F1F1F] h-[20rem]">
              <Text_19_600_EEEEEE className="mb-4">Top Models</Text_19_600_EEEEEE>
              <List
                dataSource={metrics.topModels}
                renderItem={item => (
                  <List.Item className="border-[#212225] py-2">
                    <div className="w-full">
                      <div className="flex justify-between mb-1">
                        <Text_12_400_EEEEEE className="truncate max-w-[60%]">{item.model}</Text_12_400_EEEEEE>
                        <Text_12_400_B3B3B3>{item.count} ({item.percentage.toFixed(1)}%)</Text_12_400_B3B3B3>
                      </div>
                      <Progress
                        percent={item.percentage}
                        showInfo={false}
                        strokeColor="#3F8EF7"
                        trailColor="#212225"
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
          <Col xs={24} md={8}>
            <div className="bg-[#101010] p-[1.55rem] py-[2rem] rounded-[6.403px] border-[1.067px] border-[#1F1F1F] h-[20rem]">
              <Text_19_600_EEEEEE className="mb-4">Top Deployments</Text_19_600_EEEEEE>
              <List
                dataSource={metrics.topEndpoints}
                renderItem={item => (
                  <List.Item className="border-[#212225] py-2">
                    <div className="w-full">
                      <div className="flex justify-between mb-1">
                        <Text_12_400_EEEEEE className="truncate max-w-[60%]">{item.endpoint}</Text_12_400_EEEEEE>
                        <Text_12_400_B3B3B3>{item.count} ({item.percentage.toFixed(1)}%)</Text_12_400_B3B3B3>
                      </div>
                      <Progress
                        percent={item.percentage}
                        showInfo={false}
                        strokeColor="#965CDE"
                        trailColor="#212225"
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
          <Col xs={24} md={8}>
            <div className="bg-[#101010] p-[1.55rem] py-[2rem] rounded-[6.403px] border-[1.067px] border-[#1F1F1F] h-[20rem]">
              <Text_19_600_EEEEEE className="mb-4">
                {viewBy === 'user' ? 'Top Users' : 'Top Projects'}
              </Text_19_600_EEEEEE>
              <List
                dataSource={metrics.topProjects}
                renderItem={item => (
                  <List.Item className="border-[#212225] py-2">
                    <div className="w-full">
                      <div className="flex justify-between mb-1">
                        <Text_12_400_EEEEEE className="truncate max-w-[60%]">{item.project}</Text_12_400_EEEEEE>
                        <Text_12_400_B3B3B3>{item.count} ({item.percentage.toFixed(1)}%)</Text_12_400_B3B3B3>
                      </div>
                      <Progress
                        percent={item.percentage}
                        showInfo={false}
                        strokeColor="#FFC442"
                        trailColor="#212225"
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
          <Col xs={24} md={8}>
            <div className="bg-[#101010] p-[1.55rem] py-[2rem] rounded-[6.403px] border-[1.067px] border-[#1F1F1F] h-[20rem]">
              <Text_19_600_EEEEEE className="mb-4">Models Used</Text_19_600_EEEEEE>
              <List
                dataSource={metrics.topModels}
                renderItem={item => (
                  <List.Item className="border-[#212225] py-2">
                    <div className="w-full">
                      <div className="flex justify-between mb-1">
                        <Text_12_400_EEEEEE className="truncate max-w-[60%]">{item.model}</Text_12_400_EEEEEE>
                        <Text_12_400_B3B3B3>{item.count} ({item.percentage.toFixed(1)}%)</Text_12_400_B3B3B3>
                      </div>
                      <Progress
                        percent={item.percentage}
                        showInfo={false}
                        strokeColor="#3F8EF7"
                        trailColor="#212225"
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
          <Col xs={24} md={8}>
            <div className="bg-[#101010] p-[1.55rem] py-[2rem] rounded-[6.403px] border-[1.067px] border-[#1F1F1F] h-[20rem]">
              <Text_19_600_EEEEEE className="mb-4">Active Deployments</Text_19_600_EEEEEE>
              <List
                dataSource={metrics.topEndpoints}
                renderItem={item => (
                  <List.Item className="border-[#212225] py-2">
                    <div className="w-full">
                      <div className="flex justify-between mb-1">
                        <Text_12_400_EEEEEE className="truncate max-w-[60%]">{item.endpoint}</Text_12_400_EEEEEE>
                        <Text_12_400_B3B3B3>{item.count} ({item.percentage.toFixed(1)}%)</Text_12_400_B3B3B3>
                      </div>
                      <Progress
                        percent={item.percentage}
                        showInfo={false}
                        strokeColor="#965CDE"
                        trailColor="#212225"
                        size="small"
                      />
                    </div>
                  </List.Item>
                )}
              />
            </div>
          </Col>
        )}

        <Col xs={24} md={8}>
          <ChartCard title="Success/Failure Ratio" height="20rem">
            <div className="flex justify-around items-center h-full">
              <div className="text-center">
                <CheckCircleOutlined style={{ color: '#22c55e', fontSize: '48px' }} />
                <div className="mt-4">
                  <Text_22_700_EEEEEE style={{ color: '#22c55e' }}>
                    {metrics.successRate.toFixed(1)}%
                  </Text_22_700_EEEEEE>
                </div>
                <Text_12_400_B3B3B3>Success</Text_12_400_B3B3B3>
              </div>
              <div className="w-px h-32 bg-[#212225]"></div>
              <div className="text-center">
                <CloseCircleOutlined style={{ color: '#ef4444', fontSize: '48px' }} />
                <div className="mt-4">
                  <Text_22_700_EEEEEE style={{ color: '#ef4444' }}>
                    {metrics.failureRate.toFixed(1)}%
                  </Text_22_700_EEEEEE>
                </div>
                <Text_12_400_B3B3B3>Failed</Text_12_400_B3B3B3>
              </div>
            </div>
          </ChartCard>
        </Col>
      </Row>
    </div>
  );
};

export default MetricsTab;

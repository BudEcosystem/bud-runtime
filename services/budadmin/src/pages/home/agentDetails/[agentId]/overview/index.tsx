import React, { useEffect, useState, useRef, useCallback } from "react";
import { useRouter } from "next/router";
import { Row, Col, Segmented, Spin } from "antd";
import * as echarts from "echarts";
import dayjs from "dayjs";
import {
  Text_14_600_EEEEEE,
  Text_12_400_B3B3B3,
  Text_12_600_EEEEEE,
  Text_20_400_FFFFFF,
  Text_26_600_FFFFFF,
  Text_15_600_EEEEEE,
  Text_40_400_EEEEEE,
} from "@/components/ui/text";
import Tags from "src/flows/components/DrawerTags";
import { usePrompts, IPrompt } from "src/hooks/usePrompts";
import ProjectTags from "src/flows/components/ProjectTags";
import { endpointStatusMapping } from "@/lib/colorMapping";
import { usePromptMetrics } from "src/hooks/usePromptMetrics";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import { useDrawer } from "src/hooks/useDrawer";
import { PermissionEnum, useUser } from "src/stores/useUser";
import { AppRequest } from "src/pages/api/requests";
import { tempApiBaseUrl } from "@/components/environment";

const segmentOptions = ["daily", "weekly", "monthly"];

// Shared TimeRangeSelector component for independent chart controls
interface TimeRangeSelectorProps {
  value: string;
  onChange: (value: string) => void;
}

const TimeRangeSelector: React.FC<TimeRangeSelectorProps> = ({ value, onChange }) => (
  <Segmented
    options={segmentOptions}
    value={value}
    onChange={(val) => onChange(val as string)}
    className="antSegmented antSegmented-home rounded-md text-[#EEEEEE] text-[.75rem] font-[400] bg-[transparent] border border-[#4D4D4D] border-[.53px] p-[0]"
  />
);

// Extended bucket data for tooltip display
interface ExtendedBucketData {
  value: number;
  bucketStart: number;
  bucketEnd: number;
  timestamp: string;
}

interface OverviewTabProps { }
const capitalize = (str: string) => str?.charAt(0).toUpperCase() + str?.slice(1).toLowerCase();

// Calls Chart Component using ECharts
interface CallsChartProps {
  promptId: string;
}

const CallsChart: React.FC<CallsChartProps> = ({ promptId }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<echarts.ECharts | null>(null);
  const { fetchPromptTimeSeries, PROMPT_METRICS, isLoading } = usePromptMetrics();
  const [timeRange, setTimeRange] = useState("weekly");
  const [chartData, setChartData] = useState<{
    labels: string[];
    data: ExtendedBucketData[];
    totalCalls: number;
  }>({ labels: [], data: [], totalCalls: 0 });

  // Get date range based on time range selection
  const getDateRange = useCallback((range: string): { from: dayjs.Dayjs; to: dayjs.Dayjs; interval: string } => {
    const to = dayjs();
    switch (range) {
      case "daily":
        return { from: to.subtract(24, "hour"), to, interval: "1h" };
      case "weekly":
        return { from: to.subtract(7, "day"), to, interval: "6h" };
      case "monthly":
        return { from: to.subtract(30, "day"), to, interval: "1d" };
      default:
        return { from: to.subtract(7, "day"), to, interval: "6h" };
    }
  }, []);

  // Fetch data from API
  const fetchData = useCallback(async () => {
    if (!promptId) return;

    const { from, to, interval } = getDateRange(timeRange);

    const response = await fetchPromptTimeSeries(
      from,
      to,
      [PROMPT_METRICS.requests],
      { prompt_id: [promptId] },
      { interval, dataSource: "prompt", fillGaps: true }
    );

    if (response && response.groups && response.groups.length > 0) {
      // Aggregate data points from all groups
      const aggregatedData: Map<string, number> = new Map();

      response.groups.forEach((group) => {
        group.data_points.forEach((point) => {
          const timestamp = point.timestamp;
          const value = point.values[PROMPT_METRICS.requests] || 0;
          const existing = aggregatedData.get(timestamp) || 0;
          aggregatedData.set(timestamp, existing + value);
        });
      });

      // Sort by timestamp
      const sortedEntries = Array.from(aggregatedData.entries()).sort(
        (a, b) => new Date(a[0]).getTime() - new Date(b[0]).getTime()
      );

      // Calculate total calls
      const totalCalls = sortedEntries.reduce((sum, [, value]) => sum + value, 0);

      // Format labels based on interval
      const labels = sortedEntries.map(([timestamp]) => {
        const date = new Date(timestamp);
        const hoursDiff = (Date.now() - date.getTime()) / (1000 * 60 * 60);

        if (hoursDiff <= 24) {
          return date.toLocaleTimeString("en-US", {
            hour12: false,
            hour: "2-digit",
            minute: "2-digit",
          });
        } else if (hoursDiff <= 24 * 7) {
          return (
            date.toLocaleDateString("en-US", { weekday: "short" }) +
            " " +
            date.toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit" })
          );
        } else {
          return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
        }
      });

      const data: ExtendedBucketData[] = sortedEntries.map(([timestamp, value], index) => {
        const currentTime = new Date(timestamp).getTime();
        const nextTime = index < sortedEntries.length - 1
          ? new Date(sortedEntries[index + 1][0]).getTime()
          : currentTime + (interval === "1h" ? 3600000 : interval === "6h" ? 21600000 : 86400000);

        return {
          value,
          bucketStart: currentTime,
          bucketEnd: nextTime,
          timestamp,
        };
      });

      setChartData({ labels, data, totalCalls });
    } else {
      setChartData({ labels: [], data: [], totalCalls: 0 });
    }
  }, [promptId, timeRange, fetchPromptTimeSeries, PROMPT_METRICS.requests, getDateRange]);

  // Initialize ECharts
  useEffect(() => {
    if (!chartRef.current) return;

    const myChart = echarts.init(chartRef.current, null, { renderer: "canvas" });
    chartInstanceRef.current = myChart;

    const option: echarts.EChartsOption = {
      backgroundColor: "transparent",
      grid: {
        left: "0%",
        right: "0%",
        bottom: "10%",
        top: "10%",
        containLabel: true,
      },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        backgroundColor: "rgba(24, 24, 27, 0.98)",
        borderColor: "#3f3f46",
        borderWidth: 1,
        padding: [12, 14],
        textStyle: { color: "#fafafa", fontSize: 12 },
        confine: true,
        extraCssText: "box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);",
        formatter: function (params: any) {
          const param = params[0];
          const bucketData = param?.data as ExtendedBucketData;
          const count = bucketData?.value || 0;
          const bucketStart = bucketData?.bucketStart || Date.now();
          const bucketEnd = bucketData?.bucketEnd || Date.now();

          const formatDateTime = (timestamp: number) => {
            const date = new Date(timestamp);
            return (
              date.toLocaleDateString("en-US", { month: "short", day: "numeric" }) +
              ", " +
              date.toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" })
            );
          };

          const cursorPoint = (bucketStart + bucketEnd) / 2;

          return `
            <div style="min-width: 200px;">
              <table style="border-collapse: collapse; width: 100%; font-size: 12px;">
                <tr>
                  <td style="color: #71717a; padding: 2px 12px 2px 0; white-space: nowrap;">Cursor point</td>
                  <td style="color: #fafafa; font-family: monospace; text-align: right;">${formatDateTime(cursorPoint)}</td>
                </tr>
                <tr>
                  <td style="color: #71717a; padding: 2px 12px 2px 0; white-space: nowrap;">Bar period</td>
                  <td style="color: #fafafa; font-family: monospace; text-align: right; font-size: 11px;">
                    ${formatDateTime(bucketStart)} -<br/>${formatDateTime(bucketEnd)}
                  </td>
                </tr>
                <tr>
                  <td style="color: #71717a; padding: 2px 12px 2px 0; white-space: nowrap;">Request Count</td>
                  <td style="color: #fafafa; text-align: right; font-weight: 500;">${count}</td>
                </tr>
              </table>
            </div>
          `;
        },
      },
      xAxis: {
        type: "category",
        data: [],
        axisLine: { lineStyle: { color: "#3f3f46" } },
        axisTick: { show: false },
        axisLabel: {
          color: "#71717a",
          fontSize: 10,
          interval: 0,
          rotate: 0,
        },
        animation: true,
      },
      yAxis: {
        type: "value",
        name: "Request Count",
        nameLocation: "middle",
        nameGap: 40,
        nameTextStyle: { color: "#71717a", fontSize: 11 },
        min: 0,
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: {
          lineStyle: { color: "#3D3D3D", type: "solid" },
        },
        axisLabel: {
          color: "#71717a",
          fontSize: 10,
        },
        minInterval: 1,
      },
      series: [
        {
          name: "Requests",
          type: "bar",
          data: [],
          itemStyle: {
            color: "#965CDE",
            borderRadius: [2, 2, 0, 0],
          },
          emphasis: {
            itemStyle: { color: "#a78bfa" },
          },
          barWidth: "52%",
          animationDuration: 300,
          animationEasing: "linear" as const,
        },
      ],
      animation: true,
      animationDuration: 300,
      animationDurationUpdate: 300,
      animationEasing: "linear" as const,
      animationEasingUpdate: "linear" as const,
    };

    myChart.setOption(option);

    // Handle resize
    const handleResize = () => myChart.resize();
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      myChart.dispose();
      chartInstanceRef.current = null;
    };
  }, []);

  // Fetch data when dependencies change
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Update chart when data changes
  useEffect(() => {
    if (!chartInstanceRef.current || chartData.labels.length === 0) return;

    // Calculate which labels to show (every Nth label for readability)
    const labelInterval = Math.max(1, Math.ceil(chartData.labels.length / 10));

    chartInstanceRef.current.setOption({
      xAxis: {
        data: chartData.labels,
        axisLabel: {
          interval: (index: number) => index % labelInterval === 0,
        },
      },
      series: [{ data: chartData.data }],
    });
  }, [chartData]);

  return (
    <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-[1.57rem] pb-[1rem]">
      <div className="flex justify-between items-center mb-4">
        <div className="relative w-fit">
          <Text_14_600_EEEEEE>Calls</Text_14_600_EEEEEE>
          <div className="absolute h-[3px] w-[90%] bg-[#965CDE]"></div>
        </div>
        <TimeRangeSelector value={timeRange} onChange={setTimeRange} />
      </div>
      <div className="relative">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#101010] bg-opacity-50 z-10">
            <Spin size="small" />
          </div>
        )}
        <Text_20_400_FFFFFF className="mb-3 mt-6">
          {chartData.totalCalls.toLocaleString()} Calls
        </Text_20_400_FFFFFF>
        <div ref={chartRef} style={{ width: "100%", height: 200 }} />
        {chartData.labels.length === 0 && !isLoading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <Text_12_400_B3B3B3>No data available for this time period</Text_12_400_B3B3B3>
          </div>
        )}
      </div>
    </div>
  );
};

// Users Chart Component using ECharts
interface UsersChartProps {
  promptId: string;
}

const UsersChart: React.FC<UsersChartProps> = ({ promptId }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<echarts.ECharts | null>(null);
  const { fetchPromptTimeSeries, PROMPT_METRICS, isLoading } = usePromptMetrics();
  const [timeRange, setTimeRange] = useState("weekly");
  const [chartData, setChartData] = useState<{
    labels: string[];
    data: ExtendedBucketData[];
    totalUsers: number;
  }>({ labels: [], data: [], totalUsers: 0 });

  const getDateRange = useCallback((range: string): { from: dayjs.Dayjs; to: dayjs.Dayjs; interval: string } => {
    const to = dayjs();
    switch (range) {
      case "daily":
        return { from: to.subtract(24, "hour"), to, interval: "1h" };
      case "weekly":
        return { from: to.subtract(7, "day"), to, interval: "6h" };
      case "monthly":
        return { from: to.subtract(30, "day"), to, interval: "1d" };
      default:
        return { from: to.subtract(7, "day"), to, interval: "6h" };
    }
  }, []);

  const fetchData = useCallback(async () => {
    if (!promptId) return;

    const { from, to, interval } = getDateRange(timeRange);

    const response = await fetchPromptTimeSeries(
      from,
      to,
      [PROMPT_METRICS.unique_users],
      { prompt_id: [promptId] },
      { interval, dataSource: "prompt", fillGaps: true }
    );

    if (response && response.groups && response.groups.length > 0) {
      const aggregatedData: Map<string, number> = new Map();

      response.groups.forEach((group) => {
        group.data_points.forEach((point) => {
          const timestamp = point.timestamp;
          const value = point.values[PROMPT_METRICS.unique_users] || 0;
          const existing = aggregatedData.get(timestamp) || 0;
          aggregatedData.set(timestamp, existing + value);
        });
      });

      const sortedEntries = Array.from(aggregatedData.entries()).sort(
        (a, b) => new Date(a[0]).getTime() - new Date(b[0]).getTime()
      );

      const totalUsers = Math.max(...sortedEntries.map(([, value]) => value), 0);

      const labels = sortedEntries.map(([timestamp]) => {
        const date = new Date(timestamp);
        const hoursDiff = (Date.now() - date.getTime()) / (1000 * 60 * 60);
        if (hoursDiff <= 24) {
          return date.toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit" });
        } else if (hoursDiff <= 24 * 7) {
          return date.toLocaleDateString("en-US", { weekday: "short" }) + " " +
            date.toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit" });
        } else {
          return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
        }
      });

      const data: ExtendedBucketData[] = sortedEntries.map(([timestamp, value], index) => {
        const currentTime = new Date(timestamp).getTime();
        const nextTime = index < sortedEntries.length - 1
          ? new Date(sortedEntries[index + 1][0]).getTime()
          : currentTime + (interval === "1h" ? 3600000 : interval === "6h" ? 21600000 : 86400000);
        return { value, bucketStart: currentTime, bucketEnd: nextTime, timestamp };
      });

      setChartData({ labels, data, totalUsers });
    } else {
      setChartData({ labels: [], data: [], totalUsers: 0 });
    }
  }, [promptId, timeRange, fetchPromptTimeSeries, PROMPT_METRICS.unique_users, getDateRange]);

  useEffect(() => {
    if (!chartRef.current) return;

    const myChart = echarts.init(chartRef.current, null, { renderer: "canvas" });
    chartInstanceRef.current = myChart;

    const option: echarts.EChartsOption = {
      backgroundColor: "transparent",
      grid: { left: "0%", right: "0%", bottom: "10%", top: "10%", containLabel: true },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "line" },
        backgroundColor: "rgba(24, 24, 27, 0.98)",
        borderColor: "#3f3f46",
        borderWidth: 1,
        padding: [12, 14],
        textStyle: { color: "#fafafa", fontSize: 12 },
        confine: true,
        formatter: function (params: any) {
          const param = params[0];
          const bucketData = param?.data as ExtendedBucketData;
          const count = bucketData?.value || 0;
          const bucketStart = bucketData?.bucketStart || Date.now();
          const formatDateTime = (timestamp: number) => {
            const date = new Date(timestamp);
            return date.toLocaleDateString("en-US", { month: "short", day: "numeric" }) + ", " +
              date.toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit" });
          };
          return `<div style="min-width: 150px;">
            <div style="color: #71717a; font-size: 11px; margin-bottom: 4px;">${formatDateTime(bucketStart)}</div>
            <div style="color: #fafafa; font-weight: 500;">${count} Users</div>
          </div>`;
        },
      },
      xAxis: {
        type: "category",
        data: [],
        axisLine: { lineStyle: { color: "#3f3f46" } },
        axisTick: { show: false },
        axisLabel: { color: "#71717a", fontSize: 10, interval: 0 },
      },
      yAxis: {
        type: "value",
        min: 0,
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { lineStyle: { color: "#3D3D3D", type: "solid" } },
        axisLabel: { color: "#71717a", fontSize: 10 },
        minInterval: 1,
      },
      series: [{
        name: "Users",
        type: "line",
        data: [],
        smooth: true,
        lineStyle: { color: "#D1B854", width: 2 },
        itemStyle: { color: "#D1B854" },
        areaStyle: { color: "rgba(209, 184, 84, 0.1)" },
        symbol: "circle",
        symbolSize: 6,
        showSymbol: false,
      }],
    };

    myChart.setOption(option);
    const handleResize = () => myChart.resize();
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      myChart.dispose();
      chartInstanceRef.current = null;
    };
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => {
    if (!chartInstanceRef.current || chartData.labels.length === 0) return;
    const labelInterval = Math.max(1, Math.ceil(chartData.labels.length / 8));
    chartInstanceRef.current.setOption({
      xAxis: { data: chartData.labels, axisLabel: { interval: (index: number) => index % labelInterval === 0 } },
      series: [{ data: chartData.data }],
    });
  }, [chartData]);

  return (
    <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-[1.57rem] pb-[1rem]">
      <div className="flex justify-between items-center mb-4">
        <div className="relative w-fit">
          <Text_14_600_EEEEEE>Users</Text_14_600_EEEEEE>
        </div>
        <TimeRangeSelector value={timeRange} onChange={setTimeRange} />
      </div>
      <div className="relative">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#101010] bg-opacity-50 z-10">
            <Spin size="small" />
          </div>
        )}
        <Text_20_400_FFFFFF className="mb-3">{chartData.totalUsers.toLocaleString()}</Text_20_400_FFFFFF>
        <div ref={chartRef} style={{ width: "100%", aspectRatio: 1.3122 }} />
        {chartData.labels.length === 0 && !isLoading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <Text_12_400_B3B3B3>No data available</Text_12_400_B3B3B3>
          </div>
        )}
      </div>
    </div>
  );
};

// Token Usage Chart Component using ECharts
interface TokenUsageChartProps {
  promptId: string;
}

const TokenUsageChart: React.FC<TokenUsageChartProps> = ({ promptId }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<echarts.ECharts | null>(null);
  const { fetchPromptTimeSeries, PROMPT_METRICS, isLoading } = usePromptMetrics();
  const [timeRange, setTimeRange] = useState("weekly");
  const [chartData, setChartData] = useState<{
    labels: string[];
    data: ExtendedBucketData[];
    totalTokens: number;
  }>({ labels: [], data: [], totalTokens: 0 });

  const getDateRange = useCallback((range: string): { from: dayjs.Dayjs; to: dayjs.Dayjs; interval: string } => {
    const to = dayjs();
    switch (range) {
      case "daily": return { from: to.subtract(24, "hour"), to, interval: "1h" };
      case "weekly": return { from: to.subtract(7, "day"), to, interval: "6h" };
      case "monthly": return { from: to.subtract(30, "day"), to, interval: "1d" };
      default: return { from: to.subtract(7, "day"), to, interval: "6h" };
    }
  }, []);

  const fetchData = useCallback(async () => {
    if (!promptId) return;

    const { from, to, interval } = getDateRange(timeRange);

    const response = await fetchPromptTimeSeries(
      from,
      to,
      [PROMPT_METRICS.tokens],
      { prompt_id: [promptId] },
      { interval, dataSource: "prompt", fillGaps: true }
    );

    if (response && response.groups && response.groups.length > 0) {
      const aggregatedData: Map<string, number> = new Map();

      // Debug: log first data point to see the structure
      const firstPoint = response.groups[0]?.data_points?.[0];
      console.log("TokenUsage API response - first data point values:", firstPoint?.values);
      console.log("TokenUsage - tokens value:", firstPoint?.values?.[PROMPT_METRICS.tokens]);

      response.groups.forEach((group) => {
        group.data_points.forEach((point) => {
          const timestamp = point.timestamp;
          const rawValue = point.values?.[PROMPT_METRICS.tokens];
          // Handle both number values and potential nested objects
          const value = typeof rawValue === "number" ? rawValue
            : typeof rawValue === "object" && rawValue !== null ? (rawValue as any).value ?? (rawValue as any).count ?? 0
              : Number(rawValue) || 0;
          const existing = aggregatedData.get(timestamp) || 0;
          aggregatedData.set(timestamp, existing + value);
        });
      });

      const sortedEntries = Array.from(aggregatedData.entries()).sort(
        (a, b) => new Date(a[0]).getTime() - new Date(b[0]).getTime()
      );

      const totalTokens = sortedEntries.reduce((sum, [, value]) => sum + value, 0);

      const labels = sortedEntries.map(([timestamp]) => {
        const date = new Date(timestamp);
        const hoursDiff = (Date.now() - date.getTime()) / (1000 * 60 * 60);
        if (hoursDiff <= 24) {
          return date.toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit" });
        } else if (hoursDiff <= 24 * 7) {
          return date.toLocaleDateString("en-US", { weekday: "short" }) + " " +
            date.toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit" });
        } else {
          return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
        }
      });

      const data: ExtendedBucketData[] = sortedEntries.map(([timestamp, value], index) => {
        const currentTime = new Date(timestamp).getTime();
        const nextTime = index < sortedEntries.length - 1
          ? new Date(sortedEntries[index + 1][0]).getTime()
          : currentTime + (interval === "1h" ? 3600000 : interval === "6h" ? 21600000 : 86400000);
        return { value, bucketStart: currentTime, bucketEnd: nextTime, timestamp };
      });

      setChartData({ labels, data, totalTokens });
    } else {
      setChartData({ labels: [], data: [], totalTokens: 0 });
    }
  }, [promptId, timeRange, fetchPromptTimeSeries, PROMPT_METRICS.tokens, getDateRange]);

  useEffect(() => {
    if (!chartRef.current) return;

    const myChart = echarts.init(chartRef.current, null, { renderer: "canvas" });
    chartInstanceRef.current = myChart;

    const option: echarts.EChartsOption = {
      backgroundColor: "transparent",
      grid: { left: "0%", right: "0%", bottom: "10%", top: "10%", containLabel: true },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        backgroundColor: "rgba(24, 24, 27, 0.98)",
        borderColor: "#3f3f46",
        borderWidth: 1,
        padding: [12, 14],
        textStyle: { color: "#fafafa", fontSize: 12 },
        confine: true,
        formatter: function (params: any) {
          const param = params[0];
          const bucketData = param?.data as ExtendedBucketData;
          const count = bucketData?.value || 0;
          const bucketStart = bucketData?.bucketStart || Date.now();
          const formatDateTime = (timestamp: number) => {
            const date = new Date(timestamp);
            return date.toLocaleDateString("en-US", { month: "short", day: "numeric" }) + ", " +
              date.toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit" });
          };
          const formatNumber = (num: number) => {
            if (num >= 1000000) return (num / 1000000).toFixed(1) + "M";
            if (num >= 1000) return (num / 1000).toFixed(1) + "K";
            return num.toString();
          };
          return `<div style="min-width: 150px;">
            <div style="color: #71717a; font-size: 11px; margin-bottom: 4px;">${formatDateTime(bucketStart)}</div>
            <div style="color: #fafafa; font-weight: 500;">${formatNumber(count)} Tokens</div>
          </div>`;
        },
      },
      xAxis: {
        type: "category",
        data: [],
        axisLine: { lineStyle: { color: "#3f3f46" } },
        axisTick: { show: false },
        axisLabel: { color: "#71717a", fontSize: 10, interval: 0 },
      },
      yAxis: {
        type: "value",
        min: 0,
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { lineStyle: { color: "#3D3D3D", type: "solid" } },
        axisLabel: {
          color: "#71717a",
          fontSize: 10,
          formatter: (value: number) => {
            if (value >= 1000000) return (value / 1000000).toFixed(0) + "M";
            if (value >= 1000) return (value / 1000).toFixed(0) + "K";
            return value.toString();
          },
        },
      },
      series: [{
        name: "Tokens",
        type: "bar",
        data: [],
        itemStyle: { color: "#965CDE", borderRadius: [2, 2, 0, 0] },
        emphasis: { itemStyle: { color: "#a78bfa" } },
        barWidth: "52%",
      }],
    };

    myChart.setOption(option);
    const handleResize = () => myChart.resize();
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      myChart.dispose();
      chartInstanceRef.current = null;
    };
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => {
    if (!chartInstanceRef.current || chartData.labels.length === 0) return;
    const labelInterval = Math.max(1, Math.ceil(chartData.labels.length / 8));
    chartInstanceRef.current.setOption({
      xAxis: { data: chartData.labels, axisLabel: { interval: (index: number) => index % labelInterval === 0 } },
      series: [{ data: chartData.data }],
    });
  }, [chartData]);

  const formatTotal = (num: number) => {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + "M";
    if (num >= 1000) return (num / 1000).toFixed(1) + "K";
    return num.toString();
  };

  return (
    <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-[1.57rem] pb-[1rem]">
      <div className="flex justify-between items-center mb-4">
        <div className="relative w-fit">
          <Text_14_600_EEEEEE>Token Usage</Text_14_600_EEEEEE>
        </div>
        <TimeRangeSelector value={timeRange} onChange={setTimeRange} />
      </div>
      <div className="relative">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#101010] bg-opacity-50 z-10">
            <Spin size="small" />
          </div>
        )}
        <Text_20_400_FFFFFF className="mb-3">{formatTotal(chartData.totalTokens)}</Text_20_400_FFFFFF>
        <div ref={chartRef} style={{ width: "100%", aspectRatio: 1.3122 }} />
        {chartData.labels.length === 0 && !isLoading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <Text_12_400_B3B3B3>No data available</Text_12_400_B3B3B3>
          </div>
        )}
      </div>
    </div>
  );
};

// Request Count by API Key Chart Component using ECharts
interface RequestCountByApiKeyChartProps {
  promptId: string;
}

interface ApiKeyRequestData {
  api_key_id: string;
  api_key_name?: string;
  count: number;
  delta: number;
  delta_percent: number;
}

const RequestCountByApiKeyChart: React.FC<RequestCountByApiKeyChartProps> = ({ promptId }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<echarts.ECharts | null>(null);
  const [timeRange, setTimeRange] = useState("LAST 7 DAYS");
  const [isLoading, setIsLoading] = useState(false);
  const [chartData, setChartData] = useState<{
    labels: string[];
    data: number[];
    totalCount: number;
    avgDeltaPercent: number;
  }>({ labels: [], data: [], totalCount: 0, avgDeltaPercent: 0 });

  const timeRangeOptions = ["LAST 24 HRS", "LAST 7 DAYS", "LAST 30 DAYS"];

  const getDateRange = useCallback((range: string): { from: dayjs.Dayjs; to: dayjs.Dayjs; frequencyUnit: string; frequencyInterval: number } => {
    const to = dayjs();
    switch (range) {
      case "LAST 24 HRS":
        return { from: to.subtract(24, "hour"), to, frequencyUnit: "hour", frequencyInterval: 1 };
      case "LAST 7 DAYS":
        return { from: to.subtract(7, "day"), to, frequencyUnit: "day", frequencyInterval: 1 };
      case "LAST 30 DAYS":
        return { from: to.subtract(30, "day"), to, frequencyUnit: "day", frequencyInterval: 1 };
      default:
        return { from: to.subtract(7, "day"), to, frequencyUnit: "day", frequencyInterval: 1 };
    }
  }, []);

  const fetchData = useCallback(async () => {
    if (!promptId) return;
    setIsLoading(true);

    try {
      const { from, to, frequencyUnit, frequencyInterval } = getDateRange(timeRange);

      const response = await AppRequest.Post(`${tempApiBaseUrl}/metrics/analytics`, {
        metrics: ["request_count"],
        from_date: from.toISOString(),
        to_date: to.toISOString(),
        frequency_unit: frequencyUnit,
        frequency_interval: frequencyInterval,
        return_delta: true,
        fill_time_gaps: true,
        filters: {
          prompt: [promptId]
        },
        group_by: ["api_key"],
        data_source: "prompt"
      });

      if (response && response.data) {
        // Response structure: { object: "observability_metrics", items: [...time_periods] }
        const apiKeyData: Map<string, ApiKeyRequestData> = new Map();
        const timePeriods = response.data.items || [];

        // Aggregate data across all time periods per API key
        timePeriods.forEach((period: any) => {
          if (period.items && Array.isArray(period.items)) {
            period.items.forEach((item: any) => {
              const apiKeyId = item.api_key_id || "unknown";
              const apiKeyName = item.api_key_name || apiKeyId;
              const requestCount = item.data?.request_count?.count || 0;
              const delta = item.data?.request_count?.delta || 0;
              const deltaPercent = item.data?.request_count?.delta_percent || 0;

              const existing = apiKeyData.get(apiKeyId);
              if (existing) {
                existing.count += requestCount;
                // Keep the most recent delta_percent (first non-zero one)
                if (existing.delta_percent === 0 && deltaPercent !== 0) {
                  existing.delta_percent = deltaPercent;
                }
              } else {
                apiKeyData.set(apiKeyId, {
                  api_key_id: apiKeyId,
                  api_key_name: apiKeyName,
                  count: requestCount,
                  delta,
                  delta_percent: deltaPercent
                });
              }
            });
          }
        });

        const sortedData = Array.from(apiKeyData.values()).sort((a, b) => b.count - a.count);

        const labels = sortedData.map(item => {
          const name = item.api_key_name || item.api_key_id;
          return name.length > 10 ? name.substring(0, 10) + "..." : name;
        });
        const data = sortedData.map(item => item.count);
        const totalCount = data.reduce((sum, val) => sum + val, 0);

        // Calculate weighted average delta percent based on count
        let avgDeltaPercent = 0;
        if (totalCount > 0) {
          const weightedSum = sortedData.reduce((sum, item) => sum + (item.delta_percent * item.count), 0);
          avgDeltaPercent = weightedSum / totalCount;
        }

        setChartData({ labels, data, totalCount, avgDeltaPercent });
      } else {
        setChartData({ labels: [], data: [], totalCount: 0, avgDeltaPercent: 0 });
      }
    } catch (err) {
      console.error("Error fetching request count by API key:", err);
      setChartData({ labels: [], data: [], totalCount: 0, avgDeltaPercent: 0 });
    } finally {
      setIsLoading(false);
    }
  }, [promptId, timeRange, getDateRange]);

  useEffect(() => {
    if (!chartRef.current) return;

    const myChart = echarts.init(chartRef.current, null, { renderer: "canvas" });
    chartInstanceRef.current = myChart;

    const option: echarts.EChartsOption = {
      backgroundColor: "transparent",
      grid: { left: "0%", right: "0%", bottom: "15%", top: "10%", containLabel: true },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        backgroundColor: "rgba(24, 24, 27, 0.98)",
        borderColor: "#3f3f46",
        borderWidth: 1,
        padding: [12, 14],
        textStyle: { color: "#fafafa", fontSize: 12 },
        confine: true,
        formatter: function (params: any) {
          const param = params[0];
          const apiKey = param?.name || "";
          const count = param?.value || 0;
          return `<div style="min-width: 150px;">
            <div style="color: #71717a; font-size: 11px; margin-bottom: 4px;">API Key: ${apiKey}</div>
            <div style="color: #fafafa; font-weight: 500;">Request Count: ${count}</div>
          </div>`;
        },
      },
      xAxis: {
        type: "category",
        data: [],
        axisLine: { lineStyle: { color: "#3f3f46" } },
        axisTick: { show: false },
        axisLabel: { color: "#71717a", fontSize: 10, interval: 0, rotate: 0 },
      },
      yAxis: {
        type: "value",
        min: 0,
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { lineStyle: { color: "#3D3D3D", type: "solid" } },
        axisLabel: { color: "#71717a", fontSize: 10 },
        minInterval: 1,
      },
      series: [{
        name: "Request Count",
        type: "bar",
        data: [],
        itemStyle: { color: "#965CDE", borderRadius: [2, 2, 0, 0] },
        emphasis: { itemStyle: { color: "#a78bfa" } },
        barMaxWidth: 20,
      }],
    };

    myChart.setOption(option);
    const handleResize = () => myChart.resize();
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      myChart.dispose();
      chartInstanceRef.current = null;
    };
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => {
    if (!chartInstanceRef.current || chartData.labels.length === 0) return;
    chartInstanceRef.current.setOption({
      xAxis: { data: chartData.labels },
      series: [{ data: chartData.data }],
    });
  }, [chartData]);

  const formatDelta = (delta: number) => {
    const arrow = delta >= 0 ? "\u2197" : "\u2198";
    return `Avg. ${delta.toFixed(2)}% ${arrow}`;
  };

  return (
    <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-[1.57rem] pb-[1rem]">
      <div className="flex justify-between items-center mb-4">
        <div className="relative w-fit">
          <Text_14_600_EEEEEE>Request count</Text_14_600_EEEEEE>
        </div>
        <Segmented
          options={timeRangeOptions}
          value={timeRange}
          onChange={(val) => setTimeRange(val as string)}
          className="antSegmented antSegmented-home rounded-md text-[#EEEEEE] text-[.75rem] font-[400] bg-[transparent] border border-[#4D4D4D] border-[.53px] p-[0]"
        />
      </div>
      <div className="relative">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#101010] bg-opacity-50 z-10">
            <Spin size="small" />
          </div>
        )}
        <Text_20_400_FFFFFF className="mb-1">{chartData.totalCount.toFixed(2)}</Text_20_400_FFFFFF>
        <div className={`text-[.75rem] mb-3 ${chartData.avgDeltaPercent >= 0 ? "text-[#479D5F]" : "text-[#EF4444]"}`}>
          {formatDelta(chartData.avgDeltaPercent)}
        </div>
        <div ref={chartRef} style={{ width: "100%", aspectRatio: 1.3122 }} />
        {chartData.labels.length === 0 && !isLoading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <Text_12_400_B3B3B3>No data available</Text_12_400_B3B3B3>
          </div>
        )}
      </div>
    </div>
  );
};

// Error vs Success Chart Component using ECharts
interface ErrorSuccessChartProps {
  promptId: string;
}

const ErrorSuccessChart: React.FC<ErrorSuccessChartProps> = ({ promptId }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<echarts.ECharts | null>(null);
  const { fetchPromptTimeSeries, PROMPT_METRICS, isLoading } = usePromptMetrics();
  const [timeRange, setTimeRange] = useState("weekly");
  const [chartData, setChartData] = useState<{
    labels: string[];
    errorData: ExtendedBucketData[];
    successData: ExtendedBucketData[];
  }>({ labels: [], errorData: [], successData: [] });

  const getDateRange = useCallback((range: string): { from: dayjs.Dayjs; to: dayjs.Dayjs; interval: string } => {
    const to = dayjs();
    switch (range) {
      case "daily": return { from: to.subtract(24, "hour"), to, interval: "1h" };
      case "weekly": return { from: to.subtract(7, "day"), to, interval: "6h" };
      case "monthly": return { from: to.subtract(30, "day"), to, interval: "1d" };
      default: return { from: to.subtract(7, "day"), to, interval: "6h" };
    }
  }, []);

  const fetchData = useCallback(async () => {
    if (!promptId) return;

    const { from, to, interval } = getDateRange(timeRange);

    const response = await fetchPromptTimeSeries(
      from,
      to,
      [PROMPT_METRICS.error_count, PROMPT_METRICS.success_count],
      { prompt_id: [promptId] },
      { interval, dataSource: "prompt", fillGaps: true }
    );

    if (response && response.groups && response.groups.length > 0) {
      const errorAggregated: Map<string, number> = new Map();
      const successAggregated: Map<string, number> = new Map();

      response.groups.forEach((group) => {
        group.data_points.forEach((point) => {
          const timestamp = point.timestamp;
          const errorVal = point.values[PROMPT_METRICS.error_count] || 0;
          const successVal = point.values[PROMPT_METRICS.success_count] || 0;
          errorAggregated.set(timestamp, (errorAggregated.get(timestamp) || 0) + errorVal);
          successAggregated.set(timestamp, (successAggregated.get(timestamp) || 0) + successVal);
        });
      });

      const allTimestamps = Array.from(new Set([...Array.from(errorAggregated.keys()), ...Array.from(successAggregated.keys())])).sort(
        (a, b) => new Date(a).getTime() - new Date(b).getTime()
      );

      const labels = allTimestamps.map((timestamp) => {
        const date = new Date(timestamp);
        const hoursDiff = (Date.now() - date.getTime()) / (1000 * 60 * 60);
        if (hoursDiff <= 24) {
          return date.toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit" });
        } else if (hoursDiff <= 24 * 7) {
          return date.toLocaleDateString("en-US", { weekday: "short" }) + " " +
            date.toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit" });
        } else {
          return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
        }
      });

      const errorData: ExtendedBucketData[] = allTimestamps.map((timestamp, index) => {
        const currentTime = new Date(timestamp).getTime();
        const nextTime = index < allTimestamps.length - 1
          ? new Date(allTimestamps[index + 1]).getTime()
          : currentTime + (interval === "1h" ? 3600000 : interval === "6h" ? 21600000 : 86400000);
        return {
          value: errorAggregated.get(timestamp) || 0,
          bucketStart: currentTime,
          bucketEnd: nextTime,
          timestamp,
        };
      });

      const successData: ExtendedBucketData[] = allTimestamps.map((timestamp, index) => {
        const currentTime = new Date(timestamp).getTime();
        const nextTime = index < allTimestamps.length - 1
          ? new Date(allTimestamps[index + 1]).getTime()
          : currentTime + (interval === "1h" ? 3600000 : interval === "6h" ? 21600000 : 86400000);
        return {
          value: successAggregated.get(timestamp) || 0,
          bucketStart: currentTime,
          bucketEnd: nextTime,
          timestamp,
        };
      });

      setChartData({ labels, errorData, successData });
    } else {
      setChartData({ labels: [], errorData: [], successData: [] });
    }
  }, [promptId, timeRange, fetchPromptTimeSeries, PROMPT_METRICS.error_count, PROMPT_METRICS.success_count, getDateRange]);

  useEffect(() => {
    if (!chartRef.current) return;

    const myChart = echarts.init(chartRef.current, null, { renderer: "canvas" });
    chartInstanceRef.current = myChart;

    const option: echarts.EChartsOption = {
      backgroundColor: "transparent",
      grid: { left: "0%", right: "0%", bottom: "5%", top: "25%", containLabel: true },
      legend: {
        data: ["Error Requests", "Successful Requests"],
        orient: "vertical",
        left: 0,
        top: 0,
        icon: "roundRect",
        textStyle: { color: "#B3B3B3", fontSize: 11 },
        itemWidth: 10,
        itemHeight: 10,
        itemGap: 20,
      },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "line" },
        backgroundColor: "rgba(24, 24, 27, 0.98)",
        borderColor: "#3f3f46",
        borderWidth: 1,
        padding: [12, 14],
        textStyle: { color: "#fafafa", fontSize: 12 },
        confine: true,
        formatter: function (params: any) {
          const errorParam = params.find((p: any) => p.seriesName === "Error Requests");
          const successParam = params.find((p: any) => p.seriesName === "Successful Requests");
          const bucketData = (errorParam?.data || successParam?.data) as ExtendedBucketData;
          const bucketStart = bucketData?.bucketStart || Date.now();
          const formatDateTime = (timestamp: number) => {
            const date = new Date(timestamp);
            return date.toLocaleDateString("en-US", { month: "short", day: "numeric" }) + ", " +
              date.toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit" });
          };
          return `<div style="min-width: 150px;">
            <div style="color: #71717a; font-size: 11px; margin-bottom: 8px;">${formatDateTime(bucketStart)}</div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
              <span style="color: #479D5F;">Successful Requests:</span>
              <span style="color: #fafafa; font-weight: 500;">${successParam?.data?.value || 0}</span>
            </div>
            <div style="display: flex; justify-content: space-between;">
              <span style="color: #D1B854;">Error Requests:</span>
              <span style="color: #fafafa; font-weight: 500;">${errorParam?.data?.value || 0}</span>
            </div>
          </div>`;
        },
      },
      xAxis: {
        type: "category",
        data: [],
        axisLine: { lineStyle: { color: "#3f3f46" } },
        axisTick: { show: false },
        axisLabel: { color: "#71717a", fontSize: 10, interval: 0 },
      },
      yAxis: {
        type: "value",
        min: 0,
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { lineStyle: { color: "#3D3D3D", type: "solid" } },
        axisLabel: { color: "#71717a", fontSize: 10 },
        minInterval: 1,
      },
      series: [
        {
          name: "Error Requests",
          type: "line",
          data: [],
          smooth: true,
          lineStyle: { color: "#D1B854", width: 2 },
          itemStyle: { color: "#D1B854" },
          symbol: "circle",
          symbolSize: 6,
          showSymbol: false,
        },
        {
          name: "Successful Requests",
          type: "line",
          data: [],
          smooth: true,
          lineStyle: { color: "#479D5F", width: 2 },
          itemStyle: { color: "#479D5F" },
          symbol: "circle",
          symbolSize: 6,
          showSymbol: false,
        },
      ],
    };

    myChart.setOption(option);
    const handleResize = () => myChart.resize();
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      myChart.dispose();
      chartInstanceRef.current = null;
    };
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => {
    if (!chartInstanceRef.current || chartData.labels.length === 0) return;
    const labelInterval = Math.max(1, Math.ceil(chartData.labels.length / 8));
    chartInstanceRef.current.setOption({
      xAxis: { data: chartData.labels, axisLabel: { interval: (index: number) => index % labelInterval === 0 } },
      series: [
        { name: "Error Requests", data: chartData.errorData },
        { name: "Successful Requests", data: chartData.successData },
      ],
    });
  }, [chartData]);

  return (
    <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-[1.57rem] pb-[1rem] h-full">
      <div className="flex justify-between items-center mb-4">
        <div className="relative w-fit">
          <Text_14_600_EEEEEE>Error vs Successful requests</Text_14_600_EEEEEE>
        </div>
        <TimeRangeSelector value={timeRange} onChange={setTimeRange} />
      </div>
      <div className="relative">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#101010] bg-opacity-50 z-10">
            <Spin size="small" />
          </div>
        )}
        <div ref={chartRef} style={{ width: "100%", aspectRatio: 1.3122 }} />
        {chartData.labels.length === 0 && !isLoading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <Text_12_400_B3B3B3>No data available</Text_12_400_B3B3B3>
          </div>
        )}
      </div>
    </div>
  );
};

// E2E Latency vs Concurrent Requests Chart Component using ECharts
interface E2ELatencyChartProps {
  promptId: string;
}

const E2ELatencyChart: React.FC<E2ELatencyChartProps> = ({ promptId }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<echarts.ECharts | null>(null);
  const { fetchDistribution, DISTRIBUTION_METRICS, DISTRIBUTION_BUCKET_BY, isLoading } = usePromptMetrics();
  const [timeRange, setTimeRange] = useState("weekly");
  const [chartData, setChartData] = useState<{
    labels: string[];
    data: number[];
  }>({ labels: [], data: [] });

  const getDateRange = useCallback((range: string): { from: dayjs.Dayjs; to: dayjs.Dayjs } => {
    const to = dayjs();
    switch (range) {
      case "daily":
        return { from: to.subtract(24, "hour"), to };
      case "weekly":
        return { from: to.subtract(7, "day"), to };
      case "monthly":
        return { from: to.subtract(30, "day"), to };
      default:
        return { from: to.subtract(7, "day"), to };
    }
  }, []);

  const fetchData = useCallback(async () => {
    if (!promptId) return;
    const { from, to } = getDateRange(timeRange);

    const response = await fetchDistribution(
      from,
      to,
      DISTRIBUTION_BUCKET_BY.concurrency as "concurrency",
      DISTRIBUTION_METRICS.total_duration_ms,
      { prompt_id: [promptId] }
    );

    if (response && response.buckets && response.buckets.length > 0) {
      const labels = response.buckets.map(bucket => bucket.range);
      const data = response.buckets.map(bucket => bucket.avg_value);
      setChartData({ labels, data });
    } else {
      setChartData({ labels: [], data: [] });
    }
  }, [promptId, timeRange, fetchDistribution, DISTRIBUTION_METRICS, DISTRIBUTION_BUCKET_BY, getDateRange]);

  useEffect(() => {
    if (!chartRef.current) return;
    const myChart = echarts.init(chartRef.current, "dark");
    chartInstanceRef.current = myChart;

    const option: echarts.EChartsOption = {
      backgroundColor: "transparent",
      grid: { left: 50, right: 20, top: 30, bottom: 30 },
      tooltip: {
        trigger: "axis",
        backgroundColor: "#18181b",
        borderColor: "#3f3f46",
        textStyle: { color: "#fafafa" },
        formatter: (params: any) => {
          const param = Array.isArray(params) ? params[0] : params;
          return `<div style="padding: 4px 8px;">
            <div style="color: #71717a; margin-bottom: 4px;">Concurrency: ${param.name}</div>
            <div style="color: #fafafa; font-weight: 500;">Avg Latency: ${param.value?.toFixed(2) || 0} ms</div>
          </div>`;
        },
      },
      xAxis: {
        type: "category",
        name: "Concurrency",
        nameLocation: "middle",
        nameGap: 35,
        nameTextStyle: { color: "#B3B3B3", fontSize: 11 },
        data: [],
        axisLine: { lineStyle: { color: "#3f3f46" } },
        axisTick: { show: false },
        axisLabel: { color: "#71717a", fontSize: 10, rotate: 45 },
      },
      yAxis: {
        type: "value",
        name: "E2E Latency (ms)",
        nameLocation: "middle",
        nameGap: 40,
        nameTextStyle: { color: "#B3B3B3", fontSize: 11 },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { lineStyle: { color: "#3D3D3D", type: "solid" } },
        axisLabel: { color: "#71717a", fontSize: 10 },
      },
      series: [
        {
          type: "line",
          data: [],
          smooth: true,
          lineStyle: { color: "#D1B854", width: 2 },
          itemStyle: { color: "#D1B854" },
          symbol: "circle",
          symbolSize: 6,
          showSymbol: true,
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: "rgba(209, 184, 84, 0.3)" },
              { offset: 1, color: "rgba(209, 184, 84, 0)" },
            ]),
          },
        },
      ],
    };

    myChart.setOption(option);
    const handleResize = () => myChart.resize();
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      myChart.dispose();
      chartInstanceRef.current = null;
    };
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => {
    if (!chartInstanceRef.current || chartData.labels.length === 0) return;
    chartInstanceRef.current.setOption({
      xAxis: { data: chartData.labels },
      series: [{ data: chartData.data }],
    });
  }, [chartData]);

  return (
    <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6 h-full">
      <div className="flex justify-between items-center mb-4">
        <div className="relative w-fit">
          <Text_14_600_EEEEEE>E2E Latency vs Concurrent Requests</Text_14_600_EEEEEE>
        </div>
        <TimeRangeSelector value={timeRange} onChange={setTimeRange} />
      </div>
      <div className="relative">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#101010] bg-opacity-50 z-10">
            <Spin size="small" />
          </div>
        )}
        <div ref={chartRef} style={{ width: "100%", aspectRatio: 1.3122 }} />
        {chartData.labels.length === 0 && !isLoading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <Text_12_400_B3B3B3>No data available</Text_12_400_B3B3B3>
          </div>
        )}
      </div>
    </div>
  );
};

// TTFT vs Input Tokens Chart Component using ECharts
interface TTFTChartProps {
  promptId: string;
}

const TTFTChart: React.FC<TTFTChartProps> = ({ promptId }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<echarts.ECharts | null>(null);
  const { fetchDistribution, DISTRIBUTION_METRICS, DISTRIBUTION_BUCKET_BY, isLoading } = usePromptMetrics();
  const [timeRange, setTimeRange] = useState("weekly");
  const [chartData, setChartData] = useState<{
    labels: string[];
    data: number[];
  }>({ labels: [], data: [] });

  const getDateRange = useCallback((range: string): { from: dayjs.Dayjs; to: dayjs.Dayjs } => {
    const to = dayjs();
    switch (range) {
      case "daily":
        return { from: to.subtract(24, "hour"), to };
      case "weekly":
        return { from: to.subtract(7, "day"), to };
      case "monthly":
        return { from: to.subtract(30, "day"), to };
      default:
        return { from: to.subtract(7, "day"), to };
    }
  }, []);

  const fetchData = useCallback(async () => {
    if (!promptId) return;
    const { from, to } = getDateRange(timeRange);

    const response = await fetchDistribution(
      from,
      to,
      DISTRIBUTION_BUCKET_BY.input_tokens as "input_tokens",
      DISTRIBUTION_METRICS.ttft_ms,
      { prompt_id: [promptId] }
    );

    if (response && response.buckets && response.buckets.length > 0) {
      const labels = response.buckets.map(bucket => bucket.range);
      const data = response.buckets.map(bucket => bucket.avg_value);
      setChartData({ labels, data });
    } else {
      setChartData({ labels: [], data: [] });
    }
  }, [promptId, timeRange, fetchDistribution, DISTRIBUTION_METRICS, DISTRIBUTION_BUCKET_BY, getDateRange]);

  useEffect(() => {
    if (!chartRef.current) return;
    const myChart = echarts.init(chartRef.current, "dark");
    chartInstanceRef.current = myChart;

    const option: echarts.EChartsOption = {
      backgroundColor: "transparent",
      grid: { left: 50, right: 20, top: 30, bottom: 55 },
      tooltip: {
        trigger: "axis",
        backgroundColor: "#18181b",
        borderColor: "#3f3f46",
        textStyle: { color: "#fafafa" },
        formatter: (params: any) => {
          const param = Array.isArray(params) ? params[0] : params;
          return `<div style="padding: 4px 8px;">
            <div style="color: #71717a; margin-bottom: 4px;">Input Tokens: ${param.name}</div>
            <div style="color: #fafafa; font-weight: 500;">Avg TTFT: ${param.value?.toFixed(2) || 0} ms</div>
          </div>`;
        },
      },
      xAxis: {
        type: "category",
        name: "Input Tokens",
        nameLocation: "middle",
        nameGap: 45,
        nameTextStyle: { color: "#B3B3B3", fontSize: 11 },
        data: [],
        axisLine: { lineStyle: { color: "#3f3f46" } },
        axisTick: { show: false },
        axisLabel: { color: "#71717a", fontSize: 10, rotate: 45 },
      },
      yAxis: {
        type: "value",
        name: "TTFT (ms)",
        nameLocation: "middle",
        nameGap: 40,
        nameTextStyle: { color: "#B3B3B3", fontSize: 11 },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { lineStyle: { color: "#3D3D3D", type: "solid" } },
        axisLabel: { color: "#71717a", fontSize: 10 },
      },
      series: [
        {
          type: "line",
          data: [],
          smooth: true,
          lineStyle: { color: "#D1B854", width: 2 },
          itemStyle: { color: "#D1B854" },
          symbol: "circle",
          symbolSize: 6,
          showSymbol: true,
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: "rgba(209, 184, 84, 0.3)" },
              { offset: 1, color: "rgba(209, 184, 84, 0)" },
            ]),
          },
        },
      ],
    };

    myChart.setOption(option);
    const handleResize = () => myChart.resize();
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      myChart.dispose();
      chartInstanceRef.current = null;
    };
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => {
    if (!chartInstanceRef.current || chartData.labels.length === 0) return;
    chartInstanceRef.current.setOption({
      xAxis: { data: chartData.labels },
      series: [{ data: chartData.data }],
    });
  }, [chartData]);

  return (
    <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6 h-full">
      <div className="flex justify-between items-center mb-4">
        {/* <div className="relative w-fit">
          <Text_14_600_EEEEEE>TTFT vs Input Tokens</Text_14_600_EEEEEE>
          <Text_14_600_EEEEEE>a</Text_14_600_EEEEEE>
        </div> */}
        <div className="max-w-[55%]">
          <div className="relative min-h-[4rem]">
            <Text_14_600_EEEEEE className="w-full">TTFT vs Input Tokens</Text_14_600_EEEEEE>
          </div>
        </div>
        <TimeRangeSelector value={timeRange} onChange={setTimeRange} />
      </div>
      <div className="relative">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#101010] bg-opacity-50 z-10">
            <Spin size="small" />
          </div>
        )}
        <div ref={chartRef} style={{ width: "100%", aspectRatio: 1.3122 }} />
        {chartData.labels.length === 0 && !isLoading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <Text_12_400_B3B3B3>No data available</Text_12_400_B3B3B3>
          </div>
        )}
      </div>
    </div>
  );
};

// Average Throughput/User by Concurrency Chart Component using ECharts
interface ThroughputChartProps {
  promptId: string;
}

const ThroughputChart: React.FC<ThroughputChartProps> = ({ promptId }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<echarts.ECharts | null>(null);
  const { fetchDistribution, DISTRIBUTION_METRICS, DISTRIBUTION_BUCKET_BY, isLoading } = usePromptMetrics();
  const [timeRange, setTimeRange] = useState("weekly");
  const [chartData, setChartData] = useState<{
    labels: string[];
    data: number[];
  }>({ labels: [], data: [] });

  const getDateRange = useCallback((range: string): { from: dayjs.Dayjs; to: dayjs.Dayjs } => {
    const to = dayjs();
    switch (range) {
      case "daily":
        return { from: to.subtract(24, "hour"), to };
      case "weekly":
        return { from: to.subtract(7, "day"), to };
      case "monthly":
        return { from: to.subtract(30, "day"), to };
      default:
        return { from: to.subtract(7, "day"), to };
    }
  }, []);

  const fetchData = useCallback(async () => {
    if (!promptId) return;
    const { from, to } = getDateRange(timeRange);

    const response = await fetchDistribution(
      from,
      to,
      DISTRIBUTION_BUCKET_BY.concurrency as "concurrency",
      DISTRIBUTION_METRICS.throughput_per_user,
      { prompt_id: [promptId] }
    );

    if (response && response.buckets && response.buckets.length > 0) {
      const labels = response.buckets.map(bucket => bucket.range);
      const data = response.buckets.map(bucket => bucket.avg_value);
      setChartData({ labels, data });
    } else {
      setChartData({ labels: [], data: [] });
    }
  }, [promptId, timeRange, fetchDistribution, DISTRIBUTION_METRICS, DISTRIBUTION_BUCKET_BY, getDateRange]);

  useEffect(() => {
    if (!chartRef.current) return;
    const myChart = echarts.init(chartRef.current, "dark");
    chartInstanceRef.current = myChart;

    const option: echarts.EChartsOption = {
      backgroundColor: "transparent",
      grid: { left: 80, right: 20, top: 30, bottom: 55 },
      tooltip: {
        trigger: "axis",
        backgroundColor: "#18181b",
        borderColor: "#3f3f46",
        textStyle: { color: "#fafafa" },
        formatter: (params: any) => {
          const param = Array.isArray(params) ? params[0] : params;
          return `<div style="padding: 4px 8px;">
            <div style="color: #71717a; margin-bottom: 4px;">Concurrency: ${param.name}</div>
            <div style="color: #fafafa; font-weight: 500;">Avg Throughput: ${param.value?.toFixed(2) || 0} tokens/s</div>
          </div>`;
        },
      },
      xAxis: {
        type: "category",
        name: "Concurrency",
        nameLocation: "middle",
        nameGap: 30,
        nameTextStyle: { color: "#B3B3B3", fontSize: 11 },
        data: [],
        axisLine: { lineStyle: { color: "#3f3f46" } },
        axisTick: { show: false },
        axisLabel: { color: "#71717a", fontSize: 10, rotate: 45 },
      },
      yAxis: {
        type: "value",
        name: "Avg Throughput/User",
        nameLocation: "middle",
        nameGap: 55,
        nameTextStyle: { color: "#B3B3B3", fontSize: 11 },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { lineStyle: { color: "#3D3D3D", type: "solid" } },
        axisLabel: { color: "#71717a", fontSize: 10 },
      },
      series: [
        {
          type: "bar",
          data: [],
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: "#965CDE" },
              { offset: 1, color: "rgba(150, 92, 222, 0.4)" },
            ]),
            borderRadius: [4, 4, 0, 0],
          },
          barWidth: "60%",
        },
      ],
    };

    myChart.setOption(option);
    const handleResize = () => myChart.resize();
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      myChart.dispose();
      chartInstanceRef.current = null;
    };
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => {
    if (!chartInstanceRef.current || chartData.labels.length === 0) return;
    chartInstanceRef.current.setOption({
      xAxis: { data: chartData.labels },
      series: [{ data: chartData.data }],
    });
  }, [chartData]);

  return (
    <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6 h-full">
      <div className="flex justify-between items-start mb-4">
        <div className="max-w-[55%]">
          <div className="relative min-h-[4rem]">
            <Text_14_600_EEEEEE className="w-full">Average Throughput/User by Concurrency</Text_14_600_EEEEEE>
          </div>
        </div>
        <TimeRangeSelector value={timeRange} onChange={setTimeRange} />
      </div>
      <div className="relative">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#101010] bg-opacity-50 z-10">
            <Spin size="small" />
          </div>
        )}
        <div ref={chartRef} style={{ width: "100%", aspectRatio: 1.3122 }} />
        {chartData.labels.length === 0 && !isLoading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <Text_12_400_B3B3B3>No data available</Text_12_400_B3B3B3>
          </div>
        )}
      </div>
    </div>
  );
};

const OverviewTab: React.FC<OverviewTabProps> = () => {
  const router = useRouter();
  // Support both 'id' (from rewrite rule) and 'agentId' (from folder name)
  const { id, agentId, projectId } = router.query;
  const promptId = id || agentId;
  const [agentData, setAgentData] = useState<IPrompt | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [costMetrics, setCostMetrics] = useState<{
    p95: string;
    max: string;
    min: string;
  } | null>(null);
  const [costMetricsLoading, setCostMetricsLoading] = useState(false);
  const [costMetricsError, setCostMetricsError] = useState<string | null>(null);
  const { getPromptById } = usePrompts();
  const { openDrawer } = useDrawer();
  const { hasPermission } = useUser();

  // Check if we're in development mode
  const isDevelopmentMode = process.env.NEXT_PUBLIC_VERCEL_ENV === "development" ||
    process.env.NODE_ENV === "development";

  const fetchAgentDetails = async () => {
    if (promptId && typeof promptId === "string") {
      try {
        setLoading(true);
        setError(null);
        const data = await getPromptById(promptId, projectId as string);
        setAgentData(data);
      } catch (error: any) {
        console.error("Error fetching agent details:", error);
        const errorMessage = error?.response?.data?.detail ||
          error?.message ||
          "Failed to load agent details. Please try again.";
        setError(errorMessage);

        // Only set fallback data in development mode
        if (isDevelopmentMode) {
          console.warn("Development mode: Using fallback data");
          setAgentData({
            id: promptId,
            name: "Agent Name (Dev Fallback)",
            prompt_type: "chat",
            description: "LiveMathBench can capture LLM capabilities in complex reasoning tasks, including challenging latest question sets from various mathematical competitions.",
            tags: [
              { name: "tag 1", color: "#965CDE" },
              { name: "tag 2", color: "#5CADFF" },
              { name: "tag 3", color: "#479D5F" },
            ],
            status: "Active",
            created_at: new Date().toISOString(),
            modified_at: new Date().toISOString(),
          });
        }
      } finally {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    fetchAgentDetails();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [promptId, projectId]);

  const formatCostValue = (value: number): string => {
    return `$${value.toFixed(2)}`;
  };

  const fetchCostMetrics = useCallback(async () => {
    if (!promptId || typeof promptId !== "string") return;

    setCostMetricsLoading(true);
    setCostMetricsError(null);
    try {
      const response = await AppRequest.Post(
        `${tempApiBaseUrl}/metrics/aggregated`,
        {
          data_source: "prompt",
          filters: { prompt_id: promptId },
          metrics: [
            "p95_inference_cost",
            "max_inference_cost",
            "min_inference_cost",
          ],
        },
      );

      if (response?.data?.summary) {
        const summary = response.data.summary;
        setCostMetrics({
          p95: formatCostValue(summary.p95_inference_cost?.value ?? 0),
          max: formatCostValue(summary.max_inference_cost?.value ?? 0),
          min: formatCostValue(summary.min_inference_cost?.value ?? 0),
        });
      }
    } catch (error) {
      console.error("Error fetching cost metrics:", error);
      setCostMetricsError("Failed to load cost metrics.");
    } finally {
      setCostMetricsLoading(false);
    }
  }, [promptId]);

  useEffect(() => {
    fetchCostMetrics();
  }, [fetchCostMetrics]);

  if (loading) {
    return (
      <div className="flex justify-center items-center h-96">
        <Spin size="large" />
      </div>
    );
  }

  // Error state display with retry functionality
  if (error && !agentData) {
    return (
      <div className="flex flex-col justify-center items-center h-96 gap-4">
        <div className="text-center max-w-md">
          <div className="text-[#EF4444] text-5xl mb-4">⚠️</div>
          <Text_14_600_EEEEEE className="block mb-2">
            Unable to Load Agent Details
          </Text_14_600_EEEEEE>
          <Text_12_400_B3B3B3 className="block mb-4">
            {error}
          </Text_12_400_B3B3B3>
          <button
            onClick={fetchAgentDetails}
            className="px-6 py-2 bg-[#965CDE] hover:bg-[#7B4AB8] text-white rounded-md transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Show warning banner if using fallback data in development
  const showDevWarning = isDevelopmentMode && error && agentData;

  return (
    <div className="pb-8">
      {/* Development Mode Warning Banner */}
      {showDevWarning && (
        <div className="mb-4 p-4 bg-[#FFA500] bg-opacity-10 border border-[#FFA500] rounded-lg flex items-start gap-3">
          <div className="text-[#FFA500] text-xl">⚠️</div>
          <div className="flex-1">
            <Text_12_600_EEEEEE className="block mb-1 text-[#FFA500]">
              Development Mode - Using Fallback Data
            </Text_12_600_EEEEEE>
            <Text_12_400_B3B3B3 className="block">
              {error}
            </Text_12_400_B3B3B3>
          </div>
          <button
            onClick={fetchAgentDetails}
            className="px-4 py-1 bg-[#FFA500] hover:bg-[#FF8C00] text-white rounded text-xs transition-colors"
          >
            Retry
          </button>
        </div>
      )}
      {/* Agent Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2 pt-[1.5rem]">
          <Text_26_600_FFFFFF className="text-[#EEE]">
            {agentData?.name}
          </Text_26_600_FFFFFF>
          <ProjectTags color={endpointStatusMapping[capitalize(agentData?.status)]} name={capitalize(agentData?.status)} />
          <div className="ml-auto">
            <PrimaryButton
              permission={hasPermission(PermissionEnum.ModelManage)}
              onClick={() => {
                openDrawer("use-agent", { endpoint: agentData });
              }}
            >
              Use this agent
            </PrimaryButton>
          </div>
        </div>
        <Text_12_400_B3B3B3 className="max-w-[850px] mb-3">
          {agentData?.description}
        </Text_12_400_B3B3B3>
        <div className="flex items-center gap-2 flex-wrap">
          {agentData?.tags?.map((tag: any, index: number) => (
            <Tags
              textClass="text-[.75rem]"
              key={index}
              name={tag.name}
              color={tag.color}
            />
          ))}
        </div>
      </div>

      {/* Cost Metrics */}
      <Row gutter={[16, 16]} className="mb-6 ">
        <Col span={8}>
          <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6 flex flex-col justify-between h-full items-start min-h-[11.375rem]">
            <div className="relative w-fit">
              <Text_15_600_EEEEEE className="leading-[1.5rem]">P 95 Cost / Request</Text_15_600_EEEEEE>
              <div className="absolute h-[3px] w-[1.625rem] bg-[#965CDE]"></div>
            </div>
            {costMetricsLoading ? (
              <Spin size="small" />
            ) : costMetricsError ? (
              <Text_12_400_B3B3B3>{costMetricsError}</Text_12_400_B3B3B3>
            ) : (
              <Text_40_400_EEEEEE>{costMetrics?.p95 ?? "--"}</Text_40_400_EEEEEE>
            )}
          </div>
        </Col>
        <Col span={8}>
          <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6 flex flex-col justify-between h-full items-start min-h-[11.375rem]">
            <div className="relative w-fit">
              <Text_15_600_EEEEEE className="leading-[1.5rem]">Max Cost / Request</Text_15_600_EEEEEE>
              <div className="absolute h-[3px] w-[1.625rem] bg-[#965CDE]"></div>
            </div>
            {costMetricsLoading ? (
              <Spin size="small" />
            ) : costMetricsError ? (
              <Text_12_400_B3B3B3>{costMetricsError}</Text_12_400_B3B3B3>
            ) : (
              <Text_40_400_EEEEEE>{costMetrics?.max ?? "--"}</Text_40_400_EEEEEE>
            )}
          </div>
        </Col>
        <Col span={8}>
          <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6 flex flex-col justify-between h-full items-start min-h-[11.375rem]">
            <div className="relative w-fit">
              <Text_15_600_EEEEEE className="leading-[1.5rem]">Min Cost / Request</Text_15_600_EEEEEE>
              <div className="absolute h-[3px] w-[1.625rem] bg-[#965CDE]"></div>
            </div>
            {costMetricsLoading ? (
              <Spin size="small" />
            ) : costMetricsError ? (
              <Text_12_400_B3B3B3>{costMetricsError}</Text_12_400_B3B3B3>
            ) : (
              <Text_40_400_EEEEEE>{costMetrics?.min ?? "--"}</Text_40_400_EEEEEE>
            )}
          </div>
        </Col>
      </Row>

      {/* Charts Grid */}
      <Row gutter={[16, 16]}>
        {/* Calls Chart - Now using ECharts with API data */}
        <Col span={24}>
          {promptId && typeof promptId === "string" ? (
            <CallsChart promptId={promptId} />
          ) : (
            <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6 h-[200px] flex items-center justify-center">
              <Text_12_400_B3B3B3>No prompt ID available</Text_12_400_B3B3B3>
            </div>
          )}
        </Col>

        {/* Users Chart - Now using ECharts with API data */}
        <Col span={12}>
          {promptId && typeof promptId === "string" ? (
            <UsersChart promptId={promptId} />
          ) : (
            <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6 h-[200px] flex items-center justify-center">
              <Text_12_400_B3B3B3>No prompt ID available</Text_12_400_B3B3B3>
            </div>
          )}
        </Col>

        {/* Token Usage Chart - Now using ECharts with API data */}
        <Col span={12}>
          {promptId && typeof promptId === "string" ? (
            <TokenUsageChart promptId={promptId} />
          ) : (
            <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6 h-[200px] flex items-center justify-center">
              <Text_12_400_B3B3B3>No prompt ID available</Text_12_400_B3B3B3>
            </div>
          )}
        </Col>

        {/* Request Count by API Key - Bar chart grouped by API key */}
        <Col span={12}>
          {promptId && typeof promptId === "string" ? (
            <RequestCountByApiKeyChart promptId={promptId} />
          ) : (
            <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6 h-[200px] flex items-center justify-center">
              <Text_12_400_B3B3B3>No prompt ID available</Text_12_400_B3B3B3>
            </div>
          )}
        </Col>

        {/* Error vs Successful Requests - Now using ECharts with API data */}
        <Col span={12}>
          {promptId && typeof promptId === "string" ? (
            <ErrorSuccessChart promptId={promptId} />
          ) : (
            <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6 h-[200px] flex items-center justify-center">
              <Text_12_400_B3B3B3>No prompt ID available</Text_12_400_B3B3B3>
            </div>
          )}
        </Col>

        {/* E2E Latency vs Concurrent Requests */}
        <Col span={12}>
          {promptId && typeof promptId === "string" ? (
            <E2ELatencyChart promptId={promptId} />
          ) : (
            <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6 h-[200px] flex items-center justify-center">
              <Text_12_400_B3B3B3>No prompt ID available</Text_12_400_B3B3B3>
            </div>
          )}
        </Col>

        {/* TTFT vs Input Tokens */}
        <Col span={12}>
          {promptId && typeof promptId === "string" ? (
            <TTFTChart promptId={promptId} />
          ) : (
            <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6 h-[200px] flex items-center justify-center">
              <Text_12_400_B3B3B3>No prompt ID available</Text_12_400_B3B3B3>
            </div>
          )}
        </Col>

        {/* Average Throughput/User by Concurrency */}
        <Col span={12}>
          {promptId && typeof promptId === "string" ? (
            <ThroughputChart promptId={promptId} />
          ) : (
            <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6 h-[200px] flex items-center justify-center">
              <Text_12_400_B3B3B3>No prompt ID available</Text_12_400_B3B3B3>
            </div>
          )}
        </Col>
      </Row>
    </div>
  );
};

export default OverviewTab;

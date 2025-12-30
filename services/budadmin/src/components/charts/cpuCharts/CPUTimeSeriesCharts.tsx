"use client";
import React, { useEffect, useRef } from "react";
import * as echarts from "echarts";
import { Flex } from "antd";
import {
  Text_12_400_757575,
  Text_14_600_EEEEEE,
} from "@/components/ui/text";
import { NodeCPUTimeSeriesData } from "src/hooks/useCPUMetrics";

// ============ Common Chart Container ============

interface ChartContainerProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  rightContent?: React.ReactNode;
}

const ChartContainer: React.FC<ChartContainerProps> = ({
  title,
  subtitle,
  children,
  rightContent,
}) => {
  return (
    <div className="bg-[#111113] rounded-lg border border-[#1F1F1F] overflow-hidden">
      <div className="p-4 border-b border-[#1F1F1F] flex justify-between items-center">
        <div>
          <Text_14_600_EEEEEE>{title}</Text_14_600_EEEEEE>
          {subtitle && (
            <Text_12_400_757575 className="mt-1">{subtitle}</Text_12_400_757575>
          )}
        </div>
        {rightContent}
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
};

// ============ CPU Usage Chart ============

interface CPUUsageChartProps {
  data: NodeCPUTimeSeriesData;
}

export const CPUUsageChart: React.FC<CPUUsageChartProps> = ({ data }) => {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartRef.current || !data.timestamps.length) return;

    const chart = echarts.init(chartRef.current);

    const option = {
      tooltip: {
        trigger: "axis",
        backgroundColor: "#1F1F1F",
        borderColor: "#333",
        textStyle: { color: "#EEE" },
        formatter: (params: any) => {
          const date = new Date(params[0].value[0]);
          const timeStr = date.toLocaleTimeString();
          return `<div style="font-size:12px;color:#757575;margin-bottom:4px">${timeStr}</div>
            <div style="display:flex;justify-content:space-between;gap:16px">
              <span style="color:${params[0].color}">CPU Usage</span>
              <span style="color:#EEE">${params[0].value[1].toFixed(1)}%</span>
            </div>`;
        },
      },
      grid: {
        left: "3%",
        right: "3%",
        top: "10%",
        bottom: "12%",
        containLabel: true,
      },
      xAxis: {
        type: "time",
        axisLine: { lineStyle: { color: "#333" } },
        axisLabel: {
          color: "#757575",
          fontSize: 10,
          formatter: (value: number) => {
            const date = new Date(value);
            return date.toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            });
          },
        },
        splitLine: { show: false },
      },
      yAxis: {
        type: "value",
        min: 0,
        max: 100,
        axisLine: { show: false },
        axisLabel: {
          color: "#757575",
          fontSize: 10,
          formatter: "{value}%",
        },
        splitLine: { lineStyle: { color: "#1F1F1F" } },
      },
      series: [
        {
          name: "CPU Usage",
          type: "line",
          smooth: true,
          symbol: "none",
          sampling: "lttb",
          itemStyle: { color: "#3F8EF7" },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: "rgba(63, 142, 247, 0.3)" },
              { offset: 1, color: "rgba(63, 142, 247, 0.05)" },
            ]),
          },
          data: data.timestamps.map((ts, i) => [
            ts,
            data.cpu_usage_percent[i] ?? 0,
          ]),
        },
      ],
    };

    chart.setOption(option);

    const handleResize = () => chart.resize();
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.dispose();
    };
  }, [data]);

  return (
    <ChartContainer
      title="CPU Usage"
      subtitle="CPU utilization percentage over time"
    >
      <div ref={chartRef} style={{ width: "100%", height: 220 }} />
    </ChartContainer>
  );
};

// ============ Load Averages Chart ============

interface LoadAveragesChartProps {
  data: NodeCPUTimeSeriesData;
}

export const LoadAveragesChart: React.FC<LoadAveragesChartProps> = ({
  data,
}) => {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartRef.current || !data.timestamps.length) return;

    const chart = echarts.init(chartRef.current);

    const option = {
      tooltip: {
        trigger: "axis",
        backgroundColor: "#1F1F1F",
        borderColor: "#333",
        textStyle: { color: "#EEE" },
        formatter: (params: any) => {
          const date = new Date(params[0].value[0]);
          const timeStr = date.toLocaleTimeString();
          let result = `<div style="font-size:12px;color:#757575;margin-bottom:4px">${timeStr}</div>`;
          params.forEach((p: any) => {
            result += `<div style="display:flex;justify-content:space-between;gap:16px">
              <span style="color:${p.color}">${p.seriesName}</span>
              <span style="color:#EEE">${p.value[1].toFixed(2)}</span>
            </div>`;
          });
          return result;
        },
      },
      legend: {
        data: ["Load 1m", "Load 5m", "Load 15m"],
        bottom: 0,
        textStyle: { color: "#757575", fontSize: 11 },
        itemWidth: 12,
        itemHeight: 3,
      },
      grid: {
        left: "3%",
        right: "3%",
        top: "10%",
        bottom: "18%",
        containLabel: true,
      },
      xAxis: {
        type: "time",
        axisLine: { lineStyle: { color: "#333" } },
        axisLabel: {
          color: "#757575",
          fontSize: 10,
          formatter: (value: number) => {
            const date = new Date(value);
            return date.toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            });
          },
        },
        splitLine: { show: false },
      },
      yAxis: {
        type: "value",
        min: 0,
        axisLine: { show: false },
        axisLabel: {
          color: "#757575",
          fontSize: 10,
        },
        splitLine: { lineStyle: { color: "#1F1F1F" } },
      },
      series: [
        {
          name: "Load 1m",
          type: "line",
          smooth: true,
          symbol: "none",
          sampling: "lttb",
          itemStyle: { color: "#965CDE" },
          data: data.timestamps.map((ts, i) => [ts, data.load_1[i] ?? 0]),
        },
        {
          name: "Load 5m",
          type: "line",
          smooth: true,
          symbol: "none",
          sampling: "lttb",
          itemStyle: { color: "#3F8EF7" },
          data: data.timestamps.map((ts, i) => [ts, data.load_5[i] ?? 0]),
        },
        {
          name: "Load 15m",
          type: "line",
          smooth: true,
          symbol: "none",
          sampling: "lttb",
          itemStyle: { color: "#479D5F" },
          data: data.timestamps.map((ts, i) => [ts, data.load_15[i] ?? 0]),
        },
      ],
    };

    chart.setOption(option);

    const handleResize = () => chart.resize();
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.dispose();
    };
  }, [data]);

  return (
    <ChartContainer
      title="Load Averages"
      subtitle="System load over 1, 5, and 15 minutes"
    >
      <div ref={chartRef} style={{ width: "100%", height: 220 }} />
    </ChartContainer>
  );
};

// ============ Time Range Selector ============

interface TimeRangeSelectorProps {
  value: number;
  onChange: (hours: number) => void;
}

export const CPUTimeRangeSelector: React.FC<TimeRangeSelectorProps> = ({
  value,
  onChange,
}) => {
  const options = [
    { value: 1, label: "1H" },
    { value: 6, label: "6H" },
    { value: 24, label: "24H" },
    { value: 168, label: "7D" },
  ];

  return (
    <Flex gap={4}>
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={`px-3 py-1 rounded text-xs transition-colors ${
            value === opt.value
              ? "bg-[#3F8EF7] text-white"
              : "bg-[#1F1F1F] text-[#757575] hover:bg-[#2A2A2A] hover:text-[#EEEEEE]"
          }`}
        >
          {opt.label}
        </button>
      ))}
    </Flex>
  );
};

// ============ Main Charts Section Component ============

interface CPUTimeSeriesChartsProps {
  data: NodeCPUTimeSeriesData | null;
  loading: boolean;
  onTimeRangeChange: (hours: number) => void;
  selectedTimeRange: number;
}

export const CPUTimeSeriesCharts: React.FC<CPUTimeSeriesChartsProps> = ({
  data,
  loading,
  onTimeRangeChange,
  selectedTimeRange,
}) => {
  if (!data || loading) {
    return (
      <div className="bg-[#111113] rounded-lg border border-[#1F1F1F] p-8 flex justify-center items-center">
        <Text_12_400_757575>
          {loading ? "Loading CPU metrics..." : "No CPU data available"}
        </Text_12_400_757575>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header with Time Range Selector */}
      <div className="flex justify-between items-center">
        <Text_14_600_EEEEEE>CPU Performance Trends</Text_14_600_EEEEEE>
        <CPUTimeRangeSelector
          value={selectedTimeRange}
          onChange={onTimeRangeChange}
        />
      </div>

      {/* CPU Usage + Load Averages Charts (side by side on large screens) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <CPUUsageChart data={data} />
        <LoadAveragesChart data={data} />
      </div>
    </div>
  );
};

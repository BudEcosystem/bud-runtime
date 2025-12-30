"use client";
import React, { useEffect, useRef, useState } from "react";
import * as echarts from "echarts";
import { Flex, Select } from "antd";
import {
  Text_12_400_757575,
  Text_14_400_EEEEEE,
  Text_14_600_EEEEEE,
} from "@/components/ui/text";
import { NodeGPUTimeSeriesData, getUtilizationColor } from "src/hooks/useGPUMetrics";

// ============ Common Chart Container ============

interface ChartContainerProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  rightContent?: React.ReactNode;
}

const ChartContainer: React.FC<ChartContainerProps> = ({ title, subtitle, children, rightContent }) => {
  return (
    <div className="bg-[#111113] rounded-lg border border-[#1F1F1F] overflow-hidden">
      <div className="p-4 border-b border-[#1F1F1F] flex justify-between items-center">
        <div>
          <Text_14_600_EEEEEE>{title}</Text_14_600_EEEEEE>
          {subtitle && <Text_12_400_757575 className="mt-1">{subtitle}</Text_12_400_757575>}
        </div>
        {rightContent}
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
};

// ============ GPU Utilization & Memory Chart ============

interface UtilizationMemoryChartProps {
  data: NodeGPUTimeSeriesData;
  gpuNames?: string[];
}

export const UtilizationMemoryChart: React.FC<UtilizationMemoryChartProps> = ({
  data,
  gpuNames,
}) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const [selectedGpu, setSelectedGpu] = useState(0);
  const gpuCount = data.gpu_utilization.length;

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
              <span style="color:#EEE">${p.value[1].toFixed(1)}%</span>
            </div>`;
          });
          return result;
        },
      },
      legend: {
        data: ["GPU Utilization", "Memory Utilization"],
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
            return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
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
          name: "GPU Utilization",
          type: "line",
          smooth: true,
          symbol: "none",
          sampling: "lttb",
          itemStyle: { color: "#965CDE" },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: "rgba(150, 92, 222, 0.3)" },
              { offset: 1, color: "rgba(150, 92, 222, 0.05)" },
            ]),
          },
          data: data.timestamps.map((ts, i) => [ts, data.gpu_utilization[selectedGpu]?.[i] ?? 0]),
        },
        {
          name: "Memory Utilization",
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
          data: data.timestamps.map((ts, i) => [ts, data.memory_utilization[selectedGpu]?.[i] ?? 0]),
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
  }, [data, selectedGpu]);

  return (
    <ChartContainer
      title="Utilization & Memory"
      subtitle="GPU compute and memory utilization over time"
      rightContent={
        gpuCount > 1 ? (
          <Select
            value={selectedGpu}
            onChange={setSelectedGpu}
            size="small"
            style={{ width: 100 }}
            options={Array.from({ length: gpuCount }, (_, i) => ({
              value: i,
              label: gpuNames?.[i] || `GPU ${i}`,
            }))}
            className="gpu-chart-select"
          />
        ) : undefined
      }
    >
      <div ref={chartRef} style={{ width: "100%", height: 220 }} />
    </ChartContainer>
  );
};

// ============ Temperature & Power Chart ============

interface TempPowerChartProps {
  data: NodeGPUTimeSeriesData;
  gpuNames?: string[];
}

export const TempPowerChart: React.FC<TempPowerChartProps> = ({
  data,
  gpuNames,
}) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const [selectedGpu, setSelectedGpu] = useState(0);
  const gpuCount = data.temperature.length;

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
            const unit = p.seriesName === "Temperature" ? "°C" : "W";
            result += `<div style="display:flex;justify-content:space-between;gap:16px">
              <span style="color:${p.color}">${p.seriesName}</span>
              <span style="color:#EEE">${p.value[1].toFixed(1)}${unit}</span>
            </div>`;
          });
          return result;
        },
      },
      legend: {
        data: ["Temperature", "Power"],
        bottom: 0,
        textStyle: { color: "#757575", fontSize: 11 },
        itemWidth: 12,
        itemHeight: 3,
      },
      grid: {
        left: "3%",
        right: "4%",
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
            return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
          },
        },
        splitLine: { show: false },
      },
      yAxis: [
        {
          type: "value",
          name: "°C",
          nameTextStyle: { color: "#757575", fontSize: 10 },
          min: 0,
          max: 100,
          axisLine: { show: false },
          axisLabel: { color: "#FA8C16", fontSize: 10 },
          splitLine: { lineStyle: { color: "#1F1F1F" } },
        },
        {
          type: "value",
          name: "W",
          nameTextStyle: { color: "#757575", fontSize: 10 },
          min: 0,
          axisLine: { show: false },
          axisLabel: { color: "#D1B854", fontSize: 10 },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: "Temperature",
          type: "line",
          smooth: true,
          symbol: "none",
          sampling: "lttb",
          yAxisIndex: 0,
          itemStyle: { color: "#FA8C16" },
          data: data.timestamps.map((ts, i) => [ts, data.temperature[selectedGpu]?.[i] ?? 0]),
        },
        {
          name: "Power",
          type: "line",
          smooth: true,
          symbol: "none",
          sampling: "lttb",
          yAxisIndex: 1,
          itemStyle: { color: "#D1B854" },
          data: data.timestamps.map((ts, i) => [ts, data.power[selectedGpu]?.[i] ?? 0]),
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
  }, [data, selectedGpu]);

  return (
    <ChartContainer
      title="Temperature & Power"
      subtitle="Thermal and power consumption metrics"
      rightContent={
        gpuCount > 1 ? (
          <Select
            value={selectedGpu}
            onChange={setSelectedGpu}
            size="small"
            style={{ width: 100 }}
            options={Array.from({ length: gpuCount }, (_, i) => ({
              value: i,
              label: gpuNames?.[i] || `GPU ${i}`,
            }))}
            className="gpu-chart-select"
          />
        ) : undefined
      }
    >
      <div ref={chartRef} style={{ width: "100%", height: 220 }} />
    </ChartContainer>
  );
};

// ============ Per-GPU Comparison Chart ============

interface GPUComparisonChartProps {
  data: NodeGPUTimeSeriesData;
  metric: "utilization" | "memory" | "temperature" | "power";
  gpuNames?: string[];
}

const metricConfig = {
  utilization: { title: "GPU Utilization Comparison", unit: "%", max: 100 },
  memory: { title: "Memory Utilization Comparison", unit: "%", max: 100 },
  temperature: { title: "Temperature Comparison", unit: "°C", max: 100 },
  power: { title: "Power Consumption Comparison", unit: "W", max: undefined },
};

const gpuColors = ["#965CDE", "#3F8EF7", "#479D5F", "#FA8C16", "#EC7575", "#D1B854"];

export const GPUComparisonChart: React.FC<GPUComparisonChartProps> = ({
  data,
  metric,
  gpuNames,
}) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const [selectedMetric, setSelectedMetric] = useState(metric);
  const config = metricConfig[selectedMetric];

  const getMetricData = (gpuIndex: number) => {
    switch (selectedMetric) {
      case "utilization":
        return data.gpu_utilization[gpuIndex] || [];
      case "memory":
        return data.memory_utilization[gpuIndex] || [];
      case "temperature":
        return data.temperature[gpuIndex] || [];
      case "power":
        return data.power[gpuIndex] || [];
      default:
        return [];
    }
  };

  useEffect(() => {
    if (!chartRef.current || !data.timestamps.length) return;

    const chart = echarts.init(chartRef.current);
    const gpuCount = data.gpu_utilization.length;

    const series = Array.from({ length: gpuCount }, (_, i) => ({
      name: gpuNames?.[i] || `GPU ${i}`,
      type: "line",
      smooth: true,
      symbol: "none",
      sampling: "lttb",
      itemStyle: { color: gpuColors[i % gpuColors.length] },
      data: data.timestamps.map((ts, j) => [ts, getMetricData(i)[j] ?? 0]),
    }));

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
              <span style="color:#EEE">${p.value[1].toFixed(1)}${config.unit}</span>
            </div>`;
          });
          return result;
        },
      },
      legend: {
        data: Array.from({ length: gpuCount }, (_, i) => gpuNames?.[i] || `GPU ${i}`),
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
            return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
          },
        },
        splitLine: { show: false },
      },
      yAxis: {
        type: "value",
        min: 0,
        max: config.max,
        axisLine: { show: false },
        axisLabel: {
          color: "#757575",
          fontSize: 10,
          formatter: `{value}${config.unit}`,
        },
        splitLine: { lineStyle: { color: "#1F1F1F" } },
      },
      series,
    };

    chart.setOption(option);

    const handleResize = () => chart.resize();
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.dispose();
    };
  }, [data, selectedMetric, gpuNames]);

  return (
    <ChartContainer
      title="Per-GPU Comparison"
      subtitle={config.title}
      rightContent={
        <Select
          value={selectedMetric}
          onChange={setSelectedMetric}
          size="small"
          style={{ width: 140 }}
          options={[
            { value: "utilization", label: "GPU Utilization" },
            { value: "memory", label: "Memory Usage" },
            { value: "temperature", label: "Temperature" },
            { value: "power", label: "Power" },
          ]}
          className="gpu-chart-select"
        />
      }
    >
      <div ref={chartRef} style={{ width: "100%", height: 240 }} />
    </ChartContainer>
  );
};

// ============ Slice Activity Timeline ============

interface SliceActivityChartProps {
  data: NodeGPUTimeSeriesData;
}

const sliceColors = [
  "#965CDE",
  "#3F8EF7",
  "#479D5F",
  "#FA8C16",
  "#EC7575",
  "#D1B854",
  "#8B5CF6",
  "#06B6D4",
];

export const SliceActivityChart: React.FC<SliceActivityChartProps> = ({ data }) => {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartRef.current || !data.timestamps.length || !data.slice_activity.length) return;

    const chart = echarts.init(chartRef.current);

    const series = data.slice_activity.map((slice, i) => ({
      name: slice.slice_name,
      type: "line",
      stack: "Total",
      smooth: true,
      symbol: "none",
      sampling: "lttb",
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: sliceColors[i % sliceColors.length] },
          { offset: 1, color: sliceColors[i % sliceColors.length] + "33" },
        ]),
      },
      emphasis: { focus: "series" },
      itemStyle: { color: sliceColors[i % sliceColors.length] },
      data: data.timestamps.map((ts, j) => [ts, slice.data[j] ?? 0]),
    }));

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
              <span style="color:#EEE">${p.value[1].toFixed(1)}%</span>
            </div>`;
          });
          return result;
        },
      },
      legend: {
        data: data.slice_activity.map((s) => s.slice_name),
        bottom: 0,
        textStyle: { color: "#757575", fontSize: 11 },
        itemWidth: 12,
        itemHeight: 3,
        type: "scroll",
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
        boundaryGap: false,
        axisLine: { lineStyle: { color: "#333" } },
        axisLabel: {
          color: "#757575",
          fontSize: 10,
          formatter: (value: number) => {
            const date = new Date(value);
            return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
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
          formatter: "{value}%",
        },
        splitLine: { lineStyle: { color: "#1F1F1F" } },
      },
      series,
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
      title="Slice Activity Timeline"
      subtitle="GPU utilization by workload (stacked)"
    >
      <div ref={chartRef} style={{ width: "100%", height: 260 }} />
    </ChartContainer>
  );
};

// ============ Time Range Selector ============

interface TimeRangeSelectorProps {
  value: number;
  onChange: (hours: number) => void;
}

export const TimeRangeSelector: React.FC<TimeRangeSelectorProps> = ({ value, onChange }) => {
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
              ? "bg-[#965CDE] text-white"
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

interface GPUTimeSeriesChartsProps {
  data: NodeGPUTimeSeriesData | null;
  loading: boolean;
  gpuNames?: string[];
  onTimeRangeChange: (hours: number) => void;
  selectedTimeRange: number;
}

export const GPUTimeSeriesCharts: React.FC<GPUTimeSeriesChartsProps> = ({
  data,
  loading,
  gpuNames,
  onTimeRangeChange,
  selectedTimeRange,
}) => {
  if (!data || loading) {
    return (
      <div className="bg-[#111113] rounded-lg border border-[#1F1F1F] p-8 flex justify-center items-center">
        <Text_12_400_757575>
          {loading ? "Loading timeseries data..." : "No timeseries data available"}
        </Text_12_400_757575>
      </div>
    );
  }

  const gpuCount = data.gpu_utilization.length;

  return (
    <div className="space-y-4">
      {/* Header with Time Range Selector */}
      <div className="flex justify-between items-center">
        <Text_14_600_EEEEEE>GPU Performance Trends</Text_14_600_EEEEEE>
        <TimeRangeSelector value={selectedTimeRange} onChange={onTimeRangeChange} />
      </div>

      {/* Utilization & Memory + Temperature & Power Charts (side by side) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <UtilizationMemoryChart data={data} gpuNames={gpuNames} />
        <TempPowerChart data={data} gpuNames={gpuNames} />
      </div>

      {/* Comparison Chart (only if multiple GPUs) */}
      {gpuCount > 1 && (
        <GPUComparisonChart
          data={data}
          metric="utilization"
          gpuNames={gpuNames}
        />
      )}

      {/* Slice Activity Timeline (if slices exist) */}
      {data.slice_activity.length > 0 && (
        <SliceActivityChart data={data} />
      )}
    </div>
  );
};

"use client";
import React, { useEffect, useRef, useState } from "react";
import { Flex, Table, Tag, Tooltip, Progress, Spin } from "antd";
import * as echarts from "echarts";
import { useRouter } from "next/router";
import {
  Text_10_400_EEEEEE,
  Text_12_400_757575,
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_13_400_tag,
  Text_14_400_757575,
  Text_14_400_EEEEEE,
  Text_14_600_EEEEEE,
  Text_16_400_EEEEEE,
  Text_20_400_EEEEEE,
} from "@/components/ui/text";
import {
  useGPUMetrics,
  HAMISlice,
  GPUClusterSummary,
  NodeGPUSummary,
  getSliceStatusColor,
  getUtilizationColor,
} from "src/hooks/useGPUMetrics";
import { useLoaderOnLoding } from "src/hooks/useLoaderOnLoading";
import NoDataFount from "@/components/ui/noDataFount";
import { Cpu, Thermometer, Zap, HardDrive, Layers, Activity, Server } from "lucide-react";

// ============ Stat Card Component ============

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ReactNode;
  color?: string;
  trend?: number;
}

const StatCard: React.FC<StatCardProps> = ({ title, value, subtitle, icon, color = "#965CDE" }) => {
  return (
    <div className="bg-[#111113] rounded-lg p-4 border border-[#1F1F1F] flex flex-col gap-2 min-w-[180px]">
      <div className="flex items-center justify-between">
        <Text_12_400_757575>{title}</Text_12_400_757575>
        <div style={{ color }} className="opacity-70">
          {icon}
        </div>
      </div>
      <div className="flex items-baseline gap-2">
        <Text_20_400_EEEEEE style={{ color }}>{value}</Text_20_400_EEEEEE>
        {subtitle && <Text_12_400_757575>{subtitle}</Text_12_400_757575>}
      </div>
    </div>
  );
};

// ============ GPU Summary Section ============

interface GPUSummaryProps {
  summary: GPUClusterSummary;
}

const GPUSummary: React.FC<GPUSummaryProps> = ({ summary }) => {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
      <StatCard
        title="Total GPUs"
        value={summary.total_gpus}
        icon={<Cpu size={18} />}
        color="#965CDE"
      />
      <StatCard
        title="Memory Used"
        value={`${summary.memory_utilization_percent.toFixed(1)}%`}
        subtitle={`${summary.allocated_memory_gb.toFixed(1)} / ${summary.total_memory_gb.toFixed(1)} GB`}
        icon={<HardDrive size={18} />}
        color={getUtilizationColor(summary.memory_utilization_percent)}
      />
      <StatCard
        title="Active Slices"
        value={`${summary.active_slices} / ${summary.total_slices}`}
        icon={<Layers size={18} />}
        color="#3F8EF7"
      />
      <StatCard
        title="GPU Utilization"
        value={`${summary.avg_gpu_utilization_percent.toFixed(1)}%`}
        icon={<Activity size={18} />}
        color={getUtilizationColor(summary.avg_gpu_utilization_percent)}
      />
      {summary.avg_temperature_celsius && (
        <StatCard
          title="Temperature"
          value={`${summary.avg_temperature_celsius}°C`}
          icon={<Thermometer size={18} />}
          color={summary.avg_temperature_celsius > 80 ? "#EC7575" : summary.avg_temperature_celsius > 60 ? "#FA8C16" : "#479D5F"}
        />
      )}
      {summary.total_power_watts && (
        <StatCard
          title="Power Draw"
          value={`${summary.total_power_watts.toFixed(1)}W`}
          icon={<Zap size={18} />}
          color="#D1B854"
        />
      )}
    </div>
  );
};

// ============ HAMI Slice Table ============

interface HAMISliceTableProps {
  slices: HAMISlice[];
}

const HAMISliceTable: React.FC<HAMISliceTableProps> = ({ slices }) => {
  const columns = [
    {
      title: "Pod / Container",
      key: "pod",
      width: 240,
      render: (_: any, record: HAMISlice) => (
        <div>
          <Tooltip title={record.pod_name}>
            <Text_14_400_EEEEEE className="block truncate max-w-[220px]">
              {record.pod_name.length > 30 ? `${record.pod_name.substring(0, 30)}...` : record.pod_name}
            </Text_14_400_EEEEEE>
          </Tooltip>
          <Text_12_400_757575>{record.container_name}</Text_12_400_757575>
        </div>
      ),
    },
    {
      title: "Namespace",
      dataIndex: "pod_namespace",
      key: "namespace",
      width: 160,
      render: (ns: string) => (
        <Tooltip title={ns}>
          <Text_12_400_EEEEEE className="truncate max-w-[140px] block">
            {ns.length > 18 ? `${ns.substring(0, 18)}...` : ns}
          </Text_12_400_EEEEEE>
        </Tooltip>
      ),
    },
    {
      title: "Node",
      dataIndex: "node_name",
      key: "node",
      width: 120,
      render: (nodeName: string) => (
        <div className="flex items-center gap-1.5">
          <Server size={12} className="text-[#757575]" />
          <Text_12_400_EEEEEE>{nodeName}</Text_12_400_EEEEEE>
        </div>
      ),
    },
    {
      title: "GPU",
      key: "gpu",
      width: 70,
      render: (_: any, record: HAMISlice) => (
        <Tag color="#1F1F1F" className="m-0 border-[#333]">
          <Text_12_400_EEEEEE>GPU {record.device_index}</Text_12_400_EEEEEE>
        </Tag>
      ),
    },
    {
      title: "Memory Allocation",
      key: "memory",
      width: 180,
      render: (_: any, record: HAMISlice) => (
        <div className="space-y-1">
          <div className="flex justify-between">
            <Text_12_400_757575>
              {record.memory_used_gb.toFixed(1)} / {record.memory_limit_gb.toFixed(1)} GB
            </Text_12_400_757575>
            <Text_12_400_EEEEEE style={{ color: getUtilizationColor(record.memory_utilization_percent) }}>
              {record.memory_utilization_percent.toFixed(1)}%
            </Text_12_400_EEEEEE>
          </div>
          <Progress
            percent={record.memory_utilization_percent}
            showInfo={false}
            strokeColor={getUtilizationColor(record.memory_utilization_percent)}
            trailColor="#1F1F1F"
            size="small"
          />
        </div>
      ),
    },
    {
      title: "GPU Util",
      key: "gpu_util",
      width: 80,
      render: (_: any, record: HAMISlice) => (
        <Text_14_400_EEEEEE style={{ color: getUtilizationColor(record.gpu_utilization_percent) }}>
          {record.gpu_utilization_percent.toFixed(1)}%
        </Text_14_400_EEEEEE>
      ),
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      width: 90,
      render: (status: string) => (
        <Flex
          style={{ backgroundColor: status === "running" ? "#122F1140" : status === "pending" ? "#FA8C1633" : "#861A1A33" }}
          className="rounded-md items-center justify-center px-2 py-1 w-fit"
        >
          <Text_13_400_tag style={{ color: getSliceStatusColor(status) }}>
            {status.charAt(0).toUpperCase() + status.slice(1)}
          </Text_13_400_tag>
        </Flex>
      ),
    },
  ];

  return (
    <div className="bg-[#111113] rounded-lg border border-[#1F1F1F] overflow-hidden">
      <div className="p-4 border-b border-[#1F1F1F]">
        <Text_14_600_EEEEEE>GPU Slices</Text_14_600_EEEEEE>
        <Text_12_400_757575 className="mt-1">
          {slices.length} container{slices.length !== 1 ? "s" : ""} sharing GPU resources
        </Text_12_400_757575>
      </div>
      <Table
        dataSource={slices}
        columns={columns}
        rowKey={(record) => `${record.pod_namespace}-${record.pod_name}`}
        pagination={slices.length > 10 ? { pageSize: 10, showSizeChanger: false } : false}
        className="gpu-slice-table"
        size="small"
      />
    </div>
  );
};

// ============ Memory Allocation Chart ============

interface MemoryAllocationChartProps {
  slices: HAMISlice[];
  totalMemoryGB: number;
}

const MemoryAllocationChart: React.FC<MemoryAllocationChartProps> = ({ slices, totalMemoryGB }) => {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartRef.current || slices.length === 0) return;

    const chart = echarts.init(chartRef.current);

    const usedMemory = slices.reduce((sum, s) => sum + s.memory_limit_gb, 0);
    const freeMemory = Math.max(0, totalMemoryGB - usedMemory);

    const data = [
      ...slices.map((slice, index) => ({
        name: slice.pod_namespace.length > 15
          ? slice.pod_namespace.substring(0, 15) + "..."
          : slice.pod_namespace,
        value: slice.memory_limit_gb,
        itemStyle: {
          color: [
            "#965CDE", "#3F8EF7", "#479D5F", "#D1B854", "#FA8C16",
            "#EC7575", "#8B5CF6", "#06B6D4", "#F97316", "#84CC16"
          ][index % 10],
        },
      })),
      {
        name: "Available",
        value: freeMemory,
        itemStyle: { color: "#2A2A2A" },
      },
    ];

    const option = {
      tooltip: {
        trigger: "item",
        formatter: (params: any) => `${params.name}: ${params.value.toFixed(2)} GB (${params.percent.toFixed(1)}%)`,
        backgroundColor: "#1F1F1F",
        borderColor: "#333",
        textStyle: { color: "#EEEEEE" },
      },
      legend: {
        orient: "vertical",
        right: 10,
        top: "center",
        textStyle: { color: "#757575", fontSize: 11 },
        formatter: (name: string) => name.length > 18 ? name.substring(0, 18) + "..." : name,
      },
      series: [
        {
          type: "pie",
          radius: ["45%", "70%"],
          center: ["35%", "50%"],
          avoidLabelOverlap: true,
          itemStyle: {
            borderRadius: 4,
            borderColor: "#111113",
            borderWidth: 2,
          },
          label: { show: false },
          emphasis: {
            label: { show: true, fontSize: 14, fontWeight: "bold", color: "#EEEEEE" },
          },
          data,
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
  }, [slices, totalMemoryGB]);

  return (
    <div className="bg-[#111113] rounded-lg p-5 border border-[#1F1F1F]">
      <Text_14_600_EEEEEE>Memory Allocation by Namespace</Text_14_600_EEEEEE>
      <Text_12_400_757575 className="mt-1 mb-4">
        Distribution of GPU memory across workloads
      </Text_12_400_757575>
      <div ref={chartRef} style={{ width: "100%", height: 280 }} />
    </div>
  );
};

// ============ Main GPUMetrics Component ============

const GPUMetrics: React.FC = () => {
  const router = useRouter();
  const { clustersId } = router.query;
  const cluster_id = clustersId as string;

  const { metrics, loading, error, fetchGPUMetrics } = useGPUMetrics();
  const [refreshKey, setRefreshKey] = useState(0);

  useLoaderOnLoding(loading);

  useEffect(() => {
    if (router.isReady && cluster_id) {
      fetchGPUMetrics(cluster_id);
    }
  }, [router.isReady, cluster_id, refreshKey]);

  const handleRefresh = () => {
    setRefreshKey((prev) => prev + 1);
  };

  if (loading && !metrics) {
    return (
      <div className="flex justify-center items-center h-[400px]">
        <Spin size="large" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <NoDataFount classNames="h-[300px]" textMessage={`Error loading GPU metrics: ${error}`} />
      </div>
    );
  }

  if (!metrics || metrics.devices.length === 0) {
    return (
      <div className="p-6">
        <NoDataFount classNames="h-[300px]" textMessage="No GPU devices found in this cluster" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <Text_16_400_EEEEEE>GPU Metrics & HAMI Slices</Text_16_400_EEEEEE>
          <Text_12_400_757575 className="mt-1">
            Real-time GPU utilization and time-slicing allocation
          </Text_12_400_757575>
        </div>
        <button
          onClick={handleRefresh}
          className="px-4 py-2 bg-[#1F1F1F] hover:bg-[#2A2A2A] rounded-md text-sm text-[#EEEEEE] transition-colors"
        >
          Refresh
        </button>
      </div>

      {/* Summary Stats */}
      <GPUSummary summary={metrics.summary} />

      {/* Nodes Summary */}
      <div className="bg-[#111113] rounded-lg p-4 border border-[#1F1F1F]">
        <div className="flex justify-between items-center">
          <div>
            <Text_14_600_EEEEEE>GPU Nodes</Text_14_600_EEEEEE>
            <Text_12_400_757575 className="mt-1">
              {metrics.nodes.length} node{metrics.nodes.length !== 1 ? "s" : ""} with GPU hardware
            </Text_12_400_757575>
          </div>
          <Text_12_400_757575>
            Click on a node in the Nodes tab to view detailed GPU metrics
          </Text_12_400_757575>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mt-4">
          {metrics.nodes.map((node) => (
            <div key={node.node_name} className="bg-[#0a0a0a] rounded-lg p-3 border border-[#1F1F1F]">
              <div className="flex items-center gap-2 mb-2">
                <Server size={14} className="text-[#965CDE]" />
                <Text_14_400_EEEEEE>{node.node_name}</Text_14_400_EEEEEE>
              </div>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div>
                  <Text_12_400_757575>GPUs</Text_12_400_757575>
                  <Text_12_400_EEEEEE>{node.gpu_count}</Text_12_400_EEEEEE>
                </div>
                <div>
                  <Text_12_400_757575>Memory</Text_12_400_757575>
                  <Text_12_400_EEEEEE style={{ color: getUtilizationColor(node.memory_utilization_percent) }}>
                    {node.memory_utilization_percent.toFixed(0)}%
                  </Text_12_400_EEEEEE>
                </div>
                <div>
                  <Text_12_400_757575>Compute</Text_12_400_757575>
                  <Text_12_400_EEEEEE style={{ color: getUtilizationColor(node.avg_gpu_utilization_percent) }}>
                    {node.avg_gpu_utilization_percent.toFixed(0)}%
                  </Text_12_400_EEEEEE>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Memory Allocation Chart */}
      <MemoryAllocationChart slices={metrics.slices} totalMemoryGB={metrics.summary.total_memory_gb} />

      {/* HAMI Slices Table */}
      <HAMISliceTable slices={metrics.slices} />

      {/* Last Updated */}
      <div className="text-right">
        <Text_12_400_757575>
          Last updated: {new Date(metrics.timestamp).toLocaleString()}
        </Text_12_400_757575>
      </div>

      {/* Custom Styles */}
      <style jsx global>{`
        .gpu-slice-table .ant-table {
          background: transparent !important;
        }
        .gpu-slice-table .ant-table-thead > tr > th {
          background: #1A1A1A !important;
          border-bottom: 1px solid #1F1F1F !important;
          color: #757575 !important;
          font-weight: 500;
          font-size: 12px;
        }
        .gpu-slice-table .ant-table-tbody > tr > td {
          background: transparent !important;
          border-bottom: 1px solid #1F1F1F !important;
        }
        .gpu-slice-table .ant-table-tbody > tr:hover > td {
          background: #1A1A1A !important;
        }
        .gpu-slice-table .ant-pagination {
          margin: 16px !important;
        }
        .gpu-slice-table .ant-pagination-item {
          background: #1F1F1F !important;
          border-color: #333 !important;
        }
        .gpu-slice-table .ant-pagination-item a {
          color: #EEEEEE !important;
        }
        .gpu-slice-table .ant-pagination-item-active {
          border-color: #965CDE !important;
        }
      `}</style>
    </div>
  );
};

export default GPUMetrics;

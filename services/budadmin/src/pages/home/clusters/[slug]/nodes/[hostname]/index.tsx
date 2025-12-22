"use client";
import React, { useEffect, useRef, useState } from "react";
import { useRouter } from "next/router";
import { Flex, Table, Tag, Tooltip, Progress, Spin } from "antd";
import * as echarts from "echarts";
import { Server, Cpu, HardDrive, Activity, Thermometer, Zap } from "lucide-react";
import {
  Text_10_400_EEEEEE,
  Text_12_400_757575,
  Text_12_400_EEEEEE,
  Text_13_400_tag,
  Text_14_400_EEEEEE,
  Text_14_600_EEEEEE,
  Text_16_400_EEEEEE,
  Text_20_400_EEEEEE,
  Text_26_600_FFFFFF,
} from "@/components/ui/text";
import {
  useGPUMetrics,
  GPUDevice,
  HAMISlice,
  NodeGPUMetricsResponse,
  getSliceStatusColor,
  getUtilizationColor,
} from "src/hooks/useGPUMetrics";
import { GPUTimeSeriesCharts } from "./GPUTimeSeriesCharts";
import { Node, useCluster } from "src/hooks/useCluster";
import { useLoaderOnLoding } from "src/hooks/useLoaderOnLoading";
import NoDataFount from "@/components/ui/noDataFount";
import DashBoardLayout from "../../../../layout";
import { CustomBreadcrumb } from "@/components/ui/bud/card/DrawerBreadCrumbNavigation";
import BackButton from "@/components/ui/bud/drawer/BackButton";
import Tags from "src/flows/components/DrawerTags";

// ============ Stat Card Component ============

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ReactNode;
  color?: string;
}

const StatCard: React.FC<StatCardProps> = ({ title, value, subtitle, icon, color = "#965CDE" }) => {
  return (
    <div className="bg-[#111113] rounded-lg p-4 border border-[#1F1F1F] flex flex-col gap-2">
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

// ============ GPU Device Card ============

interface GPUDeviceCardProps {
  device: GPUDevice;
  showNodeName?: boolean;
}

const GPUDeviceCard: React.FC<GPUDeviceCardProps> = ({ device, showNodeName = false }) => {
  const memoryChartRef = useRef<HTMLDivElement>(null);
  const gpuChartRef = useRef<HTMLDivElement>(null);

  const createGaugeOption = (value: number, color: string) => ({
    series: [
      {
        type: "gauge",
        center: ["50%", "65%"],
        radius: "95%",
        startAngle: 200,
        endAngle: -20,
        min: 0,
        max: 100,
        splitNumber: 10,
        itemStyle: { color },
        progress: { show: true, width: 10, roundCap: true },
        pointer: { show: false },
        axisLine: { roundCap: true, lineStyle: { width: 10, color: [[1, "#1F1F1F"]] } },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        title: { show: false },
        detail: {
          valueAnimation: true,
          offsetCenter: [0, "15%"],
          fontSize: 18,
          fontWeight: "bold",
          color: "#EEEEEE",
          formatter: "{value}%",
        },
        data: [{ value: value.toFixed(1) }],
      },
    ],
  });

  useEffect(() => {
    if (!memoryChartRef.current) return;
    const chart = echarts.init(memoryChartRef.current);
    chart.setOption(createGaugeOption(device.memory_utilization_percent, getUtilizationColor(device.memory_utilization_percent)));
    const handleResize = () => chart.resize();
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      chart.dispose();
    };
  }, [device.memory_utilization_percent]);

  useEffect(() => {
    if (!gpuChartRef.current) return;
    const chart = echarts.init(gpuChartRef.current);
    // Use gpu_utilization_percent (actual DCGM utilization) instead of core_utilization_percent (always 0 in time-slicing mode)
    const utilization = device.gpu_utilization_percent ?? device.core_utilization_percent;
    chart.setOption(createGaugeOption(utilization, getUtilizationColor(utilization)));
    const handleResize = () => chart.resize();
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      chart.dispose();
    };
  }, [device.gpu_utilization_percent, device.core_utilization_percent]);

  return (
    <div className="bg-[#111113] rounded-lg p-5 border border-[#1F1F1F]">
      <div className="flex justify-between items-start mb-3">
        <div>
          <Text_16_400_EEEEEE>{device.device_type}</Text_16_400_EEEEEE>
          <Text_12_400_757575 className="mt-1">
            {showNodeName ? `${device.node_name} • ` : ""}GPU {device.device_index}
          </Text_12_400_757575>
        </div>
        {/* <Tag color="#965CDE" className="m-0">
          {device.hardware_mode}
        </Tag> */}
      </div>

      <div className="flex gap-4 mb-3">
        <div className="flex-1 text-center">
          <div ref={memoryChartRef} style={{ width: "100%", height: 120 }} />
          <Text_12_400_757575 className="block mt-[-8px]">Memory</Text_12_400_757575>
          <Text_10_400_EEEEEE className="text-[#757575]">
            {device.memory_allocated_gb.toFixed(1)} / {device.total_memory_gb.toFixed(1)} GB
          </Text_10_400_EEEEEE>
        </div>
        <div className="flex-1 text-center">
          <div ref={gpuChartRef} style={{ width: "100%", height: 120 }} />
          <Text_12_400_757575 className="block mt-[-8px]">GPU Compute</Text_12_400_757575>
          <Text_10_400_EEEEEE className="text-[#757575]">
            {device.shared_containers_count} container{device.shared_containers_count !== 1 ? "s" : ""}
          </Text_10_400_EEEEEE>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-3 border-t border-[#1F1F1F]">
        {device.temperature_celsius != null && (
          <div className="text-center">
            <Text_12_400_757575 className="block">Temp</Text_12_400_757575>
            <Text_12_400_EEEEEE style={{ color: device.temperature_celsius > 80 ? "#EC7575" : device.temperature_celsius > 60 ? "#FA8C16" : "#EEEEEE" }}>
              {device.temperature_celsius}°C
            </Text_12_400_EEEEEE>
          </div>
        )}
        {device.power_watts != null && (
          <div className="text-center">
            <Text_12_400_757575 className="block">Power</Text_12_400_757575>
            <Text_12_400_EEEEEE>{device.power_watts.toFixed(0)}W</Text_12_400_EEEEEE>
          </div>
        )}
        {device.sm_clock_mhz != null && (
          <div className="text-center">
            <Text_12_400_757575 className="block">SM Clock</Text_12_400_757575>
            <Text_12_400_EEEEEE>{device.sm_clock_mhz} MHz</Text_12_400_EEEEEE>
          </div>
        )}
        <div className="text-center">
          <Text_12_400_757575 className="block">UUID</Text_12_400_757575>
          <Tooltip title={device.device_uuid}>
            <Text_12_400_EEEEEE className="truncate max-w-[80px] inline-block">
              {device.device_uuid.substring(4, 12)}...
            </Text_12_400_EEEEEE>
          </Tooltip>
        </div>
      </div>
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
      width: 280,
      render: (_: any, record: HAMISlice) => (
        <div>
          <Tooltip title={record.pod_name}>
            <Text_14_400_EEEEEE className="block truncate max-w-[260px]">
              {record.pod_name.length > 35 ? `${record.pod_name.substring(0, 35)}...` : record.pod_name}
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
      width: 180,
      render: (ns: string) => (
        <Tooltip title={ns}>
          <Text_12_400_EEEEEE className="truncate max-w-[160px] block">
            {ns.length > 22 ? `${ns.substring(0, 22)}...` : ns}
          </Text_12_400_EEEEEE>
        </Tooltip>
      ),
    },
    {
      title: "GPU",
      key: "gpu",
      width: 80,
      render: (_: any, record: HAMISlice) => (
        <Tag color="#1F1F1F" className="m-0 border-[#333]">
          <Text_12_400_EEEEEE>GPU {record.device_index}</Text_12_400_EEEEEE>
        </Tag>
      ),
    },
    {
      title: "Memory Allocation",
      key: "memory",
      width: 200,
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
      width: 90,
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
      width: 100,
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

// ============ Main Node Detail Component ============

const NodeDetail: React.FC = () => {
  const router = useRouter();
  const { slug: clusterId, hostname } = router.query;
  const {
    nodeMetrics: gpuNodeMetrics,
    nodeTimeSeries,
    loading: gpuLoading,
    timeSeriesLoading,
    error,
    fetchNodeGPUMetrics,
    fetchNodeGPUTimeSeries,
  } = useGPUMetrics();
  const { getClusterNodeMetrics, selectedCluster, getClusterById } = useCluster();
  const [nodeMetrics, setNodeMetrics] = useState<Node | null>(null);
  const [nodeLoading, setNodeLoading] = useState(false);
  const [isMounted, setIsMounted] = useState(false);
  const [selectedTimeRange, setSelectedTimeRange] = useState(6); // Default 6 hours

  useEffect(() => {
    setIsMounted(true);
  }, []);

  // Only show loader when actually loading
  useLoaderOnLoding(gpuLoading || nodeLoading);

  // Fetch cluster data if not available
  useEffect(() => {
    if (router.isReady && clusterId && !selectedCluster) {
      getClusterById(clusterId as string);
    }
  }, [router.isReady, clusterId, selectedCluster]);

  // Fetch GPU metrics for this specific node
  useEffect(() => {
    if (router.isReady && clusterId && hostname) {
      fetchNodeGPUMetrics(clusterId as string, hostname as string);
    }
  }, [router.isReady, clusterId, hostname]);

  // Fetch GPU timeseries data
  useEffect(() => {
    if (router.isReady && clusterId && hostname) {
      fetchNodeGPUTimeSeries(clusterId as string, hostname as string, selectedTimeRange);
    }
  }, [router.isReady, clusterId, hostname, selectedTimeRange]);

  // Handler for time range changes
  const handleTimeRangeChange = (hours: number) => {
    setSelectedTimeRange(hours);
  };

  // Fetch node metrics from cluster
  useEffect(() => {
    if (router.isReady && clusterId && hostname) {
      setNodeLoading(true);
      getClusterNodeMetrics(clusterId as string).then((res) => {
        // Find the node by hostname
        const node = Object.values(res || {}).find(
          (n: any) => n.hostname === hostname
        ) as Node | undefined;
        setNodeMetrics(node || null);
        setNodeLoading(false);
      }).catch(() => {
        setNodeLoading(false);
      });
    }
  }, [router.isReady, clusterId, hostname]);

  // Use GPU metrics from the dedicated node endpoint
  const nodeDevices = gpuNodeMetrics?.devices || [];
  const nodeSlices = gpuNodeMetrics?.slices || [];

  // Calculate node GPU summary from the node-specific data
  const nodeSummary = gpuNodeMetrics?.summary ? {
    total_gpus: gpuNodeMetrics.summary.gpu_count,
    total_memory_gb: gpuNodeMetrics.summary.total_memory_gb,
    allocated_memory_gb: gpuNodeMetrics.summary.allocated_memory_gb,
    avg_utilization: gpuNodeMetrics.summary.avg_gpu_utilization_percent,
    total_power: nodeDevices.reduce((sum, d) => sum + (d.power_watts || 0), 0),
    avg_temp: nodeDevices.length > 0
      ? nodeDevices.reduce((sum, d) => sum + (d.temperature_celsius || 0), 0) / nodeDevices.length
      : 0,
  } : null;

  const goBack = () => {
    router.back();
  };

  const HeaderContent = () => {
    return (
      <div className="flex justify-between items-center">
        {isMounted && (
          <div className="flex justify-start items-center">
            <BackButton onClick={goBack} />
            <CustomBreadcrumb
              urls={[
                "/home/clusters",
                `/home/clusters/${clusterId}`,
                "",
              ]}
              data={[
                "Clusters",
                `${selectedCluster?.icon || ""} ${selectedCluster?.name || ""}`,
                `${hostname}`,
              ]}
            />
          </div>
        )}
      </div>
    );
  };

  const tagData = [
    { name: nodeMetrics?.status || "Unknown", color: nodeMetrics?.status === "Ready" ? "#479D5F" : "#EC7575" },
    ...(nodeMetrics?.gpu ? [{ name: "GPU", color: "#965CDE" }] : []),
    ...(nodeMetrics?.cpu ? [{ name: "CPU", color: "#D1B854" }] : []),
  ];

  // Show loading only while fetching and no data yet
  if ((gpuLoading || nodeLoading) && !nodeMetrics) {
    return (
      <DashBoardLayout>
        <div className="flex justify-center items-center h-[400px]">
          <Spin size="large" />
        </div>
      </DashBoardLayout>
    );
  }

  return (
    <DashBoardLayout>
      <div className="boardPageView">
        <div className="boardPageTop pt-0 !mb-[.4rem] px-[0]">
          {/* Breadcrumb Header */}
          <div className="px-[1.2rem] pt-[1.05rem] pb-[1.15rem] mb-[2.1rem] border-b-[1px] border-b-[#1F1F1F]">
            <HeaderContent />
          </div>

          {/* Page Title and Tags */}
          <div className="flex items-center gap-4 justify-between flex-row px-[3.5rem]">
            <div className="w-full">
              <div className="flex items-center gap-3">
                <Server size={24} className="text-[#965CDE]" />
                <Text_26_600_FFFFFF className="text-[#EEE]">
                  {hostname}
                </Text_26_600_FFFFFF>
              </div>
              <div className="flex items-center gap-2 mt-[1rem]">
                {tagData.map((tag, index) => (
                  <Tags key={index} name={tag.name} color={tag.color} />
                ))}
              </div>
              {nodeMetrics?.system_info?.os && nodeMetrics.system_info.os !== "N/A" && (
                <Text_12_400_757575 className="mt-2">
                  {nodeMetrics.system_info.os}
                  {nodeMetrics.system_info.kernel && nodeMetrics.system_info.kernel !== "N/A" && ` • ${nodeMetrics.system_info.kernel}`}
                  {nodeMetrics.system_info.architecture && nodeMetrics.system_info.architecture !== "N/A" && ` • ${nodeMetrics.system_info.architecture}`}
                </Text_12_400_757575>
              )}
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="px-[3.5rem] pb-6 space-y-6">
          {/* Node GPU Summary Stats */}
          {nodeSummary && nodeSummary.total_gpus > 0 && (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
              <StatCard
                title="GPUs"
                value={nodeSummary.total_gpus}
                icon={<Cpu size={18} />}
                color="#965CDE"
              />
              <StatCard
                title="Memory Used"
                value={`${((nodeSummary.allocated_memory_gb / nodeSummary.total_memory_gb) * 100).toFixed(1)}%`}
                subtitle={`${nodeSummary.allocated_memory_gb.toFixed(1)} / ${nodeSummary.total_memory_gb.toFixed(1)} GB`}
                icon={<HardDrive size={18} />}
                color={getUtilizationColor((nodeSummary.allocated_memory_gb / nodeSummary.total_memory_gb) * 100)}
              />
              <StatCard
                title="GPU Utilization"
                value={`${nodeSummary.avg_utilization.toFixed(1)}%`}
                icon={<Activity size={18} />}
                color={getUtilizationColor(nodeSummary.avg_utilization)}
              />
              <StatCard
                title="Active Slices"
                value={nodeSlices.filter(s => s.status === "running").length}
                subtitle={`of ${nodeSlices.length}`}
                icon={<Server size={18} />}
                color="#3F8EF7"
              />
              {nodeSummary.avg_temp > 0 && (
                <StatCard
                  title="Avg Temperature"
                  value={`${nodeSummary.avg_temp.toFixed(0)}°C`}
                  icon={<Thermometer size={18} />}
                  color={nodeSummary.avg_temp > 80 ? "#EC7575" : nodeSummary.avg_temp > 60 ? "#FA8C16" : "#479D5F"}
                />
              )}
              {nodeSummary.total_power > 0 && (
                <StatCard
                  title="Power Draw"
                  value={`${nodeSummary.total_power.toFixed(0)}W`}
                  icon={<Zap size={18} />}
                  color="#D1B854"
                />
              )}
            </div>
          )}

          {/* GPU Device Cards */}
          {nodeDevices.length > 0 ? (
            <>
              <div>
                <Text_16_400_EEEEEE className="mb-4">GPU Devices</Text_16_400_EEEEEE>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {nodeDevices.map((device) => (
                    <GPUDeviceCard key={device.device_uuid} device={device} />
                  ))}
                </div>
              </div>

              {/* GPU Timeseries Charts */}
              <GPUTimeSeriesCharts
                data={nodeTimeSeries}
                loading={timeSeriesLoading}
                gpuNames={nodeDevices.map((d) => `GPU ${d.device_index}`)}
                onTimeRangeChange={handleTimeRangeChange}
                selectedTimeRange={selectedTimeRange}
              />

              {/* HAMI Slices */}
              {nodeSlices.length > 0 && (
                <HAMISliceTable slices={nodeSlices} />
              )}
            </>
          ) : (
            <NoDataFount classNames="h-[200px]" textMessage="No GPU devices found on this node" />
          )}
        </div>
      </div>

      {/* Table Styles */}
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
        .gpu-chart-select .ant-select-selector {
          background: #1F1F1F !important;
          border-color: #333 !important;
          color: #EEEEEE !important;
        }
        .gpu-chart-select .ant-select-arrow {
          color: #757575 !important;
        }
        .gpu-chart-select .ant-select-selection-item {
          color: #EEEEEE !important;
        }
      `}</style>
    </DashBoardLayout>
  );
};

export default NodeDetail;

"use client";
import { useEffect, useState } from "react";
import { Image, Segmented } from "antd";

import {
  Text_13_400_757575,
  Text_18_400_EEEEEE,
  Text_19_600_EEEEEE,
  Text_26_400_EEEEEE,
} from "@/components/ui/text";

import {
  Cluster,
  ClusterFilter,
  ClusterMetrics,
  MetricType,
  useCluster,
} from "src/hooks/useCluster";
import GuageChart from "@/components/charts/GuageChart";
import BarChart from "@/components/charts/barChart";
import MultiSeriesLineChart from "@/components/charts/MultiSeriesLineChart";
import { formatStorageSize, getCategories, getChartData } from "@/lib/utils";
import { useRouter } from "next/router";
import ComingSoon from "@/components/ui/comingSoon";
import { useLoaderOnLoding } from "src/hooks/useLoaderOnLoading";
import { useGPUMetrics, getUtilizationColor } from "src/hooks/useGPUMetrics";
import { Cpu, HardDrive, Activity, Layers, Server, Rocket, Database, MemoryStick } from "lucide-react";

const segmentOptions = ["today", "7days", "month"];
const segmentOptionsMap = {
  today: "Today",
  "7days": "7 Days",
  month: "This Month",
};

type GaugeChartProps = {
  title?: string;
  description?: string;
  average: string;
  percentage: string;
  chartData?: any;
  metricType: MetricType;
  field: string;
  metrics?: ClusterMetrics | null;
  selectedSegment?: ClusterFilter;
};

type ChartUsageCardProps = {
  title: string;
  description: string;
  value: string | number;
  percentage: number;
  chartData: any;
  arrow?: boolean;
  metricType: MetricType;
};

interface GeneralProps {
  data: Cluster;
  isActive?: boolean;
}

const ChartUsageCard = ({
  data,
  onChange,
  comingSoon,
}: {
  data: ChartUsageCardProps;
  onChange: (value: ClusterMetrics, segment: ClusterFilter) => void;
  comingSoon?: boolean;
}) => {
  const [selectedSegment, setSelectedSegment] =
    useState<ClusterFilter>("today");
  const { clustersId } = useRouter().query;
  const { getClusterMetrics } = useCluster();

  useEffect(() => {
    if (clustersId) {
      getClusterMetrics(
        clustersId as string,
        selectedSegment,
        data?.metricType,
      ).then((res) => {
        onChange(res, selectedSegment);
      });
    }
  }, [selectedSegment, clustersId]);

  return (
    <div
      className={`cardBG w-[49.1%] h-[23.75rem] py-[2rem] pb-[.5rem] px-[1.5rem] border border-[#1F1F1F] rounded-md relative`}
    >
      {comingSoon && <ComingSoon />}
      <div className="flex justify-between align-center">
        <div>
          <Text_19_600_EEEEEE>{data?.title}</Text_19_600_EEEEEE>
        </div>
        {segmentOptions && (
          <Segmented
            options={segmentOptions?.map((item) => ({
              label: segmentOptionsMap[item],
              value: item,
            }))}
            onChange={(value) => {
              setSelectedSegment(value as ClusterFilter);
            }}
            className="antSegmented general rounded-md text-[#EEEEEE] font-[400] bg-[transparent] border border-[#4D4D4D] border-[.53px] p-[0] mt-[.05rem]"
          />
        )}
      </div>
      {data?.description && (
        <div className="mt-[.7rem]">
          <Text_13_400_757575>{data?.description}</Text_13_400_757575>
        </div>
      )}
      <div className="flex flex-col items-start mt-[1.7rem]">
        <Text_26_400_EEEEEE className="">{data?.value}</Text_26_400_EEEEEE>
        <div
          className="flex  rounded-md items-center px-[.45rem] mb-[.1rem] h-[1.35rem] mt-[0.35rem]"
          style={{
            backgroundColor: data?.percentage > 0 ? "#122F1140" : "#2D0D0D40",
            color: data?.percentage > 0 ? "#479D5F" : "#E36E4F",
          }}
        >
          <span className=" font-[400] text-[0.8125rem] leading-[100%]">{`Avg. ${data?.percentage}`}</span>
          {data?.arrow &&
            (data?.percentage > 0 ? (
              <Image
                preview={false}
                width={12}
                src="/images/dashboard/greenArrow.png"
                className="ml-[.2rem]"
                alt=""
              />
            ) : (
              <Image
                preview={false}
                width={12}
                src="/images/dashboard/redArrow.png"
                className="ml-[.2rem]"
                alt=""
              />
            ))}
        </div>
      </div>
      <div className="h-[11.25rem]">{data?.chartData}</div>
    </div>
  );
};

interface NetworkBandwidthUsageProps {
  metrics: ClusterMetrics | null;
  selectedSegment: ClusterFilter;
}

function NetworkBandwidthUsage({ metrics, selectedSegment }: NetworkBandwidthUsageProps) {
  return (
    <div
      className={`cardBG w-[49.1%] h-[23.75rem] py-[2rem] pb-[.5rem] px-[1.5rem] border border-[#1F1F1F] rounded-md relative`}
    >
      <div className="flex justify-between align-center">
        <div>
          <Text_19_600_EEEEEE>Network Bandwidth</Text_19_600_EEEEEE>
        </div>
      </div>
      <div className="mt-[.7rem]">
        <Text_13_400_757575>Inbound and outbound network traffic (Mbps)</Text_13_400_757575>
      </div>
      <div className="flex flex-col items-start mt-[1.7rem]">
        <Text_26_400_EEEEEE className="">{`${
          metrics?.cluster_summary?.network_bandwidth?.total_mbps?.toFixed(2) || 0
        } Mbps`}</Text_26_400_EEEEEE>
        <Text_13_400_757575 className="mt-[.3rem]">{`In: ${
          metrics?.cluster_summary?.network_in?.inbound_mbps?.toFixed(2) || 0
        } | Out: ${
          metrics?.cluster_summary?.network_out?.outbound_mbps?.toFixed(2) || 0
        }`}</Text_13_400_757575>
        <div
          className="flex  rounded-md items-center px-[.45rem] mb-[.1rem] h-[1.35rem] mt-[0.35rem]"
          style={{
            backgroundColor: "#122F1140",
            color: "#479D5F",
          }}
        >
          <span className=" font-[400] text-[0.8125rem] leading-[100%]">Avg. 0</span>
          <Image
            preview={false}
            width={12}
            src="/images/dashboard/greenArrow.png"
            className="ml-[.2rem]"
            alt=""
          />
        </div>
      </div>
      <div className="h-[11.25rem]">
        <MultiSeriesLineChart
          data={{
            categories: getCategories(
              selectedSegment,
              metrics?.cluster_summary?.network_in?.time_series,
            ),
            series: [
              {
                name: "Network In",
                data: getChartData(
                  selectedSegment,
                  metrics?.cluster_summary?.network_in?.time_series,
                ),
                color: "#3F8EF7", // Blue for inbound
              },
              {
                name: "Network Out",
                data: getChartData(
                  selectedSegment,
                  metrics?.cluster_summary?.network_out?.time_series,
                ),
                color: "#FFC442", // Yellow for outbound
              },
            ],
            label1: "",
            label2: "",
            yAxisUnit: " Mbps",
            yAxisAutoScale: true,
          }}
        />
      </div>
    </div>
  );
}

function PowerConsumption() {
  const [data, setData] = useState<ClusterMetrics>(null);
  const [selectedSegment, setSelectedSegment] =
    useState<ClusterFilter>("today");
  return (
    <ChartUsageCard
      onChange={(value, segment) => {
        setData(value);
        setSelectedSegment(segment);
      }}
      data={{
        title: "Power Consumption",
        description: "Power consumption per Node",
        value: "0 W",
        percentage: 0,
        chartData: (
          <BarChart
            data={{
              categories: []?.map((item) => item.name),
              data: []?.map((item) => item.power_consumption),
              label1: "W",
              label2: "Node",
            }}
          />
        ),
        arrow: false,
        metricType: MetricType.ALL,
      }}
    />
  );
}

const GuageCharts = ({
  title,
  description,
  average,
  percentage,
  metricType,
  field,
  metrics,
  selectedSegment,
}: GaugeChartProps) => {

  return (
    <div className=" w-[49.1%] cardSetTwo h-[23.75rem]  py-[2rem] px-[1.5rem] border border-[#1F1F1F] rounded-md bg-[#101010]">
      {/* <div className="cardBG w-[49.1%] cardSetTwo h-[385px]  py-[1.9rem] px-[1.65rem] border border-[#1F1F1F] rounded-md"> */}
      <div className="flex justify-between align-center">
        <Text_19_600_EEEEEE className="tracking-[.005rem]">
          {title}
        </Text_19_600_EEEEEE>
      </div>
      <div className="mt-[.7rem]">
        <Text_13_400_757575>{description}</Text_13_400_757575>
      </div>

      {/* <div className="h-[232px]"> */}
      <div className="h-[14.5rem]">
        <GuageChart
          data={{
            percentage: Number(
              metrics?.cluster_summary?.[field]?.[percentage]?.toFixed(2) ?? 0,
            ),
            average: Number(
              metrics?.cluster_summary?.[field]?.[average]?.toFixed(2) ?? 0,
            ),
          }}
        />
      </div>
    </div>
  );
};

// GPU Summary Card Component
interface GPUSummaryCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ReactNode;
  color?: string;
}

const GPUSummaryCard: React.FC<GPUSummaryCardProps> = ({ title, value, subtitle, icon, color = "#965CDE" }) => {
  return (
    <div className="bg-[#101010] rounded-lg p-4 border border-[#1F1F1F] flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <Text_13_400_757575>{title}</Text_13_400_757575>
        <div style={{ color }} className="opacity-70">
          {icon}
        </div>
      </div>
      <div className="flex items-baseline gap-2">
        <Text_18_400_EEEEEE style={{ color }}>{value}</Text_18_400_EEEEEE>
        {subtitle && <Text_13_400_757575>{subtitle}</Text_13_400_757575>}
      </div>
    </div>
  );
};

const ClusterGeneral: React.FC<GeneralProps> = ({
  data,
  isActive = false,
}: {
  data?: Cluster;
  isActive?: boolean;
}) => {
  const [isHydrated, setIsHydrated] = useState(false);
  const [selectedSegment, setSelectedSegment] =
    useState<ClusterFilter>("today");
  const router = useRouter();
  const { clustersId } = router.query;
  const [metrics, setMetrics] = useState<ClusterMetrics>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [chartRefreshKey, setChartRefreshKey] = useState<number>(0);

  const { getClusterMetrics } = useCluster();
  const { metrics: gpuMetrics, fetchGPUMetrics } = useGPUMetrics();
  useLoaderOnLoding(loading);

  useEffect(() => {
    if (router.isReady && clustersId) {
      setLoading(true);
      getClusterMetrics(clustersId as string, selectedSegment, MetricType.ALL)
        .then((res) => {
          setMetrics(res);
          setLoading(false);
        })
        .finally(() => {
          setLoading(false);
        });
    }
  }, [router.isReady, clustersId, selectedSegment]);

  // Fetch GPU metrics for clusters with GPU hardware
  useEffect(() => {
    if (router.isReady && clustersId && data?.hardware_type?.includes("GPU")) {
      fetchGPUMetrics(clustersId as string);
    }
  }, [router.isReady, clustersId, data?.hardware_type]);

  // Refresh charts when tab becomes active
  useEffect(() => {
    if (isActive && isHydrated) {
      // Trigger chart refresh by updating the key
      // This forces charts to remount and reinitialize with correct dimensions
      setChartRefreshKey((prev) => prev + 1);
    }
  }, [isActive, isHydrated]);
  const GuageChartCardData: GaugeChartProps[] = [
    data?.hardware_type?.includes("CPU") && {
      title: "CPU Utilization",
      description: "CPU Utilization within a period of time",
      average: "change_percent",
      percentage: "usage_percent",
      chartData: <div>Chart</div>, // Pass your chart data here,
      metricType: MetricType.CPU,
      field: "cpu",
    },
    data?.hardware_type?.includes("GPU") && {
      title: "GPU Utilization",
      description: "GPU  Utilization within a period of time",
      average: "change_percent",
      percentage: "usage_percent",
      chartData: <div>Chart</div>, // Pass your chart data here
      metricType: MetricType.GPU,
      field: "gpu",
    },
    data?.hardware_type?.includes("HPU") && {
      title: "HPU Utilization",
      description: "HPU Utilization within a period of time",
      average: "change_percent",
      percentage: "usage_percent",
      chartData: <div>Chart</div>, // Pass your chart data here
      metricType: MetricType.HPU,
      field: "hpu",
    },
    {
      title: "Memory Utilization",
      description: "Memory Utilization within a period of time",
      average: "change_percent",
      percentage: "usage_percent",
      chartData: <div>Chart</div>, // Pass your chart data here
      metricType: MetricType.MEMORY,
      field: "memory",
    },
    {
      title: "Storage Utilization",
      description: "Storage Utilization within a period of time",
      average: "change_percent",
      percentage: "usage_percent",
      chartData: <div>Chart</div>, // Pass your chart data here
      metricType: MetricType.DISK,
      field: "storage",
    },
    // {
    //   title: "Disk Utilization",
    //   description: "Disk Utilization within a period of time",
    //   average: "change_percent",
    //   percentage: "usage_percent",
    //   chartData: <div>Chart</div>, // Pass your chart data here
    //   metricType: MetricType.DISK,
    //   field: "storage",
    // },
  ]?.filter(Boolean) as GaugeChartProps[];
  useEffect(() => {
    setIsHydrated(true);
  }, []);
  return (
    <div className="relative pb-[3rem]">
      {/* Cluster Overview Cards - 4 cards in first row */}
      <div className="grid grid-cols-4 gap-4 mt-[.5rem]">
        <GPUSummaryCard
          title="Active Nodes"
          value={data?.available_nodes || 0}
          subtitle={`of ${data?.total_nodes || 0} total`}
          icon={<Server size={18} />}
          color="#479D5F"
        />
        <GPUSummaryCard
          title="Active Deployments"
          value={data?.running_endpoints_count || 0}
          subtitle={`of ${data?.total_endpoints_count || 0} total`}
          icon={<Rocket size={18} />}
          color="#479D5F"
        />
        <GPUSummaryCard
          title="Available Disk"
          value={formatStorageSize(metrics?.cluster_summary?.storage?.available_gib || 0, "GB")}
          subtitle={`of ${formatStorageSize(metrics?.cluster_summary?.storage?.total_gib || 0, "GB")} total`}
          icon={<Database size={18} />}
          color="#4077E6"
        />
        <GPUSummaryCard
          title="Available RAM"
          value={formatStorageSize(metrics?.cluster_summary?.memory?.available_gib || 0, "GB")}
          subtitle={`of ${formatStorageSize(metrics?.cluster_summary?.memory?.total_gib || 0, "GB")} total`}
          icon={<MemoryStick size={18} />}
          color="#4077E6"
        />
      </div>

      {/* GPU Overview Section - 4 cards in second row when GPU available */}
      {data?.hardware_type?.includes("GPU") && gpuMetrics?.summary && (
        <div className="grid grid-cols-4 gap-4 mt-4">
          <GPUSummaryCard
            title="Total GPUs"
            value={gpuMetrics.summary.total_gpus}
            icon={<Cpu size={18} />}
            color="#965CDE"
          />
          <GPUSummaryCard
            title="GPU Memory"
            value={`${gpuMetrics.summary.memory_utilization_percent.toFixed(1)}%`}
            subtitle={`${gpuMetrics.summary.allocated_memory_gb.toFixed(1)} / ${gpuMetrics.summary.total_memory_gb.toFixed(1)} GB`}
            icon={<HardDrive size={18} />}
            color={getUtilizationColor(gpuMetrics.summary.memory_utilization_percent)}
          />
          <GPUSummaryCard
            title="GPU Compute"
            value={`${gpuMetrics.summary.avg_gpu_utilization_percent.toFixed(1)}%`}
            subtitle="Avg utilization"
            icon={<Activity size={18} />}
            color={getUtilizationColor(gpuMetrics.summary.avg_gpu_utilization_percent)}
          />
          <GPUSummaryCard
            title="Active Slices"
            value={gpuMetrics.summary.active_slices}
            subtitle={`of ${gpuMetrics.summary.total_slices} total`}
            icon={<Layers size={18} />}
            color="#3F8EF7"
          />
        </div>
      )}

      {/* Metrics Section with Time Period Filter */}
      {isHydrated && (
        <div className="mt-[1.55rem]">
          <div className="flex justify-between items-center mb-[1.2rem]">
            <Text_19_600_EEEEEE>Performance Metrics</Text_19_600_EEEEEE>
            <Segmented
              options={segmentOptions?.map((item) => ({
                label: segmentOptionsMap[item],
                value: item,
              }))}
              value={selectedSegment}
              onChange={(value) => {
                setSelectedSegment(value as ClusterFilter);
              }}
              className="antSegmented general rounded-md text-[#EEEEEE] font-[400] bg-[transparent] border border-[#4D4D4D] border-[.53px] p-[0]"
            />
          </div>
          <div className="flex justify-between flex-wrap gap-x-[.8rem] gap-y-[1.4rem] ">
            {/* <PowerConsumption /> */}
            {/* <NetworkBandwidthUsage /> */}
          </div>
          <div className="flex justify-between flex-wrap gap-x-[.8rem] gap-y-[1.4rem] mt-[1.4rem]">
            {GuageChartCardData.map((item, index) => (
              <GuageCharts
                key={`${index}-${chartRefreshKey}`}
                {...item}
                metrics={metrics}
                selectedSegment={selectedSegment}
              />
            ))}
            <NetworkBandwidthUsage
              key={`network-${chartRefreshKey}`}
              metrics={metrics}
              selectedSegment={selectedSegment}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default ClusterGeneral;

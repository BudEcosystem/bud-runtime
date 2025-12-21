import { tempApiBaseUrl } from "@/components/environment";
import { useState } from "react";
import { AppRequest } from "src/pages/api/requests";
import { create } from "zustand";

// ============ Types ============

// Physical GPU device info
export interface GPUDevice {
  device_uuid: string;
  device_index: number;
  device_type: string;
  node_name: string;
  total_memory_gb: number;
  memory_allocated_gb: number;
  memory_utilization_percent: number;
  core_utilization_percent: number; // HAMI allocation (always 0 in time-slicing mode)
  cores_allocated_percent: number;
  shared_containers_count: number;
  hardware_mode: string; // "time-slicing" | "dedicated" | "mig"
  last_metrics_update: string;
  // DCGM metrics
  temperature_celsius?: number;
  power_watts?: number;
  sm_clock_mhz?: number;
  memory_clock_mhz?: number;
  pcie_tx_bytes?: number;
  pcie_rx_bytes?: number;
  gpu_utilization_percent?: number; // Actual GPU utilization from DCGM
}

// HAMI vGPU slice info (per container)
export interface HAMISlice {
  pod_name: string;
  pod_namespace: string;
  container_name: string;
  device_uuid: string;
  device_index: number;  // GPU index on the node
  node_name: string;
  // Memory allocation
  memory_limit_bytes: number;
  memory_limit_gb: number;
  memory_used_bytes: number;
  memory_used_gb: number;
  memory_utilization_percent: number;
  // Core allocation
  core_limit_percent: number;
  core_used_percent: number;
  // Activity
  gpu_utilization_percent: number;
  last_kernel_id?: number;
  // Status
  status: "running" | "pending" | "terminated" | "unknown";
}

// Node-level GPU summary for grouping
export interface NodeGPUSummary {
  node_name: string;
  gpu_count: number;
  total_memory_gb: number;
  allocated_memory_gb: number;
  memory_utilization_percent: number;
  avg_gpu_utilization_percent: number;
  active_slices: number;
  devices: GPUDevice[];
}

// Namespace quota usage
export interface NamespaceQuota {
  namespace: string;
  gpu_memory_used_mb: number;
  gpu_cores_used_percent: number;
}

// Summary metrics for the cluster
export interface GPUClusterSummary {
  total_gpus: number;
  total_memory_gb: number;
  allocated_memory_gb: number;
  available_memory_gb: number;
  memory_utilization_percent: number;
  avg_gpu_utilization_percent: number;
  total_slices: number;
  active_slices: number;
  avg_temperature_celsius?: number;
  total_power_watts?: number;
}

// Full GPU metrics response
export interface GPUMetricsResponse {
  cluster_id: string;
  timestamp: string;
  summary: GPUClusterSummary;
  nodes: NodeGPUSummary[];
  devices: GPUDevice[];
  slices: HAMISlice[];
  quotas: NamespaceQuota[];
}

// Time series data point
export interface GPUTimeSeriesPoint {
  timestamp: number;
  value: number;
}

export interface GPUTimeSeries {
  metric_name: string;
  device_uuid?: string;
  data: GPUTimeSeriesPoint[];
}

// ============ Utility Functions ============

export const groupDevicesByNode = (devices: GPUDevice[], slices: HAMISlice[]): NodeGPUSummary[] => {
  const nodeMap = new Map<string, GPUDevice[]>();

  // Group devices by node_name
  devices.forEach(device => {
    const existing = nodeMap.get(device.node_name) || [];
    existing.push(device);
    nodeMap.set(device.node_name, existing);
  });

  // Create NodeGPUSummary for each node
  const nodes: NodeGPUSummary[] = [];
  nodeMap.forEach((nodeDevices, nodeName) => {
    const totalMemory = nodeDevices.reduce((sum, d) => sum + d.total_memory_gb, 0);
    const allocatedMemory = nodeDevices.reduce((sum, d) => sum + d.memory_allocated_gb, 0);
    const nodeSlices = slices.filter(s => s.node_name === nodeName && s.status === "running");

    // Calculate avg GPU utilization: prefer DCGM device utils, fallback to slice utils
    const deviceUtils = nodeDevices
      .map(d => d.gpu_utilization_percent)
      .filter((v): v is number => v != null && v > 0);
    let avgUtilization: number;
    if (deviceUtils.length > 0) {
      avgUtilization = deviceUtils.reduce((sum, v) => sum + v, 0) / deviceUtils.length;
    } else if (nodeSlices.length > 0) {
      avgUtilization = nodeSlices.reduce((sum, s) => sum + s.gpu_utilization_percent, 0) / nodeSlices.length;
    } else {
      avgUtilization = 0;
    }

    nodes.push({
      node_name: nodeName,
      gpu_count: nodeDevices.length,
      total_memory_gb: totalMemory,
      allocated_memory_gb: allocatedMemory,
      memory_utilization_percent: totalMemory > 0 ? (allocatedMemory / totalMemory) * 100 : 0,
      avg_gpu_utilization_percent: avgUtilization,
      active_slices: nodeSlices.length,
      devices: nodeDevices.sort((a, b) => a.device_index - b.device_index),
    });
  });

  // Sort nodes by name
  return nodes.sort((a, b) => a.node_name.localeCompare(b.node_name));
};

export const formatBytes = (bytes: number): string => {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
};

export const formatMemoryGB = (gb: number): string => {
  if (gb >= 1) {
    return `${gb.toFixed(1)} GB`;
  }
  return `${(gb * 1024).toFixed(0)} MB`;
};

export const getSliceStatusColor = (status: string): string => {
  switch (status) {
    case "running":
      return "#479D5F";
    case "pending":
      return "#FA8C16";
    case "terminated":
      return "#EC7575";
    default:
      return "#757575";
  }
};

export const getUtilizationColor = (percent: number): string => {
  if (percent >= 90) return "#EC7575"; // Red - critical
  if (percent >= 70) return "#FA8C16"; // Orange - warning
  if (percent >= 50) return "#D1B854"; // Yellow - moderate
  return "#479D5F"; // Green - healthy
};

// ============ Mock Data for Development ============

const generateMockGPUMetrics = (clusterId: string): GPUMetricsResponse => {
  const now = new Date().toISOString();

  // Multi-node mock data: worker-1 (2x A100), worker-2 (1x L40S)
  const devices: GPUDevice[] = [
    // worker-1: GPU 0 - A100 80GB
    {
      device_uuid: "GPU-aaa11111-1111-1111-1111-111111111111",
      device_index: 0,
      device_type: "NVIDIA A100-SXM4-80GB",
      node_name: "worker-1",
      total_memory_gb: 80.0,
      memory_allocated_gb: 36.0,
      memory_utilization_percent: 45.0,
      core_utilization_percent: 32,
      cores_allocated_percent: 100,
      shared_containers_count: 2,
      hardware_mode: "time-slicing",
      last_metrics_update: now,
      temperature_celsius: 48,
      power_watts: 185.5,
      sm_clock_mhz: 1410,
      memory_clock_mhz: 1593,
      pcie_tx_bytes: 5817060,
      pcie_rx_bytes: 4833633,
    },
    // worker-1: GPU 1 - A100 80GB
    {
      device_uuid: "GPU-bbb22222-2222-2222-2222-222222222222",
      device_index: 1,
      device_type: "NVIDIA A100-SXM4-80GB",
      node_name: "worker-1",
      total_memory_gb: 80.0,
      memory_allocated_gb: 74.0,
      memory_utilization_percent: 92.5,
      core_utilization_percent: 78,
      cores_allocated_percent: 100,
      shared_containers_count: 3,
      hardware_mode: "time-slicing",
      last_metrics_update: now,
      temperature_celsius: 62,
      power_watts: 295.0,
      sm_clock_mhz: 1410,
      memory_clock_mhz: 1593,
      pcie_tx_bytes: 8217060,
      pcie_rx_bytes: 7133633,
    },
    // worker-2: GPU 0 - L40S 48GB
    {
      device_uuid: "GPU-ccc33333-3333-3333-3333-333333333333",
      device_index: 0,
      device_type: "NVIDIA L40S",
      node_name: "worker-2",
      total_memory_gb: 48.0,
      memory_allocated_gb: 35.5,
      memory_utilization_percent: 74.0,
      core_utilization_percent: 15,
      cores_allocated_percent: 100,
      shared_containers_count: 2,
      hardware_mode: "time-slicing",
      last_metrics_update: now,
      temperature_celsius: 52,
      power_watts: 115.5,
      sm_clock_mhz: 2520,
      memory_clock_mhz: 9001,
      pcie_tx_bytes: 3817060,
      pcie_rx_bytes: 2833633,
    },
  ];

  const slices: HAMISlice[] = [
    // worker-1, GPU 0 slices
    {
      pod_name: "bud-llama-70b-abc123-5cfd5b9764-mh5cx",
      pod_namespace: "bud-llama-70b-abc123",
      container_name: "cuda-container",
      device_uuid: "GPU-aaa11111-1111-1111-1111-111111111111",
      device_index: 0,
      node_name: "worker-1",
      memory_limit_bytes: 34359738368,
      memory_limit_gb: 32.0,
      memory_used_bytes: 32212254720,
      memory_used_gb: 30.0,
      memory_utilization_percent: 93.8,
      core_limit_percent: 50,
      core_used_percent: 32,
      gpu_utilization_percent: 32,
      last_kernel_id: 174106,
      status: "running",
    },
    {
      pod_name: "bud-embed-small-xyz789-8594f6f945-gzhbv",
      pod_namespace: "bud-embed-small-xyz789",
      container_name: "cuda-container",
      device_uuid: "GPU-aaa11111-1111-1111-1111-111111111111",
      device_index: 0,
      node_name: "worker-1",
      memory_limit_bytes: 4294967296,
      memory_limit_gb: 4.0,
      memory_used_bytes: 3221225472,
      memory_used_gb: 3.0,
      memory_utilization_percent: 75.0,
      core_limit_percent: 50,
      core_used_percent: 8,
      gpu_utilization_percent: 8,
      last_kernel_id: 259219,
      status: "running",
    },
    // worker-1, GPU 1 slices
    {
      pod_name: "bud-qwen2-72b-def456-5996b75dd9-b2rcf",
      pod_namespace: "bud-qwen2-72b-def456",
      container_name: "cuda-container",
      device_uuid: "GPU-bbb22222-2222-2222-2222-222222222222",
      device_index: 1,
      node_name: "worker-1",
      memory_limit_bytes: 42949672960,
      memory_limit_gb: 40.0,
      memory_used_bytes: 40802189312,
      memory_used_gb: 38.0,
      memory_utilization_percent: 95.0,
      core_limit_percent: 60,
      core_used_percent: 55,
      gpu_utilization_percent: 55,
      last_kernel_id: 68487,
      status: "running",
    },
    {
      pod_name: "bud-mixtral-8x7b-ghi012-7b5546fb5f-5gqhj",
      pod_namespace: "bud-mixtral-8x7b-ghi012",
      container_name: "cuda-container",
      device_uuid: "GPU-bbb22222-2222-2222-2222-222222222222",
      device_index: 1,
      node_name: "worker-1",
      memory_limit_bytes: 32212254720,
      memory_limit_gb: 30.0,
      memory_used_bytes: 30064771072,
      memory_used_gb: 28.0,
      memory_utilization_percent: 93.3,
      core_limit_percent: 40,
      core_used_percent: 23,
      gpu_utilization_percent: 23,
      last_kernel_id: 59841,
      status: "running",
    },
    {
      pod_name: "bud-codegen-jkl345-pending-pod",
      pod_namespace: "bud-codegen-jkl345",
      container_name: "cuda-container",
      device_uuid: "GPU-bbb22222-2222-2222-2222-222222222222",
      device_index: 1,
      node_name: "worker-1",
      memory_limit_bytes: 4294967296,
      memory_limit_gb: 4.0,
      memory_used_bytes: 0,
      memory_used_gb: 0,
      memory_utilization_percent: 0,
      core_limit_percent: 20,
      core_used_percent: 0,
      gpu_utilization_percent: 0,
      status: "pending",
    },
    // worker-2, GPU 0 slices
    {
      pod_name: "infinity-emb-8594f6f945-gzhbv",
      pod_namespace: "infinity",
      container_name: "infinity",
      device_uuid: "GPU-ccc33333-3333-3333-3333-333333333333",
      device_index: 0,
      node_name: "worker-2",
      memory_limit_bytes: 25769803776,
      memory_limit_gb: 24.0,
      memory_used_bytes: 24696061952,
      memory_used_gb: 23.0,
      memory_utilization_percent: 95.8,
      core_limit_percent: 50,
      core_used_percent: 12,
      gpu_utilization_percent: 12,
      last_kernel_id: 174106,
      status: "running",
    },
    {
      pod_name: "bud-nomic-3af5475a-5996b75dd9-b2rcf",
      pod_namespace: "bud-nomic-3af5475a",
      container_name: "latentbud-container",
      device_uuid: "GPU-ccc33333-3333-3333-3333-333333333333",
      device_index: 0,
      node_name: "worker-2",
      memory_limit_bytes: 12884901888,
      memory_limit_gb: 12.0,
      memory_used_bytes: 11274289152,
      memory_used_gb: 10.5,
      memory_utilization_percent: 87.5,
      core_limit_percent: 50,
      core_used_percent: 3,
      gpu_utilization_percent: 3,
      last_kernel_id: 68487,
      status: "running",
    },
  ];

  // Group devices by node for nodes array
  const nodes = groupDevicesByNode(devices, slices);

  // Calculate cluster summary
  const totalMemoryGB = devices.reduce((sum, d) => sum + d.total_memory_gb, 0);
  const allocatedMemoryGB = devices.reduce((sum, d) => sum + d.memory_allocated_gb, 0);
  const activeSlices = slices.filter(s => s.status === "running").length;
  const runningSlices = slices.filter(s => s.status === "running");

  // Calculate avg GPU utilization: prefer DCGM device utils, fallback to slice utils
  const deviceUtils = devices
    .map(d => d.gpu_utilization_percent)
    .filter((v): v is number => v != null && v > 0);
  let avgGpuUtilization: number;
  if (deviceUtils.length > 0) {
    avgGpuUtilization = deviceUtils.reduce((sum, v) => sum + v, 0) / deviceUtils.length;
  } else if (runningSlices.length > 0) {
    avgGpuUtilization = runningSlices.reduce((sum, s) => sum + s.gpu_utilization_percent, 0) / runningSlices.length;
  } else {
    avgGpuUtilization = 0;
  }

  return {
    cluster_id: clusterId,
    timestamp: now,
    summary: {
      total_gpus: devices.length,
      total_memory_gb: totalMemoryGB,
      allocated_memory_gb: allocatedMemoryGB,
      available_memory_gb: totalMemoryGB - allocatedMemoryGB,
      memory_utilization_percent: (allocatedMemoryGB / totalMemoryGB) * 100,
      avg_gpu_utilization_percent: avgGpuUtilization,
      total_slices: slices.length,
      active_slices: activeSlices,
      avg_temperature_celsius: devices.reduce((sum, d) => sum + (d.temperature_celsius || 0), 0) / devices.length,
      total_power_watts: devices.reduce((sum, d) => sum + (d.power_watts || 0), 0),
    },
    nodes,
    devices,
    slices,
    quotas: [
      { namespace: "bud-llama-70b-abc123", gpu_memory_used_mb: 30720, gpu_cores_used_percent: 32 },
      { namespace: "bud-embed-small-xyz789", gpu_memory_used_mb: 3072, gpu_cores_used_percent: 8 },
      { namespace: "bud-qwen2-72b-def456", gpu_memory_used_mb: 38912, gpu_cores_used_percent: 55 },
      { namespace: "bud-mixtral-8x7b-ghi012", gpu_memory_used_mb: 28672, gpu_cores_used_percent: 23 },
      { namespace: "bud-codegen-jkl345", gpu_memory_used_mb: 0, gpu_cores_used_percent: 0 },
      { namespace: "infinity", gpu_memory_used_mb: 23552, gpu_cores_used_percent: 12 },
      { namespace: "bud-nomic-3af5475a", gpu_memory_used_mb: 10752, gpu_cores_used_percent: 3 },
    ],
  };
};

// ============ Node GPU Timeseries Types ============

export interface NodeGPUTimeSeriesData {
  timestamps: number[]; // Unix timestamps in ms
  gpu_utilization: number[][]; // Per GPU utilization [gpu0[], gpu1[], ...]
  memory_utilization: number[][]; // Per GPU memory [gpu0[], gpu1[], ...]
  temperature: number[][]; // Per GPU temp
  power: number[][]; // Per GPU power
  slice_activity: { // Per slice activity over time
    slice_name: string;
    namespace: string;
    data: number[];
  }[];
}

// Generate mock timeseries data for visualization
const generateMockTimeSeries = (hours: number = 6, intervalMinutes: number = 5): NodeGPUTimeSeriesData => {
  const now = Date.now();
  const points = Math.floor((hours * 60) / intervalMinutes);
  const timestamps: number[] = [];

  // Generate timestamps
  for (let i = points - 1; i >= 0; i--) {
    timestamps.push(now - i * intervalMinutes * 60 * 1000);
  }

  // Helper to generate realistic fluctuating data
  const generateFluctuatingData = (base: number, variance: number, trend: number = 0): number[] => {
    let current = base;
    return timestamps.map((_, i) => {
      const noise = (Math.random() - 0.5) * variance;
      const trendEffect = trend * (i / points);
      current = Math.max(0, Math.min(100, base + noise + trendEffect + (Math.random() - 0.5) * 5));
      return Math.round(current * 10) / 10;
    });
  };

  // Generate data for 2 GPUs
  const gpu_utilization = [
    generateFluctuatingData(35, 30, 10), // GPU 0 - moderate usage with slight uptrend
    generateFluctuatingData(75, 20, -5), // GPU 1 - high usage with slight downtrend
  ];

  const memory_utilization = [
    generateFluctuatingData(45, 15, 5), // GPU 0 memory
    generateFluctuatingData(92, 5, 0), // GPU 1 memory - high and stable
  ];

  const temperature = [
    generateFluctuatingData(48, 8, 3), // GPU 0 temp
    generateFluctuatingData(62, 10, 2), // GPU 1 temp - warmer
  ];

  const power = [
    generateFluctuatingData(185, 40, 10), // GPU 0 power in watts
    generateFluctuatingData(295, 50, -5), // GPU 1 power
  ];

  // Generate slice activity data
  const slice_activity = [
    {
      slice_name: "llama-70b-pod",
      namespace: "bud-llama-70b",
      data: generateFluctuatingData(30, 20, 5),
    },
    {
      slice_name: "embed-small-pod",
      namespace: "bud-embed-small",
      data: generateFluctuatingData(8, 5, 0),
    },
    {
      slice_name: "qwen2-72b-pod",
      namespace: "bud-qwen2-72b",
      data: generateFluctuatingData(55, 15, -3),
    },
    {
      slice_name: "mixtral-8x7b-pod",
      namespace: "bud-mixtral-8x7b",
      data: generateFluctuatingData(23, 10, 2),
    },
  ];

  return {
    timestamps,
    gpu_utilization,
    memory_utilization,
    temperature,
    power,
    slice_activity,
  };
};

// ============ Node-specific GPU response ============

export interface NodeGPUMetricsResponse {
  cluster_id: string;
  node_name: string;
  timestamp: string;
  devices: GPUDevice[];
  slices: HAMISlice[];
  summary: {
    gpu_count: number;
    total_memory_gb: number;
    allocated_memory_gb: number;
    memory_utilization_percent: number;
    avg_gpu_utilization_percent: number;
    active_slices: number;
  };
}

// ============ Zustand Store ============

interface GPUMetricsStore {
  // State
  metrics: GPUMetricsResponse | null;
  nodeMetrics: NodeGPUMetricsResponse | null;
  nodeTimeSeries: NodeGPUTimeSeriesData | null;
  timeSeries: GPUTimeSeries[];
  loading: boolean;
  timeSeriesLoading: boolean;
  error: string | null;
  lastFetch: Date | null;

  // Actions
  fetchGPUMetrics: (clusterId: string) => Promise<GPUMetricsResponse | null>;
  fetchNodeGPUMetrics: (clusterId: string, hostname: string) => Promise<NodeGPUMetricsResponse | null>;
  fetchNodeGPUTimeSeries: (clusterId: string, hostname: string, hours?: number) => Promise<NodeGPUTimeSeriesData | null>;
  fetchGPUTimeSeries: (clusterId: string, metric: string, hours?: number) => Promise<GPUTimeSeries[]>;
  clearMetrics: () => void;
  setError: (error: string | null) => void;
}

export const useGPUMetrics = create<GPUMetricsStore>((set, get) => ({
  metrics: null,
  nodeMetrics: null,
  nodeTimeSeries: null,
  timeSeries: [],
  loading: false,
  timeSeriesLoading: false,
  error: null,
  lastFetch: null,

  fetchGPUMetrics: async (clusterId: string) => {
    set({ loading: true, error: null });

    try {
      const response = await AppRequest.Get(`${tempApiBaseUrl}/clusters/${clusterId}/metrics/gpu`);
      const data = response.data as GPUMetricsResponse;

      // Group devices by node if not already done
      if (data.nodes.length === 0 && data.devices.length > 0) {
        data.nodes = groupDevicesByNode(data.devices, data.slices);
      }

      set({
        metrics: data,
        loading: false,
        lastFetch: new Date(),
      });

      return data;
    } catch (error: any) {
      console.error("Error fetching GPU metrics:", error);
      set({
        error: error?.response?.data?.message || error?.message || "Failed to fetch GPU metrics",
        loading: false,
      });
      return null;
    }
  },

  fetchNodeGPUMetrics: async (clusterId: string, hostname: string) => {
    set({ loading: true, error: null });

    try {
      const response = await AppRequest.Get(`${tempApiBaseUrl}/clusters/${clusterId}/nodes/${hostname}/metrics/gpu`);
      const data = response.data as NodeGPUMetricsResponse;

      set({
        nodeMetrics: data,
        loading: false,
        lastFetch: new Date(),
      });

      return data;
    } catch (error: any) {
      console.error("Error fetching node GPU metrics:", error);
      set({
        error: error?.response?.data?.message || error?.message || "Failed to fetch node GPU metrics",
        loading: false,
      });
      return null;
    }
  },

  fetchNodeGPUTimeSeries: async (clusterId: string, hostname: string, hours: number = 6) => {
    set({ timeSeriesLoading: true });

    try {
      const response = await AppRequest.Get(
        `${tempApiBaseUrl}/clusters/${clusterId}/nodes/${hostname}/metrics/gpu/timeseries`,
        { params: { hours } }
      );
      const data = response.data as NodeGPUTimeSeriesData;

      set({
        nodeTimeSeries: data,
        timeSeriesLoading: false,
      });

      return data;
    } catch (error: any) {
      console.error("Error fetching node GPU timeseries:", error);
      set({ timeSeriesLoading: false });
      return null;
    }
  },

  fetchGPUTimeSeries: async (clusterId: string, metric: string, hours: number = 24) => {
    try {
      // TODO: Replace with actual API call when backend is ready
      // const response = await AppRequest.Get(`${tempApiBaseUrl}/clusters/${clusterId}/gpu-metrics/timeseries`, {
      //   params: { metric, hours }
      // });
      // return response.data as GPUTimeSeries[];

      // For now, return empty array
      return [];
    } catch (error) {
      console.error("Error fetching GPU time series:", error);
      return [];
    }
  },

  clearMetrics: () => {
    set({ metrics: null, nodeMetrics: null, nodeTimeSeries: null, timeSeries: [], error: null, lastFetch: null });
  },

  setError: (error: string | null) => {
    set({ error });
  },
}));

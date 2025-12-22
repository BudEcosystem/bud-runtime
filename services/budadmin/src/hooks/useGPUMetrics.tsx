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
      set({
        error: error?.response?.data?.message || error?.message || "Failed to fetch node GPU timeseries",
        timeSeriesLoading: false,
      });
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

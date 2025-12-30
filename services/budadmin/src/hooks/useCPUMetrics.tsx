import { tempApiBaseUrl } from "@/components/environment";
import { AppRequest } from "src/pages/api/requests";
import { create } from "zustand";

// ============ Types ============

export interface NodeCPUTimeSeriesData {
  timestamps: number[]; // Unix timestamps in ms
  cpu_usage_percent: number[]; // CPU usage over time
  load_1: number[]; // 1-minute load average over time
  load_5: number[]; // 5-minute load average over time
  load_15: number[]; // 15-minute load average over time
}

// ============ Utility Functions ============

export const getCPUUtilizationColor = (percent: number): string => {
  if (percent >= 90) return "#EC7575"; // Red - critical
  if (percent >= 70) return "#FA8C16"; // Orange - warning
  if (percent >= 50) return "#D1B854"; // Yellow - moderate
  return "#479D5F"; // Green - healthy
};

export const getLoadColor = (load: number, cpuCores: number): string => {
  if (cpuCores <= 0) return "#479D5F";
  const loadPerCore = load / cpuCores;
  if (loadPerCore >= 2) return "#EC7575"; // Red - critical (2x overloaded)
  if (loadPerCore >= 1) return "#FA8C16"; // Orange - warning (fully loaded)
  if (loadPerCore >= 0.7) return "#D1B854"; // Yellow - moderate
  return "#479D5F"; // Green - healthy
};

// ============ Zustand Store ============

interface CPUMetricsStore {
  // State
  nodeTimeSeries: NodeCPUTimeSeriesData | null;
  timeSeriesLoading: boolean;
  error: string | null;

  // Actions
  fetchNodeCPUTimeSeries: (
    clusterId: string,
    hostname: string,
    hours?: number
  ) => Promise<NodeCPUTimeSeriesData | null>;
  clearMetrics: () => void;
  setError: (error: string | null) => void;
}

export const useCPUMetrics = create<CPUMetricsStore>((set) => ({
  nodeTimeSeries: null,
  timeSeriesLoading: false,
  error: null,

  fetchNodeCPUTimeSeries: async (
    clusterId: string,
    hostname: string,
    hours: number = 6
  ) => {
    set({ timeSeriesLoading: true });

    try {
      const response = await AppRequest.Get(
        `${tempApiBaseUrl}/clusters/${clusterId}/nodes/${hostname}/metrics/cpu/timeseries`,
        { params: { hours } }
      );
      const data = response.data as NodeCPUTimeSeriesData;

      set({
        nodeTimeSeries: data,
        timeSeriesLoading: false,
      });

      return data;
    } catch (error: any) {
      console.error("Error fetching node CPU timeseries:", error);
      set({
        error:
          error?.response?.data?.message ||
          error?.message ||
          "Failed to fetch CPU timeseries",
        timeSeriesLoading: false,
      });
      return null;
    }
  },

  clearMetrics: () => {
    set({ nodeTimeSeries: null, error: null });
  },

  setError: (error: string | null) => {
    set({ error });
  },
}));

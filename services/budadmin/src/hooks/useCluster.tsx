import { tempApiBaseUrl } from "@/components/environment";
import { successToast } from "@/components/toast";
import { useCallback, useEffect, useState } from "react";
import { Id } from "react-toastify";
import { useLoader } from "src/context/appContext";
import { AppRequest } from "src/pages/api/requests";
import { create } from "zustand";

export type ClusterNodeEvent = {
  type: string;
  reason: string;
  message: string;
  count: number;
  first_timestamp: string;
  last_timestamp: string;
  source: {
    component: string;
    host: string;
  };
};

export type Node = {
  hostname: string;
  status: string;
  system_info: {
    os: string;
    kernel: string;
    architecture: string;
  };
  pods: {
    current: number;
    max: number;
  };
  cpu?: {
    current: number;
    capacity: number;
  };
  hpu?: {
    current: number;
    capacity: number;
  };
  gpu?: {
    current: number;
    capacity: number;
  };
  memory: {
    current: number;
    capacity: number;
  };
  network: {
    bandwidth: {
      timestamp: number;
      mbps: number;
    }[];
  };
  events_count: number;
  capacity: {
    memory: string;
    hugepages_2Mi: string;
    pods: string;
    ephemeral_storage: string;
    hugepages_1Gi: string;
    cpu: string;
  };
};

export type NodeMetrics = Record<string, Node>;

export type ClusterFilter = "today" | "7days" | "month";

export enum MetricType {
  MEMORY = "memory",
  CPU = "cpu",
  DISK = "disk",
  STORAGE = "storage",
  GPU = "gpu",
  HPU = "hpu",
  NETWORK_BANDWIDTH = "network_bandwidth",
  ALL = "all",
}

type ClusterSummary = {
  memory: {
    total_gib: number;
    used_gib: number;
    available_gib: number;
    usage_percent: number;
    change_percent: number;
  };
  cpu: {
    usage_percent: number;
    change_percent: number;
  };
  gpu: {
    usage_percent: number;
    change_percent: number;
  };
  hpu: {
    usage_percent: number;
    change_percent: number;
  };
  storage: {
    total_gib: number;
    used_gib: number;
    available_gib: number;
    usage_percent: number;
    change_percent: number;
  };
  network_in: {
    inbound_mbps: number;
    change_percent: number;
    time_series: TimeSeriesData[];
  };
  network_out: {
    outbound_mbps: number;
    change_percent: number;
    time_series: TimeSeriesData[];
  };
  network_bandwidth: {
    total_mbps: number;
    change_percent: number;
    time_series: TimeSeriesData[];
  };
  power: {
    change_percent: number;
    total_watts: number;
  };
};

export type TimeSeriesData = {
  timestamp: number;
  value: number;
};

export interface ClusterMetrics {
  cluster_summary: ClusterSummary;
  time_range: ClusterFilter;
  metric_type: string;
  timestamp: string;
}

export type Cluster = {
  id: string;
  cluster_id?: string;
  name: string;
  type?: string;
  cost_per_token?: number;
  total_resources?: number;
  resources_used?: number;
  // Parser metadata from simulator
  tool_calling_parser_type?: string | null;
  reasoning_parser_type?: string | null;
  chat_template?: string | null;
  // Engine capability flags from simulator
  supports_lora?: boolean | null;
  supports_pipeline_parallelism?: boolean | null;
  required_devices?: {
    device_type: string;
    num_replicas: number;
    concurrency: number;
    cost_per_million_tokens: number;
  }[];
  resource_details?: {
    type: string;
    available: number;
    total: number;
  }[];
  benchmarks?: {
    replicas: number;
    concurrency: {
      label: string;
      value: number;
    };
    ttft?: number;
    e2e_latency?: number;
    per_session_tokens_per_sec?: number;
    over_all_throughput?: number;
  };
  created_at?: string;
  modified_at?: string;
  status?: string;
  icon?: string;
  ingress_url?: string;
  cpu_count?: number;
  gpu_count?: number;
  hpu_count?: number;
  cpu_total_workers?: number;
  cpu_available_workers?: number;
  gpu_total_workers?: number;
  gpu_available_workers?: number;
  hpu_total_workers?: number;
  hpu_available_workers?: number;
  total_nodes?: number;
  available_nodes?: number;
  endpoint_count?: number;
  total_endpoints_count?: number;
  running_endpoints_count?: number;
  active_workers_count?: number;
  total_workers_count?: number;
  hardware_type?: string[];
};

export interface ICluster {
  clusters: Cluster[];
  status: string;
  id: string;
}

export interface UpdateCluster {
  name: string;
  icon: string;
  ingress_url: string;
}

export interface GetParams {
  clusterId?: string;
  page: number;
  limit: number;
  type?: string;
}

// create zustand store
export const useCluster = create<{
  selectedNode: Node;
  setSelectedNode: (node: Node) => void;
  recommendedCluster: ICluster;
  clusters: Cluster[];
  clusterEndpoints: Cluster[];
  clusterDetails: any;
  currentProcessId: string;
  loading: boolean;
  clusterValues: any;
  getRecommendedClusterById: (id: string) => Promise<any>;
  createClusterWorkflow: (data: any) => Promise<any>;
  updateCluster: (id: string, data: UpdateCluster) => Promise<any>;
  selectedCluster: Cluster;
  setCluster: (cluster: Cluster) => void;
  getClusters: (params: GetParams) => Promise<void>;
  setClusterValues: (values: any) => void;
  filter: any;
  refresh: () => void;
  deleteCluster: (id: string) => Promise<any>;
  getClusterById: (id: string) => Promise<Cluster>;
  getClusterEndpoints: (params: GetParams) => Promise<any>;
  getClusterMetrics: (
    id: string,
    filter: ClusterFilter,
    metricType: MetricType,
  ) => Promise<ClusterMetrics>;
  getClusterNodeMetrics: (id: string) => Promise<NodeMetrics>;
  getClusterNodeEvents: (
    id: string,
    nodeId: string,
    page: number,
    limit: number,
  ) => Promise<any>;
  // Cloud based Cluster
  cloudID: string;
  setCloudID: (id: string) => void;
  cloudCredentialID: string;
  setCloudCredentialID: (id: string) => void;
  getClusterAnalytics: (id: string) => Promise<any>;
  // Cluster Settings methods
  getClusterSettings: (id: string) => Promise<any>;
  createClusterSettings: (
    id: string,
    data: { default_storage_class?: string | null; default_access_mode?: string | null },
  ) => Promise<any>;
  updateClusterSettings: (
    id: string,
    data: { default_storage_class?: string | null; default_access_mode?: string | null },
  ) => Promise<any>;
  deleteClusterSettings: (id: string) => Promise<any>;
  getClusterStorageClasses: (id: string) => Promise<any[]>;
}>((set, get) => ({
  getClusterAnalytics: async (id: string) => {
    const url = `${tempApiBaseUrl}/clusters/${id}/grafana-dashboard`;
    try {
      const response: any = await AppRequest.Get(url);
      return response.data;
    } catch (error) {
      console.error("Error getting cluster analytics:", error);
    }
  },
  cloudID: "",
  setCloudID: (id: string) => {
    set({ cloudID: id });
  },
  cloudCredentialID: "",
  setCloudCredentialID: (id: string) => {
    set({ cloudCredentialID: id });
  },
  selectedNode: {} as Node,
  setSelectedNode: (node: Node) => {
    set({ selectedNode: node });
  },
  clusterDetails: {},
  recommendedCluster: {} as ICluster,
  clusters: [],
  clusterEndpoints: [],
  currentProcessId: "",
  loading: true,
  selectedCluster: {} as Cluster,
  clusterValues: {},
  getRecommendedClusterById: async (id) => {
    const url = `${tempApiBaseUrl}/clusters/recommended/${id}`;
    set({ loading: true });
    try {
      const response: any = await AppRequest.Get(url);
      set({ recommendedCluster: response.data });
      return response.data;
    } catch (error) {
      console.error("Error getting recommended cluster:", error);
    } finally {
      set({ loading: false });
    }
  },
  createClusterWorkflow: async (data: FormData) => {
    const url = `${tempApiBaseUrl}/clusters/clusters`;
    try {
      const response: any = await AppRequest.Post(url, data);
      return response.data;
    } catch (error) {
      console.error("Error creating cluster:", error);
    }
  },
  updateCluster: async (id: string, data: UpdateCluster) => {
    const url = `${tempApiBaseUrl}/clusters/${id}`;
    try {
      const response: any = await AppRequest.Patch(url, data);
      return response.data;
    } catch (error) {
      console.error("Error updating cluster:", error);
    }
  },
  setCluster: (cluster: Cluster) => {
    set({ selectedCluster: cluster });
  },

  getClusters: async (params: GetParams) => {
    const { page, limit, type } = params;
    set({ loading: true });
    try {
      const response: any = await AppRequest.Get(
        `${tempApiBaseUrl}/clusters/clusters`,
        {
          params: {
            page: page,
            limit: limit,
            search: false,
            type: type,
            order_by: "-created_at",
          },
        },
      );
      set({ clusters: response.data.clusters });
    } catch (error) {
      console.error("Error getting clusters:", error);
    } finally {
      set({ loading: false });
    }
  },
  setClusterValues(values) {
    set({ clusterValues: values });
  },
  filter: {},
  refresh: () => {
    get().getClusters(get().filter);
  },
  deleteCluster: async (id: string) => {
    const url = `/clusters/${id}`;
    try {
      const response: any = await AppRequest.Post(
        `${tempApiBaseUrl}/clusters/${id}/delete-workflow`,
      );
      get().getClusters(get().filter);
      return response;
    } catch (error) {
      // console.error("Error deleting cluster:", error);
      console.error("error", error);
      return error;
    }
  },
  getClusterById: async (id: string) => {
    const url = `${tempApiBaseUrl}/clusters/${id}`;
    try {
      const response: any = await AppRequest.Get(url);
      set({ selectedCluster: response.data.cluster });
      return response.data.cluster;
    } catch (error) {
      console.error("Error getting cluster:", error);
    }
  },
  getClusterEndpoints: async (params: GetParams) => {
    const { clusterId, page, limit, type } = params;
    set({ loading: true });
    try {
      const response: any = await AppRequest.Get(
        `${tempApiBaseUrl}/clusters/${clusterId}/endpoints`,
        {
          params: {
            page: page,
            limit: limit,
            search: false,
            type: type,
            order_by: "-created_at",
          },
        },
      );
      set({ clusterEndpoints: response.data.endpoints });
    } catch (error) {
      console.error("Error getting clusters:", error);
    } finally {
      set({ loading: false });
    }
  },
  getClusterMetrics: async (
    id: string,
    filter: ClusterFilter,
    metricType: MetricType,
  ) => {
    const url = `${tempApiBaseUrl}/clusters/${id}/metrics`;
    try {
      const response: any = await AppRequest.Get(url, {
        params: {
          filter: filter,
          metric_type: metricType,
        },
      });
      return response.data;
    } catch (error) {
      console.error("Error getting cluster metrics:", error);
    }
  },
  getClusterNodeMetrics: async (id: string) => {
    const url = `${tempApiBaseUrl}/clusters/${id}/node-metrics`;
    try {
      const response: any = await AppRequest.Get(url);
      console.log("response", response);
      return response.data?.nodes;
    } catch (error) {
      console.error("Error getting cluster metrics:", error);
    }
  },
  getClusterNodeEvents: async (
    id: string,
    nodeId: string,
    page: number,
    limit: number,
  ) => {
    const url = `${tempApiBaseUrl}/clusters/${id}/node-events/${nodeId}`;
    try {
      const response: any = await AppRequest.Get(url, {
        params: {
          limit: limit,
          page: page,
        },
      });
      return response.data;
    } catch (error) {
      console.error("Error getting cluster events:", error);
    }
  },

  // Cluster Settings API Methods
  getClusterSettings: async (id: string) => {
    const url = `${tempApiBaseUrl}/clusters/${id}/settings`;
    try {
      const response: any = await AppRequest.Get(url);
      return response.data.settings;
    } catch (error) {
      if (error?.response?.status === 404) {
        // Settings don't exist yet, return null
        return null;
      }
      console.error("Error getting cluster settings:", error);
      throw error;
    }
  },

  createClusterSettings: async (
    id: string,
    data: { default_storage_class?: string | null; default_access_mode?: string | null },
  ) => {
    const url = `${tempApiBaseUrl}/clusters/${id}/settings`;
    try {
      const response: any = await AppRequest.Post(url, data);
      successToast("Cluster settings created successfully");
      return response.data.settings;
    } catch (error) {
      console.error("Error creating cluster settings:", error);
      throw error;
    }
  },

  updateClusterSettings: async (
    id: string,
    data: { default_storage_class?: string | null; default_access_mode?: string | null },
  ) => {
    const url = `${tempApiBaseUrl}/clusters/${id}/settings`;
    try {
      const response: any = await AppRequest.Put(url, data);
      successToast("Cluster settings updated successfully");
      return response.data.settings;
    } catch (error) {
      console.error("Error updating cluster settings:", error);
      throw error;
    }
  },

  deleteClusterSettings: async (id: string) => {
    const url = `${tempApiBaseUrl}/clusters/${id}/settings`;
    try {
      const response: any = await AppRequest.Delete(url);
      successToast("Cluster settings deleted successfully");
      return response.data;
    } catch (error) {
      console.error("Error deleting cluster settings:", error);
      throw error;
    }
  },

  getClusterStorageClasses: async (id: string) => {
    const url = `${tempApiBaseUrl}/clusters/${id}/storage-classes`;
    try {
      const response: any = await AppRequest.Get(url);
      return response.data.storage_classes || [];
    } catch (error) {
      console.error("Error getting cluster storage classes:", error);
      throw error;
    }
  },
}));

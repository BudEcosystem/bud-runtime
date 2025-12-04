import { create } from "zustand";
import { AppRequest } from "../pages/api/requests";
import { tempApiBaseUrl } from "@/components/environment";
import { message } from "antd";
import * as echarts from "echarts";

// ============ Interfaces ============

// Deployment for sidebar
export interface ComparisonDeployment {
  id: string;
  endpoint_name: string;
  model_id: string;
  model_name: string;
  model_display_name: string;
  model_icon: string | null;
  experiment_count: number;
  run_count: number;
}

// Trait for sidebar checkboxes
export interface ComparisonTrait {
  id: string;
  name: string;
  icon: string;
  description: string;
  dataset_count: number;
  run_count: number;
}

// Radar chart data from API
export interface RadarTraitScore {
  trait_id: string;
  trait_name: string;
  score: number;
  run_count: number;
}

export interface RadarDeploymentData {
  deployment_id: string;
  deployment_name: string;
  model_name: string;
  color: string;
  trait_scores: RadarTraitScore[];
}

export interface RadarChartResponse {
  traits: { id: string; name: string; icon: string }[];
  deployments: RadarDeploymentData[];
}

// Heatmap chart data from API
export interface HeatmapDatasetScore {
  dataset_id: string;
  dataset_name: string;
  score: number | null;
  run_count: number;
}

export interface HeatmapDeploymentData {
  deployment_id: string;
  deployment_name: string;
  model_name: string;
  dataset_scores: HeatmapDatasetScore[];
}

export interface HeatmapChartResponse {
  datasets: { id: string; name: string }[];
  deployments: HeatmapDeploymentData[];
  stats: {
    min_score: number;
    max_score: number;
    avg_score: number;
  };
}

// Chart data formats for components
export interface RadarChartData {
  indicators: { name: string; max: number }[];
  series: {
    name: string;
    value: number[];
    color?: string;
    areaStyle?: any;
  }[];
  showLegend?: boolean;
}

export interface HeatmapChartData {
  xAxis: string[];
  yAxis: string[];
  data: [number, number, number | null][]; // null indicates missing data
  min?: number;
  max?: number;
}

// ============ API Response Interfaces ============

interface ApiResponse<T> {
  data: T;
}

interface DeploymentsApiData {
  deployments: ComparisonDeployment[];
  page: number;
  limit: number;
  total_record: number;
}

interface TraitsApiData {
  traits: ComparisonTrait[];
}

interface RadarApiData {
  traits: { id: string; name: string; icon: string }[];
  deployments: RadarDeploymentData[];
}

interface HeatmapApiData {
  datasets: { id: string; name: string }[];
  deployments: HeatmapDeploymentData[];
  stats: {
    min_score: number;
    max_score: number;
    avg_score: number;
  };
}

// ============ Store Interface ============

interface ComparisonStore {
  // Data
  deployments: ComparisonDeployment[];
  traits: ComparisonTrait[];
  radarData: RadarChartResponse | null;
  heatmapData: HeatmapChartResponse | null;

  // Selections
  selectedDeploymentIds: string[];
  selectedTraitIds: string[];

  // Loading states
  isLoadingDeployments: boolean;
  isLoadingTraits: boolean;
  isLoadingRadar: boolean;
  isLoadingHeatmap: boolean;
  isInitialized: boolean;

  // Error states
  deploymentsError: string | null;
  traitsError: string | null;
  radarError: string | null;
  heatmapError: string | null;

  // Pagination for deployments
  deploymentsPage: number;
  deploymentsLimit: number;
  deploymentsTotal: number;

  // Fetch methods
  fetchDeployments: (page?: number, limit?: number) => Promise<void>;
  fetchTraits: (deploymentIds?: string[]) => Promise<void>;
  fetchRadarData: (
    deploymentIds?: string[],
    traitIds?: string[],
    startDate?: string,
    endDate?: string
  ) => Promise<void>;
  fetchHeatmapData: (
    deploymentIds?: string[],
    traitIds?: string[],
    datasetIds?: string[],
    startDate?: string,
    endDate?: string
  ) => Promise<void>;

  // Selection methods
  toggleDeploymentSelection: (id: string) => void;
  toggleTraitSelection: (id: string) => void;
  setSelectedDeployments: (ids: string[]) => void;
  setSelectedTraits: (ids: string[]) => void;

  // Initial load
  initializeData: () => Promise<void>;

  // Refresh charts based on selections
  refreshCharts: () => Promise<void>;

  // Transformed data getters
  getRadarChartData: () => RadarChartData;
  getHeatmapChartData: () => HeatmapChartData;

  // Reset
  reset: () => void;
}

// ============ Default Values ============

const defaultRadarChartData: RadarChartData = {
  indicators: [],
  series: [],
  showLegend: false,
};

const defaultHeatmapChartData: HeatmapChartData = {
  xAxis: [],
  yAxis: [],
  data: [],
  min: 0,
  max: 100,
};

// ============ Store Implementation ============

export const useComparisonStore = create<ComparisonStore>((set, get) => ({
  // Initial state
  deployments: [],
  traits: [],
  radarData: null,
  heatmapData: null,

  selectedDeploymentIds: [],
  selectedTraitIds: [],

  isLoadingDeployments: false,
  isLoadingTraits: false,
  isLoadingRadar: false,
  isLoadingHeatmap: false,
  isInitialized: false,

  deploymentsError: null,
  traitsError: null,
  radarError: null,
  heatmapError: null,

  deploymentsPage: 1,
  deploymentsLimit: 50,
  deploymentsTotal: 0,

  // Fetch deployments for sidebar
  fetchDeployments: async (page = 1, limit = 50) => {
    set({ isLoadingDeployments: true, deploymentsError: null });
    try {
      const params = new URLSearchParams();
      params.append("page", page.toString());
      params.append("limit", limit.toString());

      const url = `${tempApiBaseUrl}/experiments/compare/deployments?${params.toString()}`;
      const response = await AppRequest.Get(url) as ApiResponse<DeploymentsApiData>;

      if (response?.data) {
        const { deployments, page, limit, total_record } = response.data;
        set({
          deployments: deployments || [],
          deploymentsPage: page || 1,
          deploymentsLimit: limit || 50,
          deploymentsTotal: total_record || 0,
          isLoadingDeployments: false,
        });
      }
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : "Failed to fetch deployments";
      console.error("Error fetching comparison deployments:", error);
      message.error("Failed to fetch deployments");
      set({ isLoadingDeployments: false, deploymentsError: errorMessage });
      throw error;
    }
  },

  // Fetch traits for sidebar filters
  fetchTraits: async (deploymentIds?: string[]) => {
    set({ isLoadingTraits: true, traitsError: null });
    try {
      const params = new URLSearchParams();
      if (deploymentIds && deploymentIds.length > 0) {
        params.append("deployment_ids", deploymentIds.join(","));
      }

      const queryString = params.toString();
      const url = `${tempApiBaseUrl}/experiments/compare/traits${queryString ? `?${queryString}` : ""}`;
      const response = await AppRequest.Get(url) as ApiResponse<TraitsApiData>;

      if (response?.data) {
        const { traits } = response.data;
        set({
          traits: traits || [],
          isLoadingTraits: false,
        });
      }
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : "Failed to fetch traits";
      console.error("Error fetching comparison traits:", error);
      message.error("Failed to fetch traits");
      set({ isLoadingTraits: false, traitsError: errorMessage });
      throw error;
    }
  },

  // Fetch radar chart data
  fetchRadarData: async (
    deploymentIds?: string[],
    traitIds?: string[],
    startDate?: string,
    endDate?: string
  ) => {
    set({ isLoadingRadar: true, radarError: null });
    try {
      const params = new URLSearchParams();
      if (deploymentIds && deploymentIds.length > 0) {
        params.append("deployment_ids", deploymentIds.join(","));
      }
      if (traitIds && traitIds.length > 0) {
        params.append("trait_ids", traitIds.join(","));
      }
      if (startDate) {
        params.append("start_date", startDate);
      }
      if (endDate) {
        params.append("end_date", endDate);
      }

      const queryString = params.toString();
      const url = `${tempApiBaseUrl}/experiments/compare/radar${queryString ? `?${queryString}` : ""}`;
      const response = await AppRequest.Get(url) as ApiResponse<RadarApiData>;

      if (response?.data) {
        const { traits, deployments } = response.data;
        set({
          radarData: {
            traits: traits || [],
            deployments: deployments || [],
          },
          isLoadingRadar: false,
        });
      }
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : "Failed to fetch radar chart data";
      console.error("Error fetching radar chart data:", error);
      message.error("Failed to fetch radar chart data");
      set({ isLoadingRadar: false, radarError: errorMessage });
      throw error;
    }
  },

  // Fetch heatmap chart data
  fetchHeatmapData: async (
    deploymentIds?: string[],
    traitIds?: string[],
    datasetIds?: string[],
    startDate?: string,
    endDate?: string
  ) => {
    set({ isLoadingHeatmap: true, heatmapError: null });
    try {
      const params = new URLSearchParams();
      if (deploymentIds && deploymentIds.length > 0) {
        params.append("deployment_ids", deploymentIds.join(","));
      }
      if (traitIds && traitIds.length > 0) {
        params.append("trait_ids", traitIds.join(","));
      }
      if (datasetIds && datasetIds.length > 0) {
        params.append("dataset_ids", datasetIds.join(","));
      }
      if (startDate) {
        params.append("start_date", startDate);
      }
      if (endDate) {
        params.append("end_date", endDate);
      }

      const queryString = params.toString();
      const url = `${tempApiBaseUrl}/experiments/compare/heatmap${queryString ? `?${queryString}` : ""}`;
      const response = await AppRequest.Get(url) as ApiResponse<HeatmapApiData>;

      if (response?.data) {
        const { datasets, deployments, stats } = response.data;
        set({
          heatmapData: {
            datasets: datasets || [],
            deployments: deployments || [],
            stats: stats || { min_score: 0, max_score: 100, avg_score: 50 },
          },
          isLoadingHeatmap: false,
        });
      }
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : "Failed to fetch heatmap chart data";
      console.error("Error fetching heatmap chart data:", error);
      message.error("Failed to fetch heatmap chart data");
      set({ isLoadingHeatmap: false, heatmapError: errorMessage });
      throw error;
    }
  },

  // Toggle deployment selection
  toggleDeploymentSelection: (id: string) => {
    const { selectedDeploymentIds } = get();
    const newSelection = selectedDeploymentIds.includes(id)
      ? selectedDeploymentIds.filter((depId) => depId !== id)
      : [...selectedDeploymentIds, id];
    set({ selectedDeploymentIds: newSelection });
  },

  // Toggle trait selection
  toggleTraitSelection: (id: string) => {
    const { selectedTraitIds } = get();
    const newSelection = selectedTraitIds.includes(id)
      ? selectedTraitIds.filter((traitId) => traitId !== id)
      : [...selectedTraitIds, id];
    set({ selectedTraitIds: newSelection });
  },

  // Set selected deployments
  setSelectedDeployments: (ids: string[]) => {
    set({ selectedDeploymentIds: ids });
  },

  // Set selected traits
  setSelectedTraits: (ids: string[]) => {
    set({ selectedTraitIds: ids });
  },

  // Initialize all data on page load
  initializeData: async () => {
    const { fetchDeployments, fetchTraits, fetchRadarData, fetchHeatmapData } = get();

    // Fetch all data in parallel, allowing partial failures
    const results = await Promise.allSettled([
      fetchDeployments(),
      fetchTraits(),
      fetchRadarData(),
      fetchHeatmapData(),
    ]);

    // Log any failures but still mark as initialized
    results.forEach((result, index) => {
      if (result.status === "rejected") {
        const operations = ["deployments", "traits", "radar", "heatmap"];
        console.error(`Failed to initialize ${operations[index]}:`, result.reason);
      }
    });

    set({ isInitialized: true });
  },

  // Refresh charts based on current selections
  refreshCharts: async () => {
    const { selectedDeploymentIds, selectedTraitIds, fetchRadarData, fetchHeatmapData } = get();

    // Pass undefined instead of empty arrays to fetch all data
    const deploymentIds = selectedDeploymentIds.length > 0 ? selectedDeploymentIds : undefined;
    const traitIds = selectedTraitIds.length > 0 ? selectedTraitIds : undefined;

    // Fetch both charts in parallel, allowing partial failures
    const results = await Promise.allSettled([
      fetchRadarData(deploymentIds, traitIds),
      fetchHeatmapData(deploymentIds, traitIds),
    ]);

    // Log any failures
    results.forEach((result, index) => {
      if (result.status === "rejected") {
        const operations = ["radar", "heatmap"];
        console.error(`Failed to refresh ${operations[index]} chart:`, result.reason);
      }
    });
  },

  // Transform radar API response to chart format
  getRadarChartData: (): RadarChartData => {
    const { radarData } = get();

    if (!radarData || !radarData.traits || radarData.traits.length === 0) {
      return defaultRadarChartData;
    }

    const maxScore = 100; // Scores are percentages 0-100

    return {
      indicators: radarData.traits.map((trait) => ({
        name: trait.name,
        max: maxScore,
      })),
      series: radarData.deployments.map((deployment) => ({
        name: deployment.deployment_name,
        value: radarData.traits.map((trait) => {
          const score = deployment.trait_scores.find((ts) => ts.trait_id === trait.id);
          return score?.score ?? 0;
        }),
        color: deployment.color,
        areaStyle: {
          color: new echarts.graphic.RadialGradient(0.5, 0.5, 1, [
            {
              color: deployment.color + "66", // 40% opacity
              offset: 0,
            },
            {
              color: deployment.color + "1A", // 10% opacity
              offset: 1,
            },
          ]),
        },
      })),
      showLegend: false,
    };
  },

  // Transform heatmap API response to chart format
  getHeatmapChartData: (): HeatmapChartData => {
    const { heatmapData } = get();

    if (!heatmapData || !heatmapData.datasets || heatmapData.datasets.length === 0) {
      return defaultHeatmapChartData;
    }

    const data: [number, number, number | null][] = [];

    heatmapData.deployments.forEach((deployment, yIndex) => {
      heatmapData.datasets.forEach((dataset, xIndex) => {
        const scoreData = deployment.dataset_scores.find(
          (ds) => ds.dataset_id === dataset.id
        );
        // Preserve null to distinguish between missing data and a score of 0
        const score = scoreData?.score ?? null;
        data.push([xIndex, yIndex, score]);
      });
    });

    return {
      xAxis: heatmapData.datasets.map((d) => d.name),
      yAxis: heatmapData.deployments.map((d) => d.deployment_name),
      data,
      min: heatmapData.stats.min_score,
      max: heatmapData.stats.max_score,
    };
  },

  // Reset store
  reset: () => {
    set({
      deployments: [],
      traits: [],
      radarData: null,
      heatmapData: null,
      selectedDeploymentIds: [],
      selectedTraitIds: [],
      isLoadingDeployments: false,
      isLoadingTraits: false,
      isLoadingRadar: false,
      isLoadingHeatmap: false,
      isInitialized: false,
      deploymentsError: null,
      traitsError: null,
      radarError: null,
      heatmapError: null,
      deploymentsPage: 1,
      deploymentsLimit: 50,
      deploymentsTotal: 0,
    });
  },
}));

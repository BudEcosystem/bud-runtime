import { create } from "zustand";
import { AppRequest } from "../pages/api/requests";
import { message } from "antd";

// Guardrail interfaces
export interface GuardrailProfile {
  id: string;
  name: string;
  description?: string;
  project_id: string;
  project_name?: string;
  status: "active" | "inactive" | "draft";
  created_at: string;
  modified_at?: string;
  created_by?: string;
  guard_types?: string[]; // Array of guard types for tags
  tags?: any;
  severity_threshold?: number;
  provider_id?: string;
  provider_name?: string;
  rules_count?: number;
  enabled_rules_count?: number;
  last_triggered_at?: string;
  trigger_count?: number;
  metadata?: Record<string, any>;
  is_standalone?: boolean; // Indicates if guardrail can be used independently
}

export interface GuardrailFilters {
  project_id?: string;
  search?: boolean;
  name?: string;
  status?: string;
  provider_id?: string;
  order_by?: string;
}

export interface PaginationState {
  page: number;
  limit: number;
  total_count: number;
  total_pages: number;
  has_more: boolean;
}

// Deployment interfaces
export interface Deployment {
  id: string;
  name: string;
  endpoint_id?: string;
  endpoint_name?: string;
  project_id?: string;
  project_name?: string;
  status: string;
  created_at: string;
  modified_at?: string;
}

export interface DeploymentFilters {
  search?: boolean;
  name?: string;
  status?: string;
  order_by?: string;
}

// Probe interfaces
export interface ProbeRule {
  id: string;
  name: string;
  description?: string;
  status: "enabled" | "disabled" | "deleted";
  guard_types?: string[];
  created_at?: string;
  modified_at?: string;
  metadata?: Record<string, any>;
}

export interface Probe {
  id: string;
  name: string;
  description?: string;
  status: "active" | "disabled" | "deleted";
  provider_id?: string;
  provider_name?: string;
  provider_type?: string;
  tags?: Array<{ name: string; color: string }>;
  is_custom?: boolean;
  created_at: string;
  modified_at?: string;
  rules?: ProbeRule[]; // Rules will be loaded on demand
}

export interface ProbeFilters {
  search?: boolean;
  name?: string;
  status?: string;
  provider_id?: string;
  order_by?: string;
}

interface GuardrailStore {
  // State
  guardrails: GuardrailProfile[];
  filters: GuardrailFilters;
  pagination: PaginationState;
  isLoading: boolean;
  error: string | null;

  // Probe state
  probes: Probe[];
  probeFilters: ProbeFilters;
  probePagination: PaginationState;
  isLoadingProbes: boolean;

  // Deployment state
  deployments: Deployment[];
  deploymentFilters: DeploymentFilters;
  deploymentPagination: PaginationState;
  isLoadingDeployments: boolean;

  // Actions
  setFilters: (filters: Partial<GuardrailFilters>) => void;
  setPagination: (pagination: Partial<PaginationState>) => void;
  resetFilters: () => void;
  setProbeFilters: (filters: Partial<ProbeFilters>) => void;
  setProbePagination: (pagination: Partial<PaginationState>) => void;
  resetProbeFilters: () => void;
  setDeploymentFilters: (filters: Partial<DeploymentFilters>) => void;
  setDeploymentPagination: (pagination: Partial<PaginationState>) => void;
  resetDeploymentFilters: () => void;

  // API calls
  fetchGuardrails: (
    projectId?: string,
    overrideFilters?: Partial<GuardrailFilters>
  ) => Promise<void>;
  deleteGuardrail: (id: string, projectId: string) => Promise<any>;
  fetchGuardrailDetail: (id: string) => Promise<void>;
  fetchProbes: (profileId: string, overrideFilters?: Partial<ProbeFilters>) => Promise<void>;
  fetchProbeRules: (
    profileId: string,
    probeId: string,
    page?: number,
    limit?: number
  ) => Promise<{ rules: ProbeRule[]; pagination: PaginationState }>;
  fetchDeployments: (
    profileId: string,
    overrideFilters?: Partial<DeploymentFilters>
  ) => Promise<void>;
  selectedGuardrail: GuardrailProfile | null;
}

// Default filters
const defaultFilters: GuardrailFilters = {
  search: false,
  status: "",
  order_by: "created_at:desc",
};

// Default probe filters
const defaultProbeFilters: ProbeFilters = {
  search: false,
  status: "",
  order_by: "created_at:desc",
};

// Default deployment filters
const defaultDeploymentFilters: DeploymentFilters = {
  search: false,
  status: "",
  order_by: "created_at:desc",
};

// Default pagination
const defaultPagination: PaginationState = {
  page: 1,
  limit: 10,
  total_count: 0,
  total_pages: 0,
  has_more: false,
};

// Utility function to parse paginated API responses
interface ParsedResponse<T> {
  items: T[];
  pagination: PaginationState;
}

function parseApiResponse<T>(
  responseData: any,
  primaryKey: string,
  fallbackPagination: PaginationState
): ParsedResponse<T> {
  // Check for primary key array (e.g., 'profiles', 'probes', 'rules')
  if (responseData[primaryKey] && Array.isArray(responseData[primaryKey])) {
    const totalCount = responseData.total_record ?? responseData.total_count ?? 0;
    const page = responseData.page ?? fallbackPagination.page;
    const limit = responseData.limit ?? fallbackPagination.limit;
    return {
      items: responseData[primaryKey],
      pagination: {
        page,
        limit,
        total_count: totalCount,
        total_pages: responseData.total_pages ?? Math.ceil(totalCount / limit),
        has_more: responseData.has_more ?? (page * limit < totalCount),
      },
    };
  }

  // Check for 'items' array (alternative structure)
  if (responseData.items && Array.isArray(responseData.items)) {
    const totalCount = responseData.total_count ?? responseData.total_record ?? 0;
    const page = responseData.page ?? fallbackPagination.page;
    const limit = responseData.limit ?? fallbackPagination.limit;
    return {
      items: responseData.items,
      pagination: {
        page,
        limit,
        total_count: totalCount,
        total_pages: responseData.total_pages ?? Math.ceil(totalCount / limit),
        has_more: responseData.has_more ?? (page * limit < totalCount),
      },
    };
  }

  // Check if response data itself is an array
  if (Array.isArray(responseData)) {
    return {
      items: responseData,
      pagination: {
        ...fallbackPagination,
        total_count: responseData.length,
        total_pages: Math.ceil(responseData.length / fallbackPagination.limit),
        has_more: false,
      },
    };
  }

  // Unexpected structure
  console.warn(`Unexpected response structure for ${primaryKey}:`, responseData);
  return {
    items: [],
    pagination: fallbackPagination,
  };
}

export const useGuardrails = create<GuardrailStore>((set, get) => ({
  // Initial state
  guardrails: [],
  selectedGuardrail: null,
  filters: defaultFilters,
  pagination: defaultPagination,
  isLoading: false,
  error: null,

  // Probe initial state
  probes: [],
  probeFilters: defaultProbeFilters,
  probePagination: defaultPagination,
  isLoadingProbes: false,

  // Deployment initial state
  deployments: [],
  deploymentFilters: defaultDeploymentFilters,
  deploymentPagination: defaultPagination,
  isLoadingDeployments: false,

  // Filter management
  setFilters: (filters) => {
    set((state) => ({
      filters: { ...state.filters, ...filters },
      pagination: { ...state.pagination, page: 1 }, // Reset to first page when filters change
    }));
  },

  setPagination: (pagination) => {
    set((state) => ({
      pagination: { ...state.pagination, ...pagination },
    }));
  },

  resetFilters: () => {
    set({
      filters: defaultFilters,
      pagination: defaultPagination,
    });
  },

  // Probe filter management
  setProbeFilters: (filters) => {
    set((state) => ({
      probeFilters: { ...state.probeFilters, ...filters },
      probePagination: { ...state.probePagination, page: 1 }, // Reset to first page when filters change
    }));
  },

  setProbePagination: (pagination) => {
    set((state) => ({
      probePagination: { ...state.probePagination, ...pagination },
    }));
  },

  resetProbeFilters: () => {
    set({
      probeFilters: defaultProbeFilters,
      probePagination: defaultPagination,
    });
  },

  // Deployment filter management
  setDeploymentFilters: (filters) => {
    set((state) => ({
      deploymentFilters: { ...state.deploymentFilters, ...filters },
      deploymentPagination: { ...state.deploymentPagination, page: 1 }, // Reset to first page when filters change
    }));
  },

  setDeploymentPagination: (pagination) => {
    set((state) => ({
      deploymentPagination: { ...state.deploymentPagination, ...pagination },
    }));
  },

  resetDeploymentFilters: () => {
    set({
      deploymentFilters: defaultDeploymentFilters,
      deploymentPagination: defaultPagination,
    });
  },

  // Fetch guardrails list
  fetchGuardrails: async (
    projectId?: string,
    overrideFilters?: Partial<GuardrailFilters>
  ) => {
    const { filters, pagination } = get();
    set({ isLoading: true, error: null });

    try {
      // Build query parameters
      const finalFilters = overrideFilters
        ? { ...filters, ...overrideFilters }
        : filters;

      const params: Record<string, string | number | boolean> = {
        page: pagination.page,
        limit: pagination.limit,
      };

      // Add optional filters
      if (projectId || finalFilters.project_id) {
        params.project_id = projectId || finalFilters.project_id;
      }

      if (finalFilters.search !== undefined) {
        params.search = finalFilters.search;
      }

      if (finalFilters.name) {
        params.name = finalFilters.name;
      }

      if (finalFilters.status) {
        params.status = finalFilters.status;
      }

      if (finalFilters.provider_id) {
        params.provider_id = finalFilters.provider_id;
      }

      if (finalFilters.order_by) {
        params.order_by = finalFilters.order_by;
      }

      const response = await AppRequest.Get("/guardrails/profiles", { params });

      if (response.data) {
        const parsed = parseApiResponse<GuardrailProfile>(response.data, "profiles", pagination);
        set({
          guardrails: parsed.items,
          pagination: parsed.pagination,
          isLoading: false,
        });
      } else {
        throw new Error("Invalid response structure");
      }
    } catch (error: any) {
      const errorMsg =
        error?.response?.data?.message ||
        error?.message ||
        "Failed to fetch guardrail profiles";
      message.error(errorMsg);
      set({ error: errorMsg, isLoading: false, guardrails: [] });
    }
  },
  deleteGuardrail: async (id: string, projectId: string): Promise<any> => {
    try {
      const response: any = await AppRequest.Delete(
        `/guardrails/profile/${id}`,
        null,
        {
          headers: {
            "x-resource-type": "project",
            "x-entity-id": projectId,
          },
        }
      );
      // successToast(response.data.message);
      return response;
    } catch (error) {
      console.error("Error deleting guardrail:", error);
    }
  },

  // Fetch guardrail detail
  fetchGuardrailDetail: async (id: string) => {
    set({ isLoading: true, error: null });
    try {
      const response = await AppRequest.Get(`/guardrails/profile/${id}`);
      if (response.data && response.data.profile) {
        set({ selectedGuardrail: response.data.profile, isLoading: false });
      } else {
        throw new Error("Invalid response structure");
      }
    } catch (error: any) {
      const errorMsg =
        error?.response?.data?.message ||
        error?.message ||
        "Failed to fetch guardrail details";
      message.error(errorMsg);
      set({ error: errorMsg, isLoading: false });
    }
  },

  // Fetch probes for a guardrail profile
  fetchProbes: async (
    profileId: string,
    overrideFilters?: Partial<ProbeFilters>
  ) => {
    const { probeFilters, probePagination } = get();
    set({ isLoadingProbes: true });

    try {
      // Build query parameters
      const finalFilters = overrideFilters
        ? { ...probeFilters, ...overrideFilters }
        : probeFilters;

      const params: Record<string, string | number | boolean> = {
        page: probePagination.page,
        limit: probePagination.limit,
      };

      // Add optional filters
      if (finalFilters.search !== undefined) {
        params.search = finalFilters.search;
      }

      if (finalFilters.name) {
        params.name = finalFilters.name;
      }

      if (finalFilters.status) {
        params.status = finalFilters.status;
      }

      if (finalFilters.provider_id) {
        params.provider_id = finalFilters.provider_id;
      }

      if (finalFilters.order_by) {
        params.order_by = finalFilters.order_by;
      }

      const response = await AppRequest.Get(`/guardrails/profile/${profileId}/probes`, { params });

      if (response.data) {
        const parsed = parseApiResponse<Probe>(response.data, "probes", probePagination);
        set({
          probes: parsed.items,
          probePagination: parsed.pagination,
          isLoadingProbes: false,
        });
      } else {
        throw new Error("Invalid response structure");
      }
    } catch (error: any) {
      const errorMsg =
        error?.response?.data?.message ||
        error?.message ||
        "Failed to fetch probes";
      message.error(errorMsg);
      set({ isLoadingProbes: false, probes: [] });
    }
  },

  // Fetch rules for a specific probe with pagination
  fetchProbeRules: async (
    profileId: string,
    probeId: string,
    page: number = 1,
    limit: number = 10
  ): Promise<{ rules: ProbeRule[]; pagination: PaginationState }> => {
    const fallbackPagination: PaginationState = { page, limit, total_count: 0, total_pages: 0, has_more: false };

    try {
      const response = await AppRequest.Get(
        `/guardrails/profile/${profileId}/probe/${probeId}/rules`,
        {
          params: {
            page,
            limit,
          }
        }
      );

      if (response.data) {
        const parsed = parseApiResponse<ProbeRule>(response.data, "rules", fallbackPagination);
        return { rules: parsed.items, pagination: parsed.pagination };
      }

      return { rules: [], pagination: fallbackPagination };
    } catch (error: any) {
      const errorMsg =
        error?.response?.data?.message ||
        error?.message ||
        "Failed to fetch probe rules";
      console.error(errorMsg, error);
      // Don't show error toast for rules fetch to avoid cluttering UI
      return { rules: [], pagination: fallbackPagination };
    }
  },

  // Fetch deployments for a guardrail profile
  fetchDeployments: async (
    profileId: string,
    overrideFilters?: Partial<DeploymentFilters>
  ) => {
    const { deploymentFilters, deploymentPagination } = get();
    set({ isLoadingDeployments: true });

    try {
      // Build query parameters
      const finalFilters = overrideFilters
        ? { ...deploymentFilters, ...overrideFilters }
        : deploymentFilters;

      const params: Record<string, string | number | boolean> = {
        page: deploymentPagination.page,
        limit: deploymentPagination.limit,
      };

      // Add optional filters
      if (finalFilters.search !== undefined) {
        params.search = finalFilters.search;
      }

      if (finalFilters.name) {
        params.name = finalFilters.name;
      }

      if (finalFilters.status) {
        params.status = finalFilters.status;
      }

      if (finalFilters.order_by) {
        params.order_by = finalFilters.order_by;
      }

      const response = await AppRequest.Get(`/guardrails/profile/${profileId}/deployments`, { params });

      if (response.data) {
        const parsed = parseApiResponse<Deployment>(response.data, "deployments", deploymentPagination);
        set({
          deployments: parsed.items,
          deploymentPagination: parsed.pagination,
          isLoadingDeployments: false,
        });
      } else {
        throw new Error("Invalid response structure");
      }
    } catch (error: any) {
      const errorMsg =
        error?.response?.data?.message ||
        error?.message ||
        "Failed to fetch deployments";
      message.error(errorMsg);
      set({ isLoadingDeployments: false, deployments: [] });
    }
  },
}));

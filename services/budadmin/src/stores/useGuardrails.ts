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

interface GuardrailStore {
  // State
  guardrails: GuardrailProfile[];
  filters: GuardrailFilters;
  pagination: PaginationState;
  isLoading: boolean;
  error: string | null;

  // Actions
  setFilters: (filters: Partial<GuardrailFilters>) => void;
  setPagination: (pagination: Partial<PaginationState>) => void;
  resetFilters: () => void;
  // API calls
  fetchGuardrails: (
    projectId?: string,
    overrideFilters?: Partial<GuardrailFilters>
  ) => Promise<void>;
  deleteGuardrail: (id: string, projectId: string) => Promise<any>;
  fetchGuardrailDetail: (id: string) => Promise<void>;
  selectedGuardrail: GuardrailProfile | null;
}

// Default filters
const defaultFilters: GuardrailFilters = {
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

export const useGuardrails = create<GuardrailStore>((set, get) => ({
  // Initial state
  guardrails: [],
  selectedGuardrail: null,
  filters: defaultFilters,
  pagination: defaultPagination,
  isLoading: false,
  error: null,

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

      const params: any = {
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
        // Check if response has profiles array (actual API response structure)
        if (response.data.profiles && Array.isArray(response.data.profiles)) {
          const data = response.data;
          console.log("Fetched guardrails data:", data);
          set({
            guardrails: data.profiles,
            pagination: {
              page: data.page || pagination.page,
              limit: data.limit || pagination.limit,
              total_count: data.total_record || 0,
              total_pages: data.total_pages || Math.ceil((data.total_record || 0) / pagination.limit),
              has_more: (data.page * data.limit < data.total_record) || false,
            },
            isLoading: false,
          });
        }
        // Check if response has items array (alternative structure)
        else if (response.data.items && Array.isArray(response.data.items)) {
          const data = response.data;
          set({
            guardrails: data.items,
            pagination: {
              page: data.page || pagination.page,
              limit: data.limit || pagination.limit,
              total_count: data.total_count || 0,
              total_pages: data.total_pages || Math.ceil((data.total_count || 0) / pagination.limit),
              has_more: data.has_more || (data.page * data.limit < data.total_count),
            },
            isLoading: false,
          });
        }
        // Check if response data itself is an array
        else if (Array.isArray(response.data)) {
          set({
            guardrails: response.data,
            pagination: {
              ...pagination,
              total_count: response.data.length,
              total_pages: Math.ceil(response.data.length / pagination.limit),
              has_more: false,
            },
            isLoading: false,
          });
        }
        // Handle unexpected response structure
        else {
          console.warn("Unexpected response structure for guardrails:", response.data);
          set({
            guardrails: [],
            isLoading: false,
          });
        }
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
}));

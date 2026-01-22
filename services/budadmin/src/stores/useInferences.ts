import { create } from "zustand";
import { AppRequest } from "../pages/api/requests";
import { message } from "antd";
import { errorToast } from "@/components/toast";

// Gateway metadata interfaces for components
export interface RequestMetadata {
  client_ip?: string | null;
  proxy_chain?: string | null;
  protocol_version?: string | null;
  method?: string | null;
  path?: string | null;
  query_params?: string | null;
  request_headers?: Record<string, string> | null;
  body_size?: number | null;
  api_key_id?: string | null;
  auth_method?: string | null;
  user_id?: string | null;
  gateway_processing_ms?: number;
  total_duration_ms?: number;
  status_code?: number;
  response_size?: number | null;
  response_headers?: Record<string, string> | null;
}

export interface ClientInfo {
  user_agent?: string | null;
  device_type?: string | null;
  browser_name?: string | null;
  browser_version?: string | null;
  os_name?: string | null;
  os_version?: string | null;
  is_bot?: boolean;
}

export interface GeographicInfo {
  country_code?: string | null;
  country_name?: string | null;
  region?: string | null;
  city?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  timezone?: string | null;
  asn?: number | null;
  isp?: string | null;
}

export interface GatewayMetadata {
  // Network & Request Info
  client_ip?: string | null;
  proxy_chain?: string | null;
  protocol_version?: string | null;
  method?: string | null;
  path?: string | null;
  query_params?: string | null;
  request_headers?: Record<string, string> | null;
  body_size?: number | null;

  // Authentication
  api_key_id?: string | null;
  auth_method?: string | null;
  user_id?: string | null;

  // Client Information
  user_agent?: string | null;
  device_type?: string | null;
  browser_name?: string | null;
  browser_version?: string | null;
  os_name?: string | null;
  os_version?: string | null;
  is_bot?: boolean;

  // Geographic Information
  country_code?: string | null;
  country_name?: string | null;
  region?: string | null;
  city?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  timezone?: string | null;
  asn?: number | null;
  isp?: string | null;

  // Performance Metrics
  gateway_processing_ms?: number;
  total_duration_ms?: number;
  status_code?: number;
  response_size?: number | null;
  response_headers?: Record<string, string> | null;

  // Model & Routing
  routing_decision?: string | null;
  model_version?: string | null;

  // Error Information
  error_type?: string | null;
  error_message?: string | null;

  // Blocking Information
  is_blocked?: boolean;
  block_reason?: string | null;
  block_rule_id?: string | null;

  // Additional
  tags?: Record<string, string> | null;
}

export interface InferenceListItem {
  inference_id: string;
  timestamp: string;
  model_name: string;
  model_display_name?: string;
  project_name?: string;
  endpoint_name?: string;
  prompt_preview: string;
  response_preview: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  response_time_ms: number;
  cost?: number;
  is_success: boolean;
  cached: boolean;
  endpoint_type?: string;
}

export interface InferenceDetail {
  inference_id: string;
  timestamp: string;

  // Model info
  model_name: string;
  model_display_name?: string;
  model_provider: string;
  model_id: string;

  // Project/Endpoint info
  project_id: string;
  project_name?: string;
  endpoint_id: string;
  endpoint_name?: string;

  // Content
  system_prompt?: string;
  messages: Array<{ [key: string]: any }>;
  output: string;

  // Metadata
  function_name?: string;
  variant_name?: string;
  episode_id?: string;

  // Performance
  input_tokens: number;
  output_tokens: number;
  response_time_ms: number;
  ttft_ms?: number;
  processing_time_ms?: number;

  // Request details
  request_ip?: string;
  request_arrival_time: string;
  request_forward_time: string;

  // Status
  is_success: boolean;
  cached: boolean;
  finish_reason?: string;
  cost?: number;
  endpoint_type?: string;

  // Error details
  error_code?: string;
  error_message?: string;
  error_type?: string;
  status_code?: number;

  // Raw data
  raw_request?: string;
  raw_response?: string;

  // Gateway data (optional)
  gateway_request?: any;
  gateway_response?: any;
  gateway_metadata?: GatewayMetadata;

  // Feedback summary
  feedback_count: number;
  average_rating?: number;
}

export interface FeedbackItem {
  feedback_id: string;
  feedback_type: "boolean" | "float" | "comment" | "demonstration";
  metric_name?: string;
  value?: boolean | number | string;
  created_at: string;
}

export interface InferenceFilters {
  project_id?: string;
  endpoint_id?: string;
  model_id?: string;
  from_date: string;
  to_date?: string;
  is_success?: boolean;
  min_tokens?: number;
  max_tokens?: number;
  max_latency_ms?: number;
  endpoint_type?:
    | "chat"
    | "embedding"
    | "audio_transcription"
    | "audio_translation"
    | "text_to_speech"
    | "image_generation"
    | "moderation";
  sort_by: "timestamp" | "tokens" | "latency" | "cost";
  sort_order: "asc" | "desc";
}

export interface PaginationState {
  offset: number;
  limit: number;
  total_count: number;
  has_more: boolean;
}

interface InferenceStore {
  // State
  inferences: InferenceListItem[];
  selectedInference: InferenceDetail | null;
  inferenceFeedback: FeedbackItem[];
  filters: InferenceFilters;
  pagination: PaginationState;
  isLoading: boolean;
  isLoadingDetail: boolean;
  isLoadingFeedback: boolean;
  error: string | null;

  // Actions
  setFilters: (filters: Partial<InferenceFilters>) => void;
  setPagination: (pagination: Partial<PaginationState>) => void;
  resetFilters: () => void;

  // API calls
  fetchInferences: (
    projectId?: string,
    overrideFilters?: Partial<InferenceFilters>,
  ) => Promise<void>;
  fetchInferenceDetail: (inferenceId: string) => Promise<void>;
  fetchInferenceFeedback: (inferenceId: string) => Promise<void>;
  exportInferences: (format: "csv" | "json") => Promise<void>;

  // UI actions
  clearSelectedInference: () => void;
}

// Default filters
const defaultFilters: InferenceFilters = {
  from_date: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(), // Last 30 days
  sort_by: "timestamp",
  sort_order: "desc",
};

// Default pagination
const defaultPagination: PaginationState = {
  offset: 0,
  limit: 50,
  total_count: 0,
  has_more: false,
};

export const useInferences = create<InferenceStore>((set, get) => ({
  // Initial state
  inferences: [],
  selectedInference: null,
  inferenceFeedback: [],
  filters: defaultFilters,
  pagination: defaultPagination,
  isLoading: false,
  isLoadingDetail: false,
  isLoadingFeedback: false,
  error: null,

  // Filter management
  setFilters: (filters) => {
    set((state) => ({
      filters: { ...state.filters, ...filters },
      pagination: { ...state.pagination, offset: 0 }, // Reset offset when filters change
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

  // Fetch inferences list
  fetchInferences: async (
    projectId?: string,
    overrideFilters?: Partial<InferenceFilters>,
  ) => {
    const { filters, pagination } = get();
    set({ isLoading: true, error: null });

    try {
      // Use override filters if provided, otherwise use store filters
      const finalFilters = overrideFilters
        ? { ...filters, ...overrideFilters }
        : filters;

      const requestBody = {
        ...finalFilters,
        project_id: projectId || finalFilters.project_id,
        offset: pagination.offset,
        limit: pagination.limit,
      };

      const response = await AppRequest.Post(
        "/metrics/inferences/list",
        requestBody,
      );

      // Check if response is successful (could be 200 or undefined)
      if (response.data && response.data.items) {
        const data = response.data;

        set({
          inferences: data.items,
          pagination: {
            offset: data.offset || 0,
            limit: data.limit || 50,
            total_count: data.total_count || 0,
            has_more: data.has_more || false,
          },
          isLoading: false,
        });
      } else {
        throw new Error(response.data?.message || "Failed to fetch inferences");
      }
    } catch (error: any) {
      const errorMsg =
        error?.response?.data?.message ||
        error?.message ||
        "Failed to fetch inferences";
      errorToast(errorMsg);
      set({ error: errorMsg, isLoading: false });
    }
  },

  // Fetch inference detail
  fetchInferenceDetail: async (inferenceId: string) => {
    set({ isLoadingDetail: true, error: null });

    try {
      const response = await AppRequest.Get(
        `/metrics/inferences/${inferenceId}`,
      );

      if (response.data.code === 200) {
        set({
          selectedInference: response.data,
          isLoadingDetail: false,
        });
      } else {
        throw new Error(
          response.data.message || "Failed to fetch observability details",
        );
      }
    } catch (error: any) {
      const errorMsg =
        error?.response?.data?.message ||
        error?.message ||
        "Failed to fetch observability details";
      errorToast(errorMsg);
      set({ error: errorMsg, isLoadingDetail: false });
    }
  },

  // Fetch inference feedback
  fetchInferenceFeedback: async (inferenceId: string) => {
    set({ isLoadingFeedback: true, error: null });

    try {
      const response = await AppRequest.Get(
        `/metrics/inferences/${inferenceId}/feedback`,
      );

      if (response.data.code === 200) {
        set({
          inferenceFeedback: response.data.feedback_items || [],
          isLoadingFeedback: false,
        });
      } else {
        throw new Error(
          response.data.message || "Failed to fetch inference feedback",
        );
      }
    } catch (error: any) {
      const errorMsg =
        error?.response?.data?.message ||
        error?.message ||
        "Failed to fetch inference feedback";
      errorToast(errorMsg);
      set({ error: errorMsg, isLoadingFeedback: false });
    }
  },

  // Export inferences
  exportInferences: async (format: "csv" | "json") => {
    const { inferences } = get();

    if (!inferences || inferences.length === 0) {
      message.warning("No data to export");
      return;
    }

    try {
      let content: string;
      let filename: string;
      let mimeType: string;

      if (format === "csv") {
        // Convert to CSV
        const headers = [
          "Inference ID",
          "Timestamp",
          "Model Name",
          "Project",
          "Endpoint",
          "Input Tokens",
          "Output Tokens",
          "Total Tokens",
          "Response Time (ms)",
          "Cost",
          "Success",
          "Cached",
        ];

        const rows = inferences.map((item) => [
          item.inference_id,
          item.timestamp,
          item.model_display_name || item.model_name,
          item.project_name || "",
          item.endpoint_name || "",
          item.input_tokens,
          item.output_tokens,
          item.total_tokens,
          item.response_time_ms,
          item.cost || "",
          item.is_success ? "Yes" : "No",
          item.cached ? "Yes" : "No",
        ]);

        content = [headers, ...rows].map((row) => row.join(",")).join("\n");
        filename = `inferences_${new Date().toISOString().split("T")[0]}.csv`;
        mimeType = "text/csv";
      } else {
        // Export as JSON
        content = JSON.stringify(inferences, null, 2);
        filename = `inferences_${new Date().toISOString().split("T")[0]}.json`;
        mimeType = "application/json";
      }

      // Create blob and download
      const blob = new Blob([content], { type: mimeType });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);

      message.success(
        `Exported ${inferences.length} inferences to ${format.toUpperCase()}`,
      );
    } catch (error: any) {
      errorToast("Failed to export data");
      console.error("Export error:", error);
    }
  },

  // Clear selected inference
  clearSelectedInference: () => {
    set({
      selectedInference: null,
      inferenceFeedback: [],
    });
  },
}));

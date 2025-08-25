import { create } from "zustand";
import { AppRequest } from "src/pages/api/requests";
import { errorToast } from "@/components/toast";

interface ProbeTag {
  name: string;
  color: string;
}

interface Probe {
  id: string;
  name: string;
  description: string;
  tags: ProbeTag[];
  provider_id: string;
  provider_name: string;
  provider_type: string;
  is_custom: boolean;
  rule_count: number;
  object: string;
}

interface ProbeRule {
  id: string;
  probe_id: string;
  name: string;
  description: string;
  scanner_types: string[];
  modality_types: string[];
  guard_types: string[];
  examples: string[];
  configuration: any;
  is_enabled: boolean;
  is_custom: boolean;
  created_at: string;
  modified_at: string;
  object: string;
}

interface ProbesResponse {
  object: string;
  message: string;
  page: number;
  limit: number;
  total_record: number;
  probes: Probe[];
  total_pages: number;
}

interface GuardrailsWorkflow {
  workflow_id: string;
  step_number: number;
  workflow_total_steps: number;
  provider_id?: string;
  probe_selections?: Array<{
    probe_id: string;
    enabled: boolean;
    rule_selections?: string[];
  }>;
  deployment_type?: string;
  project_id?: string;
  endpoint_id?: string;
  guard_types?: string[];
  threshold?: number;
  [key: string]: any;
}

interface GuardrailsState {
  // Probes state
  probes: Probe[];
  probesLoading: boolean;
  probesError: string | null;
  totalProbes: number;
  currentPage: number;
  pageSize: number;
  totalPages: number;

  // Filters
  searchTerm: string;
  selectedTags: string[];
  selectedProviderId: string | null;
  selectedProviderType: string | null;

  // Actions
  fetchProbes: (params?: {
    tags?: string[];
    provider_id?: string;
    provider_type?: string;
    user_id?: string;
    project_id?: string;
    endpoint_id?: string;
    search?: string;
    page?: number;
    page_size?: number;
  }) => Promise<void>;

  setSearchTerm: (search: string) => void;
  setSelectedTags: (tags: string[]) => void;
  setCurrentPage: (page: number) => void;
  setPageSize: (size: number) => void;
  resetFilters: () => void;

  // Single probe
  selectedProbe: Probe | null;
  fetchProbeById: (id: string) => Promise<void>;
  setSelectedProbe: (probe: Probe | null) => void;
  clearSelectedProbe: () => void;

  // Selected project for guardrail deployment
  selectedProject: any | null;
  setSelectedProject: (project: any | null) => void;

  // Selected deployment for guardrail
  selectedDeployment: any | null;
  setSelectedDeployment: (deployment: any | null) => void;

  // Workflow state
  currentWorkflow: GuardrailsWorkflow | null;
  workflowLoading: boolean;
  workflowError: string | null;

  // Workflow actions
  createWorkflow: (providerId: string) => Promise<void>;
  updateWorkflow: (data: Partial<GuardrailsWorkflow>) => Promise<void>;
  getWorkflow: (workflowId?: string) => Promise<void>;
  clearWorkflow: () => void;

  // Probe rules
  probeRules: ProbeRule[];
  rulesLoading: boolean;
  rulesError: string | null;
  totalRules: number;
  fetchProbeRules: (
    probeId: string,
    params?: {
      page?: number;
      limit?: number;
      search?: string;
      is_enabled?: boolean;
    },
  ) => Promise<void>;
  clearProbeRules: () => void;
}

const useGuardrails = create<GuardrailsState>((set, get) => ({
  // Initial state
  probes: [],
  probesLoading: false,
  probesError: null,
  totalProbes: 0,
  currentPage: 1,
  pageSize: 20,
  totalPages: 0,

  searchTerm: "",
  selectedTags: [],
  selectedProviderId: null,
  selectedProviderType: null,

  selectedProbe: null,
  selectedProject: null,
  selectedDeployment: null,

  // Workflow state
  currentWorkflow: null,
  workflowLoading: false,
  workflowError: null,

  // Probe rules state
  probeRules: [],
  rulesLoading: false,
  rulesError: null,
  totalRules: 0,

  // Fetch probes with filtering and pagination
  fetchProbes: async (params) => {
    set({ probesLoading: true, probesError: null });

    try {
      const queryParams: any = {
        page: params?.page || get().currentPage,
        page_size: params?.page_size || get().pageSize,
      };

      // Add optional filters
      if (params?.tags && params.tags.length > 0) {
        queryParams.tags = params.tags.join(",");
      }
      if (params?.provider_id) {
        queryParams.provider_id = params.provider_id;
      }
      if (params?.provider_type) {
        queryParams.provider_type = params.provider_type;
      }
      if (params?.user_id) {
        queryParams.user_id = params.user_id;
      }
      if (params?.project_id) {
        queryParams.project_id = params.project_id;
      }
      if (params?.endpoint_id) {
        queryParams.endpoint_id = params.endpoint_id;
      }
      if (params?.search) {
        queryParams.search = params.search;
      }

      const response = await AppRequest.Get("/guardrails/probes", {
        params: queryParams,
      });

      if (response.data) {
        const data: ProbesResponse = response.data;
        set({
          probes: data.probes || [],
          totalProbes: data.total_record || 0,
          currentPage: data.page || 1,
          totalPages: data.total_pages || 0,
          probesLoading: false,
        });
      }
    } catch (error: any) {
      errorToast(error?.message || "Failed to fetch probes");
      set({
        probesError: error?.message || "Failed to fetch probes",
        probesLoading: false,
        probes: [],
      });
    }
  },

  // Fetch single probe by ID
  fetchProbeById: async (id: string) => {
    set({ probesLoading: true, probesError: null });

    try {
      const response = await AppRequest.Get(`/guardrails/probes/${id}`);

      if (response.data) {
        set({
          selectedProbe: response.data.probe || response.data,
          probesLoading: false,
        });
      }
    } catch (error: any) {
      errorToast(error?.message || "Failed to fetch probe details");
      set({
        probesError: error?.message || "Failed to fetch probe details",
        probesLoading: false,
        selectedProbe: null,
      });
    }
  },

  // Set search term
  setSearchTerm: (search: string) => {
    set({ searchTerm: search });
  },

  // Set selected tags
  setSelectedTags: (tags: string[]) => {
    set({ selectedTags: tags });
  },

  // Set current page
  setCurrentPage: (page: number) => {
    set({ currentPage: page });
  },

  // Set page size
  setPageSize: (size: number) => {
    set({ pageSize: size });
  },

  // Reset filters
  resetFilters: () => {
    set({
      searchTerm: "",
      selectedTags: [],
      selectedProviderId: null,
      selectedProviderType: null,
      currentPage: 1,
    });
  },

  // Set selected probe
  setSelectedProbe: (probe: Probe | null) => {
    set({ selectedProbe: probe });
  },

  // Clear selected probe
  clearSelectedProbe: () => {
    set({ selectedProbe: null });
  },

  // Set selected project
  setSelectedProject: (project: any | null) => {
    set({ selectedProject: project });
  },

  // Set selected deployment
  setSelectedDeployment: (deployment: any | null) => {
    set({ selectedDeployment: deployment });
  },

  // Create workflow
  createWorkflow: async (providerId: string) => {
    set({ workflowLoading: true, workflowError: null });

    try {
      const response = await AppRequest.Post(
        "/guardrails/deployment-workflow",
        {
          provider_id: providerId,
          step_number: 1,
          workflow_total_steps: 6,
          trigger_workflow: false,
        },
      );

      if (response.data) {
        set({
          currentWorkflow: response.data,
          workflowLoading: false,
        });
      }
    } catch (error: any) {
      errorToast(error?.message || "Failed to create workflow");
      set({
        workflowError: error?.message || "Failed to create workflow",
        workflowLoading: false,
        currentWorkflow: null,
      });
    }
  },

  // Update workflow
  updateWorkflow: async (data: Partial<GuardrailsWorkflow>) => {
    const currentWorkflow = get().currentWorkflow;
    if (!currentWorkflow?.workflow_id) {
      errorToast("No active workflow found");
      return;
    }

    set({ workflowLoading: true, workflowError: null });

    try {
      const payload = {
        workflow_id: currentWorkflow.workflow_id,
        ...data,
      };

      const response = await AppRequest.Post(
        "/guardrails/deployment-workflow",
        payload,
      );

      if (response.data) {
        set({
          currentWorkflow: response.data,
          workflowLoading: false,
        });
      }
    } catch (error: any) {
      errorToast(error?.message || "Failed to update workflow");
      set({
        workflowError: error?.message || "Failed to update workflow",
        workflowLoading: false,
      });
    }
  },

  // Get workflow
  getWorkflow: async (workflowId?: string) => {
    const id = workflowId || get().currentWorkflow?.workflow_id;
    if (!id) {
      return;
    }

    set({ workflowLoading: true, workflowError: null });

    try {
      const response = await AppRequest.Get(
        `/guardrails/deployment-workflow/${id}`,
      );

      if (response.data) {
        set({
          currentWorkflow: response.data,
          workflowLoading: false,
        });
      }
    } catch (error: any) {
      errorToast(error?.message || "Failed to fetch workflow");
      set({
        workflowError: error?.message || "Failed to fetch workflow",
        workflowLoading: false,
      });
    }
  },

  // Clear workflow
  clearWorkflow: () => {
    set({
      currentWorkflow: null,
      workflowError: null,
      selectedProbe: null,
      selectedProject: null,
      selectedDeployment: null,
    });
  },

  // Fetch probe rules
  fetchProbeRules: async (probeId: string, params) => {
    set({ rulesLoading: true, rulesError: null });

    try {
      const queryParams: any = {
        page: params?.page || 1,
        limit: params?.limit || 100, // Get all rules by default
      };

      // Add optional filters
      if (params?.search) {
        queryParams.search = params.search;
      }
      if (params?.is_enabled !== undefined) {
        queryParams.is_enabled = params.is_enabled;
      }

      const response = await AppRequest.Get(
        `/guardrails/probes/${probeId}/rules`,
        {
          params: queryParams,
        },
      );

      if (response.data) {
        set({
          probeRules: response.data.rules || [],
          totalRules: response.data.total_record || 0,
          rulesLoading: false,
        });
      }
    } catch (error: any) {
      errorToast(error?.message || "Failed to fetch probe rules");
      set({
        rulesError: error?.message || "Failed to fetch probe rules",
        rulesLoading: false,
        probeRules: [],
      });
    }
  },

  // Clear probe rules
  clearProbeRules: () => {
    set({ probeRules: [], totalRules: 0, rulesError: null });
  },
}));

export default useGuardrails;
export type { Probe, ProbeTag, ProbesResponse, ProbeRule, GuardrailsWorkflow };

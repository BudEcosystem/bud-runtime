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
    id: string;
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

  // Step data management (similar to useModels)
  selectedProvider: any | null;
  setSelectedProvider: (provider: any) => void;

  // Actions
  fetchProbes: (params?: {
    tags?: string[];
    provider_id?: string;
    provider_type?: string;
    user_id?: string;
    project_id?: string;
    endpoint_id?: string;
    search?: boolean;
    name?: string;
    page?: number;
    limit?: number;
    append?: boolean;
  }) => Promise<void>;

  setSearchTerm: (search: string) => void;
  setSelectedTags: (tags: string[]) => void;
  setCurrentPage: (page: number) => void;
  setPageSize: (size: number) => void;
  resetFilters: () => void;

  // Single probe
  selectedProbe: Probe | null;
  selectedProbes: Probe[]; // Multiple selected probes
  fetchProbeById: (id: string) => Promise<void>;
  setSelectedProbe: (probe: Probe | null) => void;
  setSelectedProbes: (probes: Probe[]) => void;
  clearSelectedProbe: () => void;

  // Selected project for guardrail deployment
  selectedProject: any | null;
  setSelectedProject: (project: any | null) => void;

  // Selected deployment for guardrail
  selectedDeployment: any | null;
  setSelectedDeployment: (deployment: any | null) => void;

  // Deployment type flag (true for guardrail-endpoint, false for existing-deployment)
  isStandaloneDeployment: boolean;
  setIsStandaloneDeployment: (value: boolean) => void;

  // Workflow state
  currentWorkflow: GuardrailsWorkflow | null;
  workflowLoading: boolean;
  workflowError: string | null;

  // Workflow actions
  createWorkflow: (providerId: string, providerType?: string) => Promise<void>;
  updateWorkflow: (data: Partial<GuardrailsWorkflow>) => Promise<boolean>;
  getWorkflow: (workflowId?: string) => Promise<void>;
  clearWorkflow: () => void;

  // Custom probe workflow
  customProbePolicy: any | null;
  setCustomProbePolicy: (policy: any) => void;
  createCustomProbeWorkflow: (probeTypeOption: string) => Promise<boolean>;
  updateCustomProbeWorkflow: (data: Record<string, any>) => Promise<boolean>;

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
  pageSize: 10,
  totalPages: 0,

  searchTerm: "",
  selectedTags: [],
  selectedProviderId: null,
  selectedProviderType: null,

  selectedProbe: null,
  selectedProbes: [], // Initialize empty array for multiple probes
  selectedProject: null,
  selectedDeployment: null,
  isStandaloneDeployment: false, // Default to existing-deployment flow

  // Step data management
  selectedProvider: null,

  // Workflow state
  currentWorkflow: null,
  workflowLoading: false,
  workflowError: null,
  customProbePolicy: null,

  // Probe rules state
  probeRules: [],
  rulesLoading: false,
  rulesError: null,
  totalRules: 0,

  // Fetch probes with filtering and pagination
  fetchProbes: async (params) => {
    const isAppend = params?.append === true;
    set({ probesLoading: !isAppend, probesError: null });

    try {
      const queryParams: any = {
        page: params?.page || get().currentPage,
        limit: params?.limit || get().pageSize,
      };

      // Add optional filters
      if (params?.tags && params.tags.length > 0) {
        queryParams.tags = params.tags.join(",");
      }

      // Use provider_id from params or from selectedProvider in store
      const providerId = params?.provider_id || get().selectedProvider?.id;
      if (providerId) {
        queryParams.provider_id = providerId;
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
      // search is a boolean flag, name is the search text
      if (params?.search) {
        queryParams.search = true;
      }
      if (params?.name) {
        queryParams.name = params.name;
      }
      const response = await AppRequest.Get("/guardrails/probes", {
        params: queryParams,
      });

      if (response.data) {
        const data: ProbesResponse = response.data;
        const newProbes = data.probes || [];
        set({
          probes: isAppend ? [...get().probes, ...newProbes] : newProbes,
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
        ...(isAppend ? {} : { probes: [] }),
      });
    }
  },

  // Fetch single probe by ID
  fetchProbeById: async (id: string) => {
    set({ probesLoading: true, probesError: null });

    try {
      const response = await AppRequest.Get(`/guardrails/probe/${id}`);

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

  // Set multiple selected probes
  setSelectedProbes: (probes: Probe[]) => {
    set({ selectedProbes: probes });
  },

  // Clear selected probe
  clearSelectedProbe: () => {
    set({ selectedProbe: null, selectedProbes: [] });
  },

  // Set selected project
  setSelectedProject: (project: any | null) => {
    set({ selectedProject: project });
  },

  // Set selected deployment
  setSelectedDeployment: (deployment: any | null) => {
    set({ selectedDeployment: deployment });
  },

  // Set standalone deployment flag
  setIsStandaloneDeployment: (value: boolean) => {
    set({ isStandaloneDeployment: value });
  },

  // Set selected provider (for step data management)
  setSelectedProvider: (provider: any) => {
    set({ selectedProvider: provider });
  },

  // Create workflow
  createWorkflow: async (providerId: string, providerType?: string) => {
    set({ workflowLoading: true, workflowError: null });

    try {
      const response = await AppRequest.Post(
        "/guardrails/deploy-workflow",
        {
          provider_id: providerId,
          provider_type: providerType,
          step_number: 1,
          workflow_total_steps: 10,
          trigger_workflow: false,
        },
      );

      if (response.data) {
        set({
          currentWorkflow: response.data,
        });

        // Fetch the workflow data after creation
        await get().getWorkflow(response.data.workflow_id);
      }
    } catch (error: any) {
      errorToast(error?.message || "Failed to create workflow");
      set({
        workflowError: error?.message || "Failed to create workflow",
        workflowLoading: false,
        currentWorkflow: null,
      });
    } finally {
      // Ensure workflowLoading is always set to false
      set({ workflowLoading: false });
    }
  },

  // Update workflow - returns true on success, false on failure
  updateWorkflow: async (data: Partial<GuardrailsWorkflow>): Promise<boolean> => {
    const currentWorkflow = get().currentWorkflow;
    if (!currentWorkflow?.workflow_id) {
      console.error("updateWorkflow: No active workflow found");
      errorToast("No active workflow found");
      return false;
    }

    set({ workflowLoading: true, workflowError: null });

    try {
      const payload = {
        workflow_id: currentWorkflow.workflow_id,
        ...data,
      };

      console.log("updateWorkflow: Sending request to /guardrails/deploy-workflow");
      const response = await AppRequest.Post(
        "/guardrails/deploy-workflow",
        payload,
      );

      console.log("updateWorkflow: Response received:", {
        status: response?.status,
        hasData: !!response?.data,
        dataKeys: response?.data ? Object.keys(response.data) : []
      });

      // Check for successful response (status 200-299)
      if (response && response.status >= 200 && response.status < 300 && response.data) {
        set({
          currentWorkflow: response.data,
        });

        // Fetch the workflow data after update
        await get().getWorkflow(currentWorkflow.workflow_id);

        console.log("updateWorkflow: ✅ Success with status:", response.status);
        // Return true to indicate success
        return true;
      }

      // If we get here, something went wrong
      const errorMsg = response?.data?.detail || response?.data?.message || "No response data from workflow update";
      console.error("updateWorkflow: ❌ Failed:", errorMsg, "Status:", response?.status);
      errorToast(errorMsg);
      set({ workflowLoading: false });
      return false;
    } catch (error: any) {
      console.error("updateWorkflow: Caught error:", error);

      const errorMessage = error?.response?.data?.detail ||
                          error?.response?.data?.message ||
                          error?.message ||
                          "Failed to update workflow";

      console.error("updateWorkflow: ❌ Error message:", errorMessage);
      errorToast(errorMessage);

      set({
        workflowError: errorMessage,
        workflowLoading: false,
      });

      // Always return false on error
      return false;
    } finally {
      // Ensure workflowLoading is always set to false
      set({ workflowLoading: false });
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
        `/workflows/${id}`,
      );

      if (response.data) {
        set({
          currentWorkflow: response.data,
        });
      }
    } catch (error: any) {
      errorToast(error?.message || "Failed to fetch workflow");
      set({
        workflowError: error?.message || "Failed to fetch workflow",
      });
    } finally {
      // Ensure workflowLoading is always set to false
      set({ workflowLoading: false });
    }
  },

  // Set custom probe policy
  setCustomProbePolicy: (policy: any) => {
    set({ customProbePolicy: policy });
  },

  // Create custom probe workflow (step 1)
  createCustomProbeWorkflow: async (probeTypeOption: string): Promise<boolean> => {
    set({ workflowLoading: true, workflowError: null });

    try {
      const response = await AppRequest.Post(
        "/guardrails/custom-probe-workflow",
        {
          workflow_total_steps: 3,
          step_number: 1,
          trigger_workflow: false,
          probe_type_option: probeTypeOption,
        },
      );

      if (response && response.status >= 200 && response.status < 300 && response.data) {
        set({ currentWorkflow: response.data });

        // Fetch the workflow data after creation
        await get().getWorkflow(response.data.workflow_id);

        return true;
      }

      const errorMsg = response?.data?.detail || response?.data?.message || "Failed to create custom probe workflow";
      errorToast(errorMsg);
      return false;
    } catch (error: any) {
      const errorMessage = error?.response?.data?.detail ||
                          error?.response?.data?.message ||
                          error?.message ||
                          "Failed to create custom probe workflow";
      errorToast(errorMessage);
      set({ workflowError: errorMessage });
      return false;
    } finally {
      set({ workflowLoading: false });
    }
  },

  // Update custom probe workflow (steps 2 & 3)
  updateCustomProbeWorkflow: async (data: Record<string, any>): Promise<boolean> => {
    const currentWorkflow = get().currentWorkflow;
    if (!currentWorkflow?.workflow_id) {
      errorToast("No active workflow found");
      return false;
    }

    set({ workflowLoading: true, workflowError: null });

    try {
      const payload = {
        workflow_id: currentWorkflow.workflow_id,
        ...data,
      };

      const response = await AppRequest.Post(
        "/guardrails/custom-probe-workflow",
        payload,
      );

      if (response && response.status >= 200 && response.status < 300 && response.data) {
        set({ currentWorkflow: response.data });

        // Fetch the workflow data after update
        await get().getWorkflow(currentWorkflow.workflow_id);

        return true;
      }

      const errorMsg = response?.data?.detail || response?.data?.message || "Failed to update custom probe workflow";
      errorToast(errorMsg);
      return false;
    } catch (error: any) {
      const errorMessage = error?.response?.data?.detail ||
                          error?.response?.data?.message ||
                          error?.message ||
                          "Failed to update custom probe workflow";
      errorToast(errorMessage);
      set({ workflowError: errorMessage });
      return false;
    } finally {
      set({ workflowLoading: false });
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
      selectedProvider: null,
      isStandaloneDeployment: false,
      customProbePolicy: null,
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
        `/guardrails/probe/${probeId}/rules`,
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

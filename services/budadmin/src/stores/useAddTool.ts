import { create } from "zustand";
import { AppRequest } from "src/pages/api/requests";
import { Tool, McpToolResponse } from "./useTools";

// Tool source types matching backend enum
export enum ToolSourceType {
  OPENAPI_URL = "openapi_url",
  OPENAPI_FILE = "openapi_file",
  API_DOCS_URL = "api_docs_url",
  API_DOCS_FILE = "api_docs_file",
  BUD_CATALOGUE = "bud_catalogue",
}

// Catalogue server from MCP registry
export interface CatalogueServer {
  id: string;
  name: string;
  description?: string;
  icon?: string;
  url?: string;
  transport?: string;
  isRegistered?: boolean;
  toolsCount?: number;
}

// Workflow response from API
export interface WorkflowResponse {
  workflow_id: string;
  current_step: number;
  total_steps: number;
  status: string;
  step_data?: Record<string, any>;
}

// Created tools response
export interface CreatedToolsResponse {
  tools: McpToolResponse[];
  gateway_id?: string;
}

// Virtual server response
export interface VirtualServerResponse {
  virtual_server_id: string;
  name: string;
  tool_count: number;
}

// Notification event for progress tracking
export interface ToolCreationEvent {
  title: string;
  message: string;
  status: "pending" | "in_progress" | "completed" | "failed";
  timestamp: Date;
  result?: Record<string, any>;
}

interface AddToolState {
  // Workflow state
  workflowId: string | null;
  currentStep: number;
  totalSteps: number;
  status: string;

  // Step 1: Source selection
  sourceType: ToolSourceType | null;

  // Step 2: Configuration
  openApiUrl: string;
  apiDocsUrl: string;
  enhanceWithAi: boolean;
  uploadedFile: File | null;
  uploadedFileName: string;

  // Catalogue servers
  catalogueServers: CatalogueServer[];
  selectedCatalogueServerIds: string[];

  // Step 3: Progress/Events
  creationEvents: ToolCreationEvent[];
  isCreating: boolean;

  // Step 4: Created tools
  createdTools: Tool[];
  selectedToolIds: string[];
  gatewayId: string | null;

  // Step 5: Virtual server
  virtualServerName: string;
  virtualServerId: string | null;

  // Loading/Error states
  isLoading: boolean;
  error: string | null;

  // Actions - Source selection
  setSourceType: (sourceType: ToolSourceType) => void;

  // Actions - Configuration
  setOpenApiUrl: (url: string) => void;
  setApiDocsUrl: (url: string) => void;
  setEnhanceWithAi: (enhance: boolean) => void;
  setUploadedFile: (file: File | null) => void;

  // Actions - Catalogue
  fetchCatalogueServers: (offset?: number, limit?: number) => Promise<void>;
  toggleCatalogueServer: (serverId: string) => void;
  setSelectedCatalogueServerIds: (ids: string[]) => void;

  // Actions - Tool selection
  toggleToolSelection: (toolId: string) => void;
  selectAllTools: () => void;
  deselectAllTools: () => void;

  // Actions - Virtual server
  setVirtualServerName: (name: string) => void;

  // Actions - Workflow operations
  createWorkflow: () => Promise<WorkflowResponse | null>;
  updateWorkflowStep: (stepNumber: number, triggerWorkflow?: boolean) => Promise<WorkflowResponse | null>;
  uploadFileAndCreate: () => Promise<WorkflowResponse | null>;
  fetchWorkflow: (workflowId: string) => Promise<WorkflowResponse | null>;
  fetchCreatedTools: () => Promise<void>;
  createVirtualServer: () => Promise<VirtualServerResponse | null>;

  // Actions - Events
  addCreationEvent: (event: Omit<ToolCreationEvent, "timestamp">) => void;
  clearCreationEvents: () => void;

  // Actions - Reset
  reset: () => void;
}

const initialState = {
  workflowId: null,
  currentStep: 1,
  totalSteps: 5,
  status: "pending",
  sourceType: null,
  openApiUrl: "",
  apiDocsUrl: "",
  enhanceWithAi: true,
  uploadedFile: null,
  uploadedFileName: "",
  catalogueServers: [],
  selectedCatalogueServerIds: [],
  creationEvents: [],
  isCreating: false,
  createdTools: [],
  selectedToolIds: [],
  gatewayId: null,
  virtualServerName: "",
  virtualServerId: null,
  isLoading: false,
  error: null,
};

export const useAddTool = create<AddToolState>((set, get) => ({
  ...initialState,

  // Source selection
  setSourceType: (sourceType) => set({ sourceType }),

  // Configuration
  setOpenApiUrl: (url) => set({ openApiUrl: url }),
  setApiDocsUrl: (url) => set({ apiDocsUrl: url }),
  setEnhanceWithAi: (enhance) => set({ enhanceWithAi: enhance }),
  setUploadedFile: (file) =>
    set({
      uploadedFile: file,
      uploadedFileName: file?.name || "",
    }),

  // Catalogue actions
  fetchCatalogueServers: async (offset = 0, limit = 50) => {
    set({ isLoading: true, error: null });
    try {
      const response = await AppRequest.Get("/tools/catalogue", {
        params: { offset, limit },
      });

      const servers: CatalogueServer[] = response.data?.servers || [];
      set({ catalogueServers: servers });
    } catch (error: any) {
      console.error("Error fetching catalogue servers:", error);
      set({ error: error?.message || "Failed to fetch catalogue servers" });
    } finally {
      set({ isLoading: false });
    }
  },

  toggleCatalogueServer: (serverId) => {
    const { selectedCatalogueServerIds } = get();
    const newSelection = selectedCatalogueServerIds.includes(serverId)
      ? selectedCatalogueServerIds.filter((id) => id !== serverId)
      : [...selectedCatalogueServerIds, serverId];
    set({ selectedCatalogueServerIds: newSelection });
  },

  setSelectedCatalogueServerIds: (ids) => set({ selectedCatalogueServerIds: ids }),

  // Tool selection actions
  toggleToolSelection: (toolId) => {
    const { selectedToolIds } = get();
    const newSelection = selectedToolIds.includes(toolId)
      ? selectedToolIds.filter((id) => id !== toolId)
      : [...selectedToolIds, toolId];
    set({ selectedToolIds: newSelection });
  },

  selectAllTools: () => {
    const { createdTools } = get();
    set({ selectedToolIds: createdTools.map((t) => t.id) });
  },

  deselectAllTools: () => set({ selectedToolIds: [] }),

  // Virtual server
  setVirtualServerName: (name) => set({ virtualServerName: name }),

  // Create workflow (Step 1)
  createWorkflow: async () => {
    const { sourceType } = get();
    if (!sourceType) {
      set({ error: "Source type is required" });
      return null;
    }

    set({ isLoading: true, error: null });
    try {
      const response = await AppRequest.Post("/tools/workflow", {
        step_number: 1,
        workflow_total_steps: 5,
        source_type: sourceType,
      });

      // AppRequest returns false on error instead of throwing
      if (!response || !response.data) {
        set({ error: "Failed to create workflow" });
        return null;
      }

      const workflow: WorkflowResponse = {
        workflow_id: response.data?.workflow_id,
        current_step: response.data?.current_step || 1,
        total_steps: response.data?.total_steps || 5,
        status: response.data?.status || "pending",
      };

      set({
        workflowId: workflow.workflow_id,
        currentStep: workflow.current_step,
        totalSteps: workflow.total_steps,
        status: workflow.status,
      });

      return workflow;
    } catch (error: any) {
      console.error("Error creating workflow:", error);
      const errorMessage = error?.response?.data?.message || error?.response?.data?.detail || error?.message || "Failed to create workflow";
      set({ error: errorMessage });
      return null;
    } finally {
      set({ isLoading: false });
    }
  },

  // Update workflow step
  updateWorkflowStep: async (stepNumber, triggerWorkflow = false) => {
    const state = get();
    const { workflowId, sourceType, openApiUrl, apiDocsUrl, enhanceWithAi, selectedCatalogueServerIds, selectedToolIds, virtualServerName } = state;

    if (!workflowId) {
      set({ error: "Workflow not initialized" });
      return null;
    }

    set({ isLoading: true, error: null });

    if (triggerWorkflow) {
      set({ isCreating: true });
    }

    try {
      const payload: Record<string, any> = {
        workflow_id: workflowId,
        step_number: stepNumber,
        workflow_total_steps: 5,
        trigger_workflow: triggerWorkflow,
      };

      // Add step-specific data
      if (sourceType) payload.source_type = sourceType;
      if (openApiUrl) payload.openapi_url = openApiUrl;
      if (apiDocsUrl) payload.api_docs_url = apiDocsUrl;
      payload.enhance_with_ai = enhanceWithAi;

      if (selectedCatalogueServerIds.length > 0) {
        payload.catalogue_server_ids = selectedCatalogueServerIds;
      }

      if (selectedToolIds.length > 0) {
        payload.selected_tool_ids = selectedToolIds;
      }

      if (virtualServerName) {
        payload.virtual_server_name = virtualServerName;
      }

      const response = await AppRequest.Post("/tools/workflow", payload);

      // AppRequest returns false on error instead of throwing
      if (!response || !response.data) {
        set({ error: "Failed to update workflow" });
        return null;
      }

      const workflow: WorkflowResponse = {
        workflow_id: response.data?.workflow_id,
        current_step: response.data?.current_step || stepNumber,
        total_steps: response.data?.total_steps || 5,
        status: response.data?.status || "pending",
        step_data: response.data?.step_data,
      };

      set({
        currentStep: workflow.current_step,
        status: workflow.status,
      });

      return workflow;
    } catch (error: any) {
      console.error("Error updating workflow:", error);
      const errorMessage = error?.response?.data?.message || error?.response?.data?.detail || error?.message || "Failed to update workflow";
      set({ error: errorMessage });
      return null;
    } finally {
      set({ isLoading: false, isCreating: false });
    }
  },

  // Upload file and create tools
  uploadFileAndCreate: async () => {
    const { workflowId, uploadedFile, sourceType, enhanceWithAi } = get();

    if (!workflowId) {
      set({ error: "Workflow not initialized" });
      return null;
    }

    if (!uploadedFile) {
      set({ error: "No file uploaded" });
      return null;
    }

    if (sourceType !== ToolSourceType.OPENAPI_FILE && sourceType !== ToolSourceType.API_DOCS_FILE) {
      set({ error: "Invalid source type for file upload" });
      return null;
    }

    set({ isLoading: true, isCreating: true, error: null });

    try {
      const formData = new FormData();
      formData.append("file", uploadedFile);
      formData.append("source_type", sourceType);
      formData.append("enhance_with_ai", String(enhanceWithAi));

      const response = await AppRequest.Post(`/tools/workflow/${workflowId}/upload`, formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });

      // AppRequest returns false on error instead of throwing
      if (!response || !response.data) {
        set({ error: "Failed to upload file" });
        return null;
      }

      const workflow: WorkflowResponse = {
        workflow_id: response.data?.workflow_id,
        current_step: response.data?.current_step || 3,
        total_steps: response.data?.total_steps || 5,
        status: response.data?.status || "completed",
      };

      set({
        currentStep: workflow.current_step,
        status: workflow.status,
      });

      return workflow;
    } catch (error: any) {
      console.error("Error uploading file:", error);
      const errorMessage = error?.response?.data?.message || error?.response?.data?.detail || error?.message || "Failed to upload file";
      set({ error: errorMessage });
      return null;
    } finally {
      set({ isLoading: false, isCreating: false });
    }
  },

  // Fetch workflow status
  fetchWorkflow: async (workflowId) => {
    set({ isLoading: true, error: null });
    try {
      const response = await AppRequest.Get(`/tools/workflow/${workflowId}`);

      const workflow: WorkflowResponse = {
        workflow_id: response.data?.workflow_id,
        current_step: response.data?.current_step,
        total_steps: response.data?.total_steps,
        status: response.data?.status,
        step_data: response.data?.step_data,
      };

      set({
        workflowId: workflow.workflow_id,
        currentStep: workflow.current_step,
        totalSteps: workflow.total_steps,
        status: workflow.status,
        gatewayId: workflow.step_data?.gateway_id || null,
      });

      return workflow;
    } catch (error: any) {
      console.error("Error fetching workflow:", error);
      set({ error: error?.message || "Failed to fetch workflow" });
      return null;
    } finally {
      set({ isLoading: false });
    }
  },

  // Fetch created tools
  fetchCreatedTools: async () => {
    const { workflowId } = get();
    if (!workflowId) {
      set({ error: "Workflow not initialized" });
      return;
    }

    set({ isLoading: true, error: null });
    try {
      const response = await AppRequest.Get(`/tools/workflow/${workflowId}/tools`);

      const toolsData = response.data?.tools || [];
      const gatewayId = response.data?.gateway_id;

      // Transform to UI Tool format (simplified - reuse from useTools)
      const tools: Tool[] = toolsData.map((t: McpToolResponse) => ({
        id: t.id,
        name: t.displayName || t.customName || t.name,
        icon: "🔧",
        category: t.integrationType || "General",
        description: t.description || "",
        tags: (t.tags || []).map((tagName) => ({ name: tagName, color: "#965CDE" })),
        created_at: t.createdAt,
        usage_count: t.executionCount || 0,
        enabled: t.enabled,
        rawData: t,
      }));

      set({
        createdTools: tools,
        gatewayId: gatewayId || null,
        // Auto-select all tools by default
        selectedToolIds: tools.map((t) => t.id),
      });
    } catch (error: any) {
      console.error("Error fetching created tools:", error);
      set({ error: error?.message || "Failed to fetch created tools" });
    } finally {
      set({ isLoading: false });
    }
  },

  // Create virtual server
  createVirtualServer: async () => {
    const { workflowId, virtualServerName, selectedToolIds } = get();

    if (!workflowId) {
      set({ error: "Workflow not initialized" });
      return null;
    }

    if (!virtualServerName.trim()) {
      set({ error: "Virtual server name is required" });
      return null;
    }

    if (selectedToolIds.length === 0) {
      set({ error: "At least one tool must be selected" });
      return null;
    }

    set({ isLoading: true, error: null });
    try {
      const response = await AppRequest.Post(`/tools/workflow/${workflowId}/virtual-server`, {
        name: virtualServerName.trim(),
        selected_tool_ids: selectedToolIds,
      });

      const result: VirtualServerResponse = {
        virtual_server_id: response.data?.virtual_server_id,
        name: response.data?.name,
        tool_count: response.data?.tool_count,
      };

      set({
        virtualServerId: result.virtual_server_id,
        currentStep: 5,
        status: "completed",
      });

      return result;
    } catch (error: any) {
      console.error("Error creating virtual server:", error);
      set({ error: error?.message || "Failed to create virtual server" });
      return null;
    } finally {
      set({ isLoading: false });
    }
  },

  // Event management
  addCreationEvent: (event) => {
    set((state) => ({
      creationEvents: [
        ...state.creationEvents,
        { ...event, timestamp: new Date() },
      ],
    }));
  },

  clearCreationEvents: () => set({ creationEvents: [] }),

  // Reset
  reset: () => set(initialState),
}));

import { tempApiBaseUrl } from "@/components/environment";
import { errorToast, successToast } from "@/components/toast";
import { Project } from "src/hooks/useProjects";
import { Model } from "src/hooks/useModels";
import { create } from "zustand";
import { WorkflowType } from "./useWorkflow";
import { AppRequest } from "src/pages/api/requests";
import { Tag } from "@/components/ui/bud/dataEntry/TagsInput";

export type AgentType = {
  id: string;
  name: string;
  description?: string;
  icon?: string;
};

export type AgentConfiguration = {
  name: string;
  description: string;
  system_prompt: string;
  temperature: number;
  max_tokens: number;
  top_p: number;
  frequency_penalty: number;
  presence_penalty: number;
  tools?: any[];
  knowledge_base?: any[];
};

export type DeploymentConfiguration = {
  deploymentName: string;
  tags: any[];
  description: string;
  minConcurrency: number;
  maxConcurrency: number;
  autoScale: boolean;
  autoCaching: boolean;
  autoLogging: boolean;
  rateLimit: boolean;
  rateLimitValue: number;
  triggerWorkflow: boolean;
};

export type WarningData = {
  warnings: string[];
  errors: string[];
  validation_issues: string[];
  recommendations: Record<string, any>;
};

export const useAddAgent = create<{
  loading: boolean;
  requestCount: number;
  currentWorkflow: WorkflowType | null;
  selectedProject: Partial<Project> | null;
  selectedAgentType: AgentType | null;
  selectedModel: Model | null;
  agentConfiguration: AgentConfiguration;
  deploymentConfiguration: DeploymentConfiguration | null;
  warningData: WarningData | null;
  promptMessages: any[];
  promptTags: Tag[];
  formResetKey: number;

  setLoading: (loading: boolean) => void;
  setCurrentWorkflow: (workflow: WorkflowType) => void;
  setSelectedProject: (project: Partial<Project>) => void;
  setSelectedAgentType: (agentType: AgentType) => void;
  setSelectedModel: (model: Model) => void;
  setAgentConfiguration: (config: Partial<AgentConfiguration>) => void;
  setDeploymentConfiguration: (config: DeploymentConfiguration) => void;
  setWarningData: (warnings: WarningData | null) => void;
  setPromptMessages: (messages: any[]) => void;

  startRequest: () => void;
  endRequest: () => void;
  reset: () => void;

  getWorkflow: (id?: string) => Promise<any>;
  getPromptTags: () => Promise<void>;
  createWorkflow: (projectId: string) => Promise<any>;
  updateAgentType: () => Promise<any>;
  updateModel: () => Promise<any>;
  updateConfiguration: () => Promise<any>;
  updatePrompts: () => Promise<any>;
  deployAgent: () => Promise<any>;
}>((set, get) => ({
  loading: false,
  requestCount: 0,
  currentWorkflow: null,
  selectedProject: null,
  formResetKey: 0,
  selectedAgentType: null,
  selectedModel: null,
  agentConfiguration: {
    name: "",
    description: "",
    system_prompt: "",
    temperature: 0.7,
    max_tokens: 2048,
    top_p: 1,
    frequency_penalty: 0,
    presence_penalty: 0,
    tools: [],
    knowledge_base: [],
  },
  deploymentConfiguration: null,
  warningData: null,
  promptMessages: [],
  promptTags: [],

  setLoading: (loading: boolean) => {
    set({ loading });
  },

  setCurrentWorkflow: (workflow: WorkflowType) => {
    set({ currentWorkflow: workflow });
  },

  setSelectedProject: (project: Partial<Project>) => {
    set({ selectedProject: project });
  },

  setSelectedAgentType: (agentType: AgentType) => {
    set({ selectedAgentType: agentType });
  },

  setSelectedModel: (model: Model) => {
    set({ selectedModel: model });
  },

  setAgentConfiguration: (config: Partial<AgentConfiguration>) => {
    set((state) => ({
      agentConfiguration: {
        ...state.agentConfiguration,
        ...config,
      },
    }));
  },

  setDeploymentConfiguration: (config: DeploymentConfiguration) => {
    set({ deploymentConfiguration: config });
  },

  setWarningData: (warnings: WarningData | null) => {
    set({ warningData: warnings });
  },

  setPromptMessages: (messages: any[]) => {
    set({ promptMessages: messages });
  },

  startRequest: () => {
    const newCount = get().requestCount + 1;
    set({ requestCount: newCount, loading: true });
  },

  endRequest: () => {
    const newCount = get().requestCount - 1;
    set({
      requestCount: newCount,
      loading: newCount > 0,
    });
  },

  reset: () => {
    set((state) => ({
      currentWorkflow: null,
      selectedProject: null,
      selectedAgentType: null,
      selectedModel: null,
      agentConfiguration: {
        name: "",
        description: "",
        system_prompt: "",
        temperature: 0.7,
        max_tokens: 2048,
        top_p: 1,
        frequency_penalty: 0,
        presence_penalty: 0,
        tools: [],
        knowledge_base: [],
      },
      deploymentConfiguration: null,
      warningData: null,
      promptMessages: [],
      loading: false,
      requestCount: 0,
      // Increment formResetKey to force remount of form components in AgentConfiguration
      formResetKey: state.formResetKey + 1,
    }));
  },

  getWorkflow: async (id?: string) => {
    const workflowId = id || get().currentWorkflow?.workflow_id;
    if (!workflowId) {
      return;
    }
    get().startRequest();
    try {
      const response: any = await AppRequest.Get(
        `${tempApiBaseUrl}/workflows/${workflowId}`
      );
      if (response) {
        const workflow: WorkflowType = response.data;
        set({ currentWorkflow: workflow });
        return workflow;
      }
    } catch (error) {
      console.error("Error getting workflow:", error);
      return false;
    } finally {
      get().endRequest();
    }
  },

  getPromptTags: async () => {
    try {
      const response: any = await AppRequest.Get(
        `${tempApiBaseUrl}/prompts/tags?page=1&limit=1000`
      );
      if (response?.data?.tags) {
        set({ promptTags: response.data.tags });
      }
    } catch (error) {
      console.error("Error fetching prompt tags:", error);
    }
  },

  createWorkflow: async (projectId: string) => {
    if (!projectId) {
      errorToast("Please select a project");
      return;
    }
    get().startRequest();
    try {
      const response: any = await AppRequest.Post(
        `${tempApiBaseUrl}/prompts/prompt-workflow`,
        {
          workflow_total_steps: 6,
          step_number: 1,
          project_id: projectId,
        },
        {
          headers: {
            "x-resource-type": "project",
            "x-entity-id": projectId,
          },
        }
      );
      if (response?.data) {
        // Store the workflow with project_id for reference in other steps
        const workflowData = {
          ...response.data,
          project_id: projectId
        };
        set({ currentWorkflow: workflowData });

        // Fetch the complete workflow details
        if (response.data.workflow_id || response.data.id) {
          await get().getWorkflow(response.data.workflow_id || response.data.id);
        }
        return response;
      }
    } catch (error) {
      console.error("Error creating agent workflow:", error);
      errorToast("Failed to create agent workflow");
    } finally {
      get().endRequest();
    }
  },

  updateAgentType: async () => {
    const workflowId = get().currentWorkflow?.workflow_id;
    const agentType = get().selectedAgentType;
    const projectId = get().selectedProject?.id;

    if (!workflowId) {
      errorToast("Please create a workflow first");
      return;
    }

    get().startRequest();
    try {
      const response: any = await AppRequest.Post(
        `${tempApiBaseUrl}/prompts/prompt-workflow`,
        {
          step_number: 2,
          workflow_id: workflowId,
          agent_type_id: agentType?.id,
        },
        {
          headers: {
            "x-resource-type": "project",
            "x-entity-id": projectId,
          },
        }
      );
      await get().getWorkflow();
      return response;
    } catch (error) {
      console.error("Error updating agent type:", error);
      errorToast("Failed to update agent type");
    } finally {
      get().endRequest();
    }
  },

  updateModel: async () => {
    const workflowId = get().currentWorkflow?.workflow_id;
    const modelId = get().selectedModel?.id;
    const projectId = get().selectedProject?.id;

    if (!workflowId) {
      errorToast("Please create a workflow first");
      return;
    }

    if (!modelId) {
      errorToast("Please select a model");
      return;
    }

    get().startRequest();
    try {
      const response: any = await AppRequest.Post(
        `${tempApiBaseUrl}/prompts/prompt-workflow`,
        {
          step_number: 3,
          workflow_id: workflowId,
          model_id: modelId,
        },
        {
          headers: {
            "x-resource-type": "project",
            "x-entity-id": projectId,
          },
        }
      );
      await get().getWorkflow();
      return response;
    } catch (error) {
      console.error("Error updating model:", error);
      errorToast("Failed to update model");
    } finally {
      get().endRequest();
    }
  },

  updateConfiguration: async () => {
    const workflowId = get().currentWorkflow?.workflow_id;
    const configuration = get().agentConfiguration;
    const projectId = get().selectedProject?.id;

    if (!workflowId) {
      errorToast("Please create a workflow first");
      return;
    }

    get().startRequest();
    try {
      const response: any = await AppRequest.Post(
        `${tempApiBaseUrl}/prompts/prompt-workflow`,
        {
          step_number: 4,
          workflow_id: workflowId,
          agent_configuration: configuration,
        },
        {
          headers: {
            "x-resource-type": "project",
            "x-entity-id": projectId,
          },
        }
      );
      await get().getWorkflow();
      return response;
    } catch (error) {
      console.error("Error updating configuration:", error);
      errorToast("Failed to update configuration");
    } finally {
      get().endRequest();
    }
  },

  updatePrompts: async () => {
    const workflowId = get().currentWorkflow?.workflow_id;
    const prompts = get().promptMessages;
    const projectId = get().selectedProject?.id;

    if (!workflowId) {
      errorToast("Please create a workflow first");
      return;
    }

    get().startRequest();
    try {
      const response: any = await AppRequest.Post(
        `${tempApiBaseUrl}/prompts/prompt-workflow`,
        {
          step_number: 5,
          workflow_id: workflowId,
          prompt_messages: prompts,
        },
        {
          headers: {
            "x-resource-type": "project",
            "x-entity-id": projectId,
          },
        }
      );
      await get().getWorkflow();
      return response;
    } catch (error) {
      console.error("Error updating prompts:", error);
      errorToast("Failed to update prompts");
    } finally {
      get().endRequest();
    }
  },

  deployAgent: async () => {
    const workflowId = get().currentWorkflow?.workflow_id;
    const projectId = get().selectedProject?.id;

    if (!workflowId) {
      errorToast("Please create a workflow first");
      return;
    }

    get().startRequest();
    try {
      const response: any = await AppRequest.Post(
        `${tempApiBaseUrl}/prompts/prompt-workflow`,
        {
          step_number: 6,
          workflow_id: workflowId,
          trigger_workflow: true,
        },
        {
          headers: {
            "x-resource-type": "project",
            "x-entity-id": projectId,
          },
        }
      );
      await get().getWorkflow();
      successToast("Agent deployment started successfully");
      return response;
    } catch (error) {
      console.error("Error deploying agent:", error);
      errorToast("Failed to deploy agent");
    } finally {
      get().endRequest();
    }
  },
}));

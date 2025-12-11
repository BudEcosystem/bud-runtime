import { tempApiBaseUrl } from "@/components/environment";
import { errorToast, successToast } from "@/components/toast";
import { Provider } from "src/hooks/useCloudProviders";
import { Model, ModelIssue, ScanResult, useModels } from "src/hooks/useModels";
import { Project, useProjects } from "src/hooks/useProjects";
import { IDeploymentTemplate } from "src/hooks/useTemplates";
import { create } from "zustand";
import { Credentials } from "./useProprietaryCredentials";
import { WorkflowType } from "./useWorkflow";
import { AppRequest } from "src/pages/api/requests";
import { Cluster } from "src/hooks/useCluster";

export type CreateForm = {
  name: string;
  tags: [];
  description: string;
  concurrent_requests: number;
  eval_with: string;
};
export type StepTwo = {
  max_input_tokens: string;
  max_output_tokens: string;
};

type GetUserParams = {
  page: number;
  limit: number;
  order_by?: string;
  name?: string;
  email?: string;
  role?: string;
  status?: string;
};

export type Benchmark = {
  key?: string;
  created_at?: string;
  model: [];
  cluster: [];
  name?: string;
  modelName?: string;
  modelImage?: string;
  clusterName?: string;
  clusterImage?: string;
  node_type?: any;
  vendor_type?: string;
  status?: string;
  concurrentRequest?: string;
  tpot?: string;
  ttft?: string;
  id?: string;
};

export type Node = {
  capacity?: {};
  cpu?: {};
  events_count?: number;
  hostname?: string;
  memory?: {};
  network?: {};
  pods?: {};
  status?: string;
  system_info?: {};
};

export type Dataset = {
  columns?: {};
  created_at?: string;
  description?: string;
  filename?: string;
  folder?: string;
  formatting?: string;
  hf_hub_url?: string;
  id?: string;
  modified_at?: string;
  ms_hub_url?: string;
  name?: string;
  num_samples?: number;
  ranking?: boolean;
  script_url?: string;
  split?: string;
  status?: string;
  subset?: {};
  tags?: {};
};

// Node Configuration Types
export type TPPPOption = {
  tp_size: number;
  pp_size: number;
  max_replicas: number;
  total_devices_needed: number;
  description: string;
};

export type DeviceTypeConfiguration = {
  device_type: string;
  device_name: string | null;
  device_model: string | null;
  total_devices: number;
  nodes_count: number;
  max_devices_per_node: number;
  memory_per_device_gb: number;
  tp_pp_options: TPPPOption[];
  min_tp_required: number;
  supports_pipeline_parallelism: boolean;
};

export type ModelMemoryInfo = {
  model_id: string;
  model_name: string | null;
  model_uri: string | null;
  estimated_weight_memory_gb: number;
  min_tp_for_model: number;
};

export type NodeConfigurationResponse = {
  cluster_id: string;
  model_info: ModelMemoryInfo;
  device_configurations: DeviceTypeConfiguration[];
  selected_nodes: string[];
  hardware_mode: string;
};

export type SelectedConfiguration = {
  device_type: string;
  tp_size: number;
  pp_size: number;
  replicas: number;
};

export const usePerfomanceBenchmark = create<{
  totalPages: number;
  totalUsers: number;
  filters: any;
  stepOneData: CreateForm | null;
  stepTwoData: StepTwo | null;
  evalWith: string;

  dataset: any | null;
  nodeMetrics: any | null;
  searchText: string;
  filteredNodeMetrics: any | null;

  selectedCluster: Cluster | null;
  selectedNodes: Node[];
  selectedDataset: Dataset[];
  selectedModel: Model | null;
  runAsSimulation: boolean;
  hardwareMode: "dedicated" | "shared" | null;

  // Node Configuration state
  nodeConfigurations: NodeConfigurationResponse | null;
  selectedConfiguration: SelectedConfiguration | null;
  loadingConfigurations: boolean;

  benchmarks: Benchmark[];
  currentWorkflow: WorkflowType | null;
  currentWorkflowId: null;
  selectedCredentials: Credentials | null;
  totalDataset: number | null;
  reset: () => void;
  setSelectedCredentials: (credentials: Credentials | null) => void;
  setCurrentWorkflow: (workflow: WorkflowType) => void;
  getDataset: (params: any) => void;
  getWorkflow: (id?: string) => Promise<any>;
  loading: boolean;
  setLoading: (loading: boolean) => void;
  deleteWorkflow: (id: string, suppressToast?: boolean) => Promise<any>;
  createWorkflow: (projectId: string) => void;

  setEvalWith: (evalWith: any) => any;
  setNodeMetrics: (nodeMetrics: any) => any;
  setFilteredNodes: (text: string) => any;
  setSearchText: (text: string) => any;
  setRunAsSimulation: (runAsSimulation: boolean) => any;

  setSelectedCluster: (cluster: any) => void;
  setSelectedNodes: (node: Node) => void;
  setSelecteUnselectAll: (selectAll: boolean) => void;
  setSelecteUnselectAllDataset: (selectAll: boolean) => void;
  setSelectedDataset: (dataset: Dataset) => void;
  setSelectedModel: (model: Model) => void;
  setHardwareMode: (mode: "dedicated" | "shared" | null) => void;

  createBenchmark: (data: CreateForm) => any;
  stepTwo: (data: StepTwo) => any;
  stepTwoDataset: () => any;
  stepThree: () => any;
  stepHardwareMode: () => Promise<any>;
  stepFour: () => any;
  stepFive: () => any;
  updateCredentials: (credentials: Credentials) => any;
  stepSix: () => any;
  stepSeven: () => any;
  stepEight: () => any;

  // Node Configuration methods
  fetchNodeConfigurations: () => Promise<NodeConfigurationResponse | null>;
  setSelectedConfiguration: (config: SelectedConfiguration | null) => void;
  stepConfigurationOptions: () => Promise<any>;
}>((set, get) => ({
  filters: {},
  totalPages: 0,
  totalUsers: 0,
  evalWith: "",

  dataset: [],
  nodeMetrics: null,
  filteredNodeMetrics: null,
  searchText: null,

  benchmarks: [],
  stepOneData: null,
  stepTwoData: null,
  currentWorkflow: null,
  currentWorkflowId: null,
  runAsSimulation: false,

  selectedCluster: null,
  selectedNodes: [],
  selectedDataset: [],
  selectedModel: null,
  selectedCredentials: null,
  hardwareMode: null,
  totalDataset: null,

  // Node Configuration state
  nodeConfigurations: null,
  selectedConfiguration: null,
  loadingConfigurations: false,
  setSelectedCredentials: (credentials: Credentials | null) => {
    set({ selectedCredentials: credentials });
  },
  setSelectedModel: (model: any) => {
    set({ selectedModel: model });
  },
  setHardwareMode: (mode: "dedicated" | "shared" | null) => {
    set({ hardwareMode: mode });
  },
  setNodeMetrics: (nodeMetrics: any) => {
    set({ nodeMetrics: nodeMetrics });
    set({ filteredNodeMetrics: get().nodeMetrics });
  },

  setSearchText: (text) => {
    set({ searchText: text });
  },
  setFilteredNodes: (text) => {
    get().setSearchText(text);
    let nodeMetrics = get().nodeMetrics;
    const filtered = Object.values(nodeMetrics).filter((node: any) =>
      node.hostname.toLowerCase().includes(get().searchText.toLowerCase()),
    );
    set({ filteredNodeMetrics: filtered });
  },

  setRunAsSimulation: (runAsSimulation: boolean) =>
    set({ runAsSimulation: runAsSimulation }),
  setEvalWith: (evalWith: string) => set({ evalWith: evalWith }),

  setCurrentWorkflow: (workflow: WorkflowType) =>
    set({ currentWorkflow: workflow }),

  reset: () => {
    set({
      currentWorkflow: null,
      selectedModel: null,
      selectedCredentials: null,
      stepOneData: null,
      stepTwoData: null,
      currentWorkflowId: null,
      runAsSimulation: false,
      selectedCluster: null,
      selectedNodes: [],
      selectedDataset: [],
      totalDataset: null,
      evalWith: "",
      hardwareMode: null,
      nodeConfigurations: null,
      selectedConfiguration: null,
      loadingConfigurations: false,
    });
  },

  getDataset: async (params: any) => {
    get().setLoading(true);
    try {
      const response: any = await AppRequest.Get(`${tempApiBaseUrl}/dataset`, {
        params,
      });
      if (response) {
        const workflow: WorkflowType = response.data;
        set({ dataset: response.data.datasets });
        set({ totalDataset: response.data.total_record });
        return workflow;
      }
      // successToast(response.data.message);
    } catch (error) {
      return false;
    } finally {
      get().setLoading(false);
    }
  },

  getWorkflow: async (id?: string) => {
    const workflowId = id || get().currentWorkflow?.workflow_id;
    if (!workflowId) {
      return;
    }
    get().setLoading(true);
    try {
      const response: any = await AppRequest.Get(
        `${tempApiBaseUrl}/workflows/${workflowId}`,
      );
      if (response) {
        const workflow: WorkflowType = response.data;
        set({ currentWorkflow: workflow });
        return workflow;
      }
      // successToast(response.data.message);
    } catch (error) {
      return false;
    } finally {
      get().setLoading(false);
    }
  },
  loading: false,
  setLoading: (loading: boolean) => set({ loading }),
  deleteWorkflow: async (id: string, suppressToast?: boolean) => {
    try {
      const response: any = await AppRequest.Delete(
        `${tempApiBaseUrl}/workflows/${id}`,
      );
      if (!suppressToast) {
        successToast(response.data.message);
      }
      set({ currentWorkflow: null });
      return response.data;
    } catch (error) {
      console.error("Error creating model:", error);
      return error;
    }
  },
  createWorkflow: (projectId: string) => {
    // Implementation here
  },

  setSelectedCluster: (cluster: any) => {
    set({ selectedCluster: cluster });
  },
  setSelecteUnselectAll: (selectAll) => {
    if (selectAll) {
      set({ selectedNodes: [] });
    } else {
      let nodes = get().filteredNodeMetrics;
      Object.keys(nodes).map((key, index) =>
        get().setSelectedNodes(nodes[key]),
      );
    }
  },
  setSelectedNodes: (node) => {
    set((state) => {
      const isAlreadySelected = state.selectedNodes.some(
        (selected) => selected.hostname === node.hostname,
      );

      return {
        selectedNodes: isAlreadySelected
          ? state.selectedNodes.filter(
              (selected) => selected.hostname !== node.hostname,
            ) // Remove if already selected
          : [...state.selectedNodes, node], // Add if not selected
      };
    });
  },

  setSelectedDataset: (dataset) => {
    set((state) => {
      const isAlreadySelected = state.selectedDataset.some(
        (selected) => selected.id === dataset.id,
      );

      return {
        selectedDataset: isAlreadySelected
          ? state.selectedDataset.filter(
              (selected) => selected.id !== dataset.id,
            ) // Remove if already selected
          : [...state.selectedDataset, dataset], // Add if not selected
      };
    });
  },

  setSelecteUnselectAllDataset: (selectAll) => {
    if (selectAll) {
      set({ selectedDataset: [] });
    } else {
      let nodes = get().dataset;
      set({ selectedDataset: nodes });
    }
  },

  createBenchmark: async (data: CreateForm) => {
    if (!data) {
      errorToast("Please enter data");
      return;
    }
    get().setLoading(true);
    set({ stepOneData: data });
    try {
      const response: any = await AppRequest.Post(
        `${tempApiBaseUrl}/benchmark/run-workflow`,
        {
          ...data,
          workflow_total_steps: 9,
          step_number: 1,
          trigger_workflow: false,
        },
      );
      set({ currentWorkflow: response.data });
      set({ currentWorkflowId: response.data.workflow_id });
      console.log("response", response);
      return response;
    } catch (error) {
      console.error("Error creating model:", error);
    } finally {
      get().setLoading(false);
    }
  },
  stepTwo: async (data: StepTwo) => {
    const workflowId = get().currentWorkflow?.workflow_id;
    console.log("workflowId", workflowId);
    set({ stepTwoData: data });
    if (!data) {
      errorToast("Please enter data");
      return;
    }
    get().setLoading(true);
    try {
      const response: any = await AppRequest.Post(
        `${tempApiBaseUrl}/benchmark/run-workflow`,
        {
          ...data,
          ...get().stepOneData,
          workflow_id: workflowId,
          step_number: 2,
          trigger_workflow: false,
        },
      );
      get().getWorkflow();
      // successToast(response.data.message);
      return response;
    } catch (error) {
      console.error("Error creating model:", error);
    } finally {
      get().setLoading(false);
    }
  },
  stepTwoDataset: async () => {
    const workflowId = get().currentWorkflow?.workflow_id;
    let data = get().selectedDataset;
    if (!data) {
      errorToast("Please enter data");
      return;
    }
    get().setLoading(true);
    try {
      const response: any = await AppRequest.Post(
        `${tempApiBaseUrl}/benchmark/run-workflow`,
        {
          ...get().stepOneData,
          workflow_id: workflowId,
          step_number: 2,
          trigger_workflow: false,
          datasets: get().selectedDataset.map((dataset) => dataset.id),
        },
      );
      get().getWorkflow();
      // successToast(response.data.message);
      return response;
    } catch (error) {
      console.error("Error creating model:", error);
    } finally {
      get().setLoading(false);
    }
  },
  stepThree: async () => {
    const workflowId = get().currentWorkflow?.workflow_id;
    const cluster = get().selectedCluster;
    console.log("cluster", cluster);
    console.log("workflowId", workflowId);
    if (!cluster?.id) {
      errorToast("Please select a cluster");
      return;
    }
    get().setLoading(true);
    try {
      const response: any = await AppRequest.Post(
        `${tempApiBaseUrl}/benchmark/run-workflow`,
        {
          ...get().stepOneData,
          workflow_id: workflowId,
          step_number: 3,
          trigger_workflow: false,
          cluster_id: cluster?.id,
        },
      );
      get().getWorkflow();
      // successToast(response.data.message);
      return response;
    } catch (error) {
      console.error("Error creating model:", error);
    } finally {
      get().setLoading(false);
    }
  },
  stepHardwareMode: async () => {
    const workflowId = get().currentWorkflow?.workflow_id;
    const hardwareMode = get().hardwareMode;
    if (!hardwareMode) {
      errorToast("Please select a hardware mode");
      return;
    }
    get().setLoading(true);
    try {
      const response: any = await AppRequest.Post(
        `${tempApiBaseUrl}/benchmark/run-workflow`,
        {
          ...get().stepOneData,
          workflow_id: workflowId,
          step_number: 4,
          trigger_workflow: false,
          hardware_mode: hardwareMode,
        },
      );
      get().getWorkflow();
      return response;
    } catch (error) {
      console.error("Error saving hardware mode:", error);
    } finally {
      get().setLoading(false);
    }
  },
  stepFour: async () => {
    const workflowId = get().currentWorkflow?.workflow_id;
    const nodes = get().selectedNodes;
    const hardwareMode = get().hardwareMode;
    console.log("cluster", nodes);
    if (!nodes) {
      errorToast("Please select nodes");
      return;
    }
    get().setLoading(true);
    try {
      const response: any = await AppRequest.Post(
        `${tempApiBaseUrl}/benchmark/run-workflow`,
        {
          ...get().stepOneData,
          workflow_id: workflowId,
          step_number: 5,
          trigger_workflow: false,
          nodes: nodes,
          hardware_mode: hardwareMode,
        },
      );
      get().getWorkflow();
      // successToast(response.data.message);
      return response;
    } catch (error) {
      console.error("Error creating model:", error);
    } finally {
      get().setLoading(false);
    }
  },
  stepFive: async () => {
    const workflowId = get().currentWorkflow?.workflow_id;
    const modelId = get().selectedModel?.id;
    if (!modelId) {
      errorToast("Please select nodes");
      return;
    }
    get().setLoading(true);
    try {
      const response: any = await AppRequest.Post(
        `${tempApiBaseUrl}/benchmark/run-workflow`,
        {
          ...get().stepOneData,
          ...get().stepTwoData,
          workflow_id: workflowId,
          step_number: 6,
          // "trigger_workflow": false,
          model_id: modelId,
        },
      );
      get().getWorkflow();
      // successToast(response.data.message);
      return response;
    } catch (error) {
      console.error("Error creating model:", error);
    } finally {
      get().setLoading(false);
    }
  },
  updateCredentials: async (credentials: Credentials) => {
    console.log("credentials", credentials);
    const workflowId = get().currentWorkflow?.workflow_id;
    if (!workflowId) {
      errorToast("Please create a workflow");
      return;
    }
    get().setLoading(true);
    try {
      const response: any = await AppRequest.Post(
        `${tempApiBaseUrl}/benchmark/run-workflow`,
        {
          ...get().stepOneData,
          step_number: 6,
          trigger_workflow: false,
          workflow_id: workflowId,
          credential_id: credentials?.id,
        },
      );
      get().getWorkflow();
      // successToast(response.data.message);
    } catch (error) {
      console.error("Error creating model:", error);
    } finally {
      get().setLoading(false);
    }
  },
  stepSix: async () => {
    const workflowId = get().currentWorkflow?.workflow_id;
    const modelId = get().selectedModel?.id;
    if (!modelId) {
      errorToast("Please select model");
      return;
    }
    get().setLoading(true);
    try {
      const response: any = await AppRequest.Post(
        `${tempApiBaseUrl}/benchmark/run-workflow`,
        {
          ...get().stepOneData,
          workflow_id: workflowId,
          step_number: 8,
          // "trigger_workflow": false,
        },
      );
      get().getWorkflow();
      // successToast(response.data.message);
      return response;
    } catch (error) {
      console.error("Error creating model:", error);
    } finally {
      get().setLoading(false);
    }
  },
  stepSeven: async () => {
    const workflowId = get().currentWorkflow?.workflow_id;
    const modelId = get().selectedModel?.id;
    if (!modelId) {
      errorToast("Please select nodes");
      return;
    }
    get().setLoading(true);
    try {
      const response: any = await AppRequest.Post(
        `${tempApiBaseUrl}/benchmark/run-workflow`,
        {
          ...get().stepOneData,
          workflow_id: workflowId,
          step_number: 8,
          // "trigger_workflow": false,
          user_confirmation: true,
        },
      );
      get().getWorkflow();
      // successToast(response.data.message);
      return response;
    } catch (error) {
      console.error("Error creating model:", error);
    } finally {
      get().setLoading(false);
    }
  },
  stepEight: async () => {
    const workflowId = get().currentWorkflow?.workflow_id;
    const simulation = get().runAsSimulation;
    const modelId = get().selectedModel?.id;
    get().setLoading(true);
    try {
      const response: any = await AppRequest.Post(
        `${tempApiBaseUrl}/benchmark/run-workflow`,
        {
          ...get().stepOneData,
          workflow_id: workflowId,
          step_number: 9,
          // "trigger_workflow": false,
          run_as_simulation: simulation,
          trigger_workflow: true,
          model_id: modelId,
          provider_type: "",
          simulator_id: "",
        },
      );
      get().getWorkflow();
      // successToast(response.data.message);
      return response;
    } catch (error) {
      console.error("Error creating model:", error);
    } finally {
      get().setLoading(false);
    }
  },

  // Node Configuration methods
  fetchNodeConfigurations: async () => {
    const clusterId = get().selectedCluster?.id;
    const modelId = get().selectedModel?.id;
    const nodes = get().selectedNodes;
    const hardwareMode = get().hardwareMode;
    const stepTwoData = get().stepTwoData;

    if (!clusterId || !modelId || !nodes.length) {
      errorToast("Missing required data for configuration options");
      return null;
    }

    // Extract hostnames from selected nodes
    const hostnames = nodes
      .map((node) => node.hostname)
      .filter((h): h is string => !!h);

    if (!hostnames.length) {
      errorToast("No valid hostnames found in selected nodes");
      return null;
    }

    set({ loadingConfigurations: true });
    try {
      const response: any = await AppRequest.Post(
        `${tempApiBaseUrl}/benchmark/node-configurations`,
        {
          model_id: modelId,
          cluster_id: clusterId,
          hostnames: hostnames,
          hardware_mode: hardwareMode || "dedicated",
          input_tokens: stepTwoData?.max_input_tokens
            ? parseInt(stepTwoData.max_input_tokens)
            : 1024,
          output_tokens: stepTwoData?.max_output_tokens
            ? parseInt(stepTwoData.max_output_tokens)
            : 512,
          concurrency: get().stepOneData?.concurrent_requests || 10,
        },
      );
      if (response?.data) {
        set({ nodeConfigurations: response.data });
        return response.data as NodeConfigurationResponse;
      }
      return null;
    } catch (error) {
      console.error("Error fetching node configurations:", error);
      errorToast("Failed to fetch configuration options");
      return null;
    } finally {
      set({ loadingConfigurations: false });
    }
  },

  setSelectedConfiguration: (config: SelectedConfiguration | null) => {
    set({ selectedConfiguration: config });
  },

  stepConfigurationOptions: async () => {
    const workflowId = get().currentWorkflow?.workflow_id;
    const config = get().selectedConfiguration;

    if (!config) {
      errorToast("Please select a configuration");
      return;
    }

    get().setLoading(true);
    try {
      const response: any = await AppRequest.Post(
        `${tempApiBaseUrl}/benchmark/run-workflow`,
        {
          ...get().stepOneData,
          workflow_id: workflowId,
          step_number: 7,
          trigger_workflow: false,
          selected_device_type: config.device_type,
          tp_size: config.tp_size,
          pp_size: config.pp_size,
          replicas: config.replicas,
        },
      );
      get().getWorkflow();
      return response;
    } catch (error) {
      console.error("Error saving configuration options:", error);
      errorToast("Failed to save configuration options");
    } finally {
      get().setLoading(false);
    }
  },
}));

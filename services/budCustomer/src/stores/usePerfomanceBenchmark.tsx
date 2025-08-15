import { create } from "zustand";
import { WorkflowType } from "./useWorkflow";

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
  selectedCluster: any | null;
  selectedNodes: Node[];
  selectedDataset: Dataset[];
  selectedModel: any | null;
  runAsSimulation: boolean;
  benchmarks: Benchmark[];
  currentWorkflow: WorkflowType | null;
  currentWorkflowId: null;
  selectedCredentials: any | null;
  totalDataset: number | null;
  reset: () => void;
  setSelectedCredentials: (credentials: any | null) => void;
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
  setSelectedModel: (model: any) => void;
  createBenchmark: (data: CreateForm) => any;
  stepTwo: (data: StepTwo) => any;
  stepTwoDataset: () => any;
  stepThree: () => any;
  stepFour: () => any;
  stepFive: () => any;
  updateCredentials: (credentials: any) => any;
  stepSix: () => any;
  stepSeven: () => any;
  stepEight: () => any;
}>((set, get) => ({
  filters: {},
  totalPages: 0,
  totalUsers: 0,
  evalWith: "",
  dataset: [],
  nodeMetrics: null,
  filteredNodeMetrics: null,
  searchText: "",
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
  totalDataset: null,
  loading: false,

  setSelectedCredentials: (credentials: any | null) => {
    set({ selectedCredentials: credentials });
  },

  setSelectedModel: (model: any) => {
    set({ selectedModel: model });
  },

  setNodeMetrics: (nodeMetrics: any) => {
    set({ nodeMetrics: nodeMetrics });
    set({ filteredNodeMetrics: get().nodeMetrics });
  },

  setSearchText: (text: string) => {
    set({ searchText: text });
  },

  setFilteredNodes: (text: string) => {
    get().setSearchText(text);
    let nodeMetrics = get().nodeMetrics;
    const filtered = Object.values(nodeMetrics || {}).filter((node: any) =>
      node.hostname?.toLowerCase().includes(get().searchText.toLowerCase()),
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
    });
  },

  getDataset: async (params: any) => {
    // Stub implementation
  },

  getWorkflow: async (id?: string) => {
    // Stub implementation
    return {};
  },

  setLoading: (loading: boolean) => set({ loading }),

  deleteWorkflow: async (id: string, suppressToast?: boolean) => {
    // Stub implementation
    return {};
  },

  createWorkflow: (projectId: string) => {
    // Stub implementation
  },

  setSelectedCluster: (cluster: any) => {
    set({ selectedCluster: cluster });
  },

  setSelecteUnselectAll: (selectAll: boolean) => {
    if (selectAll) {
      set({ selectedNodes: [] });
    } else {
      let nodes = get().filteredNodeMetrics;
      Object.keys(nodes || {}).map((key, index) =>
        get().setSelectedNodes(nodes[key]),
      );
    }
  },

  setSelectedNodes: (node: Node) => {
    set((state) => {
      const isAlreadySelected = state.selectedNodes.some(
        (selected) => selected.hostname === node.hostname,
      );

      return {
        selectedNodes: isAlreadySelected
          ? state.selectedNodes.filter(
              (selected) => selected.hostname !== node.hostname,
            )
          : [...state.selectedNodes, node],
      };
    });
  },

  setSelectedDataset: (dataset: Dataset) => {
    set((state) => {
      const isAlreadySelected = state.selectedDataset.some(
        (selected) => selected.id === dataset.id,
      );

      return {
        selectedDataset: isAlreadySelected
          ? state.selectedDataset.filter(
              (selected) => selected.id !== dataset.id,
            )
          : [...state.selectedDataset, dataset],
      };
    });
  },

  setSelecteUnselectAllDataset: (selectAll: boolean) => {
    if (selectAll) {
      set({ selectedDataset: [] });
    } else {
      let nodes = get().dataset;
      set({ selectedDataset: nodes });
    }
  },

  // Stub implementations for all step methods
  createBenchmark: async (data: CreateForm) => {},
  stepTwo: async (data: StepTwo) => {},
  stepTwoDataset: async () => {},
  stepThree: async () => {},
  stepFour: async () => {},
  stepFive: async () => {},
  updateCredentials: async (credentials: any) => {},
  stepSix: async () => {},
  stepSeven: async () => {},
  stepEight: async () => {},
}));

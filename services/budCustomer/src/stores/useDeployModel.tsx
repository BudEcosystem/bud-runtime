import { create } from "zustand";
import { WorkflowType } from "./useWorkflow";

export type ModalityType = {
  id: string;
  type?: string[];
  icon: string;
  name: string;
  description: string;
};

export type ProviderType = {
  id: string;
  icon: string;
  name: string;
  title?: string;
  description: string;
  type?: string;
};

export type QuantizeConfig = {
  bit: number;
  granularity: string;
  symmetric: boolean;
};

type QuantizationWorkflow = {
  modelName: string;
  type: string;
  hardware: string;
  method: string;
  weight: QuantizeConfig;
  activation: QuantizeConfig;
  clusterId: string;
};

type QuantizationMethod = {
  name: string;
  description: string;
  hardware_support: string[];
  method_type: string[];
  runtime_hardware_support: string[];
};

type AdapterWorkflow = {
  adapterName: string;
  adapterModelId: string;
  endpointId: string;
  adapterId: string;
};

export const useDeployModel = create<{
  requestCount: any | null;
  currentWorkflow: WorkflowType | null;
  setCurrentWorkflow: (workflow: WorkflowType) => void;
  selectedModel: any | null;
  setSelectedModel: (model: any) => void;
  selectedTemplate: any | null;
  deploymentCluster: any;
  providerType: ProviderType | null;
  modalityType: ModalityType | null;
  selectedProvider: any | null;
  providerTypeList: ProviderType[];
  modalityTypeList: ModalityType[];
  deploymentSpecifcation: {
    deployment_name: string;
    concurrent_requests: number;
    avg_context_length: number;
    avg_sequence_length: number;
    per_session_tokens_per_sec: number[];
    ttft: number[];
    e2e_latency: number[];
  };
  scalingSpecifcation: {
    scalingType: string;
    scalingMetric: string;
    scalingValue: number;
    minReplicas: number;
    maxReplicas: number;
    scaleUpTolerance: number;
    scaleDownTolerance: number;
    window: number;
  };
  cloudModelDetails: {
    name: string;
    tags: { name: string; color: string }[];
    modality: string[];
    uri?: string;
  };
  status: any;
  providerName: string;
  selectedCredentials: any | null;
  quantizationWorkflow: QuantizationWorkflow | null;
  quantizationMethods: QuantizationMethod[];
  adapterWorkflow: AdapterWorkflow | null;
  setSelectedCredentials: (credentials: any | null) => void;
  setSelectedProvider: (provider: any) => void;
  setDeploymentSpecification: (spec: any) => void;
  setScalingSpecification: (spec: any) => void;
  setCloudModelDetails: (details: any) => void;
  setSelectedTemplate: (template: any) => void;
  setDeploymentCluster: (cluster: any) => void;
  setProviderType: (id: string) => void;
  setModalityType: (id: any) => void;
  setStatus: (status: any) => void;
  setQuantizationWorkflow: (workflow: QuantizationWorkflow | null) => void;
  setQuantizationMethods: (methods: QuantizationMethod[]) => void;
  setAdapterWorkflow: (workflow: AdapterWorkflow | null) => void;
  reset: () => void;
  createWorkflow: (projectId: string) => void;
  updateModel: () => void;
  updateTemplate: () => void;
  getWorkflow: (id?: string) => Promise<any>;
  updateDeploymentSpecification: () => Promise<any>;
  updateScalingSpecification: () => Promise<any>;
  updateCluster: () => Promise<any>;
  createCloudModelWorkflow: () => any;
  updateProviderType: () => any;
  updateProvider: () => any;
  updateCredentials: (credentials: any) => any;
  updateCloudModel: () => Promise<any>;
  updateCloudModelDetails: () => Promise<any>;
  getWorkflowCloud: (id?: string) => Promise<any>;
  createLocalModelWorkflow: () => any;
  createModalityForWorkflow: () => any;
  updateProviderTypeLocal: () => Promise<any>;
  updateModelDetailsLocal: (data: {
    name: any;
    tags: any;
    author: any;
    uri: any;
    icon?: string;
  }) => Promise<any>;
  updateCredentialsLocal: (credentials: any) => Promise<any>;
  localModelDetails: any;
  setLocalModelDetails: (details: any) => void;
  startSecurityScan: () => Promise<any>;
  cancelModelDeployment: (id: string, projectId?: string) => Promise<any>;
  loading: boolean;
  setLoading: (loading: boolean) => void;
  deleteWorkflow: (id: string, suppressToast?: boolean) => Promise<any>;
  cancelClusterOnboarding: (id: string) => Promise<any>;
  workerDetails: any;
  setWorkerDetails: (details: any) => void;
  createWorkerFlow: (
    endpointId: string,
    additionalConcurrency: number,
    projectId?: string
  ) => Promise<any>;
  completeCreateWorkerFlow: (workflowId: string, projectId?: string) => Promise<any>;
  getQuantizationMethods: () => Promise<any>;
  createQuantizationWorkflow: (
    model_name: string,
    type: string,
    hardware: string
  ) => Promise<any>;
  updateQuantizationMethod: (method: string) => Promise<any>;
  updateQuantizationAdvanced: (
    weight: QuantizeConfig,
    activation: QuantizeConfig
  ) => Promise<any>;
  updateQuantizationCluster: (clusterId: string) => Promise<any>;
  cancelQuantizationDeployment: (id: string) => Promise<any>;
  createAddAdapterWorkflow: (
    endpointId: string,
    adapterModelId: string,
    projectId?: string
  ) => Promise<any>;
  updateAdapterDetailWorkflow: (adapterName: string, projectId?: string) => Promise<any>;
  startRequest: () => void;
  endRequest: () => void;
}>((set, get) => ({
  loading: false,
  setLoading: (loading: boolean) => {
    set({ loading });
  },
  workerDetails: {},
  setWorkerDetails: (details: any) => {
    set({ workerDetails: details });
  },
  providerType: null,
  modalityType: null,
  currentWorkflow: null,
  selectedProvider: null,
  setCurrentWorkflow: (workflow: WorkflowType) => {
    set({ currentWorkflow: workflow });
  },
  selectedModel: null,
  setSelectedModel: (model: any) => {
    set({ selectedModel: model });
  },
  selectedTemplate: null,
  setSelectedTemplate: (template: any) => {
    set({ selectedTemplate: template });
  },
  setProviderType: (id: string) => {
    set({
      providerType: get().providerTypeList.find(
        (provider) => provider.id === id
      ),
    });
  },
  setModalityType: (id: any) => {
    set({
      modalityType: get().modalityTypeList.find(
        (modality) => modality.id === id
      ),
    });
  },
  deploymentSpecifcation: {
    deployment_name: "",
    concurrent_requests: 0,
    avg_context_length: 0,
    avg_sequence_length: 0,
    per_session_tokens_per_sec: [],
    ttft: [],
    e2e_latency: [],
  },
  scalingSpecifcation: {
    scalingType: "metric",
    scalingMetric: "bud:time_to_first_token_seconds_average",
    scalingValue: 1,
    minReplicas: 1,
    maxReplicas: 1,
    scaleUpTolerance: 1.5,
    scaleDownTolerance: 0.5,
    window: 60,
  },
  cloudModelDetails: {
    name: "",
    tags: [],
    modality: [],
    uri: "",
  },
  setDeploymentSpecification: (spec: any) => {
    set({ deploymentSpecifcation: spec });
  },
  setScalingSpecification: (spec: any) => {
    set({ scalingSpecifcation: spec });
  },
  setCloudModelDetails: (details: any) => {
    set({ cloudModelDetails: details });
  },
  setSelectedProvider: (provider: any) => {
    set({ selectedProvider: provider });
  },
  deploymentCluster: {},
  setDeploymentCluster: (cluster: any) => {
    set({ deploymentCluster: cluster });
  },
  status: null,
  setStatus: (status: any) => {
    set({ status });
  },
  providerName: "",
  selectedCredentials: null,
  setSelectedCredentials: (credentials: any | null) => {
    set({ selectedCredentials: credentials });
  },
  quantizationWorkflow: null,
  quantizationMethods: [],
  adapterWorkflow: null,
  setQuantizationWorkflow: (workflow: QuantizationWorkflow | null) => {
    set({ quantizationWorkflow: workflow });
  },
  setQuantizationMethods: (methods: QuantizationMethod[]) => {
    set({ quantizationMethods: methods });
  },
  setAdapterWorkflow: (workflow: AdapterWorkflow | null) => {
    set({ adapterWorkflow: workflow });
  },
  localModelDetails: null,
  setLocalModelDetails: (details: any) => {
    set({ localModelDetails: details });
  },
  requestCount: null,
  providerTypeList: [
    {
      id: "cloud_model",
      icon: "/images/drawer/cloud-2.png",
      name: "Cloud",
      description: "Models from various cloud providers",
    },
    {
      id: "hugging_face",
      icon: "/images/drawer/huggingface.png",
      name: "Hugging Face",
      title: "Add Huggingface model",
      description: "Download from Hugging Face",
    },
    {
      id: "url",
      icon: "/images/drawer/url-2.png",
      name: "URL",
      title: "Add model from URL",
      description: "Provide a URL to download model",
    },
    {
      id: "disk",
      icon: "/images/drawer/disk-2.png",
      name: "Disk",
      title: "Add model from Disk",
      description: "Add from Disk",
    },
  ],
  modalityTypeList: [
    {
      id: "1",
      type: ["llm", "mllm"],
      icon: "/images/drawer/brain.png",
      name: "LLM, Multi-Model LLM",
      description: "Add LLM, Multi-Model LLM",
    },
    {
      id: "2",
      type: ["embedding"],
      icon: "/images/drawer/embedding.png",
      name: "Embedding models",
      description: "Add Embedding models",
    },
    {
      id: "speech_to_text",
      icon: "/images/drawer/speachToText.png",
      name: "Speech to text",
      description: "Add Speech to text models",
    },
    {
      id: "text_to_speech",
      icon: "/images/drawer/textToSpeach.png",
      name: "Text to Speech",
      description: "Add Text to Speech models",
    },
    {
      id: "action_transformers",
      icon: "/images/drawer/compare.png",
      name: "Action Transformers",
      description: "Add Action Transformers models",
    },
  ],
  reset: () => {
    set({
      selectedModel: null,
      selectedTemplate: null,
      deploymentSpecifcation: {
        deployment_name: "",
        concurrent_requests: 0,
        avg_context_length: 0,
        avg_sequence_length: 0,
        per_session_tokens_per_sec: [],
        ttft: [],
        e2e_latency: [],
      },
      scalingSpecifcation: {
        scalingType: "metric",
        scalingMetric: "bud:time_to_first_token_seconds_average",
        scalingValue: 1,
        minReplicas: 1,
        maxReplicas: 1,
        scaleUpTolerance: 1.5,
        scaleDownTolerance: 0.5,
        window: 60,
      },
      deploymentCluster: {},
      currentWorkflow: null,
      status: null,
      selectedProvider: null,
      providerType: null,
      modalityType: null,
      cloudModelDetails: {
        name: "",
        tags: [],
        modality: [],
        uri: "",
      },
      localModelDetails: null,
      selectedCredentials: null,
      quantizationWorkflow: null,
      adapterWorkflow: null,
    });
  },
  // Stub implementations for all methods
  createWorkflow: async (projectId: string) => {},
  updateModel: async () => {},
  updateTemplate: async () => {},
  getWorkflow: async (id?: string) => ({}),
  updateDeploymentSpecification: async () => ({}),
  updateScalingSpecification: async () => ({}),
  updateCluster: async () => ({}),
  createCloudModelWorkflow: () => {},
  updateProviderType: () => {},
  updateProvider: () => {},
  updateCredentials: (credentials: any) => {},
  updateCloudModel: async () => ({}),
  updateCloudModelDetails: async () => ({}),
  getWorkflowCloud: async (id?: string) => ({}),
  createLocalModelWorkflow: () => {},
  createModalityForWorkflow: () => {},
  updateProviderTypeLocal: async () => ({}),
  updateModelDetailsLocal: async (data: any) => ({}),
  updateCredentialsLocal: async (credentials: any) => ({}),
  startSecurityScan: async () => ({}),
  cancelModelDeployment: async (id: string, projectId?: string) => ({}),
  deleteWorkflow: async (id: string, suppressToast?: boolean) => ({}),
  cancelClusterOnboarding: async (id: string) => ({}),
  createWorkerFlow: async (
    endpointId: string,
    additionalConcurrency: number,
    projectId?: string
  ) => ({}),
  completeCreateWorkerFlow: async (workflowId: string, projectId?: string) => ({}),
  getQuantizationMethods: async () => ({}),
  createQuantizationWorkflow: async (
    model_name: string,
    type: string,
    hardware: string
  ) => ({}),
  updateQuantizationMethod: async (method: string) => ({}),
  updateQuantizationAdvanced: async (
    weight: QuantizeConfig,
    activation: QuantizeConfig
  ) => ({}),
  updateQuantizationCluster: async (clusterId: string) => ({}),
  cancelQuantizationDeployment: async (id: string) => ({}),
  createAddAdapterWorkflow: async (
    endpointId: string,
    adapterModelId: string,
    projectId?: string
  ) => ({}),
  updateAdapterDetailWorkflow: async (adapterName: string, projectId?: string) => ({}),
  startRequest: () => {},
  endRequest: () => {},
}));
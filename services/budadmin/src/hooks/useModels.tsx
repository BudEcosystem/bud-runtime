import { tempApiBaseUrl } from "@/components/environment";
import { AppRequest } from "src/pages/api/requests";
import { create } from "zustand";
import { Provider } from "./useCloudProviders";

type LeaderBoardValue = {
  type: string;
  label: string;
  value: number;
};

export const cloudProviders = [
  { modality: "text_input", label: "Text Input" },
  { modality: "text_output", label: "Text Output" },
  { modality: "image_input", label: "Image Input" },
  { modality: "image_output", label: "Image Output" },
  { modality: "audio_input", label: "Audio Input" },
  { modality: "audio_output", label: "Audio Output" },
];

export type LeaderBoardBenchmark = {
  [key: string]: LeaderBoardValue;
};

export type LeaderBoardItem = {
  model: {
    uri: string;
    model_size: number;
    is_selected: boolean;
  };
  benchmarks: LeaderBoardBenchmark;
};

type License = {
  id: string;
  name: string;
  path: string;
  url: string;
  model_id: string;
  data_type: string;
  license_type: string;
  description: string;
  suitability: string;
  faqs: {
    answer: string;
    question: string;
    description: string;
  }[];
};

export type PaperPublished = {
  id: string;
  model_id: string;
  title: string;
  url: string;
  authors?: string[];
};

export type ModelIssue = {
  title: string;
  source: string;
  severity: string;
  description: string;
};

type CreatedUser = {
  name: string;
  email: string;
  id: string;
  color: string;
  role: string;
};

export type ScanResult = {
  status: string;
  total_issues: number;
  total_scanned_files: number;
  total_skipped_files: number;
  low_severity_count: number;
  medium_severity_count: number;
  high_severity_count: number;
  critical_severity_count: number;
  model_id: string;
  scanned_files: string[];
  model_issues: {
    critical: ModelIssue[];
    high: ModelIssue[];
    medium: ModelIssue[];
    low: ModelIssue[];
  };
  id: string;
  created_at: string;
  modified_at: string;
};

type EndpointInfo = {
  path: string;
  enabled: boolean;
  label: string;
};

export type Model = {
  provider: Provider;
  provider_type: string;
  is_present_in_model?: boolean;
  id: string;
  name: string;
  author: string;
  modality: {
    audio: { input: boolean; output: boolean; label: string };
    image: { input: boolean; output: boolean; label: string };
    text: { input: boolean; output: boolean; label: string };
  };
  supported_endpoints: {
    chat: EndpointInfo;
    completion: EndpointInfo;
    image_generation: EndpointInfo;
    audio_transcription: EndpointInfo;
    audio_speech: EndpointInfo;
    embedding: EndpointInfo;
    batch: EndpointInfo;
    response: EndpointInfo;
    rerank: EndpointInfo;
    moderation: EndpointInfo;
  };
  type?: string;
  source: string;
  uri: string;
  created_user?: CreatedUser;
  model_size: number;
  tasks: {
    name: string;
    color: string;
  }[];
  tags: {
    name: string;
    color: string;
  }[];
  icon: string;
  languages: string[];
  use_cases: string[];
  family: string;
  kv_cache_size: number;
  description: string;
  model_licenses?: License;
  paper_published?: PaperPublished[];
  modified_at?: string;
  endpoints_count?: number;
  model_cluster_recommended?: any;
  adapters_count?: number;
  finetunes_count?: number;
  merges_count?: number;
  quantizations_count?: number;
  minimum_requirements?: any;
  strengths?: any;
  limitations?: any;
  num_attention_heads?: any;
  model_weights_size?: number;
  base_model?: string[];
  architecture_text_config?: {
    context_length: number;
    hidden_size: number;
    intermediate_size: number;
    num_attention_heads: number;
    num_key_value_heads: number;
    num_layers: number;
    rope_scaling: {
      factor: number;
      high_freq_factor: number;
      low_freq_factor: number;
      original_max_position_embeddings: number;
      rope_type: string;
    };
    torch_dtype: string;
    vocab_size: number;
  };
  architecture_vision_config?: {
    hidden_size: number;
    intermediate_size: number;
    num_layers: number;
    torch_dtype: string;
  };
  examples?: any[];
  bud_verified: boolean;
  scan_verified: boolean;
  eval_verified: boolean;
  eval_result?: {} | null;
  scan_result?: ScanResult | null;
  github_url?: string;
  huggingface_url?: string;
  website_url?: string;
  model_type?: string;
  created_at?: string;
};

export interface IModel {
  model: Model;
  endpoints_count: number;
}

type GetModelParams = {
    page: number;
    limit: number;
    order_by?: string;
    name?: string;
    description?: string;
    tag?: string;
    tasks?: string[]
    modality?: string[];
    author?: string[];
    model_size_min?: number;
    model_size_max?: number;
    table_source?: "model" | "cloud_model";
    search?: string;
    source?: string;
    base_model?: string;
    base_model_relation?: string;
    supported_endpoints?: string[];
    exclude_adapters?: boolean;
};

// create zustand store
export const useModels = create<{
  tasks: any[];
  models: Model[];
  authors: string[];
  loading: boolean;
  selectedModel: Model | null;
  selectedModelId: string;
  totalPages: number;
  totalModels: number;
  getGlobalModels: (parms: GetModelParams) => void;
  getModel: (modelId: string) => any;
  setSelectedModel: (model: Model) => void;
  modelValues: any;
  setModelValues: (values: any) => void;
  updateModel: (modelId: string, data: any) => Promise<any>;
  getTasks: () => void;
  getAuthors: () => void;
  filters: any;
  refresh: () => void;
  fetchModels: (params: GetModelParams) => Promise<Model[]>;
  deleteModel: (modelId: string) => Promise<any>;
  getLeaderBoard: (modelId: string) => Promise<LeaderBoardItem[]>;
}>((set, get) => ({
  tasks: [],
  models: [],
  authors: [],
  loading: true,
  selectedModel: null,
  totalPages: 0,
  totalModels: 0,
  selectedModelId: "",
  getLeaderBoard: async (modelId: string) => {
    try {
      const response: any = await AppRequest.Get(
        `${tempApiBaseUrl}/models/${modelId}/leaderboards`,
        {
          params: {
            table_source: "model",
            k: 10,
          },
        },
      );
      return (
        response.data?.leaderboards || [
          {
            model: {
              uri: "HuggingFaceH4/zephyr-7b-beta",
              model_size: 1000000000,
              is_selected: true,
            },
            benchmarks: {
              bcfl: {
                type: "Tool Use",
                label: "BCFL",
                value: 10,
              },
              live_code_bench: {
                type: "Code Generation",
                label: "Live Code Bench",
                value: 10,
              },
              classification: {
                type: "Classification",
                label: "Classification",
                value: 10,
              },
              clustering: {
                type: "Clustering",
                label: "Clustering",
                value: 10,
              },
              pair_classification: {
                type: "Classification",
                label: "Pair Classification",
                value: 10,
              },
              reranking: {
                type: "Reranking",
                label: "Reranking",
                value: 10,
              },
              retrieval: {
                type: "Retrieval",
                label: "Retrieval",
                value: 10,
              },
              semantic: {
                type: "Semantic",
                label: "Semantic",
                value: 10,
              },
              summarization: {
                type: "Summarization",
                label: "Summarization",
                value: 10,
              },
              mmbench: {
                type: "Reasoning",
                label: "MMBench",
                value: 10,
              },
              mmstar: {
                type: "Reasoning",
                label: "MMStar",
                value: 10,
              },
              mmmu: {
                type: "Knowledge",
                label: "MMMU",
                value: 10,
              },
              math_vista: {
                type: "Math",
                label: "Math Vista",
                value: 10,
              },
              ocr_bench: {
                type: "OCR",
                label: "OCRBench",
                value: 10,
              },
              ai2d: {
                type: "Visual QA",
                label: "AI2D",
                value: 500,
              },
              hallucination_bench: {
                type: "Hallucination",
                label: "HallucinationBench",
                value: 200,
              },
              mmvet: {
                type: "Visual QA",
                label: "MMVet",
                value: 300,
              },
              lmsys_areana: {
                type: "Human Preference",
                label: "LMSYS Areana",
                value: 1269,
              },
            },
          },
        ]
      );
    } catch (error) {
      console.error("Error creating model:", error);
    }
  },
  setSelectedModel: (model: Model) => {
    set({ selectedModel: model });
  },
  fetchModels: async (params: GetModelParams) => {
    Object.keys(params).forEach((key) => {
      if (!params[key]) {
        delete params[key];
      }
    });

    set({ loading: true });
    try {
      const response: any = await AppRequest.Get(`${tempApiBaseUrl}/models\\`, {
        params: {
          ...params,
          search: Boolean(params.name),
          order_by: "-created_at",
        },
      });
      set({
        totalPages: response.data.total_pages,
        totalModels: response.data.total_record,
      });
      const listData = response.data.models;
      const updatedListData = listData.map((item) => {
        return {
          ...item.model,
          endpoints_count: item.endpoints_count,
        };
      });
      return updatedListData;
    } catch (error) {
      console.error("Error creating model:", error);
    } finally {
      set({ loading: false });
    }
  },
  getGlobalModels: async (params: GetModelParams) => {
    let updatedListData = await get().fetchModels(params);
    if (params.page !== 1) {
      updatedListData = [...get().models, ...updatedListData];
    }
    set({ models: updatedListData, filters: params });
  },
  getModel: async (modelId: string) => {
    set({ loading: true });
    try {
      set({ selectedModel: null });
      const response: any = await AppRequest.Get(
        `${tempApiBaseUrl}/models/${modelId}`,
      );
      set({
        selectedModel: {
          ...response.data.model,
          ...response.data.model_tree,
          endpoints_count: response.data.endpoints_count,
          eval_result: response.data.eval_result,
          scan_result: response.data.scan_result,
        },
      });
      set({ loading: true });
      return response.data;
    } catch (error) {
      set({ loading: true });
      console.error("Error creating model:", error);
    }
  },
  updateModel: async (modelId: string, data: any) => {
    try {
      const response: any = await AppRequest.Patch(
        `${tempApiBaseUrl}/models/${modelId}`,
        data,
      );
      return response.data;
    } catch (error) {
      console.error("Error creating model:", error);
    }
  },
  modelValues: {},
  setModelValues: (values: any) => {
    set({ modelValues: values });
  },
  getTasks: async () => {
    try {
      const response: any = await AppRequest.Get(
        `${tempApiBaseUrl}/models/tasks`,
      );
      set({ tasks: response.data?.tasks });
    } catch (error) {
      console.error("Error creating model:", error);
    }
  },
  getAuthors: async () => {
    try {
      const response: any = await AppRequest.Get(
        `${tempApiBaseUrl}/models/authors`,
        {
          params: {
            page: 1,
            limit: 1000,
          },
        },
      );
      set({ authors: response.data?.authors });
    } catch (error) {
      console.error("Error creating model:", error);
    }
  },
  filters: {},
  refresh: () => {
    get().getGlobalModels(get().filters);
  },
  deleteModel: async (modelId: string) => {
    try {
      const response: any = await AppRequest.Delete(
        `${tempApiBaseUrl}/models/${modelId}`,
      );
      return response.data;
    } catch (error) {
      console.error("Error creating model:", error);
    }
  },
}));

import { tempApiBaseUrl } from "@/components/environment";
import { errorToast, successToast } from "@/components/toast";
import { WorkflowType } from "@/stores/useWorkflow";
import { AppRequest } from "src/pages/api/requests";
import { create } from "zustand";


export interface GetEvaluationsPayload {
  page?: number;
  limit?: number;
  name?: string;
  modalities?: string;
  language?: string;
  domains?: string;
  trait_ids?: string[];
}

export interface GetExperimentsPayload {
  page?: number;
  limit?: number;
  search?: string;
  experiment_status?: string;
  tags?: string[];
  order?: string;
  orderBy?: string;
  model_id?: string;
  created_before?: string;
  created_after?: string;
}

export interface ExperimentData {
  id: string;
  name?: string;
  experimentName?: string;
  models: string | any[] | any;  // Can be string, array, or object
  traits: string | any[] | any;  // Can be string, array, or object
  tags: string[] | any[];
  status: "Running" | "Completed" | "Failed" | string;
  created_at: string;
}

export interface Trait {
  id: string;
  name: string;
  description: string;
  category: string;
  exps_ids: string[];
  datasets: any[];
}

export interface DatasetInfo {
  id: string;
  name: string;
  description: string;
  estimated_input_tokens: number;
  estimated_output_tokens: number;
  modalities: string[];
  sample_questions_answers: {
    format: string;
    sample_count: number;
  };
  advantages_disadvantages: any | null;
}

export interface TraitWithDatasets extends Trait {
  datasets: DatasetInfo[];
}

export interface TraitSimple {
  id: string;
  name: string;
  description: string;
  category: string;
  exps_ids: string[];
}

export interface ExperimentTags {
  name: string;
  color: string;
}

export interface MetaLinks {
  manifest_id: string;
  github?: string;
  paper?: string;
  papers?: string[];
  website?: string;
  author?: string;
  author_url?: string;
  website_url?: string;
  create_date?: string;
  creator?: {
    avatar?: string;
    name?: string;
    nickname?: string;
    uid?: string;
  }
}

export interface SampleQuestionsAnswers {
  format: string;
  sample_count: number;
}

export interface Evaluation {
  id: string;
  name: string;
  description: string;
  meta_links: MetaLinks;
  config_validation_schema: any | null;
  estimated_input_tokens: number;
  estimated_output_tokens: number;
  language: string[];
  domains: string[];
  concepts: any | null;
  humans_vs_llm_qualifications: any | null;
  task_type: string[];
  modalities: string[];
  sample_questions_answers: SampleQuestionsAnswers;
  advantages_disadvantages: any | null;
  traits: Trait[];
}

// create zustand store
export const useEvaluations = create<{
  loading: boolean;
  experimentLoading: boolean;
  evaluationsList: Evaluation[];
  selectedEvals: Evaluation[];
  evaluationsListTotal: number;
  traitsList: TraitSimple[];
  experimentsList: ExperimentData[];
  experimentsListTotal: number;
  experimentTags: ExperimentTags[];
  experimentDetails: any;
  experimentMetrics: any;
  experimentBenchmarks: any;
  experimentRuns: any;
  currentWorkflow: WorkflowType | null;
  currentWorkflowId: string | null;
  workflowData: any;
  evaluationDetails: any;
  experimentModels: any;
  experimentSummary: any;

  setSelectedEvals: (evaluation: any) => void;
  getEvaluations: (payload?: GetEvaluationsPayload) => Promise<any>;
  getEvaluationDetails: (datasetId: string) => Promise<any>;
  getTraits: (payload?: any) => Promise<any>;
  getExperiments: (payload?: GetExperimentsPayload) => Promise<any>;
  getExperimentTags: () => Promise<any>;
  getExperimentDetails: (id: string) => Promise<any>;
  getExperimentRuns: (id: string) => Promise<any>;
  createExperiment: (payload: any) => Promise<any>;
  createWorkflow: (experimentId: string, payload: any) => Promise<any>;
  getWorkflow: (id?: string) => Promise<any>;
  setCurrentWorkflow: (workflow: WorkflowType | null) => void;
  getCurrentWorkflow: () => WorkflowType | null;
  getWorkflowData: (experimentId: string, workflowId: string) => Promise<any>;
  deleteWorkflow: (id: string, suppressToast?: boolean) => Promise<any>;
  getExperimentModels: () => Promise<any>;
  getExperimentSummary: (id) => Promise<any>
}>((set, get) => ({
  loading: false,
  experimentLoading: false,
  selectedEvals: [],
  evaluationsList: [],
  traitsList: [],
  evaluationsListTotal: 0,
  experimentsList: [],
  experimentsListTotal: 0,
  experimentTags: [],
  experimentDetails: null,
  experimentMetrics: null,
  experimentBenchmarks: null,
  experimentRuns: null,
  currentWorkflow: null,
  currentWorkflowId: null,
  workflowData: null,
  evaluationDetails: null,
  experimentModels: [],
  experimentSummary: null,

  getEvaluations: async (payload) => {
    set({ loading: true });
    try {
      // Build query parameters
      const params = new URLSearchParams();

      if (payload?.page) params.append('page', payload.page.toString());
      if (payload?.limit) params.append('limit', payload.limit.toString());
      if (payload?.name) params.append('name', payload.name);
      if (payload?.modalities) params.append('modalities', payload.modalities);
      if (payload?.language) params.append('language', payload.language);
      if (payload?.domains) params.append('domains', payload.domains);
      if (payload?.trait_ids && payload.trait_ids.length > 0) {
        params.append('trait_ids', payload.trait_ids.join(','));
      }

      const queryString = params.toString();
      const url = `${tempApiBaseUrl}/experiments/datasets${queryString ? `?${queryString}` : ''}`;

      const response: any = await AppRequest.Get(url);
      set({ evaluationsList: response.data.datasets });
      set({ evaluationsListTotal: response.data.total_record });
    } catch (error) {
      console.error("Error fetching evaluations:", error);
    } finally {
      set({ loading: false });
    }
  },

  setSelectedEvals: (evaluation: Evaluation[]) => {
    set({ selectedEvals: evaluation });
  },

  getEvaluationDetails: async (datasetId: string) => {
    set({ loading: true });
    try {
      const url = `${tempApiBaseUrl}/experiments/datasets/${datasetId}`;

      const response: any = await AppRequest.Get(url);

      set({ evaluationDetails: response.data });
      return response.data;
    } catch (error) {
      console.error("Error fetching evaluation details:", error);
      throw error;
    } finally {
      set({ loading: false });
    }
  },
  getTraits: async (payload) => {
    set({ loading: true });
    try {
      // Set default page and limit if not provided
      const page = payload?.page ?? 1;
      const limit = payload?.limit ?? 50;

      const params = new URLSearchParams();
      params.append('page', page.toString());
      params.append('limit', limit.toString());

      const queryString = params.toString();
      const url = `${tempApiBaseUrl}/experiments/traits${queryString ? `?${queryString}` : ''}`;

      const response: any = await AppRequest.Get(url);

      // Remove datasets field from each trait
      const traitsWithoutDatasets: TraitSimple[] = response.data.traits.map((trait: TraitWithDatasets) => ({
        id: trait.id,
        name: trait.name,
        description: trait.description,
        category: trait.category,
        exps_ids: trait.exps_ids
      }));

      set({ traitsList: traitsWithoutDatasets });
    } catch (error) {
      console.error("Error fetching evaluations:", error);
    } finally {
      set({ loading: false });
    }
  },

  getExperiments: async (payload) => {
    set({ loading: true });
    try {
      // Build query parameters
      const params = new URLSearchParams();

      if (payload?.page) params.append('page', payload.page.toString());
      if (payload?.limit) params.append('limit', payload.limit.toString());
      if (payload?.search) params.append('search', payload.search);
      if (payload?.experiment_status) {
        params.append('search', payload.experiment_status);
        // payload.experiment_status.forEach(status => params.append('status', status));
      }
      if (payload?.tags && payload.tags.length > 0) {
        payload.tags.forEach(tag => params.append('tags', tag));
      }
      if (payload?.model_id) {
        params.append('model_id', payload.model_id);
      }
      if(payload?.created_after) {
        params.append('created_after', payload.created_after);
      }
      if(payload?.created_before) {
        params.append('created_after', payload.created_before);
      }
      if (payload?.order) params.append('order', payload.order);
      if (payload?.orderBy) params.append('orderBy', payload.orderBy);
      console.log(payload)
      const url = `${tempApiBaseUrl}/experiments/`;

      const response: any = await AppRequest.Get(url, {
        params: payload,
      });
      // Ensure experimentsList is always an array
      const experiments = response.data?.experiments || response.data || [];
      const experimentsArray = Array.isArray(experiments) ? experiments : [];

      set({ experimentsList: experimentsArray });
      set({ experimentsListTotal: response.data?.total_record || response.data?.total || response.total || 0 });

      return { experiments: experimentsArray, total: response.data?.total_record || response.data?.total || response.total || 0 };
    } catch (error) {
      console.error("Error fetching experiments:", error);
      // Return empty data on error
      set({ experimentsList: [], experimentsListTotal: 0 });
      throw error;
    } finally {
      set({ loading: false });
    }
  },

  getExperimentTags: async () => {
    const url = `${tempApiBaseUrl}/experiments/tags`;
    set({ loading: true });
    try {
      const response: any = await AppRequest.Get(url);
      console.log("experiment tags response", response);
      set({
        experimentTags: response.data.tags,
      });
    } catch (error) {
      console.error("Error fetching experiment tags:", error);
    } finally {
      set({ loading: false });
    }
  },

  getExperimentDetails: async (id: string) => {
    set({ experimentLoading: true });
    try {
      const response: any = await AppRequest.Get(`${tempApiBaseUrl}/experiments/${id}`);
      set({ experimentDetails: response.data.experiment });
      return response.data.experiment;
    } catch (error) {
      console.error("Error fetching experiment details:", error);
      throw error;
    } finally {
      set({ experimentLoading: false });
    }
  },

  getExperimentRuns: async (id: string) => {
    set({ loading: true });
    try {
      const response: any = await AppRequest.Get(`${tempApiBaseUrl}/experiments/${id}/runs`);
      // Ensure experimentRuns is always an array or object with array properties
      const runs = response.data;
      const runsData = Array.isArray(runs) ? { runsHistory: runs } : runs;
      set({ experimentRuns: runsData });
      return runsData;
    } catch (error) {
      console.error("Error fetching experiment runs:", error);
      // Set empty array on error
      set({ experimentRuns: { runsHistory: [] } });
      throw error;
    } finally {
      set({ loading: false });
    }
  },

  createExperiment: async (payload: any) => {
    set({ loading: true });
    try {
      const response: any = await AppRequest.Post(`${tempApiBaseUrl}/experiments/`, payload);
      console.log('response', response)
      return response.data;
    } catch (error) {
      console.log('error', error)
      console.error("Error creating experiment:", error);
      throw error;
    } finally {
      set({ loading: false });
    }
  },

  createWorkflow: async (experimentId: string, payload: any) => {
    set({ loading: true });
    try {
      const response: any = await AppRequest.Post(
        `${tempApiBaseUrl}/experiments/${experimentId}/evaluations/workflow`,
        payload
      );
      const workflow: WorkflowType = response.data;;
      set({ currentWorkflow: workflow });
      set({ currentWorkflowId: workflow.workflow_id });

      // Fetch the updated workflow data using getWorkflow (similar to getWorkflowCloud pattern)
      await get().getWorkflow(workflow.workflow_id);

      return response.data;
    } catch (error) {
      console.error("Error creating evaluation workflow:", error);
      throw error;
    } finally {
      set({ loading: false });
    }
  },

  getWorkflow: async (id?: string) => {
    const workflowId = id || get().currentWorkflow?.workflow_id;
    if (!workflowId) {
      return;
    }
    set({ loading: true });
    try {
      const response: any = await AppRequest.Get(
        `${tempApiBaseUrl}/workflows/${workflowId}`
      );
      if (response && response.data) {
        const workflow: WorkflowType = response.data;
        set({ currentWorkflow: workflow });
        return workflow;
      }
      return false;
    } catch (error) {
      console.error("Error fetching workflow:", error);
      return false;
    } finally {
      set({ loading: false });
    }
  },

  setCurrentWorkflow: (workflow: WorkflowType | null) => {
    set({ currentWorkflow: workflow });
    set({ currentWorkflowId: workflow?.workflow_id || null });
  },

  getCurrentWorkflow: () => {
    return get().currentWorkflow;
  },

  getWorkflowData: async (experimentId: string, workflowId: string) => {
    set({ loading: true });
    try {
      const url = `${tempApiBaseUrl}/experiments/${experimentId}/evaluations/workflow/${workflowId}`;

      const response: any = await AppRequest.Get(url);

      set({ workflowData: response.data });
      return response.data;
    } catch (error) {
      console.error("Error fetching workflow data:", error);
      throw error;
    } finally {
      set({ loading: false });
    }
  },

  deleteWorkflow: async (id: string, suppressToast?: boolean) => {
    try {
      const response: any = await AppRequest.Delete(
        `${tempApiBaseUrl}/workflows/${id}`
      );
      if (!suppressToast) {
        successToast(response?.data?.message || "Workflow deleted successfully");
      }
      set({ currentWorkflow: null, currentWorkflowId: null });
      return response.data;
    } catch (error) {
      console.error("Error deleting workflow:", error);
      if (!suppressToast) {
        errorToast("Failed to delete workflow");
      }
      throw error;
    }
  },
  getExperimentModels: async () => {
    try {
      const response: any = await AppRequest.Get(
        `${tempApiBaseUrl}/experiments/models`
      );
      set({ experimentModels: response.data.models });
      return response.data.models;
    } catch (error) {
      throw error;
    }
  },
  getExperimentSummary: async (id: string) => {
    set({ loading: true });
    try {
      const response: any = await AppRequest.Get(`${tempApiBaseUrl}/experiments/${id}/summary`);
      set({ experimentSummary: response.data.summary });
      return response.data.summary;
    } catch (error) {
      console.error("Error fetching experiment summary:", error);
      // Set empty array on error
      set({ experimentSummary: {} });
      throw error;
    } finally {
      set({ loading: false });
    }
  },
}));

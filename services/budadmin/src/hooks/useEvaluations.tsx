import { tempApiBaseUrl } from "@/components/environment";
import { Worker } from "cluster";
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
  status?: string[];
  tags?: string[];
  order?: string;
  orderBy?: string;
}

export interface ExperimentData {
  id: string;
  name?: string;
  experimentName: string;
  models: string;
  traits: string;
  tags: string[];
  status: "Running" | "Completed" | "Failed";
  createdDate: string;
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

// Evaluation workflow type
export interface EvaluationWorkflow {
  workflow_id: string;
  experiment_id: string;
  current_step: number;
  total_steps: number;
  status: string;
  workflow_steps: any; // This will store step-specific data
  created_at?: string;
  updated_at?: string;
}

export interface MetaLinks {
  manifest_id: string;
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
  evaluationsList: Evaluation[];
  evaluationsListTotal: number;
  traitsList: TraitSimple[];
  experimentsList: ExperimentData[];
  experimentsListTotal: number;
  experimentDetails: any;
  experimentMetrics: any;
  experimentBenchmarks: any;
  experimentRuns: any;
  currentWorkflow: EvaluationWorkflow | null;
  workflowData: any;

  getEvaluations: (payload?: GetEvaluationsPayload) => Promise<any>;
  getTraits: (payload?: any) => Promise<any>;
  getExperiments: (payload?: GetExperimentsPayload) => Promise<any>;
  getExperimentDetails: (id: string) => Promise<any>;
  getExperimentRuns: (id: string) => Promise<any>;
  createExperiment: (payload: any) => Promise<any>;
  createEvaluationWorkflow: (experimentId: string, payload: any) => Promise<any>;
  setCurrentWorkflow: (workflow: EvaluationWorkflow | null) => void;
  getCurrentWorkflow: () => EvaluationWorkflow | null;
  getWorkflowData: (experimentId: string, workflowId: string) => Promise<any>;
}>((set, get) => ({
  loading: false,
  evaluationsList: [],
  traitsList: [],
  evaluationsListTotal: 0,
  experimentsList: [],
  experimentsListTotal: 0,
  experimentDetails: null,
  experimentMetrics: null,
  experimentBenchmarks: null,
  experimentRuns: null,
  currentWorkflow: null,
  workflowData: null,

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
        console.log('Adding trait_ids to params:', payload.trait_ids);
        payload.trait_ids.forEach(id => params.append('trait_ids', id));
      }

      const queryString = params.toString();
      const url = `${tempApiBaseUrl}/experiments/datasets${queryString ? `?${queryString}` : ''}`;
      console.log('Fetching evaluations with URL:', url);

      const response: any = await AppRequest.Get(url);
      set({ evaluationsList: response.data.datasets });
      set({ evaluationsListTotal: response.data.total_record });
    } catch (error) {
      console.error("Error fetching evaluations:", error);
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
      if (payload?.status && payload.status.length > 0) {
        payload.status.forEach(status => params.append('status', status));
      }
      if (payload?.tags && payload.tags.length > 0) {
        payload.tags.forEach(tag => params.append('tags', tag));
      }
      if (payload?.order) params.append('order', payload.order);
      if (payload?.orderBy) params.append('orderBy', payload.orderBy);

      const queryString = params.toString();
      const url = `${tempApiBaseUrl}/experiments/`;
      // const url = `${tempApiBaseUrl}/experiments${queryString ? `?${queryString}` : ''}`;

      const response: any = await AppRequest.Get(url);
      // Ensure experimentsList is always an array
      const experiments = response.data?.experiments || response.data || [];
      const experimentsArray = Array.isArray(experiments) ? experiments : [];

      set({ experimentsList: experimentsArray });
      set({ experimentsListTotal: response.data?.total || response.total || 0 });

      return { experiments: experimentsArray, total: response.data?.total || response.total || 0 };
    } catch (error) {
      console.error("Error fetching experiments:", error);
      // Return empty data on error
      set({ experimentsList: [], experimentsListTotal: 0 });
      throw error;
    } finally {
      set({ loading: false });
    }
  },

  getExperimentDetails: async (id: string) => {
    set({ loading: true });
    try {
      const response: any = await AppRequest.Get(`${tempApiBaseUrl}/experiments/${id}`);
      set({ experimentDetails: response.data });
      return response.data;
    } catch (error) {
      console.error("Error fetching experiment details:", error);
      throw error;
    } finally {
      set({ loading: false });
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
      return response.data;
    } catch (error) {
      console.error("Error creating experiment:", error);
      throw error;
    } finally {
      set({ loading: false });
    }
  },

  createEvaluationWorkflow: async (experimentId: string, payload: any) => {
    set({ loading: true });
    try {
      const response: any = await AppRequest.Post(`${tempApiBaseUrl}/experiments/${experimentId}/evaluations/workflow`, payload);

      // Save the workflow response in currentWorkflow
      const currentWorkflowData = get().currentWorkflow;

      // Merge stage_data from payload into workflow_steps
      const updatedWorkflowSteps = {
        ...currentWorkflowData?.workflow_steps,
        ...response.data.workflow_steps,
        ...response.data,
        // Explicitly merge the stage_data from the current payload
        stage_data: {
          ...currentWorkflowData?.workflow_steps?.stage_data,
          ...payload.stage_data
        }
      };

      const workflow: EvaluationWorkflow = {
        workflow_id: response.data.workflow_id || response.data.id || payload.workflow_id,
        experiment_id: experimentId,
        current_step: payload.step_number || response.data.current_step || 1,
        total_steps: response.data.total_steps || 5,
        status: response.data.status || 'in_progress',
        workflow_steps: updatedWorkflowSteps,
        created_at: response.data.created_at || currentWorkflowData?.created_at,
        updated_at: response.data.updated_at || new Date().toISOString()
      };

      console.log('Saving workflow with steps:', workflow.workflow_steps);
      set({ currentWorkflow: workflow });
      return response.data;
    } catch (error) {
      console.error("Error creating evaluation workflow:", error);
      throw error;
    } finally {
      set({ loading: false });
    }
  },

  setCurrentWorkflow: (workflow: EvaluationWorkflow | null) => {
    set({ currentWorkflow: workflow });
  },

  getCurrentWorkflow: () => {
    return get().currentWorkflow;
  },

  getWorkflowData: async (experimentId: string, workflowId: string) => {
    set({ loading: true });
    try {
      const url = `${tempApiBaseUrl}/experiments/${experimentId}/evaluations/workflow/${workflowId}`;
      console.log('Fetching workflow data with URL:', url);

      const response: any = await AppRequest.Get(url);
      console.log('Workflow data response:', response.data);

      set({ workflowData: response.data });
      return response.data;
    } catch (error) {
      console.error("Error fetching workflow data:", error);
      throw error;
    } finally {
      set({ loading: false });
    }
  },

}));

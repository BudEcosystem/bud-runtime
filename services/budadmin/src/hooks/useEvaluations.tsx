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

  getEvaluations: (payload?: GetEvaluationsPayload) => Promise<any>;
  getTraits: (payload?: any) => Promise<any>;
  getExperiments: (payload?: GetExperimentsPayload) => Promise<any>;
  getExperimentDetails: (id: string) => Promise<any>;
  getExperimentMetrics: (id: string) => Promise<any>;
  getExperimentBenchmarks: (id: string) => Promise<any>;
  getExperimentRuns: (id: string) => Promise<any>;
}>((set, get) => ({
  loading: false,
  evaluationsList: [],
  traitsList: [],
  evaluationsListTotal: null,
  experimentsList: [],
  experimentsListTotal: null,
  experimentDetails: null,
  experimentMetrics: null,
  experimentBenchmarks: null,
  experimentRuns: null,

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
      set({ experimentsList: response.data.experiments || response.data || [] });
      set({ experimentsListTotal: response.data.total || response.total || 0 });

      return response.data;
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

  getExperimentMetrics: async (id: string) => {
    set({ loading: true });
    try {
      const response: any = await AppRequest.Get(`${tempApiBaseUrl}/experiments/${id}/metrics`);
      set({ experimentMetrics: response.data });
      return response.data;
    } catch (error) {
      console.error("Error fetching experiment metrics:", error);
      throw error;
    } finally {
      set({ loading: false });
    }
  },

  getExperimentBenchmarks: async (id: string) => {
    set({ loading: true });
    try {
      const response: any = await AppRequest.Get(`${tempApiBaseUrl}/experiments/${id}/benchmarks`);
      set({ experimentBenchmarks: response.data });
      return response.data;
    } catch (error) {
      console.error("Error fetching experiment benchmarks:", error);
      throw error;
    } finally {
      set({ loading: false });
    }
  },

  getExperimentRuns: async (id: string) => {
    set({ loading: true });
    try {
      const response: any = await AppRequest.Get(`${tempApiBaseUrl}/experiments/${id}/runs`);
      set({ experimentRuns: response.data });
      return response.data;
    } catch (error) {
      console.error("Error fetching experiment runs:", error);
      throw error;
    } finally {
      set({ loading: false });
    }
  },

}));

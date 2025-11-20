import { AppRequest } from "../pages/api/requests";
import { create } from "zustand";
import { tempApiBaseUrl } from "@/components/environment";
import { Model } from "./useModels";

export interface IPrompt {
  id: string;
  name: string;
  prompt_name?: string;
  version?: string;
  default_version?: string;
  prompt_type: string;
  type?: string;
  status: string;
  model_name?: string;
  modality?: string[];
  created_at: string;
  modified_at?: string;
  model?: Model;
  system_prompt?: string;
  prompt_messages?: string;
  settings?: {
    temperature?: number;
    max_tokens?: number;
    top_p?: number;
    stream?: boolean;
  };
  llm_retry_limit?: number;
}

export interface IPromptVersion {
  id: string;
  endpoint_name: string;
  version: number;
  created_at: string;
  modified_at: string;
  is_default_version: boolean;
}

export type GetPromptsParams = {
  page: number;
  limit: number;
  name?: string;
  order_by?: string;
  project_id?: string;
};

export const usePrompts = create<{
  prompts: IPrompt[];
  totalRecords: number;
  loading: boolean;
  versions: IPromptVersion[];
  currentVersion: IPromptVersion | null;
  previousVersions: IPromptVersion[];
  versionsLoading: boolean;
  getPrompts: (params: GetPromptsParams, projectId?: string) => void;
  getPromptById: (promptId: string, projectId?: string) => Promise<IPrompt>;
  getPromptVersions: (promptId: string, projectId?: string) => Promise<void>;
  createPrompt: (data: any, projectId?: string) => Promise<any>;
  deletePrompt: (promptId: string, projectId?: string) => Promise<any>;
  updatePrompt: (promptId: string, data: any, projectId?: string) => Promise<any>;
}>((set) => ({
  prompts: [],
  totalRecords: 0,
  loading: true,
  versions: [],
  currentVersion: null,
  previousVersions: [],
  versionsLoading: false,

  getPrompts: async (params: GetPromptsParams, projectId?) => {
    const url = `${tempApiBaseUrl}/prompts`;
    set({ loading: true });
    try {
      const queryParams: any = {
        page: params.page,
        limit: params.limit,
        search: params.name ? true : false,
        name: params.name ? params.name : undefined,
        order_by: params.order_by || "-created_at",
      };

      // Only add project_id if it's provided
      if (params.project_id) {
        queryParams.project_id = params.project_id;
      }

      const headers: any = {};
      // Only add headers if projectId is provided
      if (projectId) {
        headers["x-resource-type"] = "project";
        headers["x-entity-id"] = projectId;
      }

      const response: any = await AppRequest.Get(url, {
        params: queryParams,
        headers,
      });

      const listData = response.data;
      set({ prompts: listData.prompts || listData.items || [] });
      set({ totalRecords: listData.total_record || listData.total || 0 });
    } catch (error) {
      console.error("Error fetching prompts:", error);
      set({ prompts: [] });
      set({ totalRecords: 0 });
    } finally {
      set({ loading: false });
    }
  },

  getPromptById: async (promptId: string, projectId?): Promise<IPrompt> => {
    try {
      const url = `${tempApiBaseUrl}/prompts/${promptId}`;
      const headers: any = {};
      if (projectId) {
        headers["x-resource-type"] = "project";
        headers["x-entity-id"] = projectId;
      }

      const response: any = await AppRequest.Get(url, { headers });
      return response.data?.prompt;
    } catch (error) {
      console.error("Error fetching prompt by ID:", error);
      throw error;
    }
  },

  getPromptVersions: async (promptId: string, projectId?): Promise<void> => {
    set({ versionsLoading: true });
    try {
      const url = `${tempApiBaseUrl}/prompts/${promptId}/versions`;
      const headers: any = {};
      if (projectId) {
        headers["x-resource-type"] = "project";
        headers["x-entity-id"] = projectId;
      }

      const response: any = await AppRequest.Get(url, {
        params: {
          page: 1,
          limit: 100,
        },
        headers,
      });

      const data = response.data;
      const allVersions = data.versions || [];

      // Separate versions based on is_default_version
      const current = allVersions.find((v: IPromptVersion) => v.is_default_version);
      const previous = allVersions.filter((v: IPromptVersion) => !v.is_default_version);

      set({
        versions: allVersions,
        currentVersion: current || null,
        previousVersions: previous,
      });
    } catch (error) {
      console.error("Error fetching prompt versions:", error);
      set({
        versions: [],
        currentVersion: null,
        previousVersions: [],
      });
    } finally {
      set({ versionsLoading: false });
    }
  },

  createPrompt: async (data: any, projectId?): Promise<any> => {
    try {
      const url = `${tempApiBaseUrl}/prompts`;
      const headers: any = {};
      if (projectId) {
        headers["x-resource-type"] = "project";
        headers["x-entity-id"] = projectId;
      }

      const response: any = await AppRequest.Post(url, data, { headers });
      return response.data;
    } catch (error) {
      console.error("Error creating prompt:", error);
      throw error;
    }
  },

  deletePrompt: async (promptId: string, projectId?): Promise<any> => {
    try {
      const url = `${tempApiBaseUrl}/prompts/${promptId}`;
      const headers: any = {};
      if (projectId) {
        headers["x-resource-type"] = "project";
        headers["x-entity-id"] = projectId;
      }

      const response: any = await AppRequest.Delete(url, { headers });
      return response;
    } catch (error) {
      console.error("Error deleting prompt:", error);
      throw error;
    }
  },

  updatePrompt: async (promptId: string, data: any, projectId?): Promise<any> => {
    try {
      const url = `${tempApiBaseUrl}/prompts/${promptId}`;
      const headers: any = {};
      if (projectId) {
        headers["x-resource-type"] = "project";
        headers["x-entity-id"] = projectId;
      }

      const response: any = await AppRequest.Patch(url, data);
      return response.data;
    } catch (error) {
      console.error("Error updating prompt:", error);
      throw error;
    }
  },
}));

import { successToast } from "../components/toast";
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
  getPrompts: (params: GetPromptsParams, projectId?: string) => void;
  createPrompt: (data: any, projectId?: string) => Promise<any>;
  deletePrompt: (promptId: string, projectId?: string) => Promise<any>;
  updatePrompt: (promptId: string, data: any, projectId?: string) => Promise<any>;
}>((set) => ({
  prompts: [],
  totalRecords: 0,
  loading: true,

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

  createPrompt: async (data: any, projectId?): Promise<any> => {
    try {
      const url = `${tempApiBaseUrl}/prompts`;
      const headers: any = {};
      if (projectId) {
        headers["x-resource-type"] = "project";
        headers["x-entity-id"] = projectId;
      }

      const response: any = await AppRequest.Post(url, data, { headers });
      successToast(response.message || "Prompt created successfully");
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
      successToast(response.message || "Prompt updated successfully");
      return response.data;
    } catch (error) {
      console.error("Error updating prompt:", error);
      throw error;
    }
  },
}));

import { tempApiBaseUrl } from "@/components/environment";
import { useCallback, useEffect, useState } from "react";
import { useLoader } from "src/context/appContext";
import { AppRequest } from "src/pages/api/requests";
import { create } from "zustand";

export interface IDeploymentTemplate {
  id: string;
  template_type: string;
  avg_sequence_length: number;
  avg_context_length: number;
  per_session_tokens_per_sec: number[];
  ttft: number[];
  e2e_latency: number[];
  icon: string;
  name: string;
  description: string;
}

// create zustand store
export const useDeploymentTemplates = create<{
  deploymentTemplates: IDeploymentTemplate[];
  loading: boolean;
  selectedModel: IDeploymentTemplate | null;
  selectedModelId: string;
  getTemplates: (params: any) => void;
}>((set) => ({
  deploymentTemplates: [],
  loading: true,
  selectedModel: null,
  selectedModelId: "",
  getTemplates: async (params: any) => {
    const url = `${tempApiBaseUrl}/templates`;
    set({ loading: true });
    try {
      const response: any = await AppRequest.Get(url, { params });
      const listData = response.data.templates || [];
      const updatedListData = listData.map((item: any) => ({
        ...item,
      }));

      set({ deploymentTemplates: updatedListData });
    } catch (error) {
      console.error("Error fetching templates:", error);
    } finally {
      set({ loading: false });
    }
  },
}));

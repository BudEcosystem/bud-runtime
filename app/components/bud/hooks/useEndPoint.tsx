import { axiosInstance } from "@/app/api/requests";
import { create } from "zustand";
import { apiKey, tempApiBaseUrl } from "../environment";
import axios from "axios";

function successToast(message: string) {
  console.log(message);
}

type Provider = {
  id: string;
  name: string;
  description: string;
  type: string;
  icon: string;
};
type Tag = {
  name: string;
  color: string;
};

type Model = {
  id: string;
  name: string;
  description: string;
  uri: string;
  tags: Tag[];
  provider: Provider;
  is_present_in_model: boolean;
};



type Project = {
  name: string;
  description: string;
  tags: Tag[];
  icon: string;
  id: string;
};

export type Endpoint = {
  id: string;
  name: string;
  status: string;
  model: Model;
  project: Project;
  created_at: string;
};

export const useEndPoints = create<{
  endPoints: Endpoint[];
  getEndPoints: ({ page, limit }: { page: number; limit: number }) => void;
}>((set, get) => ({
  endPoints: [],
  getEndPoints: async ({ page = 1, limit = 25 }) => {
    const result = await axios
      .get(`${tempApiBaseUrl}/playground/deployments`, {
        params: {
          page: page,
          limit: limit,
        },
        headers: {
          "api-key": apiKey,
        },
      })
      .then((res) => {
        console.log(res.data.endpoints);
        set({ endPoints: res.data.endpoints });
        return res.data.endpoints;
      });

    console.log(result);
    return result;
  },
}));

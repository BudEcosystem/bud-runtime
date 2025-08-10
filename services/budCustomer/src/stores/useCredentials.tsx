import { AppRequest } from "@/services/api/requests";
import { create } from "zustand";
import { ProviderType } from "./useDeployModel";

export type ProivderInfo = {
  field: string;
  label: string;
  type: string;
  description: string;
  required: boolean;
  order: number;
};

export type Credentials = {
  id: string;
  expiry: string;
  name: string;
  key: string;
  last_used_at: string;
  max_budget: string;
  model_budgets: string;
  project: any;
};
export type CredentialDetailEndpoint = {
  id: string;
  name: string;
  status: string;
  project_info: any;
  model_info: any;
  created_at: string;
};
type CredentialDetailedType = {
  id: string;
  name: string;
  type: string;
  provider_icon: string;
  other_provider_creds: any;
  created_at: string;
  num_of_endpoints: number;
  endpoints: CredentialDetailEndpoint[];
};

export interface GetParams {
  page: number;
  limit: number;
  type?: string;
  order_by?: string;
}
export const useCredentials = create<{
  getProprietaryCredentialDetails: (id: string) => Promise<any>;
  createProprietaryCredentials: (
    keyName: string,
    providerType: string,
    values: any,
  ) => Promise<any>;
  getCredentials: (params: any) => void;
  addProjectCredentials: (params: any) => Promise<any>;
  editProjectCredentials: (params: any, id: any) => Promise<any>;
  deleteProjectCredentials: (id: any) => Promise<any>;
  credentials: Credentials[];
  totalCredentials: number | null;
  credentialDetails: CredentialDetailedType | null;
  selectedCredential: Credentials | null;
  setSelectedCredential: (credential: Credentials | null) => void;
  selectedProvider: ProviderType | null;
  setSelectedProvider: (provider: ProviderType | null) => void;
  filters: any;
  refresh: () => void;
  projectCredentialDetails: {
    name?: string;
    project?: string;
    SetExpiry?: string;
    SetMaxBudget?: any;
  };

  editProjectCredentialDetails: {
    SetExpiry?: string;
    SetMaxBudget?: any;
  };
  setProjectCredentialsDetails: (details: any) => void;
  setEditProjectCredentialsDetails: (details: any) => void;
}>((set, get) => ({
  totalCredentials: null,
  projectCredentialDetails: {
    name: "",
    project: "",
    SetExpiry: "",
    SetMaxBudget: "",
  },
  editProjectCredentialDetails: {
    SetExpiry: "",
    SetMaxBudget: "",
  },
  setProjectCredentialsDetails: (details: any) => {
    set({ projectCredentialDetails: details });
  },
  setEditProjectCredentialsDetails: (details: any) => {
    set({ editProjectCredentialDetails: details });
  },
  selectedProvider: null,
  setSelectedProvider: (provider: ProviderType | null) => {
    set({ selectedProvider: provider });
  },
  selectedCredential: null,
  setSelectedCredential: (credential: Credentials | null) => {
    set({ selectedCredential: credential });
  },
  createProprietaryCredentials: async (
    keyName: string,
    providerType: string,
    values: any,
  ) => {
    try {
      const response: any = await AppRequest.Post(`/proprietary/credentials`, {
        name: keyName,
        type: providerType,
        other_provider_creds: values,
      });
      if (response) {
        return response.data.result;
      }
      return false;
      // successToast(response.data.message);
    } catch (error) {
      console.error("Error creating model:", error);
      return false;
    }
  },
  getCredentials: async (params: GetParams) => {
    try {
      const response: any = await AppRequest.Get(`/credentials/`, {
        params,
      });
      if (response) {
        set({ credentials: response.data.credentials });
        set({ totalCredentials: response.data.total_record });
        return response.data.credentials;
      }
      return false;
      // successToast(response.data.message);
    } catch (error) {
      console.error("Error creating model:", error);
      return false;
    }
  },
  filters: {
    page: 1,
    limit: 1000,
  },
  refresh: () => {
    get().getCredentials(get().filters);
  },
  addProjectCredentials: async (params) => {
    try {
      const response: any = await AppRequest.Post(`/credentials/`, params);
      if (response) {
        set({ credentials: response.data.results });
        get().getCredentials(get().filters);
        return response.data;
      }
      return false;
      // successToast(response.data.message);
    } catch (error) {
      console.error("Error creating model:", error);
      return false;
    }
  },
  credentials: [],

  editProjectCredentials: async (params, id) => {
    try {
      const response: any = await AppRequest.Put(`/credentials/${id}`, params);
      if (response) {
        // set({ credentials: response.data.results });
        get().getCredentials(get().filters);
        return response.data;
      }
      return false;
      // successToast(response.data.message);
    } catch (error) {
      console.error("Error creating model:", error);
      return false;
    }
  },

  getProprietaryCredentialDetails: async (id) => {
    try {
      const response: any = await AppRequest.Get(
        `/proprietary/credentials/${id}/detailed-view`,
      );
      if (response) {
        set({ credentialDetails: response.data.result });
        return response.data.result;
      }
      return false;
      // successToast(response.data.message);
    } catch (error) {
      console.error("Error creating model:", error);
      return false;
    }
  },
  credentialDetails: null,
  deleteProjectCredentials: async (id) => {
    try {
      const response: any = await AppRequest.Delete(`/credentials/${id}`);
      if (response) {
        get().getCredentials(get().filters);
        return response.data;
      }
      return false;
      // successToast(response.data.message);
    } catch (error) {
      console.error("Error creating model:", error);
      return false;
    }
  },
}));

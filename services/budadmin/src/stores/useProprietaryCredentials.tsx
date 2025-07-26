import { AppRequest } from "src/pages/api/requests";
import { create } from "zustand";
import { ProviderType } from "./useDeployModel";

export type ProivderInfo = {
    field: string;
    label: string;
    type: string;
    description: string;
    required: boolean;
    order: number;
    id?: number;
};

export type Credentials = {
    id: string;
    name: string;
    type: string;
    num_of_endpoints: number;
    created_at: string;
    provider_icon: string;
    other_provider_creds: any;
};
export type CredentialDetailEndpoint = {
    id: string,
    name: string,
    status: string,
    project_info: any,
    model_info: any,
    created_at: string
}
type CredentialDetailedType = {
    id: string;
    name: string;
    type: string;
    provider_icon: string;
    other_provider_creds: any;
    created_at: string;
    num_of_endpoints: number;
    endpoints: CredentialDetailEndpoint[];
}

export interface GetParams {
    page: number;
    limit: number;
    type?: string;
    order_by?: string;
}
export const useProprietaryCredentials = create<{
    getProviderInfo: (providerName: string) => Promise<any>;
    getProprietaryCredentialDetails: (id: string) => Promise<any>;
    createProprietaryCredentials: (keyName: string, providerType: string, values: any) => Promise<any>;
    getCredentials: (params: any) => void;
    addproprietaryCredentials: (params: any) => Promise<any>;
    deleteProprietaryCredential: (params: any) => Promise<any>;
    credentials: Credentials[];
    totalCredentials: number;
    loading: boolean;
    credentialDetails: CredentialDetailedType;
    providerInfo: ProivderInfo[];
    selectedCredential: Credentials | null;
    setSelectedCredential: (credential: Credentials | null) => void;
    selectedProvider: ProviderType | null;
    setSelectedProvider: (provider: ProviderType | null) => void;
    filters: any;
    refresh: () => void;
}
>((set, get) => ({
    loading: false,
    selectedProvider: null,
    totalCredentials: null,
    setSelectedProvider: (provider: ProviderType | null) => {
        set({ selectedProvider: provider });
    },
    selectedCredential: null,
    setSelectedCredential: (credential: Credentials | null) => {
        set({ selectedCredential: credential });
    },
    providerInfo: [],
    getProviderInfo: async (providerName: string) => {
        try {
            const response: any = await AppRequest.Get(`/proprietary/credentials/provider-info`, {
                params: {
                    provider_name: providerName
                }
            });
            if (response) {
                const providerInfo: ProivderInfo[] = response.data.result?.credentials;
                set({ providerInfo });
                return providerInfo;
            }
            return false;
            // successToast(response.data.message);
        } catch (error) {
            console.error("Error creating model:", error);
            return false;
        }
    },
    createProprietaryCredentials: async (keyName: string, providerType: string, values: any) => {
        console.log("selectedProvider", get().selectedProvider);
        console.log("providerInfo", get().providerInfo)
        try {
            const response: any = await AppRequest.Post(`/proprietary/credentials/`, {
                "name": keyName,
                "type": providerType,
                "other_provider_creds": values,
                "provider_id": get().selectedProvider?.id
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
        set({ loading: true });
        try {
            const response: any = await AppRequest.Get(`/proprietary/credentials/`, {
                params: {
                    page: 1,
                    limit: 10000,
                    ...params // include additional parameters if needed
                }
            },);
            if (response) {
                set({ credentials: response.data.credentials });
                set({ totalCredentials: response.data.total_record });
                return response.data.credentials;
            }
            set({ loading: true });
            return false;
            // successToast(response.data.message);
        } catch (error) {
            set({ loading: true });
            console.error("Error creating model:", error);
            return false;
        }
    },
    filters: {
        page: 1,
        limit: 1000
    },
    refresh: () => {
        get().getCredentials(get().filters);
    },
    addproprietaryCredentials: async (params) => {
        try {
            const response: any = await AppRequest.Post(`/proprietary/credentials`, params);
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

    getProprietaryCredentialDetails: async (id) => {
        try {
            const response: any = await AppRequest.Get(`/proprietary/credentials/${id}/detailed-view`);
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

    deleteProprietaryCredential: async (id) => {
        try {
            const response: any = await AppRequest.Delete(`/proprietary/credentials/${id}`);
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

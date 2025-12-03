import { create } from "zustand";
import { AppRequest } from "src/pages/api/requests";
import { tempApiBaseUrl } from "@/components/environment";

// Types based on API response
export interface Connector {
  id: string;
  name: string;
  description?: string;
  icon?: string;
  connected?: boolean;
  connector_type?: string;
  created_at?: string;
  updated_at?: string;
  config?: any;
  category?: string;
  url?: string;
  provider?: string;
  documentation_url?: string;
  auth_type?: string;
  credential_schema?: CredentialSchemaField[];
  isFromConnectedSection?: boolean; // Client-side flag
}

export interface CredentialSchemaField {
  type: 'text' | 'password' | 'url' | 'dropdown';
  field: string;
  label: string;
  order: number;
  required: boolean;
  description: string;
  options?: string[];
  visible_when?: string[];
}

export interface ConnectorsListParams {
  version?: number;
  page?: number;
  limit?: number;
  search?: boolean;
  name?: string;
  prompt_id?: string;
  is_registered?: boolean;
  order_by?: string;
}

export interface ConnectorsListResponse {
  data: Connector[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

interface ConnectorsStore {
  // Data
  connectors: Connector[];
  connectedTools: Connector[];
  selectedConnectorDetails: Connector | null;
  totalCount: number;
  currentPage: number;
  pageSize: number;
  totalPages: number;

  // Loading states
  isLoading: boolean;
  isLoadingMore: boolean;
  isLoadingDetails: boolean;

  // Filter state
  searchQuery: string;

  // Public Actions - Used by Tools components
  fetchConnectedTools: (params?: ConnectorsListParams) => Promise<void>;
  fetchUnregisteredTools: (params?: ConnectorsListParams) => Promise<void>;
  fetchConnectorDetails: (connectorId: string) => Promise<void>;
  setSearchQuery: (query: string) => void;
}

export const useConnectors = create<ConnectorsStore>((set, get) => {
  // Internal generic fetch function to reduce duplication
  const fetchConnectors = async (
    params: ConnectorsListParams | undefined,
    isRegistered: boolean,
    updateTarget: 'connectedTools' | 'connectors'
  ) => {
    const state = get();

    // Set loading state based on pagination
    if (params?.page && params.page > 1) {
      set({ isLoadingMore: true });
    } else {
      set({ isLoading: true });
    }

    try {
      // Build query parameters
      const queryParams: ConnectorsListParams = {
        page: params?.page || (updateTarget === 'connectors' ? state.currentPage : 1),
        limit: params?.limit || state.pageSize,
        is_registered: isRegistered,
        search: params?.search !== undefined ? params.search : (state.searchQuery.length > 0),
        order_by: params?.order_by || "-created_at",
      };

      // Add prompt_id if available
      if (params?.prompt_id) {
        queryParams.prompt_id = params.prompt_id;
      }

      // Add search query
      if (state.searchQuery) {
        queryParams.name = state.searchQuery;
      }

      // Remove undefined/empty values
      Object.keys(queryParams).forEach(key => {
        const value = queryParams[key as keyof ConnectorsListParams];
        if (value === undefined || value === "") {
          delete queryParams[key as keyof ConnectorsListParams];
        }
      });

      // Make API request
      const response = await AppRequest.Get(`${tempApiBaseUrl}/prompts/connectors`, {
        params: queryParams,
      });

      if (response.data) {
        const tools = response.data.connectors || response.data.data || [];
        const isLoadMore = params?.page && params.page > 1;

        // Update state based on target and pagination
        if (updateTarget === 'connectedTools') {
          set({
            connectedTools: tools,
            isLoading: false,
            isLoadingMore: false,
          });
        } else {
          // For connectors, support pagination
          const newConnectors = isLoadMore ? [...state.connectors, ...tools] : tools;

          set({
            connectors: newConnectors,
            totalCount: response.data.total || tools.length,
            currentPage: response.data.page || params?.page || 1,
            totalPages: response.data.total_pages || Math.ceil((response.data.total || tools.length) / state.pageSize),
            isLoading: false,
            isLoadingMore: false,
          });
        }
      }
    } catch (error) {
      console.error(`Error fetching ${isRegistered ? 'connected' : 'unregistered'} tools:`, error);
      set({
        isLoading: false,
        isLoadingMore: false
      });
    }
  };

  return {
    // Initial state
    connectors: [],
    connectedTools: [],
    selectedConnectorDetails: null,
    totalCount: 0,
    currentPage: 1,
    pageSize: 10,
    totalPages: 0,
    isLoading: false,
    isLoadingMore: false,
    isLoadingDetails: false,
    searchQuery: "",

    // Public wrapper: Fetch connected tools (is_registered: true)
    fetchConnectedTools: async (params?: ConnectorsListParams) => {
      await fetchConnectors(params, true, 'connectedTools');
    },

    // Public wrapper: Fetch unregistered tools (is_registered: false)
    fetchUnregisteredTools: async (params?: ConnectorsListParams) => {
      await fetchConnectors(params, false, 'connectors');
    },

    // Fetch connector details
    fetchConnectorDetails: async (connectorId: string) => {
      set({ isLoadingDetails: true });

      try {
        const response = await AppRequest.Get(`${tempApiBaseUrl}/prompts/connectors/${connectorId}`);

        if (response.data && response.data.connector) {
          set({
            selectedConnectorDetails: response.data.connector,
            isLoadingDetails: false,
          });
        }
      } catch (error) {
        console.error("Error fetching connector details:", error);
        set({
          isLoadingDetails: false,
        });
      }
    },

    // Filter actions
    setSearchQuery: (query) => {
      set({ searchQuery: query });
    },
  };
});

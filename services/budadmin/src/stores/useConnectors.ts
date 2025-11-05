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
  promptId: string | undefined;
  isRegistered: boolean | undefined;
  orderBy: string;

  // Actions
  fetchConnectors: (params?: ConnectorsListParams) => Promise<void>;
  fetchConnectedTools: (params?: ConnectorsListParams) => Promise<void>;
  fetchUnregisteredTools: (params?: ConnectorsListParams) => Promise<void>;
  fetchConnectorDetails: (connectorId: string) => Promise<void>;
  loadMore: () => Promise<void>;
  refreshConnectors: () => Promise<void>;

  // Filter actions
  setSearchQuery: (query: string) => void;
  setPromptId: (promptId: string | undefined) => void;
  setIsRegistered: (isRegistered: boolean | undefined) => void;
  setOrderBy: (orderBy: string) => void;
  applyFilters: () => void;
  resetFilters: () => void;
  clearConnectors: () => void;
}

const defaultFilters = {
  searchQuery: "",
  promptId: undefined,
  isRegistered: undefined,
  orderBy: "-created_at",
};

export const useConnectors = create<ConnectorsStore>((set, get) => ({
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
  ...defaultFilters,

  // Fetch connectors from API
  fetchConnectors: async (params?: ConnectorsListParams) => {
    const state = get();

    // Don't set loading if we're loading more
    if (params?.page && params.page > 1) {
      set({ isLoadingMore: true });
    } else {
      set({ isLoading: true });
    }

    try {
      const queryParams: ConnectorsListParams = {
        page: params?.page || state.currentPage,
        limit: params?.limit || state.pageSize,
        search: params?.search !== undefined ? params.search : (state.searchQuery.length > 0),
        order_by: params?.order_by || state.orderBy,
      };

      // Add conditional parameters
      if (state.searchQuery) {
        queryParams.name = state.searchQuery;
      }

      if (state.promptId) {
        queryParams.prompt_id = state.promptId;
      }

      if (state.isRegistered !== undefined) {
        queryParams.is_registered = state.isRegistered;
      }

      // Remove undefined values
      Object.keys(queryParams).forEach(key => {
        if (queryParams[key as keyof ConnectorsListParams] === undefined || queryParams[key as keyof ConnectorsListParams] === "") {
          delete queryParams[key as keyof ConnectorsListParams];
        }
      });

      const response = await AppRequest.Get(`${tempApiBaseUrl}/prompts/connectors`, {
        params: queryParams,
      });

      if (response.data) {
        const connectors = response.data.connectors || response.data.data || [];
        const isLoadMore = params?.page && params.page > 1;

        // Update or append connectors based on whether we're loading more
        const newConnectors = isLoadMore
          ? [...state.connectors, ...connectors]
          : connectors;

        // Filter connected tools
        const connectedTools = newConnectors.filter((c: Connector) => c.connected);

        set({
          connectors: newConnectors,
          connectedTools,
          totalCount: response.data.total || connectors.length,
          currentPage: response.data.page || params?.page || 1,
          totalPages: response.data.total_pages || Math.ceil((response.data.total || connectors.length) / state.pageSize),
          isLoading: false,
          isLoadingMore: false,
        });
      }
    } catch (error) {
      console.error("Error fetching connectors:", error);
      set({
        isLoading: false,
        isLoadingMore: false
      });
    }
  },

  // Fetch connected tools (is_registered: true)
  fetchConnectedTools: async (params?: ConnectorsListParams) => {
    const state = get();

    if (params?.page && params.page > 1) {
      set({ isLoadingMore: true });
    } else {
      set({ isLoading: true });
    }

    try {
      const queryParams: ConnectorsListParams = {
        page: params?.page || 1,
        limit: params?.limit || state.pageSize,
        is_registered: true,
        search: params?.search !== undefined ? params.search : (state.searchQuery.length > 0),
        order_by: params?.order_by || state.orderBy,
      };

      // Add prompt_id if available
      if (params?.prompt_id || state.promptId) {
        queryParams.prompt_id = params?.prompt_id || state.promptId;
      }

      // Add search query
      if (state.searchQuery) {
        queryParams.name = state.searchQuery;
      }

      // Remove undefined values
      Object.keys(queryParams).forEach(key => {
        if (queryParams[key as keyof ConnectorsListParams] === undefined || queryParams[key as keyof ConnectorsListParams] === "") {
          delete queryParams[key as keyof ConnectorsListParams];
        }
      });

      const response = await AppRequest.Get(`${tempApiBaseUrl}/prompts/connectors`, {
        params: queryParams,
      });

      if (response.data) {
        const tools = response.data.connectors || response.data.data || [];

        set({
          connectedTools: tools,
          isLoading: false,
          isLoadingMore: false,
        });
      }
    } catch (error) {
      console.error("Error fetching connected tools:", error);
      set({
        isLoading: false,
        isLoadingMore: false
      });
    }
  },

  // Fetch unregistered tools (is_registered: false)
  fetchUnregisteredTools: async (params?: ConnectorsListParams) => {
    const state = get();

    if (params?.page && params.page > 1) {
      set({ isLoadingMore: true });
    } else {
      set({ isLoading: true });
    }

    try {
      const queryParams: ConnectorsListParams = {
        page: params?.page || state.currentPage,
        limit: params?.limit || state.pageSize,
        is_registered: false,
        search: params?.search !== undefined ? params.search : (state.searchQuery.length > 0),
        order_by: params?.order_by || state.orderBy,
      };

      // Add prompt_id if available
      if (params?.prompt_id || state.promptId) {
        queryParams.prompt_id = params?.prompt_id || state.promptId;
      }

      // Add search query
      if (state.searchQuery) {
        queryParams.name = state.searchQuery;
      }

      // Remove undefined values
      Object.keys(queryParams).forEach(key => {
        if (queryParams[key as keyof ConnectorsListParams] === undefined || queryParams[key as keyof ConnectorsListParams] === "") {
          delete queryParams[key as keyof ConnectorsListParams];
        }
      });

      const response = await AppRequest.Get(`${tempApiBaseUrl}/prompts/connectors`, {
        params: queryParams,
      });

      if (response.data) {
        const tools = response.data.connectors || response.data.data || [];
        const isLoadMore = params?.page && params.page > 1;

        // Update or append connectors based on whether we're loading more
        const newConnectors = isLoadMore
          ? [...state.connectors, ...tools]
          : tools;

        set({
          connectors: newConnectors,
          totalCount: response.data.total || tools.length,
          currentPage: response.data.page || params?.page || 1,
          totalPages: response.data.total_pages || Math.ceil((response.data.total || tools.length) / state.pageSize),
          isLoading: false,
          isLoadingMore: false,
        });
      }
    } catch (error) {
      console.error("Error fetching unregistered tools:", error);
      set({
        isLoading: false,
        isLoadingMore: false
      });
    }
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

  // Load more connectors (pagination)
  loadMore: async () => {
    const state = get();
    if (state.currentPage >= state.totalPages || state.isLoadingMore) return;

    await state.fetchConnectors({ page: state.currentPage + 1 });
  },

  // Refresh connectors
  refreshConnectors: async () => {
    set({ currentPage: 1, connectors: [] });
    await get().fetchConnectors({ page: 1 });
  },

  // Filter actions
  setSearchQuery: (query) => {
    set({ searchQuery: query });
  },

  setPromptId: (promptId) => {
    set({ promptId: promptId });
  },

  setIsRegistered: (isRegistered) => {
    set({ isRegistered: isRegistered });
  },

  setOrderBy: (orderBy) => {
    set({ orderBy: orderBy });
  },

  applyFilters: () => {
    set({ currentPage: 1, connectors: [] });
    get().fetchConnectors({ page: 1 });
  },

  resetFilters: () => {
    set({ ...defaultFilters, currentPage: 1, connectors: [] });
    get().fetchConnectors({ page: 1 });
  },

  clearConnectors: () => {
    set({
      connectors: [],
      connectedTools: [],
      totalCount: 0,
      currentPage: 1,
      totalPages: 0,
    });
  },
}));

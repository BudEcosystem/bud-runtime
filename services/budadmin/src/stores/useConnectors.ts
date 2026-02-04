import { create } from "zustand";
import { AppRequest } from "src/pages/api/requests";
import { tempApiBaseUrl } from "@/components/environment";

// Module-level tracking to prevent duplicate fetches (survives component remounts)
const inFlightFetches = new Set<string>();
const completedFetches = new Set<string>();
const inFlightListFetches = new Set<string>();
const completedListFetches = new Set<string>();

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
  type: 'text' | 'password' | 'url' | 'dropdown' | 'key-value-array';
  field: string;
  label: string;
  order: number;
  required: boolean;
  description: string;
  options?: string[];
  visible_when?: string[];
}

// Type for key-value pair entries (used with key-value-array field type)
export interface KeyValuePair {
  key: string;
  value: string;
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
  force?: boolean;
}

export interface ConnectorsListResponse {
  data: Connector[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

// Per-session pagination state
interface PaginationState {
  totalCount: number;
  currentPage: number;
  totalPages: number;
  pageSize: number;
}

// Per-session loading state
interface LoadingState {
  isLoading: boolean;
  isLoadingMore: boolean;
}

interface ConnectorsStore {
  // Per-session data (NEW - isolated per agent box)
  connectorsByPromptId: Record<string, Connector[]>;
  connectedToolsByPromptId: Record<string, Connector[]>;
  paginationByPromptId: Record<string, PaginationState>;
  loadingStatesByPromptId: Record<string, LoadingState>;
  searchQueryByPromptId: Record<string, string>;

  // Legacy global data (kept for backward compatibility)
  connectors: Connector[];
  connectedTools: Connector[];
  selectedConnectorDetails: Connector | null;
  connectorDetailsByPromptId: Record<string, Connector | null>; // Session-scoped connector details
  totalCount: number;
  currentPage: number;
  pageSize: number;
  totalPages: number;

  // Loading states
  isLoading: boolean;
  isLoadingMore: boolean;
  isLoadingDetails: boolean;
  loadingDetailsByPromptId: Record<string, boolean>; // Session-scoped loading states

  // Filter state
  searchQuery: string;

  // Public Actions - Used by Tools components
  fetchConnectedTools: (params?: ConnectorsListParams) => Promise<void>;
  fetchUnregisteredTools: (params?: ConnectorsListParams) => Promise<void>;
  fetchConnectorDetails: (connectorId: string, promptId?: string) => Promise<void>;
  setSearchQuery: (query: string) => void;
  clearSelectedConnectorDetails: () => void;

  // Session-scoped connector details actions
  getConnectorDetailsForPromptId: (promptId: string) => Connector | null;
  clearConnectorDetailsForPromptId: (promptId: string) => void;
  isLoadingDetailsForPromptId: (promptId: string) => boolean;

  // NEW: Per-session getters
  getConnectorsForPromptId: (promptId: string) => Connector[];
  getConnectedToolsForPromptId: (promptId: string) => Connector[];
  getPaginationForPromptId: (promptId: string) => PaginationState;
  getLoadingStateForPromptId: (promptId: string) => LoadingState;
  getSearchQueryForPromptId: (promptId: string) => string;

  // NEW: Per-session setters
  setSearchQueryForPromptId: (promptId: string, query: string) => void;

  // NEW: Session cleanup
  clearSessionData: (promptId: string) => void;
}

export const useConnectors = create<ConnectorsStore>((set, get) => {
  // Internal generic fetch function to reduce duplication
  const fetchConnectors = async (
    params: ConnectorsListParams | undefined,
    isRegistered: boolean,
    updateTarget: 'connectedTools' | 'connectors'
  ) => {
    const state = get();
    const searchName = params?.name ?? state.searchQuery;
    const searchKey = searchName ?? "";
    // Create a unique key for this fetch (only guard page 1 fetches, allow pagination)
    const fetchKey = `${updateTarget}:${params?.prompt_id || 'global'}:${isRegistered}:page${params?.page || 1}:search${searchKey}`;

    // Only guard against duplicate initial fetches (page 1), allow pagination
    if (params?.page === 1 || !params?.page) {
      if (!params?.force && (inFlightListFetches.has(fetchKey) || completedListFetches.has(fetchKey))) {
        return;
      }
      inFlightListFetches.add(fetchKey);
    }

    // Set loading state based on pagination
    const promptId = params?.prompt_id;

    if (params?.page && params.page > 1) {
      // Set per-session loading state if promptId provided
      if (promptId) {
        const currentLoadingState = get().loadingStatesByPromptId[promptId] || { isLoading: false, isLoadingMore: false };
        set({
          loadingStatesByPromptId: {
            ...get().loadingStatesByPromptId,
            [promptId]: { ...currentLoadingState, isLoadingMore: true },
          },
        });
      }
      set({ isLoadingMore: true });
    } else {
      // Set per-session loading state if promptId provided
      if (promptId) {
        set({
          loadingStatesByPromptId: {
            ...get().loadingStatesByPromptId,
            [promptId]: { isLoading: true, isLoadingMore: false },
          },
        });
      }
      set({ isLoading: true });
    }

    try {
      // Build query parameters
      const queryParams: ConnectorsListParams = {
        page: params?.page || (updateTarget === 'connectors' ? state.currentPage : 1),
        limit: params?.limit || state.pageSize,
        is_registered: isRegistered,
        search: params?.search !== undefined ? params.search : Boolean(searchName),
        // order_by: params?.order_by || "-created_at",
      };

      // Add prompt_id if available
      if (params?.prompt_id) {
        queryParams.prompt_id = params.prompt_id;
      }

      // Add search query
      if (searchName) {
        queryParams.name = searchName;
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
        const promptId = params?.prompt_id;

        // Update per-session state if promptId is provided (NEW - isolated per agent box)
        if (promptId) {
          if (updateTarget === 'connectedTools') {
            set({
              connectedToolsByPromptId: {
                ...get().connectedToolsByPromptId,
                [promptId]: tools,
              },
              loadingStatesByPromptId: {
                ...get().loadingStatesByPromptId,
                [promptId]: { isLoading: false, isLoadingMore: false },
              },
            });
          } else {
            // For connectors, support pagination
            const existingConnectors = get().connectorsByPromptId[promptId] || [];
            const newConnectors = isLoadMore ? [...existingConnectors, ...tools] : tools;

            set({
              connectorsByPromptId: {
                ...get().connectorsByPromptId,
                [promptId]: newConnectors,
              },
              paginationByPromptId: {
                ...get().paginationByPromptId,
                [promptId]: {
                  totalCount: response.data.total || tools.length,
                  currentPage: response.data.page || params?.page || 1,
                  totalPages: response.data.total_pages || Math.ceil((response.data.total || tools.length) / state.pageSize),
                  pageSize: state.pageSize,
                },
              },
              loadingStatesByPromptId: {
                ...get().loadingStatesByPromptId,
                [promptId]: { isLoading: false, isLoadingMore: false },
              },
            });
          }
        }

        // ALSO update legacy global state for backward compatibility
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

        // Mark as completed for page 1 fetches
        if (params?.page === 1 || !params?.page) {
          completedListFetches.add(fetchKey);
        }
      }
    } catch (error) {
      console.error(`Error fetching ${isRegistered ? 'connected' : 'unregistered'} tools:`, error);
      const promptId = params?.prompt_id;

      // Clear per-session loading state on error
      if (promptId) {
        set({
          loadingStatesByPromptId: {
            ...get().loadingStatesByPromptId,
            [promptId]: { isLoading: false, isLoadingMore: false },
          },
        });
      }
      set({
        isLoading: false,
        isLoadingMore: false
      });
    } finally {
      // Always remove from in-flight for page 1 fetches
      if (params?.page === 1 || !params?.page) {
        inFlightListFetches.delete(fetchKey);
      }
    }
  };

  return {
    // Per-session state (NEW - isolated per agent box)
    connectorsByPromptId: {},
    connectedToolsByPromptId: {},
    paginationByPromptId: {},
    loadingStatesByPromptId: {},
    searchQueryByPromptId: {},

    // Legacy global state (kept for backward compatibility)
    connectors: [],
    connectedTools: [],
    selectedConnectorDetails: null,
    connectorDetailsByPromptId: {},
    totalCount: 0,
    currentPage: 1,
    pageSize: 10,
    totalPages: 0,
    isLoading: false,
    isLoadingMore: false,
    isLoadingDetails: false,
    loadingDetailsByPromptId: {},
    searchQuery: "",

    // Public wrapper: Fetch connected tools (is_registered: true)
    fetchConnectedTools: async (params?: ConnectorsListParams) => {
      await fetchConnectors(params, true, 'connectedTools');
    },

    // Public wrapper: Fetch unregistered tools (is_registered: false)
    fetchUnregisteredTools: async (params?: ConnectorsListParams) => {
      await fetchConnectors(params, false, 'connectors');
    },

    // Fetch connector details (supports both global and session-scoped storage)
    fetchConnectorDetails: async (connectorId: string, promptId?: string) => {
      // Create a unique key for this fetch
      const fetchKey = promptId ? `${promptId}:${connectorId}` : connectorId;

      // Guard 1: Skip if this exact fetch is already in flight or completed (module-level)
      if (inFlightFetches.has(fetchKey) || completedFetches.has(fetchKey)) {
        return;
      }

      const state = get();

      // Guard 2: Skip if already loading for this promptId (state-level)
      if (promptId && state.loadingDetailsByPromptId[promptId]) {
        return;
      }

      // Guard 3: Skip if we already have data for this connector+promptId (state-level)
      if (promptId && state.connectorDetailsByPromptId[promptId]?.id === connectorId) {
        completedFetches.add(fetchKey); // Mark as completed since we have data
        return;
      }

      // Mark as in-flight IMMEDIATELY (before any async operations)
      inFlightFetches.add(fetchKey);

      // Set loading state
      if (promptId) {
        set({
          loadingDetailsByPromptId: {
            ...state.loadingDetailsByPromptId,
            [promptId]: true,
          },
        });
      } else {
        set({ isLoadingDetails: true });
      }

      try {
        const response = await AppRequest.Get(`${tempApiBaseUrl}/prompts/connectors/${connectorId}`);

        if (response.data && response.data.connector) {
          if (promptId) {
            // Store in session-scoped map
            set({
              connectorDetailsByPromptId: {
                ...get().connectorDetailsByPromptId,
                [promptId]: response.data.connector,
              },
              loadingDetailsByPromptId: {
                ...get().loadingDetailsByPromptId,
                [promptId]: false,
              },
            });
          } else {
            // Legacy: store in global state for backward compatibility
            set({
              selectedConnectorDetails: response.data.connector,
              isLoadingDetails: false,
            });
          }
        }

        // Mark as completed (prevents future duplicate fetches)
        completedFetches.add(fetchKey);
      } catch (error) {
        console.error("Error fetching connector details:", error);
        if (promptId) {
          set({
            loadingDetailsByPromptId: {
              ...get().loadingDetailsByPromptId,
              [promptId]: false,
            },
          });
        } else {
          set({
            isLoadingDetails: false,
          });
        }
        // On error, don't mark as completed so it can be retried
      } finally {
        // Always remove from in-flight
        inFlightFetches.delete(fetchKey);
      }
    },

    // Filter actions
    setSearchQuery: (query) => {
      set({ searchQuery: query });
    },

    // Clear selected connector details (used when navigating back)
    clearSelectedConnectorDetails: () => {
      set({ selectedConnectorDetails: null });
    },

    // Session-scoped connector details actions
    getConnectorDetailsForPromptId: (promptId: string) => {
      return get().connectorDetailsByPromptId[promptId] || null;
    },

    clearConnectorDetailsForPromptId: (promptId: string) => {
      const current = get().connectorDetailsByPromptId;
      const connector = current[promptId];

      // Clear from completedFetches so user can re-fetch this connector
      if (connector?.id) {
        const fetchKey = `${promptId}:${connector.id}`;
        completedFetches.delete(fetchKey);
      }

      const { [promptId]: _, ...rest } = current;
      set({ connectorDetailsByPromptId: rest });
    },

    isLoadingDetailsForPromptId: (promptId: string) => {
      return get().loadingDetailsByPromptId[promptId] || false;
    },

    // NEW: Per-session getters
    getConnectorsForPromptId: (promptId: string) => {
      return get().connectorsByPromptId[promptId] || [];
    },

    getConnectedToolsForPromptId: (promptId: string) => {
      return get().connectedToolsByPromptId[promptId] || [];
    },

    getPaginationForPromptId: (promptId: string) => {
      return get().paginationByPromptId[promptId] || {
        totalCount: 0,
        currentPage: 1,
        totalPages: 0,
        pageSize: 10,
      };
    },

    getLoadingStateForPromptId: (promptId: string) => {
      return get().loadingStatesByPromptId[promptId] || {
        isLoading: false,
        isLoadingMore: false,
      };
    },

    getSearchQueryForPromptId: (promptId: string) => {
      return get().searchQueryByPromptId[promptId] || '';
    },

    // NEW: Per-session setters
    setSearchQueryForPromptId: (promptId: string, query: string) => {
      set({
        searchQueryByPromptId: {
          ...get().searchQueryByPromptId,
          [promptId]: query,
        },
      });
    },

    // NEW: Session cleanup - call when agent box is closed
    clearSessionData: (promptId: string) => {
      const {
        connectorsByPromptId,
        connectedToolsByPromptId,
        paginationByPromptId,
        loadingStatesByPromptId,
        searchQueryByPromptId,
        connectorDetailsByPromptId,
        loadingDetailsByPromptId,
      } = get();

      // Clear completed fetches for this promptId
      const keysToDelete: string[] = [];
      completedListFetches.forEach(key => {
        if (key.includes(`:${promptId}:`)) {
          keysToDelete.push(key);
        }
      });
      keysToDelete.forEach(key => completedListFetches.delete(key));

      // Clear connector details completed fetches
      const detailKeysToDelete: string[] = [];
      completedFetches.forEach(key => {
        if (key.startsWith(`${promptId}:`)) {
          detailKeysToDelete.push(key);
        }
      });
      detailKeysToDelete.forEach(key => completedFetches.delete(key));

      // Remove session data from all per-session maps
      const { [promptId]: _c, ...restConnectors } = connectorsByPromptId;
      const { [promptId]: _ct, ...restConnectedTools } = connectedToolsByPromptId;
      const { [promptId]: _p, ...restPagination } = paginationByPromptId;
      const { [promptId]: _l, ...restLoading } = loadingStatesByPromptId;
      const { [promptId]: _s, ...restSearch } = searchQueryByPromptId;
      const { [promptId]: _cd, ...restDetails } = connectorDetailsByPromptId;
      const { [promptId]: _ld, ...restDetailsLoading } = loadingDetailsByPromptId;

      set({
        connectorsByPromptId: restConnectors,
        connectedToolsByPromptId: restConnectedTools,
        paginationByPromptId: restPagination,
        loadingStatesByPromptId: restLoading,
        searchQueryByPromptId: restSearch,
        connectorDetailsByPromptId: restDetails,
        loadingDetailsByPromptId: restDetailsLoading,
      });
    },
  };
});

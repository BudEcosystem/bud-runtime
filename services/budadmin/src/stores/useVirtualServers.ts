import { create } from "zustand";
import { AppRequest } from "src/pages/api/requests";

// API response interface from MCP Foundry
export interface VirtualServerResponse {
  id: string;
  name: string;
  description?: string;
  visibility?: string;
  associatedTools?: string[];
  associated_tools?: string[];
  toolsCount?: number;
  createdAt?: string;
  updatedAt?: string;
}

// UI VirtualServer interface used by components
export interface VirtualServer {
  id: string;
  name: string;
  description: string;
  visibility: string;
  toolsCount: number;
  created_at: string;
  updated_at: string;
}

// Tool interface for tools inside a virtual server
export interface VirtualServerTool {
  id: string;
  name: string;
  displayName?: string;
  description?: string;
  integrationType?: string;
  requestType?: string;
  url?: string;
  isActive?: boolean;
  enabled?: boolean;
}

// Virtual server detail with tools
export interface VirtualServerDetail {
  id: string;
  name: string;
  description?: string;
  visibility?: string;
  tools: VirtualServerTool[];
  toolsCount: number;
  createdAt?: string;
  updatedAt?: string;
}

// Transform API response to UI VirtualServer format
const transformApiToVirtualServer = (apiServer: VirtualServerResponse): VirtualServer => {
  const associatedTools = apiServer.associatedTools || apiServer.associated_tools || [];
  return {
    id: apiServer.id,
    name: apiServer.name,
    description: apiServer.description || "",
    visibility: apiServer.visibility || "public",
    toolsCount: apiServer.toolsCount || associatedTools.length,
    created_at: apiServer.createdAt || "",
    updated_at: apiServer.updatedAt || "",
  };
};

interface VirtualServersState {
  virtualServers: VirtualServer[];
  selectedVirtualServer: VirtualServer | null;
  virtualServerDetail: VirtualServerDetail | null;
  isLoading: boolean;
  isLoadingMore: boolean;
  isLoadingDetail: boolean;
  error: string | null;

  // Pagination state
  currentPage: number;
  hasMore: boolean;
  totalCount: number;

  // Actions
  setVirtualServers: (servers: VirtualServer[]) => void;
  setSelectedVirtualServer: (server: VirtualServer | null) => void;
  getVirtualServers: (params?: {
    page?: number;
    limit?: number;
    append?: boolean;
  }) => Promise<void>;
  getVirtualServerById: (serverId: string) => Promise<void>;
  loadMore: () => Promise<void>;
  resetPagination: () => void;
  clearVirtualServerDetail: () => void;
}

const DEFAULT_PAGE_SIZE = 30;

export const useVirtualServers = create<VirtualServersState>((set, get) => ({
  virtualServers: [],
  selectedVirtualServer: null,
  virtualServerDetail: null,
  isLoading: false,
  isLoadingMore: false,
  isLoadingDetail: false,
  error: null,
  currentPage: 1,
  hasMore: true,
  totalCount: 0,

  setVirtualServers: (servers) => set({ virtualServers: servers }),

  setSelectedVirtualServer: (server) => set({ selectedVirtualServer: server }),

  clearVirtualServerDetail: () => set({ virtualServerDetail: null }),

  getVirtualServers: async (params) => {
    const isAppend = params?.append ?? false;
    const page = params?.page ?? 1;
    const limit = params?.limit ?? DEFAULT_PAGE_SIZE;
    const offset = (page - 1) * limit;

    set({
      isLoading: !isAppend,
      isLoadingMore: isAppend,
      error: null,
    });

    try {
      const response = await AppRequest.Get("/tools/virtual-servers", {
        params: {
          offset,
          limit,
        },
      });

      // Handle AppRequest returning false on error
      if (!response || !response.data) {
        set({ error: "Failed to fetch virtual servers", hasMore: false });
        return;
      }

      const apiServers: VirtualServerResponse[] = response.data?.servers || [];
      const total = response.data?.total || 0;
      const servers = apiServers.map(transformApiToVirtualServer);

      // Determine if there are more pages
      const hasMore = servers.length === limit;

      if (isAppend) {
        // Append to existing servers
        const existingServers = get().virtualServers;
        set({
          virtualServers: [...existingServers, ...servers],
          currentPage: page,
          hasMore,
          totalCount: total,
        });
      } else {
        // Replace servers
        set({
          virtualServers: servers,
          currentPage: page,
          hasMore,
          totalCount: total,
        });
      }
    } catch (error: any) {
      console.error("Error fetching virtual servers:", error);
      set({ error: error?.message || "Failed to fetch virtual servers", hasMore: false });
    } finally {
      set({ isLoading: false, isLoadingMore: false });
    }
  },

  loadMore: async () => {
    const { currentPage, hasMore, isLoadingMore } = get();
    if (!hasMore || isLoadingMore) return;

    await get().getVirtualServers({
      page: currentPage + 1,
      limit: DEFAULT_PAGE_SIZE,
      append: true,
    });
  },

  getVirtualServerById: async (serverId: string) => {
    set({
      isLoadingDetail: true,
      virtualServerDetail: null,
      error: null,
    });

    try {
      const response = await AppRequest.Get(`/tools/virtual-servers/${serverId}`);

      if (!response || !response.data) {
        set({ error: "Failed to fetch virtual server details", isLoadingDetail: false });
        return;
      }

      const data = response.data;
      const detail: VirtualServerDetail = {
        id: data.id,
        name: data.name,
        description: data.description,
        visibility: data.visibility,
        tools: data.tools || [],
        toolsCount: data.toolsCount || data.tools_count || (data.tools?.length || 0),
        createdAt: data.createdAt || data.created_at,
        updatedAt: data.updatedAt || data.updated_at,
      };

      set({ virtualServerDetail: detail });
    } catch (error: any) {
      console.error("Error fetching virtual server details:", error);
      set({ error: error?.message || "Failed to fetch virtual server details" });
    } finally {
      set({ isLoadingDetail: false });
    }
  },

  resetPagination: () => {
    set({
      virtualServers: [],
      currentPage: 1,
      hasMore: true,
      totalCount: 0,
    });
  },
}));

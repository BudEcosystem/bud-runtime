import { create } from "zustand";
import { AppRequest } from "src/pages/api/requests";

// API response interface from MCP Foundry
export interface McpToolResponse {
  id: string;
  name: string;
  displayName?: string;
  originalName?: string;
  description: string;
  integrationType?: string;
  tags: string[];
  createdAt: string;
  updatedAt?: string;
  executionCount: number;
  enabled?: boolean;
  reachable?: boolean;
  url?: string;
  requestType?: string;
  headers?: Record<string, string>;
  inputSchema?: Record<string, any>;
  outputSchema?: Record<string, any>;
  annotations?: Record<string, any>;
  jsonpathFilter?: string;
  auth?: {
    authType?: string;
    authValue?: string;
    username?: string;
    password?: string;
    token?: string;
    authHeaderKey?: string;
    authHeaderValue?: string;
  };
  gatewayId?: string;
  metrics?: {
    totalExecutions?: number;
    successfulExecutions?: number;
    failedExecutions?: number;
    failureRate?: number;
    minResponseTime?: number;
    maxResponseTime?: number;
    avgResponseTime?: number;
    lastExecutionTime?: string;
  };
  gatewaySlug?: string;
  customName?: string;
  customNameSlug?: string;
  createdBy?: string;
  modifiedBy?: string;
  teamId?: string;
  team?: string;
  ownerEmail?: string;
  visibility?: string;
  baseUrl?: string;
  pathTemplate?: string;
  queryMapping?: Record<string, any>;
  headerMapping?: Record<string, any>;
  timeoutMs?: number;
  version?: number;
}

// UI Tool interface used by components
export interface Tool {
  id: string;
  name: string;
  icon: string;
  category: string;
  description: string;
  tags: { name: string; color: string }[];
  created_at: string;
  usage_count: number;
  subTools?: SubTool[];
  // Additional fields from API
  enabled?: boolean;
  reachable?: boolean;
  url?: string;
  requestType?: string;
  integrationType?: string;
  metrics?: McpToolResponse["metrics"];
  visibility?: string;
  teamId?: string;
  rawData?: McpToolResponse;
  executionCount?: number;
}

export interface SubTool {
  id: string;
  name: string;
  description: string;
}

// Tag color palette for consistent color assignment
const TAG_COLORS = [
  "#965CDE", // Purple
  "#22C55E", // Green
  "#F59E0B", // Amber
  "#3B82F6", // Blue
  "#EF4444", // Red
  "#06B6D4", // Cyan
  "#EC4899", // Pink
  "#8B5CF6", // Violet
  "#14B8A6", // Teal
  "#F97316", // Orange
];

// Generate consistent color based on tag name
const generateTagColor = (tagName: string): string => {
  const hash = tagName.split("").reduce((acc, char) => acc + char.charCodeAt(0), 0);
  return TAG_COLORS[hash % TAG_COLORS.length];
};

// Get icon based on integration type or default
const getToolIcon = (tool: McpToolResponse): string => {
  const type = tool.integrationType?.toLowerCase() || "";
  const name = tool.name?.toLowerCase() || "";

  if (type.includes("api") || name.includes("api")) return "🔌";
  if (type.includes("database") || name.includes("db")) return "🗄️";
  if (type.includes("auth") || name.includes("auth")) return "🔐";
  if (type.includes("file") || name.includes("file")) return "📁";
  if (type.includes("email") || name.includes("email")) return "📧";
  if (type.includes("webhook") || name.includes("webhook")) return "🪝";
  if (type.includes("chat") || name.includes("chat")) return "💬";
  if (type.includes("search") || name.includes("search")) return "🔍";
  if (type.includes("analytics") || name.includes("analytics")) return "📊";
  if (type.includes("storage") || name.includes("storage")) return "💾";

  return "🔧"; // Default tool icon
};

// Transform API response to UI Tool format
const transformApiToTool = (apiTool: McpToolResponse): Tool => {
  return {
    id: apiTool.id,
    name: apiTool.displayName || apiTool.customName || apiTool.name,
    icon: getToolIcon(apiTool),
    category: apiTool.integrationType || "General",
    description: apiTool.description || "",
    tags: (apiTool.tags || []).map((tagName) => ({
      name: tagName,
      color: generateTagColor(tagName),
    })),
    created_at: apiTool.createdAt,
    usage_count: apiTool.executionCount || 0,
    enabled: apiTool.enabled,
    reachable: apiTool.reachable,
    url: apiTool.url,
    requestType: apiTool.requestType,
    integrationType: apiTool.integrationType,
    metrics: apiTool.metrics,
    visibility: apiTool.visibility,
    teamId: apiTool.teamId,
    rawData: apiTool,
  };
};

interface ToolsState {
  tools: Tool[];
  selectedTool: Tool | null;
  isLoading: boolean;
  isLoadingMore: boolean;
  error: string | null;

  // Pagination state
  currentPage: number;
  hasMore: boolean;
  totalCount: number;

  // Actions
  setTools: (tools: Tool[]) => void;
  setSelectedTool: (tool: Tool | null) => void;
  getTools: (params?: {
    cursor?: string;
    include_inactive?: boolean;
    tags?: string;
    team_id?: string;
    visibility?: string;
    search?: string;
    page?: number;
    limit?: number;
    append?: boolean;
  }) => Promise<void>;
  loadMore: () => Promise<void>;
  resetPagination: () => void;
  getTool: (id: string) => Promise<Tool | null>;
}

const DEFAULT_PAGE_SIZE = 30;

export const useTools = create<ToolsState>((set, get) => ({
  tools: [],
  selectedTool: null,
  isLoading: false,
  isLoadingMore: false,
  error: null,
  currentPage: 1,
  hasMore: true,
  totalCount: 0,

  setTools: (tools) => set({ tools }),

  setSelectedTool: (tool) => set({ selectedTool: tool }),

  getTools: async (params) => {
    const isAppend = params?.append ?? false;
    const page = params?.page ?? 1;
    const limit = params?.limit ?? DEFAULT_PAGE_SIZE;

    set({
      isLoading: !isAppend,
      isLoadingMore: isAppend,
      error: null,
    });

    try {
      const response = await AppRequest.Get("/tools", {
        params: {
          include_inactive: params?.include_inactive ?? false,
          page,
          limit,
          ...(params?.cursor && { cursor: params.cursor }),
          ...(params?.tags && { tags: params.tags }),
          ...(params?.team_id && { team_id: params.team_id }),
          ...(params?.visibility && { visibility: params.visibility }),
          ...(params?.search && { search: params.search }),
        },
      });

      // Handle AppRequest returning false on error
      if (!response || !response.data) {
        set({ error: "Failed to fetch tools" });
        return;
      }

      // Response from budapp proxy: { tools: [...], total_record, page, limit, ... }
      const apiTools: McpToolResponse[] = response.data?.tools || response.data || [];
      const totalRecord = response.data?.total_record || 0;
      const tools = apiTools.map(transformApiToTool);

      // Determine if there are more pages
      const hasMore = tools.length === limit;

      if (isAppend) {
        // Append to existing tools
        const existingTools = get().tools;
        set({
          tools: [...existingTools, ...tools],
          currentPage: page,
          hasMore,
          totalCount: totalRecord,
        });
      } else {
        // Replace tools
        set({
          tools,
          currentPage: page,
          hasMore,
          totalCount: totalRecord,
        });
      }
    } catch (error: any) {
      console.error("Error fetching tools:", error);
      set({ error: error?.message || "Failed to fetch tools" });
    } finally {
      set({ isLoading: false, isLoadingMore: false });
    }
  },

  loadMore: async () => {
    const { currentPage, hasMore, isLoadingMore } = get();
    if (!hasMore || isLoadingMore) return;

    await get().getTools({
      page: currentPage + 1,
      limit: DEFAULT_PAGE_SIZE,
      append: true,
    });
  },

  resetPagination: () => {
    set({
      tools: [],
      currentPage: 1,
      hasMore: true,
      totalCount: 0,
    });
  },

  getTool: async (id: string) => {
    set({ isLoading: true, error: null });
    try {
      // First check if tool exists in current list
      const { tools } = get();
      const existingTool = tools.find((t) => t.id === id);
      if (existingTool) {
        set({ selectedTool: existingTool });
        return existingTool;
      }

      // If not found, fetch from API via budapp proxy
      const response = await AppRequest.Get(`/tools/${id}`);
      // Response from budapp proxy: { tool: {...}, code, message }
      const apiTool: McpToolResponse = response.data?.tool || response.data;
      const tool = transformApiToTool(apiTool);
      set({ selectedTool: tool });
      return tool;
    } catch (error: any) {
      console.error("Error fetching tool:", error);
      set({ error: error?.message || "Failed to fetch tool" });
      return null;
    } finally {
      set({ isLoading: false });
    }
  },
}));

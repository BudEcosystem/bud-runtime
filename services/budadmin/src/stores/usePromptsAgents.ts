import { create } from "zustand";
import { AppRequest } from "src/pages/api/requests";

// Types based on API response
export interface PromptAgent {
  id: string;
  name: string;
  description: string;
  prompt_type: 'simple_prompt' | 'agent';
  category?: string;
  tags?: Array<{ name: string; color: string }>;
  created_at: string;
  modified_at?: string;
  updated_at?: string;
  author?: string;
  usage_count?: number;
  rating?: number;
  is_public?: boolean;
  icon?: string;
  model_icon?: string | null;
  model_name?: string;
  default_version?: number;
  modality?: string[];
  status?: string;
  parameters?: any;
  version?: string;
  project_id?: string;
  system_prompt?: string;
  prompt_messages?: string;
  input_variables?: any[];
  output_variables?: any[];
  model_id?: string;
  settings?: {
    temperature?: number;
    max_tokens?: number;
    top_p?: number;
  };
}

export interface PromptsListParams {
  page?: number;
  limit?: number;
  search?: boolean;
  name?: string;
  prompt_type?: 'simple_prompt' | 'agent';
  project_id?: string;
  order_by?: string;
}

export interface PromptsListResponse {
  data: PromptAgent[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

interface PromptsAgentsStore {
  // Data
  prompts: PromptAgent[];
  filteredPrompts: PromptAgent[];
  totalCount: number;
  currentPage: number;
  pageSize: number;
  totalPages: number;

  // Loading states
  isLoading: boolean;
  isLoadingMore: boolean;

  // Filter state
  searchQuery: string;
  selectedType: 'simple_prompt' | 'agent' | undefined;
  selectedCategory: string | undefined;
  selectedAuthor: string | undefined;
  selectedTags: string[];
  ratingMin: number | undefined;
  ratingMax: number | undefined;
  projectId: string | undefined;
  orderBy: string;

  // Computed values
  categories: string[];
  authors: string[];
  allTags: string[];

  // Actions
  fetchPrompts: (params?: PromptsListParams) => Promise<void>;
  loadMore: () => Promise<void>;
  refreshPrompts: () => Promise<void>;

  // Filter actions
  setSearchQuery: (query: string) => void;
  setSelectedType: (type: 'simple_prompt' | 'agent' | undefined) => void;
  setSelectedCategory: (category: string | undefined) => void;
  setSelectedAuthor: (author: string | undefined) => void;
  setSelectedTags: (tags: string[]) => void;
  setRatingRange: (min: number | undefined, max: number | undefined) => void;
  setProjectId: (projectId: string | undefined) => void;
  setOrderBy: (orderBy: string) => void;
  applyFilters: () => void;
  resetFilters: () => void;
}

const defaultFilters = {
  searchQuery: "",
  selectedType: undefined as 'simple_prompt' | 'agent' | undefined,
  selectedCategory: undefined,
  selectedAuthor: undefined,
  selectedTags: [] as string[],
  ratingMin: undefined,
  ratingMax: undefined,
  projectId: undefined,
  orderBy: "-created_at",
};

export const usePromptsAgents = create<PromptsAgentsStore>((set, get) => ({
  // Initial state
  prompts: [],
  filteredPrompts: [],
  totalCount: 0,
  currentPage: 1,
  pageSize: 10,
  totalPages: 0,
  isLoading: false,
  isLoadingMore: false,
  ...defaultFilters,
  categories: [],
  authors: [],
  allTags: [],

  // Fetch prompts from API
  fetchPrompts: async (params?: PromptsListParams) => {
    const state = get();
    const page = params?.page || state.currentPage;
    const isAppend = page > 1;

    if (!isAppend) {
      set({ isLoading: true });
    }

    try {
      // Determine the search query - use params.name if provided, otherwise use state.searchQuery
      const searchQuery = params?.name !== undefined ? params.name : state.searchQuery;
      const hasSearchQuery = searchQuery && searchQuery.trim().length > 0;

      const queryParams: PromptsListParams = {
        page: page,
        limit: params?.limit || state.pageSize,
        search: hasSearchQuery ? true : undefined,
        name: hasSearchQuery ? searchQuery : undefined,
        prompt_type: params?.prompt_type || state.selectedType,
        project_id: params?.project_id || state.projectId,
        order_by: params?.order_by || state.orderBy,
      };

      // Remove undefined values
      Object.keys(queryParams).forEach(key => {
        const value = queryParams[key as keyof PromptsListParams];
        if (value === undefined || value === "") {
          delete queryParams[key as keyof PromptsListParams];
        }
      });

      const response = await AppRequest.Get("/prompts", {
        params: queryParams,
      });

      if (response.data) {
        const newPrompts = response.data.prompts || [];

        // Apply client-side filters for additional filtering (category, author, tags, rating)
        let filtered = [...newPrompts];

        if (state.selectedCategory) {
          filtered = filtered.filter(p => p.category === state.selectedCategory);
        }

        if (state.selectedAuthor) {
          filtered = filtered.filter(p => p.author === state.selectedAuthor);
        }

        if (state.selectedTags.length > 0) {
          filtered = filtered.filter(p =>
            state.selectedTags.some(tag => p.tags?.some(t => t.name === tag))
          );
        }

        if (state.ratingMin !== undefined) {
          filtered = filtered.filter(p => (p.rating || 0) >= state.ratingMin!);
        }

        if (state.ratingMax !== undefined) {
          filtered = filtered.filter(p => (p.rating || 0) <= state.ratingMax!);
        }

        // Append or replace based on page
        const finalPrompts = isAppend ? [...state.prompts, ...newPrompts] : newPrompts;
        const finalFiltered = isAppend ? [...state.filteredPrompts, ...filtered] : filtered;

        // Extract unique categories, authors, and tags for filters
        const categories = Array.from(new Set(finalPrompts.map(p => p.category).filter(Boolean))) as string[];
        const authors = Array.from(new Set(finalPrompts.map(p => p.author).filter(Boolean))) as string[];
        const allTags = Array.from(new Set(finalPrompts.flatMap(p => (p.tags || []).map(t => t.name))));

        set({
          prompts: finalPrompts,
          filteredPrompts: finalFiltered,
          totalCount: response.data.total || finalPrompts.length,
          currentPage: response.data.page || 1,
          totalPages: response.data.total_pages || Math.ceil((response.data.total || finalPrompts.length) / state.pageSize),
          categories,
          authors,
          isLoading: false,
        });
      }
    } catch (error) {
      console.error("Error fetching prompts:", error);
      set({ isLoading: false });
    }
  },

  // Load more prompts (pagination)
  loadMore: async () => {
    const state = get();
    if (state.currentPage >= state.totalPages) return;

    set({ isLoadingMore: true });
    await state.fetchPrompts({ page: state.currentPage + 1 });
    set({ isLoadingMore: false });
  },

  // Refresh prompts
  refreshPrompts: async () => {
    const state = get();
    set({ currentPage: 1 });
    await state.fetchPrompts({ page: 1 });
  },

  // Filter actions
  setSearchQuery: (query) => {
    set({ searchQuery: query });
  },

  setSelectedType: (type) => {
    set({ selectedType: type });
  },

  setSelectedCategory: (category) => {
    set({ selectedCategory: category });
  },

  setSelectedAuthor: (author) => {
    set({ selectedAuthor: author });
  },

  setSelectedTags: (tags) => {
    set({ selectedTags: tags });
  },

  setRatingRange: (min, max) => {
    set({ ratingMin: min, ratingMax: max });
  },

  setProjectId: (projectId) => {
    set({ projectId: projectId });
  },

  setOrderBy: (orderBy) => {
    set({ orderBy: orderBy });
  },

  applyFilters: () => {
    const state = get();
    set({ currentPage: 1 });
    state.fetchPrompts({ page: 1 });
  },

  resetFilters: () => {
    set({ ...defaultFilters, currentPage: 1 });
    get().fetchPrompts({ page: 1 });
  }
}));

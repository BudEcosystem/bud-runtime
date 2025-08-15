import { create } from 'zustand';
import { AppRequest } from '../pages/api/requests';
import { message } from 'antd';

export type BlockingRuleType = 'IP_BLOCKING' | 'COUNTRY_BLOCKING' | 'USER_AGENT_BLOCKING' | 'RATE_BASED_BLOCKING';
export type BlockingRuleStatus = 'ACTIVE' | 'INACTIVE' | 'EXPIRED';

export interface BlockingRule {
  id: string;
  name: string;
  description?: string;
  rule_type: BlockingRuleType;
  rule_config: Record<string, any>;
  status: BlockingRuleStatus;
  reason: string;
  priority: number;
  project_id: string;
  project_name?: string;
  endpoint_id?: string;
  endpoint_name?: string;
  created_by: string;
  created_by_name?: string;
  match_count: number;
  last_matched_at?: string;
  created_at: string;
  updated_at: string;
}

export interface BlockingRuleCreate {
  name: string;
  description?: string;
  rule_type: BlockingRuleType;
  rule_config: Record<string, any>;
  status?: BlockingRuleStatus;
  reason: string;
  priority?: number;
  endpoint_id?: string;
}

export interface BlockingRuleUpdate {
  name?: string;
  description?: string;
  rule_config?: Record<string, any>;
  status?: BlockingRuleStatus;
  reason?: string;
  priority?: number;
  endpoint_id?: string;
}

export interface BlockingStats {
  total_rules: number;
  active_rules: number;
  inactive_rules: number;
  expired_rules: number;
  total_blocks_today: number;
  total_blocks_week: number;
  top_blocked_ips: Array<{ ip: string; count: number }>;
  top_blocked_countries: Array<{ country: string; count: number }>;
  blocks_by_type: Record<BlockingRuleType, number>;
  blocks_timeline: Array<{ timestamp: string; count: number }>;
}

interface BlockingRulesState {
  rules: BlockingRule[];
  stats: BlockingStats | null;
  isLoading: boolean;
  isCreating: boolean;
  isUpdating: boolean;
  isDeleting: boolean;
  isSyncing: boolean;
  currentPage: number;
  pageSize: number;
  totalCount: number;
  filters: {
    project_id?: string;
    rule_type?: BlockingRuleType;
    status?: BlockingRuleStatus;
    endpoint_id?: string;
  };

  // Actions
  fetchRules: (projectId?: string) => Promise<void>;
  fetchStats: (projectId?: string, startTime?: string, endTime?: string) => Promise<void>;
  createRule: (projectId: string, rule: BlockingRuleCreate) => Promise<boolean>;
  updateRule: (ruleId: string, update: BlockingRuleUpdate) => Promise<boolean>;
  deleteRule: (ruleId: string) => Promise<boolean>;
  syncRules: (projectIds?: string[]) => Promise<boolean>;
  setFilters: (filters: Partial<BlockingRulesState['filters']>) => void;
  setPagination: (page: number, pageSize: number) => void;
  clearFilters: () => void;
}

export const useBlockingRules = create<BlockingRulesState>((set, get) => ({
  rules: [],
  stats: null,
  isLoading: false,
  isCreating: false,
  isUpdating: false,
  isDeleting: false,
  isSyncing: false,
  currentPage: 1,
  pageSize: 20,
  totalCount: 0,
  filters: {},

  fetchRules: async (projectId?: string) => {
    set({ isLoading: true });
    try {
      const { filters, currentPage, pageSize } = get();
      const params: any = {
        page: currentPage,
        page_size: pageSize,
        ...filters,
      };

      if (projectId) {
        params.project_id = projectId;
      }

      const response = await AppRequest.Get('/metrics/gateway/blocking-rules', { params });

      if (response.data) {
        set({
          rules: response.data.rules || [],
          totalCount: response.data.total || 0,
          isLoading: false,
        });
      }
    } catch (error: any) {
      const errorMsg = error?.response?.data?.message || error?.message || 'Failed to fetch rules';
      message.error(errorMsg);
      set({ isLoading: false });
    }
  },

  fetchStats: async (projectId?: string, startTime?: string, endTime?: string) => {
    try {
      const params: any = {};
      if (projectId) params.project_id = projectId;
      if (startTime) params.start_time = startTime;
      if (endTime) params.end_time = endTime;

      const response = await AppRequest.Get('/metrics/gateway/blocking-stats', { params });

      if (response.data) {
        set({ stats: response.data });
      }
    } catch (error: any) {
      const errorMsg = error?.response?.data?.message || error?.message || 'Failed to fetch statistics';
      message.error(errorMsg);
    }
  },

  createRule: async (projectId: string, rule: BlockingRuleCreate) => {
    set({ isCreating: true });
    try {
      const response = await AppRequest.Post(
        `/metrics/gateway/blocking-rules?project_id=${projectId}`,
        rule
      );

      if (response.data?.success) {
        message.success('Blocking rule created successfully');
        await get().fetchRules(projectId);
        set({ isCreating: false });
        return true;
      }
      set({ isCreating: false });
      return false;
    } catch (error: any) {
      const errorMsg = error?.response?.data?.message || error?.message || 'Failed to create rule';
      message.error(errorMsg);
      set({ isCreating: false });
      return false;
    }
  },

  updateRule: async (ruleId: string, update: BlockingRuleUpdate) => {
    set({ isUpdating: true });
    try {
      const response = await AppRequest.Put(
        `/metrics/gateway/blocking-rules/${ruleId}`,
        update
      );

      if (response.data?.success) {
        message.success('Blocking rule updated successfully');
        await get().fetchRules();
        set({ isUpdating: false });
        return true;
      }
      set({ isUpdating: false });
      return false;
    } catch (error: any) {
      const errorMsg = error?.response?.data?.message || error?.message || 'Failed to update rule';
      message.error(errorMsg);
      set({ isUpdating: false });
      return false;
    }
  },

  deleteRule: async (ruleId: string) => {
    set({ isDeleting: true });
    try {
      const response = await AppRequest.Delete(
        `/metrics/gateway/blocking-rules/${ruleId}`
      );

      if (response.data?.success) {
        message.success('Blocking rule deleted successfully');
        await get().fetchRules();
        set({ isDeleting: false });
        return true;
      }
      set({ isDeleting: false });
      return false;
    } catch (error: any) {
      const errorMsg = error?.response?.data?.message || error?.message || 'Failed to delete rule';
      message.error(errorMsg);
      set({ isDeleting: false });
      return false;
    }
  },

  syncRules: async (projectIds?: string[]) => {
    set({ isSyncing: true });
    try {
      const response = await AppRequest.Post(
        '/metrics/gateway/blocking-rules/sync',
        { project_ids: projectIds }
      );

      if (response.data?.success) {
        message.success(response.data.message || 'Rules synced successfully');
        set({ isSyncing: false });
        return true;
      }
      set({ isSyncing: false });
      return false;
    } catch (error: any) {
      const errorMsg = error?.response?.data?.message || error?.message || 'Failed to sync rules';
      message.error(errorMsg);
      set({ isSyncing: false });
      return false;
    }
  },

  setFilters: (filters) => {
    set((state) => ({
      filters: { ...state.filters, ...filters },
      currentPage: 1, // Reset to first page when filters change
    }));
  },

  setPagination: (page, pageSize) => {
    set({ currentPage: page, pageSize });
  },

  clearFilters: () => {
    set({ filters: {}, currentPage: 1 });
  },
}));

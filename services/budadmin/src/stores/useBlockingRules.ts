import { create } from 'zustand';
import { AppRequest } from '../pages/api/requests';
import { successToast, errorToast } from '@/components/toast';

export type BlockingRuleType = 'ip_blocking' | 'country_blocking' | 'user_agent_blocking' | 'rate_based_blocking';
export type BlockingRuleStatus = 'active' | 'inactive' | 'expired' | 'ACTIVE' | 'INACTIVE' | 'EXPIRED';

export interface BlockingRule {
  id: string;
  name: string;
  description?: string;
  rule_type: BlockingRuleType;
  rule_config: Record<string, any>;
  status: BlockingRuleStatus;
  reason: string;
  priority: number;
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
}

export interface BlockingRuleUpdate {
  name?: string;
  description?: string;
  rule_config?: Record<string, any>;
  status?: BlockingRuleStatus;
  reason?: string;
  priority?: number;
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
  currentPage: number;
  pageSize: number;
  totalCount: number;
  filters: {
    rule_type?: BlockingRuleType;
    status?: BlockingRuleStatus;
  };

  // Actions
  fetchRules: () => Promise<void>;
  fetchStats: (startTime?: string, endTime?: string) => Promise<void>;
  createRule: (rule: BlockingRuleCreate) => Promise<boolean>;
  updateRule: (ruleId: string, update: BlockingRuleUpdate) => Promise<boolean>;
  deleteRule: (ruleId: string) => Promise<boolean>;
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
  currentPage: 1,
  pageSize: 20,
  totalCount: 0,
  filters: {},

  fetchRules: async () => {
    set({ isLoading: true });
    try {
      const { filters, currentPage, pageSize } = get();
      const params: any = {
        page: currentPage,
        page_size: pageSize,
        ...filters,
      };

      const response = await AppRequest.Get('/metrics/gateway/blocking-rules', { params });

      if (response.data) {
        set({
          rules: response.data.items || response.data.rules || [],
          totalCount: response.data.total || 0,
          isLoading: false,
        });
      }
    } catch (error: any) {
      const errorMsg = error?.response?.data?.message || error?.message || 'Failed to fetch rules';
      errorToast(errorMsg);
      set({ isLoading: false });
    }
  },

  fetchStats: async (startTime?: string, endTime?: string) => {
    try {
      const params: any = {};
      if (startTime) params.start_time = startTime;
      if (endTime) params.end_time = endTime;

      // Call the new dashboard stats endpoint that queries directly from source databases
      const response = await AppRequest.Get('/metrics/gateway/blocking-dashboard-stats', { params });

      if (response.data) {
        set({ stats: response.data });
      }
    } catch (error: any) {
      const errorMsg = error?.response?.data?.message || error?.message || 'Failed to fetch statistics';
      errorToast(errorMsg);
      console.error('Failed to fetch dashboard stats:', error);
    }
  },

  createRule: async (rule: BlockingRuleCreate) => {
    set({ isCreating: true });
    try {
      const response = await AppRequest.Post('/metrics/gateway/blocking-rules', rule);

      if (response.data?.data) {
        successToast(response.data?.message || 'Blocking rule created successfully');
        await get().fetchRules();
        set({ isCreating: false });
        return true;
      }
      set({ isCreating: false });
      return false;
    } catch (error: any) {
      const errorMsg = error?.response?.data?.message || error?.message || 'Failed to create rule';
      errorToast(errorMsg);
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

      if (response.data?.data) {
        // Override the message to ensure it says "updated" not "retrieved"
        const message = response.data?.message?.includes('retrieved')
          ? 'Blocking rule updated successfully'
          : (response.data?.message || 'Blocking rule updated successfully');
        successToast(message);
        await get().fetchRules();
        set({ isUpdating: false });
        return true;
      }
      set({ isUpdating: false });
      return false;
    } catch (error: any) {
      const errorMsg = error?.response?.data?.message || error?.message || 'Failed to update rule';
      errorToast(errorMsg);
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

      if (response.data?.id) {
        successToast(response.data?.message || 'Blocking rule deleted successfully');
        await get().fetchRules();
        set({ isDeleting: false });
        return true;
      }
      set({ isDeleting: false });
      return false;
    } catch (error: any) {
      const errorMsg = error?.response?.data?.message || error?.message || 'Failed to delete rule';
      errorToast(errorMsg);
      set({ isDeleting: false });
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

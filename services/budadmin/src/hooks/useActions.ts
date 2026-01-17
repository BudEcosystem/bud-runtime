/**
 * Hook for fetching and caching pipeline actions from the budpipeline API.
 *
 * This hook provides dynamic action metadata for the pipeline editor,
 * replacing the static action definitions in actionRegistry.ts.
 */

import { useCallback, useEffect, useState } from 'react';
import { AppRequest } from 'src/pages/api/requests';
import type {
  ActionListResponse,
  ActionMeta,
  ActionCategory,
  ValidateRequest,
  ValidateResponse,
} from 'src/types/actions';

// API endpoint for budpipeline via budapp proxy
const BUDPIPELINE_API = '/budpipeline';

// Cache duration in milliseconds (5 minutes)
const CACHE_DURATION = 5 * 60 * 1000;

// Module-level cache to persist across component remounts
let actionsCache: {
  data: ActionListResponse | null;
  timestamp: number;
} = {
  data: null,
  timestamp: 0,
};

export interface UseActionsResult {
  /** All actions as a flat list */
  actions: ActionMeta[];
  /** Actions grouped by category */
  categories: ActionCategory[];
  /** Whether actions are being loaded */
  isLoading: boolean;
  /** Error message if loading failed */
  error: string | null;
  /** Refetch actions from API */
  refetch: () => Promise<void>;
  /** Get a specific action by type */
  getAction: (actionType: string) => ActionMeta | undefined;
  /** Validate action parameters */
  validateParams: (actionType: string, params: Record<string, unknown>) => Promise<ValidateResponse>;
}

/**
 * Hook to fetch and cache pipeline actions from the API.
 *
 * @example
 * ```tsx
 * const { actions, categories, isLoading, getAction } = useActions();
 *
 * // Get all actions
 * actions.forEach(action => console.log(action.type, action.name));
 *
 * // Get a specific action
 * const logAction = getAction('log');
 * ```
 */
export function useActions(): UseActionsResult {
  const [actions, setActions] = useState<ActionMeta[]>([]);
  const [categories, setCategories] = useState<ActionCategory[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchActions = useCallback(async (forceRefresh = false) => {
    // Check cache first
    const now = Date.now();
    if (
      !forceRefresh &&
      actionsCache.data &&
      now - actionsCache.timestamp < CACHE_DURATION
    ) {
      setActions(actionsCache.data.actions);
      setCategories(actionsCache.data.categories);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await AppRequest.Get(
        `${BUDPIPELINE_API}/actions`
      );

      if (response?.data) {
        const data = response.data as ActionListResponse;

        // Update cache
        actionsCache = {
          data,
          timestamp: now,
        };

        setActions(data.actions);
        setCategories(data.categories);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch actions';
      setError(message);
      console.error('Error fetching actions:', err);

      // Fall back to cached data if available
      if (actionsCache.data) {
        setActions(actionsCache.data.actions);
        setCategories(actionsCache.data.categories);
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  const refetch = useCallback(async () => {
    await fetchActions(true);
  }, [fetchActions]);

  const getAction = useCallback(
    (actionType: string): ActionMeta | undefined => {
      return actions.find((action) => action.type === actionType);
    },
    [actions]
  );

  const validateParams = useCallback(
    async (
      actionType: string,
      params: Record<string, unknown>
    ): Promise<ValidateResponse> => {
      try {
        const request: ValidateRequest = {
          actionType,
          params,
        };

        const response = await AppRequest.Post(
          `${BUDPIPELINE_API}/actions/validate`,
          request
        );

        if (response?.data) {
          return response.data as ValidateResponse;
        }

        return { valid: false, errors: ['Validation request failed'] };
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Validation error';
        return { valid: false, errors: [message] };
      }
    },
    []
  );

  // Fetch actions on mount
  useEffect(() => {
    fetchActions();
  }, [fetchActions]);

  return {
    actions,
    categories,
    isLoading,
    error,
    refetch,
    getAction,
    validateParams,
  };
}

/**
 * Utility function to get cached actions synchronously.
 *
 * Useful for functions that can't use hooks (e.g., validation utilities).
 * Returns empty arrays if cache is not populated.
 */
export function getCachedActions(): {
  actions: ActionMeta[];
  categories: ActionCategory[];
} {
  if (actionsCache.data) {
    return {
      actions: actionsCache.data.actions,
      categories: actionsCache.data.categories,
    };
  }
  return { actions: [], categories: [] };
}

/**
 * Utility function to get a specific action from cache.
 *
 * @param actionType - The action type to find
 * @returns The action metadata or undefined if not found
 */
export function getCachedAction(actionType: string): ActionMeta | undefined {
  const { actions } = getCachedActions();
  return actions.find((action) => action.type === actionType);
}

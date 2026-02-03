/**
 * Workflow Action Registry
 *
 * Provides utility functions for working with pipeline actions.
 * All action metadata is fetched dynamically from the budpipeline API.
 *
 * Use the useActions() hook for React components, or getCachedAction()
 * for non-React utility functions.
 */

import { getCachedAction, getCachedActions } from 'src/hooks/useActions';
import type {
  ActionMeta as ApiActionMeta,
  ParamDefinition as ApiParamDefinition,
} from 'src/types/actions';

// ============================================================================
// Local Types (for backwards compatibility with existing components)
// ============================================================================

export type ParamType =
  | 'string'
  | 'number'
  | 'boolean'
  | 'select'
  | 'multiselect'
  | 'json'
  | 'template'
  | 'range'
  | 'model_ref'
  | 'cluster_ref'
  | 'project_ref'
  | 'endpoint_ref'
  | 'provider_ref'
  | 'branches';

export interface SelectOption {
  label: string;
  value: string;
}

export interface ConditionalBranch {
  id: string;
  label: string;
  condition: string;
  target_step: string | null;
}

export interface ParamDefinition {
  name: string;
  label: string;
  type: ParamType;
  required: boolean;
  default?: unknown;
  description?: string;
  placeholder?: string;
  options?: SelectOption[];
  validation?: {
    min?: number;
    max?: number;
    minLength?: number;
    maxLength?: number;
    pattern?: string;
    patternMessage?: string;
  };
  showWhen?: {
    param: string;
    equals?: unknown;
    notEquals?: unknown;
  };
  group?: string;
}

export interface ActionMeta {
  value: string;
  label: string;
  icon: string;
  color: string;
  description: string;
  params: ParamDefinition[];
  outputs?: string[];
}

export interface ActionCategory {
  category: string;
  icon: string;
  actions: ActionMeta[];
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Convert API action metadata to the local ActionMeta format
 */
function convertApiActionToLocal(apiAction: ApiActionMeta): ActionMeta {
  return {
    value: apiAction.type,
    label: apiAction.name,
    icon: apiAction.icon || '⚙️',
    color: apiAction.color || '#8c8c8c',
    description: apiAction.description,
    outputs: apiAction.outputs.map((o) => o.name),
    params: apiAction.params.map((p: ApiParamDefinition) => ({
      name: p.name,
      label: p.label,
      type: p.type as ParamType,
      required: p.required,
      default: p.default,
      description: p.description,
      placeholder: p.placeholder,
      options: p.options,
      validation: p.validation,
      showWhen: p.visibleWhen
        ? {
            param: p.visibleWhen.param,
            equals: p.visibleWhen.equals,
            notEquals: p.visibleWhen.notEquals,
          }
        : undefined,
    })),
  };
}

/**
 * Get action metadata by action type.
 * Fetches from API cache - returns default if not found.
 */
export function getActionMeta(action: string): ActionMeta {
  const cachedAction = getCachedAction(action);
  if (cachedAction) {
    return convertApiActionToLocal(cachedAction);
  }

  // Return default for unknown actions
  return {
    value: action,
    label: action,
    icon: '⚙️',
    color: '#8c8c8c',
    description: 'Custom action',
    params: [],
  };
}

/**
 * Get all actions from API cache as local ActionMeta format
 */
export function getAllActions(): ActionMeta[] {
  const { actions } = getCachedActions();
  return actions.map(convertApiActionToLocal);
}

/**
 * Get all action categories from API cache as local format
 */
export function getActionCategories(): ActionCategory[] {
  const { categories } = getCachedActions();
  return categories.map((cat) => ({
    category: cat.name,
    icon: cat.icon,
    actions: cat.actions.map(convertApiActionToLocal),
  }));
}

/**
 * Get parameter definitions for an action
 */
export function getActionParams(action: string): ParamDefinition[] {
  const meta = getActionMeta(action);
  return meta.params || [];
}

/**
 * Get required parameters for an action
 */
export function getRequiredParams(action: string): ParamDefinition[] {
  return getActionParams(action).filter((p) => p.required);
}

/**
 * Get optional parameters for an action
 */
export function getOptionalParams(action: string): ParamDefinition[] {
  return getActionParams(action).filter((p) => !p.required);
}

/**
 * Validate parameters against schema
 */
export function validateParams(
  action: string,
  params: Record<string, unknown>
): { valid: boolean; errors: string[] } {
  const schema = getActionParams(action);
  const errors: string[] = [];

  for (const param of schema) {
    const value = params[param.name];

    // Check required
    if (param.required && (value === undefined || value === null || value === '')) {
      errors.push(`${param.label} is required`);
      continue;
    }

    // Skip validation for empty optional fields
    if (value === undefined || value === null || value === '') {
      continue;
    }

    // Type-specific validation
    if (param.validation) {
      const v = param.validation;

      if (typeof value === 'number') {
        if (v.min !== undefined && value < v.min) {
          errors.push(`${param.label} must be at least ${v.min}`);
        }
        if (v.max !== undefined && value > v.max) {
          errors.push(`${param.label} must be at most ${v.max}`);
        }
      }

      if (typeof value === 'string') {
        if (v.minLength !== undefined && value.length < v.minLength) {
          errors.push(`${param.label} must be at least ${v.minLength} characters`);
        }
        if (v.maxLength !== undefined && value.length > v.maxLength) {
          errors.push(`${param.label} must be at most ${v.maxLength} characters`);
        }
        if (v.pattern && !new RegExp(v.pattern).test(value)) {
          errors.push(v.patternMessage || `${param.label} format is invalid`);
        }
      }
    }
  }

  return { valid: errors.length === 0, errors };
}

/**
 * Get default parameter values for an action
 */
export function getDefaultParams(action: string): Record<string, unknown> {
  const schema = getActionParams(action);
  const defaults: Record<string, unknown> = {};

  for (const param of schema) {
    if (param.default !== undefined) {
      defaults[param.name] = param.default;
    }
  }

  return defaults;
}

/**
 * Default action for unknown types
 */
export const DEFAULT_ACTION_META: ActionMeta = {
  value: 'unknown',
  label: 'Unknown Action',
  icon: '❓',
  color: '#8c8c8c',
  description: 'Unknown action type',
  params: [],
};

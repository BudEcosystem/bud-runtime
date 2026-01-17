/**
 * TypeScript types for pipeline actions.
 *
 * These types mirror the API response schemas from budpipeline's Actions API.
 * They are used by the pipeline editor to dynamically render action metadata.
 */

// ============================================================================
// Parameter Types
// ============================================================================

export type ParamType =
  | 'string'
  | 'number'
  | 'boolean'
  | 'select'
  | 'multiselect'
  | 'json'
  | 'template'
  | 'branches'
  | 'model_ref'
  | 'cluster_ref'
  | 'project_ref'
  | 'endpoint_ref';

export interface SelectOption {
  value: string;
  label: string;
}

export interface ValidationRules {
  min?: number;
  max?: number;
  minLength?: number;
  maxLength?: number;
  pattern?: string;
  patternMessage?: string;
}

export interface ConditionalVisibility {
  param: string;
  equals?: unknown;
  notEquals?: unknown;
}

export interface ParamDefinition {
  name: string;
  label: string;
  type: ParamType;
  description?: string;
  required: boolean;
  default?: unknown;
  placeholder?: string;
  options?: SelectOption[];
  validation?: ValidationRules;
  visibleWhen?: ConditionalVisibility;
}

// ============================================================================
// Output Types
// ============================================================================

export interface OutputDefinition {
  name: string;
  type: string;
  description?: string;
}

// ============================================================================
// Retry Policy
// ============================================================================

export interface RetryPolicy {
  maxAttempts: number;
  backoffMultiplier: number;
  initialIntervalSeconds: number;
}

// ============================================================================
// Action Example
// ============================================================================

export interface ActionExample {
  title: string;
  params: Record<string, unknown>;
  description?: string;
}

// ============================================================================
// Action Metadata
// ============================================================================

export type ExecutionMode = 'sync' | 'event_driven';

export interface ActionMeta {
  /** Unique action type identifier */
  type: string;
  /** Semantic version */
  version: string;
  /** Human-readable name */
  name: string;
  /** Description of what this action does */
  description: string;
  /** Category for grouping (Model, Cluster, Control Flow, etc.) */
  category: string;
  /** Icon identifier (emoji or icon name) */
  icon?: string;
  /** Theme color (hex) */
  color?: string;
  /** Parameter definitions */
  params: ParamDefinition[];
  /** Output definitions */
  outputs: OutputDefinition[];
  /** Execution mode */
  executionMode: ExecutionMode;
  /** Timeout in seconds */
  timeoutSeconds?: number;
  /** Retry policy */
  retryPolicy?: RetryPolicy;
  /** Whether this action is idempotent */
  idempotent: boolean;
  /** Required services for this action */
  requiredServices: string[];
  /** Required permissions */
  requiredPermissions: string[];
  /** Usage examples */
  examples: ActionExample[];
  /** Documentation URL */
  docsUrl?: string;
}

// ============================================================================
// Action Category (for grouping in sidebar)
// ============================================================================

export interface ActionCategory {
  name: string;
  icon: string;
  actions: ActionMeta[];
}

// ============================================================================
// API Response Types
// ============================================================================

export interface ActionListResponse {
  actions: ActionMeta[];
  categories: ActionCategory[];
  total: number;
}

export interface ValidateRequest {
  actionType: string;
  params: Record<string, unknown>;
}

export interface ValidateResponse {
  valid: boolean;
  errors: string[];
}

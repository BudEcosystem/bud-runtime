/**
 * Workflow Action Registry
 *
 * Defines all available workflow actions with their metadata and parameter schemas.
 * This is shared between the sidebar, node rendering, and configuration panel.
 */

// ============================================================================
// Parameter Schema Types
// ============================================================================

export type ParamType =
  | 'string'
  | 'number'
  | 'boolean'
  | 'select'
  | 'multiselect'
  | 'json'
  | 'template'      // Jinja2 template string
  | 'model_ref'     // Reference to a model (fetched from API)
  | 'cluster_ref'   // Reference to a cluster
  | 'project_ref'   // Reference to a project
  | 'endpoint_ref'  // Reference to an endpoint
  | 'branches';     // Multi-branch conditional routing

/**
 * Branch definition for conditional routing
 */
export interface ConditionalBranch {
  /** Unique branch identifier */
  id: string;
  /** Display label for the branch */
  label: string;
  /** Jinja2 condition expression */
  condition: string;
  /** Target step ID to route to when condition matches */
  target_step: string | null;
}

export interface SelectOption {
  label: string;
  value: string;
}

export interface ParamDefinition {
  /** Parameter name (key in params object) */
  name: string;
  /** Display label */
  label: string;
  /** Parameter type */
  type: ParamType;
  /** Whether this parameter is required */
  required: boolean;
  /** Default value */
  default?: unknown;
  /** Description/help text */
  description?: string;
  /** Placeholder text for input */
  placeholder?: string;
  /** Static options for select/multiselect types */
  options?: SelectOption[];
  /** Validation rules */
  validation?: {
    min?: number;
    max?: number;
    minLength?: number;
    maxLength?: number;
    pattern?: string;
    patternMessage?: string;
  };
  /** Conditional visibility based on other params */
  showWhen?: {
    param: string;
    equals?: unknown;
    notEquals?: unknown;
  };
  /** Group name for organizing params in UI */
  group?: string;
}

export interface ActionMeta {
  /** Unique action identifier */
  value: string;
  /** Display label */
  label: string;
  /** Icon (emoji or component) */
  icon: string;
  /** Theme color */
  color: string;
  /** Short description */
  description: string;
  /** Parameter definitions */
  params: ParamDefinition[];
  /** Output definitions (what this action produces) */
  outputs?: string[];
}

export interface ActionCategory {
  category: string;
  icon: string;
  actions: ActionMeta[];
}

// ============================================================================
// Action Definitions
// ============================================================================

export const actionCategories: ActionCategory[] = [
  {
    category: 'Deployment',
    icon: '🚀',
    actions: [
      {
        value: 'deployment_create',
        label: 'Create Deployment',
        icon: '➕',
        color: '#52c41a',
        description: 'Create a new model deployment',
        outputs: ['deployment_id', 'endpoint_url', 'status'],
        params: [
          {
            name: 'model_id',
            label: 'Model',
            type: 'model_ref',
            required: true,
            description: 'The model to deploy',
          },
          {
            name: 'cluster_id',
            label: 'Cluster',
            type: 'cluster_ref',
            required: true,
            description: 'Target cluster for deployment',
          },
          {
            name: 'endpoint_name',
            label: 'Endpoint Name',
            type: 'string',
            required: true,
            placeholder: 'my-model-endpoint',
            description: 'Name for the inference endpoint',
            validation: {
              minLength: 3,
              maxLength: 63,
              pattern: '^[a-z0-9][a-z0-9-]*[a-z0-9]$',
              patternMessage: 'Must be lowercase alphanumeric with hyphens',
            },
          },
          {
            name: 'replicas',
            label: 'Replicas',
            type: 'number',
            required: false,
            default: 1,
            description: 'Number of replicas',
            validation: { min: 1, max: 10 },
            group: 'Scaling',
          },
          {
            name: 'gpu_type',
            label: 'GPU Type',
            type: 'select',
            required: false,
            options: [
              { label: 'Auto (recommended)', value: 'auto' },
              { label: 'NVIDIA A100', value: 'a100' },
              { label: 'NVIDIA A10G', value: 'a10g' },
              { label: 'NVIDIA T4', value: 't4' },
              { label: 'NVIDIA L4', value: 'l4' },
            ],
            default: 'auto',
            group: 'Resources',
          },
          {
            name: 'run_simulation',
            label: 'Run Optimization',
            type: 'boolean',
            required: false,
            default: true,
            description: 'Run budsim optimization before deployment',
            group: 'Advanced',
          },
        ],
      },
      {
        value: 'deployment_autoscale',
        label: 'Autoscale',
        icon: '📈',
        color: '#1890ff',
        description: 'Configure autoscaling for deployment',
        outputs: ['success', 'config'],
        params: [
          {
            name: 'deployment_id',
            label: 'Deployment',
            type: 'template',
            required: true,
            placeholder: '{{ steps.previous.outputs.deployment_id }}',
            description: 'Deployment ID to configure',
          },
          {
            name: 'min_replicas',
            label: 'Min Replicas',
            type: 'number',
            required: true,
            default: 1,
            validation: { min: 0, max: 100 },
          },
          {
            name: 'max_replicas',
            label: 'Max Replicas',
            type: 'number',
            required: true,
            default: 4,
            validation: { min: 1, max: 100 },
          },
          {
            name: 'target_cpu_utilization',
            label: 'Target CPU %',
            type: 'number',
            required: false,
            default: 70,
            description: 'Target CPU utilization percentage',
            validation: { min: 10, max: 100 },
          },
          {
            name: 'scale_up_cooldown',
            label: 'Scale Up Cooldown (s)',
            type: 'number',
            required: false,
            default: 60,
            group: 'Advanced',
          },
          {
            name: 'scale_down_cooldown',
            label: 'Scale Down Cooldown (s)',
            type: 'number',
            required: false,
            default: 300,
            group: 'Advanced',
          },
        ],
      },
      {
        value: 'deployment_delete',
        label: 'Delete Deployment',
        icon: '🗑️',
        color: '#f5222d',
        description: 'Delete an existing deployment',
        outputs: ['success'],
        params: [
          {
            name: 'deployment_id',
            label: 'Deployment',
            type: 'template',
            required: true,
            placeholder: '{{ steps.previous.outputs.deployment_id }}',
          },
          {
            name: 'force',
            label: 'Force Delete',
            type: 'boolean',
            required: false,
            default: false,
            description: 'Force delete even if serving traffic',
          },
        ],
      },
      {
        value: 'deployment_ratelimit',
        label: 'Rate Limit',
        icon: '⚡',
        color: '#fa8c16',
        description: 'Configure rate limiting',
        outputs: ['success', 'config'],
        params: [
          {
            name: 'deployment_id',
            label: 'Deployment',
            type: 'template',
            required: true,
          },
          {
            name: 'requests_per_second',
            label: 'Requests/Second',
            type: 'number',
            required: true,
            default: 100,
            validation: { min: 1 },
          },
          {
            name: 'burst_size',
            label: 'Burst Size',
            type: 'number',
            required: false,
            default: 200,
          },
        ],
      },
    ],
  },
  {
    category: 'Model',
    icon: '🤖',
    actions: [
      {
        value: 'model_add',
        label: 'Add Model',
        icon: '📥',
        color: '#722ed1',
        description: 'Add a new model to the repository from HuggingFace',
        outputs: ['success', 'model_id', 'model_name', 'workflow_id', 'status', 'message'],
        params: [
          {
            name: 'huggingface_id',
            label: 'HuggingFace Model ID',
            type: 'string',
            required: true,
            placeholder: 'meta-llama/Llama-2-7b-hf',
            description: 'The HuggingFace model identifier (org/model)',
          },
          {
            name: 'model_name',
            label: 'Model Name',
            type: 'string',
            required: false,
            placeholder: 'Auto-derived from HuggingFace ID',
            description: 'Display name for the model (optional, derived from HuggingFace ID if not provided)',
          },
          {
            name: 'description',
            label: 'Description',
            type: 'string',
            required: false,
            placeholder: 'A large language model for...',
          },
          {
            name: 'author',
            label: 'Author',
            type: 'string',
            required: false,
            placeholder: 'Model author or organization',
          },
          {
            name: 'modality',
            label: 'Modality',
            type: 'multiselect',
            required: false,
            options: [
              { label: 'Text', value: 'text' },
              { label: 'Image', value: 'image' },
              { label: 'Audio', value: 'audio' },
              { label: 'Video', value: 'video' },
            ],
            default: ['text'],
          },
          {
            name: 'max_wait_seconds',
            label: 'Max Wait Time (seconds)',
            type: 'number',
            required: false,
            default: 1800,
            description: 'Maximum time to wait for model download completion (default: 30 min)',
            validation: { min: 60, max: 7200 },
            group: 'Advanced',
          },
        ],
      },
      {
        value: 'model_delete',
        label: 'Delete Model',
        icon: '🗑️',
        color: '#f5222d',
        description: 'Remove a model from repository',
        outputs: ['success', 'model_id', 'message'],
        params: [
          {
            name: 'model_id',
            label: 'Model',
            type: 'model_ref',
            required: true,
            description: 'The model to delete',
          },
          {
            name: 'force',
            label: 'Force Delete',
            type: 'boolean',
            required: false,
            default: false,
            description: 'Force delete even if model is in use',
          },
        ],
      },
      {
        value: 'model_benchmark',
        label: 'Benchmark',
        icon: '📊',
        color: '#13c2c2',
        description: 'Run benchmarks on a deployed model',
        outputs: ['success', 'benchmark_id', 'workflow_id', 'status', 'results', 'message'],
        params: [
          {
            name: 'model_id',
            label: 'Model',
            type: 'model_ref',
            required: true,
            description: 'The model to benchmark',
          },
          {
            name: 'cluster_id',
            label: 'Cluster',
            type: 'cluster_ref',
            required: true,
            description: 'Target cluster where model is deployed',
          },
          {
            name: 'benchmark_name',
            label: 'Benchmark Name',
            type: 'string',
            required: false,
            default: 'auto-benchmark',
            placeholder: 'auto-benchmark',
            description: 'Name for this benchmark run',
          },
          {
            name: 'concurrent_requests',
            label: 'Concurrent Requests',
            type: 'number',
            required: false,
            default: 1,
            validation: { min: 1, max: 100 },
            description: 'Number of concurrent requests during benchmark',
          },
          {
            name: 'max_input_tokens',
            label: 'Max Input Tokens',
            type: 'number',
            required: false,
            default: 1024,
            validation: { min: 1, max: 32768 },
            group: 'Token Settings',
          },
          {
            name: 'max_output_tokens',
            label: 'Max Output Tokens',
            type: 'number',
            required: false,
            default: 512,
            validation: { min: 1, max: 8192 },
            group: 'Token Settings',
          },
          {
            name: 'max_wait_seconds',
            label: 'Max Wait Time (seconds)',
            type: 'number',
            required: false,
            default: 600,
            description: 'Maximum time to wait for benchmark completion (default: 10 min)',
            validation: { min: 60, max: 3600 },
            group: 'Advanced',
          },
        ],
      },
    ],
  },
  {
    category: 'Cluster',
    icon: '🖥️',
    actions: [
      {
        value: 'cluster_create',
        label: 'Create Cluster',
        icon: '➕',
        color: '#52c41a',
        description: 'Provision a new cluster',
        outputs: ['cluster_id', 'status', 'endpoint'],
        params: [
          {
            name: 'cluster_name',
            label: 'Cluster Name',
            type: 'string',
            required: true,
            placeholder: 'my-gpu-cluster',
          },
          {
            name: 'provider',
            label: 'Cloud Provider',
            type: 'select',
            required: true,
            options: [
              { label: 'AWS (EKS)', value: 'aws' },
              { label: 'Azure (AKS)', value: 'azure' },
              { label: 'GCP (GKE)', value: 'gcp' },
              { label: 'On-Premises', value: 'onprem' },
            ],
          },
          {
            name: 'region',
            label: 'Region',
            type: 'string',
            required: true,
            placeholder: 'us-west-2',
          },
          {
            name: 'node_type',
            label: 'Node Type',
            type: 'select',
            required: true,
            options: [
              { label: 'GPU - Small (1x A10G)', value: 'gpu-small' },
              { label: 'GPU - Medium (1x A100 40GB)', value: 'gpu-medium' },
              { label: 'GPU - Large (1x A100 80GB)', value: 'gpu-large' },
              { label: 'GPU - Multi (4x A100)', value: 'gpu-multi' },
              { label: 'CPU Only', value: 'cpu' },
            ],
          },
          {
            name: 'node_count',
            label: 'Node Count',
            type: 'number',
            required: true,
            default: 1,
            validation: { min: 1, max: 100 },
          },
        ],
      },
      {
        value: 'cluster_delete',
        label: 'Delete Cluster',
        icon: '🗑️',
        color: '#f5222d',
        description: 'Delete an existing cluster',
        outputs: ['success'],
        params: [
          {
            name: 'cluster_id',
            label: 'Cluster',
            type: 'cluster_ref',
            required: true,
          },
          {
            name: 'force',
            label: 'Force Delete',
            type: 'boolean',
            required: false,
            default: false,
            description: 'Force delete even with running workloads',
          },
        ],
      },
      {
        value: 'cluster_health',
        label: 'Health Check',
        icon: '💚',
        color: '#52c41a',
        description: 'Check cluster health status',
        outputs: ['healthy', 'status', 'issues'],
        params: [
          {
            name: 'cluster_id',
            label: 'Cluster',
            type: 'cluster_ref',
            required: true,
          },
          {
            name: 'checks',
            label: 'Health Checks',
            type: 'multiselect',
            required: false,
            options: [
              { label: 'Node Status', value: 'nodes' },
              { label: 'API Server', value: 'api' },
              { label: 'Storage', value: 'storage' },
              { label: 'Network', value: 'network' },
              { label: 'GPU Drivers', value: 'gpu' },
            ],
            default: ['nodes', 'api', 'gpu'],
          },
        ],
      },
    ],
  },
  {
    category: 'Control Flow',
    icon: '🔀',
    actions: [
      {
        value: 'conditional',
        label: 'Conditional',
        icon: '🔀',
        color: '#fa8c16',
        description: 'Route to different steps based on conditions',
        outputs: ['matched_branch', 'matched_label', 'target_step', 'branch', 'result'],
        params: [
          {
            name: 'branches',
            label: 'Branches',
            type: 'branches',
            required: true,
            description: 'Define conditions and their target steps. First matching condition wins.',
            default: [
              { id: 'branch_0', label: 'Branch 1', condition: '', target_step: null },
            ],
          },
        ],
      },
      {
        value: 'delay',
        label: 'Delay',
        icon: '⏱️',
        color: '#faad14',
        description: 'Wait for specified time',
        outputs: ['completed'],
        params: [
          {
            name: 'duration_seconds',
            label: 'Duration (seconds)',
            type: 'number',
            required: true,
            default: 60,
            validation: { min: 1, max: 86400 },
          },
          {
            name: 'reason',
            label: 'Reason',
            type: 'string',
            required: false,
            placeholder: 'Waiting for resources to stabilize',
          },
        ],
      },
      {
        value: 'log',
        label: 'Log',
        icon: '📝',
        color: '#8c8c8c',
        description: 'Log a message',
        outputs: ['logged'],
        params: [
          {
            name: 'message',
            label: 'Message',
            type: 'template',
            required: true,
            placeholder: 'Processing {{ params.model_id }}...',
          },
          {
            name: 'level',
            label: 'Log Level',
            type: 'select',
            required: false,
            options: [
              { label: 'Info', value: 'info' },
              { label: 'Warning', value: 'warning' },
              { label: 'Error', value: 'error' },
              { label: 'Debug', value: 'debug' },
            ],
            default: 'info',
          },
        ],
      },
    ],
  },
  {
    category: 'Integration',
    icon: '🔗',
    actions: [
      {
        value: 'http_request',
        label: 'HTTP Request',
        icon: '🌐',
        color: '#1890ff',
        description: 'Make an HTTP API call',
        outputs: ['status_code', 'body', 'headers'],
        params: [
          {
            name: 'url',
            label: 'URL',
            type: 'template',
            required: true,
            placeholder: 'https://api.example.com/endpoint',
          },
          {
            name: 'method',
            label: 'Method',
            type: 'select',
            required: true,
            options: [
              { label: 'GET', value: 'GET' },
              { label: 'POST', value: 'POST' },
              { label: 'PUT', value: 'PUT' },
              { label: 'PATCH', value: 'PATCH' },
              { label: 'DELETE', value: 'DELETE' },
            ],
            default: 'GET',
          },
          {
            name: 'headers',
            label: 'Headers',
            type: 'json',
            required: false,
            placeholder: '{"Authorization": "Bearer ..."}',
          },
          {
            name: 'body',
            label: 'Body',
            type: 'json',
            required: false,
            showWhen: { param: 'method', notEquals: 'GET' },
          },
          {
            name: 'timeout_seconds',
            label: 'Timeout (seconds)',
            type: 'number',
            required: false,
            default: 30,
            group: 'Advanced',
          },
        ],
      },
      {
        value: 'notification',
        label: 'Notification',
        icon: '🔔',
        color: '#eb2f96',
        description: 'Send a notification',
        outputs: ['sent', 'notification_id'],
        params: [
          {
            name: 'channel',
            label: 'Channel',
            type: 'select',
            required: true,
            options: [
              { label: 'Email', value: 'email' },
              { label: 'Slack', value: 'slack' },
              { label: 'Teams', value: 'teams' },
              { label: 'Webhook', value: 'webhook' },
            ],
          },
          {
            name: 'recipient',
            label: 'Recipient',
            type: 'string',
            required: true,
            placeholder: 'team@example.com or #channel',
          },
          {
            name: 'title',
            label: 'Title',
            type: 'template',
            required: true,
            placeholder: 'Deployment Complete',
          },
          {
            name: 'message',
            label: 'Message',
            type: 'template',
            required: true,
            placeholder: 'Model {{ params.model_id }} deployed successfully',
          },
          {
            name: 'severity',
            label: 'Severity',
            type: 'select',
            required: false,
            options: [
              { label: 'Info', value: 'info' },
              { label: 'Success', value: 'success' },
              { label: 'Warning', value: 'warning' },
              { label: 'Error', value: 'error' },
            ],
            default: 'info',
          },
        ],
      },
      {
        value: 'webhook',
        label: 'Webhook',
        icon: '📡',
        color: '#722ed1',
        description: 'Trigger a webhook',
        outputs: ['success', 'response'],
        params: [
          {
            name: 'url',
            label: 'Webhook URL',
            type: 'string',
            required: true,
            placeholder: 'https://hooks.example.com/trigger',
          },
          {
            name: 'payload',
            label: 'Payload',
            type: 'json',
            required: false,
            placeholder: '{"event": "deployment_complete"}',
          },
          {
            name: 'secret',
            label: 'Secret (for signing)',
            type: 'string',
            required: false,
            description: 'HMAC secret for request signing',
          },
        ],
      },
    ],
  },
  {
    category: 'Data',
    icon: '📦',
    actions: [
      {
        value: 'transform',
        label: 'Transform',
        icon: '🔄',
        color: '#1890ff',
        description: 'Transform data',
        outputs: ['result'],
        params: [
          {
            name: 'input',
            label: 'Input Data',
            type: 'template',
            required: true,
            placeholder: '{{ steps.previous.outputs.data }}',
          },
          {
            name: 'expression',
            label: 'Transform Expression',
            type: 'template',
            required: true,
            placeholder: '{{ input | map("name") | list }}',
            description: 'Jinja2 expression to transform the input',
          },
        ],
      },
      {
        value: 'aggregate',
        label: 'Aggregate',
        icon: '📊',
        color: '#eb2f96',
        description: 'Aggregate multiple inputs',
        outputs: ['result'],
        params: [
          {
            name: 'inputs',
            label: 'Input Sources',
            type: 'json',
            required: true,
            placeholder: '["{{ steps.a.outputs.value }}", "{{ steps.b.outputs.value }}"]',
          },
          {
            name: 'operation',
            label: 'Operation',
            type: 'select',
            required: true,
            options: [
              { label: 'Merge Objects', value: 'merge' },
              { label: 'Concatenate Arrays', value: 'concat' },
              { label: 'Sum', value: 'sum' },
              { label: 'Average', value: 'avg' },
              { label: 'First Non-Null', value: 'coalesce' },
            ],
          },
        ],
      },
      {
        value: 'set_output',
        label: 'Set Output',
        icon: '📤',
        color: '#13c2c2',
        description: 'Set workflow outputs',
        outputs: ['value'],
        params: [
          {
            name: 'name',
            label: 'Output Name',
            type: 'string',
            required: true,
            placeholder: 'result',
          },
          {
            name: 'value',
            label: 'Value',
            type: 'template',
            required: true,
            placeholder: '{{ steps.final.outputs.data }}',
          },
        ],
      },
    ],
  },
];

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Flattened list of all actions for quick lookup
 */
export const allActions: ActionMeta[] = actionCategories.flatMap((cat) => cat.actions);

/**
 * Get action metadata by action type
 */
export function getActionMeta(action: string): ActionMeta {
  return (
    allActions.find((a) => a.value === action) || {
      value: action,
      label: action,
      icon: '⚙️',
      color: '#8c8c8c',
      description: 'Custom action',
      params: [],
    }
  );
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

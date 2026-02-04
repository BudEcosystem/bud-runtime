import { create } from "zustand";
import { AppRequest } from "src/pages/api/requests";

// API endpoint for budpipeline via budapp proxy
const BUDPIPELINE_API = "/budpipeline";

// Use real API or fallback to mock data (for development without backend)
const USE_MOCK_DATA = process.env.NEXT_PUBLIC_USE_MOCK_WORKFLOW_DATA === "true";

// Types for budpipeline DAG orchestration
export type PipelineParameter = {
  name: string;
  type: "string" | "integer" | "boolean" | "object" | "array";
  description?: string;
  default?: any;
  required?: boolean;
};

export type PipelineStep = {
  id: string;
  name: string;
  action: string;
  params: Record<string, any>;
  depends_on: string[];
  condition?: string;
  on_failure?: "stop" | "continue";
  timeout_seconds?: number;
};

export type DAGDefinition = {
  name: string;
  version?: string;
  description?: string;
  parameters: PipelineParameter[];
  steps: PipelineStep[];
  outputs?: Record<string, string>;
};

export type BudPipelineItem = {
  id: string;
  name: string;
  version?: string;
  status: "active" | "inactive" | "draft";
  created_at: string;
  updated_at?: string;
  step_count: number;
  dag: DAGDefinition;
  warnings?: string[];
  execution_count?: number;
  last_execution_at?: string;
};

export type PipelineStepExecution = {
  step_id: string;
  name: string;
  status: "pending" | "running" | "completed" | "skipped" | "failed";
  started_at?: string;
  completed_at?: string;
  outputs: Record<string, any>;
  error?: string;
};

export type PipelineExecution = {
  execution_id: string;
  workflow_id: string;
  workflow_name: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  started_at: string;
  completed_at?: string;
  params: Record<string, any>;
  outputs: Record<string, any>;
  error?: string;
  steps: PipelineStepExecution[];
};

// Dummy data for UI development
// Design principle: Workflow params are for high-level control (flags, options)
// Action-specific resources (model_id, cluster_id) are in step params for flexibility
const DUMMY_WORKFLOWS: BudPipelineItem[] = [
  {
    id: "wf-001",
    name: "Model Deployment Pipeline",
    version: "1.0.0",
    status: "active",
    created_at: "2024-12-15T10:30:00Z",
    updated_at: "2024-12-28T14:20:00Z",
    step_count: 5,
    execution_count: 23,
    last_execution_at: "2024-12-30T09:15:00Z",
    dag: {
      name: "Model Deployment Pipeline",
      version: "1.0.0",
      description: "Automated pipeline for deploying ML models to production clusters",
      parameters: [
        { name: "enable_monitoring", type: "boolean", description: "Enable metrics collection", default: true },
        { name: "dry_run", type: "boolean", description: "Simulate without deploying", default: false },
      ],
      steps: [
        {
          id: "validate_model",
          name: "Validate Model",
          action: "http_request",
          params: {
            url: "/models/llama-3-8b/validate",
            method: "POST",
          },
          depends_on: [],
        },
        {
          id: "check_cluster",
          name: "Check Cluster Health",
          action: "http_request",
          params: {
            url: "/clusters/prod-cluster-01/health",
            method: "GET",
          },
          depends_on: [],
        },
        {
          id: "prepare_config",
          name: "Prepare Deploy Config",
          action: "transform",
          params: {
            input: {
              model: "{{ steps.validate_model.outputs.model }}",
              cluster: "{{ steps.check_cluster.outputs.cluster }}",
              replicas: 2,
            },
            operation: "passthrough",
          },
          depends_on: ["validate_model", "check_cluster"],
        },
        {
          id: "deploy",
          name: "Deploy to Cluster",
          action: "http_request",
          condition: "{{ not params.dry_run }}",
          params: {
            url: "/deployments",
            method: "POST",
            body: "{{ steps.prepare_config.outputs.result }}",
          },
          depends_on: ["prepare_config"],
        },
        {
          id: "setup_monitoring",
          name: "Setup Monitoring",
          action: "http_request",
          condition: "{{ params.enable_monitoring and not params.dry_run }}",
          params: {
            url: "/monitoring/setup",
            method: "POST",
          },
          depends_on: ["deploy"],
        },
      ],
      outputs: {
        deployment_id: "{{ steps.deploy.outputs.deployment_id }}",
        endpoint_url: "{{ steps.deploy.outputs.endpoint_url }}",
      },
    },
  },
  {
    id: "wf-002",
    name: "Data Processing Pipeline",
    version: "2.1.0",
    status: "active",
    created_at: "2024-11-20T08:00:00Z",
    updated_at: "2024-12-25T16:45:00Z",
    step_count: 4,
    execution_count: 156,
    last_execution_at: "2024-12-31T11:30:00Z",
    dag: {
      name: "Data Processing Pipeline",
      version: "2.1.0",
      description: "Process and transform datasets for ML training",
      parameters: [
        { name: "output_format", type: "string", description: "Output format", default: "parquet" },
        { name: "validate_schema", type: "boolean", description: "Validate data schema", default: true },
      ],
      steps: [
        {
          id: "fetch_data",
          name: "Fetch Dataset",
          action: "http_request",
          params: { url: "/datasets/training-data-v3", method: "GET" },
          depends_on: [],
        },
        {
          id: "validate_data",
          name: "Validate Data",
          action: "transform",
          condition: "{{ params.validate_schema }}",
          params: { operation: "validate" },
          depends_on: ["fetch_data"],
        },
        {
          id: "transform_data",
          name: "Transform Data",
          action: "transform",
          params: {
            operation: "uppercase",
            input: "{{ steps.validate_data.outputs.result }}",
          },
          depends_on: ["validate_data"],
        },
        {
          id: "save_output",
          name: "Save Output",
          action: "http_request",
          params: {
            url: "/datasets/training-data-v3/output",
            method: "PUT",
            body: { format: "{{ params.output_format }}" },
          },
          depends_on: ["transform_data"],
        },
      ],
      outputs: {
        output_path: "{{ steps.save_output.outputs.path }}",
        record_count: "{{ steps.transform_data.outputs.count }}",
      },
    },
  },
  {
    id: "wf-003",
    name: "Model Scaling Workflow",
    version: "1.2.0",
    status: "active",
    created_at: "2024-12-01T12:00:00Z",
    step_count: 3,
    execution_count: 8,
    dag: {
      name: "Model Scaling Workflow",
      version: "1.2.0",
      description: "Automatically scale model replicas based on load",
      parameters: [
        { name: "wait_for_ready", type: "boolean", description: "Wait for replicas to be ready", default: true },
      ],
      steps: [
        {
          id: "get_current",
          name: "Get Current State",
          action: "http_request",
          params: { url: "/endpoints/llama-endpoint-prod", method: "GET" },
          depends_on: [],
        },
        {
          id: "scale",
          name: "Scale Replicas",
          action: "http_request",
          params: {
            url: "/endpoints/llama-endpoint-prod/scale",
            method: "POST",
            body: { replicas: 4 },
          },
          depends_on: ["get_current"],
        },
        {
          id: "wait_ready",
          name: "Wait for Ready",
          action: "delay",
          condition: "{{ params.wait_for_ready }}",
          params: { seconds: 30 },
          depends_on: ["scale"],
        },
      ],
      outputs: {
        new_replica_count: "{{ steps.scale.outputs.replicas }}",
        status: "{{ steps.scale.outputs.status }}",
      },
    },
  },
  {
    id: "wf-004",
    name: "Multi-Cluster Deployment",
    version: "1.0.0",
    status: "draft",
    created_at: "2024-12-28T09:00:00Z",
    step_count: 4,
    execution_count: 0,
    dag: {
      name: "Multi-Cluster Deployment",
      version: "1.0.0",
      description: "Deploy model to multiple clusters with health checks",
      parameters: [
        { name: "notify_on_complete", type: "boolean", description: "Send notification when done", default: true },
      ],
      steps: [
        {
          id: "deploy_cluster_1",
          name: "Deploy to US Cluster",
          action: "http_request",
          params: {
            url: "/clusters/us-prod-01/deploy",
            method: "POST",
            body: { model_id: "gpt-4-mini", replicas: 2 },
          },
          depends_on: [],
        },
        {
          id: "deploy_cluster_2",
          name: "Deploy to EU Cluster",
          action: "http_request",
          params: {
            url: "/clusters/eu-prod-01/deploy",
            method: "POST",
            body: { model_id: "gpt-4-mini", replicas: 2 },
          },
          depends_on: [],
        },
        {
          id: "verify_all",
          name: "Verify All Deployments",
          action: "aggregate",
          params: {
            inputs: [
              "{{ steps.deploy_cluster_1.outputs }}",
              "{{ steps.deploy_cluster_2.outputs }}",
            ],
            operation: "list",
          },
          depends_on: ["deploy_cluster_1", "deploy_cluster_2"],
        },
        {
          id: "notify",
          name: "Send Notification",
          action: "notification",
          condition: "{{ params.notify_on_complete }}",
          params: {
            channel: "deployments",
            message: "Multi-cluster deployment completed",
          },
          depends_on: ["verify_all"],
        },
      ],
      outputs: {
        cluster_1_status: "{{ steps.deploy_cluster_1.outputs.status }}",
        cluster_2_status: "{{ steps.deploy_cluster_2.outputs.status }}",
      },
    },
  },
];

const DUMMY_EXECUTIONS: PipelineExecution[] = [
  {
    execution_id: "exec-001",
    workflow_id: "wf-001",
    workflow_name: "Model Deployment Pipeline",
    status: "completed",
    started_at: "2024-12-30T09:15:00Z",
    completed_at: "2024-12-30T09:17:23Z",
    params: {
      enable_monitoring: true,
      dry_run: false,
    },
    outputs: {
      deployment_id: "deploy-abc123",
      endpoint_url: "https://api.bud.ai/v1/models/llama-3-8b",
    },
    steps: [
      {
        step_id: "validate_model",
        name: "Validate Model",
        status: "completed",
        started_at: "2024-12-30T09:15:00Z",
        completed_at: "2024-12-30T09:15:12Z",
        outputs: { model: { id: "llama-3-8b", valid: true } },
      },
      {
        step_id: "check_cluster",
        name: "Check Cluster Health",
        status: "completed",
        started_at: "2024-12-30T09:15:00Z",
        completed_at: "2024-12-30T09:15:08Z",
        outputs: { cluster: { id: "prod-cluster-01", healthy: true } },
      },
      {
        step_id: "prepare_config",
        name: "Prepare Deploy Config",
        status: "completed",
        started_at: "2024-12-30T09:15:12Z",
        completed_at: "2024-12-30T09:15:14Z",
        outputs: { result: { model: "llama-3-8b", replicas: 2 } },
      },
      {
        step_id: "deploy",
        name: "Deploy to Cluster",
        status: "completed",
        started_at: "2024-12-30T09:15:14Z",
        completed_at: "2024-12-30T09:17:10Z",
        outputs: {
          deployment_id: "deploy-abc123",
          endpoint_url: "https://api.bud.ai/v1/models/llama-3-8b",
        },
      },
      {
        step_id: "setup_monitoring",
        name: "Setup Monitoring",
        status: "completed",
        started_at: "2024-12-30T09:17:10Z",
        completed_at: "2024-12-30T09:17:23Z",
        outputs: { monitoring_enabled: true },
      },
    ],
  },
  {
    execution_id: "exec-002",
    workflow_id: "wf-001",
    workflow_name: "Model Deployment Pipeline",
    status: "completed",
    started_at: "2024-12-29T14:20:00Z",
    completed_at: "2024-12-29T14:20:15Z",
    params: {
      enable_monitoring: false,
      dry_run: true,
    },
    outputs: {},
    steps: [
      {
        step_id: "validate_model",
        name: "Validate Model",
        status: "completed",
        started_at: "2024-12-29T14:20:00Z",
        completed_at: "2024-12-29T14:20:10Z",
        outputs: { model: { id: "llama-3-8b", valid: true } },
      },
      {
        step_id: "check_cluster",
        name: "Check Cluster Health",
        status: "completed",
        started_at: "2024-12-29T14:20:00Z",
        completed_at: "2024-12-29T14:20:08Z",
        outputs: { cluster: { id: "prod-cluster-01", healthy: true } },
      },
      {
        step_id: "prepare_config",
        name: "Prepare Deploy Config",
        status: "completed",
        started_at: "2024-12-29T14:20:10Z",
        completed_at: "2024-12-29T14:20:12Z",
        outputs: { result: { model: "llama-3-8b", replicas: 2 } },
      },
      {
        step_id: "deploy",
        name: "Deploy to Cluster",
        status: "skipped",
        outputs: {},
      },
      {
        step_id: "setup_monitoring",
        name: "Setup Monitoring",
        status: "skipped",
        outputs: {},
      },
    ],
  },
  {
    execution_id: "exec-003",
    workflow_id: "wf-002",
    workflow_name: "Data Processing Pipeline",
    status: "running",
    started_at: "2024-12-31T11:30:00Z",
    params: {
      output_format: "parquet",
      validate_schema: true,
    },
    outputs: {},
    steps: [
      {
        step_id: "fetch_data",
        name: "Fetch Dataset",
        status: "completed",
        started_at: "2024-12-31T11:30:00Z",
        completed_at: "2024-12-31T11:30:45Z",
        outputs: { records: 10000 },
      },
      {
        step_id: "validate_data",
        name: "Validate Data",
        status: "completed",
        started_at: "2024-12-31T11:30:45Z",
        completed_at: "2024-12-31T11:31:20Z",
        outputs: { valid: true, errors: 0 },
      },
      {
        step_id: "transform_data",
        name: "Transform Data",
        status: "running",
        started_at: "2024-12-31T11:31:20Z",
        outputs: {},
      },
      {
        step_id: "save_output",
        name: "Save Output",
        status: "pending",
        outputs: {},
      },
    ],
  },
];

export type ValidationResult = {
  valid: boolean;
  errors: string[];
  warnings: string[];
};

// ============================================================================
// Trigger Types (Schedules, Webhooks, Event Triggers)
// ============================================================================

export type ScheduleType = "cron" | "interval" | "one_time";

export type ScheduleConfig = {
  type: ScheduleType;
  expression?: string;  // Cron: "0 9 * * 1-5", Interval: "@every 1h"
  timezone?: string;
  run_at?: string;  // For one_time
};

export type PipelineSchedule = {
  id: string;
  workflow_id: string;
  name: string;
  schedule: ScheduleConfig;
  params: Record<string, any>;
  enabled: boolean;
  description?: string;
  created_at: string;
  updated_at: string;
  next_run_at?: string;
  last_run_at?: string;
  last_execution_id?: string;
  last_execution_status?: string;
  run_count: number;
  max_runs?: number;
  expires_at?: string;
  status: "active" | "paused" | "expired" | "completed";
};

export type WebhookConfig = {
  require_secret: boolean;
  allowed_ips?: string[];
  headers_to_include?: string[];
};

export type PipelineWebhook = {
  id: string;
  workflow_id: string;
  name: string;
  endpoint_url: string;
  config: WebhookConfig;
  params: Record<string, any>;
  enabled: boolean;
  created_at: string;
  updated_at: string;
  last_triggered_at?: string;
  trigger_count: number;
  secret?: string;  // Only returned on creation
};

export type EventTriggerConfig = {
  event_type: string;
  filters: Record<string, any>;
};

export type PipelineEventTrigger = {
  id: string;
  workflow_id: string;
  name: string;
  config: EventTriggerConfig;
  params: Record<string, any>;
  enabled: boolean;
  created_at: string;
  updated_at: string;
  last_triggered_at?: string;
  trigger_count: number;
};

export const SUPPORTED_EVENT_TYPES = [
  { value: "model.onboarded", label: "Model Onboarded", description: "When a new model is added" },
  { value: "model.deleted", label: "Model Deleted", description: "When a model is removed" },
  { value: "benchmark.completed", label: "Benchmark Completed", description: "When a benchmark finishes successfully" },
  { value: "benchmark.failed", label: "Benchmark Failed", description: "When a benchmark fails" },
  { value: "cluster.healthy", label: "Cluster Healthy", description: "When cluster health check passes" },
  { value: "cluster.unhealthy", label: "Cluster Unhealthy", description: "When cluster health check fails" },
  { value: "deployment.created", label: "Deployment Created", description: "When a new deployment is created" },
  { value: "deployment.failed", label: "Deployment Failed", description: "When a deployment fails" },
];

// Pagination info returned by backend
export type PaginationInfo = {
  page: number;
  page_size: number;
  total_count: number;
  total_pages: number;
};

type BudPipelineStore = {
  // State
  workflows: BudPipelineItem[];
  selectedWorkflow: BudPipelineItem | null;
  executions: PipelineExecution[];
  executionsPagination: PaginationInfo | null;
  selectedExecution: PipelineExecution | null;
  isLoading: boolean;
  error: string | null;

  // Trigger state
  schedules: PipelineSchedule[];
  webhooks: PipelineWebhook[];
  eventTriggers: PipelineEventTrigger[];
  triggersLoading: boolean;

  // Actions
  getWorkflows: () => Promise<void>;
  getWorkflow: (id: string) => Promise<void>;
  getExecutions: (workflowId?: string, page?: number, pageSize?: number) => Promise<void>;
  getExecution: (executionId: string) => Promise<void>;
  createWorkflow: (dag: DAGDefinition) => Promise<BudPipelineItem | null>;
  updateWorkflow: (id: string, dag: DAGDefinition) => Promise<BudPipelineItem | null>;
  executeWorkflow: (workflowId: string, params: Record<string, any>) => Promise<PipelineExecution | null>;
  deleteWorkflow: (id: string) => Promise<boolean>;
  validatePipeline: (dag: DAGDefinition) => Promise<ValidationResult>;
  clearSelection: () => void;

  // Trigger Actions - Schedules
  getSchedules: (workflowId?: string) => Promise<void>;
  createSchedule: (data: { workflow_id: string; name: string; schedule: ScheduleConfig; params?: Record<string, any>; enabled?: boolean; description?: string }) => Promise<PipelineSchedule | null>;
  updateSchedule: (id: string, updates: Partial<PipelineSchedule>) => Promise<PipelineSchedule | null>;
  deleteSchedule: (id: string) => Promise<boolean>;
  pauseSchedule: (id: string) => Promise<boolean>;
  resumeSchedule: (id: string) => Promise<boolean>;
  triggerSchedule: (id: string) => Promise<boolean>;

  // Trigger Actions - Webhooks
  getWebhooks: (workflowId?: string) => Promise<void>;
  createWebhook: (data: { workflow_id: string; name: string; require_secret?: boolean; params?: Record<string, any> }) => Promise<PipelineWebhook | null>;
  deleteWebhook: (id: string) => Promise<boolean>;
  rotateWebhookSecret: (id: string) => Promise<string | null>;

  // Trigger Actions - Event Triggers
  getEventTriggers: (workflowId?: string) => Promise<void>;
  createEventTrigger: (data: { workflow_id: string; name: string; event_type: string; filters?: Record<string, any>; params?: Record<string, any> }) => Promise<PipelineEventTrigger | null>;
  deleteEventTrigger: (id: string) => Promise<boolean>;
};

export const useBudPipeline = create<BudPipelineStore>((set, get) => ({
  // Initial state
  workflows: [],
  selectedWorkflow: null,
  executions: [],
  executionsPagination: null,
  selectedExecution: null,
  isLoading: false,
  error: null,

  // Trigger state
  schedules: [],
  webhooks: [],
  eventTriggers: [],
  triggersLoading: false,

  // Get all workflows
  getWorkflows: async () => {
    set({ isLoading: true, error: null });

    if (USE_MOCK_DATA) {
      // Fallback to mock data for development
      await new Promise((resolve) => setTimeout(resolve, 500));
      set({ workflows: DUMMY_WORKFLOWS, isLoading: false });
      return;
    }

    try {
      const response = await AppRequest.Get(BUDPIPELINE_API);
      const workflows = response.data?.workflows || response.data || [];
      set({ workflows, isLoading: false });
    } catch (error: any) {
      console.error("Failed to fetch workflows:", error);
      set({
        error: error?.response?.data?.message || "Failed to fetch workflows",
        isLoading: false,
        workflows: [], // Clear workflows on error
      });
    }
  },

  // Get single workflow
  getWorkflow: async (id: string) => {
    set({ isLoading: true, error: null });

    if (USE_MOCK_DATA) {
      await new Promise((resolve) => setTimeout(resolve, 300));
      const workflow = DUMMY_WORKFLOWS.find((w) => w.id === id);
      if (workflow) {
        set({ selectedWorkflow: workflow, isLoading: false });
      } else {
        set({ error: "Workflow not found", isLoading: false });
      }
      return;
    }

    try {
      const response = await AppRequest.Get(`${BUDPIPELINE_API}/${id}`);
      const workflow = response.data;
      set({ selectedWorkflow: workflow, isLoading: false });
    } catch (error: any) {
      console.error("Failed to fetch workflow:", error);
      set({
        error: error?.response?.data?.message || "Workflow not found",
        isLoading: false,
        selectedWorkflow: null,
      });
    }
  },

  // Get executions with pagination support
  getExecutions: async (workflowId?: string, page: number = 1, pageSize: number = 20) => {
    set({ isLoading: true, error: null });

    if (USE_MOCK_DATA) {
      await new Promise((resolve) => setTimeout(resolve, 400));
      const allExecutions = workflowId
        ? DUMMY_EXECUTIONS.filter((e) => e.workflow_id === workflowId)
        : DUMMY_EXECUTIONS;
      // Simulate pagination for mock data
      const start = (page - 1) * pageSize;
      const executions = allExecutions.slice(start, start + pageSize);
      const pagination: PaginationInfo = {
        page,
        page_size: pageSize,
        total_count: allExecutions.length,
        total_pages: Math.ceil(allExecutions.length / pageSize),
      };
      set({ executions, executionsPagination: pagination, isLoading: false });
      return;
    }

    try {
      const params: Record<string, any> = { page, page_size: pageSize };
      if (workflowId) {
        params.workflow_id = workflowId;
      }
      const response = await AppRequest.Get(`${BUDPIPELINE_API}/executions`, { params });
      const rawExecutions = response.data?.executions || (Array.isArray(response.data) ? response.data : []);
      const pagination = response.data?.pagination || null;
      // Map backend field names to frontend expected names
      const executions = rawExecutions.map((e: any) => ({
        execution_id: e.execution_id || e.id,
        workflow_id: e.workflow_id || e.pipeline_definition?.workflow_id || e.id,
        workflow_name: e.workflow_name || e.pipeline_definition?.name || "Unknown Pipeline",
        status: e.status,
        started_at: e.started_at || e.start_time,
        completed_at: e.completed_at || e.end_time,
        params: e.params || e.pipeline_definition?.params || {},
        outputs: e.outputs || e.final_outputs || {},
        error: e.error || e.error_info?.message,
        steps: e.steps || [],
      }));
      set({ executions, executionsPagination: pagination, isLoading: false });
    } catch (error: any) {
      console.error("Failed to fetch executions:", error);
      set({
        error: error?.response?.data?.message || "Failed to fetch executions",
        isLoading: false,
        executions: [],
        executionsPagination: null,
      });
    }
  },

  // Get single execution
  getExecution: async (executionId: string) => {
    set({ isLoading: true, error: null });

    if (USE_MOCK_DATA) {
      await new Promise((resolve) => setTimeout(resolve, 300));
      const execution = DUMMY_EXECUTIONS.find((e) => e.execution_id === executionId);
      if (execution) {
        set({ selectedExecution: execution, isLoading: false });
      } else {
        set({ error: "Execution not found", isLoading: false });
      }
      return;
    }

    try {
      // Use progress endpoint to get execution with steps
      const response = await AppRequest.Get(`${BUDPIPELINE_API}/executions/${executionId}/progress`);
      const data = response.data;
      const e = data.execution || data;
      // Map backend field names to frontend expected names
      const execution = {
        execution_id: e.execution_id || e.id,
        workflow_id: e.workflow_id || e.pipeline_definition?.workflow_id || e.id,
        workflow_name: e.workflow_name || e.pipeline_definition?.workflow_name || e.pipeline_definition?.name || "Unknown Pipeline",
        status: e.status?.toLowerCase() || e.status,
        started_at: e.started_at || e.start_time,
        completed_at: e.completed_at || e.end_time,
        params: e.params || e.pipeline_definition?.params || {},
        outputs: e.outputs || e.final_outputs || {},
        error: e.error || e.error_info?.message,
        // Map steps from progress response
        steps: (data.steps || []).map((s: any) => ({
          step_id: s.step_id,
          name: s.step_name || s.name,
          status: s.status?.toLowerCase() || s.status,
          started_at: s.started_at || s.start_time,
          completed_at: s.completed_at || s.end_time,
          outputs: s.outputs || {},
          error: s.error || s.error_message,
        })),
      };
      set({ selectedExecution: execution, isLoading: false });
    } catch (error: any) {
      console.error("Failed to fetch execution:", error);
      set({
        error: error?.response?.data?.message || "Execution not found",
        isLoading: false,
        selectedExecution: null,
      });
    }
  },

  // Create workflow
  createWorkflow: async (dag: DAGDefinition) => {
    set({ isLoading: true, error: null });

    if (USE_MOCK_DATA) {
      await new Promise((resolve) => setTimeout(resolve, 500));
      const newWorkflow: BudPipelineItem = {
        id: `wf-${Date.now()}`,
        name: dag.name,
        version: dag.version,
        status: "draft",
        created_at: new Date().toISOString(),
        step_count: dag.steps.length,
        dag,
        execution_count: 0,
      };
      set((state) => ({
        workflows: [...state.workflows, newWorkflow],
        isLoading: false,
      }));
      return newWorkflow;
    }

    try {
      const response = await AppRequest.Post(BUDPIPELINE_API, {
        dag,
        name: dag.name,
      });
      const newWorkflow = response.data;
      set((state) => ({
        workflows: [...state.workflows, newWorkflow],
        isLoading: false,
      }));
      return newWorkflow;
    } catch (error: any) {
      console.error("Failed to create workflow:", error);
      // Extract error message from various possible response formats
      const responseData = error?.response?.data;
      const errorMessage =
        responseData?.message ||           // FastAPI ClientException format: {"message": "..."}
        responseData?.detail?.message ||   // FastAPI HTTPException with object: {"detail": {"message": "..."}}
        (typeof responseData?.detail === 'string' ? responseData?.detail : null) || // FastAPI HTTPException with string
        error?.message ||                  // Axios/network error
        "Failed to create workflow";
      set({
        error: errorMessage,
        isLoading: false,
      });
      return null;
    }
  },

  // Update workflow
  updateWorkflow: async (id: string, dag: DAGDefinition) => {
    set({ isLoading: true, error: null });

    if (USE_MOCK_DATA) {
      await new Promise((resolve) => setTimeout(resolve, 500));
      const updatedWorkflow: BudPipelineItem = {
        id,
        name: dag.name,
        version: dag.version,
        status: "draft",
        created_at: get().workflows.find((w) => w.id === id)?.created_at || new Date().toISOString(),
        updated_at: new Date().toISOString(),
        step_count: dag.steps.length,
        dag,
        execution_count: get().workflows.find((w) => w.id === id)?.execution_count || 0,
      };
      set((state) => ({
        workflows: state.workflows.map((w) => (w.id === id ? updatedWorkflow : w)),
        selectedWorkflow: updatedWorkflow,
        isLoading: false,
      }));
      return updatedWorkflow;
    }

    try {
      const response = await AppRequest.Put(`${BUDPIPELINE_API}/${id}`, {
        dag,
        name: dag.name,
      });
      const updatedWorkflow = response.data;
      set((state) => ({
        workflows: state.workflows.map((w) => (w.id === id ? updatedWorkflow : w)),
        selectedWorkflow: updatedWorkflow,
        isLoading: false,
      }));
      return updatedWorkflow;
    } catch (error: any) {
      console.error("Failed to update workflow:", error);
      // Extract error message from various possible response formats
      const responseData = error?.response?.data;
      const errorMessage =
        responseData?.message ||           // FastAPI ClientException format: {"message": "..."}
        responseData?.detail?.message ||   // FastAPI HTTPException with object: {"detail": {"message": "..."}}
        (typeof responseData?.detail === 'string' ? responseData?.detail : null) || // FastAPI HTTPException with string
        error?.message ||                  // Axios/network error
        "Failed to update workflow";
      set({
        error: errorMessage,
        isLoading: false,
      });
      return null;
    }
  },

  // Execute workflow
  executeWorkflow: async (workflowId: string, params: Record<string, any>) => {
    set({ isLoading: true, error: null });

    if (USE_MOCK_DATA) {
      await new Promise((resolve) => setTimeout(resolve, 500));
      const workflow = get().workflows.find((w) => w.id === workflowId);
      if (!workflow) {
        set({ error: "Workflow not found", isLoading: false });
        return null;
      }
      const newExecution: PipelineExecution = {
        execution_id: `exec-${Date.now()}`,
        workflow_id: workflowId,
        workflow_name: workflow.name,
        status: "running",
        started_at: new Date().toISOString(),
        params,
        outputs: {},
        steps: workflow.dag.steps.map((step) => ({
          step_id: step.id,
          name: step.name,
          status: "pending",
          outputs: {},
        })),
      };
      set((state) => ({
        executions: [newExecution, ...state.executions],
        isLoading: false,
      }));
      return newExecution;
    }

    try {
      const response = await AppRequest.Post(`${BUDPIPELINE_API}/${workflowId}/execute`, {
        params,
      });
      const data = response.data;

      // Check for error response even with 2xx status (backend may return error in body)
      if (data?.object === "error" || data?.detail) {
        const errorMessage = data?.message || data?.detail?.error || (typeof data?.detail === 'object' ? JSON.stringify(data.detail) : data?.detail) || "Failed to execute workflow";
        console.error("Execute workflow error response:", data);
        set({
          error: errorMessage,
          isLoading: false,
        });
        return null;
      }

      const newExecution = data;
      set((state) => ({
        executions: [newExecution, ...state.executions],
        isLoading: false,
      }));
      return newExecution;
    } catch (error: any) {
      console.error("Failed to execute workflow:", error);
      // Extract error message from various possible response formats
      const responseData = error?.response?.data;
      const errorMessage =
        responseData?.message ||           // FastAPI ClientException format: {"message": "..."}
        (typeof responseData?.detail === 'object' ? JSON.stringify(responseData.detail) : responseData?.detail) ||  // FastAPI HTTPException format: {"detail": "..."}
        (typeof responseData === "string" ? responseData : null) ||
        error?.message ||                  // Axios/network error
        "Failed to execute workflow";
      set({
        error: errorMessage,
        isLoading: false,
      });
      return null;
    }
  },

  // Delete workflow
  deleteWorkflow: async (id: string) => {
    set({ isLoading: true, error: null });

    if (USE_MOCK_DATA) {
      await new Promise((resolve) => setTimeout(resolve, 300));
      set((state) => ({
        workflows: state.workflows.filter((w) => w.id !== id),
        isLoading: false,
      }));
      return true;
    }

    try {
      await AppRequest.Delete(`${BUDPIPELINE_API}/${id}`);
      set((state) => ({
        workflows: state.workflows.filter((w) => w.id !== id),
        isLoading: false,
      }));
      return true;
    } catch (error: any) {
      console.error("Failed to delete workflow:", error);
      set({
        error: error?.response?.data?.message || "Failed to delete workflow",
        isLoading: false,
      });
      return false;
    }
  },

  // Validate workflow DAG
  validatePipeline: async (dag: DAGDefinition) => {
    if (USE_MOCK_DATA) {
      // Basic client-side validation for mock mode
      const errors: string[] = [];
      const warnings: string[] = [];

      if (!dag.name) errors.push("Workflow name is required");
      if (!dag.steps || dag.steps.length === 0) errors.push("At least one step is required");

      // Check for duplicate step IDs
      const stepIds = dag.steps.map((s) => s.id);
      const duplicateIds = stepIds.filter((id, idx) => stepIds.indexOf(id) !== idx);
      if (duplicateIds.length > 0) {
        errors.push(`Duplicate step IDs: ${duplicateIds.join(", ")}`);
      }

      // Check for invalid dependencies
      dag.steps.forEach((step) => {
        step.depends_on.forEach((depId) => {
          if (!stepIds.includes(depId)) {
            errors.push(`Step "${step.id}" depends on non-existent step "${depId}"`);
          }
        });
      });

      return { valid: errors.length === 0, errors, warnings };
    }

    try {
      const response = await AppRequest.Post(`${BUDPIPELINE_API}/validate`, { dag });
      return response.data as ValidationResult;
    } catch (error: any) {
      console.error("Failed to validate workflow:", error);
      return {
        valid: false,
        errors: [error?.response?.data?.message || "Validation failed"],
        warnings: [],
      };
    }
  },

  // Clear selection
  clearSelection: () => {
    set({ selectedWorkflow: null, selectedExecution: null });
  },

  // ============================================================================
  // Schedule Actions
  // ============================================================================

  getSchedules: async (workflowId?: string) => {
    set({ triggersLoading: true });
    try {
      const params = workflowId ? { workflow_id: workflowId } : {};
      const response = await AppRequest.Get(`${BUDPIPELINE_API}/schedules`, { params });
      const schedules = response.data?.schedules || response.data || [];
      set({ schedules, triggersLoading: false });
    } catch (error: any) {
      console.error("Failed to fetch schedules:", error);
      set({ triggersLoading: false, schedules: [] });
    }
  },

  createSchedule: async (data) => {
    set({ triggersLoading: true });
    try {
      const response = await AppRequest.Post(`${BUDPIPELINE_API}/schedules`, data);
      const newSchedule = response.data;
      set((state) => ({
        schedules: [...state.schedules, newSchedule],
        triggersLoading: false,
      }));
      return newSchedule;
    } catch (error: any) {
      console.error("Failed to create schedule:", error);
      set({ triggersLoading: false });
      return null;
    }
  },

  updateSchedule: async (id, updates) => {
    try {
      const response = await AppRequest.Put(`${BUDPIPELINE_API}/schedules/${id}`, updates);
      const updatedSchedule = response.data;
      set((state) => ({
        schedules: state.schedules.map((s) => (s.id === id ? updatedSchedule : s)),
      }));
      return updatedSchedule;
    } catch (error: any) {
      console.error("Failed to update schedule:", error);
      return null;
    }
  },

  deleteSchedule: async (id) => {
    try {
      await AppRequest.Delete(`${BUDPIPELINE_API}/schedules/${id}`);
      set((state) => ({
        schedules: state.schedules.filter((s) => s.id !== id),
      }));
      return true;
    } catch (error: any) {
      console.error("Failed to delete schedule:", error);
      return false;
    }
  },

  pauseSchedule: async (id) => {
    try {
      await AppRequest.Post(`${BUDPIPELINE_API}/schedules/${id}/pause`);
      set((state) => ({
        schedules: state.schedules.map((s) =>
          s.id === id ? { ...s, enabled: false, status: "paused" as const } : s
        ),
      }));
      return true;
    } catch (error: any) {
      console.error("Failed to pause schedule:", error);
      return false;
    }
  },

  resumeSchedule: async (id) => {
    try {
      const response = await AppRequest.Post(`${BUDPIPELINE_API}/schedules/${id}/resume`);
      const updatedSchedule = response.data;
      set((state) => ({
        schedules: state.schedules.map((s) => (s.id === id ? updatedSchedule : s)),
      }));
      return true;
    } catch (error: any) {
      console.error("Failed to resume schedule:", error);
      return false;
    }
  },

  triggerSchedule: async (id) => {
    try {
      await AppRequest.Post(`${BUDPIPELINE_API}/schedules/${id}/trigger`);
      return true;
    } catch (error: any) {
      console.error("Failed to trigger schedule:", error);
      return false;
    }
  },

  // ============================================================================
  // Webhook Actions
  // ============================================================================

  getWebhooks: async (workflowId?: string) => {
    set({ triggersLoading: true });
    try {
      const params = workflowId ? { workflow_id: workflowId } : {};
      const response = await AppRequest.Get(`${BUDPIPELINE_API}/webhooks`, { params });
      const webhooks = response.data || [];
      set({ webhooks, triggersLoading: false });
    } catch (error: any) {
      console.error("Failed to fetch webhooks:", error);
      set({ triggersLoading: false, webhooks: [] });
    }
  },

  createWebhook: async (data) => {
    set({ triggersLoading: true });
    try {
      const response = await AppRequest.Post(`${BUDPIPELINE_API}/webhooks`, data);
      const newWebhook = response.data;
      set((state) => ({
        webhooks: [...state.webhooks, newWebhook],
        triggersLoading: false,
      }));
      return newWebhook;
    } catch (error: any) {
      console.error("Failed to create webhook:", error);
      set({ triggersLoading: false });
      return null;
    }
  },

  deleteWebhook: async (id) => {
    try {
      await AppRequest.Delete(`${BUDPIPELINE_API}/webhooks/${id}`);
      set((state) => ({
        webhooks: state.webhooks.filter((w) => w.id !== id),
      }));
      return true;
    } catch (error: any) {
      console.error("Failed to delete webhook:", error);
      return false;
    }
  },

  rotateWebhookSecret: async (id) => {
    try {
      const response = await AppRequest.Post(`${BUDPIPELINE_API}/webhooks/${id}/rotate-secret`);
      return response.data?.secret || null;
    } catch (error: any) {
      console.error("Failed to rotate webhook secret:", error);
      return null;
    }
  },

  // ============================================================================
  // Event Trigger Actions
  // ============================================================================

  getEventTriggers: async (workflowId?: string) => {
    set({ triggersLoading: true });
    try {
      const params = workflowId ? { workflow_id: workflowId } : {};
      const response = await AppRequest.Get(`${BUDPIPELINE_API}/event-triggers`, { params });
      const eventTriggers = response.data || [];
      set({ eventTriggers, triggersLoading: false });
    } catch (error: any) {
      console.error("Failed to fetch event triggers:", error);
      set({ triggersLoading: false, eventTriggers: [] });
    }
  },

  createEventTrigger: async (data) => {
    set({ triggersLoading: true });
    try {
      const response = await AppRequest.Post(`${BUDPIPELINE_API}/event-triggers`, data);
      const newTrigger = response.data;
      set((state) => ({
        eventTriggers: [...state.eventTriggers, newTrigger],
        triggersLoading: false,
      }));
      return newTrigger;
    } catch (error: any) {
      console.error("Failed to create event trigger:", error);
      set({ triggersLoading: false });
      return null;
    }
  },

  deleteEventTrigger: async (id) => {
    try {
      await AppRequest.Delete(`${BUDPIPELINE_API}/event-triggers/${id}`);
      set((state) => ({
        eventTriggers: state.eventTriggers.filter((t) => t.id !== id),
      }));
      return true;
    } catch (error: any) {
      console.error("Failed to delete event trigger:", error);
      return false;
    }
  },
}));

/**
 * BudUseCases API Client
 *
 * This module provides API methods for interacting with the BudUseCases service
 * for template browsing, deployment creation, and deployment management.
 *
 * All requests go through budapp (which handles auth) via Dapr proxy to budusecases.
 */

import { AppRequest } from "@/pages/api/requests";

// All URLs are relative to budapp's base URL. budapp proxies to budusecases via Dapr.
const BUDUSECASES_BASE_URL = "/budusecases";

const UseCasesRequest = {
  Get: (url: string, config?: any) => AppRequest.Get(url, config),
  Post: (url: string, data?: any, config?: any) => AppRequest.Post(url, data, config),
  Put: (url: string, data?: any, config?: any) => AppRequest.Put(url, data, config),
  Delete: (url: string, config?: any) => AppRequest.Delete(url, config),
};

// ============================================================================
// Types
// ============================================================================

export type ComponentType = "model" | "llm" | "embedder" | "reranker" | "vector_db" | "memory_store" | "helm";

export interface HelmChartConfig {
  ref: string;
  version?: string;
  values?: Record<string, any>;
}

export interface TemplateComponent {
  id: string;
  name: string;
  display_name: string;
  description: string | null;
  component_type: ComponentType;
  required: boolean;
  default_component: string | null;
  compatible_components: string[];
  chart?: HelmChartConfig;
  sort_order: number;
}

export interface AccessUIConfig {
  enabled: boolean;
  port: number;
  path: string;
}

export interface ApiEndpointSpec {
  path: string;
  method: string;
  description: string;
  request_body?: Record<string, any>;
  response?: Record<string, any>;
}

export interface AccessAPIConfig {
  enabled: boolean;
  port: number;
  base_path: string;
  spec: ApiEndpointSpec[];
}

export interface AccessConfig {
  ui: AccessUIConfig;
  api: AccessAPIConfig;
}

export interface Template {
  id: string;
  name: string;
  display_name: string;
  version: string;
  description: string;
  category: string | null;
  tags: string[];
  parameters: Record<string, TemplateParameter>;
  resources: TemplateResources | null;
  deployment_order: string[];
  source: string;
  user_id: string | null;
  is_public: boolean;
  components: TemplateComponent[];
  access?: AccessConfig;
  created_at: string;
  updated_at: string;
}

export interface TemplateParameter {
  type: "integer" | "float" | "string" | "boolean";
  default: any;
  min?: number;
  max?: number;
  description: string;
}

export interface TemplateResources {
  minimum: ResourceSpec;
  recommended: ResourceSpec;
}

export interface ResourceSpec {
  cpu: number;
  memory: string;
  gpu?: number;
  gpu_memory?: string;
}

export interface TemplateListResponse {
  items: Template[];
  total: number;
  page: number;
  page_size: number;
}

export interface ComponentDeployment {
  id: string;
  component_name: string;
  component_type: ComponentType;
  selected_component: string | null;
  job_id: string | null;
  status: string;
  endpoint_url: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface Deployment {
  id: string;
  name: string;
  template_id: string | null;
  template_name: string | null;
  cluster_id: string;
  project_id: string | null;
  status: string;
  parameters: Record<string, any>;
  error_message: string | null;
  pipeline_execution_id?: string;
  components: ComponentDeployment[];
  access_config?: AccessConfig;
  access_urls?: { ui?: string; api?: string };
  workflow_id?: string;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface DeploymentListResponse {
  items: Deployment[];
  total: number;
  page: number;
  page_size: number;
}

export interface CreateDeploymentRequest {
  name: string;
  template_name: string;
  cluster_id: string;
  project_id?: string;
  components?: Record<string, string>;
  parameters?: Record<string, any>;
  metadata?: Record<string, any>;
}

export interface TemplateComponentInput {
  name: string;
  display_name: string;
  description?: string;
  type: ComponentType;
  required?: boolean;
  default_component?: string;
  compatible_components?: string[];
  chart?: HelmChartConfig;
}

export interface CreateTemplateRequest {
  name: string;
  display_name: string;
  version?: string;
  description: string;
  category?: string;
  tags?: string[];
  components: TemplateComponentInput[];
  parameters?: Record<string, TemplateParameter>;
  resources?: TemplateResources;
  deployment_order?: string[];
  is_public?: boolean;
}

export interface UpdateTemplateRequest {
  display_name?: string;
  version?: string;
  description?: string;
  category?: string;
  tags?: string[];
  components?: TemplateComponentInput[];
  parameters?: Record<string, TemplateParameter>;
  resources?: TemplateResources;
  deployment_order?: string[];
  is_public?: boolean;
}

export interface DeploymentStepProgress {
  id: string;
  execution_id: string;
  step_id: string;
  step_name: string;
  status: string;
  start_time: string | null;
  end_time: string | null;
  progress_percentage: string;
  outputs: Record<string, any> | null;
  error_message: string | null;
  sequence_number: number;
  awaiting_event: boolean;
  external_workflow_id?: string;
}

export interface DeploymentProgressEvent {
  id: string;
  execution_id: string;
  event_type: string;
  data: Record<string, any>;
  timestamp: string;
}

export interface AggregatedProgress {
  overall_progress: string;
  eta_seconds: number | null;
  completed_steps: number;
  total_steps: number;
  current_step: string | null;
}

export interface DeploymentProgressResponse {
  execution: {
    id: string;
    status: string;
    progress_percentage: string;
    [key: string]: any;
  };
  steps: DeploymentStepProgress[];
  recent_events: DeploymentProgressEvent[];
  aggregated_progress: AggregatedProgress;
}

// ============================================================================
// Template API Methods
// ============================================================================

export const TemplateAPI = {
  /**
   * List templates with optional filtering
   */
  list: async (params?: {
    page?: number;
    page_size?: number;
    category?: string;
    tag?: string;
    source?: string;
  }): Promise<TemplateListResponse> => {
    const response = await UseCasesRequest.Get(`${BUDUSECASES_BASE_URL}/templates`, { params });
    return response.data;
  },

  /**
   * Get a template by ID
   */
  get: async (templateId: string): Promise<Template> => {
    const response = await UseCasesRequest.Get(`${BUDUSECASES_BASE_URL}/templates/${templateId}`);
    return response.data;
  },

  /**
   * Get a template by name
   */
  getByName: async (name: string): Promise<Template> => {
    const response = await UseCasesRequest.Get(`${BUDUSECASES_BASE_URL}/templates/by-name/${name}`);
    return response.data;
  },

  /**
   * Create a custom template
   */
  create: async (request: CreateTemplateRequest): Promise<Template> => {
    const response = await UseCasesRequest.Post(`${BUDUSECASES_BASE_URL}/templates`, request);
    return response.data;
  },

  /**
   * Update a custom template
   */
  update: async (templateId: string, request: UpdateTemplateRequest): Promise<Template> => {
    const response = await UseCasesRequest.Put(`${BUDUSECASES_BASE_URL}/templates/${templateId}`, request);
    return response.data;
  },

  /**
   * Delete a custom template
   */
  delete: async (templateId: string): Promise<void> => {
    await UseCasesRequest.Delete(`${BUDUSECASES_BASE_URL}/templates/${templateId}`);
  },

  /**
   * Sync templates from YAML files (admin only)
   */
  sync: async (): Promise<{ created: number; updated: number; deleted: number; skipped: number }> => {
    const response = await UseCasesRequest.Post(`${BUDUSECASES_BASE_URL}/templates/sync`);
    return response.data;
  },
};

// ============================================================================
// Deployment API Methods
// ============================================================================

export const DeploymentAPI = {
  /**
   * List deployments with optional filtering
   */
  list: async (params?: {
    page?: number;
    page_size?: number;
    status?: string;
    cluster_id?: string;
    template_name?: string;
    project_id?: string;
  }): Promise<DeploymentListResponse> => {
    const response = await UseCasesRequest.Get(`${BUDUSECASES_BASE_URL}/deployments`, { params });
    return response.data;
  },

  /**
   * Get a deployment by ID
   */
  get: async (deploymentId: string): Promise<Deployment> => {
    const response = await UseCasesRequest.Get(`${BUDUSECASES_BASE_URL}/deployments/${deploymentId}`);
    return response.data;
  },

  /**
   * Create a new deployment
   */
  create: async (request: CreateDeploymentRequest): Promise<Deployment> => {
    const response = await UseCasesRequest.Post(`${BUDUSECASES_BASE_URL}/deployments`, request);
    return response.data;
  },

  /**
   * Start a deployment
   */
  start: async (deploymentId: string): Promise<{ id: string; status: string; message: string; workflow_id?: string }> => {
    const response = await UseCasesRequest.Post(`${BUDUSECASES_BASE_URL}/deployments/${deploymentId}/start`);
    return response.data;
  },

  /**
   * Stop a deployment
   */
  stop: async (deploymentId: string): Promise<{ id: string; status: string; message: string }> => {
    const response = await UseCasesRequest.Post(`${BUDUSECASES_BASE_URL}/deployments/${deploymentId}/stop`);
    return response.data;
  },

  /**
   * Delete a deployment
   */
  delete: async (deploymentId: string): Promise<void> => {
    await UseCasesRequest.Delete(`${BUDUSECASES_BASE_URL}/deployments/${deploymentId}`);
  },

  /**
   * Sync deployment status from BudCluster
   */
  sync: async (deploymentId: string): Promise<Deployment> => {
    const response = await UseCasesRequest.Post(`${BUDUSECASES_BASE_URL}/deployments/${deploymentId}/sync`);
    return response.data;
  },

  /**
   * Get deployment progress from pipeline execution
   */
  getDeploymentProgress: async (deploymentId: string): Promise<DeploymentProgressResponse> => {
    const response = await UseCasesRequest.Get(`${BUDUSECASES_BASE_URL}/deployments/${deploymentId}/progress`);
    return response.data;
  },

  /**
   * Retry gateway route creation for a deployment missing a gateway URL
   */
  retryGateway: async (deploymentId: string): Promise<Deployment> => {
    const response = await UseCasesRequest.Post(`${BUDUSECASES_BASE_URL}/deployments/${deploymentId}/retry-gateway`);
    return response.data;
  },
};

// Export combined API
export const BudUseCasesAPI = {
  templates: TemplateAPI,
  deployments: DeploymentAPI,
};

export default BudUseCasesAPI;

import { AgentVariable, AgentSettings } from '@/stores/useAgentStore';

/**
 * Schema for storing individual session data in workflow API's client_metadata
 */
export interface SessionMetadata {
  id: string;
  promptId: string;
  name: string;
  position: number;

  // Model/Deployment Selection
  modelId?: string;
  modelName?: string;
  selectedDeployment?: {
    id: string;
    name: string;
    model?: any;
  };

  // Prompts
  systemPrompt?: string;
  promptMessages?: string;

  // Variables (schema)
  inputVariables: AgentVariable[];
  outputVariables: AgentVariable[];

  // Settings
  settings?: {
    temperature?: number;
    maxTokens?: number;
    topP?: number;
    stream?: boolean;
  };
  llm_retry_limit?: number;

  // Schema flags
  allowMultipleCalls?: boolean;
  structuredInputEnabled?: boolean;
  structuredOutputEnabled?: boolean;

  // Model settings (full)
  modelSettings?: Partial<AgentSettings>;

  // Connector state (for OAuth resumption)
  connectorState?: {
    connectorId?: string;
    step?: 1 | 2;
  };

  // Workflow IDs for tracking async operations
  workflowId?: string;
  inputWorkflowId?: string;
  outputWorkflowId?: string;
  systemPromptWorkflowId?: string;
  promptMessagesWorkflowId?: string;
}

/**
 * Schema for the complete client_metadata stored in workflow API
 */
export interface WorkflowClientMetadata {
  sessions: SessionMetadata[];
  activeSessionIds: string[];
  selectedSessionId: string | null;
  lastUpdated: string; // ISO timestamp
  version: number; // Schema version for future migrations
}

/**
 * Current schema version - increment when breaking changes are made
 */
export const CLIENT_METADATA_VERSION = 1;

import { tempApiBaseUrl } from '@/components/environment';
import { AppRequest } from 'src/pages/api/requests';
import { AgentSession, AgentVariable, AgentSettings } from '@/stores/useAgentStore';
import {
  SessionMetadata,
  WorkflowClientMetadata,
  CLIENT_METADATA_VERSION,
} from '@/types/agentWorkflow';

/**
 * Service for managing workflow client_metadata for agent sessions
 */

/**
 * Convert an AgentSession from Zustand store to SessionMetadata for API
 */
export function sessionToMetadata(session: AgentSession): SessionMetadata {
  return {
    id: session.id,
    promptId: session.promptId || '',
    name: session.name,
    position: session.position || 0,

    // Model/Deployment
    modelId: session.modelId,
    modelName: session.modelName,
    selectedDeployment: session.selectedDeployment,

    // Prompts
    systemPrompt: session.systemPrompt,
    promptMessages: session.promptMessages,

    // Variables
    inputVariables: session.inputVariables || [],
    outputVariables: session.outputVariables || [],

    // Settings
    settings: session.settings,
    llm_retry_limit: session.llm_retry_limit,

    // Schema flags
    allowMultipleCalls: session.allowMultipleCalls,
    structuredInputEnabled: session.structuredInputEnabled,
    structuredOutputEnabled: session.structuredOutputEnabled,

    // Model settings (partial to avoid storing too much data)
    modelSettings: session.modelSettings ? {
      temperature: session.modelSettings.temperature,
      max_tokens: session.modelSettings.max_tokens,
      top_p: session.modelSettings.top_p,
      frequency_penalty: session.modelSettings.frequency_penalty,
      presence_penalty: session.modelSettings.presence_penalty,
      stop_sequences: session.modelSettings.stop_sequences,
      tool_choice: session.modelSettings.tool_choice,
    } : undefined,

    // Connector state
    connectorState: session.selectedConnectorId ? {
      connectorId: session.selectedConnectorId,
    } : undefined,

    // Workflow IDs
    workflowId: session.workflowId,
    inputWorkflowId: session.inputWorkflowId,
    outputWorkflowId: session.outputWorkflowId,
    systemPromptWorkflowId: session.systemPromptWorkflowId,
    promptMessagesWorkflowId: session.promptMessagesWorkflowId,
  };
}

/**
 * Convert SessionMetadata from API to partial AgentSession for Zustand store
 */
export function metadataToSession(metadata: SessionMetadata): Partial<AgentSession> {
  return {
    id: metadata.id,
    promptId: metadata.promptId,
    name: metadata.name,
    position: metadata.position,
    active: true,

    // Model/Deployment
    modelId: metadata.modelId,
    modelName: metadata.modelName,
    selectedDeployment: metadata.selectedDeployment,

    // Prompts
    systemPrompt: metadata.systemPrompt,
    promptMessages: metadata.promptMessages,

    // Variables
    inputVariables: metadata.inputVariables || [],
    outputVariables: metadata.outputVariables || [],

    // Settings
    settings: metadata.settings,
    llm_retry_limit: metadata.llm_retry_limit,

    // Schema flags
    allowMultipleCalls: metadata.allowMultipleCalls,
    structuredInputEnabled: metadata.structuredInputEnabled,
    structuredOutputEnabled: metadata.structuredOutputEnabled,

    // Model settings
    modelSettings: metadata.modelSettings as AgentSettings | undefined,

    // Connector state
    selectedConnectorId: metadata.connectorState?.connectorId,

    // Workflow IDs
    workflowId: metadata.workflowId,
    inputWorkflowId: metadata.inputWorkflowId,
    outputWorkflowId: metadata.outputWorkflowId,
    systemPromptWorkflowId: metadata.systemPromptWorkflowId,
    promptMessagesWorkflowId: metadata.promptMessagesWorkflowId,

    // Timestamps
    createdAt: new Date(),
    updatedAt: new Date(),
  };
}

/**
 * Convert Zustand store state to WorkflowClientMetadata for API
 */
export function sessionsToClientMetadata(
  sessions: AgentSession[],
  activeSessionIds: string[],
  selectedSessionId: string | null
): WorkflowClientMetadata {
  return {
    sessions: sessions.map(sessionToMetadata),
    activeSessionIds,
    selectedSessionId,
    lastUpdated: new Date().toISOString(),
    version: CLIENT_METADATA_VERSION,
  };
}

/**
 * Convert WorkflowClientMetadata from API to store-compatible format
 */
export function clientMetadataToSessions(metadata: WorkflowClientMetadata | null | undefined): {
  sessions: Partial<AgentSession>[];
  activeSessionIds: string[];
  selectedSessionId: string | null;
} | null {
  if (!metadata || !metadata.sessions || !Array.isArray(metadata.sessions)) {
    return null;
  }

  // Handle potential schema version migrations here
  if (metadata.version !== CLIENT_METADATA_VERSION) {
    console.warn(`Client metadata version mismatch. Expected ${CLIENT_METADATA_VERSION}, got ${metadata.version}`);
    // For now, proceed with parsing - add migration logic if needed
  }

  // Limit to max 3 sessions
  const limitedSessions = metadata.sessions.slice(0, 3);

  return {
    sessions: limitedSessions.map(metadataToSession),
    activeSessionIds: metadata.activeSessionIds?.slice(0, 3) || [],
    selectedSessionId: metadata.selectedSessionId,
  };
}

/**
 * Save agent metadata to workflow API (step 3)
 */
export async function saveAgentMetadata(
  workflowId: string,
  projectId: string,
  sessions: AgentSession[],
  activeSessionIds: string[],
  selectedSessionId: string | null
): Promise<boolean> {
  if (!workflowId) {
    console.error('[workflowMetadataService] No workflow ID provided');
    return false;
  }

  const clientMetadata = sessionsToClientMetadata(sessions, activeSessionIds, selectedSessionId);

  try {
    const response = await AppRequest.Post(
      `${tempApiBaseUrl}/prompts/prompt-workflow`,
      {
        workflow_id: workflowId,
        step_number: 3,
        trigger_workflow: false,
        client_metadata: clientMetadata,
      },
      {
        headers: {
          'x-resource-type': 'project',
          'x-entity-id': projectId,
        },
      }
    );

    if (response?.data) {
      console.log('[workflowMetadataService] Successfully saved agent metadata');
      return true;
    }

    return false;
  } catch (error) {
    console.error('[workflowMetadataService] Failed to save agent metadata:', error);
    return false;
  }
}

/**
 * Load agent metadata from workflow API
 */
export async function loadAgentMetadata(workflowId: string): Promise<{
  sessions: Partial<AgentSession>[];
  activeSessionIds: string[];
  selectedSessionId: string | null;
  projectId?: string;
} | null> {
  if (!workflowId) {
    console.error('[workflowMetadataService] No workflow ID provided');
    return null;
  }

  try {
    const response = await AppRequest.Get(`${tempApiBaseUrl}/workflows/${workflowId}`);

    if (response?.data) {
      const workflowData = response.data;
      const clientMetadata = workflowData.client_metadata as WorkflowClientMetadata | undefined;

      // Extract project ID from workflow_steps if available
      const projectId = workflowData.workflow_steps?.project?.id;

      if (clientMetadata) {
        const result = clientMetadataToSessions(clientMetadata);
        if (result) {
          return {
            ...result,
            projectId,
          };
        }
      }

      // Return null but include projectId for workflows without client_metadata
      return {
        sessions: [],
        activeSessionIds: [],
        selectedSessionId: null,
        projectId,
      };
    }

    return null;
  } catch (error) {
    console.error('[workflowMetadataService] Failed to load agent metadata:', error);
    return null;
  }
}

/**
 * Debounce helper for auto-save functionality
 */
export function createDebouncedSave(delay: number = 1000) {
  let timeoutId: NodeJS.Timeout | null = null;

  return (saveFn: () => Promise<void>) => {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }

    timeoutId = setTimeout(async () => {
      await saveFn();
      timeoutId = null;
    }, delay);
  };
}

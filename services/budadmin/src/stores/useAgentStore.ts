import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { infoToast } from "@/components/toast";
import { WorkflowClientMetadata } from "@/types/agentWorkflow";

export interface AgentVariable {
  id: string;
  name: string;
  value: string;
  type: "input" | "output";
  description?: string;
  dataType?: "string" | "number" | "boolean" | "array" | "object";
  defaultValue?: string;
  required?: boolean;
  validation?: string;
}

export interface AgentSettings {
  id: string;
  name: string;
  temperature: number;
  max_tokens: number;
  top_p: number;
  frequency_penalty: number;
  presence_penalty: number;
  stop_sequences: string[];
  seed: number;
  timeout: number;
  parallel_tool_calls: boolean;
  logprobs: boolean;
  logit_bias: Record<string, number>;
  extra_headers: Record<string, string>;
  max_completion_tokens: number;
  stream_options: Record<string, any>;
  response_format: Record<string, any>;
  tool_choice: string;
  chat_template: string;
  chat_template_kwargs: Record<string, any>;
  mm_processor_kwargs: Record<string, any>;
  created_at: string;
  modified_at: string;
  modifiedFields?: Set<string>; // Track which fields have been modified by user
}

export interface AgentSession {
  id: string;
  name: string;
  active: boolean;
  modelId?: string;
  modelName?: string;
  workflowId?: string; // Deprecated: kept for backward compatibility
  inputWorkflowId?: string;
  outputWorkflowId?: string;
  systemPromptWorkflowId?: string;
  promptMessagesWorkflowId?: string;
  promptId?: string;
  // TODO: selectedConnectorId is reserved for future use - will replace URL-based connector state management
  selectedConnectorId?: string; // Selected connector for this session's tools drawer
  selectedDeployment?: {
    id: string;
    name: string;
    model?: any;
  };
  systemPrompt?: string;
  promptMessages?: string;
  inputVariables: AgentVariable[];
  outputVariables: AgentVariable[];
  createdAt: Date;
  updatedAt: Date;
  position?: number;
  llm_retry_limit?: number;
  settings?: {
    temperature?: number;
    maxTokens?: number;
    topP?: number;
    stream?: boolean;
  };
  // Schema and settings flags (persisted across OAuth redirects)
  allowMultipleCalls?: boolean;
  structuredInputEnabled?: boolean;
  structuredOutputEnabled?: boolean;
  // Per-session model settings (isolated per agent box)
  modelSettings?: AgentSettings;
  promptConfigKey?: string;
}

interface AgentStore {
  // Sessions
  sessions: AgentSession[];
  activeSessionIds: string[];

  // Settings
  settingPresets: AgentSettings[];
  currentSettingPreset: AgentSettings | null;

  // UI State
  isAgentDrawerOpen: boolean;
  isTransitioningToAgentDrawer: boolean; // Flag to prevent race conditions with useDrawer
  selectedSessionId: string | null;
  isModelSelectorOpen: boolean;
  workflowContext: {
    isInWorkflow: boolean;
    nextStep: string | null;
  };

  // Edit Mode
  isEditMode: boolean;
  editingPromptId: string | null;

  // Add Version Mode
  isAddVersionMode: boolean;
  addVersionPromptId: string | null;

  // Edit Version Mode
  isEditVersionMode: boolean;
  editVersionData: {
    versionId: string;
    versionNumber: number;
    isDefault: boolean;
  } | null;

  // Deleted prompts tracking
  deletedPromptIds: Array<{sessionId: string; promptId: string}>;

  // Session Management
  createSession: () => string;
  updateSession: (id: string, updates: Partial<AgentSession>) => void;
  deleteSession: (id: string) => void;
  duplicateSession: (id: string) => void;

  // Variable Management
  addInputVariable: (sessionId: string) => void;
  addOutputVariable: (sessionId: string) => void;
  updateVariable: (sessionId: string, variableId: string, updates: Partial<AgentVariable>) => void;
  deleteVariable: (sessionId: string, variableId: string) => void;

  // Settings Management (Global Presets)
  addSettingPreset: (preset: AgentSettings) => void;
  updateSettingPreset: (preset: AgentSettings) => void;
  setCurrentSettingPreset: (preset: AgentSettings) => void;

  // Session-Specific Settings Management
  initializeSessionSettings: (sessionId: string, preset?: AgentSettings) => void;
  updateSessionSettings: (sessionId: string, updates: Partial<AgentSettings>) => void;
  getSessionSettings: (sessionId: string) => AgentSettings | undefined;

  // UI Actions
  openAgentDrawer: (workflowId?: string, nextStep?: string, skipSessionCreation?: boolean) => void;
  closeAgentDrawer: () => void;
  setSelectedSession: (id: string | null) => void;
  openModelSelector: () => void;
  closeModelSelector: () => void;

  // Edit Mode Actions
  setEditMode: (promptId: string) => void;
  clearEditMode: () => void;
  loadPromptForEdit: (promptId: string, sessionData: Partial<AgentSession>) => void;

  // Add Version Mode Actions
  setAddVersionMode: (promptId: string) => void;
  clearAddVersionMode: () => void;
  loadPromptForAddVersion: (promptId: string, sessionData: Partial<AgentSession>) => void;

  // Edit Version Mode Actions
  setEditVersionMode: (versionData: { versionId: string; versionNumber: number; isDefault: boolean }) => void;
  clearEditVersionMode: () => void;
  loadPromptForEditVersion: (promptId: string, versionData: { versionId: string; versionNumber: number; isDefault: boolean }, sessionData: Partial<AgentSession>) => void;

  // Bulk Actions
  clearAllSessions: () => void;
  resetSessionState: () => void;
  setActiveSessionIds: (ids: string[]) => void;

  // Prompt cleanup tracking
  addDeletedPromptId: (sessionId: string, promptId: string) => void;

  // OAuth Session Restoration
  restoreSessionWithPromptId: (promptId: string, sessionData?: Partial<AgentSession>) => string;
  getSessionByPromptId: (promptId: string) => AgentSession | undefined;

  // TODO: Connector Management (per-session) - reserved for future use to replace URL-based connector state
  setSessionConnectorId: (sessionId: string, connectorId: string | null) => void;
  getSessionConnectorId: (sessionId: string) => string | undefined;

  // Persistence Management
  clearPersistedSessions: () => void;

  // Workflow API Metadata Restoration
  restoreSessionsFromMetadata: (metadata: WorkflowClientMetadata) => void;

  // Auto-save trigger (used by AgentBox to signal changes)
  markSessionChanged: (sessionId: string) => void;
  getLastChangeTimestamp: () => number;
  lastChangeTimestamp: number;
}

const generateId = () => {
  return `agent_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`;
};

const generateVariableId = () => {
  return `var_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`;
};

const generatePromptId = () => {
  return `prompt_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`;
};

const createDefaultSession = (): AgentSession => ({
  id: generateId(),
  name: `Agent ${new Date().toLocaleTimeString()}`,
  active: true,
  promptId: generatePromptId(), // Generate promptId when session is created
  systemPrompt: "",
  promptMessages: "",  // Explicitly set as empty string
  inputVariables: [
    {
      id: generateVariableId(),
      name: "Input Variable 1",
      value: "",
      type: "input",
      description: "",
      dataType: "string",
      defaultValue: ""
    }
  ],
  outputVariables: [
    {
      id: generateVariableId(),
      name: "Output Variable 1",
      value: "",
      type: "output",
      description: "",
      dataType: "string",
      defaultValue: ""
    }
  ],
  createdAt: new Date(),
  updatedAt: new Date(),
  position: 0,
  llm_retry_limit: 3,
  settings: {
    temperature: 0.7,
    maxTokens: 2000,
    topP: 1.0
  }
});

const createDefaultModelSettings = (sessionId: string): AgentSettings => ({
  id: `settings_${sessionId}`,
  name: "Default",
  temperature: 0.7,
  max_tokens: 2000,
  top_p: 1.0,
  frequency_penalty: 0,
  presence_penalty: 0,
  stop_sequences: [],
  seed: 0,
  timeout: 0,
  parallel_tool_calls: true,
  logprobs: false,
  logit_bias: {},
  extra_headers: {},
  max_completion_tokens: 0,
  stream_options: {},
  response_format: {},
  tool_choice: "auto",
  chat_template: "",
  chat_template_kwargs: {},
  mm_processor_kwargs: {},
  created_at: new Date().toISOString(),
  modified_at: new Date().toISOString(),
  modifiedFields: new Set<string>(),
});

// Storage key for persisted agent sessions
const AGENT_STORE_KEY = 'agent-store-sessions';

export const useAgentStore = create<AgentStore>()(
  persist(
    (set, get) => ({
      // Initial State
      sessions: [],
      activeSessionIds: [],
      settingPresets: [],
      currentSettingPreset: null,
      isAgentDrawerOpen: false,
      isTransitioningToAgentDrawer: false,
      selectedSessionId: null,
      isModelSelectorOpen: false,
      workflowContext: {
        isInWorkflow: false,
        nextStep: null,
      },
      isEditMode: false,
      editingPromptId: null,
      isAddVersionMode: false,
      addVersionPromptId: null,
      isEditVersionMode: false,
      editVersionData: null,
      deletedPromptIds: [],
      lastChangeTimestamp: 0,

      // Session Management
      createSession: () => {
        const activeSessionIds = get().activeSessionIds;

        // Limit to maximum 3 active sessions
        if (activeSessionIds.length >= 3) {
          infoToast("Maximum of 3 agent boxes allowed");
          return activeSessionIds[activeSessionIds.length - 1];
        }

        const newSession = createDefaultSession();
        const currentSessions = get().sessions;
        newSession.position = currentSessions.length;

        set({
          sessions: [...currentSessions, newSession],
          activeSessionIds: [...activeSessionIds, newSession.id],
          selectedSessionId: newSession.id
        });

        return newSession.id;
      },

      updateSession: (id, updates) => {
        set({
          sessions: get().sessions.map(session =>
            session.id === id
              ? { ...session, ...updates, updatedAt: new Date() }
              : session
          )
        });
      },

      deleteSession: (id) => {
        const sessions = get().sessions.filter(s => s.id !== id);
        const activeSessionIds = get().activeSessionIds.filter(sid => sid !== id);

        // If no sessions remain, create a default one
        if (sessions.length === 0) {
          const newSession = createDefaultSession();
          set({
            sessions: [newSession],
            activeSessionIds: [newSession.id],
            selectedSessionId: newSession.id
          });
        } else {
          set({
            sessions,
            activeSessionIds,
            selectedSessionId: activeSessionIds.length > 0 ? activeSessionIds[0] : null
          });
        }
      },

      duplicateSession: (id) => {
        const sessionToDuplicate = get().sessions.find(s => s.id === id);
        if (!sessionToDuplicate) return;

        const newSession: AgentSession = {
          ...sessionToDuplicate,
          id: generateId(),
          name: `${sessionToDuplicate.name} (Copy)`,
          promptMessages: typeof sessionToDuplicate.promptMessages === 'string'
            ? sessionToDuplicate.promptMessages
            : "",  // Ensure promptMessages is always a string
          createdAt: new Date(),
          updatedAt: new Date(),
          position: get().sessions.length
        };

        set({
          sessions: [...get().sessions, newSession],
          activeSessionIds: [...get().activeSessionIds, newSession.id],
          selectedSessionId: newSession.id
        });
      },

      // Variable Management
      addInputVariable: (sessionId) => {
        const session = get().sessions.find(s => s.id === sessionId);
        if (!session) return;

        const newVariable: AgentVariable = {
          id: generateVariableId(),
          name: `Input Variable ${session.inputVariables.length + 1}`,
          value: "",
          type: "input",
          description: "",
          dataType: "string",
          defaultValue: ""
        };

        set({
          sessions: get().sessions.map(s =>
            s.id === sessionId
              ? {
                  ...s,
                  inputVariables: [...s.inputVariables, newVariable],
                  updatedAt: new Date()
                }
              : s
          )
        });
      },

      addOutputVariable: (sessionId) => {
        const session = get().sessions.find(s => s.id === sessionId);
        if (!session) return;

        const newVariable: AgentVariable = {
          id: generateVariableId(),
          name: `Output Variable ${session.outputVariables.length + 1}`,
          value: "",
          type: "output",
          description: "",
          dataType: "string",
          defaultValue: ""
        };

        set({
          sessions: get().sessions.map(s =>
            s.id === sessionId
              ? {
                  ...s,
                  outputVariables: [...s.outputVariables, newVariable],
                  updatedAt: new Date()
                }
              : s
          )
        });
      },

      updateVariable: (sessionId, variableId, updates) => {
        set({
          sessions: get().sessions.map(session => {
            if (session.id !== sessionId) return session;

            return {
              ...session,
              inputVariables: session.inputVariables.map(v =>
                v.id === variableId ? { ...v, ...updates } : v
              ),
              outputVariables: session.outputVariables.map(v =>
                v.id === variableId ? { ...v, ...updates } : v
              ),
              updatedAt: new Date()
            };
          })
        });
      },

      deleteVariable: (sessionId, variableId) => {
        set({
          sessions: get().sessions.map(session => {
            if (session.id !== sessionId) return session;

            return {
              ...session,
              inputVariables: session.inputVariables.filter(v => v.id !== variableId),
              outputVariables: session.outputVariables.filter(v => v.id !== variableId),
              updatedAt: new Date()
            };
          })
        });
      },

      // Settings Management
      addSettingPreset: (preset) => {
        set({
          settingPresets: [...get().settingPresets, preset]
        });
      },

      updateSettingPreset: (preset) => {
        set({
          settingPresets: get().settingPresets.map(p =>
            p.id === preset.id ? preset : p
          )
        });
      },

      setCurrentSettingPreset: (preset) => {
        set({ currentSettingPreset: preset });
      },

      // Session-Specific Settings Management
      initializeSessionSettings: (sessionId, preset) => {
        set((state) => {
          const sessionIndex = state.sessions.findIndex(s => s.id === sessionId);
          if (sessionIndex === -1) return state;

          const session = state.sessions[sessionIndex];
          // If session already has settings, don't reinitialize
          if (session.modelSettings) return state;

          const defaultSettings: AgentSettings = preset || createDefaultModelSettings(sessionId);

          const sessions = [...state.sessions];
          sessions[sessionIndex] = {
            ...session,
            modelSettings: defaultSettings,
            updatedAt: new Date(),
          };

          return { sessions };
        });
      },

      updateSessionSettings: (sessionId, updates) => {
        set((state) => {
          const sessionIndex = state.sessions.findIndex(s => s.id === sessionId);
          if (sessionIndex === -1) return state;

          const sessions = [...state.sessions];
          const session = { ...sessions[sessionIndex] };

          // Initialize settings if not present
          if (!session.modelSettings) {
            session.modelSettings = createDefaultModelSettings(sessionId);
          }

          const currentSettings = session.modelSettings;

          // Track which fields are being modified
          const modifiedFields = new Set<string>(currentSettings.modifiedFields || []);
          Object.keys(updates).forEach(key => {
            modifiedFields.add(key);
          });

          const updatedSettings: AgentSettings = {
            ...currentSettings,
            ...updates,
            modified_at: new Date().toISOString(),
            modifiedFields,
          };

          sessions[sessionIndex] = {
            ...session,
            modelSettings: updatedSettings,
            updatedAt: new Date(),
          };

          return { sessions };
        });
      },

      getSessionSettings: (sessionId) => {
        const session = get().sessions.find(s => s.id === sessionId);
        return session?.modelSettings;
      },

      // UI Actions
      openAgentDrawer: (workflowId?: string, nextStep?: string, skipSessionCreation?: boolean) => {
        // Set transition flag FIRST to prevent race conditions with useDrawer.closeDrawer
        set({ isTransitioningToAgentDrawer: true });

        const sessions = get().sessions;
        // Only create session if not skipped (e.g., when restoring from URL params)
        if (sessions.length === 0 && !skipSessionCreation) {
          const sessionId = get().createSession();
          // If workflow_id is provided, update the created session with it
          if (workflowId && sessionId) {
            get().updateSession(sessionId, { workflowId });
          }
        } else if (workflowId) {
          // Update the current active session with the workflow_id
          const activeSessionId = get().selectedSessionId || get().activeSessionIds[0];
          if (activeSessionId) {
            get().updateSession(activeSessionId, { workflowId });
          }
        }

        // Set workflow context if nextStep is provided
        if (nextStep) {
          set({
            isAgentDrawerOpen: true,
            isTransitioningToAgentDrawer: false, // Clear transition flag
            workflowContext: {
              isInWorkflow: true,
              nextStep: nextStep,
            }
          });
        } else {
          set({
            isAgentDrawerOpen: true,
            isTransitioningToAgentDrawer: false // Clear transition flag
          });
        }
      },

      closeAgentDrawer: () => {
        const { workflowContext } = get();
        const nextStep = workflowContext.nextStep;
        const isInWorkflow = workflowContext.isInWorkflow;

        // Base state to set when closing
        const baseState: Partial<AgentStore> = {
          isAgentDrawerOpen: false,
          isTransitioningToAgentDrawer: false, // Clear transition flag
          workflowContext: {
            isInWorkflow: false,
            nextStep: null,
          },
          isEditMode: false,
          editingPromptId: null,
          isAddVersionMode: false,
          addVersionPromptId: null,
          isEditVersionMode: false,
          editVersionData: null,
        };

        // Only clear session data if NOT in a workflow with a next step
        // (i.e., when user is explicitly closing the drawer without proceeding)
        if (!isInWorkflow || !nextStep) {
          baseState.sessions = [];
          baseState.activeSessionIds = [];
          baseState.selectedSessionId = null;
        }

        set(baseState);

        // If we're in a workflow and have a next step, trigger it after closing
        if (workflowContext.isInWorkflow && nextStep) {
          // Use setTimeout to ensure the drawer closes before opening the next step
          setTimeout(() => {
            // Import useDrawer dynamically to avoid circular dependencies
            import('../hooks/useDrawer').then(({ useDrawer }) => {
              const { openDrawerWithStep } = useDrawer.getState();
              openDrawerWithStep(nextStep);
            });
          }, 100);
        }
      },

      setSelectedSession: (id) => {
        set({ selectedSessionId: id });
      },

      openModelSelector: () => {
        set({ isModelSelectorOpen: true });
      },

      closeModelSelector: () => {
        set({ isModelSelectorOpen: false });
      },

      // Edit Mode Actions
      setEditMode: (promptId: string) => {
        set({
          isEditMode: true,
          editingPromptId: promptId
        });
      },

      clearEditMode: () => {
        set({
          isEditMode: false,
          editingPromptId: null
        });
      },

      loadPromptForEdit: (promptId: string, sessionData: Partial<AgentSession>) => {
        // Clear existing sessions and create a new one with the prompt data
        const newSession: AgentSession = {
          ...createDefaultSession(),
          ...sessionData,
          id: generateId(), // Generate new session ID
          promptId: promptId, // Ensure promptId is set
          updatedAt: new Date(),
        };

        set({
          sessions: [newSession],
          activeSessionIds: [newSession.id],
          selectedSessionId: newSession.id,
          isEditMode: true,
          editingPromptId: promptId
        });
      },

      // Bulk Actions
      clearAllSessions: () => {
        const newSession = createDefaultSession();
        set({
          sessions: [newSession],
          activeSessionIds: [newSession.id],
          selectedSessionId: newSession.id
        });
      },

      resetSessionState: () => {
        set({
          sessions: [],
          activeSessionIds: [],
          selectedSessionId: null,
        });
      },

      setActiveSessionIds: (ids) => {
        set({ activeSessionIds: ids });
      },

      // Prompt cleanup tracking
      addDeletedPromptId: (sessionId, promptId) => {
        set({
          deletedPromptIds: [...get().deletedPromptIds, { sessionId, promptId }]
        });
      },

      // Add Version Mode Actions
      setAddVersionMode: (promptId: string) => {
        set({
          isAddVersionMode: true,
          addVersionPromptId: promptId
        });
      },

      clearAddVersionMode: () => {
        set({
          isAddVersionMode: false,
          addVersionPromptId: null
        });
      },

      loadPromptForAddVersion: (promptId: string, sessionData: Partial<AgentSession>) => {
        // Clear existing sessions and create a new one with the prompt data
        const newSession: AgentSession = {
          ...createDefaultSession(),
          ...sessionData,
          id: generateId(), // Generate new session ID
          promptId: promptId, // Use the provided promptId for version creation
          updatedAt: new Date(),
        };

        set({
          sessions: [newSession],
          activeSessionIds: [newSession.id],
          selectedSessionId: newSession.id,
          isAddVersionMode: true,
          addVersionPromptId: promptId
        });
      },

      // Edit Version Mode Actions
      setEditVersionMode: (versionData: { versionId: string; versionNumber: number; isDefault: boolean }) => {
        set({
          isEditVersionMode: true,
          editVersionData: versionData
        });
      },

      clearEditVersionMode: () => {
        set({
          isEditVersionMode: false,
          editVersionData: null
        });
      },

      loadPromptForEditVersion: (promptId: string, versionData: { versionId: string; versionNumber: number; isDefault: boolean }, sessionData: Partial<AgentSession>) => {
        // Clear existing sessions and create a new one with the prompt data for editing
        const newSession: AgentSession = {
          ...createDefaultSession(),
          ...sessionData,
          id: generateId(), // Generate new session ID
          promptId: promptId, // Use the provided promptId
          updatedAt: new Date(),
        };

        set({
          sessions: [newSession],
          activeSessionIds: [newSession.id],
          selectedSessionId: newSession.id,
          isEditVersionMode: true,
          editVersionData: versionData
        });
      },

      // OAuth Session Restoration - creates or restores a session with a specific prompt ID
      restoreSessionWithPromptId: (promptId: string, sessionData?: Partial<AgentSession>) => {
        const existingSessions = get().sessions;
        const activeSessionIds = get().activeSessionIds;

        // Check if session with this prompt ID already exists
        const existingSession = existingSessions.find(s => s.promptId === promptId);
        if (existingSession) {
          // Ensure session ID is in activeSessionIds (might not be if restored from persistence)
          const newActiveSessionIds = activeSessionIds.includes(existingSession.id)
            ? activeSessionIds
            : [...activeSessionIds, existingSession.id];

          // Update existing session with new data if provided
          const updatedSessions = sessionData
            ? existingSessions.map(s =>
                s.id === existingSession.id
                  ? { ...s, ...sessionData, updatedAt: new Date() }
                  : s
              )
            : existingSessions;

          set({
            sessions: updatedSessions,
            activeSessionIds: newActiveSessionIds,
            selectedSessionId: existingSession.id
          });
          return existingSession.id;
        }

        // Limit to maximum 3 active sessions
        if (activeSessionIds.length >= 3) {
          infoToast("Maximum of 3 agent boxes allowed");
          return activeSessionIds[activeSessionIds.length - 1];
        }

        // Create new session with the specific prompt ID (not auto-generated)
        const newSession: AgentSession = {
          ...createDefaultSession(),
          ...sessionData,
          id: generateId(),
          promptId: promptId, // Use the provided promptId, NOT auto-generated
          position: existingSessions.length,
          updatedAt: new Date(),
        };

        set({
          sessions: [...existingSessions, newSession],
          activeSessionIds: [...activeSessionIds, newSession.id],
          selectedSessionId: newSession.id
        });

        return newSession.id;
      },

      // Get session by prompt ID
      getSessionByPromptId: (promptId: string) => {
        return get().sessions.find(s => s.promptId === promptId);
      },

      // Connector Management (per-session)
      setSessionConnectorId: (sessionId: string, connectorId: string | null) => {
        set({
          sessions: get().sessions.map(session =>
            session.id === sessionId
              ? { ...session, selectedConnectorId: connectorId || undefined, updatedAt: new Date() }
              : session
          )
        });
      },

      getSessionConnectorId: (sessionId: string) => {
        const session = get().sessions.find(s => s.id === sessionId);
        return session?.selectedConnectorId;
      },

      // Persistence Management - clears persisted session data
      clearPersistedSessions: () => {
        // Clear the persisted storage
        if (typeof window !== 'undefined') {
          localStorage.removeItem(AGENT_STORE_KEY);
        }
        // Reset session state in memory
        set({
          sessions: [],
          activeSessionIds: [],
          selectedSessionId: null,
        });
      },

      // Workflow API Metadata Restoration - restores sessions from API client_metadata
      restoreSessionsFromMetadata: (metadata: WorkflowClientMetadata) => {
        if (!metadata || !metadata.sessions || !Array.isArray(metadata.sessions)) {
          console.warn('[useAgentStore] Invalid metadata provided for restoration');
          return;
        }

        // Import conversion function dynamically to avoid circular dependency
        import('@/services/workflowMetadataService').then(({ clientMetadataToSessions }) => {
          const result = clientMetadataToSessions(metadata);
          if (!result) {
            console.warn('[useAgentStore] Failed to parse metadata');
            return;
          }

          // Limit to max 3 sessions
          const limitedSessions = result.sessions.slice(0, 3);
          const limitedActiveIds = result.activeSessionIds.slice(0, 3);

          // Convert partial sessions to full sessions with required fields
          const fullSessions: AgentSession[] = limitedSessions.map((partialSession, index) => ({
            id: partialSession.id || generateId(),
            name: partialSession.name || `Agent ${index + 1}`,
            active: true,
            promptId: partialSession.promptId,
            modelId: partialSession.modelId,
            modelName: partialSession.modelName,
            selectedDeployment: partialSession.selectedDeployment,
            systemPrompt: partialSession.systemPrompt || "",
            promptMessages: partialSession.promptMessages || "",
            inputVariables: partialSession.inputVariables || [],
            outputVariables: partialSession.outputVariables || [],
            createdAt: new Date(),
            updatedAt: new Date(),
            position: partialSession.position ?? index,
            llm_retry_limit: partialSession.llm_retry_limit ?? 3,
            settings: partialSession.settings || {
              temperature: 0.7,
              maxTokens: 2000,
              topP: 1.0,
            },
            allowMultipleCalls: partialSession.allowMultipleCalls,
            structuredInputEnabled: partialSession.structuredInputEnabled,
            structuredOutputEnabled: partialSession.structuredOutputEnabled,
            modelSettings: partialSession.modelSettings as AgentSettings | undefined,
            selectedConnectorId: partialSession.selectedConnectorId,
            workflowId: partialSession.workflowId,
            inputWorkflowId: partialSession.inputWorkflowId,
            outputWorkflowId: partialSession.outputWorkflowId,
            systemPromptWorkflowId: partialSession.systemPromptWorkflowId,
            promptMessagesWorkflowId: partialSession.promptMessagesWorkflowId,
          }));

          // Update store with restored sessions
          set({
            sessions: fullSessions,
            activeSessionIds: limitedActiveIds.length > 0 ? limitedActiveIds : fullSessions.map(s => s.id),
            selectedSessionId: result.selectedSessionId || (fullSessions.length > 0 ? fullSessions[0].id : null),
          });

          console.log('[useAgentStore] Successfully restored sessions from metadata:', fullSessions.length);
        });
      },

      // Mark a session as changed (triggers auto-save in AgentDrawer)
      markSessionChanged: (sessionId: string) => {
        set({ lastChangeTimestamp: Date.now() });
      },

      // Get the last change timestamp
      getLastChangeTimestamp: () => {
        return get().lastChangeTimestamp;
      }
    }),
    {
      name: AGENT_STORE_KEY,
      storage: createJSONStorage(() => localStorage),
      // Only persist session-related data, not UI state
      partialize: (state) => ({
        sessions: state.sessions,
        activeSessionIds: state.activeSessionIds,
        selectedSessionId: state.selectedSessionId,
      }),
      // Custom merge function to handle Date deserialization
      merge: (persistedState: any, currentState) => {
        if (persistedState?.sessions) {
          // Convert date strings back to Date objects
          persistedState.sessions = persistedState.sessions.map((session: any) => ({
            ...session,
            createdAt: session.createdAt ? new Date(session.createdAt) : new Date(),
            updatedAt: session.updatedAt ? new Date(session.updatedAt) : new Date(),
          }));
        }
        return {
          ...currentState,
          ...persistedState,
        };
      },
    }
  )
);

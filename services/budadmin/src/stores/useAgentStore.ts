import { create } from "zustand";
import { infoToast } from "@/components/toast";

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
  selectedSessionId: string | null;
  isModelSelectorOpen: boolean;
  workflowContext: {
    isInWorkflow: boolean;
    nextStep: string | null;
  };

  // Edit Mode
  isEditMode: boolean;
  editingPromptId: string | null;

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

  // Settings Management
  addSettingPreset: (preset: AgentSettings) => void;
  updateSettingPreset: (preset: AgentSettings) => void;
  setCurrentSettingPreset: (preset: AgentSettings) => void;

  // UI Actions
  openAgentDrawer: (workflowId?: string, nextStep?: string) => void;
  closeAgentDrawer: () => void;
  setSelectedSession: (id: string | null) => void;
  openModelSelector: () => void;
  closeModelSelector: () => void;

  // Edit Mode Actions
  setEditMode: (promptId: string) => void;
  clearEditMode: () => void;
  loadPromptForEdit: (promptId: string, sessionData: Partial<AgentSession>) => void;

  // Bulk Actions
  clearAllSessions: () => void;
  setActiveSessionIds: (ids: string[]) => void;

  // Prompt cleanup tracking
  addDeletedPromptId: (sessionId: string, promptId: string) => void;
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

export const useAgentStore = create<AgentStore>()((set, get) => ({
      // Initial State
      sessions: [],
      activeSessionIds: [],
      settingPresets: [],
      currentSettingPreset: null,
      isAgentDrawerOpen: false,
      selectedSessionId: null,
      isModelSelectorOpen: false,
      workflowContext: {
        isInWorkflow: false,
        nextStep: null,
      },
      isEditMode: false,
      editingPromptId: null,
      deletedPromptIds: [],

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

      // UI Actions
      openAgentDrawer: (workflowId?: string, nextStep?: string) => {
        const sessions = get().sessions;
        if (sessions.length === 0) {
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
            workflowContext: {
              isInWorkflow: true,
              nextStep: nextStep,
            }
          });
        } else {
          set({ isAgentDrawerOpen: true });
        }
      },

      closeAgentDrawer: () => {
        const { workflowContext } = get();
        const nextStep = workflowContext.nextStep;

        // Close the drawer first and clear edit mode
        set({
          isAgentDrawerOpen: false,
          workflowContext: {
            isInWorkflow: false,
            nextStep: null,
          },
          isEditMode: false,
          editingPromptId: null
        });

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

      setActiveSessionIds: (ids) => {
        set({ activeSessionIds: ids });
      },

      // Prompt cleanup tracking
      addDeletedPromptId: (sessionId, promptId) => {
        set({
          deletedPromptIds: [...get().deletedPromptIds, { sessionId, promptId }]
        });
      }
    }));

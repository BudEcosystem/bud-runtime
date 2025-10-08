import { create } from "zustand";
import { persist } from "zustand/middleware";

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

export interface AgentSession {
  id: string;
  name: string;
  active: boolean;
  modelId?: string;
  modelName?: string;
  workflowId?: string;
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
  settings?: {
    temperature?: number;
    maxTokens?: number;
    topP?: number;
  };
}

interface AgentStore {
  // Sessions
  sessions: AgentSession[];
  activeSessionIds: string[];

  // UI State
  isAgentDrawerOpen: boolean;
  selectedSessionId: string | null;
  isModelSelectorOpen: boolean;

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

  // UI Actions
  openAgentDrawer: (workflowId?: string) => void;
  closeAgentDrawer: () => void;
  setSelectedSession: (id: string | null) => void;
  openModelSelector: () => void;
  closeModelSelector: () => void;

  // Bulk Actions
  clearAllSessions: () => void;
  setActiveSessionIds: (ids: string[]) => void;
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
  settings: {
    temperature: 0.7,
    maxTokens: 2000,
    topP: 1.0
  }
});

export const useAgentStore = create<AgentStore>()(
  persist(
    (set, get) => ({
      // Initial State
      sessions: [],
      activeSessionIds: [],
      isAgentDrawerOpen: false,
      selectedSessionId: null,
      isModelSelectorOpen: false,

      // Session Management
      createSession: () => {
        const newSession = createDefaultSession();
        const currentSessions = get().sessions;
        newSession.position = currentSessions.length;

        set({
          sessions: [...currentSessions, newSession],
          activeSessionIds: [...get().activeSessionIds, newSession.id],
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

      // UI Actions
      openAgentDrawer: (workflowId?: string) => {
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
        set({ isAgentDrawerOpen: true });
      },

      closeAgentDrawer: () => {
        set({ isAgentDrawerOpen: false });
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
      }
    }),
    {
      name: "agent-store",
      version: 1, // Adding version to force migration
      partialize: (state) => ({
        sessions: state.sessions,
        activeSessionIds: state.activeSessionIds
      }),
      // Migration to fix promptMessages if it's an array and add default output variable
      migrate: (persistedState: any, _version: number) => {
        // Clean up any corrupted promptMessages data
        if (persistedState && persistedState.sessions) {
          persistedState.sessions = persistedState.sessions.map((session: any) => {
            const updatedSession = { ...session };

            // If promptMessages is an array or object, convert it to empty string
            if (typeof session.promptMessages !== 'string') {
              updatedSession.promptMessages = "";
              updatedSession.systemPrompt = session.systemPrompt || "";
            }

            // Add default output variable if none exist
            if (!updatedSession.outputVariables || updatedSession.outputVariables.length === 0) {
              updatedSession.outputVariables = [
                {
                  id: generateVariableId(),
                  name: "Output Variable 1",
                  value: "",
                  type: "output",
                  description: "",
                  dataType: "string",
                  defaultValue: ""
                }
              ];
            }

            return updatedSession;
          });
        }
        return persistedState;
      }
    }
  )
);

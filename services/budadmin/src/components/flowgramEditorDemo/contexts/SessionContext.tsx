import React, { createContext, useContext } from 'react';
import { AgentSession } from '@/stores/useAgentStore';
import { WorkflowStatus } from '@/hooks/usePromptSchemaWorkflow';

interface SessionContextType {
  session: AgentSession | null;
  onSavePromptSchema?: () => void;
  isSaving?: boolean;
  workflowStatus?: WorkflowStatus;
}

const SessionContext = createContext<SessionContextType>({
  session: null,
});

export const SessionProvider: React.FC<{
  session: AgentSession;
  children: React.ReactNode;
  onSavePromptSchema?: () => void;
  isSaving?: boolean;
  workflowStatus?: WorkflowStatus;
}> = ({ session, children, onSavePromptSchema, isSaving, workflowStatus }) => {
  return (
    <SessionContext.Provider value={{ session, onSavePromptSchema, isSaving, workflowStatus }}>
      {children}
    </SessionContext.Provider>
  );
};

export const useSession = () => {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error('useSession must be used within a SessionProvider');
  }
  return context;
};

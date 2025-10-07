import React, { createContext, useContext } from 'react';
import { AgentSession } from '@/stores/useAgentStore';
import { WorkflowStatus } from '@/hooks/usePromptSchemaWorkflow';

interface SessionContextType {
  session: AgentSession | null;
  onSavePromptSchema?: () => void;
  onSaveOutputSchema?: () => void;
  isSaving?: boolean;
  isSavingOutput?: boolean;
  workflowStatus?: WorkflowStatus;
  outputWorkflowStatus?: WorkflowStatus;
}

const SessionContext = createContext<SessionContextType>({
  session: null,
});

export const SessionProvider: React.FC<{
  session: AgentSession;
  children: React.ReactNode;
  onSavePromptSchema?: () => void;
  onSaveOutputSchema?: () => void;
  isSaving?: boolean;
  isSavingOutput?: boolean;
  workflowStatus?: WorkflowStatus;
  outputWorkflowStatus?: WorkflowStatus;
}> = ({ session, children, onSavePromptSchema, onSaveOutputSchema, isSaving, isSavingOutput, workflowStatus, outputWorkflowStatus }) => {
  return (
    <SessionContext.Provider value={{ session, onSavePromptSchema, onSaveOutputSchema, isSaving, isSavingOutput, workflowStatus, outputWorkflowStatus }}>
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

import React, { createContext, useContext } from 'react';
import { AgentSession } from '@/stores/useAgentStore';
import { WorkflowStatus } from '@/hooks/usePromptSchemaWorkflow';

interface SessionContextType {
  session: AgentSession | null;
  onSavePromptSchema?: () => void;
  onSaveOutputSchema?: () => void;
  onSaveSystemPrompt?: () => void;
  onSavePromptMessages?: () => void;
  onDeleteVariable?: (variableId: string) => void;
  onDeletePromptMessage?: (messageId: string) => void;
  isSaving?: boolean;
  isSavingOutput?: boolean;
  isSavingSystemPrompt?: boolean;
  isSavingPromptMessages?: boolean;
  workflowStatus?: WorkflowStatus;
  outputWorkflowStatus?: WorkflowStatus;
  systemPromptWorkflowStatus?: WorkflowStatus;
  promptMessagesWorkflowStatus?: WorkflowStatus;
  structuredInputEnabled?: boolean;
  structuredOutputEnabled?: boolean;
}

const SessionContext = createContext<SessionContextType>({
  session: null,
});

export const SessionProvider: React.FC<{
  session: AgentSession;
  children: React.ReactNode;
  onSavePromptSchema?: () => void;
  onSaveOutputSchema?: () => void;
  onSaveSystemPrompt?: () => void;
  onSavePromptMessages?: () => void;
  onDeleteVariable?: (variableId: string) => void;
  onDeletePromptMessage?: (messageId: string) => void;
  isSaving?: boolean;
  isSavingOutput?: boolean;
  isSavingSystemPrompt?: boolean;
  isSavingPromptMessages?: boolean;
  workflowStatus?: WorkflowStatus;
  outputWorkflowStatus?: WorkflowStatus;
  systemPromptWorkflowStatus?: WorkflowStatus;
  promptMessagesWorkflowStatus?: WorkflowStatus;
  structuredInputEnabled?: boolean;
  structuredOutputEnabled?: boolean;
}> = ({
  session,
  children,
  onSavePromptSchema,
  onSaveOutputSchema,
  onSaveSystemPrompt,
  onSavePromptMessages,
  onDeleteVariable,
  onDeletePromptMessage,
  isSaving,
  isSavingOutput,
  isSavingSystemPrompt,
  isSavingPromptMessages,
  workflowStatus,
  outputWorkflowStatus,
  systemPromptWorkflowStatus,
  promptMessagesWorkflowStatus,
  structuredInputEnabled,
  structuredOutputEnabled
}) => {
  return (
    <SessionContext.Provider value={{
      session,
      onSavePromptSchema,
      onSaveOutputSchema,
      onSaveSystemPrompt,
      onSavePromptMessages,
      onDeleteVariable,
      onDeletePromptMessage,
      isSaving,
      isSavingOutput,
      isSavingSystemPrompt,
      isSavingPromptMessages,
      workflowStatus,
      outputWorkflowStatus,
      systemPromptWorkflowStatus,
      promptMessagesWorkflowStatus,
      structuredInputEnabled,
      structuredOutputEnabled
    }}>
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

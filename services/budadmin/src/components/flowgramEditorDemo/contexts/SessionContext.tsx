import React, { createContext, useContext } from 'react';
import { AgentSession } from '@/stores/useAgentStore';

interface SessionContextType {
  session: AgentSession | null;
  onSavePromptSchema?: () => void;
  isSaving?: boolean;
}

const SessionContext = createContext<SessionContextType>({
  session: null,
});

export const SessionProvider: React.FC<{
  session: AgentSession;
  children: React.ReactNode;
  onSavePromptSchema?: () => void;
  isSaving?: boolean;
}> = ({ session, children, onSavePromptSchema, isSaving }) => {
  return (
    <SessionContext.Provider value={{ session, onSavePromptSchema, isSaving }}>
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

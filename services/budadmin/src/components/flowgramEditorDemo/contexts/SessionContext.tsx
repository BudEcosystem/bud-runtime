import React, { createContext, useContext } from 'react';
import { AgentSession } from '@/stores/useAgentStore';

interface SessionContextType {
  session: AgentSession | null;
}

const SessionContext = createContext<SessionContextType>({
  session: null,
});

export const SessionProvider: React.FC<{
  session: AgentSession;
  children: React.ReactNode;
}> = ({ session, children }) => {
  return (
    <SessionContext.Provider value={{ session }}>
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

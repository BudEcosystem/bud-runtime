'use client';

import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { parseConnectorParam } from '@/utils/urlUtils';

interface ToolsContextType {
  isOpen: boolean;
  openTools: () => void;
  closeTools: () => void;
  toggleTools: () => void;
}

interface ToolsProviderProps {
  children: React.ReactNode;
  promptId?: string; // Optional promptId for session-scoped behavior
  sessionIndex?: number; // Position of this session in active sessions array
}

const ToolsContext = createContext<ToolsContextType>({
  isOpen: false,
  openTools: () => {},
  closeTools: () => {},
  toggleTools: () => {},
});

export const ToolsProvider: React.FC<ToolsProviderProps> = ({ children, promptId, sessionIndex = 0 }) => {
  const searchParams = useSearchParams();
  const [isOpen, setIsOpen] = useState(false);

  // Auto-open sidebar if THIS session's connector is in URL (using positional index)
  useEffect(() => {
    const connectorParam = searchParams?.get('connector');
    if (connectorParam && sessionIndex >= 0) {
      // Parse positional array format: connectorId1,connectorId2,connectorId3
      const connectors = parseConnectorParam(connectorParam);
      // Check if there's a connector at this session's position
      const connectorId = connectors[sessionIndex];
      if (connectorId && connectorId.length > 0) {
        setIsOpen(true);
      }
    }
  }, [searchParams, sessionIndex]);

  const openTools = useCallback(() => {
    setIsOpen(true);
  }, []);

  const closeTools = useCallback(() => {
    setIsOpen(false);
  }, []);

  const toggleTools = useCallback(() => {
    setIsOpen(prev => !prev);
  }, []);

  return (
    <ToolsContext.Provider
      value={{
        isOpen,
        openTools,
        closeTools,
        toggleTools,
      }}
    >
      {children}
    </ToolsContext.Provider>
  );
};

export const useTools = () => {
  const context = useContext(ToolsContext);
  if (!context) {
    throw new Error('useTools must be used within a ToolsProvider');
  }
  return context;
};

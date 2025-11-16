'use client';

import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';

interface ToolsContextType {
  isOpen: boolean;
  openTools: () => void;
  closeTools: () => void;
  toggleTools: () => void;
}

const ToolsContext = createContext<ToolsContextType>({
  isOpen: false,
  openTools: () => {},
  closeTools: () => {},
  toggleTools: () => {},
});

export const ToolsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const searchParams = useSearchParams();
  const [isOpen, setIsOpen] = useState(false);

  // Auto-open sidebar if connector parameter is in URL
  useEffect(() => {
    const connectorId = searchParams?.get('connector');
    if (connectorId) {
      setIsOpen(true);
    }
  }, [searchParams]);

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

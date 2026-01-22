'use client';

import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { parseConnectorParam } from '@/utils/urlUtils';
import { isOAuthCallback, getOAuthState, clearOAuthState } from '@/hooks/useOAuthCallback';

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
  // CRITICAL: Only auto-open if this is an OAuth callback, NOT a manual page refresh
  useEffect(() => {
    const connectorParam = searchParams?.get('connector');
    if (!connectorParam || sessionIndex < 0) {
      return;
    }

    // Check if this is a valid OAuth callback:
    // 1. code/state params in URL (OAuth redirect just happened)
    // 2. authentication=true param in URL (set before OAuth redirect)
    const isOAuthReturn = isOAuthCallback();
    const hasAuthenticationParam = searchParams?.get('authentication') === 'true';
    const oauthState = getOAuthState();

    // Clear stale OAuth state if present but no valid OAuth indicators
    if (oauthState && !isOAuthReturn && !hasAuthenticationParam) {
      clearOAuthState();
    }

    // CRITICAL: Only auto-open if this is a valid OAuth callback
    // This prevents tools from auto-opening on manual page refresh
    const isValidOAuthCallback = isOAuthReturn || hasAuthenticationParam;

    if (!isValidOAuthCallback) {
      // Not an OAuth callback - don't auto-open tools sidebar
      return;
    }

    // Parse positional array format: connectorId1,connectorId2,connectorId3
    const connectors = parseConnectorParam(connectorParam);
    // Check if there's a connector at this session's position
    const connectorId = connectors[sessionIndex];
    if (connectorId && connectorId.length > 0) {
      setIsOpen(true);
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

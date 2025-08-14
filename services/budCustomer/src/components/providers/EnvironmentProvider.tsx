"use client";

import React, { createContext, useContext, ReactNode } from 'react';
import { EnvironmentConfig } from '@/lib/environment';

interface EnvironmentContextType {
  environment: EnvironmentConfig;
}

const EnvironmentContext = createContext<EnvironmentContextType | undefined>(undefined);

interface EnvironmentProviderProps {
  children: ReactNode;
  environment: EnvironmentConfig;
}

export function EnvironmentProvider({ children, environment }: EnvironmentProviderProps) {
  return (
    <EnvironmentContext.Provider value={{ environment }}>
      {children}
    </EnvironmentContext.Provider>
  );
}

export function useEnvironment() {
  const context = useContext(EnvironmentContext);
  if (context === undefined) {
    throw new Error('useEnvironment must be used within an EnvironmentProvider');
  }
  return context.environment;
}

// Hook for components that need specific environment variables
export function useApiConfig() {
  const environment = useEnvironment();
  return {
    baseUrl: environment.baseUrl,
    apiBaseUrl: environment.apiBaseUrl,
    tempApiBaseUrl: environment.tempApiBaseUrl,
  };
}

export function usePlaygroundConfig() {
  const environment = useEnvironment();
  return {
    playgroundUrl: environment.playgroundUrl,
    askBudUrl: environment.askBudUrl,
    askBudModel: environment.askBudModel,
  };
}

export function useNotificationConfig() {
  const environment = useEnvironment();
  return {
    novuBaseUrl: environment.novuBaseUrl,
    novuSocketUrl: environment.novuSocketUrl,
  };
}
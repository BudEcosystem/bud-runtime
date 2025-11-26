"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from 'react';

interface ConfigContextType {
  assetBaseUrl: string;
  isConfigLoaded: boolean;
  configError: string | null;
}

const DEFAULT_ASSET_BASE_URL = '/static/';

const ConfigContext = createContext<ConfigContextType>({
  assetBaseUrl: DEFAULT_ASSET_BASE_URL,
  isConfigLoaded: false,
  configError: null,
});

interface ConfigProviderProps {
  children: ReactNode;
}

export const ConfigProvider = ({ children }: ConfigProviderProps) => {
  const [assetBaseUrl, setAssetBaseUrl] = useState(DEFAULT_ASSET_BASE_URL);
  const [isConfigLoaded, setIsConfigLoaded] = useState(false);
  const [configError, setConfigError] = useState<string | null>(null);

  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const response = await fetch('/api/config');
        if (!response.ok) {
          throw new Error(`Config fetch failed with status: ${response.status}`);
        }
        const config = await response.json();
        if (config.assetBaseUrl) {
          setAssetBaseUrl(config.assetBaseUrl);
        }
        setConfigError(null);
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Unknown error';
        console.error('Failed to fetch config:', errorMessage);
        setConfigError(errorMessage);
        // Keep default values on error
      } finally {
        setIsConfigLoaded(true);
      }
    };

    fetchConfig();
  }, []);

  return (
    <ConfigContext.Provider value={{ assetBaseUrl, isConfigLoaded, configError }}>
      {children}
    </ConfigContext.Provider>
  );
};

export const useConfig = () => useContext(ConfigContext);

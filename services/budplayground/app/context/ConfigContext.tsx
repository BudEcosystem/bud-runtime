"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from 'react';

interface ConfigContextType {
  assetBaseUrl: string;
  isConfigLoaded: boolean;
}

const DEFAULT_ASSET_BASE_URL = '/static/';

const ConfigContext = createContext<ConfigContextType>({
  assetBaseUrl: DEFAULT_ASSET_BASE_URL,
  isConfigLoaded: false,
});

interface ConfigProviderProps {
  children: ReactNode;
}

export const ConfigProvider = ({ children }: ConfigProviderProps) => {
  const [assetBaseUrl, setAssetBaseUrl] = useState(DEFAULT_ASSET_BASE_URL);
  const [isConfigLoaded, setIsConfigLoaded] = useState(false);

  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const response = await fetch('/api/config');
        if (response.ok) {
          const config = await response.json();
          setAssetBaseUrl(config.assetBaseUrl || DEFAULT_ASSET_BASE_URL);
        }
      } catch (error) {
        console.error('Failed to fetch config:', error);
      } finally {
        setIsConfigLoaded(true);
      }
    };

    fetchConfig();
  }, []);

  return (
    <ConfigContext.Provider value={{ assetBaseUrl, isConfigLoaded }}>
      {children}
    </ConfigContext.Provider>
  );
};

export const useConfig = () => useContext(ConfigContext);

"use client";

import { ReactNode, createContext, useContext, useEffect, useState } from 'react';
import { useEndPoints } from '../components/bud/hooks/useEndPoint';

interface AuthContextType {
  apiKey: string | null;
  accessKey: string | null;
  isLoading: boolean;
  login: (key?: string, accessKey?: string) => Promise<boolean>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider = ({ children }: AuthProviderProps) => {
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [accessKey, setAccessKey] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const { getEndPoints } = useEndPoints();

  useEffect(() => {
    const storedKey = localStorage.getItem('token');
    const accessKey = localStorage.getItem('access_key');
    if (storedKey) {
      setApiKey(storedKey);
    }
    if(accessKey){
      setAccessKey(accessKey);
    }
    setIsLoading(false);
  }, []);

  const login = async (key?: string, accessKey?: string) => {
    localStorage.removeItem('token');
    localStorage.removeItem('access_key');
    const endpointResult = await getEndPoints({ page: 1, limit: 25, apiKey: key, accessKey: accessKey });

    if(Array.isArray(endpointResult)){
      if(key) setApiKey(key);
      if(accessKey) setAccessKey(accessKey);
      if(key) localStorage.setItem('token', key);
      if(accessKey) localStorage.setItem('access_key', accessKey);
      return true;
    }

    return false;
  };

  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('access_key');
    setApiKey(null);
    setAccessKey(null);
  };

  return (
    <AuthContext.Provider value={{ apiKey, accessKey, login, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

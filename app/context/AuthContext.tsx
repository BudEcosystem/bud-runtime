"use client";

import { ReactNode, createContext, useContext, useEffect, useState } from 'react';
import { useEndPoints } from '../components/bud/hooks/useEndPoint';

interface AuthContextType {
  apiKey: string | null;
  isLoading: boolean;
  login: (key: string) => Promise<boolean>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider = ({ children }: AuthProviderProps) => {
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const { getEndPoints } = useEndPoints();

  useEffect(() => {
    const storedKey = localStorage.getItem('token');
    if (storedKey) {
      setApiKey(storedKey);
    }
    setIsLoading(false);
  }, []);

  const login = async (key: string) => {
    localStorage.removeItem('token');
    const endpointResult = await getEndPoints({ page: 1, limit: 25, apiKey: key });
    if(Array.isArray(endpointResult)){
      setApiKey(key);
      localStorage.setItem('token', key);
      return true;
    }

    return false;
  };

  const logout = () => {
    localStorage.removeItem('token');
    setApiKey(null);
  };

  return (
    <AuthContext.Provider value={{ apiKey, login, logout, isLoading }}>
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

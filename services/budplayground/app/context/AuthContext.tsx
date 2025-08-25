"use client";

import { ReactNode, createContext, useContext, useEffect, useState, useRef } from 'react';
import { useEndPoints } from '../components/bud/hooks/useEndPoint';
import axios from 'axios';

interface AuthContextType {
  apiKey: string | null;
  accessKey: string | null;  // This can be either a regular access key or JWT token
  isLoading: boolean;
  login: (key?: string, accessKey?: string) => Promise<boolean>;
  logout: () => void;
  isJWTAuth: boolean;  // Indicates if accessKey is a JWT token
}

const AuthContext = createContext<AuthContextType | null>(null);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider = ({ children }: AuthProviderProps) => {
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [accessKey, setAccessKey] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isJWTAuth, setIsJWTAuth] = useState(false);
  const [isInitializing, setIsInitializing] = useState(false);
  const hasInitialized = useRef(false);

  const { getEndPoints } = useEndPoints();

  // Helper function to check if a string looks like a JWT
  const isJWT = (token: string): boolean => {
    if (!token) return false;
    const parts = token.split('.');
    return parts.length === 3;
  };

  // Initialize session with JWT
  const initializeWithJWT = async (jwt: string): Promise<boolean> => {
    // Prevent multiple simultaneous initialization attempts
    if (isInitializing) {
      console.log('JWT initialization already in progress, skipping...');
      return false;
    }

    setIsInitializing(true);

    try {
      console.log('Initializing JWT session...');
      // Call the initialization API
      const response = await axios.post('/api/initialize', { jwt_token: jwt });

      if (response.data && response.data.initialization_status === 'success') {
        // Store JWT as token (not access_key)
        setApiKey(jwt);
        setIsJWTAuth(true);
        localStorage.setItem('token', jwt);
        localStorage.setItem('is_jwt_auth', 'true');
        console.log('JWT session initialized successfully');
        return true;
      }
      console.error('JWT initialization failed: Invalid response');
      return false;
    } catch (error) {
      console.error('Failed to initialize JWT session:', error);
      // Don't store invalid JWT
      localStorage.removeItem('access_key');
      localStorage.removeItem('is_jwt_auth');
      return false;
    } finally {
      setIsInitializing(false);
    }
  };

  useEffect(() => {
    // Prevent multiple initializations (React StrictMode, HMR, etc.)
    if (hasInitialized.current) {
      return;
    }

    // Use a flag to prevent multiple executions
    let mounted = true;

    const initAuth = async () => {
      // Only proceed if component is still mounted and not already initialized
      if (!mounted || hasInitialized.current) return;

      // Mark as initialized immediately to prevent race conditions
      hasInitialized.current = true;

      // Check for access_key in query parameters
      const urlParams = new URLSearchParams(window.location.search);
      const accessKeyFromQuery = urlParams.get('access_key');

      if (accessKeyFromQuery) {
        // Check if it's a JWT token
        if (isJWT(accessKeyFromQuery)) {
          // Initialize with JWT
          const success = await initializeWithJWT(accessKeyFromQuery);

          // Always remove access_key from URL to prevent re-initialization
          const newUrl = new URL(window.location.href);
          newUrl.searchParams.delete('access_key');
          window.history.replaceState({}, '', newUrl.toString());

          if (!success) {
            // Clear any stored invalid JWT
            localStorage.removeItem('token');
            localStorage.removeItem('is_jwt_auth');
            setApiKey(null);
            setIsJWTAuth(false);
          }
        } else {
          // Regular access key
          setAccessKey(accessKeyFromQuery);
          setIsJWTAuth(false);
          localStorage.setItem('access_key', accessKeyFromQuery);
          localStorage.setItem('is_jwt_auth', 'false');

          // Remove from URL after processing
          const newUrl = new URL(window.location.href);
          newUrl.searchParams.delete('access_key');
          window.history.replaceState({}, '', newUrl.toString());
        }
        setIsLoading(false);
      } else {
        // Check for stored authentication
        const storedToken = localStorage.getItem('token');
        const storedAccessKey = localStorage.getItem('access_key');
        const storedIsJWT = localStorage.getItem('is_jwt_auth') === 'true';

        if (storedToken) {
          // Check if it's a JWT or API key
          if (storedIsJWT && isJWT(storedToken)) {
            // It's a JWT token
            setApiKey(storedToken);
            setIsJWTAuth(true);
          } else if (storedToken.startsWith('budserve_')) {
            // It's a regular API key
            setApiKey(storedToken);
            setIsJWTAuth(false);
          }
        }

        // Handle regular access key (not JWT)
        if (storedAccessKey && !isJWT(storedAccessKey)) {
          setAccessKey(storedAccessKey);
        }
        setIsLoading(false);
      }
    };

    initAuth();

    // Cleanup function
    return () => {
      mounted = false;
    };
  }, []); // Empty dependency array ensures this runs only once

  const login = async (key?: string, accessKeyParam?: string) => {
    // Clear all auth data
    localStorage.removeItem('token');
    localStorage.removeItem('access_key');
    localStorage.removeItem('is_jwt_auth');
    setApiKey(null);
    setAccessKey(null);
    setIsJWTAuth(false);

    // Check if accessKey is a JWT and initialize if needed
    if (accessKeyParam && isJWT(accessKeyParam)) {
      const success = await initializeWithJWT(accessKeyParam);
      if (success) {
        // For JWT auth, skip endpoint verification since JWT is already validated
        // and cached during initialization
        if(key) {
          setApiKey(key);
          localStorage.setItem('token', key);
        }
        return true;
      }
      return false;
    }

    // Regular login flow
    const endpointResult = await getEndPoints({
      page: 1,
      limit: 25,
      apiKey: key,
      accessKey: accessKeyParam
    });

    if(Array.isArray(endpointResult)){
      if(key) {
        setApiKey(key);
        localStorage.setItem('token', key);
      }
      if(accessKeyParam) {
        setAccessKey(accessKeyParam);
        localStorage.setItem('access_key', accessKeyParam);
        localStorage.setItem('is_jwt_auth', 'false');
      }
      return true;
    }

    return false;
  };

  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('access_key');
    localStorage.removeItem('is_jwt_auth');
    setApiKey(null);
    setAccessKey(null);
    setIsJWTAuth(false);
  };

  return (
    <AuthContext.Provider value={{
      apiKey,
      accessKey,
      login,
      logout,
      isLoading,
      isJWTAuth
    }}>
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

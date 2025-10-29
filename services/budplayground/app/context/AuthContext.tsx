"use client";

import { ReactNode, createContext, useContext, useEffect, useState, useRef, useCallback } from 'react';
import { useEndPoints } from '../components/bud/hooks/useEndPoint';
import { useUserSwitching } from '../hooks/useUserSwitching';
import { useChatStore } from '../store/chat';
import axios from 'axios';

interface AuthContextType {
  apiKey: string | null;
  accessKey: string | null;  // This can be either a regular access key or JWT token
  isLoading: boolean;
  login: (key?: string, accessKey?: string) => Promise<boolean>;
  logout: () => void;
  isJWTAuth: boolean;  // Indicates if accessKey is a JWT token
  accessToken: string | null;  // New access token from refresh token flow
  refreshToken: string | null;  // Refresh token for re-initialization
  isSessionValid: boolean;  // Indicates if the current session is valid
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

  // Enable automatic user switching based on authentication changes
  const { getCurrentUserIdentifier } = useUserSwitching();

  // New state for token refresh management
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState<string | null>(null);
  const [isSessionValid, setIsSessionValid] = useState(false);
  const [refreshTimeoutId, setRefreshTimeoutId] = useState<NodeJS.Timeout | null>(null);
  const [sessionData, setSessionData] = useState<any>(null);

  const { getEndPoints } = useEndPoints();

  // Helper function to check if a string looks like a JWT
  const isJWT = (token: string): boolean => {
    if (!token) return false;
    const parts = token.split('.');
    return parts.length === 3;
  };

  // Function to schedule automatic re-initialization
  const scheduleRefresh = useCallback((refreshTime: number) => {
    // Clear any existing timeout
    if (refreshTimeoutId) {
      clearTimeout(refreshTimeoutId);
    }

    const timeoutId = setTimeout(async () => {
      // Get fresh values from localStorage
      const storedRefreshToken = localStorage.getItem('refresh_token');

      // Use stored refresh token as primary source of truth
      if (storedRefreshToken) {
        try {
          // Call refresh directly instead of relying on refreshSession function
          const response = await axios.post('/api/initialize', { refresh_token: storedRefreshToken });

          if (response.data && response.data.initialization_status === 'success') {
            const newSessionData = response.data;

            // Update all state and storage
            setAccessToken(newSessionData.access_token);
            setRefreshToken(newSessionData.refresh_token);
            setSessionData(newSessionData);
            setIsSessionValid(true);
            setApiKey(newSessionData.access_token);

            localStorage.setItem('access_token', newSessionData.access_token);
            localStorage.setItem('refresh_token', newSessionData.refresh_token);
            localStorage.setItem('session_data', JSON.stringify(newSessionData));
            localStorage.setItem('token', newSessionData.access_token);

            // Schedule next refresh
            if (newSessionData.refresh_time) {
              scheduleRefresh(newSessionData.refresh_time);
            }
          } else {
            setIsSessionValid(false);
          }
        } catch (error) {
          setIsSessionValid(false);
        }
      }
    }, refreshTime);

    setRefreshTimeoutId(timeoutId);
  }, [refreshTimeoutId]);

  // Function to refresh the session using stored refresh token
  const refreshSession = useCallback(async (): Promise<boolean> => {
    if (!refreshToken) {
      setIsSessionValid(false);
      return false;
    }

    try {
      const response = await axios.post('/api/initialize', { refresh_token: refreshToken });

      if (response.data && response.data.initialization_status === 'success') {
        const newSessionData = response.data;

        // Update tokens
        setAccessToken(newSessionData.access_token);
        setRefreshToken(newSessionData.refresh_token);
        setSessionData(newSessionData);
        setIsSessionValid(true);

        // Update main API token for requests
        setApiKey(newSessionData.access_token);

        // Store updated tokens
        localStorage.setItem('access_token', newSessionData.access_token);
        localStorage.setItem('refresh_token', newSessionData.refresh_token);
        localStorage.setItem('session_data', JSON.stringify(newSessionData));
        localStorage.setItem('token', newSessionData.access_token);

        // Schedule next refresh
        if (newSessionData.refresh_time) {
          scheduleRefresh(newSessionData.refresh_time);
        }

        return true;
      }

      setIsSessionValid(false);
      return false;
    } catch (error) {
      setIsSessionValid(false);
      return false;
    }
  }, [refreshToken, scheduleRefresh]);

  // Initialize session with refresh token
  const initializeWithRefreshToken = useCallback(async (refreshTokenValue: string): Promise<boolean> => {
    // Prevent multiple simultaneous initialization attempts
    if (isInitializing) {
      return false;
    }

    setIsInitializing(true);

    try {
      // Call the initialization API with refresh token
      const response = await axios.post('/api/initialize', { refresh_token: refreshTokenValue });

      if (response.data && response.data.initialization_status === 'success') {
        const initData = response.data;

        // Store all token information
        setAccessToken(initData.access_token);
        setRefreshToken(initData.refresh_token);
        setSessionData(initData);
        setIsSessionValid(true);
        setIsJWTAuth(true);

        // Store in localStorage
        localStorage.setItem('access_token', initData.access_token);
        localStorage.setItem('refresh_token', initData.refresh_token);
        localStorage.setItem('session_data', JSON.stringify(initData));
        localStorage.setItem('is_jwt_auth', 'true');

        // Use access token as the main token for API requests
        setApiKey(initData.access_token);
        localStorage.setItem('token', initData.access_token);

        // Schedule automatic refresh based on TTL
        if (initData.refresh_time) {
          scheduleRefresh(initData.refresh_time);
        }
        return true;
      }
      return false;
    } catch (error) {
      // Clean up on failure
      setIsSessionValid(false);
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('session_data');
      localStorage.removeItem('is_jwt_auth');
      return false;
    } finally {
      setIsInitializing(false);
    }
  }, [isInitializing, scheduleRefresh]);

  // Legacy function - now redirects to refresh token flow
  const initializeWithJWT = async (jwt: string): Promise<boolean> => {
    // For backward compatibility, treat JWT as refresh token
    return await initializeWithRefreshToken(jwt);
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

      // Check for refresh_token or access_key in query parameters
      const urlParams = new URLSearchParams(window.location.search);
      const refreshTokenFromQuery = urlParams.get('refresh_token');
      const accessKeyFromQuery = urlParams.get('access_key');

      // Prioritize refresh_token over access_key for new flow
      const tokenFromQuery = refreshTokenFromQuery || accessKeyFromQuery;
      const paramToRemove = refreshTokenFromQuery ? 'refresh_token' : 'access_key';

      if (tokenFromQuery) {
        // Check if it's a JWT/refresh token
        if (isJWT(tokenFromQuery)) {
          // Initialize with refresh token
          const success = await initializeWithRefreshToken(tokenFromQuery);

          // Always remove token parameter from URL to prevent re-initialization
          const newUrl = new URL(window.location.href);
          newUrl.searchParams.delete(paramToRemove);
          window.history.replaceState({}, '', newUrl.toString());

          if (!success) {
            // Clear any stored invalid tokens
            localStorage.removeItem('token');
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            localStorage.removeItem('session_data');
            localStorage.removeItem('is_jwt_auth');
            setApiKey(null);
            setIsJWTAuth(false);
            setIsSessionValid(false);
          }
        } else {
          // Regular access key (legacy support)
          setAccessKey(tokenFromQuery);
          setIsJWTAuth(false);
          localStorage.setItem('access_key', tokenFromQuery);
          localStorage.setItem('is_jwt_auth', 'false');

          // Remove from URL after processing
          const newUrl = new URL(window.location.href);
          newUrl.searchParams.delete(paramToRemove);
          window.history.replaceState({}, '', newUrl.toString());
        }
        setIsLoading(false);
      } else {
        // Check for stored authentication
        const storedToken = localStorage.getItem('token');
        const storedAccessKey = localStorage.getItem('access_key');
        const storedIsJWT = localStorage.getItem('is_jwt_auth') === 'true';
        const storedAccessToken = localStorage.getItem('access_token');
        const storedRefreshToken = localStorage.getItem('refresh_token');
        const storedSessionData = localStorage.getItem('session_data');

        // Check if we have a complete token-based session
        if (storedAccessToken && storedRefreshToken && storedSessionData) {
          try {
            const sessionData = JSON.parse(storedSessionData);

            // Restore session state
            setAccessToken(storedAccessToken);
            setRefreshToken(storedRefreshToken);
            setSessionData(sessionData);
            setIsSessionValid(true);
            setIsJWTAuth(true);
            setApiKey(storedAccessToken); // Use access token for API calls

            // Check if session needs refresh based on stored TTL
            if (sessionData.initialized_at && sessionData.refresh_time) {
              const timeElapsed = Date.now() - sessionData.initialized_at;
              const remainingTime = sessionData.refresh_time - timeElapsed;

              if (remainingTime > 0) {
                // Schedule refresh for remaining time
                scheduleRefresh(remainingTime);
              } else {
                // Token should have been refreshed already, refresh now
                refreshSession();
              }
            }
          } catch (error) {
            // Clear corrupted session data
            localStorage.removeItem('session_data');
            setIsSessionValid(false);
          }
        } else if (storedToken) {
          // Legacy token handling
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
  }, [initializeWithRefreshToken, refreshSession, scheduleRefresh]);

  const login = async (key?: string, accessKeyParam?: string) => {
    // Clear all auth data
    if (refreshTimeoutId) {
      clearTimeout(refreshTimeoutId);
      setRefreshTimeoutId(null);
    }

    localStorage.removeItem('token');
    localStorage.removeItem('access_key');
    localStorage.removeItem('is_jwt_auth');
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('session_data');

    setApiKey(null);
    setAccessKey(null);
    setIsJWTAuth(false);
    setAccessToken(null);
    setRefreshToken(null);
    setIsSessionValid(false);
    setSessionData(null);

    // Check if accessKey is a JWT/refresh token and initialize if needed
    if (accessKeyParam && isJWT(accessKeyParam)) {
      const success = await initializeWithRefreshToken(accessKeyParam);
      if (success) {
        // For token-based auth, the initialization already set up everything
        if(key) {
          // If additional API key provided, store it but access token takes precedence
          localStorage.setItem('api_key', key);
        }
        return true;
      }
      return false;
    }

    // Regular login flow (for API keys)
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
    // Clear refresh timeout
    if (refreshTimeoutId) {
      clearTimeout(refreshTimeoutId);
      setRefreshTimeoutId(null);
    }

    // Clear all localStorage items
    localStorage.removeItem('token');
    localStorage.removeItem('access_key');
    localStorage.removeItem('is_jwt_auth');
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('session_data');
    localStorage.removeItem('api_key');

    // Clear chat store data when logging out
    const { switchUser } = useChatStore.getState();
    switchUser();

    // Reset all state
    setApiKey(null);
    setAccessKey(null);
    setIsJWTAuth(false);
    setAccessToken(null);
    setRefreshToken(null);
    setIsSessionValid(false);
    setSessionData(null);
  };

  return (
    <AuthContext.Provider value={{
      apiKey,
      accessKey,
      login,
      logout,
      isLoading,
      isJWTAuth,
      accessToken,
      refreshToken,
      isSessionValid
    }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuthContext = () => useContext(AuthContext);

export const useAuth = () => {
  const context = useAuthContext();
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

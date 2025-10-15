import { useEffect, useRef } from 'react';
import { useChatStore, reloadStoreForUser, initializeStore } from '../store/chat';

/**
 * Hook to detect user authentication changes and switch user data accordingly
 */
export const useUserSwitching = () => {
  const switchUser = useChatStore((state) => state.switchUser);
  const lastUserIdentifierRef = useRef<string | null>(null);

  const getUserIdentifier = (): string | null => {
    if (typeof window === 'undefined') return null;

    // For JWT/refresh token auth, get user_id from session data
    const isJWTAuth = localStorage.getItem('is_jwt_auth') === 'true';
    if (isJWTAuth) {
      const sessionData = localStorage.getItem('session_data');
      if (sessionData) {
        try {
          const parsed = JSON.parse(sessionData);
          return parsed.user_id;
        } catch (error) {
          console.error('Failed to parse session data:', error);
        }
      }
    }

    // For API key auth, use the API key itself as identifier
    const apiKey = localStorage.getItem('token') || localStorage.getItem('access_key');
    if (apiKey) {
      // Create a hash of the API key for privacy (simple approach)
      return btoa(apiKey).substring(0, 16); // Base64 encoded, first 16 chars
    }

    return null;
  };

  useEffect(() => {
    // Initialize store on first mount with correct user
    if (lastUserIdentifierRef.current === null) {
      const initialUser = getUserIdentifier();
      lastUserIdentifierRef.current = initialUser;
      initializeStore();
    }

    const checkUserChange = () => {
      const currentUserIdentifier = getUserIdentifier();

      // If user identifier has changed, switch user data
      if (lastUserIdentifierRef.current !== null &&
          lastUserIdentifierRef.current !== currentUserIdentifier) {

        // Reload store with new user's data
        reloadStoreForUser();
      }

      lastUserIdentifierRef.current = currentUserIdentifier;
    };

    // Check after initialization
    checkUserChange();

    // Set up interval to periodically check for auth changes
    const interval = setInterval(checkUserChange, 1000);

    // Listen for storage events from other tabs
    const handleStorageChange = (event: StorageEvent) => {
      if (event.key === 'session_data' ||
          event.key === 'token' ||
          event.key === 'access_key' ||
          event.key === 'is_jwt_auth') {
        setTimeout(checkUserChange, 100); // Small delay to ensure all storage updates are complete
      }
    };

    window.addEventListener('storage', handleStorageChange);

    return () => {
      clearInterval(interval);
      window.removeEventListener('storage', handleStorageChange);
    };
  }, [switchUser]);

  return {
    getCurrentUserIdentifier: getUserIdentifier,
  };
};

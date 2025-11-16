import { useEffect, useRef } from 'react';
import { useRouter } from 'next/router';

const OAUTH_STATE_KEY = 'oauth_connector_state';
const OAUTH_DRAWER_KEY = 'oauth_should_open_drawer';
const OAUTH_PROCESSED_KEY = 'oauth_callback_processed';

export interface OAuthState {
  promptId: string;
  connectorId: string;
  connectorName: string;
  workflowId?: string;
  step: 1 | 2;
  timestamp: number;
}

export const useOAuthCallback = (onOAuthCallback?: (state: OAuthState) => void) => {
  const router = useRouter();
  const hasProcessed = useRef(false);

  useEffect(() => {
    // Prevent multiple executions
    if (hasProcessed.current) return;

    // Check if we have OAuth callback params
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get('code');
    const state = urlParams.get('state');

    if (!code || !state) return;

    // Check if already processed (from sessionStorage)
    const alreadyProcessed = sessionStorage.getItem(OAUTH_PROCESSED_KEY);
    if (alreadyProcessed) {
      console.log('OAuth callback already processed in this session');
      return;
    }

    console.log('OAuth callback detected in page');

    // Get saved state from localStorage
    const savedStateStr = localStorage.getItem(OAUTH_STATE_KEY);

    if (savedStateStr) {
      try {
        const savedState: OAuthState = JSON.parse(savedStateStr);

        // Check if state is still valid (not older than 10 minutes)
        if (Date.now() - savedState.timestamp <= 10 * 60 * 1000) {
          console.log('Valid OAuth state found, triggering callback');

          // Mark as processed
          hasProcessed.current = true;
          sessionStorage.setItem(OAUTH_PROCESSED_KEY, 'true');

          // Set flag to open drawer
          // Note: AgentDrawer will handle URL updates with proper agent/prompt params
          localStorage.setItem(OAUTH_DRAWER_KEY, 'true');

          // Call the callback function if provided
          if (onOAuthCallback) {
            onOAuthCallback(savedState);
          }

          // Clear the processed flag after a delay to allow for page navigation
          setTimeout(() => {
            sessionStorage.removeItem(OAUTH_PROCESSED_KEY);
          }, 5000);
        } else {
          console.log('OAuth state expired');
          localStorage.removeItem(OAUTH_STATE_KEY);
        }
      } catch (error) {
        console.error('Failed to parse OAuth state:', error);
      }
    }
  }, [router.query.code, router.query.state]);
};

export const shouldOpenOAuthDrawer = (): boolean => {
  const shouldOpen = localStorage.getItem(OAUTH_DRAWER_KEY) === 'true';
  if (shouldOpen) {
    localStorage.removeItem(OAUTH_DRAWER_KEY);
  }
  return shouldOpen;
};

export const getOAuthState = (): OAuthState | null => {
  try {
    const saved = localStorage.getItem(OAUTH_STATE_KEY);
    if (!saved) return null;

    const state = JSON.parse(saved);
    // Check if state is not older than 10 minutes
    if (Date.now() - state.timestamp > 10 * 60 * 1000) {
      localStorage.removeItem(OAUTH_STATE_KEY);
      return null;
    }

    return state;
  } catch (error) {
    console.error('Failed to get OAuth state:', error);
    return null;
  }
};

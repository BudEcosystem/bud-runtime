import { useEffect, useRef } from 'react';
import { useRouter } from 'next/router';

const OAUTH_STATE_KEY = 'oauth_connector_state';
const OAUTH_DRAWER_KEY = 'oauth_should_open_drawer';
const OAUTH_PROCESSED_KEY = 'oauth_callback_processed';
const OAUTH_PROMPT_ID_KEY = 'oauth_original_prompt_id'; // Dedicated key for prompt ID preservation
const OAUTH_SESSION_DATA_KEY = 'oauth_session_data'; // Dedicated key for session data preservation

export interface OAuthSessionData {
  modelId?: string;
  modelName?: string;
  systemPrompt?: string;
  promptMessages?: string;
  name?: string;
  selectedDeployment?: {
    id: string;
    name: string;
    model?: any;
  };

  // Agent mode flags (to restore after OAuth)
  isEditMode?: boolean;
  editingPromptId?: string | null;
  isAddVersionMode?: boolean;
  addVersionPromptId?: string | null;
  isEditVersionMode?: boolean;
  editVersionData?: {
    versionId: string;
    versionNumber: number;
    isDefault: boolean;
  } | null;
}

export interface OAuthState {
  promptId: string;
  connectorId: string;
  connectorName: string;
  workflowId?: string;
  agentId?: string; // The agent/workflow ID from URL
  step: 1 | 2;
  timestamp: number;
  sessionData?: OAuthSessionData; // Session data to restore after OAuth
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

// Clear ALL OAuth state - use after session restoration is complete
export const clearOAuthState = (): void => {
  try {
    localStorage.removeItem(OAUTH_STATE_KEY);
    localStorage.removeItem(OAUTH_DRAWER_KEY);
    localStorage.removeItem(OAUTH_PROMPT_ID_KEY);
    localStorage.removeItem(OAUTH_SESSION_DATA_KEY);
    sessionStorage.removeItem(OAUTH_PROCESSED_KEY);
  } catch (error) {
    console.error('Failed to clear OAuth state:', error);
  }
};

// Clear only URL-related OAuth state - use after OAuth API callback completes
// This preserves session data (selectedDeployment, etc.) for restoration
export const clearOAuthUrlState = (): void => {
  try {
    // Only clear URL-related state, NOT session data
    localStorage.removeItem(OAUTH_STATE_KEY);
    localStorage.removeItem(OAUTH_DRAWER_KEY);
    sessionStorage.removeItem(OAUTH_PROCESSED_KEY);
    // NOTE: Do NOT clear OAUTH_PROMPT_ID_KEY or OAUTH_SESSION_DATA_KEY here
    // Those are needed for session restoration in agents/index.tsx
  } catch (error) {
    console.error('Failed to clear OAuth URL state:', error);
  }
};

export const isOAuthCallback = (): boolean => {
  if (typeof window === 'undefined') return false;
  const urlParams = new URLSearchParams(window.location.search);
  return !!(urlParams.get('code') && urlParams.get('state'));
};

// Save the original prompt ID before OAuth redirect
export const saveOAuthPromptId = (promptId: string): void => {
  try {
    localStorage.setItem(OAUTH_PROMPT_ID_KEY, promptId);
  } catch (error) {
    console.error('Failed to save OAuth prompt ID:', error);
  }
};

// Get the original prompt ID after OAuth redirect
export const getOAuthPromptId = (): string | null => {
  try {
    return localStorage.getItem(OAUTH_PROMPT_ID_KEY);
  } catch (error) {
    console.error('Failed to get OAuth prompt ID:', error);
    return null;
  }
};

// Check if we have a saved OAuth prompt ID (indicates OAuth in progress)
export const hasOAuthPromptId = (): boolean => {
  try {
    return !!localStorage.getItem(OAUTH_PROMPT_ID_KEY);
  } catch (error) {
    return false;
  }
};

// Save session data before OAuth redirect (for model selection restoration)
export const saveOAuthSessionData = (sessionData: OAuthSessionData): void => {
  try {
    localStorage.setItem(OAUTH_SESSION_DATA_KEY, JSON.stringify(sessionData));
  } catch (error) {
    console.error('Failed to save OAuth session data:', error);
  }
};

// Get session data after OAuth redirect
export const getOAuthSessionData = (): OAuthSessionData | null => {
  try {
    const data = localStorage.getItem(OAUTH_SESSION_DATA_KEY);
    return data ? JSON.parse(data) : null;
  } catch (error) {
    console.error('Failed to get OAuth session data:', error);
    return null;
  }
};

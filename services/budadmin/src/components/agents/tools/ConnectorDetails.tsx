'use client';

import React, { useState, useEffect } from 'react';
import { Checkbox, Spin } from 'antd';
import { useConnectors, Connector, CredentialSchemaField } from '@/stores/useConnectors';
import { Text_10_400_B3B3B3, Text_14_400_EEEEEE } from '@/components/ui/text';
import { successToast, errorToast } from '@/components/toast';
import { toast } from 'react-toastify';
import { ToolDetails } from './ToolDetails';
import { ConnectorService } from 'src/services/connectorService';
import { CredentialConfigStep } from './CredentialConfigStep';
import { ToolSelectionStep } from './ToolSelectionStep';
import { AgentSession, useAgentStore } from '@/stores/useAgentStore';
import { useAddAgent } from '@/stores/useAddAgent';
import { OAuthState, OAuthSessionData, clearOAuthState, saveOAuthPromptId, getOAuthPromptId, saveOAuthSessionData } from '@/hooks/useOAuthCallback';
import { updateConnectorInUrl } from '@/utils/urlUtils';
import { saveAgentMetadata } from '@/services/workflowMetadataService';
import { AppRequest } from "src/pages/api/requests";
import { tempApiBaseUrl } from "@/components/environment";

interface Tool {
  id: string;
  name: string;
  is_added?: boolean;
}

interface ConnectorDetailsProps {
  connector: Connector;
  onBack: (options?: { removeConnectorFromUrl?: boolean }) => void;
  promptId?: string;
  workflowId?: string;
  sessionIndex?: number; // Position of this session in active sessions array
  totalSessions?: number; // Total number of active sessions
}

/**
 * OAuth Flow:
 * 1. User fills connector credentials and clicks "Continue"
 * 2. Connector is registered via /prompts/{promptId}/connectors/{connectorId}/register
 * 3. If OAuth connector, initiate OAuth via /prompts/oauth/initiate
 * 4. Save current state to localStorage
 * 5. Redirect user to OAuth provider's authorization URL
 * 6. User authorizes on OAuth provider's site
 * 7. OAuth provider redirects back to /prompts&agents?code=...&state=...
 * 8. Page detects callback and opens AgentDrawer
 * 9. ConnectorDetails component detects callback params
 * 10. Complete OAuth via /prompts/oauth/callback with code and state
 * 11. Move to step 2 and fetch tools
 * 12. Clean up URL params and localStorage state
 */

// OAuth state management helpers
const OAUTH_STATE_KEY = 'oauth_connector_state';

const saveOAuthState = (state: OAuthState) => {
  try {
    localStorage.setItem(OAUTH_STATE_KEY, JSON.stringify(state));
  } catch (error) {
    // Silently fail - localStorage might not be available
  }
};

const getOAuthState = (): OAuthState | null => {
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
    return null;
  }
};

// Helper to identify redirect URI fields
const REDIRECT_URI_FIELDS = ['redirect_uri', 'redirect_url', 'callback_url'];
const isRedirectUriField = (fieldName: string) =>
  REDIRECT_URI_FIELDS.includes(fieldName.toLowerCase());

const buildDefaultModelSettings = (session: AgentSession) => ({
  temperature: session.settings?.temperature ?? 0.7,
  max_tokens: session.settings?.maxTokens ?? 2000,
  top_p: session.settings?.topP ?? 0.9,
  frequency_penalty: 0,
  presence_penalty: 0,
  stop_sequences: [],
  seed: 0,
  timeout: 0,
  parallel_tool_calls: true,
  logprobs: true,
  logit_bias: {},
  extra_headers: {},
  max_completion_tokens: 0,
  stream_options: {},
  response_format: {},
  tool_choice: "string",
  chat_template: "string",
  chat_template_kwargs: {},
  mm_processor_kwargs: {},
  guided_json: {},
  guided_regex: "string",
  guided_choice: [],
  guided_grammar: "string",
  structural_tag: "string",
  guided_decoding_backend: "string",
  guided_whitespace_pattern: "string"
});

const buildPromptConfigPayload = (session: AgentSession, promptId: string) => {
  let messages: Array<{ role: string; content: string }> = [];

  try {
    if (session.promptMessages && typeof session.promptMessages === 'string') {
      const parsed = JSON.parse(session.promptMessages);
      if (Array.isArray(parsed)) {
        messages = parsed;
      }
    }
  } catch (error) {
    messages = [];
  }

  const filteredMessages = messages
    .filter((msg) => msg.content?.trim())
    .map((msg) => ({ role: msg.role, content: msg.content }));

  const baseSettings = buildDefaultModelSettings(session);
  const sessionSettings = session.modelSettings || {};
  const mergedSettings: Record<string, any> = {
    ...baseSettings,
    ...sessionSettings,
  };

  delete mergedSettings.id;
  delete mergedSettings.name;
  delete mergedSettings.created_at;
  delete mergedSettings.modified_at;
  delete mergedSettings.modifiedFields;

  return {
    prompt_id: promptId,
    version: 1,
    set_default: false,
    deployment_name: session.selectedDeployment?.name,
    model_settings: mergedSettings,
    stream: session.settings?.stream ?? false,
    messages: filteredMessages,
    llm_retry_limit: session.llm_retry_limit ?? 0,
    enable_tools: true,
    allow_multiple_calls: session.allowMultipleCalls ?? true,
    system_prompt_role: "system",
    system_prompt: session.systemPrompt?.trim() || "",
    permanent: true,
  };
};

export const ConnectorDetails: React.FC<ConnectorDetailsProps> = ({
  connector,
  onBack,
  promptId,
  workflowId,
  sessionIndex = 0,
  totalSessions = 1,
}) => {
  const { fetchConnectorDetails, selectedConnectorDetails, isLoadingDetails } = useConnectors();
  const {
    getSessionByPromptId,
    sessions,
    activeSessionIds,
    selectedSessionId,
    isEditMode,
    isEditVersionMode,
  } = useAgentStore();
  const { currentWorkflow, selectedProject } = useAddAgent();

  // Determine initial step - check if this is an OAuth callback for this connector
  const getInitialStep = (): 1 | 2 => {
    if (connector.isFromConnectedSection) return 2;

    // Check if we're in an OAuth callback for this specific connector
    if (typeof window !== 'undefined') {
      const urlParams = new URLSearchParams(window.location.search);
      const code = urlParams.get('code');
      const state = urlParams.get('state');

      if (code && state) {
        // This is an OAuth callback - get saved state to verify it's for this connector
        const savedState = getOAuthState();
        if (savedState && savedState.connectorId === connector.id) {
          // OAuth callback for this connector - start at step 2 to prevent flicker
          return 2;
        }
      }
    }

    return 1;
  };

  const [step, setStep] = useState<1 | 2>(getInitialStep());
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [selectedTools, setSelectedTools] = useState<string[]>([]);
  const [selectAll, setSelectAll] = useState(false);
  const [isRegistering, setIsRegistering] = useState(false);
  const [availableTools, setAvailableTools] = useState<Tool[]>([]);
  const [isLoadingTools, setIsLoadingTools] = useState(false);
  const [isDisconnecting, setIsDisconnecting] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [viewMode, setViewMode] = useState<'connector' | 'tool'>('connector');
  const [selectedToolId, setSelectedToolId] = useState<string | null>(null);
  const [selectedToolName, setSelectedToolName] = useState<string | null>(null);
  const [headerHeight, setHeaderHeight] = useState<number>(0);
  const headerRef = React.useRef<HTMLDivElement>(null);
  const oauthCallbackProcessed = React.useRef(false);

  // Reusable function to fetch tools
  // isOAuthCallback: When true, always try fetchOAuthTools first (regardless of selectedConnectorDetails loading state)
  const fetchTools = React.useCallback(async (isOAuthCallback: boolean = false) => {
    // CRITICAL: Determine the correct prompt ID to use
    // Priority: 1. OAuth prompt ID (for OAuth callbacks), 2. Validated session prompt ID, 3. Prop prompt ID
    let effectivePromptId = getOAuthPromptId();

    if (!effectivePromptId && promptId) {
      // Verify the promptId exists in the store (session was properly restored)
      const session = getSessionByPromptId(promptId);
      if (session) {
        effectivePromptId = session.promptId;
      } else {
        // Fallback to prop promptId if session not found (shouldn't happen with persist)
        effectivePromptId = promptId;
      }
    }

    const promptIdForTools =
      (isEditMode || isEditVersionMode) && promptId
        ? getSessionByPromptId(promptId)?.name || effectivePromptId
        : effectivePromptId;

    if (!promptIdForTools) return;

    setIsLoadingTools(true);
    try {
      const authType = selectedConnectorDetails?.auth_type;

      let allTools: Tool[] = [];

      // CRITICAL FIX: If this is an OAuth callback, ALWAYS try fetchOAuthTools first
      // because selectedConnectorDetails might not be loaded yet when this is called
      // after OAuth redirect. We know it's an OAuth connector since we came from OAuth flow.
      const shouldFetchOAuthTools = isOAuthCallback || (authType && authType.toLowerCase() !== 'open');

      // If auth_type is "Open" or empty/undefined (and not OAuth callback), only call fetchTools
      // If auth_type is "OAuth" or any other value (or is OAuth callback), call fetchOAuthTools
      if (shouldFetchOAuthTools) {
        try {
          console.log('[ConnectorDetails] Calling fetchOAuthTools with:', {
            prompt_id: promptIdForTools,
            connector_id: connector.id,
            isOAuthCallback,
            authType
          });
          const oauthResponse = await ConnectorService.fetchOAuthTools({
            prompt_id: promptIdForTools,
            connector_id: connector.id,
            version: 1,
          });

          if (oauthResponse.data && oauthResponse.data.tools) {
            allTools = oauthResponse.data.tools;
            console.log('[ConnectorDetails] OAuth tools fetched:', allTools.length);
          }
        } catch (error) {
          // No user-facing toast, but log for developers
          console.error('[ConnectorDetails] Failed to fetch OAuth tools, proceeding with regular tools:', error);
        }

        // Also call GET /prompts/tools to get regular tools
        try {
          const regularResponse = await ConnectorService.fetchTools({
            prompt_id: promptIdForTools,
            connector_id: connector.id,
            page: 1,
            limit: 100,
          });

          if (regularResponse.data && regularResponse.data.tools) {
            // Merge tools from both responses (avoiding duplicates by ID)
            const regularTools = regularResponse.data.tools;
            const existingIds = new Set(allTools.map(t => t.id));

            regularTools.forEach((tool: Tool) => {
              if (!existingIds.has(tool.id)) {
                allTools.push(tool);
              }
            });
          }
        } catch (error) {
          // If regular fetch also fails, throw to show error toast
          throw error;
        }
      } else {
        // auth_type is "Open" or not set (and not OAuth callback), only call GET /prompts/tools
        const response = await ConnectorService.fetchTools({
          prompt_id: promptIdForTools,
          connector_id: connector.id,
          page: 1,
          limit: 100,
        });

        if (response.data && response.data.tools) {
          allTools = response.data.tools;
        }
      }

      // Set all collected tools
      setAvailableTools(allTools);

      // Auto-select tools that have is_added: true
      const addedToolIds = allTools
        .filter((tool) => tool.is_added === true)
        .map((tool) => tool.id)
        .filter(Boolean);

      if (addedToolIds.length > 0) {
        setSelectedTools(addedToolIds);
        // Check if all tools are added
        if (addedToolIds.length === allTools.length) {
          setSelectAll(true);
        }
      }
    } catch (error) {
      errorToast('Failed to fetch tools');
    } finally {
      setIsLoadingTools(false);
    }
  }, [promptId, connector.id, selectedConnectorDetails?.auth_type, getSessionByPromptId]);

  // Fetch connector details on mount (only if not already loaded)
  useEffect(() => {
    // Don't fetch if we already have the details for this connector
    if (selectedConnectorDetails && selectedConnectorDetails.id === connector.id) {
      return;
    }
    // Don't fetch if already loading
    if (isLoadingDetails) {
      return;
    }
    fetchConnectorDetails(connector.id);
  }, [connector.id, fetchConnectorDetails, isLoadingDetails, selectedConnectorDetails]);

  // Handle OAuth callback on mount
  useEffect(() => {
    const handleOAuthCallback = async () => {
      // Prevent multiple executions
      if (oauthCallbackProcessed.current) {
        return;
      }

      // Check if we're coming back from OAuth
      const urlParams = new URLSearchParams(window.location.search);
      const code = urlParams.get('code');
      const state = urlParams.get('state');

      if (!code || !state) return;

      // Get saved state
      const savedState = getOAuthState();

      if (!savedState) {
        return;
      }

      // Verify this callback is for the current connector
      if (savedState.connectorId !== connector.id) {
        return;
      }

      // Mark as processed
      oauthCallbackProcessed.current = true;

      // Helper function to clean up OAuth-specific URL params (preserves connector, agent and prompt params)
      const cleanupOAuthParams = () => {
        // Update connector URL FIRST using positional format (matches prompt IDs order)
        // This ensures the connector is properly mapped to the correct session position
        if (savedState.connectorId && savedState.sessionIndex !== undefined) {
          updateConnectorInUrl(savedState.sessionIndex, savedState.connectorId, savedState.totalSessions ?? 1);
        }

        // Now read the updated URL params (after updateConnectorInUrl has modified it)
        const cleanUrlParams = new URLSearchParams(window.location.search);
        cleanUrlParams.delete('code');
        cleanUrlParams.delete('state');
        cleanUrlParams.delete('authentication'); // Also remove authentication param after OAuth callback

        // Build URL manually to avoid encoding commas in connector param
        const cleanQueryParts: string[] = [];
        cleanUrlParams.forEach((value, key) => {
          if (key === 'connector' || key === 'agent' || key === 'prompt') {
            // Don't encode these params (they may contain commas)
            cleanQueryParts.push(`${key}=${value}`);
          } else {
            cleanQueryParts.push(`${key}=${encodeURIComponent(value)}`);
          }
        });
        const cleanUrl = cleanQueryParts.length > 0
          ? `${window.location.pathname}?${cleanQueryParts.join('&')}`
          : window.location.pathname;

        window.history.replaceState({}, document.title, cleanUrl);
      };

      // Complete the OAuth flow
      try {
        setIsRegistering(true);

        await ConnectorService.completeOAuthCallback(
          savedState.promptId,
          savedState.connectorId,
          code,
          state
        );

        // Move to step 2 to show tools
        setStep(2);

        // Fetch tools - pass true to indicate this is an OAuth callback
        // This ensures fetchOAuthTools is called even if selectedConnectorDetails isn't loaded yet
        await fetchTools(true);
      } catch (error: any) {
        errorToast(error?.response?.data?.message || 'Failed to complete OAuth authorization');
      } finally {
        // Clean up OAuth-specific URL params (always runs whether success or error)
        cleanupOAuthParams();

        // Clear saved state
        clearOAuthState();

        setIsRegistering(false);
      }
    };

    handleOAuthCallback();
  }, [connector.id, fetchTools]);

  // Fetch tools if coming from connected section
  useEffect(() => {
    if (connector.isFromConnectedSection && promptId) {
      fetchTools();
    }
  }, [connector.isFromConnectedSection, promptId, fetchTools]);

  // Measure header height
  useEffect(() => {
    if (headerRef.current) {
      const height = headerRef.current.offsetHeight;
      setHeaderHeight(height);
    }
  }, [selectedConnectorDetails?.url]); // Re-measure when connection URL changes (can affect height)

  // Auto-populate redirect URI with current browser URL when it becomes visible
  useEffect(() => {
    if (typeof window === 'undefined' || !selectedConnectorDetails?.credential_schema) return;

    const grantTypeValue = formData.grant_type;
    const visibleFields = selectedConnectorDetails.credential_schema.filter(field => {
      if (!field.visible_when || field.visible_when.length === 0) return true;
      return grantTypeValue && field.visible_when.includes(grantTypeValue);
    });
    const redirectField = visibleFields.find(f => isRedirectUriField(f.field));

    if (redirectField) {
      // Use full URL, but clean OAuth-specific params to avoid issues on re-authentication
      const url = new URL(window.location.href);
      url.searchParams.delete('code');
      url.searchParams.delete('state');
      const currentUrl = url.toString();
      setFormData(prev => {
        // Only set if not already populated
        if (!prev[redirectField.field]) {
          return { ...prev, [redirectField.field]: currentUrl };
        }
        return prev;
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedConnectorDetails?.credential_schema, formData.grant_type]);


  const handleSelectAll = (checked: boolean) => {
    setSelectAll(checked);
    if (checked) {
      // Only extract tool IDs (not names)
      const toolIds = availableTools
        .map(tool => typeof tool === 'string' ? tool : tool.id)
        .filter(Boolean); // Remove any undefined/null values
      setSelectedTools(toolIds);
    } else {
      setSelectedTools([]);
    }
  };

  const handleToolToggle = (tool: Tool, checked: boolean) => {
    const toolId = tool.id;
    if (!toolId) return; // Skip if no ID

    if (checked) {
      setSelectedTools([...selectedTools, toolId]);
    } else {
      setSelectedTools(selectedTools.filter(t => t !== toolId));
      setSelectAll(false);
    }
  };

  const handleToolClick = (tool: Tool) => {
    const toolId = tool.id;
    const toolName = tool.name;

    if (!toolId) return;

    setSelectedToolId(toolId);
    setSelectedToolName(toolName);
    setViewMode('tool');
  };

  const handleBackFromToolDetails = () => {
    setSelectedToolId(null);
    setSelectedToolName(null);
    setViewMode('connector');
  };

  // Helper function to filter visible fields based on grant_type selection
  const getVisibleFields = (fields: CredentialSchemaField[], grantTypeOverride?: string): CredentialSchemaField[] => {
    const grantTypeValue = grantTypeOverride !== undefined ? grantTypeOverride : formData['grant_type'];

    return fields.filter(field => {
      // If no visible_when, field is always visible
      if (!field.visible_when || field.visible_when.length === 0) {
        return true;
      }
      // If visible_when exists, check if current grant_type is in the array
      return grantTypeValue && field.visible_when.includes(grantTypeValue);
    });
  };

  const handleInputChange = (field: string, value: string) => {
    setFormData(prev => {
      const newFormData = { ...prev, [field]: value };

      // If grant_type changed, clear values of fields that are no longer visible
      if (field === 'grant_type' && selectedConnectorDetails?.credential_schema) {
        const visibleFields = getVisibleFields(selectedConnectorDetails.credential_schema, value);
        const visibleFieldNames = new Set(visibleFields.map(f => f.field));
        visibleFieldNames.add('grant_type'); // Ensure grant_type is always preserved

        return Object.keys(newFormData)
          .filter(key => visibleFieldNames.has(key))
          .reduce((obj, key) => {
            obj[key] = newFormData[key];
            return obj;
          }, {} as Record<string, string>);
      }

      return newFormData;
    });
  };

  const handleContinue = async () => {
    // Validate required fields before continuing
    const credentialSchema = selectedConnectorDetails?.credential_schema || [];
    const allRequiredFieldsFilled = credentialSchema
      .filter(field => field.required)
      .every(field => formData[field.field]);

    if (!allRequiredFieldsFilled) {
      errorToast('Please fill in all required fields');
      return;
    }

    if (!promptId) {
      errorToast('Prompt ID is missing');
      return;
    }

    const currentSession = promptId ? getSessionByPromptId(promptId) : undefined;

    setIsRegistering(true);

    try {
      // Format the credentials object based on the form data
      const credentials: Record<string, any> = {};

      for (const [key, value] of Object.entries(formData)) {
        // Convert comma-separated strings to arrays for specific fields
        if (key === 'passthrough_headers' || key === 'scopes') {
          if (value) {
            credentials[key] = value.split(',').map(item => item.trim()).filter(Boolean);
          }
        } else {
          credentials[key] = value;
        }
      }

      const payload = {
        credentials,
        version: 1
      };

      // Step 1: Register the connector first
      const promptIdForRegister =
        (isEditMode || isEditVersionMode) && currentSession?.name
          ? currentSession.name
          : promptId;
      if (!promptIdForRegister) {
        errorToast('Prompt ID is missing');
        return;
      }
      const response = await ConnectorService.registerConnector(promptIdForRegister, connector.id, payload);

      if (response.status === 200 || response.status === 201) {
        // Step 2: Check if OAuth authentication is required
        const authType = selectedConnectorDetails?.auth_type;

        if (authType?.toLowerCase() === 'oauth') {
          try {
            const oauthPromptId =
              (isEditMode || isEditVersionMode) && currentSession?.name
                ? currentSession.name
                : promptId;
            const oauthPayload = {
              prompt_id: oauthPromptId,
              connector_id: connector.id,
              workflow_id: workflowId,
              version: 1
            };

            const oauthResponse = await ConnectorService.initiateOAuth(oauthPayload);

            // Redirect to the authorization URL from the response
            const authorizationUrl = oauthResponse.data?.authorization_url;

            if (authorizationUrl) {
              // Get current session data to preserve model selection and other settings
              // Get agent ID from URL to preserve it across OAuth redirect
              const urlParams = new URLSearchParams(window.location.search);
              const agentId = urlParams.get('agent') || undefined;

              // Get agent store state to preserve edit/add version modes across OAuth
              const agentStoreState = useAgentStore.getState();

              // Build session data to restore after OAuth (includes agent mode flags and schema data)
              const sessionData: OAuthSessionData | undefined = currentSession ? {
                modelId: currentSession.modelId,
                modelName: currentSession.modelName,
                systemPrompt: currentSession.systemPrompt,
                promptMessages: currentSession.promptMessages,
                name: currentSession.name,
                selectedDeployment: currentSession.selectedDeployment,
                // Include agent mode flags for restoration after OAuth
                isEditMode: agentStoreState.isEditMode,
                editingPromptId: agentStoreState.editingPromptId,
                isAddVersionMode: agentStoreState.isAddVersionMode,
                addVersionPromptId: agentStoreState.addVersionPromptId,
                isEditVersionMode: agentStoreState.isEditVersionMode,
                editVersionData: agentStoreState.editVersionData,
                // Include schema variables for restoration after OAuth
                inputVariables: currentSession.inputVariables,
                outputVariables: currentSession.outputVariables,
                // Include session settings for restoration after OAuth
                llm_retry_limit: currentSession.llm_retry_limit,
                settings: currentSession.settings,
                // Include schema and settings flags for restoration after OAuth
                allowMultipleCalls: currentSession.allowMultipleCalls,
                structuredInputEnabled: currentSession.structuredInputEnabled,
                structuredOutputEnabled: currentSession.structuredOutputEnabled,
                // Include workflow context for add-agent flow continuation after OAuth
                workflowNextStep: agentStoreState.workflowContext?.nextStep,
              } : undefined;

              // CRITICAL: Save to workflow API's client_metadata before OAuth redirect
              // This reduces dependency on localStorage and enables API-based restoration
              const effectiveWorkflowId = workflowId || currentWorkflow?.workflow_id || agentId;
              const effectiveProjectId = selectedProject?.id || currentWorkflow?.workflow_steps?.project?.id;

              if (effectiveWorkflowId && effectiveProjectId) {
                try {
                  // Get active sessions to save
                  const sessionsToSave = sessions.filter(s => activeSessionIds.includes(s.id));

                  // Update the current session with connector state before saving
                  const updatedSessions = sessionsToSave.map(s => {
                    if (s.promptId === promptId) {
                      return {
                        ...s,
                        selectedConnectorId: connector.id,
                      };
                    }
                    return s;
                  });

                  await saveAgentMetadata(
                    effectiveWorkflowId,
                    effectiveProjectId,
                    updatedSessions,
                    activeSessionIds,
                    selectedSessionId
                  );
                  console.log('[ConnectorDetails] Saved metadata to API before OAuth redirect');
                } catch (apiError) {
                  // Log but don't block - localStorage backup will still work
                  console.warn('[ConnectorDetails] Failed to save to API, relying on localStorage:', apiError);
                }
              }

              // CRITICAL: Save prompt ID in dedicated localStorage key for reliable restoration
              if (promptId) {
                saveOAuthPromptId(promptId);
              }

              // CRITICAL: Save session data in dedicated localStorage key for model restoration
              if (sessionData) {
                saveOAuthSessionData(sessionData);
              }

              // Save state before redirecting (includes session data for restoration)
              saveOAuthState({
                promptId: promptId,
                connectorId: connector.id,
                connectorName: connector.name,
                workflowId: effectiveWorkflowId,
                agentId: agentId,
                step: 1,
                timestamp: Date.now(),
                sessionData: sessionData,
                sessionIndex: sessionIndex,
                totalSessions: totalSessions,
              });

              // CRITICAL: Add authentication=true param to URL before OAuth redirect
              // This marks the URL so ToolsHome knows to auto-open tools only after OAuth callback
              // Without this param, manual page refresh won't auto-open tools (correct behavior)
              updateConnectorInUrl(sessionIndex, connector.id, totalSessions);

              // Add authentication param without URL-encoding (to preserve comma-separated connector values)
              // Don't use new URL().toString() as it URL-encodes special characters like commas
              const authUrlParams = new URLSearchParams(window.location.search);
              authUrlParams.set('authentication', 'true');
              // Build URL manually to avoid encoding commas in connector param
              const queryParts: string[] = [];
              authUrlParams.forEach((value, key) => {
                if (key === 'connector' || key === 'agent' || key === 'prompt') {
                  // Don't encode these params (they may contain commas)
                  queryParts.push(`${key}=${value}`);
                } else {
                  queryParts.push(`${key}=${encodeURIComponent(value)}`);
                }
              });
              const authNewUrl = queryParts.length > 0
                ? `${window.location.pathname}?${queryParts.join('&')}`
                : window.location.pathname;
              window.history.replaceState({}, '', authNewUrl);

              // Redirect to OAuth provider
              window.location.href = authorizationUrl;
            } else {
              errorToast('OAuth authorization URL not found');
            }

            return;
          } catch (oauthError: any) {
            errorToast(oauthError?.response?.data?.message || 'Failed to initiate OAuth');
            return;
          }
        } else {
          // For non-OAuth connectors, proceed normally to step 2
          setStep(2);

          // Fetch tools after successful registration
          await fetchTools();
        }
      }
    } catch (error: any) {
      errorToast(error?.response?.data?.message || 'Failed to register connector');
    } finally {
      setIsRegistering(false);
    }
  };

  const handleConnect = async () => {
    // Use saved OAuth prompt ID if available (for OAuth callback scenarios)
    const effectivePromptId = getOAuthPromptId() || promptId;
    const currentSession = effectivePromptId ? getSessionByPromptId(effectivePromptId) : undefined;
    const promptIdForConfig = (isEditMode || isEditVersionMode) && currentSession?.name
      ? currentSession.name
      : effectivePromptId;

    if (!effectivePromptId || !promptIdForConfig) {
      errorToast('Prompt ID is missing');
      return;
    }

    if (selectedTools.length === 0) {
      errorToast('Please select at least one tool');
      return;
    }

    if ((isEditMode || isEditVersionMode) && currentSession) {
      if (!currentSession.selectedDeployment?.name) {
        errorToast('Please select a deployment model first');
        return;
      }

      try {
        const payload = buildPromptConfigPayload(currentSession, promptIdForConfig);
        await AppRequest.Post(`${tempApiBaseUrl}/prompts/prompt-config`, payload);
      } catch (error: any) {
        errorToast(error?.response?.data?.message || 'Failed to sync prompt configuration');
        return;
      }
    }

    setIsConnecting(true);

    try {
      const payload = {
        prompt_id: promptIdForConfig,
        connector_id: connector.id,
        tool_ids: selectedTools,
        version: 1
      };

      const response = await ConnectorService.connectTools(payload);

      if (response.status === 200 || response.status === 201) {
        // Show toast at bottom-right for the sidebar context
        toast.success('Tools added successfully', {
          position: 'bottom-right',
          icon: () => (
            <img alt="" height="20" width="20" src="/icons/toast-icon.svg" />
          ),
          style: {
            background: '#479d5f1a !important',
            color: '#479d5f',
            border: '1px solid #479d5f',
          },
        });
        // Refresh tools list to show updated is_added status
        await fetchTools();
        // Go back to the tools list
        onBack({ removeConnectorFromUrl: false });
      }
    } catch (error: any) {
      errorToast(error?.response?.data?.message || 'Failed to connect tools');
    } finally {
      setIsConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    // Use saved OAuth prompt ID if available (for OAuth callback scenarios)
    const effectivePromptId = getOAuthPromptId() || promptId;
    const currentSession = effectivePromptId ? getSessionByPromptId(effectivePromptId) : undefined;
    const promptIdForDisconnect = (isEditMode || isEditVersionMode) && currentSession?.name
      ? currentSession.name
      : effectivePromptId;

    if (!effectivePromptId || !promptIdForDisconnect) {
      errorToast('Prompt ID is missing');
      return;
    }

    setIsDisconnecting(true);

    try {
      const response = await ConnectorService.disconnectConnector(promptIdForDisconnect, connector.id);

      if (response.status === 200 || response.status === 204) {
        successToast('Connector disconnected successfully');
        // Go back to ToolsHome and remove connector from URL
        onBack({ removeConnectorFromUrl: true });
      }
    } catch (error: any) {
      errorToast(error?.response?.data?.message || 'Failed to disconnect connector');
    } finally {
      setIsDisconnecting(false);
    }
  };

  const getToolIcon = () => {
    if (connector.icon) {
      return connector.icon;
    }
    return connector.name.charAt(0).toUpperCase();
  };

  const isStepOneValid = () => {
    if (!selectedConnectorDetails?.credential_schema) return false;

    // Only validate visible required fields
    const visibleFields = getVisibleFields(selectedConnectorDetails.credential_schema);

    return visibleFields
      .filter(field => field.required)
      .every(field => formData[field.field]);
  };

  // Render tool details view
  if (viewMode === 'tool' && selectedToolId) {
    return (
      <ToolDetails
        toolId={selectedToolId}
        toolName={selectedToolName || undefined}
        onBack={handleBackFromToolDetails}
      />
    );
  }

  if (isLoadingDetails) {
    return (
      <div className="flex flex-col h-full text-white items-center justify-center">
        <Spin size="large" />
      </div>
    );
  }

  const connectionUrl = selectedConnectorDetails?.url;

  return (
    <div className="flex flex-col h-full  text-white">
      {/* Header */}
      <div ref={headerRef} className="px-[1.125rem] py-[1.2rem] relative">
        <button
          onClick={() => onBack()}
          className="w-[1.125rem] h-[1.125rem] p-[.1rem] rounded-full flex items-center justify-center bg-[#18191B] hover:bg-[#1A1A1A] transition-colors absolute"
          style={{ transform: 'none' }}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="m15 18-6-6 6-6" />
          </svg>
        </button>
        <div className='flex flex-col justify-center items-center gap-2 mt-[.5rem]'>
          <div className='flex justify-center items-center gap-[.5rem]'>
            <div className="w-[1.5rem] h-[1.5rem] rounded-[0.25rem] bg-[#1F1F1F] flex items-center justify-center text-lg">
              {getToolIcon()}
            </div>
            <Text_14_400_EEEEEE className="">Connect to {connector.name}</Text_14_400_EEEEEE>
          </div>
          {/* Connection URL */}
          {connectionUrl && (
            <div className="mb-4">
              <a
                href={connectionUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="cursor-pointer hover:underline hover:decoration-[#EEEEEE]"
              >
                <Text_10_400_B3B3B3 className="">
                  {connectionUrl}
                </Text_10_400_B3B3B3>
              </a>
            </div>
          )}
        </div>
      </div>

      {/* Scrollable Content */}
      <div
        className="flex-1 overflow-y-auto py-2 pb-[0]"
        style={{ minHeight: headerHeight > 0 ? `calc(100% - ${headerHeight}px)` : 'auto' }}
      >
        {/* first step */}
        {step === 1 && (
          <CredentialConfigStep
            credentialSchema={selectedConnectorDetails?.credential_schema || []}
            formData={formData}
            onInputChange={handleInputChange}
            onContinue={handleContinue}
            isRegistering={isRegistering}
            isValid={isStepOneValid()}
          />
        )}

        {/* second step */}
        {step === 2 && (
          <ToolSelectionStep
            availableTools={availableTools}
            selectedTools={selectedTools}
            selectAll={selectAll}
            isLoadingTools={isLoadingTools}
            isConnecting={isConnecting}
            isDisconnecting={isDisconnecting}
            isFromConnectedSection={connector.isFromConnectedSection || false}
            onSelectAll={handleSelectAll}
            onToolToggle={handleToolToggle}
            onToolClick={handleToolClick}
            onConnect={handleConnect}
            onDisconnect={handleDisconnect}
          />
        )}

      </div>
    </div>
  );
};

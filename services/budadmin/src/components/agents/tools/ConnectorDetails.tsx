'use client';

import React, { useState, useEffect } from 'react';
import { Input, Checkbox, Spin } from 'antd';
import { useConnectors, Connector, CredentialSchemaField } from '@/stores/useConnectors';
import { Text_10_400_B3B3B3, Text_12_400_EEEEEE, Text_14_400_EEEEEE } from '@/components/ui/text';
import { PrimaryButton, SecondaryButton } from '@/components/ui/bud/form/Buttons';
import CustomSelect from 'src/flows/components/CustomSelect';
import { successToast, errorToast } from '@/components/toast';
import { toast } from 'react-toastify';
import { ToolDetails } from './ToolDetails';
import { ConnectorService } from 'src/services/connectorService';

interface Tool {
  id: string;
  name: string;
  is_added?: boolean;
}

interface ConnectorDetailsProps {
  connector: Connector;
  onBack: () => void;
  promptId?: string;
  workflowId?: string;
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

interface OAuthState {
  promptId: string;
  connectorId: string;
  connectorName: string;
  workflowId?: string;
  step: 1 | 2;
  timestamp: number;
}

const saveOAuthState = (state: OAuthState) => {
  try {
    localStorage.setItem(OAUTH_STATE_KEY, JSON.stringify(state));
  } catch (error) {
    console.error('Failed to save OAuth state:', error);
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
    console.error('Failed to get OAuth state:', error);
    return null;
  }
};

const clearOAuthState = () => {
  try {
    localStorage.removeItem(OAUTH_STATE_KEY);
  } catch (error) {
    console.error('Failed to clear OAuth state:', error);
  }
};

export const ConnectorDetails: React.FC<ConnectorDetailsProps> = ({
  connector,
  onBack,
  promptId,
  workflowId,
}) => {
  const { fetchConnectorDetails, selectedConnectorDetails, isLoadingDetails } = useConnectors();

  const [step, setStep] = useState<1 | 2>(connector.isFromConnectedSection ? 2 : 1);
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
  const fetchTools = React.useCallback(async () => {
    if (!promptId) return;

    setIsLoadingTools(true);
    try {
      const authType = selectedConnectorDetails?.auth_type;
      let response: any;

      // Use different endpoint based on auth type
      if (authType?.toLowerCase() === 'oauth') {
        response = await ConnectorService.fetchOAuthTools({
          prompt_id: promptId,
          connector_id: connector.id,
          version: 1,
        });
      } else {
        response = await ConnectorService.fetchTools({
          prompt_id: promptId,
          connector_id: connector.id,
          page: 1,
          limit: 100,
        });
      }

      if (response.data && response.data.tools) {
        const tools: Tool[] = response.data.tools;
        setAvailableTools(tools);

        // Auto-select tools that have is_added: true
        const addedToolIds = tools
          .filter((tool) => tool.is_added === true)
          .map((tool) => tool.id)
          .filter(Boolean);

        if (addedToolIds.length > 0) {
          setSelectedTools(addedToolIds);
          // Check if all tools are added
          if (addedToolIds.length === tools.length) {
            setSelectAll(true);
          }
        }
      }
    } catch (error) {
      console.error('Error fetching tools:', error);
      errorToast('Failed to fetch tools');
    } finally {
      setIsLoadingTools(false);
    }
  }, [promptId, connector.id, selectedConnectorDetails?.auth_type]);

  // Fetch connector details on mount
  useEffect(() => {
    fetchConnectorDetails(connector.id);
  }, [connector.id]);

  // Handle OAuth callback on mount
  useEffect(() => {
    const handleOAuthCallback = async () => {
      // Prevent multiple executions
      if (oauthCallbackProcessed.current) {
        console.log('OAuth callback already processed, skipping');
        return;
      }

      // Check if we're coming back from OAuth
      const urlParams = new URLSearchParams(window.location.search);
      const code = urlParams.get('code');
      const state = urlParams.get('state');

      if (!code || !state) return;

      console.log('OAuth callback detected with code and state');

      // Get saved state
      const savedState = getOAuthState();

      if (!savedState) {
        console.log('No saved OAuth state found');
        return;
      }

      console.log('Saved OAuth state:', savedState);

      // Verify this callback is for the current connector
      if (savedState.connectorId !== connector.id) {
        console.log('OAuth callback is for different connector, ignoring');
        return;
      }

      // Mark as processed
      oauthCallbackProcessed.current = true;

      // Complete the OAuth flow
      try {
        setIsRegistering(true);

        console.log('Completing OAuth callback...');
        const response = await ConnectorService.completeOAuthCallback(
          savedState.promptId,
          savedState.connectorId,
          code,
          state
        );

        console.log('OAuth callback response:', response.data);

        // Clean up URL params
        const cleanUrl = window.location.pathname;
        window.history.replaceState({}, document.title, cleanUrl);

        // Clear saved state
        clearOAuthState();

        // Move to step 2 to show tools
        setStep(2);

        // Fetch tools
        await fetchTools();

        successToast('OAuth authorization successful');
      } catch (error: any) {
        console.error('Error completing OAuth callback:', error);
        errorToast(error?.response?.data?.message || 'Failed to complete OAuth authorization');

        // Clean up URL params even on error
        const cleanUrl = window.location.pathname;
        window.history.replaceState({}, document.title, cleanUrl);

        clearOAuthState();
      } finally {
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

  // Check OAuth status when component loads and OAuth is detected
  useEffect(() => {
    const checkOAuthStatus = async () => {
      if (!promptId || !selectedConnectorDetails) return;

      const authType = selectedConnectorDetails?.auth_type;

      if (authType?.toLowerCase() === 'oauth') {
        console.log('OAuth connector detected on load, checking OAuth status...');

        try {
          const statusResponse = await ConnectorService.checkOAuthStatus(promptId, connector.id);
          console.log('OAuth status response:', statusResponse.data);

          // TODO: Handle OAuth status response
          // Possible statuses: pending, authorized, failed, etc.
        } catch (error: any) {
          console.error('Error checking OAuth status:', error);
          // Don't show error toast on load, just log it
        }
      }
    };

    checkOAuthStatus();
  }, [promptId, connector.id, selectedConnectorDetails]);

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

  const handleInputChange = (field: string, value: string) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
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

      console.log('Registering connector with payload:', payload);

      // Step 1: Register the connector first
      const response = await ConnectorService.registerConnector(promptId, connector.id, payload);

      console.log('Registration response status:', response.status);
      console.log('Registration response:', response.data);

      if (response.status === 200 || response.status === 201) {
        console.log('Registration successful');

        // Step 2: Check if OAuth authentication is required
        const authType = selectedConnectorDetails?.auth_type;
        console.log('Auth Type from connector details:', authType);
        console.log('Is OAuth?:', authType?.toLowerCase() === 'oauth');

        if (authType?.toLowerCase() === 'oauth') {
          console.log('OAuth connector detected, initiating OAuth flow...');

          try {
            const oauthPayload = {
              prompt_id: promptId,
              connector_id: connector.id,
              workflow_id: workflowId,
              version: 1
            };

            console.log('Calling OAuth initiate API with payload:', oauthPayload);

            const oauthResponse = await ConnectorService.initiateOAuth(oauthPayload);

            console.log('OAuth initiate response:', oauthResponse.data);

            // Redirect to the authorization URL from the response
            const authorizationUrl = oauthResponse.data?.authorization_url;

            if (authorizationUrl) {
              console.log('Redirecting to authorization URL:', authorizationUrl);

              // Save state before redirecting
              saveOAuthState({
                promptId: promptId,
                connectorId: connector.id,
                connectorName: connector.name,
                workflowId: workflowId,
                step: 1,
                timestamp: Date.now()
              });

              // Redirect to OAuth provider
              window.location.href = authorizationUrl;
            } else {
              console.error('No authorization_url in OAuth response');
              errorToast('OAuth authorization URL not found');
            }

            return;
          } catch (oauthError: any) {
            console.error('Error initiating OAuth:', oauthError);
            errorToast(oauthError?.response?.data?.message || 'Failed to initiate OAuth');
            return;
          }
        } else {
          console.log('Non-OAuth connector, proceeding to step 2');

          // For non-OAuth connectors, proceed normally to step 2
          setStep(2);

          // Fetch tools after successful registration
          await fetchTools();
        }
      }
    } catch (error: any) {
      console.error('Error registering connector:', error);
      errorToast(error?.response?.data?.message || 'Failed to register connector');
    } finally {
      setIsRegistering(false);
    }
  };

  const handleConnect = async () => {
    if (!promptId) {
      errorToast('Prompt ID is missing');
      return;
    }

    if (selectedTools.length === 0) {
      errorToast('Please select at least one tool');
      return;
    }

    setIsConnecting(true);

    try {
      const payload = {
        prompt_id: promptId,
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
      }
    } catch (error: any) {
      console.error('Error connecting tools:', error);
      errorToast(error?.response?.data?.message || 'Failed to connect tools');
    } finally {
      setIsConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    if (!promptId) {
      errorToast('Prompt ID is missing');
      return;
    }

    setIsDisconnecting(true);

    try {
      const response = await ConnectorService.disconnectConnector(promptId, connector.id);

      if (response.status === 200 || response.status === 204) {
        successToast('Connector disconnected successfully');
        // Go back to ToolsHome
        onBack();
      }
    } catch (error: any) {
      console.error('Error disconnecting connector:', error);
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

  const renderFormField = (field: CredentialSchemaField) => {
    const inputClassName = "!bg-[#1A1A1A] border-[#1F1F1F] hover:border-[#3A3A3A] focus:border-[#965CDE] text-[#EEEEEE] text-[0.6875rem] font-[400] placeholder:text-[#808080] rounded-[.5rem] h-[1.9375rem]";
    const inputStyle = {
      backgroundColor: '#1A1A1A',
      borderColor: '#2A2A2A',
      color: 'white',
    };

    switch (field.type) {
      case 'dropdown':
        return (
          <CustomSelect
            key={field.field}
            name={field.field}
            placeholder={field.label}
            value={formData[field.field]}
            onChange={(value) => handleInputChange(field.field, value)}
            selectOptions={field.options?.map(opt => ({ label: opt, value: opt }))}
            InputClasses="!h-[1.9375rem] min-h-[1.9375rem] !text-[0.6875rem] !py-[.45rem]"
          />
        );

      case 'password':
        return (
          <Input
            key={field.field}
            type="password"
            placeholder={field.label}
            value={formData[field.field] || ''}
            onChange={(e) => handleInputChange(field.field, e.target.value)}
            className={inputClassName}
            style={inputStyle}
          />
        );

      case 'url':
      case 'text':
      default:
        return (
          <Input
            key={field.field}
            placeholder={field.label}
            value={formData[field.field] || ''}
            onChange={(e) => handleInputChange(field.field, e.target.value)}
            className={inputClassName}
            style={inputStyle}
          />
        );
    }
  };

  const isStepOneValid = () => {
    if (!selectedConnectorDetails?.credential_schema) return false;

    return selectedConnectorDetails.credential_schema
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
          onClick={onBack}
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
          <div className='flex flex-col h-full justify-between'>
            {/* Dynamic Input Fields based on credential_schema */}
            <div className="space-y-3 mb-6 px-[1.125rem]">
              {selectedConnectorDetails?.credential_schema
                ?.sort((a, b) => a.order - b.order)
                .map(field => renderFormField(field))}
            </div>
            <div style={{
              marginTop: '18px',
              paddingTop: '18px',
              paddingBottom: '18px',
              borderRadius: '0 0 11px 11px',
              borderTop: '0.5px solid #1F1F1F',
              background: 'rgba(255, 255, 255, 0.03)',
              backdropFilter: 'blur(5px)'
            }} className='px-[1rem]'>
              <div className='flex justify-end items-center px-[1rem]'>
                <PrimaryButton
                  onClick={handleContinue}
                  loading={isRegistering}
                  disabled={isRegistering || !isStepOneValid()}
                  style={{
                    cursor: (isRegistering || !isStepOneValid()) ? 'not-allowed' : 'pointer',
                    transform: 'none'
                  }}
                  classNames="h-[1.375rem] rounded-[0.375rem] "
                  textClass="!text-[0.625rem] !font-[400]"
                >
                  {isRegistering ? 'Registering...' : 'Continue'}
                </PrimaryButton>
              </div>
            </div>
          </div>
        )}

        {/* second step */}
        {step === 2 && (
          <div className='flex flex-col h-full justify-between'>
            {isLoadingTools ? (
              <div className="flex justify-center items-center py-8">
                <Spin />
              </div>
            ) : (
              <>
                <div>
                  {/* Select All Tools */}
                  <div className="flex items-center gap-2 mb-4 px-[1.125rem]">
                    <Checkbox
                      checked={selectAll}
                      onChange={(e) => handleSelectAll(e.target.checked)}
                      className="AntCheckbox text-[#757575] w-[0.75rem] h-[0.75rem] text-[0.875rem]"
                    />
                    <Text_12_400_EEEEEE className="text-nowrap">Select all tools</Text_12_400_EEEEEE>
                  </div>

                  {/* Tools List */}
                  <div className="space-y-2 mb-1 mx-[.5rem] border-[.5px] border-[#1F1F1F] rounded-[.5rem] ">
                    {availableTools.length === 0 ? (
                      <div className="px-4 py-8 text-center text-[#808080]">
                        No tools available
                      </div>
                    ) : (
                      availableTools.map((tool) => {
                        const toolId = tool.id;
                        const toolName = tool.name;

                        if (!toolId) return null; // Skip if no ID

                        return (
                          <div
                            key={toolId}
                            onClick={() => handleToolClick(tool)}
                            className="flex items-center justify-between px-[0.625rem] py-[0.46875rem] rounded-lg hover:bg-[#1A1A1A] border-[.5px] border-[transparent] hover:border-[#2A2A2A] cursor-pointer"
                          >
                            <div className='flex items-center justify-start gap-[.5rem]'>
                              <Checkbox
                                checked={selectedTools.includes(toolId)}
                                onChange={(e) => {
                                  e.stopPropagation();
                                  handleToolToggle(tool, e.target.checked);
                                }}
                                onClick={(e) => e.stopPropagation()}
                                className="AntCheckbox text-[#757575] w-[0.75rem] h-[0.75rem] text-[0.875rem]"
                              />
                              <Text_12_400_EEEEEE className="text-white">{toolName}</Text_12_400_EEEEEE>
                            </div>
                            <button
                              className="cursor-pointer hover:opacity-70 transition-opacity"
                              style={{ transform: 'none' }}
                            >
                              <svg
                                xmlns="http://www.w3.org/2000/svg"
                                width="16"
                                height="16"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                className="text-[#808080]"
                              >
                                <polyline points="9 18 15 12 9 6" />
                              </svg>
                            </button>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              </>
            )}
            {/* Buttons - Only show on step 2 */}
            {step === 2 && (
              <div style={{
                marginTop: '18px',
                paddingTop: '18px',
                paddingBottom: '18px',
                borderRadius: '0 0 11px 11px',
                borderTop: '0.5px solid #1F1F1F',
                background: 'rgba(255, 255, 255, 0.03)',
                backdropFilter: 'blur(5px)'
              }} className='px-[1rem]'>
                {connector.isFromConnectedSection ? (
                  // Show Save and Disconnect buttons for connected tools
                  <div className='flex justify-between items-center'>
                    <SecondaryButton
                      onClick={handleConnect}
                      loading={isConnecting}
                      disabled={isConnecting || selectedTools.length === 0 || isDisconnecting}
                      style={{
                        cursor: (isConnecting || selectedTools.length === 0 || isDisconnecting) ? 'not-allowed' : 'pointer',
                        transform: 'none'
                      }}
                      classNames="h-[1.375rem] rounded-[0.375rem] min-w-[3rem] !transition-colors !tranform-none"
                      textClass="!text-[0.625rem] !font-[400] !transition-colors !tranform-none"
                    >
                      {isConnecting ? 'Saving...' : 'Save'}
                    </SecondaryButton>
                    <PrimaryButton
                      onClick={handleDisconnect}
                      loading={isDisconnecting}
                      disabled={isDisconnecting || isConnecting}
                      style={{
                        cursor: (isDisconnecting || isConnecting) ? 'not-allowed' : 'pointer',
                        transform: 'none'
                      }}
                      classNames="h-[1.375rem] rounded-[0.375rem] !border-[#361519] bg-[#952f2f26] group"
                      textClass="!text-[0.625rem] !font-[400] text-[#E82E2E] group-hover:text-[#EEEEEE]"
                    >
                      {isDisconnecting ? 'Disconnecting...' : 'Disconnect'}
                    </PrimaryButton>
                  </div>
                ) : (
                  // Show Connect button for unregistered tools
                  <div className='flex justify-end items-center'>
                    <PrimaryButton
                      onClick={handleConnect}
                      loading={isConnecting}
                      disabled={isConnecting || selectedTools.length === 0}
                      style={{
                        cursor: (isConnecting || selectedTools.length === 0) ? 'not-allowed' : 'pointer',
                        transform: 'none'
                      }}
                      classNames="h-[1.375rem] rounded-[0.375rem]"
                      textClass="!text-[0.625rem] !font-[400]"
                    >
                      {isConnecting ? 'Connecting...' : 'Connect'}
                    </PrimaryButton>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  );
};

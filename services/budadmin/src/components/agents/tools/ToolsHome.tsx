'use client';

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { Input, Spin, Empty } from 'antd';
import { useConnectors, Connector } from '@/stores/useConnectors';
import { useAgentStore } from '@/stores/useAgentStore';
import { Text_14_400_757575, Text_14_400_EEEEEE } from '@/components/ui/text';
import { ConnectorDetails } from './ConnectorDetails';
import { getOAuthState, isOAuthCallback, clearOAuthState, getOAuthPromptId } from '@/hooks/useOAuthCallback';
import { updateConnectorInUrl, getConnectorFromUrlByPosition } from '@/utils/urlUtils';

const EMPTY_CONNECTOR_LIST: Connector[] = [];
const EMPTY_CONNECTED_TOOL_LIST: Connector[] = [];

interface ToolsHomeProps {
  promptId?: string;
  workflowId?: string;
  sessionIndex?: number; // Position of this session in active sessions array
  totalSessions?: number; // Total number of active sessions
}

export const ToolsHome: React.FC<ToolsHomeProps> = ({ promptId: propPromptId, workflowId, sessionIndex = 0, totalSessions = 1 }) => {
  const getSessionByPromptId = useAgentStore((state) => state.getSessionByPromptId);
  const isEditMode = useAgentStore((state) => state.isEditMode);
  const isEditVersionMode = useAgentStore((state) => state.isEditVersionMode);

  // Validate and get the effective promptId
  // Priority: 1. Validated session prompt ID, 2. Prop prompt ID
  const promptId = useMemo(() => {
    // Validate prop promptId against the store
    if (propPromptId) {
      const session = getSessionByPromptId(propPromptId);
      if (session) {
        return session.promptId;
      }
    }

    // Fallback to prop promptId
    return propPromptId;
  }, [propPromptId, getSessionByPromptId]);

  const promptIdForConnectors = useMemo(() => {
    if (!promptId) return undefined;
    const session = getSessionByPromptId(promptId);
    if ((isEditMode || isEditVersionMode) && session?.name) {
      return session.name;
    }
    return promptId;
  }, [promptId, getSessionByPromptId, isEditMode, isEditVersionMode]);

  // Get store actions via selectors so their references stay stable
  const fetchConnectedTools = useConnectors((state) => state.fetchConnectedTools);
  const fetchUnregisteredTools = useConnectors((state) => state.fetchUnregisteredTools);
  const fetchConnectorDetails = useConnectors((state) => state.fetchConnectorDetails);
  const clearConnectorDetailsForPromptId = useConnectors((state) => state.clearConnectorDetailsForPromptId);

  const fetchConnectedToolsRef = useRef(fetchConnectedTools);
  const fetchUnregisteredToolsRef = useRef(fetchUnregisteredTools);

  useEffect(() => {
    fetchConnectedToolsRef.current = fetchConnectedTools;
  }, [fetchConnectedTools]);

  useEffect(() => {
    fetchUnregisteredToolsRef.current = fetchUnregisteredTools;
  }, [fetchUnregisteredTools]);

  // Use per-session selectors for data (isolated per agent box)
  const connectors = useConnectors((state) =>
    promptIdForConnectors ? state.connectorsByPromptId[promptIdForConnectors] ?? EMPTY_CONNECTOR_LIST : state.connectors
  );

  const connectedTools = useConnectors((state) =>
    promptIdForConnectors ? state.connectedToolsByPromptId[promptIdForConnectors] ?? EMPTY_CONNECTED_TOOL_LIST : state.connectedTools
  );

  const pagination = useConnectors((state) =>
    promptIdForConnectors ? state.paginationByPromptId[promptIdForConnectors] : null
  );

  const loadingState = useConnectors((state) =>
    promptIdForConnectors ? state.loadingStatesByPromptId[promptIdForConnectors] : null
  );

  // Atomic selectors for global state to prevent object identity churn
  const globalIsLoading = useConnectors(state => state.isLoading);
  const globalIsLoadingMore = useConnectors(state => state.isLoadingMore);
  const globalCurrentPage = useConnectors(state => state.currentPage);
  const globalTotalPages = useConnectors(state => state.totalPages);

  const isLoading = loadingState?.isLoading ?? globalIsLoading;
  const isLoadingMore = loadingState?.isLoadingMore ?? globalIsLoadingMore;
  const currentPage = pagination?.currentPage ?? globalCurrentPage;
  const totalPages = pagination?.totalPages ?? globalTotalPages;

  // Use proper Zustand selectors for stable references
  const selectedConnectorDetails = useConnectors((state) =>
    promptIdForConnectors ? state.connectorDetailsByPromptId[promptIdForConnectors] || null : null
  );

  const isLoadingDetails = useConnectors((state) =>
    promptIdForConnectors ? state.loadingDetailsByPromptId[promptIdForConnectors] || false : false
  );

  const [connectedExpanded, setConnectedExpanded] = useState(true);
  const [toolListExpanded, setToolListExpanded] = useState(true);
  const [localSearchQuery, setLocalSearchQuery] = useState('');
  const [selectedConnector, setSelectedConnector] = useState<Connector | null>(null);
  const [viewMode, setViewMode] = useState<'list' | 'details'>('list');
  const [isSearching, setIsSearching] = useState(false);

  const searchTimeoutRef = useRef<ReturnType<typeof setTimeout>>();
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const isInitialMount = useRef(true);
  const hasRestoredFromUrl = useRef(false);
  const hasSetConnectorFromUrl = useRef(false);
  const fetchedConnectorRef = useRef<string | null>(null); // Track which connector we've fetched
  const isBackNavigationRef = useRef(false);
  const hasFetchedListsRef = useRef<string | null>(null); // Track if we've fetched lists for this promptId
  // Initial load - Fetch both connected and unregistered tools (ONCE per promptId)
  useEffect(() => {
    if (!promptIdForConnectors || hasFetchedListsRef.current === promptIdForConnectors) {
      return;
    }
    hasFetchedListsRef.current = promptIdForConnectors;
    // Fetch connected tools (is_registered: true)
    fetchConnectedTools({ page: 1, prompt_id: promptIdForConnectors });
    // Fetch unregistered tools (is_registered: false)
    fetchUnregisteredTools({ page: 1, prompt_id: promptIdForConnectors });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [promptIdForConnectors]); // Only depend on promptIdForConnectors, NOT on functions

  // Restore connector state from URL on initial load (or from OAuth state)
  // This effect runs ONCE on mount to restore connector from URL
  // CRITICAL: Only auto-open tools if this is an OAuth callback, NOT a manual page refresh
  useEffect(() => {
    // Skip if user explicitly navigated back or no promptId
    if (isBackNavigationRef.current || !promptId) {
      return;
    }

    // Check if this is an OAuth callback - multiple indicators:
    // 1. code/state params in URL (OAuth redirect just happened)
    // 2. authentication=true param in URL (set before OAuth redirect)
    const isOAuthReturn = isOAuthCallback();
    const urlParams = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : null;
    const hasAuthenticationParam = urlParams?.get('authentication') === 'true';

    // Get OAuth state from localStorage
    const oauthState = getOAuthState();

    // CRITICAL: If there's OAuth state but NO code/state params and NO authentication param,
    // this means the OAuth flow was started but not completed (user refreshed manually)
    // Clear the stale OAuth state to prevent auto-opening on manual refresh
    if (oauthState && !isOAuthReturn && !hasAuthenticationParam) {
      clearOAuthState();
    }

    // CRITICAL: Only auto-restore connector if this is a VALID OAuth callback
    // Must have EITHER code/state params OR authentication=true param
    // OAuth state alone is NOT sufficient (could be stale from incomplete OAuth)
    const isValidOAuthCallback = isOAuthReturn || hasAuthenticationParam;

    console.log('[ToolsHome] OAuth check:', { isOAuthReturn, hasAuthenticationParam, isValidOAuthCallback, oauthState: !!oauthState });

    if (!isValidOAuthCallback) {
      // Not a valid OAuth callback - don't auto-open tools on manual page refresh
      console.log('[ToolsHome] Not a valid OAuth callback - skipping auto-open');
      return;
    }

    // Get connector ID - PRIORITIZE OAuth state's connector ID for OAuth callbacks
    // This ensures the connector that triggered the OAuth flow is opened, not the positional one
    let connectorId: string | null = null;
    if (isOAuthReturn && oauthState?.connectorId && oauthState?.promptId === promptId) {
      // OAuth callback - use the connector that initiated the OAuth flow
      connectorId = oauthState.connectorId;
      console.log('[ToolsHome] Using OAuth state connector:', connectorId);
    } else {
      // Fallback to positional lookup from URL
      connectorId = getConnectorFromUrlByPosition(sessionIndex);
    }

    // Prevent duplicate fetch - use ref to track what we've already fetched
    if (!connectorId || fetchedConnectorRef.current === connectorId) {
      return;
    }

    // Mark as fetched BEFORE making the call to prevent re-entry
    fetchedConnectorRef.current = connectorId;
    hasRestoredFromUrl.current = true;

    // Fetch connector details from API with session scope
    fetchConnectorDetails(connectorId, promptIdForConnectors).catch(() => {
      // Reset on error so we can retry
      fetchedConnectorRef.current = null;
      hasRestoredFromUrl.current = false;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [promptId, promptIdForConnectors, sessionIndex]); // Only depend on identity props, NOT on loading state or functions

  // Set selected connector when details are fetched
  useEffect(() => {
    // Skip if user explicitly navigated back or no promptId
    if (isBackNavigationRef.current || !promptId) {
      return;
    }

    // Check if this is a valid OAuth callback
    const isOAuthReturn = isOAuthCallback();
    const urlParams = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : null;
    const hasAuthenticationParam = urlParams?.get('authentication') === 'true';
    const oauthState = getOAuthState();

    // CRITICAL: Only auto-open if this is a VALID OAuth callback
    // Must have EITHER code/state params OR authentication=true param
    const isValidOAuthCallback = isOAuthReturn || hasAuthenticationParam;

    if (!isValidOAuthCallback) {
      // Not a valid OAuth callback - don't auto-open tools on manual page refresh
      return;
    }

    // Get connector ID - PRIORITIZE OAuth state's connector ID for OAuth callbacks
    // This ensures the connector that triggered the OAuth flow is selected, not the positional one
    let connectorId: string | null = null;
    if (isOAuthReturn && oauthState?.connectorId && oauthState?.promptId === promptId) {
      // OAuth callback - use the connector that initiated the OAuth flow
      connectorId = oauthState.connectorId;
    } else {
      // Fallback to positional lookup from URL
      connectorId = getConnectorFromUrlByPosition(sessionIndex);
    }

    // Only proceed if we have connector ID and details loaded
    if (!connectorId || !selectedConnectorDetails || selectedConnectorDetails.id !== connectorId) {
      return;
    }

    // Prevent duplicate setting using ref
    if (hasSetConnectorFromUrl.current) {
      return;
    }

    hasSetConnectorFromUrl.current = true;

    // Check if connector is in connected tools
    const isConnected = connectedTools.some(c => c.id === connectorId);

    setSelectedConnector({
      ...selectedConnectorDetails,
      isFromConnectedSection: isConnected
    } as Connector);
    setViewMode('details');

    // CRITICAL: Remove authentication param from URL after successfully opening tools
    // This ensures that subsequent page refreshes won't auto-open tools
    if (hasAuthenticationParam && typeof window !== 'undefined') {
      const newUrlParams = new URLSearchParams(window.location.search);
      newUrlParams.delete('authentication');
      const newUrl = newUrlParams.toString()
        ? `${window.location.pathname}?${newUrlParams.toString()}`
        : window.location.pathname;
      window.history.replaceState({}, '', newUrl);
    }
  }, [selectedConnectorDetails, promptIdForConnectors, sessionIndex, connectedTools]);

  // Handle search with debounce
  useEffect(() => {
    // Skip on initial mount to avoid duplicate API calls
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }

    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }

    // Show loading indicator when user starts typing
    setIsSearching(true);

    searchTimeoutRef.current = setTimeout(async () => {
      if (promptIdForConnectors) {
        // Refetch both lists with search query
        await Promise.all([
          fetchConnectedToolsRef.current({
            page: 1,
            prompt_id: promptIdForConnectors,
            name: localSearchQuery,
            search: !!localSearchQuery,
            force: true
          }),
          fetchUnregisteredToolsRef.current({
            page: 1,
            prompt_id: promptIdForConnectors,
            name: localSearchQuery,
            search: !!localSearchQuery,
            force: true
          })
        ]);
        // Hide loading indicator after search completes
        setIsSearching(false);
      } else {
        setIsSearching(false);
      }
    }, 500);

    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current);
      }
    };
  }, [localSearchQuery, promptIdForConnectors]);

  // Handle scroll for lazy loading
  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    const element = e.currentTarget;
    const { scrollTop, scrollHeight, clientHeight } = element;

    // Check if scrolled to bottom
    if (scrollHeight - scrollTop <= clientHeight + 50 &&
      !isLoadingMore &&
      currentPage < totalPages &&
      promptIdForConnectors) {
      fetchUnregisteredTools({ page: currentPage + 1, prompt_id: promptIdForConnectors });
    }
  }, [currentPage, totalPages, isLoadingMore, promptIdForConnectors, fetchUnregisteredTools]);

  // Filter tools based on local search (for instant feedback)
  const filterTools = (tools: typeof connectors) => {
    if (!localSearchQuery) return tools;
    return tools.filter(tool =>
      tool.name.toLowerCase().includes(localSearchQuery.toLowerCase())
    );
  };

  const getToolIcon = (tool: typeof connectors[0]) => {
    if (tool.icon) {
      return tool.icon;
    }
    // Fallback to first letter
    return tool.name.charAt(0).toUpperCase();
  };

  const handleConnectorClick = (connector: Connector, isConnected: boolean = false) => {
    // Clear search when navigating to details
    setLocalSearchQuery('');
    // Clear per-session search query
    setIsSearching(false);
    setSelectedConnector({ ...connector, isFromConnectedSection: isConnected } as Connector);
    setViewMode('details');

    // Add connector ID to URL using positional format (index matches prompt IDs position)
    updateConnectorInUrl(sessionIndex, connector.id, totalSessions);
  };

  const handleBackToList = (options?: { removeConnectorFromUrl?: boolean }) => {
    // Set back navigation flag FIRST to prevent effects from re-triggering
    isBackNavigationRef.current = true;

    setSelectedConnector(null);
    setViewMode('list');
    setLocalSearchQuery('');
    // Clear per-session search query
    setIsSearching(false);

    // Reset all URL restoration flags
    hasRestoredFromUrl.current = false;
    hasSetConnectorFromUrl.current = false;
    fetchedConnectorRef.current = null;

    // Clear session-scoped connector details from store
    if (promptIdForConnectors) {
      clearConnectorDetailsForPromptId(promptIdForConnectors);
    }

    // Clear OAuth localStorage state (does not affect URL)
    clearOAuthState();

    // Remove connector from URL if explicitly requested (e.g., after disconnect)
    // Uses positional URL update (only removes this session's connector position)
    if (options?.removeConnectorFromUrl) {
      updateConnectorInUrl(sessionIndex, null, totalSessions);
    }

    // Refresh both lists when coming back
    if (promptIdForConnectors) {
      fetchConnectedTools({ page: 1, prompt_id: promptIdForConnectors, force: true });
      fetchUnregisteredTools({ page: 1, prompt_id: promptIdForConnectors, force: true });
    }

    // Reset back navigation flag after effects have settled
    requestAnimationFrame(() => {
      isBackNavigationRef.current = false;
    });
  };

  // Show loading state when fetching connector from URL (positional check)
  if (isLoadingDetails && getConnectorFromUrlByPosition(sessionIndex)) {
    return (
      <div className="flex flex-col h-full text-white">
        <div className="px-[.857rem] py-4 border-b border-[#1F1F1F]">
          <h2 className="text-lg font-medium">Tools</h2>
        </div>
        <div className="flex-1 flex justify-center items-center">
          <Spin />
        </div>
      </div>
    );
  }

  // Render details view
  if (viewMode === 'details' && selectedConnector) {
    return <ConnectorDetails connector={selectedConnector} onBack={handleBackToList} promptId={promptId} workflowId={workflowId} sessionIndex={sessionIndex} totalSessions={totalSessions} />;
  }

  // Render list view
  return (
    <div className="flex flex-col h-full text-white">
      {/* Header */}
      <div className="px-[.857rem] py-4 border-b border-[#1F1F1F]">
        <h2 className="text-lg font-medium">Tools</h2>
      </div>

      {/* Search Bar */}
      <div className="px-[.875rem] py-4">
        <Input
          placeholder="Search"
          prefix={
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
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.35-4.35" />
            </svg>
          }
          value={localSearchQuery}
          onChange={(e) => setLocalSearchQuery(e.target.value)}
          className="bg-transparent border-[#2A2A2A] hover:border-[#3A3A3A] focus:border-[#965CDE] text-white placeholder:text-[#808080] rounded-[0.403125rem] h-[1.875rem]"
          style={{
            backgroundColor: 'transparent',
            borderColor: '#2A2A2A',
            color: 'white',
          }}
        />
      </div>

      {/* Scrollable Content */}
      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto relative"
        onScroll={handleScroll}
      >
        {/* Search Loading Overlay */}
        {isSearching && (
          <div className="absolute inset-0 bg-[#0A0A0A] bg-opacity-70 flex justify-center items-center z-10">
            <Spin />
          </div>
        )}

        {isLoading && connectors.length === 0 ? (
          <div className="flex justify-center items-center h-full">
            <Spin />
          </div>
        ) : (
          <>
            {/* Connected Tools Section */}
            {connectedTools.length > 0 && (
              <div className="border-b border-[#1F1F1F]">
                <button
                  onClick={() => setConnectedExpanded(!connectedExpanded)}
                  className="w-full px-[.5rem] py-3 flex items-center justify-between text-[#808080] hover:text-white transition-colors"
                  style={{ transform: 'none' }}
                >
                  <Text_14_400_757575 className="px-[0.375rem]">Connected Tools</Text_14_400_757575>
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
                    className={`transition-transform ${connectedExpanded ? 'rotate-180' : ''}`}
                  >
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </button>

                {connectedExpanded && (
                  <div>
                    {filterTools(connectedTools).map((tool) => (
                      <button
                        key={tool.id}
                        onClick={() => handleConnectorClick(tool, true)}
                        className="w-full px-4 py-3 flex items-center justify-between hover:bg-[#1A1A1A] transition-colors group"
                        style={{ transform: 'none' }}
                      >
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-lg bg-[#1F1F1F] flex items-center justify-center text-lg">
                            {getToolIcon(tool)}
                          </div>
                          <span className="text-white">{tool.name}</span>
                        </div>
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
                          className="text-[#808080] group-hover:text-white transition-colors"
                        >
                          <polyline points="9 18 15 12 9 6" />
                        </svg>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Tool List Section */}
            <div>
              <button
                onClick={() => setToolListExpanded(!toolListExpanded)}
                className="w-full px-[.5rem] py-3 flex items-center justify-between text-[#808080] hover:text-white transition-colors"
                style={{ transform: 'none' }}
              >
                <Text_14_400_757575 className="px-[0.375rem]">Tool List</Text_14_400_757575>
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
                  className={`transition-transform ${toolListExpanded ? 'rotate-180' : ''}`}
                >
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </button>

              {toolListExpanded && (
                <div>
                  {filterTools(connectors).length === 0 && !isLoading ? (
                    <div className="px-4 py-8">
                      <Empty
                        description="No tools found"
                        image={Empty.PRESENTED_IMAGE_SIMPLE}
                        className="text-[#808080]"
                      />
                    </div>
                  ) : (
                    <>
                      {filterTools(connectors).map((tool) => (
                        <button
                          key={`list-${tool.id}`}
                          onClick={() => handleConnectorClick(tool)}
                          className="w-full px-[.5rem] py-[.563rem] flex items-center justify-between border-b-[.5px] border-t-[.5px] border-t-[transparent] border-b-[#1F1F1F] hover:bg-[#ffffff08] hover:border-b-[#757575] hover:border-t-[#757575] transition-colors group"
                          style={{ transform: 'none' }}
                        >
                          <div className="flex items-center gap-3 max-w-[92%]">
                            <div className="w-8 h-8 rounded-lg bg-[#1F1F1F] flex items-center justify-center text-lg">
                              {getToolIcon(tool)}
                            </div>
                            <Text_14_400_EEEEEE className='truncate'>{tool.name}</Text_14_400_EEEEEE>
                          </div>
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
                            className="text-[#808080] group-hover:text-white transition-colors"
                          >
                            <polyline points="9 18 15 12 9 6" />
                          </svg>
                        </button>
                      ))}

                      {/* Loading more indicator */}
                      {isLoadingMore && (
                        <div className="flex justify-center py-4">
                          <Spin />
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
};

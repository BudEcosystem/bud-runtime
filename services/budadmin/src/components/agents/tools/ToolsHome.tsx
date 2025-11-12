'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Input, Spin, Empty } from 'antd';
import { useRouter, useSearchParams } from 'next/navigation';
import { useConnectors, Connector } from '@/stores/useConnectors';
import { Text_14_400_757575, Text_14_400_EEEEEE } from '@/components/ui/text';
import { ConnectorDetails } from './ConnectorDetails';

interface ToolsHomeProps {
  promptId?: string;
  workflowId?: string;
}

export const ToolsHome: React.FC<ToolsHomeProps> = ({ promptId, workflowId }) => {
  const router = useRouter();
  const searchParams = useSearchParams();

  const {
    connectors,
    connectedTools,
    isLoading,
    isLoadingMore,
    totalPages,
    currentPage,
    setSearchQuery,
    fetchConnectedTools,
    fetchUnregisteredTools,
    fetchConnectorDetails,
    selectedConnectorDetails,
    isLoadingDetails,
  } = useConnectors();

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
  const lastConnectorIdRef = useRef<string | null>(null);

  // Initial load - Fetch both connected and unregistered tools
  useEffect(() => {
    if (promptId) {
      // Fetch connected tools (is_registered: true)
      fetchConnectedTools({ page: 1, prompt_id: promptId });
      // Fetch unregistered tools (is_registered: false)
      fetchUnregisteredTools({ page: 1, prompt_id: promptId });
    }
  }, [promptId]);

  // Restore connector state from URL on initial load
  useEffect(() => {
    const connectorId = searchParams.get('connector');

    // Reset refs when connector ID changes
    if (connectorId !== lastConnectorIdRef.current) {
      hasRestoredFromUrl.current = false;
      hasSetConnectorFromUrl.current = false;
      lastConnectorIdRef.current = connectorId;
    }

    // Prevent duplicate restoration or unnecessary calls
    if (!connectorId || hasRestoredFromUrl.current) {
      return;
    }

    // Don't fetch if already loading
    if (isLoadingDetails) {
      return;
    }

    // Don't fetch if we already have the details for this connector
    if (selectedConnectorDetails && selectedConnectorDetails.id === connectorId) {
      hasRestoredFromUrl.current = true;
      return;
    }

    // Fetch connector details from API (only once)
    hasRestoredFromUrl.current = true;
    fetchConnectorDetails(connectorId).catch((error) => {
      console.error('Error fetching connector from URL:', error);
      hasRestoredFromUrl.current = false;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  // Set selected connector when details are fetched
  useEffect(() => {
    const connectorId = searchParams.get('connector');

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
  }, [selectedConnectorDetails, searchParams, connectedTools]);

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
      setSearchQuery(localSearchQuery);
      if (promptId) {
        // Refetch both lists with search query
        await Promise.all([
          fetchConnectedTools({ page: 1, prompt_id: promptId }),
          fetchUnregisteredTools({ page: 1, prompt_id: promptId })
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
  }, [localSearchQuery, setSearchQuery, promptId]);

  // Handle scroll for lazy loading
  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    const element = e.currentTarget;
    const { scrollTop, scrollHeight, clientHeight } = element;

    // Check if scrolled to bottom
    if (scrollHeight - scrollTop <= clientHeight + 50 &&
        !isLoadingMore &&
        currentPage < totalPages &&
        promptId) {
      fetchUnregisteredTools({ page: currentPage + 1, prompt_id: promptId });
    }
  }, [currentPage, totalPages, isLoadingMore, promptId, fetchUnregisteredTools]);

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
    setSearchQuery('');
    setIsSearching(false);
    setSelectedConnector({ ...connector, isFromConnectedSection: isConnected } as Connector);
    setViewMode('details');

    // Add connector ID to URL parameters while preserving all existing parameters
    const params = new URLSearchParams(window.location.search);
    params.set('connector', connector.id);
    const newUrl = `${window.location.pathname}?${params.toString()}`;

    // Use window.history.pushState to avoid Next.js router interference
    window.history.pushState({}, '', newUrl);
  };

  const handleBackToList = () => {
    setSelectedConnector(null);
    setViewMode('list');

    // Reset all URL restoration flags
    hasRestoredFromUrl.current = false;
    hasSetConnectorFromUrl.current = false;
    lastConnectorIdRef.current = null;

    // Remove connector parameter from URL while preserving all other parameters
    const params = new URLSearchParams(window.location.search);
    params.delete('connector');
    const newUrl = `${window.location.pathname}?${params.toString()}`;

    // Use window.history.pushState to avoid Next.js router interference
    window.history.pushState({}, '', newUrl);

    // Refresh both lists when coming back
    if (promptId) {
      fetchConnectedTools({ page: 1, prompt_id: promptId });
      fetchUnregisteredTools({ page: 1, prompt_id: promptId });
    }
  };

  // Show loading state when fetching connector from URL
  if (isLoadingDetails && searchParams.get('connector')) {
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
    return <ConnectorDetails connector={selectedConnector} onBack={handleBackToList} promptId={promptId} workflowId={workflowId} />;
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

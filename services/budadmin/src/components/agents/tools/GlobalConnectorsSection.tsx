'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Spin, Empty } from 'antd';
import { useGlobalConnectors, Gateway } from '@/stores/useGlobalConnectors';
import { Text_14_400_757575, Text_14_400_EEEEEE, Text_12_400_EEEEEE } from '@/components/ui/text';
import { errorToast } from '@/components/toast';

const GLOBAL_OAUTH_STATE_KEY = 'global_oauth_connector_state';

interface GlobalConnectorsSectionProps {
  promptId?: string;
  onToolSelect?: (gatewayId: string, toolIds: string[]) => void;
}

interface GatewayWithStatus extends Gateway {
  isAuthorized?: boolean;
  oauthLoading?: boolean;
  toolsExpanded?: boolean;
  tools?: any[];
  toolsLoading?: boolean;
}

export const GlobalConnectorsSection: React.FC<GlobalConnectorsSectionProps> = ({
  promptId,
  onToolSelect,
}) => {
  const fetchAvailable = useGlobalConnectors((state) => state.fetchAvailable);
  const availableGateways = useGlobalConnectors((state) => state.availableGateways);
  const availableLoading = useGlobalConnectors((state) => state.availableLoading);
  const getOAuthStatus = useGlobalConnectors((state) => state.getOAuthStatus);
  const initiateOAuth = useGlobalConnectors((state) => state.initiateOAuth);
  const listToolsForGateway = useGlobalConnectors((state) => state.listToolsForGateway);

  const [expanded, setExpanded] = useState(true);
  const [gatewayStatuses, setGatewayStatuses] = useState<Record<string, GatewayWithStatus>>({});

  // Fetch available gateways on mount
  useEffect(() => {
    fetchAvailable({ limit: 50 });
  }, [fetchAvailable]);

  // Fetch OAuth status for each gateway
  useEffect(() => {
    if (!availableGateways.length) return;

    const fetchStatuses = async () => {
      const statuses: Record<string, GatewayWithStatus> = {};
      for (const gw of availableGateways) {
        try {
          const status = await getOAuthStatus(gw.id);
          statuses[gw.id] = {
            ...gw,
            isAuthorized: status?.oauth_enabled === true,
          };
        } catch {
          statuses[gw.id] = { ...gw, isAuthorized: false };
        }
      }
      setGatewayStatuses(statuses);
    };

    fetchStatuses();
  }, [availableGateways, getOAuthStatus]);

  const handleConnect = useCallback(async (gateway: Gateway) => {
    const result = await initiateOAuth(gateway.id);
    if (result?.authorization_url) {
      // Save state for OAuth callback
      localStorage.setItem(
        GLOBAL_OAUTH_STATE_KEY,
        JSON.stringify({
          gatewayId: gateway.id,
          gatewayName: gateway.name,
          oauthType: 'global',
          timestamp: Date.now(),
        })
      );
      window.location.href = result.authorization_url;
    } else {
      errorToast('Failed to get authorization URL');
    }
  }, [initiateOAuth]);

  const handleToggleTools = useCallback(async (gatewayId: string) => {
    setGatewayStatuses((prev) => {
      const current = prev[gatewayId];
      if (!current) return prev;

      if (current.toolsExpanded) {
        return { ...prev, [gatewayId]: { ...current, toolsExpanded: false } };
      }

      // Expand and load tools if not loaded
      if (!current.tools) {
        const updated = { ...prev, [gatewayId]: { ...current, toolsExpanded: true, toolsLoading: true } };

        // Fetch tools async
        listToolsForGateway(gatewayId).then((tools) => {
          setGatewayStatuses((p) => ({
            ...p,
            [gatewayId]: { ...p[gatewayId], tools, toolsLoading: false },
          }));
        });

        return updated;
      }

      return { ...prev, [gatewayId]: { ...current, toolsExpanded: true } };
    });
  }, [listToolsForGateway]);

  if (availableLoading && !availableGateways.length) {
    return null;
  }

  if (!availableGateways.length) {
    return null;
  }

  return (
    <div className="border-b border-[#1F1F1F]">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-[.5rem] py-3 flex items-center justify-between text-[#808080] hover:text-white transition-colors"
        style={{ transform: 'none' }}
      >
        <Text_14_400_757575 className="px-[0.375rem]">Global Connectors</Text_14_400_757575>
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
          className={`transition-transform ${expanded ? 'rotate-180' : ''}`}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {expanded && (
        <div>
          {availableGateways.map((gw) => {
            const status = gatewayStatuses[gw.id];
            const isAuthorized = status?.isAuthorized;
            const isToolsExpanded = status?.toolsExpanded;
            const tools = status?.tools;
            const toolsLoading = status?.toolsLoading;

            return (
              <div key={gw.id} className="border-b-[.5px] border-b-[#1F1F1F]">
                <div className="w-full px-[.5rem] py-[.563rem] flex items-center justify-between hover:bg-[#ffffff08] transition-colors">
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <div className="w-8 h-8 rounded-lg bg-[#1F1F1F] flex items-center justify-center text-lg shrink-0">
                      {gw.name?.charAt(0)?.toUpperCase() || 'G'}
                    </div>
                    <div className="flex flex-col min-w-0">
                      <Text_14_400_EEEEEE className="truncate">
                        {gw.name?.replace('global__', '') || gw.id}
                      </Text_14_400_EEEEEE>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {isAuthorized ? (
                      <>
                        <span className="text-[#52c41a] text-xs">Connected</span>
                        <button
                          onClick={() => handleToggleTools(gw.id)}
                          className="p-1 hover:bg-[#2A2A2A] rounded transition-colors"
                          title="View tools"
                        >
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            width="14"
                            height="14"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            className={`text-[#808080] transition-transform ${isToolsExpanded ? 'rotate-180' : ''}`}
                          >
                            <polyline points="6 9 12 15 18 9" />
                          </svg>
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={() => handleConnect(gw)}
                        className="px-3 py-1 text-xs rounded bg-[#965CDE] hover:bg-[#7B4DBF] text-white transition-colors"
                      >
                        Connect
                      </button>
                    )}
                  </div>
                </div>

                {/* Expanded tools list */}
                {isToolsExpanded && (
                  <div className="pl-12 pr-4 pb-2">
                    {toolsLoading ? (
                      <div className="py-2 flex justify-center">
                        <Spin size="small" />
                      </div>
                    ) : tools && tools.length > 0 ? (
                      <div className="flex flex-col gap-1">
                        {tools.map((tool: any) => (
                          <div
                            key={tool.id}
                            className="flex items-center gap-2 py-1 px-2 rounded hover:bg-[#ffffff08] transition-colors"
                          >
                            <div className="w-1.5 h-1.5 rounded-full bg-[#965CDE] shrink-0" />
                            <Text_12_400_EEEEEE className="truncate">
                              {tool.displayName || tool.originalName || tool.name || tool.id}
                            </Text_12_400_EEEEEE>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <Text_14_400_757575 className="py-2">No tools available</Text_14_400_757575>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

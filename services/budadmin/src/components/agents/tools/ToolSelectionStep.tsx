'use client';

import React from 'react';
import { Checkbox, Spin } from 'antd';
import { Text_12_400_EEEEEE } from '@/components/ui/text';
import { PrimaryButton, SecondaryButton } from '@/components/ui/bud/form/Buttons';

interface Tool {
  id: string;
  name: string;
  is_added?: boolean;
}

interface ToolSelectionStepProps {
  availableTools: Tool[];
  selectedTools: string[];
  selectAll: boolean;
  isLoadingTools: boolean;
  isConnecting: boolean;
  isDisconnecting: boolean;
  isFromConnectedSection: boolean;
  onSelectAll: (checked: boolean) => void;
  onToolToggle: (tool: Tool, checked: boolean) => void;
  onToolClick: (tool: Tool) => void;
  onConnect: () => void;
  onDisconnect: () => void;
}

export const ToolSelectionStep: React.FC<ToolSelectionStepProps> = ({
  availableTools,
  selectedTools,
  selectAll,
  isLoadingTools,
  isConnecting,
  isDisconnecting,
  isFromConnectedSection,
  onSelectAll,
  onToolToggle,
  onToolClick,
  onConnect,
  onDisconnect,
}) => {
  if (isLoadingTools) {
    return (
      <div className="flex justify-center items-center py-8">
        <Spin />
      </div>
    );
  }

  return (
    <div className='flex flex-col h-full justify-between'>
      <div>
        {/* Select All Tools */}
        <div className="flex items-center gap-2 mb-4 px-[1.125rem]">
          <Checkbox
            checked={selectAll}
            onChange={(e) => onSelectAll(e.target.checked)}
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
                  onClick={() => onToolClick(tool)}
                  className="flex items-center justify-between px-[0.625rem] py-[0.46875rem] rounded-lg hover:bg-[#1A1A1A] border-[.5px] border-[transparent] hover:border-[#2A2A2A] cursor-pointer"
                >
                  <div className='flex items-center justify-start gap-[.5rem]'>
                    <Checkbox
                      checked={selectedTools.includes(toolId)}
                      onChange={(e) => {
                        e.stopPropagation();
                        onToolToggle(tool, e.target.checked);
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

      {/* Buttons */}
      <div style={{
        marginTop: '18px',
        paddingTop: '18px',
        paddingBottom: '18px',
        borderRadius: '0 0 11px 11px',
        borderTop: '0.5px solid #1F1F1F',
        background: 'rgba(255, 255, 255, 0.03)',
        backdropFilter: 'blur(5px)'
      }} className='px-[1rem]'>
        {isFromConnectedSection ? (
          // Show Save and Disconnect buttons for connected tools
          <div className='flex justify-between items-center'>
            <SecondaryButton
              onClick={onConnect}
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
              onClick={onDisconnect}
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
              onClick={onConnect}
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
    </div>
  );
};

'use client';

import React from 'react';
import { ToolsHome } from './ToolsHome';

interface ToolsSidebarProps {
  isOpen: boolean;
  onClose?: () => void;
  promptId?: string;
  workflowId?: string;
  sessionIndex?: number; // Position of this session in active sessions array
  totalSessions?: number; // Total number of active sessions
}

export const ToolsSidebar: React.FC<ToolsSidebarProps> = ({
  isOpen,
  onClose,
  promptId,
  workflowId,
  sessionIndex = 0,
  totalSessions = 1,
}) => {
  if (!isOpen) return null;

  return (
    <div
      className="z-[100] tools-box absolute p-3 right-0 top-0 h-full transition-all duration-300 ease-in-out translate-x-0"
      onClick={(e) => e.stopPropagation()} // Prevent closing when clicking inside tools
    >
      <div
        className="flex flex-col h-full w-[16rem] prompt-settings overflow-y-auto rounded-[12px]"
        style={{
          backgroundImage: 'url(/agents/settingsBg.png)',
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          backgroundRepeat: 'no-repeat'
        }}
      >
        <ToolsHome promptId={promptId} workflowId={workflowId} sessionIndex={sessionIndex} totalSessions={totalSessions} />
      </div>
    </div>
  );
};

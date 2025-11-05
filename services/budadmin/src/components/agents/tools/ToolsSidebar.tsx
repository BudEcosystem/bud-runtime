'use client';

import React from 'react';
import { ToolsHome } from './ToolsHome';

interface ToolsSidebarProps {
  isOpen: boolean;
  onClose?: () => void;
  promptId?: string;
}

export const ToolsSidebar: React.FC<ToolsSidebarProps> = ({
  isOpen,
  onClose,
  promptId,
}) => {
  return (
    <div
      className={`z-[100] tools-box absolute p-3 right-0 top-0 h-full transition-all duration-300 ease-in-out ${
        isOpen ? 'translate-x-0' : 'translate-x-full'
      }`}
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
        <ToolsHome promptId={promptId} />
      </div>
    </div>
  );
};

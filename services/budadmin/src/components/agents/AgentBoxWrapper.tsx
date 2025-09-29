'use client';

import dynamic from 'next/dynamic';
import React from 'react';
import { AgentSession } from '@/stores/useAgentStore';

const AgentBox = dynamic(() => import('./AgentBox'), {
  ssr: false,
  loading: () => (
    <div className="agent-box flex flex-col bg-[#0A0A0A] border border-[#1F1F1F] rounded-lg min-w-[400px] h-full overflow-hidden justify-center items-center">
      <span className="text-[#808080]">Loading...</span>
    </div>
  ),
});

interface AgentBoxWrapperProps {
  session: AgentSession;
  index: number;
  totalSessions: number;
  onToggleRightSidebar?: () => void;
  isRightSidebarOpen?: boolean;
}

const AgentBoxWrapper: React.FC<AgentBoxWrapperProps> = (props) => {
  return <AgentBox {...props} />;
};

export default AgentBoxWrapper;

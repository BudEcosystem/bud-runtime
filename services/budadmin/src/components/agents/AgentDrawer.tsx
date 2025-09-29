import React, { useEffect, useRef, useState } from "react";
import { Drawer, Empty, Tooltip, Image } from "antd";
import {
  SettingOutlined,
  PlayCircleOutlined,
  MessageOutlined
} from "@ant-design/icons";
import { useAgentStore } from "@/stores/useAgentStore";
import AgentBoxWrapper from "./AgentBoxWrapper";
import AgentSelector from "./AgentSelector";

const AgentDrawer: React.FC = () => {
  const {
    isAgentDrawerOpen,
    closeAgentDrawer,
    sessions,
    activeSessionIds,
    createSession,
  } = useAgentStore();

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [drawerWidth, setDrawerWidth] = useState<string>('100%');
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);

  // Get active sessions
  const activeSessions = sessions.filter((session) =>
    activeSessionIds.includes(session.id)
  );

  // Create initial session when drawer opens if none exist
  useEffect(() => {
    if (isAgentDrawerOpen && activeSessions.length === 0) {
      createSession();
    }
  }, [isAgentDrawerOpen, activeSessions.length, createSession]);

  // Set drawer width on client side
  useEffect(() => {
    const updateDrawerWidth = () => {
      if (typeof window !== 'undefined') {
        const screenWidth = window.innerWidth;
        setDrawerWidth(`${screenWidth}px`);
      }
    };

    updateDrawerWidth();
    window.addEventListener('resize', updateDrawerWidth);

    return () => {
      window.removeEventListener('resize', updateDrawerWidth);
    };
  }, []);



  return (
    <>
      <Drawer
        open={isAgentDrawerOpen}
        onClose={closeAgentDrawer}
        placement="right"
        width={drawerWidth}
        className="agent-drawer p-[.75rem]"
        closeIcon={null}
        styles={{
          wrapper: {
            backgroundColor: "transparent",
            boxShadow: "none",
          },
          mask: {
            backgroundColor: "#101010",
          },
          content: {
            backgroundColor: "#101010",
          },
          header: {
            padding: "16px 24px",
          },
          body: {
            backgroundColor: "#050505",
            border: "none",
          },
        }}
      >
        <div className="flex h-full relative justify-between">
          {/* Control Bar - Vertical icon bar on the left */}
          <div className="control-bar left-0 bg-[transparent] h-full flex flex-col items-center justify-between py-4 px-[1rem] z-[1045]">
            <div className="this-back mb-3">
              <Tooltip title="Back" placement="right">
                <button
                  onClick={closeAgentDrawer}
                  className="control-bar-icon w-8 h-8 flex items-center justify-center rounded-md border-none bg-transparent p-0"
                >
                  <Image
                    src="/icons/left-circle-navigation.svg"
                    alt="Back"
                    preview={false}
                    className="transition-transform hover:scale-105 w-8 h-8"
                  />
                </button>
              </Tooltip>
            </div>
            <div>
              {/* Settings Icon */}
              <Tooltip title="Settings" placement="right">
                <button
                  onClick={() => setIsSettingsOpen(!isSettingsOpen)}
                  className="control-bar-icon w-8 h-8 flex items-center justify-center rounded-md hover:bg-[#1A1A1A] transition-colors mb-3"
                >
                  <SettingOutlined className="text-[#808080] hover:text-[#EEEEEE] text-lg" />
                </button>
              </Tooltip>


              {/* Play/Run Icon */}
              <Tooltip title="Run Agent" placement="right">
                <button className="control-bar-icon w-8 h-8 flex items-center justify-center rounded-md hover:bg-[#1A1A1A] transition-colors mb-3">
                  <PlayCircleOutlined className="text-[#808080] hover:text-[#4ADE80] text-lg" />
                </button>
              </Tooltip>

              {/* Chat/Message Icon */}
              <Tooltip title="Chat History" placement="right">
                <button className="control-bar-icon w-8 h-8 flex items-center justify-center rounded-md hover:bg-[#1A1A1A] transition-colors">
                  <MessageOutlined className="text-[#808080] hover:text-[#965CDE] text-lg" />
                </button>
              </Tooltip>
            </div>
            <div></div>
          </div>
          <div className="w-full">
            {/* Content */}
            <div className="h-full bg-[transparent] relative">
              {activeSessions.length > 0 ? (
                <div
                  ref={scrollContainerRef}
                  className="flex h-full overflow-x-auto overflow-y-hidden gap-4 agent-boxes-container"
                  style={{
                    scrollBehavior: "smooth",
                    scrollSnapType: "x proximity",
                  }}
                >
                  {/* Agent Boxes */}
                  {activeSessions.map((session, index) => (
                    <div
                      key={session.id}
                      className="flex-shrink-0"
                      style={{ scrollSnapAlign: "start" }}
                    >
                      <AgentBoxWrapper
                        session={session}
                        index={index}
                        totalSessions={activeSessions.length}
                        onToggleRightSidebar={() => setIsSettingsOpen(!isSettingsOpen)}
                        isRightSidebarOpen={isSettingsOpen}
                      />
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex items-center justify-center h-full">
                  <Empty
                    description={
                      <div className="text-center">
                        <p className="text-[#808080] mb-4">No agents configured</p>
                        <p className="text-[#606060] text-xs">Create a new agent session to get started</p>
                      </div>
                    }
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      </Drawer>

      {/* Agent Selector Modal */}
      <AgentSelector />
    </>
  );
};

export default AgentDrawer;

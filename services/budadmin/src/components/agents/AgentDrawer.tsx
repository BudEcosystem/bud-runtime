import React, { useEffect, useRef, useState } from "react";
import { Drawer, Empty, Tooltip, Image } from "antd";
import {
  SettingOutlined,
  PlayCircleOutlined,
  MessageOutlined
} from "@ant-design/icons";
import { useAgentStore } from "@/stores/useAgentStore";
import { useDrawer } from "@/hooks/useDrawer";
import AgentBoxWrapper from "./AgentBoxWrapper";
import AgentSelector from "./AgentSelector";
import dynamic from "next/dynamic";
import { useRouter } from "next/router";

const AgentIframe = dynamic(() => import("./AgentIframe"), { ssr: false });

const AgentDrawer: React.FC = () => {
  const router = useRouter();
  const {
    isAgentDrawerOpen,
    closeAgentDrawer,
    sessions,
    activeSessionIds,
    createSession,
    workflowContext,
    isEditMode,
    editingPromptId,
    clearEditMode,
    isAddVersionMode,
    addVersionPromptId,
    isEditVersionMode,
    editVersionData,
  } = useAgentStore();

  const { openDrawerWithStep, step, currentFlow } = useDrawer();

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [drawerWidth, setDrawerWidth] = useState<string>('100%');
  const [showPlayground, setShowPlayground] = useState(false);
  const [showChatHistory, setShowChatHistory] = useState(false);
  const [activeBoxId, setActiveBoxId] = useState<string | null>(null);
  const [typeFormMessage, setTypeFormMessage] = useState<{ timestamp: number; value: boolean } | null>(null);

  // Get active sessions
  const activeSessions = sessions.filter((session) =>
    activeSessionIds.includes(session.id)
  );

  // Handle close button click
  const handleCloseDrawer = () => {
    // Remove prompt parameter from URL
    removePromptFromUrl();

    // Check if we're in a workflow
    if (workflowContext.isInWorkflow) {
      // Close the agent drawer
      closeAgentDrawer();
      // Navigate back to select agent type
      setTimeout(() => {
        openDrawerWithStep("add-agent-select-type");
      }, 100);
    } else {
      // Just close the drawer
      closeAgentDrawer();
    }
    // Reset views when drawer closes
    setShowPlayground(false);
    setShowChatHistory(false);
    // Clear edit mode is handled in closeAgentDrawer in the store
  };

  // Helper function to remove prompt parameter from URL
  const removePromptFromUrl = () => {
    if (typeof window === 'undefined') return;

    const currentPath = window.location.pathname;
    const urlSearchParams = new URLSearchParams(window.location.search);

    // Remove the prompt parameter
    urlSearchParams.delete('prompt');

    // Build query parts for remaining parameters
    const queryParts: string[] = [];
    urlSearchParams.forEach((value, key) => {
      if (value) {
        // Don't encode agent parameter
        if (key === 'agent') {
          queryParts.push(`${key}=${value}`);
        } else {
          queryParts.push(`${key}=${encodeURIComponent(value)}`);
        }
      }
    });

    // Build the final URL
    const newUrl = queryParts.length > 0
      ? `${currentPath}?${queryParts.join('&')}`
      : currentPath;

    // Use window.history.replaceState to update URL
    window.history.replaceState(
      { ...window.history.state },
      '',
      newUrl
    );
  };

  // Handle Play button click
  const handlePlayClick = () => {
    const wasAnyViewOpen = showPlayground || showChatHistory;

    // Always ensure the playground is shown and chat history is hidden when play is clicked
    setShowPlayground(true);
    setShowChatHistory(false);

    if (wasAnyViewOpen) {
      // If a view was already open, switch to type mode
      setTypeFormMessage({ timestamp: Date.now(), value: true });
    }
  };

  // Handle Settings button click
  const handleSettingsClick = () => {
    if (showPlayground || showChatHistory) {
      setShowPlayground(false);
      setShowChatHistory(false);
    }
  };

  // Handle Chat History button click
  const handleChatHistoryClick = () => {
    // Only allow click if playground is enabled
    if (showPlayground || showChatHistory) {
      setShowChatHistory(true);
      setShowPlayground(false);
      setTypeFormMessage({ timestamp: Date.now(), value: false });
    }
  };

  // Create initial session when drawer opens if none exist
  useEffect(() => {
    if (!isAgentDrawerOpen) return;

    // Check if this is an OAuth callback - don't create new session
    const isOAuthCallback = localStorage.getItem('oauth_should_open_drawer') === 'true';

    if (isOAuthCallback) {
      // OAuth callback - session should already exist, don't create new one
      return;
    }

    // Don't create a new session if in edit mode, add version mode, or edit version mode (session already loaded)
    if (isEditMode || isAddVersionMode || isEditVersionMode) {
      return;
    }

    // Only create session if none exist AND not OAuth callback AND not in any special mode
    if (activeSessions.length === 0) {
      createSession();
    }
  }, [isAgentDrawerOpen, activeSessions.length, createSession, isEditMode, isAddVersionMode, isEditVersionMode]);

  // Set first session as active by default
  useEffect(() => {
    if (activeSessions.length > 0 && !activeBoxId) {
      setActiveBoxId(activeSessions[0].id);
    }
  }, [activeSessions, activeBoxId]);

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

  // Update URL with prompt IDs when active sessions change
  useEffect(() => {
    if (!isAgentDrawerOpen) return;

    // Don't update URL if we're on the add-agent success step
    // This allows AgentSuccess component to clear the URL parameters
    if (currentFlow === 'add-agent' && step?.id === 'add-agent-success') {
      return;
    }

    // Get all prompt IDs from active sessions
    const promptIds = activeSessions
      .map(session => session.promptId)
      .filter(Boolean); // Remove undefined/null values

    // Get current prompt param from URL
    const currentPromptParam = router.query.prompt;
    const newPromptParam = promptIds.length > 0 ? promptIds.join(',') : undefined;

    // Only update if the URL param is different from what we want to set
    if (currentPromptParam !== newPromptParam) {
      console.log('🔄 AgentDrawer updating URL:', {
        currentPrompt: currentPromptParam,
        newPrompt: newPromptParam,
        willAddPrompt: !!newPromptParam
      });

      // Build URL manually to avoid encoding commas
      // Use window.location to get the actual browser URL
      const currentPath = window.location.pathname;
      const queryParts: string[] = [];

      // Parse existing query params from actual browser URL (not router.query)
      // This ensures we capture params added via window.history.replaceState
      const urlSearchParams = new URLSearchParams(window.location.search);

      // CRITICAL: Explicitly capture agent parameter FIRST before any operations
      const agentParam = urlSearchParams.get('agent');
      console.log('📌 Agent parameter captured:', agentParam);

      // Add all existing query params except 'prompt'
      urlSearchParams.forEach((value, key) => {
        if (key !== 'prompt' && value) {
          // Don't encode agent parameter
          if (key === 'agent') {
            queryParts.push(`${key}=${value}`);
          } else {
            queryParts.push(`${key}=${encodeURIComponent(value)}`);
          }
        }
      });

      // TRIPLE-CHECK: If agent parameter was in URL but somehow not added, force add it
      if (agentParam && !queryParts.some(part => part.startsWith('agent='))) {
        console.log('⚠️ Agent parameter was missing, force adding it!');
        queryParts.unshift(`agent=${agentParam}`);
      }

      // Add new prompt param if exists (without encoding commas)
      if (newPromptParam) {
        queryParts.push(`prompt=${newPromptParam}`);
        console.log('✓ Adding prompt parameter:', newPromptParam);
      }

      console.log('🔧 Final query parts:', queryParts);

      // Build the final URL
      const newUrl = queryParts.length > 0
        ? `${currentPath}?${queryParts.join('&')}`
        : currentPath;

      console.log('✓ New URL:', newUrl);

      // Use window.history.replaceState to update URL
      window.history.replaceState(
        { ...window.history.state },
        '',
        newUrl
      );
    }
  }, [activeSessions, isAgentDrawerOpen, router, currentFlow, step]);



  return (
    <>
      <Drawer
        open={isAgentDrawerOpen}
        onClose={handleCloseDrawer}
        placement="right"
        width={drawerWidth}
        className="agent-drawer p-[.75rem]"
        closeIcon={null}
        styles={{
          wrapper: {
            backgroundColor: "transparent",
            boxShadow: "none",
            zIndex: 1050, // Higher than AddAgent drawer to ensure proper stacking
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
        <div className="flex h-full relative">
          {/* Control Bar - Vertical icon bar on the left */}
          <div className="control-bar left-0 bg-[transparent] h-full flex flex-col items-center justify-between py-4 px-[1rem] z-[1045] w-[4rem]">
            <div className="this-back mb-3">
              <Tooltip title="Back" placement="right">
                <button
                  onClick={handleCloseDrawer}
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
              {/* Settings Icon - Now opens settings for individual agent boxes */}
              <Tooltip title={(showPlayground || showChatHistory) ? "Back to Agent Settings" : "Use settings icon in each agent box"} placement="right">
                <button
                  onClick={handleSettingsClick}
                  className={`control-bar-icon w-8 h-8 flex items-center justify-center rounded-md transition-colors mb-3 ${
                    (showPlayground || showChatHistory)
                      ? 'cursor-pointer'
                      : activeSessions.length > 0
                        ? 'cursor-not-allowed'
                        : 'opacity-50 cursor-not-allowed'
                  }`}
                  disabled={!showPlayground && !showChatHistory}
                >
                  <SettingOutlined className={`text-lg ${activeSessions.length > 0 && !showPlayground && !showChatHistory ? 'text-[#EEEEEE]' : 'text-[#808080]'}`} />
                </button>
              </Tooltip>


              {/* Play/Run Icon */}
              <Tooltip title={showPlayground ? "Switch to Type Mode" : "Run Agent"} placement="right">
                <button
                  onClick={handlePlayClick}
                  className="control-bar-icon w-8 h-8 flex items-center justify-center rounded-md transition-colors mb-3"
                >
                  <PlayCircleOutlined className={`text-lg ${showPlayground ? 'text-[#EEEEEE]' : 'text-[#808080] hover:text-[#EEEEEE]'}`} />
                </button>
              </Tooltip>

              {/* Chat/Message Icon */}
              <Tooltip title={(showPlayground || showChatHistory) ? "Chat History" : "Enable playground first"} placement="right">
                <button
                  onClick={handleChatHistoryClick}
                  className={`control-bar-icon w-8 h-8 flex items-center justify-center rounded-md transition-colors ${
                    (showPlayground || showChatHistory) ? 'cursor-pointer' : 'cursor-not-allowed opacity-50'
                  }`}
                  disabled={!showPlayground && !showChatHistory}
                >
                  <MessageOutlined className={`text-lg ${showChatHistory ? 'text-[#EEEEEE]' : 'text-[#808080] hover:text-[#EEEEEE]'}`} />
                </button>
              </Tooltip>
            </div>
            <div></div>
          </div>
          <div className="flex-1" style={{ width: "calc(100% - 4rem)" }}>
            {/* Content */}
            <div className="h-full w-[100%] bg-[transparent] relative">
              {(showPlayground || showChatHistory) ? (
                /* Playground/Iframe View or Chat History View */
                <div className="h-full w-full">
                  <AgentIframe
                    sessionId={activeSessions[0]?.id}
                    promptIds={activeSessions.map(session => session.promptId).filter(Boolean) as string[]}
                    typeFormMessage={typeFormMessage}
                  />
                </div>
              ) : (
                /* Agent Boxes View */
                <>
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
                      {activeSessions.slice(0, 3).map((session, index) => {
                        const numBoxes = Math.min(activeSessions.length, 3);
                        const boxWidth = numBoxes === 1
                          ? "100%"
                          : `calc(${100 / numBoxes}% - ${(numBoxes - 1) * 16 / numBoxes}px)`;

                        return (
                          <div
                            key={session.id}
                            className="flex-shrink-0"
                            style={{
                              width: boxWidth,
                              scrollSnapAlign: "start",
                              transition: "width 0.3s ease",
                              minWidth: "600px",
                            }}
                          >
                            <AgentBoxWrapper
                              session={session}
                              index={index}
                              totalSessions={numBoxes}
                              isActive={activeBoxId === session.id}
                              onActivate={() => setActiveBoxId(session.id)}
                              isAddVersionMode={isAddVersionMode}
                              isEditVersionMode={isEditVersionMode}
                              editVersionData={editVersionData}
                            />
                          </div>
                        );
                      })}
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
                </>
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

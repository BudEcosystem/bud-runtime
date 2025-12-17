import { v4 as uuidv4 } from 'uuid';
import { useChat } from '@ai-sdk/react';
import { Messages } from "../../components/bud/chat/Messages";
import { Metrics, SavedMessage, Session, Usage } from "../../types/chat";
import { useAuth } from '@/app/context/AuthContext';
import { ChangeEvent, useEffect, useMemo, useState, useRef } from 'react';
import { Image, Layout, Tooltip } from "antd";

import { Message } from "ai";
import NavBar from './NavBar';
import HistoryList from './HistoryList';
import ModelInfo from './ModelInfo';
import MessageLoading from './MessageLoading';
import NormalEditor from '@/app/components/bud/components/input/NormalEditor';
import { useChatStore } from '@/app/store/chat';
import SettingsList from './Settings';
import PromptForm from './PromptForm';
import UnstructuredPromptInput from './UnstructuredPromptInput';
import { getPromptConfig } from '@/app/lib/api';
import { useEndPoints } from '@/app/components/bud/hooks/useEndPoint';



const { Header, Footer, Sider, Content } = Layout;

export default function ChatWindow({ chat, isSingleChat }: { chat: Session, isSingleChat: boolean }) {

  const { addMessage, getMessages, updateChat, createChat, disableChat, currentSettingPreset, deleteMessageAfter, getPromptIds, setDeployment, setDeploymentLock } = useChatStore();
  const { apiKey, accessKey } = useAuth();
  const { endpoints, getEndPoints, isReady } = useEndPoints();

  const [toggleLeft, setToggleLeft] = useState<boolean>(false);
  const [toggleRight, setToggleRight] = useState<boolean>(false);
  const [showPromptForm, setShowPromptForm] = useState<boolean>(false);
  const [promptFormSubmitted, setPromptFormSubmitted] = useState<boolean>(false);

  // Prompt configuration state
  const [promptConfig, setPromptConfig] = useState<any>(null);
  const [isStructuredPrompt, setIsStructuredPrompt] = useState<boolean | null>(null);
  const [promptConfigLoading, setPromptConfigLoading] = useState<boolean>(false);
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);
  const [isDeploymentReady, setIsDeploymentReady] = useState<boolean>(false);

  // State to control PromptForm visibility based on postMessage from parent window
  // Initially true if promptIds are present in URL
  const [enablePromptForm, setEnablePromptForm] = useState<boolean>(() => {
    const params = new URLSearchParams(window.location.search);
    const promptIdsParam = params.get('promptIds');
    return !!(promptIdsParam && promptIdsParam.trim().length > 0);
  });

  const promptRef = useRef("");
  const lastMessageRef = useRef<string>("");
  const contentRef = useRef<HTMLDivElement>(null);

  const promptIds = getPromptIds();
  const [promptData, setPromptData] = useState<any>(null);

  const body = useMemo(() => {
    if (!chat) {
      return;
    }
    const params = new URLSearchParams(window.location.search);
    const baseUrl = params.get('base_url');
    const baseBody = {
      model: chat?.selectedDeployment?.name,
      metadata: {
        project_id: chat?.selectedDeployment?.project?.id,
        base_url: baseUrl,
      },
      settings: currentSettingPreset,
    };

    // If we have prompt data for the first message, include it
    if (promptData) {
      return {
        ...baseBody,
        ...promptData,
      };
    }

    return baseBody;
  }, [chat, currentSettingPreset, promptData]);

  // Determine API endpoint based on whether we have promptIds
  const apiEndpoint = useMemo(() => {
    return promptIds.length > 0 ? '/api/prompt-chat' : '/api/chat';
  }, [promptIds]);

  const { messages, input, handleInputChange, handleSubmit, reload, error, stop, status, setMessages, append, setInput } = useChat({
    id: chat.id,
    api: apiEndpoint,
    headers: {
      Authorization: `Bearer ${apiKey ? apiKey : accessKey}`,
    },
    body: body,
    generateId: uuidv4,
    initialMessages: getMessages(chat.id),
    onFinish: (message, { usage, finishReason }) => {
      handleFinish(message, { usage, finishReason });
    },
  });



  useEffect(() => {
    if (messages.length > 0) {
      const currentLastMessage = messages.length > 1 ? messages[messages.length - 2] : messages[messages.length - 1];
      if (currentLastMessage?.id !== lastMessageRef.current) {
        lastMessageRef.current = currentLastMessage.id;
      }
    }
  }, [messages]);

  // Check URL parameter to show form (for testing/demo)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const showForm = params.get('show_form');
    const promptIdsParam = params.get('promptIds');

    // Show form if either show_form=true OR promptIds exist in URL
    if (showForm === 'true' || (promptIdsParam && promptIdsParam.trim().length > 0)) {
      setShowPromptForm(true);
    }
  }, []);

  // Listen for multiple events to trigger refresh when returning to playground
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      // Optional: Verify the origin for security
      // if (event.origin !== 'http://localhost:3000') return;

      // Check if this is the message we're expecting
      if (event.data && event.data.type === 'SET_TYPE_FORM') {
        const typeFormValue = event.data.typeForm;

        // Update state to show/hide PromptForm based on parent message
        setEnablePromptForm(typeFormValue);

        // Trigger refresh of prompt config when switching to playground
        setRefreshTrigger(prev => prev + 1);

        // Also update showPromptForm to reopen the form if typeForm is true
        if (typeFormValue && getPromptIds().length > 0) {
          setShowPromptForm(true);
        } else {
          setShowPromptForm(false);
        }
      }
    };

    // Handler for visibility change (tab switch)
    const handleVisibilityChange = () => {
      if (!document.hidden && getPromptIds().length > 0) {
        setRefreshTrigger(prev => prev + 1);
      }
    };

    // Handler for window focus
    const handleFocus = () => {
      if (getPromptIds().length > 0) {
        setRefreshTrigger(prev => prev + 1);
      }
    };

    // Listen for all events
    window.addEventListener('message', handleMessage);
    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('focus', handleFocus);

    // Cleanup listener on unmount
    return () => {
      window.removeEventListener('message', handleMessage);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('focus', handleFocus);
    };
  }, [getPromptIds]);

  // Fetch prompt configuration to determine if structured or unstructured
  useEffect(() => {
    const fetchPromptConfiguration = async () => {
      const promptIds = getPromptIds();

      if (promptIds.length === 0 || (!apiKey && !accessKey)) {
        // No promptIds - ensure deployment is not locked (clear any persisted lock state)
        setDeploymentLock(chat.id, false);
        setIsDeploymentReady(true);
        return;
      }

      setPromptConfigLoading(true);
      setIsDeploymentReady(false); // Start loading

      try {
        const config = await getPromptConfig(promptIds[0], apiKey || '', accessKey || '');

        if (config && config.data) {
          setPromptConfig(config.data);

          // Determine if structured or unstructured
          let schemaToCheck = config.data.input_schema;

          // Check for $defs structure (JSON schema format)
          if (schemaToCheck && schemaToCheck.$defs) {
            if (schemaToCheck.$defs.Input) {
              schemaToCheck = schemaToCheck.$defs.Input.properties || {};
            } else if (schemaToCheck.$defs.InputSchema) {
              schemaToCheck = schemaToCheck.$defs.InputSchema.properties || {};
            }
          }

          // Is structured if schema has properties
          const hasSchema = schemaToCheck &&
                           typeof schemaToCheck === 'object' &&
                           Object.keys(schemaToCheck).length > 0;

          setIsStructuredPrompt(hasSchema);

          // If unstructured, prepare prompt data for chat body
          if (!hasSchema) {
            const version = config.data?.version ?? config.data?.prompt?.version ?? undefined;
            const promptPayload: any = {
              prompt: {
                id: promptIds[0],
              },
              promptId: promptIds[0],
            };

            if (version !== undefined && version !== null) {
              promptPayload.prompt.version = String(version);
            }

            if (config.data.deployment_name && typeof config.data.deployment_name === 'string') {
              promptPayload.model = config.data.deployment_name;
            }

            setPromptData(promptPayload);
          }
        }
      } catch (error) {
        console.error('[ChatWindow] Error fetching prompt config:', error);
        setIsStructuredPrompt(false); // Default to unstructured on error
      } finally {
        setPromptConfigLoading(false);
      }
    };

    fetchPromptConfiguration();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [getPromptIds, apiKey, accessKey, refreshTrigger]);

  // Fetch endpoints when prompt config has deployment_name (for unstructured prompts)
  // Note: Structured prompts handle this in PromptForm
  useEffect(() => {
    if (isReady && promptConfig?.deployment_name && isStructuredPrompt !== true) {
      getEndPoints({ page: 1, limit: 100 });
    }
  }, [isReady, promptConfig, isStructuredPrompt, getEndPoints]);

  // Auto-select deployment for unstructured prompts
  // Note: Structured prompts handle this in PromptForm
  useEffect(() => {
    const promptIds = getPromptIds();

    if (promptConfig?.deployment_name && endpoints && endpoints.length > 0 && isStructuredPrompt !== true) {
      const deploymentName = promptConfig.deployment_name;
      const currentDeploymentName = chat.selectedDeployment?.name;

      const matchingEndpoint = endpoints.find(
        (ep) => ep.name === deploymentName || ep.id === deploymentName
      );

      if (matchingEndpoint) {
        // Update deployment if it's different from current selection
        if (currentDeploymentName !== matchingEndpoint.name) {
          setDeployment(chat.id, matchingEndpoint);
          setDeploymentLock(chat.id, true);
          setIsDeploymentReady(true); // Deployment updated, ready to show
        } else {
          setIsDeploymentReady(true); // No update needed, ready to show
        }
      } else {
        setIsDeploymentReady(true); // Even if not found, stop loading to avoid infinite spinner
      }
    } else if (promptConfig && isStructuredPrompt === true) {
      // For structured prompts, PromptForm handles deployment, so we're ready
      setIsDeploymentReady(true);
    } else if (!promptConfig?.deployment_name && promptIds.length === 0) {
      // No prompt IDs, no deployment needed, ready to show
      setIsDeploymentReady(true);
    }
  }, [promptConfig, endpoints, isStructuredPrompt, chat, setDeployment, setDeploymentLock, getPromptIds]);



  const createNewChat = () => {
    const newChatPayload = {
      id: uuidv4(),
      name: `New Chat`,
      chat_setting_id: "default",
      created_at: new Date().toISOString(),
      modified_at: new Date().toISOString(),
      total_tokens: 0,
      active: true,
    };
    createChat(newChatPayload);
    disableChat(chat.id);

  }

  const onToggleLeftSidebar = () => {
    setToggleLeft(!toggleLeft);
  };

  const onToggleRightSidebar = () => {
    setToggleRight(!toggleRight);
  };

  const handleChange = (value: ChangeEvent<HTMLInputElement>) => {
    // setSharedChatInput(value);
    handleInputChange(value);
  };

  const handleFinish = (
    message: Message,
    { usage, finishReason }: { usage: Usage; finishReason: string },
  ) => {

    const msgHistory = getMessages(chat.id);
    const updatedChat = {
      ...chat,
      "total_tokens": usage?.totalTokens || 0,
    }
    if (msgHistory.length == 0) {
      updatedChat.name = input;
    }
    updateChat(updatedChat);

    const promptMessage: SavedMessage = {
      id: lastMessageRef.current,
      content: promptRef.current || input,
      createdAt: new Date(),
      role: 'user',
      feedback: "",
    }

    // Extract outputItems from the message's data or annotations
    // The Vercel AI SDK may place custom metadata in different locations
    const messageAny = message as any;
    let outputItems: any[] | undefined;

    // Try to get outputItems from various possible locations
    if (messageAny.data?.outputItems) {
      outputItems = messageAny.data.outputItems;
    } else if (messageAny.experimental_providerMetadata?.outputItems) {
      outputItems = messageAny.experimental_providerMetadata.outputItems;
    } else if (messageAny.annotations) {
      // Check if outputItems is in annotations array
      const annotation = messageAny.annotations.find((a: any) => a?.outputItems);
      if (annotation) {
        outputItems = annotation.outputItems;
      }
    }

    const responseMessage: SavedMessage = {
      ...message,
      feedback: "",
      responseItems: outputItems,  // Store output items for conversation history
    }
    addMessage(chat.id, promptMessage);
    addMessage(chat.id, responseMessage);

    // After the first prompt message completes, update promptData to only include prompt ID context
    // This ensures subsequent messages don't re-send the variables (for structured) or input (for unstructured)
    if (promptData && (promptData.prompt?.variables || promptData.input)) {
      setPromptData({
        prompt: {
          id: promptData.prompt?.id,
          version: promptData.prompt?.version,
        },
        promptId: promptData.promptId,
        model: promptData.model,
      });
    }

    // Use smooth scrolling with scrollTo
    setTimeout(() => {
      if (contentRef.current) {
        contentRef.current.scrollTo({
          top: contentRef.current.scrollHeight,
          behavior: 'smooth'
        });
      }
    }, 100);
  };

  const handleEdit = (content: string, message: Message) => {
    message.content = content;

    promptRef.current = content;
    deleteMessageAfter(chat.id, message.id)

    const list = getMessages(chat.id)

    setMessages(list)
    append(message)
  }

  const handlePromptFormSubmit = (data: any) => {
    // Set the prompt data for the chat body (includes full data with variables for first message)
    setPromptData(data);

    // Mark that the prompt form has been submitted (enables textarea for subsequent messages)
    setPromptFormSubmitted(true);

    // Create a user message with the prompt input
    let userMessage = '';

    if (data.input) {
      // Unstructured input
      userMessage = data.input;
    } else if (data.prompt?.variables) {
      // Structured input - need to unwrap 'content' if it exists
      const variables = data.prompt.variables.content || data.prompt.variables;

      userMessage = Object.entries(variables)
        .map(([k, v]) => {
          // Handle objects and arrays by stringifying them
          if (typeof v === 'object' && v !== null) {
            return `${k}: ${JSON.stringify(v)}`;
          }
          return `${k}: ${v}`;
        })
        .join('\n');
    }

    // Append the message to trigger the chat with prompt context
    append({
      role: 'user',
      content: userMessage,
    });

    // Note: promptData will be updated in handleFinish after the first message completes
    // to only include prompt ID context for subsequent messages

    // Close the form
    setShowPromptForm(false);
  };

  const handleUnstructuredPromptSubmit = (data: any) => {
    // Only set promptData with input for the first message
    // For subsequent messages, promptData already has prompt ID context (set by handleFinish)
    if (messages.length === 0) {
      // First message - include full prompt data with input field
      setPromptData(data);
    }

    // Create user message from the input
    const userMessage = data.input || '';

    // Append the message to trigger the chat with prompt context
    append({
      role: 'user',
      content: userMessage,
    });

    // Clear the input field after sending
    setInput('');

    // Scroll to bottom
    setTimeout(() => {
      if (contentRef.current) {
        contentRef.current.scrollTo({
          top: contentRef.current.scrollHeight,
          behavior: 'smooth'
        });
      }
    }, 100);
  };

  return (
    <Layout className={`chat-container relative ${isSingleChat ? 'single-chat' : ''}`}>
      <Sider
        width="280px"
        className={`leftSider rounded-l-[1rem] border-[1px] border-[#1F1F1F] border-r-[0px] overflow-hidden ml-[-250px] ease-in-out ${toggleLeft ? "visible ml-[0]" : "invisible ml-[-280px]"
          }`}
      // style={{ display: toggleLeft ? "block" : "none" }}
      >
        <div className="leftBg w-full h-full min-w-[200px]">
          <div className="absolute z-0 top-0 left-0 bottom-0 right-0 w-full h-full">
            <div className="absolute top-0 left-0 bottom-0 right-0 opacity-5 bg-gradient-to-b from-[#965CDE] via-[#101010] to-[#965CDE] overflow-y-auto pb-[5rem] pt-[1rem] px-[1rem]"></div>
            {/* <div className="absolute top-0 right-0 w-[200px] h-[200px] blur-xl opacity-7 bg-gradient-to-b from-[#A737EC] to-[#A737EC] overflow-y-auto pb-[5rem] pt-[1rem] px-[1rem]"></div> */}
          </div>
          <div className="relative z-10 flex flex-row justify-between py-[1rem] px-[1.5rem] bg-[#101010] border-b-[1px] border-[#1F1F1F] h-[3.625rem]">
            <div
              className="flex flex-row items-center gap-[.85rem] p-[.5rem] bg-[#101010] cursor-pointer"
              onClick={onToggleLeftSidebar}
            >
              <Image
                preview={false}
                src="icons/minimize.svg"
                alt="bud"
                width={".75rem"}
                height={".75rem"}
              />
              <span className="Lato-Regular text-[#EEE] text-[1rem] font-[400]">
                Chats
              </span>
            </div>
            <button className="group flex items-center flex-row gap-[.4rem] h-[1.375rem] text-[#B3B3B3] text-[300] text-[.625rem] font-[400] p-[.35rem] bg-[#FFFFFF08] rounded-[0.375rem] border-[1px] border-[#1F1F1F] hover:bg-[#965CDE] hover:text-[#FFFFFF] cursor-pointer" onClick={createNewChat}>

              <div className="w-[1rem] h-[1rem] transform scale-[.6] mr-[-.2rem]  flex justify-center items-center cursor-pointer group text-[#B3B3B3] group-hover:text-[#FFFFFF]">
                <Tooltip title="Create a new chat">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="18"
                    height="18"
                    fill="none"
                  >
                    <path
                      fill="currentColor"
                      d="M9 2a.757.757 0 0 0-.757.757v5.486H2.757a.757.757 0 0 0 0 1.514h5.486v5.486a.757.757 0 0 0 1.514 0V9.757h5.486a.757.757 0 0 0 0-1.514H9.757V2.757A.757.757 0 0 0 9 2Z"
                    />
                  </svg>
                </Tooltip>
              </div>
              New Chat
            </button>
          </div>
          <div className="h-[calc(100vh-3.625rem)]">
            <HistoryList chatId={chat.id} />
          </div>
        </div>
      </Sider>
      <Layout
        className={`centerLayout relative border-[1px] border-[#1F1F1F] ${!toggleLeft && "!rounded-l-[0.875rem] overflow-hidden"
          } ${!toggleRight && "!rounded-r-[0.875rem] overflow-hidden"}`}
      >
        <Header>
          {!isDeploymentReady && promptIds.length > 0 ? (
            <div className="topBg text-[#FFF] p-[1rem] flex justify-center items-center h-[3.625rem] relative sticky top-0 z-10 bg-[#101010] border-b-[1px] border-b-[#1F1F1F]">
              <div className="flex items-center gap-2">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                <span className="text-sm text-[#EEEEEE]">Loading deployment configuration...</span>
              </div>
            </div>
          ) : (
            <NavBar
              chatId={chat.id}
              isLeftSidebarOpen={toggleLeft}
              isRightSidebarOpen={toggleRight}
              onToggleLeftSidebar={() => setToggleLeft(!toggleLeft)}
              onToggleRightSidebar={() => setToggleRight(!toggleRight)}
              isSingleChat={isSingleChat}
            />
          )}
        </Header>
        <Content
          className="overflow-hidden overflow-y-auto hide-scrollbar"
          ref={contentRef}
        >

          <div
            className="flex flex-col h-full w-full py-24 mx-auto stretch px-[1rem] max-w-5xl  gap-[1rem]"
            id="chat-container"
          >
            {(chat?.selectedDeployment?.name && messages.length < 1 && (typeof chat?.selectedDeployment?.model === 'object' && chat?.selectedDeployment?.model?.id)) && <ModelInfo deployment={chat?.selectedDeployment} />}
            <Messages chatId={chat.id} messages={messages} reload={reload} onEdit={handleEdit} />
            {(!chat?.selectedDeployment?.name) &&
              (!messages || messages.length === 0) && (
                <div className="h-full flex flex-col items-center justify-center">
                  <div className="mt-[-4.75rem] text-[#EEEEEE] text-center">
                    {/* <div className="relative z-10 Open-Sans mt-[4.75rem] text-[1.575rem]">
                    Hello there 👋
                  </div> */}
                    <Image
                      preview={false}
                      src="images/looking.gif"
                      alt="bud"
                      width={"1150px"} // 750px
                      // height={"150px"}
                      className="relative z-9 mt-[-8.5rem]"
                    />

                    {promptIds.length === 0 && (
                      <div className="relative z-10 Open-Sans text-[1.575rem] mt-[-18.5rem]">
                        Select a model to get started
                      </div>
                    )}
                  </div>
                </div>
              )}
            {(status === "submitted" || status === "streaming") && (
              <MessageLoading />
            )}
            {error && (() => {
              // Parse error message if it's a JSON string
              let errorMessage = error.message || 'An unexpected error occurred';
              let errorDetails = null;

              try {
                const parsed = JSON.parse(errorMessage);
                if (parsed.error) {
                  errorMessage = parsed.error;
                  errorDetails = parsed.details;
                }
              } catch (e) {
                // Not a JSON string, use as is
              }

              return (
                <div className="mt-4 pb-4 border border-[#FF000040] bg-[#FF000010] rounded-lg p-4">
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 mt-0.5">
                      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <circle cx="10" cy="10" r="9" stroke="#FF0000" strokeWidth="1.5"/>
                        <path d="M10 6V11" stroke="#FF0000" strokeWidth="1.5" strokeLinecap="round"/>
                        <circle cx="10" cy="14" r="0.75" fill="#FF0000"/>
                      </svg>
                    </div>
                    <div className="flex-1">
                      <div className="text-[#FF4444] text-[.875rem] font-[500] mb-2">
                        Error Processing Request
                      </div>
                      <div className="text-[#FFAAAA] text-[.75rem] font-[400] leading-relaxed">
                        {errorMessage}
                        {errorDetails && (
                          <span className="block mt-1 text-[#FF8888]">
                            details: "{errorDetails}"
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <button
                    type="button"
                    className="px-[.75rem] py-[.5rem] mt-4 text-[#fff] border border-[#965cde] rounded-md bg-[#965cde] text-[.75rem] font-[500] hover:bg-[#8a4dcc] hover:border-[#8a4dcc] transition-colors focus:outline-none focus:ring-2 focus:ring-[#965cde] focus:ring-offset-2 focus:ring-offset-[#101010] cursor-pointer"
                    onClick={() => reload()}
                  >
                    Try Again
                  </button>
                </div>
              );
            })()}
          </div>
        </Content>
        <Footer className="sticky bottom-0 !px-[2.6875rem]">
          {/* Regular chat - no promptIds */}
          {promptIds.length === 0 && (
              <NormalEditor
                isLoading={status === "submitted" || status === "streaming"}
                error={error}
                disabled={!chat?.selectedDeployment?.name}
                isPromptMode={false}
                stop={stop}
                handleInputChange={handleChange}
                handleSubmit={(e) => {
                  handleSubmit(e);
                  setTimeout(() => {
                    if (contentRef.current) {
                      contentRef.current.scrollTo({
                        top: contentRef.current.scrollHeight,
                        behavior: 'smooth'
                      });
                    }
                  }, 100);
                }}
                input={input}
              />
          )}

          {/* Unstructured prompt - show UnstructuredPromptInput */}
          {/* Show for unstructured prompts OR while loading (when not confirmed as structured) */}
          {promptIds.length > 0 && isStructuredPrompt !== true && (
            <UnstructuredPromptInput
              promptId={promptIds[0]}
              promptVersion={promptConfig?.version}
              deploymentName={promptConfig?.deployment_name}
              onSubmit={handleUnstructuredPromptSubmit}
              status={status}
              stop={stop}
              input={input}
              handleInputChange={handleChange}
              error={error}
              disabled={!chat?.selectedDeployment?.name}
            />
          )}
        </Footer>

        {/* Loading state while determining prompt schema type */}
        {promptIds.length > 0 && promptConfigLoading && (
          <div className="absolute bottom-0 left-0 right-0 z-50 flex items-center justify-center p-4">
            <div className="bg-[#0c0c0d] rounded-lg border border-[#1F1F1F] p-4 shadow-2xl">
              <span className="text-white text-sm">Loading prompt configuration...</span>
            </div>
          </div>
        )}

        {/* Prompt Form - Absolutely positioned at bottom */}
        {/* Show PromptForm only for structured prompts */}
        {enablePromptForm &&
         showPromptForm &&
         getPromptIds().length > 0 &&
         isStructuredPrompt === true && (
          <PromptForm
            promptIds={getPromptIds()}
            chatId={chat.id}
            onSubmit={handlePromptFormSubmit}
            onClose={() => setShowPromptForm(false)}
          />
        )}
      </Layout>
      <Sider
        width="280px"
        className={`rightSider rounded-r-[1rem] border-[1px] border-[#1F1F1F] border-l-[0px] overflow-hidden Open-Sans mr-[-280px] ease-in-out ${toggleRight ? "visible mr-[0]" : "invisible mr-[-280px]"
          }`}
      // style={{ display: toggleRight ? "block" : "none" }}
      >
        <div className="rightBg w-full h-full">
          <div className="absolute z-0 top-0 left-0 bottom-0 right-0 w-full h-full">
            <div className="absolute top-0 left-0 bottom-0 right-0 opacity-2 bg-gradient-to-b from-[#A737EC] via-[#72AFD3] to-[#A737EC] overflow-y-auto pb-[5rem] pt-[1rem] px-[1rem]"></div>
            <div className="absolute top-0 right-0 w-[200px] h-[200px] blur-xl opacity-7 bg-gradient-to-b from-[#A737EC] to-[#A737EC] overflow-y-auto pb-[5rem] pt-[1rem] px-[1rem]"></div>
          </div>
          <div className="relative z-10 flex flex-row pt-[.7rem] pb-[.4rem] px-[.9rem]  border-b-[1px] border-[#1F1F1F] h-[3.625rem] justify-between items-center">
            <div
              className="flex flex-row items-center gap-[.65rem] bg-[#101010] pl-[.15rem] cursor-pointer"
              onClick={onToggleRightSidebar}
            >
              <div className="w-[1rem] h-[1rem] flex justify-center items-center cursor-pointer group text-[#B3B3B3] hover:text-white">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="18"
                  height="18"
                  fill="none"
                >
                  <path
                    fill="currentColor"
                    fillRule="evenodd"
                    d="M15.194 14.373c.539.539-.28 1.356-.818.819l-3.618-3.619v1.995c0 .761-1.157.761-1.157 0v-3.391c0-.32.26-.579.58-.579h3.391c.762 0 .762 1.157 0 1.157h-1.995l3.617 3.618ZM7.241 4.424c0-.761 1.158-.761 1.158 0v3.392a.58.58 0 0 1-.58.579H4.429c-.762 0-.762-1.158 0-1.158h1.995L2.805 3.619c-.538-.538.28-1.356.819-.818L7.24 6.419V4.424Z"
                    clipRule="evenodd"
                  />
                </svg>
              </div>
              <span className="Lato-Regular text-[#EEE] text-[1rem] font-[300]">
                Settings
              </span>
            </div>
          </div>
          <SettingsList chatId={chat.id} />
        </div>
      </Sider>
    </Layout>
  );
}

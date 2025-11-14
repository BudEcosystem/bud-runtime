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
import { resolveChatBaseUrl } from '@/app/lib/gateway';



const { Header, Footer, Sider, Content } = Layout;

export default function ChatWindow({ chat, isSingleChat }: { chat: Session, isSingleChat: boolean }) {

  const { addMessage, getMessages, updateChat, createChat, disableChat, currentSettingPreset, deleteMessageAfter, getPromptIds } = useChatStore();
  const { apiKey, accessKey } = useAuth();

  const [toggleLeft, setToggleLeft] = useState<boolean>(false);
  const [toggleRight, setToggleRight] = useState<boolean>(false);
  const [showPromptForm, setShowPromptForm] = useState<boolean>(false);
  const [promptFormSubmitted, setPromptFormSubmitted] = useState<boolean>(false);

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
    const resolvedBaseUrl = resolveChatBaseUrl(baseUrl);
    const baseBody = {
      model: chat?.selectedDeployment?.name,
      metadata: {
        project_id: chat?.selectedDeployment?.project?.id,
        base_url: baseUrl, //reverting as it's causing issue with chat
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

  const { messages, input, handleInputChange, handleSubmit, reload, error, stop, status, setMessages, append } = useChat({
    id: chat.id,
    api: promptIds.length > 0 ? '/api/prompt-chat' : '/api/chat',
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

  // Listen for postMessage events from parent window to control PromptForm visibility
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      // Optional: Verify the origin for security
      // if (event.origin !== 'http://localhost:3000') return;

      // Check if this is the message we're expecting
      if (event.data && event.data.type === 'SET_TYPE_FORM') {
        const typeFormValue = event.data.typeForm;

        console.log('Received typeForm signal:', typeFormValue);

        // Update state to show/hide PromptForm based on parent message
        setEnablePromptForm(typeFormValue);

        // Also update showPromptForm to reopen the form if typeForm is true
        if (typeFormValue && getPromptIds().length > 0) {
          setShowPromptForm(true);
        } else {
          setShowPromptForm(false);
        }
      }
    };

    // Listen for messages from parent
    window.addEventListener('message', handleMessage);

    // Cleanup listener on unmount
    return () => {
      window.removeEventListener('message', handleMessage);
    };
  }, [getPromptIds]);



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
      "total_tokens": usage.totalTokens,
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
    const responseMessage: SavedMessage = {
      ...message,
      feedback: "",
    }
    addMessage(chat.id, promptMessage);
    addMessage(chat.id, responseMessage);

    // After the first prompt message completes, update promptData to only include prompt ID context
    // This ensures subsequent messages don't re-send the variables
    if (promptData && promptData.prompt?.variables) {
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
    console.log('handleEdit - setting prompt to:', message);
    message.content = content;

    promptRef.current = content;
    deleteMessageAfter(chat.id, message.id)

    const list = getMessages(chat.id)

    setMessages(list)
    append(message)
  }

  const handlePromptFormSubmit = (data: any) => {
    console.log('Prompt form submitted with data:', data);

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
        .map(([k, v]) => `${k}: ${v}`)
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
          <NavBar
            chatId={chat.id}
            isLeftSidebarOpen={toggleLeft}
            isRightSidebarOpen={toggleRight}
            onToggleLeftSidebar={() => setToggleLeft(!toggleLeft)}
            onToggleRightSidebar={() => setToggleRight(!toggleRight)}
            isSingleChat={isSingleChat}
          />
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

                    <div className="relative z-10 Open-Sans text-[1.575rem] mt-[-18.5rem]">
                      Select a model to get started
                    </div>
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
          {promptIds.length === 0 && (
            <NormalEditor
              isLoading={status === "submitted" || status === "streaming"}
              error={error}
              disabled={
                promptIds.length > 0
                  ? !promptFormSubmitted
                  : !chat?.selectedDeployment?.name
              }
              isPromptMode={promptIds.length > 0}
              stop={stop}
              handleInputChange={handleChange}
              handleSubmit={(e) => {
                // setSubmitInput(e);
                handleSubmit(e);

                // Use smooth scrolling with scrollTo
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
        </Footer>

        {/* Prompt Form - Absolutely positioned at bottom */}
        {enablePromptForm && showPromptForm && getPromptIds().length > 0 && (
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

import { Image, Layout } from "antd";
import { useCallback, useContext, useEffect, useMemo, useState } from "react";
import RootContext from "../context/RootContext";
import ChatContext from "../context/ChatContext";
import NavBar from "./bud/components/navigation/NavBar";
import { HistoryMessages, Messages } from "./bud/chat/Messages";
import MessageLoading from "./bud/chat/MessageLoading";
import { Message, useChat } from "@ai-sdk/react";
import { useEndPoints } from "./bud/hooks/useEndPoint";
import { NEW_SESSION, Usage, useMessages } from "./bud/hooks/useMessages";
import HistoryList, { ActiveSession } from "./bud/chat/HistoryList";
import SettingsList from "./bud/chat/SettingsList";
import NormalEditor from "./bud/components/input/NormalEditor";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
const { Header, Footer, Sider, Content } = Layout;

export function Chat() {
  const [lastMessage, setLastMessage] = useState<string>("");
  const [toggleLeft, setToggleLeft] = useState<boolean>(false);
  const [toggleRight, setToggleRight] = useState<boolean>(false);
  const { getEndPoints } = useEndPoints();

  const onToggleLeftSidebar = () => {
    setToggleLeft(!toggleLeft);
  };

  const onToggleRightSidebar = () => {
    setToggleRight(!toggleRight);
  };

  const { sessions, token } = useContext(RootContext);
  const { chat, messages: historyMessages } = useContext(ChatContext);
  const { createMessage } = useMessages();

  const handleFinish = useCallback(
    async (
      message: Message,
      response: {
        usage: Usage;
        finishReason: string;
      }
    ) => {
      const { usage, finishReason } = response;
      console.log("Finish", message, usage, finishReason);
      if (!chat?.selectedDeployment) return;
      await createMessage(
        {
          deployment_id: chat?.selectedDeployment?.id,
          e2e_latency: 0,
          is_cache: false,
          chat_session_id: chat?.id === NEW_SESSION ? undefined : chat?.id,
          prompt: lastMessage,
          response: {
            message,
            usage,
          },
          output_tokens: usage.completionTokens,
          input_tokens: usage.promptTokens,
          token_per_sec: 0,
          total_tokens: usage.totalTokens,
          tpot: 0,
          ttft: 0,
          request_id: chat?.selectedDeployment?.id,
        },
        chat.id
      );
      setLastMessage("");
    },
    [chat, createMessage, lastMessage]
  );

  const body = useMemo(() => {
    if (!chat) {
      return;
    }

    return {
      // model: 'gpt-4o',
      model: chat.selectedDeployment?.name,
      metadata: {
        project_id: chat?.selectedDeployment?.project.id,
      },
      settings: chat?.chat_setting,
    };
  }, [chat, chat?.selectedDeployment, JSON.stringify(chat?.chat_setting)]);

  const {
    error,
    input,
    status,
    handleInputChange,
    handleSubmit,
    messages,
    reload,
    stop,
  } = useChat({
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
    },
    body,
    onFinish(message, { usage, finishReason }) {
      handleFinish(message, { usage, finishReason });
      document.getElementById("chat-container")?.scrollIntoView({
        behavior: "smooth",
        block: "end",
        inline: "nearest",
      });
    },
    onError: (error) => {
      console.error("An error occurred:", error);
      document.getElementById("chat-container")?.scrollIntoView({
        behavior: "smooth",
        block: "end",
        inline: "nearest",
      });
    },
    onResponse: (response) => {},
  });

  useEffect(() => {
    if (input !== "") {
      setLastMessage(input);
    }
  }, [input]);

  const handleChange = (value: string) => {
    console.log(`selected ${value}`);
  };

  useEffect(() => {
    if (chat) {
      getEndPoints({ page: 1, limit: 10 });
    }
  }, [toggleLeft, toggleRight]);

  console.log(`historyMessages`, historyMessages);
  console.log(`messages`, messages);

  return (
    <Layout className="chat-container ">
      <Sider
        width="280px"
        className={`leftSider rounded-l-[1rem] border-[1px] border-[#1F1F1F] border-r-[0px] overflow-hidden ml-[-250px] ease-in-out ${
          toggleLeft ? "visible ml-[0]" : "invisible ml-[-280px]"
        }`}
        // style={{ display: toggleLeft ? "block" : "none" }}
      >
        <div className="leftBg w-full h-full min-w-[200px]">
          <div className="flex flex-row py-[1rem] px-[1.5rem] bg-[#101010] border-b-[1px] border-[#1F1F1F] h-[3.625rem]">
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
          </div>
          <div className="h-[calc(100vh-3.625rem)]">
            <HistoryList data={sessions} />
          </div>
        </div>
      </Sider>
      <Layout
        className={`centerLayout border-[1px] border-[#1F1F1F] ${
          !toggleLeft && "!rounded-l-[0.875rem] overflow-hidden"
        } ${!toggleRight && "!rounded-r-[0.875rem] overflow-hidden"}`}
      >
        {/* <Layout className="border-[1px] border-[#1F1F1F] border-l-0 border-r-0"> */}
        <Header>
          <NavBar
            isLeftSidebarOpen={toggleLeft}
            isRightSidebarOpen={toggleRight}
            onToggleLeftSidebar={() => setToggleLeft(!toggleLeft)}
            onToggleRightSidebar={() => setToggleRight(!toggleRight)}
          />
        </Header>
        <Content className="overflow-hidden overflow-y-auto hide-scrollbar">
          <div
            className="flex flex-col w-full py-24 mx-auto stretch px-[.5rem] max-w-2xl  gap-[1rem]"
            id="chat-container"
          >
            <HistoryMessages messages={historyMessages} />
            <Messages messages={messages} />
            {(!historyMessages || historyMessages.length === 0) &&
              (!messages || messages.length === 0) && (
                <div className="mt-4 text-[#EEEEEE] text-center">
                  <Image
                    preview={false}
                    src="icons/load.png"
                    alt="bud"
                    width={"330px"}
                    height={"130px"}
                  />
                  <div className="Open-Sans mt-[.75rem] text-[1.375rem]">
                    Hello there 👋
                  </div>
                  <div className="Open-Sans text-[1.375rem]">
                    Select a model to get started
                  </div>
                </div>
              )}
            {(status === "submitted" || status === "streaming") && (
              <MessageLoading />
            )}
            {error && (
              <div className="mt-4">
                <div
                  className="text-[#FF0000] text-[.75rem] font-[400] 
                
                "
                >
                  {error.message}
                </div>
                <button
                  type="button"
                  className="px-[.5rem] p-[.25rem] mt-4 text-[#fff] border border-[#757575] rounded-sm bg-[#965cde] text-[.75rem] font-[400] hover:bg-[#965cde] hover:text-[
                  #fff] focus:outline-none cursor-pointer"
                  onClick={() => reload()}
                >
                  Retry
                </button>
              </div>
            )}
          </div>
        </Content>
        <Footer className="sticky bottom-0 !px-[2.6875rem]">
          <NormalEditor
            isLoading={status === "submitted" || status === "streaming"}
            error={error}
            disabled={!chat?.selectedDeployment?.id}
            stop={stop}
            handleInputChange={handleInputChange}
            handleSubmit={(e) => {
              handleSubmit(e);
              document.getElementById("chat-container")?.scrollIntoView({
                behavior: "smooth",
                block: "end",
                inline: "nearest",
              });
            }}
            input={input}
          />
        </Footer>
      </Layout>
      <Sider
        width="280px"
        className={`rightSider rounded-r-[1rem] border-[1px] border-[#1F1F1F] border-l-[0px] overflow-hidden Open-Sans mr-[-280px] ease-in-out ${
          toggleRight ? "visible mr-[0]" : "invisible mr-[-280px]"
        }`}
        // style={{ display: toggleRight ? "block" : "none" }}
      >
        <div className="rightBg w-full h-full">
          <div className="flex flex-row pt-[.7rem] pb-[.4rem] px-[.9rem] bg-[#101010] border-b-[1px] border-[#1F1F1F] h-[3.625rem] justify-between items-center">
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
            <div>
              <button className="group flex items-center flex-row gap-[.4rem] h-[1.375rem] text-[#B3B3B3] text-[300] text-[.625rem] font-[400] p-[.35rem] bg-[#FFFFFF08] rounded-[0.375rem] border-[1px] border-[#1F1F1F] hover:bg-[#965CDE] hover:text-[#FFFFFF]">
                Save as Preset
                <div className="w-[1rem] h-[1rem] flex justify-center items-center cursor-pointer group text-[#B3B3B3] group-hover:text-white">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="14"
                    height="14"
                    fill="none"
                  >
                    <path
                      fill="currentColor"
                      d="m11.93 3.836-2.158-2.55a1.13 1.13 0 0 0-.858-.411H2.928A1.252 1.252 0 0 0 1.75 2.188v9.624a1.252 1.252 0 0 0 1.178 1.313h8.144a1.252 1.252 0 0 0 1.178-1.313V4.739a1.396 1.396 0 0 0-.32-.902ZM8.75 12.25h-3.5V9.188c0-.242.195-.438.437-.438h2.625a.438.438 0 0 1 .438.438v3.062Zm2.625-.437c0 .232-.141.437-.303.437H9.625V9.188c0-.725-.588-1.313-1.313-1.313H5.687c-.724 0-1.312.588-1.312 1.313v3.062H2.928c-.162 0-.303-.204-.303-.437V2.188c0-.233.14-.438.303-.438h5.986a.255.255 0 0 1 .19.102l2.157 2.55a.525.525 0 0 1 .114.336v7.075Zm-1.75-7a.438.438 0 0 1-.438.437H4.812a.437.437 0 1 1 0-.875h4.375a.438.438 0 0 1 .438.438Z"
                    />
                  </svg>
                </div>
              </button>
            </div>
          </div>
          <SettingsList data={[1, 2, 3]} />
        </div>
      </Sider>
    </Layout>
  );
}

function ChatWithStore(props: { chat: ActiveSession }) {
  const { localMode } = useContext(RootContext);
  const { getSessionMessages } = useMessages();
  const [messages, setMessages] = useState<any[]>([]);
  const [loadedChatID, setLoadedChatID] = useState<string | undefined>(
    undefined
  );

  useEffect(() => {
    const init = async () => {
      const id = props.chat?.id;
      if (localMode) {
        console.log("Loading from local storage");
        const existing = localStorage.getItem(id);
        if (existing) {
          const data = JSON.parse(existing);
          if (loadedChatID !== id) {
            setLoadedChatID(id);
            setMessages(data);
          }
        }
      } else {
        if (id !== NEW_SESSION) {
          if (loadedChatID !== id) {
            const result = await getSessionMessages(id);
            console.log("Loading from server");
            setLoadedChatID(id);
            setMessages(result);
          }
          return;
        }
      }
    };
    init();
  }, [props.chat]);

  return (
    <>
      <ResizablePanel defaultSize={100}>
        <ChatContext.Provider
          value={{
            chat: props.chat,
            messages: messages
            // ?.filter((m) => m.prompt !== NEW_SESSION)
            ,
            setMessages,
          }}
        >
          <Chat />
        </ChatContext.Provider>
      </ResizablePanel>
      <ResizableHandle />
    </>
  );
}

export default function ChatWindowWithStore() {
  const { chats } = useContext(RootContext);

  return (
    <div
      className="!grid w-full h-full transition-all duration-300"
      style={
        chats?.length > 0
          ? {}
          : {
              position: "absolute",
              top: 0,
              left: -5000,
              zIndex: -1,
            }
      }
    >
      <ResizablePanelGroup direction="horizontal" className="h-full w-full">
        {chats.map((chat, index) => (
          <ChatWithStore key={index} chat={chat} />
        ))}
      </ResizablePanelGroup>
    </div>
  );
}

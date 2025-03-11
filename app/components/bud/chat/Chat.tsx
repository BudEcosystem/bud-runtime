import { Message, useChat } from "@ai-sdk/react";
import { Image } from "antd";
import { Messages, HistoryMessages } from "./Messages";
import { Layout } from "antd";
import HistoryList from "./HistoryList";
import SettingsList from "./SettingsList";
import { useContext, useEffect, useMemo, useState } from "react";
import NormalEditor from "../components/input/NormalEditor";
import MessageLoading from "./MessageLoading";
import NavBar from "../components/navigation/NavBar";
import { copyCodeApiBaseUrl, OpenAiKey } from "../environment";
import ChatContext, { Endpoint } from "@/app/context/ChatContext";
import { useEndPoints } from "../hooks/useEndPoint";
import { useMessages } from "../hooks/useMessages";
import RootContext from "@/app/context/RootContext";
import { ChatType } from "@/app/page";

const { Header, Footer, Sider, Content } = Layout;

function Chat() {
  const { chat, messages: historyMessages } = useContext(ChatContext);
  const { createMessage } = useMessages();
  const [toggleLeft, setToggleLeft] = useState<boolean>(false);
  const [toggleRight, setToggleRight] = useState<boolean>(false);
  const [isHovered, setIsHovered] = useState<boolean>(false);


  const handleFinish = (message: Message, { usage, finishReason }: any) => {
    // console.log("Message", message);
    // console.log("FinishReason", finishReason);
    createMessage({
      chat_session_id: "1234",
      deployment_id: "1234",
      e2e_latency: usage.e2e_latency,
      input_tokens: usage.input_tokens,
      is_cache: false,
      output_tokens: usage.output_tokens,
      prompt: message.content,
      response: message.parts as any[],
      token_per_sec: usage.token_per_sec,
      total_tokens: usage.total_tokens,
      tpot: usage.tpot,
      ttft: usage.ttft,
    });
    // console.log("Usage", usage);
  };

  const body = useMemo(() => {
    if (!chat) {
      return;
    }

    return {
      // model: 'gpt-4o',
      model: chat.selectedDeployment?.name,
      max_tokens: chat?.settings.limit_response_length ? chat?.settings.sequence_length : undefined,
      temperature: chat?.settings.temperature,
      metadata: {
        project_id: `${chat?.selectedDeployment?.project.id}`
      }
      // top_k: chat?.settings.tool_k_sampling,
      // top_p: chat?.settings.top_p_sampling,
      // frequency_penalty: chat?.settings.repeat_penalty,
      // presence_penalty: chat?.settings.min_p_sampling,
      // stop: chat?.settings.stop_strings,
      // context: chat?.settings.context_overflow,
    };
  }, [chat, chat?.settings.limit_response_length, chat?.settings.sequence_length, chat?.settings.temperature, chat?.settings.tool_k_sampling, chat?.settings.top_p_sampling, chat?.settings.repeat_penalty, chat?.settings.min_p_sampling, chat?.settings.stop_strings, chat?.settings.context_overflow, chat?.selectedDeployment?.model]);

  const { error, input, isLoading, handleInputChange, handleSubmit, messages, reload, stop, } = useChat(
    chat?.apiKey ? {
      // uncomment this line to use the copy code api provided by the backend
      api: `${copyCodeApiBaseUrl}`,
      headers: {
        "api-key": `${chat?.apiKey}`,
        authorization: `Bearer ${localStorage.getItem("access_token") ? localStorage.getItem("access_token") : `${chat?.token}`}`,
        // "Project-Id": `${chat?.selectedDeployment?.project.id}`
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Transfer-Encoding": "chunked",
        "Connection": "keep-alive",
      },
      body,
      onFinish(message, { usage, finishReason }) {
        console.log("message", message);
        console.log("Usage", usage);
        console.log("FinishReason", finishReason);
        handleFinish(message, { usage, finishReason });
      },
      onError: error => {
        console.error('An error occurred:', error);
      },
      onResponse: response => {
        console.log('Received HTTP response from server:', response);
      },
    }
      : {
        onFinish(message, { usage, finishReason }) {
          console.log("message", message);
          console.log("Usage", usage);
          console.log("FinishReason", finishReason);
          handleFinish(message, { usage, finishReason });
        },
        onError: error => {
          console.error('An error occurred:', error);
        },
        onResponse: response => {
          console.log('Received HTTP response from server:', response);
        },
      }
  );
  const handleChange = (value: string) => {
    console.log(`selected ${value}`);
  };

  const { getEndPoints } = useEndPoints();

  useEffect(() => {
    console.log("getEndPoints");
    if (chat) {
      getEndPoints({ page: 1, limit: 10 });
    }
  }, []);

  return (
    <Layout className="chat-container ">
      <Sider
        width="20.8%"
        className={`leftSider rounded-l-[1rem] border-[1px] border-[#1F1F1F] border-r-[0px] overflow-hidden ml-[-20.8%] ease-in-out ${toggleLeft ? "visible ml-[0]" : "invisible ml-[-20.8%]"}`}
      // style={{ display: toggleLeft ? "block" : "none" }}
      >
        <div className="leftBg w-full h-full">
          <div className="flex flex-row py-[1rem] px-[1.5rem] bg-[#101010] border-b-[1px] border-[#1F1F1F] h-[3.625rem]">
            <div
              className="flex flex-row items-center gap-[.85rem] p-[.5rem] bg-[#101010] cursor-pointer"
              onClick={() => setToggleLeft(!toggleLeft)}
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
            <HistoryList data={[1, 2, 3]} />
          </div>
        </div>
      </Sider>
      <Layout className={`centerLayout border-[1px] border-[#1F1F1F] ${!toggleLeft && '!rounded-l-[0.875rem] overflow-hidden'} ${!toggleRight && '!rounded-r-[0.875rem] overflow-hidden'}`}>
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
          <div className="flex flex-col w-full py-24 mx-auto stretch px-[.5rem] max-w-2xl ">
            <HistoryMessages messages={historyMessages} />
            <Messages messages={messages} />
            {
              !error &&
              historyMessages.length === 0 &&
              messages.length === 0 && (
                <div className="mt-4 text-[#EEEEEE] text-center">
                  <Image
                    preview={false}
                    src="icons/load.png"
                    alt="bud"
                    width={"330px"}
                    height={"130px"}
                  />
                  <div className="mt-[.75rem] text-[1.375rem]">
                    Hello there 👋
                  </div>
                  <div className="text-[1.375rem]">
                    Select a model to get started
                  </div>
                </div>
              )}
            {isLoading && <MessageLoading />}
            {error && (
              <div className="mt-4">
                <div className="text-red-500">An error occurred.</div>
                <button
                  type="button"
                  className="px-4 py-2 mt-4 text-blue-500 border border-blue-500 rounded-md"
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
            isLoading={isLoading}
            error={error}
            stop={stop}
            handleInputChange={handleInputChange}
            handleSubmit={(e) => {
              createMessage({
                chat_session_id: chat?.chatSessionId || "",
                deployment_id: "1234",
                e2e_latency: 0,
                input_tokens: 0,
                is_cache: false,
                output_tokens: 0,
                prompt: input,
                response: [],
                token_per_sec: 0,
                total_tokens: 0,
                tpot: 0,
                ttft: 0,
              });
              handleSubmit(e);
            }}
            input={input}
          />
        </Footer>
      </Layout>
      <Sider
        width="20.8%"
        className={`rightSider rounded-r-[1rem] border-[1px] border-[#1F1F1F] border-l-[0px] overflow-hidden Open-Sans mr-[-20.8%] ease-in-out ${toggleRight ? "visible mr-[0]" : "invisible mr-[-20.8%]"}`}
      // style={{ display: toggleRight ? "block" : "none" }}
      >
        <div className="rightBg w-full h-full">
          <div className="flex flex-row pt-[.7rem] pb-[.4rem] px-[.9rem] bg-[#101010] border-b-[1px] border-[#1F1F1F] h-[3.625rem] justify-between items-center">
            <div
              className="flex flex-row items-center gap-[.65rem] bg-[#101010] pl-[.15rem] cursor-pointer"
              onClick={() => setToggleRight(!toggleRight)}
            >
              <div className="w-[1rem] h-[1rem] flex justify-center items-center cursor-pointer group text-[#B3B3B3] hover:text-white">
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none"><path fill="currentColor" fill-rule="evenodd" d="M15.194 14.373c.539.539-.28 1.356-.818.819l-3.618-3.619v1.995c0 .761-1.157.761-1.157 0v-3.391c0-.32.26-.579.58-.579h3.391c.762 0 .762 1.157 0 1.157h-1.995l3.617 3.618ZM7.241 4.424c0-.761 1.158-.761 1.158 0v3.392a.58.58 0 0 1-.58.579H4.429c-.762 0-.762-1.158 0-1.158h1.995L2.805 3.619c-.538-.538.28-1.356.819-.818L7.24 6.419V4.424Z" clip-rule="evenodd" /></svg>
              </div>
              <span className="Lato-Regular text-[#EEE] text-[1rem] font-[300]">
                Settings
              </span>
            </div>
            <div>
              <button
                className="group flex items-center flex-row gap-[.4rem] h-[1.375rem] text-[#B3B3B3] text-[300] text-[.625rem] font-[400] p-[.35rem] bg-[#FFFFFF08] rounded-[0.375rem] border-[1px] border-[#1F1F1F] hover:bg-[#965CDE] hover:text-[#FFFFFF]"
                onMouseEnter={() => setIsHovered(true)}
                onMouseLeave={() => setIsHovered(false)}
              >
                Save as Preset
                <div className="w-[1rem] h-[1rem] flex justify-center items-center cursor-pointer group text-[#B3B3B3] group-hover:text-white">
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="none"><path fill="currentColor" d="m11.93 3.836-2.158-2.55a1.13 1.13 0 0 0-.858-.411H2.928A1.252 1.252 0 0 0 1.75 2.188v9.624a1.252 1.252 0 0 0 1.178 1.313h8.144a1.252 1.252 0 0 0 1.178-1.313V4.739a1.396 1.396 0 0 0-.32-.902ZM8.75 12.25h-3.5V9.188c0-.242.195-.438.437-.438h2.625a.438.438 0 0 1 .438.438v3.062Zm2.625-.437c0 .232-.141.437-.303.437H9.625V9.188c0-.725-.588-1.313-1.313-1.313H5.687c-.724 0-1.312.588-1.312 1.313v3.062H2.928c-.162 0-.303-.204-.303-.437V2.188c0-.233.14-.438.303-.438h5.986a.255.255 0 0 1 .19.102l2.157 2.55a.525.525 0 0 1 .114.336v7.075Zm-1.75-7a.438.438 0 0 1-.438.437H4.812a.437.437 0 1 1 0-.875h4.375a.438.438 0 0 1 .438.438Z" /></svg>
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

function ChatWithStore(props: { chat: ChatType }) {
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [messages, setMessages] = useState<any[]>([]);

  return (
    <ChatContext.Provider
      value={{
        chat: props.chat,
        token: "",
        endpoints,
        setEndpoints,
        messages,
        setMessages,
      }}
    >
      <Chat />
    </ChatContext.Provider>
  );
}


export default function ChatWindowWithStore() {
  const { chats, createChat } = useContext(RootContext);

  useEffect(() => {
    console.log("localStorage.getItemaccess_token", localStorage.getItem("access_token"));
  }, []);

  return (
    <Layout
      className="!grid w-full h-full"
      style={{
        gridTemplateColumns: chats?.map(() => "1fr").join(" "),
        gridGap: "1rem",
      }}
    >
      {chats.map((chat, index) => (
        <ChatWithStore key={index} chat={chat} />
      ))}
      {chats.length === 0 && (
        <div className="flex justify-center items-center w-full h-full">
          <button
            onClick={createChat}
            type="button"
            className="px-4 py-2 text-blue-500 border border-blue-500 rounded-md z-50"
          >
            Create Chat
          </button>
        </div>
      )}
    </Layout>
  );
}

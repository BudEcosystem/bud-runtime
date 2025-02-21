"use client";

import { useChat } from "@ai-sdk/react";
import { UIMessage } from "@ai-sdk/ui-utils";
import NavBar from "./bud/components/navigation/NavBar";
import { Image } from "antd";
import Editor from "./bud/chat/Editor";
import Messages from "./bud/chat/Messages";
import { Flex, Layout } from "antd";
import HistoryList from "./bud/chat/HistoryList";
import SettingsList from "./bud/chat/SettingsList";

const { Header, Footer, Sider, Content } = Layout;

function Loading() {
  return (
    <div className="mt-4  flex flex-row  gap-[1rem]">
      <div>
        <Image
          src="icons/budrect.svg"
          alt="bud"
          width={"1.25rem"}
          height={"1.25rem"}
        />
      </div>
      <div className="flex justify-start items-center gap-[.25rem]">
        <svg
          width="6"
          height="6"
          viewBox="0 0 6 6"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="animate-bounce delay-75"
        >
          <circle cx="3" cy="3" r="3" fill="#1F1F1F" />
        </svg>
        <svg
          width="6"
          height="6"
          viewBox="0 0 6 6"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="animate-bounce delay-150"
        >
          <circle cx="3" cy="3" r="3" fill="#1F1F1F" />
        </svg>

        <svg
          width="6"
          height="6"
          viewBox="0 0 6 6"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="animate-bounce delay-300"
        >
          <circle cx="3" cy="3" r="3" fill="#1F1F1F" />
        </svg>
      </div>
      {/* <button
    type="button"
    className="px-4 py-2 mt-4 text-blue-500 border border-blue-500 rounded-md"
    onClick={stop}
  >
    Stop
  </button> */}
    </div>
  );
}

export default function Chat() {
  const {
    error,
    input,
    isLoading,
    handleInputChange,
    handleSubmit,
    messages,
    reload,
    stop,
  } = useChat({
    onFinish(message, { usage, finishReason }) {
      console.log("Usage", usage);
      console.log("FinishReason", finishReason);
    },
  });

  return (
    <Layout className="chat-container ">
      <Sider width="25%" className="rounded-l-[1rem]">
        <div className="flex flex-row py-[1rem] px-[1.5rem] bg-[#101010] border-b-[1px] border-[#1F1F1F] h-[58px]">
          <div className="flex flex-row items-center gap-[1rem] p-[.5rem] bg-[#101010]">
            <Image
              src="icons/minimize.svg"
              alt="bud"
              width={".75rem"}
              height={".75rem"}
            />
            <span className="text-[#EEE] text-[1rem] font-[400]">Chats</span>
          </div>
        </div>
        <HistoryList data={[1, 2, 3]} />
      </Sider>
      <Layout className="border-[1px] border-[#1F1F1F] rounded-[1rem]">
        <Header>
          <NavBar />
        </Header>
        <Content>
          <div className="flex flex-col w-full py-24 mx-auto stretch px-[.5rem] max-w-2xl">
            <Messages messages={messages} />
            {isLoading && <Loading />}
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
        <Footer>
          <Editor
            handleInputChange={handleInputChange}
            handleSubmit={handleSubmit}
            input={input}
            // isLoading={isLoading}
            // error={error}
          />
        </Footer>
      </Layout>
      <Sider width="25%" className="rounded-r-[1rem]">
        <div className="flex flex-row py-[1rem] px-[1.5rem] bg-[#101010] border-b-[1px] border-[#1F1F1F] h-[58px] justify-between">
          <div className="flex flex-row items-center gap-[1rem] p-[.5rem] bg-[#101010]">
            <Image
              src="icons/minimize.svg"
              alt="bud"
              width={".75rem"}
              height={".75rem"}
            />
            <span className="text-[#EEE] text-[1rem] font-[400]">Settings</span>
          </div>
          <div>
            <button className="flex items-center flex-row gap-[.5rem] text-[#EEE] text-[.625rem] font-[400] p-[.5rem] bg-[#FFFFFF08] rounded-[0.5rem]">
              Save as Preset
              <Image
                src="icons/save.svg"
                alt="bud"
                width={".75rem"}
                height={".75rem"}
              />
            </button>
          </div>
        </div>
        <SettingsList data={[1, 2, 3]} />
      </Sider>
    </Layout>
  );
}

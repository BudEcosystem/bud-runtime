"use client";

import { useChat } from "@ai-sdk/react";
import NavBar from "./bud/components/navigation/NavBar";
import { Image } from "antd";
import Editor from "./bud/chat/Editor";
import Messages from "./bud/chat/Messages";
import { Layout } from "antd";
import HistoryList from "./bud/chat/HistoryList";
import SettingsList from "./bud/chat/SettingsList";
import { useState } from "react";
import NormalEditor from "./bud/chat/NormalEditor";

const { Header, Footer, Sider, Content } = Layout;

function Loading() {
  return (
    <div className="mt-4  flex flex-row  gap-[1rem]">
      <div>
        <Image
          preview={false}
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
  const [toggleLeft, setToggleLeft] = useState<boolean>(false);
  const [toggleRight, setToggleRight] = useState<boolean>(false);
  const [isHovered, setIsHovered] = useState<boolean>(false);
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
  const handleChange = (value: string) => {
    console.log(`selected ${value}`);
  };
  return (
    <Layout className="chat-container">
      <Sider
        width="20.8%"
        className="rounded-l-[1rem]"
        style={{ display: toggleLeft ? "block" : "none" }}
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
            {/* <div className="px-[.9rem] py-[3.1rem]">
            <div className="custom-select">
              <Select
                getPopupContainer={(trigger) =>
                  (trigger.parentNode as HTMLElement) || document.body
                }
                suffixIcon={<DownOutlined style={{ color: '#EEEEEE' }} />}
                className=" !text-[1rem] text-[#EEEEEE] font-[400]"
                defaultValue="Presets"
                style={{ width: '100%' }}
                onChange={handleChange}
                options={[
                  { value: 'Presets', label: 'Presets' },
                  { value: 'lucy', label: 'Lucy' },
                  { value: 'Yiminghe', label: 'yiminghe' },
                  { value: 'disabled', label: 'Disabled', disabled: true },
                ]}
              />
            </div>
          </div> */}
          </div>
        </div>
      </Sider>
      <Layout className="border-[1px] border-[#1F1F1F] border-l-0 border-r-0">
        <Header>
          <NavBar
            isLeftSidebarOpen={toggleLeft}
            isRightSidebarOpen={toggleRight}
            onToggleLeftSidebar={() => setToggleLeft(!toggleLeft)}
            onToggleRightSidebar={() => setToggleRight(!toggleRight)}
          />
        </Header>
        <Content className="overflow-hidden overflow-y-auto">
          <div className="flex flex-col w-full py-24 mx-auto stretch px-[.5rem] max-w-2xl ">
            <Messages messages={messages} />
            {!isLoading && !error && messages.length === 0 && (
              <div className="mt-4 text-[#EEEEEE] text-center">
                <Image
                  preview={false}
                  src="icons/load.svg"
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
        <Footer className="sticky bottom-0 !px-[2.6875rem]">
          <NormalEditor
            isLoading={isLoading}
            error={error}
            handleInputChange={handleInputChange}
            handleSubmit={handleSubmit}
            input={input}
            // isLoading={isLoading}
            // error={error}
          />
        </Footer>
      </Layout>
      <Sider
        width="20.8%"
        className="rounded-r-[1rem] Open-Sans"
        style={{ display: toggleRight ? "block" : "none" }}
      >
        <div className="rightBg w-full h-full">
          <div className="flex flex-row pt-[.7rem] pb-[.4rem] px-[.9rem] bg-[#101010] border-b-[1px] border-[#1F1F1F] h-[3.625rem] justify-between items-center">
            <div
              className="flex flex-row items-center gap-[.65rem] bg-[#101010] pl-[.15rem] cursor-pointer"
              onClick={() => setToggleRight(!toggleRight)}
            >
              <Image
                preview={false}
                src="icons/minimize.svg"
                alt="bud"
                width={".85rem"}
                height={".85rem"}
              />
              <span className="Lato-Regular text-[#EEE] text-[1rem] font-[300]">
                Settings
              </span>
            </div>
            <div>
              <button
                className="flex items-center flex-row gap-[.4rem] h-[1.375rem] text-[#B3B3B3] text-[300] text-[.625rem] font-[400] p-[.35rem] bg-[#FFFFFF08] rounded-[0.375rem] border-[1px] border-[#1F1F1F] hover:bg-[#965CDE] hover:text-[#FFFFFF]"
                onMouseEnter={() => setIsHovered(true)}
                onMouseLeave={() => setIsHovered(false)}
              >
                Save as Preset
                <Image
                  preview={false}
                  className="text-[#B3B3B3]"
                  src={isHovered ? "icons/save-white.png" : "icons/save.png"}
                  alt="bud"
                  width={"0.875rem"}
                  height={"0.875rem"}
                />
              </button>
            </div>
          </div>
          <SettingsList data={[1, 2, 3]} />
        </div>
      </Sider>
    </Layout>
  );
}

"use client";

import { useChat } from "@ai-sdk/react";
import { UIMessage } from "@ai-sdk/ui-utils";
import NavBar from "./bud/components/navigation/NavBar";
import { Image } from "antd";
import Markdown from 'react-markdown'
import Editor from "./Editor";

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

function Message(props: UIMessage) {
  return (
    <div
      className="text-[#FFFFFF] relative mb-[1.5rem] text-[.75rem]  rounded-[.625rem] py-[.75rem] "
      style={{
        right: props.role === "user" ? 0 : 0,
      }}
    >
      {props.role === "user" ? (
        <div className="flex justify-end">
          <UserMessage {...props} />
        </div>
      ) : (
        <div className="flex justify-start ">
          <AIMessage {...props} />
        </div>
      )}
    </div>
  );
}

function UserMessage(props: UIMessage) {
  return (
    <div className="flex flex-row items-center gap-[.5rem]">
      <div className="flex items-center justify-end gap-[.5rem] ">
        <button>
          <Image
            preview={false}
            src="icons/copy.svg"
            alt="bud"
            width={"0.625rem"}
            height={"0.625rem"}
          />
        </button>
        <button>
          <Image
            preview={false}
            src="icons/edit.svg"
            alt="bud"
            width={"0.625rem"}
            height={"0.625rem"}
          />
        </button>
      </div>
      <span className="message-text user-message relative  p-[.5rem] rounded-[0.5rem] border-[#1F1F1F4D] border-[1px] text-[#FFF] text-right">
        <div className="blur-[0.5rem] absolute top-0 left-0 right-0 bottom-0 bg-[#FFFFFF05] rounded-[0.5rem]" />
        {props.content}
      </span>
    </div>
  );
}

function AIMessage(props: UIMessage) {
  return (
    <div className="flex flex-row items-center gap-[.5rem]">
      <div className="mr-[.5rem]">
        <Image
          preview={false}
          src="icons/budrect.svg"
          alt="bud"
          width={"1.5rem"}
          height={"1.5rem"}
        />
      </div>
      <Markdown className="message-text ai-message">{props.content}</Markdown>
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
    <main className="chat-container ">
      <NavBar />
      <div className="flex flex-col w-full py-24 mx-auto stretch px-[.5rem] max-w-2xl">
        {messages.map((m) => (
          <Message {...m} key={m.id} />
        ))}
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
      <Editor 
              handleInputChange={handleInputChange}
              handleSubmit={handleSubmit}
              input={input}
              // isLoading={isLoading}
              // error={error}
            />
        
      </div>
    </main>
  );
}

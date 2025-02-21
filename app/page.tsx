"use client";

import { useChat } from "@ai-sdk/react";
import { UIMessage } from "@ai-sdk/ui-utils";
import NavBar from "./bud/components/navigation/NavBar";
import { Image } from "antd";
import Editor from "./bud/chat/Editor";
import Messages from "./bud/chat/Messages";

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
    <main className="chat-container ">
      <NavBar />
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

import { UIMessage } from "@ai-sdk/ui-utils";
import { Image } from "antd";
import React from "react";
import Markdown from "react-markdown";
import { PostMessage } from "../hooks/useMessages";

function Message(props: { content: string; role: string }) {
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

function UserMessage(props: { content: string; role: string }) {
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

function AIMessage(props: { content: string; role: string }) {
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

interface MessagesProps {
  messages: UIMessage[];
}

interface HistoryMessagesProps {
  messages: PostMessage[];
}

export function Messages({ messages }: MessagesProps) {
  return messages.map((m) => <Message {...m} key={m.id} />);
}

// export function HistoryMessages({ messages }: HistoryMessagesProps) {
//   return messages.map((m, index) => (
//     <>
//       <Message
//         content={m.response?.[0]?.text || m.prompt }
//         role={m.response?.[0]?.text ? "ai" : "user"}
//         key={m.chat_session_id + index}
//       />
//     </>
//   ));
// }
export function HistoryMessages({ messages }: HistoryMessagesProps) {
  return (
    <>
      {messages.map((m, index) => (
        <Message
          content={m.response?.[0]?.text || m.prompt}
          role={m.response?.[0]?.text ? "ai" : "user"}
          key={m.chat_session_id ? `${m.chat_session_id}-${index}` : index}
        />
      ))}
    </>
  );
}

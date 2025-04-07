import { Image } from "antd";
import React, { useEffect, useState } from "react";
import Markdown from "react-markdown";
import { Metrics, PostMessage } from "../hooks/useMessages";
import { format } from "date-fns";
import { UIMessage } from "ai";
import { MemoizedMarkdown } from "./MenorizedMarkdown";

type MessageProps = {
  content: string;
  role: "system" | "user" | "assistant" | "data" | "ai";
  data: PostMessage;
};

function Message(props: MessageProps & { reload: () => void, onEdit: () => void }) {
  return (
    <div
      className="text-[#FFFFFF] relative text-[.75rem]  rounded-[.625rem] "
      style={{
        right: props.role === "user" ? 0 : 0,
      }}
    >
      {props.role === "user" ? (
        <div className="flex justify-end">
          <UserMessage {...props} onEdit={props.onEdit} />
        </div>
      ) : (
        <div className="flex justify-start ">
          <AIMessage {...props} reload={props.reload} />
        </div>
      )}
    </div>
  );
}

function UserMessage(props: MessageProps & { onEdit: () => void }) {
  return (
    <div className="flex flex-row items-center gap-[.5rem]">
      <div className="flex items-center justify-end gap-[.5rem] ">
        <button>
          <div className="w-[1rem] h-[1rem] flex justify-center items-center cursor-pointer group text-[#B3B3B3] hover:text-[#FFFFFF]">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="12"
              height="15"
              fill="none"
            >
              <path
                fill="currentColor"
                fillRule="evenodd"
                d="M.8 9.498a1.2 1.2 0 0 0 1.2 1.2h1.2v1.595a1.2 1.2 0 0 0 1.2 1.2H10a1.2 1.2 0 0 0 1.2-1.2v-6.8a1.2 1.2 0 0 0-1.2-1.2H4.4a1.2 1.2 0 0 0-1.2 1.2v4.405H2a.4.4 0 0 1-.4-.4v-6.8c0-.22.18-.4.4-.4h5.6c.221 0 .4.18.4.4v1.534h.8V2.698a1.2 1.2 0 0 0-1.2-1.2H2a1.2 1.2 0 0 0-1.2 1.2v6.8ZM4 5.493c0-.221.18-.4.4-.4H10c.221 0 .4.179.4.4v6.8a.4.4 0 0 1-.4.4H4.4a.4.4 0 0 1-.4-.4v-6.8Z"
                clipRule="evenodd"
              />
            </svg>
          </div>
        </button>
        <button>
          <div className="w-[1rem] h-[1rem] flex justify-center items-center cursor-pointer group text-[#B3B3B3] hover:text-[#FFFFFF]" onClick={()=> props.onEdit()}>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="12"
              height="11"
              fill="none"
            >
              <path
                fill="currentColor"
                d="M11.176 2.708 8.792.324a.548.548 0 0 0-.774 0L1.002 7.34a.54.54 0 0 0-.16.348l-.18 2.564a.547.547 0 0 0 .544.585h.039l2.565-.18a.54.54 0 0 0 .347-.159l7.016-7.016a.54.54 0 0 0 .003-.774ZM3.531 9.58l-1.734.123.123-1.734 4.775-4.774 1.61 1.61L3.531 9.58Zm5.55-5.548-1.61-1.61.938-.939 1.61 1.61-.937.939Z"
              />
            </svg>
          </div>
        </button>
      </div>
      {/* #0d0d0d */}
      <span className="message-text user-message relative  p-[.8rem] py-[1rem] rounded-[0.5rem] border-[#1F1F1F4D] border-[1px] text-[#EEEEEE] font-[400] text-[.75rem] text-right Open-Sans z-[2]">
        <div className="absolute z-[1] w-[100%] h-[100%] top-0 left-0 right-0 bottom-0 !bg-[#0d0d0d] rounded-[0.5rem] border-[1px] border-[#1F1F1F]" />
        <div className="relative z-[2]">{props.content}</div>
      </span>
    </div>
  );
}

function AIMessage(props: MessageProps & { reload: () => void }) {
  const [metrics, setMetrics] = useState<Metrics | undefined>(undefined);
  
  useEffect(() => {
    if(!props.data?.annotations  ){
      return;
    }
    const metrics = props.data.annotations?.find((item: any) => item.type == 'metrics')
    if(metrics){
      setMetrics(metrics as Metrics);
    }
  }, [props]);

  return (
    <div className="flex flex-row items-top gap-[.5rem]">
      <div className="mr-[.5rem] mt-[.2rem]">
        <Image
          preview={false}
          src="icons/budrect.svg"
          alt="bud"
          width={"1.5rem"}
          height={"1.5rem"}
        />
      </div>
      <div className="message-text ai-message">
        <MemoizedMarkdown content={props.content} id={props.data.id} />
        {metrics && <div className="w-[100%] h-[40px] tempClass mt-[1rem] rounded-[6px] z-[10] relative overflow-hiden">
          <div className="bg !bg-[#101010] rounded-[6px]"></div>
          <div className="fg flex justify-between items-center pl-[.6rem] pr-[.5rem] gap-[.5rem]">
            <div className="flex justify-start items-center gap-x-[.7rem]">
              <div className="text-[#B3B3B3] text-[.625rem] font-[400]">
                Tokens/sec : {metrics?.throughput}
              </div>
              <div className="text-[#B3B3B3] text-[.625rem] font-[400]">
                TTFT : {metrics?.ttft} ms
              </div>
              <div className="text-[#B3B3B3] text-[.625rem] font-[400]">
                ITL : {metrics?.itl} ms
              </div>
              <div className="text-[#B3B3B3] text-[.625rem] font-[400]">
                E2E Latency : {metrics?.e2e_latency} s
              </div>
            </div>
            <div className="flex justify-end items-center gap-x-[.4rem]">
              <div className="w-[1rem] h-[1rem] flex justify-center items-center cursor-pointer group text-[#B3B3B3] hover:text-[#FFFFFF]">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="12"
                  height="15"
                  fill="none"
                >
                  <path
                    fill="currentColor"
                    fillRule="evenodd"
                    d="M.8 9.498a1.2 1.2 0 0 0 1.2 1.2h1.2v1.595a1.2 1.2 0 0 0 1.2 1.2H10a1.2 1.2 0 0 0 1.2-1.2v-6.8a1.2 1.2 0 0 0-1.2-1.2H4.4a1.2 1.2 0 0 0-1.2 1.2v4.405H2a.4.4 0 0 1-.4-.4v-6.8c0-.22.18-.4.4-.4h5.6c.221 0 .4.18.4.4v1.534h.8V2.698a1.2 1.2 0 0 0-1.2-1.2H2a1.2 1.2 0 0 0-1.2 1.2v6.8ZM4 5.493c0-.221.18-.4.4-.4H10c.221 0 .4.179.4.4v6.8a.4.4 0 0 1-.4.4H4.4a.4.4 0 0 1-.4-.4v-6.8Z"
                    clipRule="evenodd"
                  />
                </svg>
              </div>
              <div className="w-[1rem] h-[1rem] flex justify-center items-center cursor-pointer group text-[#B3B3B3] hover:text-[#FFFFFF]">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="14"
                  height="14"
                  fill="none"
                >
                  <path
                    fill="currentColor"
                    fillRule="evenodd"
                    d="M6.563 1.167a.583.583 0 0 0-.54.364l-1.75 4.303H2.918a1.75 1.75 0 0 0-1.75 1.75v3.5c0 .966.783 1.75 1.75 1.75h7.193a1.75 1.75 0 0 0 1.722-1.438l.742-4.083a1.75 1.75 0 0 0-1.722-2.063H9.334V3.493l-.001-.01v-.027a2.31 2.31 0 0 0-.045-.349 2.433 2.433 0 0 0-.317-.791c-.387-.62-1.128-1.15-2.409-1.15Zm-2.48 10.5V7H2.917a.583.583 0 0 0-.582.584v3.5c0 .322.26.583.582.583h1.168Zm1.167 0h4.86a.583.583 0 0 0 .574-.48l.742-4.082a.583.583 0 0 0-.574-.688H9.333A1.167 1.167 0 0 1 8.166 5.25V3.504l-.001-.027a1.28 1.28 0 0 0-.183-.542c-.135-.216-.408-.496-1.036-.578L5.25 6.53v5.136Z"
                    clipRule="evenodd"
                  />
                </svg>
              </div>
              <div className="w-[1rem] h-[1rem] flex justify-center items-center cursor-pointer group text-[#B3B3B3] hover:text-[#FFFFFF]">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="14"
                  height="14"
                  fill="none"
                >
                  <path
                    fill="currentColor"
                    fillRule="evenodd"
                    d="M7.438 12.833a.583.583 0 0 0 .54-.364l1.748-4.303h1.357a1.75 1.75 0 0 0 1.75-1.75v-3.5a1.75 1.75 0 0 0-1.75-1.75H3.89a1.75 1.75 0 0 0-1.722 1.438l-.742 4.083A1.75 1.75 0 0 0 3.148 8.75h1.518v1.757l.001.01v.027l.006.083a2.433 2.433 0 0 0 .356 1.057c.387.62 1.128 1.15 2.409 1.15Zm2.478-10.5V7h1.168a.583.583 0 0 0 .582-.584v-3.5a.583.583 0 0 0-.582-.583H9.916Zm-1.166 0H3.89a.583.583 0 0 0-.574.48l-.742 4.082a.583.583 0 0 0 .574.688h1.519c.644 0 1.167.523 1.167 1.167v1.746l.001.027a1.28 1.28 0 0 0 .183.543c.135.215.408.495 1.036.577L8.75 7.47V2.333Z"
                    clipRule="evenodd"
                  />
                </svg>
              </div>
              {/* <div className="w-[1rem] h-[1rem] flex justify-center items-center cursor-pointer group text-[#B3B3B3] hover:text-[#FFFFFF]">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="14"
                  height="14"
                  fill="none"
                >
                  <path
                    fill="currentColor"
                    fillRule="evenodd"
                    d="M8.42 1.225c.202.096.33.3.33.525v10.5a.582.582 0 0 1-.948.456l-2.597-2.078a.58.58 0 0 0-.364-.128H2.917a1.75 1.75 0 0 1-1.75-1.75v-3.5c0-.966.783-1.75 1.75-1.75H4.84a.58.58 0 0 0 .364-.128l2.597-2.078a.583.583 0 0 1 .617-.07Zm-.836 1.739-1.65 1.32c-.31.247-.696.383-1.093.383H2.917a.583.583 0 0 0-.583.583v3.5c0 .322.26.584.583.584H4.84c.397 0 .783.135 1.093.383l1.65 1.32V2.964Z"
                    clipRule="evenodd"
                  />
                  <path
                    fill="#B3B3B3"
                    d="M9.916 7c0-.566-.184-1.054-.451-1.381a.583.583 0 0 1 .903-.738c.452.553.716 1.308.716 2.119 0 .811-.264 1.566-.716 2.12a.583.583 0 1 1-.903-.74c.267-.326.451-.814.451-1.38Z"
                  />
                  <path
                    fill="#B3B3B3"
                    d="M10.632 3.87c.626.766 1.034 1.875 1.034 3.13s-.408 2.364-1.034 3.13a.583.583 0 0 0 .903.74c.811-.994 1.299-2.37 1.299-3.87s-.488-2.876-1.299-3.87a.583.583 0 0 0-.903.739Z"
                  />
                </svg>
              </div>
              <div className="w-[1rem] h-[1rem] flex justify-center items-center cursor-pointer group text-[#B3B3B3] hover:text-[#FFFFFF]">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="14"
                  height="14"
                  fill="none"
                >
                  <path
                    fill="currentColor"
                    fillRule="evenodd"
                    d="M8.42 1.225c.202.096.33.3.33.525v10.5a.582.582 0 0 1-.948.456l-2.597-2.078a.58.58 0 0 0-.364-.128H2.917a1.75 1.75 0 0 1-1.75-1.75v-3.5c0-.966.783-1.75 1.75-1.75H4.84a.58.58 0 0 0 .364-.128l2.597-2.078a.583.583 0 0 1 .617-.07Zm-.836 1.739-1.65 1.32c-.31.247-.696.383-1.093.383H2.917a.583.583 0 0 0-.583.583v3.5c0 .322.26.584.583.584H4.84c.397 0 .783.135 1.093.383l1.65 1.32V2.964Z"
                    clipRule="evenodd"
                  />
                  <path
                    fill="#B3B3B3"
                    d="M9.916 7c0-.566-.184-1.054-.451-1.381a.583.583 0 0 1 .903-.738c.452.553.716 1.308.716 2.119 0 .811-.264 1.566-.716 2.12a.583.583 0 1 1-.903-.74c.267-.326.451-.814.451-1.38Z"
                  />
                  <path
                    fill="#B3B3B3"
                    d="M10.632 3.87c.626.766 1.034 1.875 1.034 3.13s-.408 2.364-1.034 3.13a.583.583 0 0 0 .903.74c.811-.994 1.299-2.37 1.299-3.87s-.488-2.876-1.299-3.87a.583.583 0 0 0-.903.739Z"
                  />
                </svg>
              </div> */}
              <div className="w-[1rem] h-[1rem] flex justify-center items-center cursor-pointer group text-[#B3B3B3] hover:text-[#FFFFFF]" onClick={()=> props.reload()}>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="14"
                  height="14"
                  fill="none"
                >
                  <path
                    fill="currentColor"
                    d="M9.8 2.156a5.58 5.58 0 0 0-4.256-.56 5.617 5.617 0 0 0-2.422 1.357l-1.33-.77.476 1.793.112.364.084.322.322-.084.378-.098 1.778-.476-.896-.518a4.51 4.51 0 0 1 1.765-.91 4.53 4.53 0 0 1 3.485.462 4.6 4.6 0 0 1 2.255 4.648l.994.14c.32-2.296-.743-4.522-2.745-5.67ZM11.62 9.66l-.084-.322-.322.084-.365.098-1.777.476.895.518a4.539 4.539 0 0 1-1.764.924 4.554 4.554 0 0 1-3.499-.462C3.066 10.024 2.17 8.204 2.45 6.328l-.994-.14c-.322 2.282.742 4.508 2.744 5.656a5.517 5.517 0 0 0 4.241.56 5.617 5.617 0 0 0 2.423-1.358l1.315.77-.475-1.792-.084-.364Z"
                  />
                </svg>
              </div>
              <div className="pl-[.75rem] text-[#757575] text-[.75rem] font-[400]">
                {props.data?.response?.message?.createdAt &&
                  format(
                    new Date(props.data.response.message.createdAt),
                    "HH:mm"
                  )}
              </div>
            </div>
          </div>
        </div>}
      </div>
    </div>
  );
}

interface MessagesProps {
  messages: UIMessage[];
  reload: () => void;
  onEdit: (message: UIMessage) => void;
}


export function Messages({ messages, reload, onEdit }: MessagesProps) {
  return (
    <div className="flex flex-col gap-[1rem]">
      {messages.map((m) => (
        <Message {...m} key={m.id} content={m.content} role={m.role} data={m as any} reload={reload} onEdit={()=> onEdit(m)} />
      ))}
    </div>
  );
}

import { Image } from "antd";
import { RectangleEllipsisIcon, StopCircleIcon } from "lucide-react";
import React, { useState } from "react";

export interface EditorProps {
  input: string;
  handleSubmit: (e: React.FormEvent) => void;
  isLoading: boolean;
  error?: Error;
  disabled?: boolean;
  stop?: () => void;
  handleInputChange: (e: any) => void;
  isPromptMode?: boolean; // Indicates if we're using prompt IDs (don't show "Select deployment" message)
}

function NormalEditor({
  input,
  handleSubmit,
  isLoading,
  disabled,
  stop,
  error,
  handleInputChange,
  isPromptMode = false,
}: EditorProps) {
  const [toggleFormat, setToggleFormat] = useState<boolean>(false);
  const [isHovered, setIsHovered] = useState<boolean>(false);

  return (
    <div className="flex flex-row w-full justify-center items-center mb-[.55rem] "
    style={{
      cursor: disabled ? "not-allowed" : "auto",
    }}
    >
      <form
        className="chat-message-form w-full  flex items-center justify-center  border-t-2 hover:border-[#333333] rounded-[0.625rem] bg-[#101010] relative z-10 overflow-hidden max-w-5xl px-[1rem]"
        onSubmit={handleSubmit}
      >
        <div className="blur-[0.5rem] absolute top-0 left-0 right-0 bottom-0 bg-[#FFFFFF03] rounded-[0.5rem] " />
        <div className="flex flex-row items-center w-full pb-[2rem] pt-[.5rem]"   style={{
      cursor: disabled ? "not-allowed" : "auto",
    }}>
          <Image
            src="icons/budrect.svg"
            alt="attachment"
            width={"1.25rem"}
            className="absolute left-0 top-[-0.75rem] m-auto"
            preview={false}
            height={"1.25rem"}
          />
          <textarea
             style={{
              cursor: disabled ? "not-allowed" : "auto",
            }}
            className=" w-full  p-2 border border-gray-300 rounded shadow-xl placeholder-[#757575] placeholder-[.625rem] text-[1rem] bg-transparent  border-[#e5e5e5] outline-none border-none text-[#FFFFFF] z-10 !shadow-none"
            value={input}
            rows={2}
            placeholder={
              disabled && !isPromptMode
                ? "Select a deployment to chat"
                : "Type a message and press Enter to send"
            }
            onChange={(e) => handleInputChange(e)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e);
              }
            }}
            disabled={isLoading || disabled}
          />
        </div>
        <div className="absolute flex justify-between items-end w-full bottom-0 left-0 right-0 pr-[.85rem] pl-[.25rem]">
          <div className="toolbar pb-[.65rem]">
            <button
              type="button"
              onClick={() => {}}
              className={"toolbar-item spaced " + (false ? "active" : "")}
              aria-label="Format Attachment"
            >
              <i className="format attachment" />
            </button>
            {/* <button
              type="button"
              onClick={() => {}}
              className={"toolbar-item spaced " + (false ? "active" : "")}
              aria-label="Format smiley"
            >
              <i className="format smiley" />
            </button> */}
          </div>
          <div className="pb-[.95rem]">
            <button
              className="Open-Sans cursor-pointer text-[400] z-[999] text-[.75rem] text-[#EEEEEE] border-[#757575] border-[1px] rounded-[6px] p-[.2rem] hover:bg-[#1F1F1F4D] hover:text-[#FFFFFF]  flex items-center gap-[.5rem] px-[.8rem] py-[.15rem] bg-[#1F1F1F] hover:bg-[#965CDE] hover:text-[#FFFFFF] z-[99] absolute right-[.5rem] bottom-[1rem] "
              style={{
                cursor: disabled ? "not-allowed" : "pointer",
              }}
              type="submit"
              onMouseEnter={() => setIsHovered(true)}
              onMouseLeave={() => setIsHovered(false)}
              onClick={(e) => {
                if (isLoading) {
                  e.preventDefault();
                  stop && stop();
                }
              }}
            >
              {isLoading ? "Stop" : "Send"}
              {isLoading ? (
                <div className="w-[1.25rem] h-[1.25rem]">
                  <StopCircleIcon width={20} height={20} />
                </div>
              ) : (
                <div className="w-[1.25rem] h-[1.25rem]">
                  <Image
                    src={isHovered ? "icons/send-white.png" : "icons/send.png"}
                    alt="send"
                    preview={false}
                  />
                </div>
              )}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}

export default NormalEditor;

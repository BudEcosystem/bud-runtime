import { Image } from "antd";
import { RectangleEllipsisIcon, StopCircleIcon } from "lucide-react";
import React, { useState } from "react";

interface NormalEditorProps {
  input: string;
  handleSubmit: (e: React.FormEvent) => void;
  isLoading: boolean;
  error?: Error;
  stop?: () => void;
  handleInputChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
}

function NormalEditor({
  input,
  handleSubmit,
  isLoading,
  stop,
  error,
  handleInputChange,
}: NormalEditorProps) {
  const [isHovered, setIsHovered] = useState<boolean>(false);

  return (
    <div className="flex flex-row w-full justify-center items-center mb-[.55rem] ">
      <form
        className="chat-message-form   w-full  flex items-center justify-center  border-t-2 rounded-[0.625rem] bg-[#101010] relative z-10 overflow-hidden max-w-2xl px-[1rem]"
        onSubmit={handleSubmit}
      >
        <div className="blur-[0.5rem] absolute top-0 left-0 right-0 bottom-0 bg-[#FFFFFF03] rounded-[0.5rem] " />
        <Image
          src="icons/bud.svg"
          alt="attachment"
          width={"1.25rem"}
          preview={false}
          height={"1.25rem"}
        />
        <input
          className=" w-full  p-2 border border-gray-300 rounded shadow-xl placeholder-[#757575] placeholder-[.625rem] text-[.75rem] bg-transparent  border-[#e5e5e5] outline-none border-none text-[#757575] z-10"
          value={input}
          placeholder="Type a message and press Enter to send"
          onChange={handleInputChange}
          onSubmit={handleSubmit}
          disabled={isLoading || error != null}
        />
        <button
          className="Open-Sans text-[400] z-[999] text-[.75rem] text-[#EEEEEE] border-[#757575] border-[1px] rounded-[6px] p-[.2rem] hover:bg-[#1F1F1F4D] hover:text-[#FFFFFF]  flex items-center gap-[.5rem] px-[.8rem] py-[.15rem] bg-[#1F1F1F] hover:bg-[#965CDE] hover:text-[#FFFFFF]"
          type="submit"
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
          onClick={(e)=>{
            if(isLoading){
              e.preventDefault();
              stop && stop();
            }
          }}
        >
          {isLoading ? "Stop" : "Send"}
          {isLoading ?
          <div className="w-[1.25rem] h-[1.25rem]">
            <StopCircleIcon width={20} height={20} />
          </div>
          :
          <div className="w-[1.25rem] h-[1.25rem]">
            <Image
              src={isHovered ? "icons/send-white.png" : "icons/send.png"}
              alt="send"
              preview={false}
            />
          </div>}
        </button>
      </form>
    </div>
  );
}

export default NormalEditor;

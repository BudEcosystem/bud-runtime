import { Image } from "antd";
import React from "react";

interface NormalEditorProps {
  input: string;
  handleSubmit: (e: React.FormEvent) => void;
  isLoading: boolean;
  error?: Error;
  handleInputChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
}

function NormalEditor({
  input,
  handleSubmit,
  isLoading,
  error,
  handleInputChange,
}: NormalEditorProps) {
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
        <button type="submit" className="ml-2 flex items-center">
          <Image src="icons/send.svg" alt="send" preview={false} />
        </button>
      </form>
    </div>
  );
}

export default NormalEditor;

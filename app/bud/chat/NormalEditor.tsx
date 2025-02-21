import { Image } from "antd";
import React from "react";

interface NormalEditorProps {
  input: string;
  setInput: (input: string) => void;
  handleSubmit: (e: React.FormEvent) => void;
  isLoading: boolean;
  error: string | null;
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
    <div className="flex flex-row w-full fixed left-0 bottom-[10rem] justify-center items-center mb-[.5rem] bg-[#101010]">
      <form
        onSubmit={handleSubmit}
        className="chat-message-form max-w-2xl  w-full  flex items-center justify-center p-[1rem] border-t-2 h-[62px] rounded-[0.625rem] relative z-10"
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
          className=" w-full  p-2 border border-gray-300 rounded shadow-xl placeholder-[#757575] placeholder-[.75rem] text-[.875rem] bg-transparent  border-[#e5e5e5] outline-none border-none text-[#757575] z-10"
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

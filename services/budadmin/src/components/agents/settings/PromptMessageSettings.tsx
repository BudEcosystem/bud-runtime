'use client';

import React from 'react';
import { Image } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { Text_14_400_757575 } from "../../ui/text";
import { TextAreaInput } from "../../ui/input";

interface PromptMessageSettingsProps {
  sessionId: string;
  promptMessages: string;
  onPromptMessagesChange: (value: string) => void;
}

export const PromptMessageSettings: React.FC<PromptMessageSettingsProps> = ({
  sessionId,
  promptMessages,
  onPromptMessagesChange
}) => {
  const [isOpen, setIsOpen] = React.useState(true);

  return (
    <div className="flex flex-col w-full px-[.4rem] py-[1rem] border-b border-[#1F1F1F]">
      <div
        className="flex flex-row items-center gap-[1rem] px-[.3rem] justify-between cursor-pointer"
        onClick={() => setIsOpen(!isOpen)}
      >
        <div className="flex flex-row items-center gap-[.4rem] py-[.5rem]">
          <Text_14_400_757575>Prompt Messages</Text_14_400_757575>
        </div>
        <div className="flex flex-row items-center">
          <Image
            src="/icons/customArrow.png"
            className={`w-[.75rem] transform transition-transform rotate-0 ${isOpen ? "" : "rotate-180"}`}
            preview={false}
            alt="chevron"
          />
        </div>
      </div>
      {isOpen && (
        <div className="space-y-2 px-[.5rem] pt-2">
          <div className="border border-[#2A2A2A] rounded-md p-2 min-h-[100px]">
            <TextAreaInput
              className="!w-full !max-w-full !border-0 !p-0 !min-h-[4rem] !text-[#EEEEEE] !text-xs !placeholder-[#606060]"
              value={promptMessages}
              onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => {
                onPromptMessagesChange(e.target.value);
              }}
              placeholder="Add Prompt Messages..."
            />
            <div className="flex justify-between items-center mt-2 pt-2 border-t border-[#1A1A1A]">
              <span className="text-[#606060] text-xs">53%</span>
              <button className="text-[#606060] hover:text-[#965CDE] text-xs">
                <PlusOutlined className="mr-1" />
                Add
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

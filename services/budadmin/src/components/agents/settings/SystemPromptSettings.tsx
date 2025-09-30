'use client';

import React from 'react';
import { Image } from "antd";
import { Text_14_400_757575 } from "../../ui/text";
import { TextAreaInput } from "../../ui/input";

interface SystemPromptSettingsProps {
  sessionId: string;
  systemPrompt: string;
  onSystemPromptChange: (value: string) => void;
}

export const SystemPromptSettings: React.FC<SystemPromptSettingsProps> = ({
  sessionId,
  systemPrompt,
  onSystemPromptChange
}) => {
  const [isOpen, setIsOpen] = React.useState(true);

  return (
    <div className="flex flex-col w-full px-[.4rem] py-[1rem] border-b border-[#1F1F1F]">
      <div
        className="flex flex-row items-center gap-[1rem] px-[.3rem] justify-between cursor-pointer"
        onClick={() => setIsOpen(!isOpen)}
      >
        <div className="flex flex-row items-center gap-[.4rem] py-[.5rem]">
          <Text_14_400_757575>System Prompt</Text_14_400_757575>
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
          <TextAreaInput
            className="!w-full !max-w-full !min-h-[4rem] !text-[#EEEEEE] !text-xs !placeholder-[#606060] !border-[#2A2A2A] hover:!border-[#965CDE] focus:!border-[#965CDE]"
            value={systemPrompt}
            onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => {
              onSystemPromptChange(e.target.value);
            }}
            placeholder="Enter System Prompt..."
          />
        </div>
      )}
    </div>
  );
};

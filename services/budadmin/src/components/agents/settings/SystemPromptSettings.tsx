'use client';

import React from 'react';
import { Checkbox } from "antd";
import { Text_16_400_EEEEEE, Text_10_400_757575 } from "../../ui/text";
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
  const [allowMultipleCalls, setAllowMultipleCalls] = React.useState(false);

  return (
    <div className="flex flex-col w-full px-[1rem] py-[1.5rem] bg-[#0A0A0A] border-b border-[#1F1F1F]">
      {/* Header */}
      <div className="mb-4">
        <Text_16_400_EEEEEE>System Prompt</Text_16_400_EEEEEE>
      </div>

      {/* Text Area */}
      <div className="mb-4">
        <TextAreaInput
          className="!w-full !max-w-full !min-h-[7.5rem] text-[#EEEEEE] text-sm placeholder:text-[#757575] bg-[#0F0F0F] border-[#2A2A2A] hover:border-[#965CDE] focus:border-[#965CDE] !rounded-lg"
          value={systemPrompt}
          onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => {
            onSystemPromptChange(e.target.value);
          }}
          placeholder="Enter system prompt..."
          style={{ color: '#EEEEEE' }}
        />
      </div>

      {/* Checkbox Section */}
      <div className="space-y-2">
        <Checkbox
          checked={allowMultipleCalls}
          onChange={(e) => setAllowMultipleCalls(e.target.checked)}
          className="text-[#EEEEEE]"
        >
          <Text_16_400_EEEEEE className="text-[#EEEEEE] text-sm">Allow multiple calls</Text_16_400_EEEEEE>
        </Checkbox>
        <div className="pl-6">
          <Text_10_400_757575 className='leading-[140%]'>
            This option allows hghcgjhkjhknj bhjvjfg hcvn mhbj,bnvnhfccnv hvbnvhcn
          </Text_10_400_757575>
        </div>
      </div>
    </div>
  );
};

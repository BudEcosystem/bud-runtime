'use client';

import React from 'react';
import { Checkbox } from "antd";
import { PrimaryButton } from "../../ui/bud/form/Buttons";
import { Text_16_400_EEEEEE, Text_10_400_757575, Text_12_400_EEEEEE } from "../../ui/text";

interface SystemPromptSettingsProps {
  sessionId: string;
  systemPrompt: string;
  onSystemPromptChange: (value: string) => void;
  onSaveSystemPrompt?: () => void;
  isSavingSystemPrompt?: boolean;
}

export const SystemPromptSettings: React.FC<SystemPromptSettingsProps> = ({
  sessionId,
  systemPrompt,
  onSystemPromptChange,
  onSaveSystemPrompt,
  isSavingSystemPrompt
}) => {
  const [allowMultipleCalls, setAllowMultipleCalls] = React.useState(false);

  return (
    <div className="flex flex-col justify-between h-full w-full">
      <div className='flex flex-col py-[1rem]'>
        {/* Header */}
        <div className='flex flex-col gap-[1rem] border-b border-[#1F1F1F] pb-[1rem] px-[.9375rem]'>
          <div className="flex flex-row items-center gap-[.2rem] px-[.3rem] justify-between">
            <div className="flex flex-row items-center py-[.5rem]">
              <Text_16_400_EEEEEE>System Prompt</Text_16_400_EEEEEE>
            </div>
          </div>
        </div>

        {/* Text Area */}
        <div className="mb-4 mt-[1rem] px-[.5rem] border-b border-[#1F1F1F] pb-[1rem]">
          <textarea
            className="w-full max-w-full min-h-[7.5rem] text-[#EEEEEE] text-sm bg-[#0F0F0F] border border-[#2A2A2A] hover:border-[#965CDE] focus:border-[#965CDE] rounded-lg p-3 outline-none resize-y placeholder:text-[#757575] placeholder:opacity-100 placeholder:text-[.75rem]"
            value={systemPrompt}
            onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => {
              onSystemPromptChange(e.target.value);
            }}
            placeholder="Enter system prompt..."
            style={{
              color: '#EEEEEE',
            }}
          />
        </div>

        {/* Checkbox Section */}
        <div className="space-y-2 px-[.5rem]">
          <div className='bg-[#FFFFFF08] px-[.725rem] py-[1rem] rounded-[.5rem]'>
            <Checkbox
              checked={allowMultipleCalls}
              onChange={(e) => setAllowMultipleCalls(e.target.checked)}
              className="AntCheckbox text-[#EEEEEE]"
            >
              <Text_12_400_EEEEEE className="text-[#EEEEEE] text-sm">Allow multiple calls</Text_12_400_EEEEEE>
            </Checkbox>
            <div className="pt-[.8rem]">
              <Text_10_400_757575 className='leading-[140%]'>
                This option allows the agent to execute multiple function calls in a single response, enabling more complex and efficient task completion.
              </Text_10_400_757575>
            </div>
          </div>
        </div>
      </div>
      <div style={{
        marginTop: '18px',
        paddingTop: '18px',
        paddingBottom: '18px',
        borderRadius: '0 0 11px 11px',
        borderTop: '0.5px solid #1F1F1F',
        background: 'rgba(255, 255, 255, 0.03)',
        backdropFilter: 'blur(5px)'
      }} className='flex justify-end items-center px-[1rem]'>
        <PrimaryButton
          onClick={(e: React.MouseEvent) => {
            e.stopPropagation();
            onSaveSystemPrompt?.();
          }}
          loading={isSavingSystemPrompt}
          disabled={isSavingSystemPrompt}
          style={{
            cursor: isSavingSystemPrompt ? 'not-allowed' : 'pointer',
          }}
          classNames="h-[1.375rem] rounded-[0.375rem]"
          textClass="!text-[0.625rem] !font-[400]"
        >
          {isSavingSystemPrompt ? 'Updating...' : 'Update'}
        </PrimaryButton>
      </div>
    </div>
  );
};

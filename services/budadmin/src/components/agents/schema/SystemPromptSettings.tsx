'use client';

import React from 'react';
import { Checkbox } from "antd";
import { PrimaryButton } from "../../ui/bud/form/Buttons";
import { Text_16_400_EEEEEE, Text_10_400_757575, Text_12_400_EEEEEE } from "../../ui/text";
import { TextInput } from "../../ui/input";

interface SystemPromptSettingsProps {
  sessionId: string;
  systemPrompt: string;
  onSystemPromptChange: (value: string) => void;
  onSaveSystemPrompt?: () => void;
  isSavingSystemPrompt?: boolean;
  llmRetryLimit?: number;
  onLlmRetryLimitChange?: (value: number) => void;
  allowMultipleCalls?: boolean;
  onAllowMultipleCallsChange?: (value: boolean) => void;
}

export const SystemPromptSettings: React.FC<SystemPromptSettingsProps> = ({
  sessionId,
  systemPrompt,
  onSystemPromptChange,
  onSaveSystemPrompt,
  isSavingSystemPrompt,
  llmRetryLimit = 3,
  onLlmRetryLimitChange,
  allowMultipleCalls = false,
  onAllowMultipleCallsChange
}) => {
  const [localRetryLimit, setLocalRetryLimit] = React.useState<number | string>(llmRetryLimit);

  React.useEffect(() => {
    setLocalRetryLimit(llmRetryLimit);
  }, [llmRetryLimit]);

  const handleRetryLimitChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    // Allow only digits or empty string
    if (value === '' || /^\d*$/.test(value)) {
      setLocalRetryLimit(value);
    }
  };

  const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    const value = e.target.value;
    let numValue = parseInt(value, 10);

    if (isNaN(numValue)) {
      numValue = 3; // Default to 3 if empty or invalid
    }
    const clampedValue = Math.min(Math.max(numValue, 3), 10);

    // Update both local and parent state
    setLocalRetryLimit(clampedValue);
    onLlmRetryLimitChange?.(clampedValue);
  };

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
            className="w-full max-w-full min-h-[5rem] text-[#EEEEEE] text-sm bg-[#0F0F0F] border border-[#2A2A2A] hover:border-[#965CDE] focus:border-[#965CDE] rounded-lg p-3 outline-none resize-y placeholder:text-[#757575] placeholder:opacity-100 placeholder:text-[.75rem]"
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

        {/* LLM Retry Limit Section */}
        <div className="space-y-2 px-[.5rem] mb-4">
          <div className='bg-[#FFFFFF08] px-[.725rem] py-[1rem] rounded-[.5rem]'>
            <div className="flex flex-col gap-[.5rem]">
              <Text_12_400_EEEEEE className="text-[#EEEEEE] text-sm">LLM Retry Limit</Text_12_400_EEEEEE>
              <TextInput
                type="text"
                name="limit"
                className="!w-full !max-w-full !h-[1.9375rem] placeholder-[#606060] !border-[#2A2A2A] hover:!border-[#965CDE] focus:!border-[#965CDE] text-[#EEEEEE] text-[.75rem] indent-[.625rem] px-[0] bg-[#FFFFFF08]"
                value={localRetryLimit}
                onChange={handleRetryLimitChange}
                onBlur={handleBlur}
              />
              <Text_10_400_757575 className='leading-[140%]'>
                The number of retry attempts for LLM calls. Value must be between 3 and 10.
              </Text_10_400_757575>
            </div>
          </div>
        </div>

        {/* Checkbox Section */}
        <div className="space-y-2 px-[.5rem]">
          <div className='bg-[#FFFFFF08] px-[.725rem] py-[1rem] rounded-[.5rem]'>
            <Checkbox
              checked={allowMultipleCalls}
              onChange={(e) => onAllowMultipleCallsChange?.(e.target.checked)}
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
        marginTop: '0px',
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

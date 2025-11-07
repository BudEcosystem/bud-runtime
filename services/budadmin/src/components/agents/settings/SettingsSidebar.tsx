import React, { useState } from "react";
import Settings from "./Settings";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import { useAgentStore, AgentSession } from "@/stores/useAgentStore";
import { AppRequest } from "src/pages/api/requests";
import { successToast, errorToast } from "@/components/toast";

interface SettingsSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  session?: AgentSession;
}

export function SettingsSidebar({ isOpen, onClose, session }: SettingsSidebarProps) {
  const { currentSettingPreset } = useAgentStore();
  const [isUpdating, setIsUpdating] = useState(false);

  if (!isOpen) return null;

  const handleUpdate = async (e: React.MouseEvent) => {
    e.stopPropagation();

    if (!session?.promptId) {
      errorToast("No prompt ID found for this session");
      return;
    }

    if (!currentSettingPreset) {
      errorToast("No settings found to update");
      return;
    }

    setIsUpdating(true);

    try {
      // Map the current settings to the API payload format
      const payload = {
        prompt_id: session.promptId,
        model_settings: {
          temperature: currentSettingPreset.temperature,
          max_tokens: currentSettingPreset.max_tokens,
          top_p: currentSettingPreset.top_p,
          frequency_penalty: currentSettingPreset.frequency_penalty,
          presence_penalty: currentSettingPreset.presence_penalty,
          stop_sequences: currentSettingPreset.stop_sequences,
          seed: currentSettingPreset.seed,
          timeout: currentSettingPreset.timeout,
          parallel_tool_calls: currentSettingPreset.parallel_tool_calls,
          logprobs: currentSettingPreset.logprobs,
          logit_bias: currentSettingPreset.logit_bias,
          extra_headers: currentSettingPreset.extra_headers,
          max_completion_tokens: currentSettingPreset.max_completion_tokens,
          stream_options: currentSettingPreset.stream_options,
          response_format: currentSettingPreset.response_format,
          tool_choice: currentSettingPreset.tool_choice,
          chat_template: currentSettingPreset.chat_template,
          chat_template_kwargs: currentSettingPreset.chat_template_kwargs,
          mm_processor_kwargs: currentSettingPreset.mm_processor_kwargs,
        },
      };

      await AppRequest.Post("/prompts/prompt-config", payload);
      successToast("Model settings updated successfully");
    } catch (error) {
      console.error("Failed to update model settings:", error);
      errorToast("Failed to update model settings");
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <div
      className="z-[100] tools-box absolute p-3 right-0 top-0 h-full transition-all duration-300 ease-in-out translate-x-0"
      onClick={(e) => e.stopPropagation()}
    >
      <div
        className="flex flex-col h-full w-[16rem] prompt-settings overflow-y-auto rounded-[12px]"
        style={{
          backgroundImage: 'url(/agents/settingsBg.png)',
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          backgroundRepeat: 'no-repeat'
        }}
      >
        <Settings onClose={onClose} />
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
          onClick={handleUpdate}
          disabled={isUpdating}
          classNames="h-[1.375rem] rounded-[0.375rem]"
          textClass="!text-[0.625rem] !font-[400]"
        >
          {isUpdating ? 'Updating...' : 'Update'}
        </PrimaryButton>
      </div>
      </div>

      {/* <div className="flex flex-col h-full">
]        <div className="flex items-center justify-between p-4 border-b border-[#1F1F1F]">
          <h3 className="text-[#EEEEEE] text-sm font-medium">Model Settings</h3>
          <button
            onClick={onClose}
            className="text-[#B3B3B3] hover:text-[#FFFFFF] transition-colors"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="18"
              height="18"
              viewBox="0 0 18 18"
              fill="none"
            >
              <path
                d="M13.5 4.5L4.5 13.5M4.5 4.5L13.5 13.5"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          <Settings />
        </div>
      </div> */}
    </div>
  );
}

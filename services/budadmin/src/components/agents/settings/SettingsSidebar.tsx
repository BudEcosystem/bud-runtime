import React, { useState } from "react";
import Settings from "./Settings";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import { AgentSession, AgentSettings } from "@/stores/useAgentStore";
import { AppRequest } from "src/pages/api/requests";
import { errorToast } from "@/components/toast";

interface SettingsSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  session?: AgentSession;
}

export function SettingsSidebar({ isOpen, onClose, session }: SettingsSidebarProps) {
  const [isUpdating, setIsUpdating] = useState(false);

  if (!isOpen) return null;

  // Get settings from the session's modelSettings (session-specific)
  const sessionSettings = session?.modelSettings;

  const handleUpdate = async (e: React.MouseEvent) => {
    e.stopPropagation();

    if (!session?.promptId) {
      errorToast("No prompt ID found for this session");
      return;
    }

    if (!sessionSettings) {
      errorToast("No settings found to update");
      return;
    }

    setIsUpdating(true);

    try {
      // Build model_settings with only temperature (always) and modified fields
      const modelSettings: Partial<AgentSettings> = {
        temperature: sessionSettings.temperature, // Always include temperature
      };

      // Get modified fields from the session's settings
      const modifiedFields = sessionSettings.modifiedFields || new Set<string>();

      // Add only the fields that have been modified by the user
      modifiedFields.forEach((field) => {
        if (field !== 'temperature' && field in sessionSettings) {
          const key = field as keyof AgentSettings;
          (modelSettings as any)[key] = sessionSettings[key];
        }
      });

      const payload = {
        prompt_id: session.promptId,
        model_settings: modelSettings,
      };

      await AppRequest.Post("/prompts/prompt-config", payload);
      // successToast("Model settings updated successfully"); // Removed: No toast needed
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
        <Settings onClose={onClose} sessionId={session?.id || ''} />
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
    </div>
  );
}

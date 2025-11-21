'use client';

import React from 'react';
import { InputSettings } from './InputSettings';
import { SystemPromptSettings } from './SystemPromptSettings';
import { PromptMessageSettings } from './PromptMessageSettings';
import { OutputSettings } from './OutputSettings';
import { AgentSession, AgentVariable } from "@/stores/useAgentStore";

export enum SettingsType {
  INPUT = 'input',
  SYSTEM_PROMPT = 'system_prompt',
  PROMPT_MESSAGE = 'prompt_message',
  OUTPUT = 'output'
}

interface SettingsSidebarProps {
  session: AgentSession;
  isOpen: boolean;
  activeSettings: SettingsType;
  onClose?: () => void;
  // Input settings props
  onAddInputVariable: () => void;
  onAddOutputVariable: () => void;
  onVariableChange: (variableId: string, field: keyof AgentVariable, value: string) => void;
  onDeleteVariable: (variableId: string) => void;
  onStructuredInputEnabledChange?: (enabled: boolean) => void;
  onStructuredOutputEnabledChange?: (enabled: boolean) => void;
  structuredInputEnabled?: boolean;
  structuredOutputEnabled?: boolean;
  // System prompt and messages props
  onSystemPromptChange: (value: string) => void;
  onPromptMessagesChange: (value: string) => void;
  localSystemPrompt: string;
  localPromptMessages: string;
  // LLM retry limit props
  onLlmRetryLimitChange?: (value: number) => void;
  // Save props
  onSavePromptSchema?: () => void;
  isSaving?: boolean;
  onSaveSystemPrompt?: () => void;
  isSavingSystemPrompt?: boolean;
  onSavePromptMessages?: () => void;
  isSavingPromptMessages?: boolean;
  onSaveOutputSchema?: () => void;
  isSavingOutput?: boolean;
  // Clear schema props
  onClearInputSchema?: () => void;
  onClearOutputSchema?: () => void;
}

export const SettingsSidebar: React.FC<SettingsSidebarProps> = ({
  session,
  isOpen,
  activeSettings,
  onClose,
  onAddInputVariable,
  onAddOutputVariable,
  onVariableChange,
  onDeleteVariable,
  onStructuredInputEnabledChange,
  onStructuredOutputEnabledChange,
  structuredInputEnabled,
  structuredOutputEnabled,
  onSystemPromptChange,
  onPromptMessagesChange,
  localSystemPrompt,
  localPromptMessages,
  onLlmRetryLimitChange,
  onSavePromptSchema,
  isSaving,
  onSaveSystemPrompt,
  isSavingSystemPrompt,
  onSavePromptMessages,
  isSavingPromptMessages,
  onSaveOutputSchema,
  isSavingOutput,
  onClearInputSchema,
  onClearOutputSchema
}) => {
  const renderSettings = () => {
    switch (activeSettings) {
      case SettingsType.INPUT:
        return (
          <InputSettings
            sessionId={session.id}
            inputVariables={session.inputVariables || []}
            onAddVariable={onAddInputVariable}
            onVariableChange={onVariableChange}
            onDeleteVariable={onDeleteVariable}
            onSavePromptSchema={onSavePromptSchema}
            isSaving={isSaving}
            onStructuredInputEnabledChange={onStructuredInputEnabledChange}
            initialStructuredInputEnabled={structuredInputEnabled}
            onClearInputSchema={onClearInputSchema}
          />
        );
      case SettingsType.SYSTEM_PROMPT:
        return (
          <SystemPromptSettings
            sessionId={session.id}
            systemPrompt={localSystemPrompt}
            onSystemPromptChange={onSystemPromptChange}
            onSaveSystemPrompt={onSaveSystemPrompt}
            isSavingSystemPrompt={isSavingSystemPrompt}
            llmRetryLimit={session.llm_retry_limit}
            onLlmRetryLimitChange={onLlmRetryLimitChange}
          />
        );
      case SettingsType.PROMPT_MESSAGE:
        return (
          <PromptMessageSettings
            sessionId={session.id}
            promptMessages={localPromptMessages}
            onPromptMessagesChange={onPromptMessagesChange}
            onSavePromptMessages={onSavePromptMessages}
            isSavingPromptMessages={isSavingPromptMessages}
          />
        );
      case SettingsType.OUTPUT:
        return (
          <OutputSettings
            sessionId={session.id}
            outputVariables={session.outputVariables || []}
            onAddVariable={onAddOutputVariable}
            onVariableChange={onVariableChange}
            onDeleteVariable={onDeleteVariable}
            onSaveOutputSchema={onSaveOutputSchema}
            isSavingOutput={isSavingOutput}
            onStructuredOutputEnabledChange={onStructuredOutputEnabledChange}
            initialStructuredOutputEnabled={structuredOutputEnabled}
            onClearOutputSchema={onClearOutputSchema}
          />
        );
      default:
        // Show all settings as default
        return (
          <>
            <InputSettings
              sessionId={session.id}
              inputVariables={session.inputVariables || []}
              onAddVariable={onAddInputVariable}
              onVariableChange={onVariableChange}
              onDeleteVariable={onDeleteVariable}
              onSavePromptSchema={onSavePromptSchema}
              isSaving={isSaving}
              onStructuredInputEnabledChange={onStructuredInputEnabledChange}
              initialStructuredInputEnabled={structuredInputEnabled}
              onClearInputSchema={onClearInputSchema}
            />
            <SystemPromptSettings
              sessionId={session.id}
              systemPrompt={localSystemPrompt}
              onSystemPromptChange={onSystemPromptChange}
              onSaveSystemPrompt={onSaveSystemPrompt}
              isSavingSystemPrompt={isSavingSystemPrompt}
              llmRetryLimit={session.llm_retry_limit}
              onLlmRetryLimitChange={onLlmRetryLimitChange}
            />
            <PromptMessageSettings
              sessionId={session.id}
              promptMessages={localPromptMessages}
              onPromptMessagesChange={onPromptMessagesChange}
              onSavePromptMessages={onSavePromptMessages}
              isSavingPromptMessages={isSavingPromptMessages}
            />
            <OutputSettings
              sessionId={session.id}
              outputVariables={session.outputVariables || []}
              onAddVariable={onAddOutputVariable}
              onVariableChange={onVariableChange}
              onDeleteVariable={onDeleteVariable}
              onSaveOutputSchema={onSaveOutputSchema}
              isSavingOutput={isSavingOutput}
              onStructuredOutputEnabledChange={onStructuredOutputEnabledChange}
              initialStructuredOutputEnabled={structuredOutputEnabled}
              onClearOutputSchema={onClearOutputSchema}
            />
          </>
        );
    }
  };

  return (
    <div
      className={`z-[100] settings-box absolute p-3 right-0 top-0 h-full transition-all duration-300 ease-in-out ${
        isOpen ? 'translate-x-0' : 'translate-x-full'
      }`}
      onClick={(e) => e.stopPropagation()} // Prevent closing when clicking inside settings
    >
      <div className="flex flex-col h-full w-[16rem] prompt-settings border border-[#1F1F1F] bg-[#0A0A0A] overflow-y-auto rounded-[12px]">
        {renderSettings()}
      </div>
    </div>
  );
};

'use client';

import React from 'react';
import { PlusOutlined, CloseOutlined } from "@ant-design/icons";
import { Image, Switch, Select, Checkbox } from "antd";
import { PrimaryButton } from "../../ui/bud/form/Buttons";
import { Text_12_400_808080, Text_12_400_B3B3B3, Text_14_400_757575, Text_14_400_EEEEEE, Text_16_400_EEEEEE } from "../../ui/text";
import { TextInput, TextAreaInput } from "../../ui/input";
import { AgentVariable } from "@/stores/useAgentStore";

interface OutputSettingsProps {
  sessionId: string;
  outputVariables: AgentVariable[];
  onAddVariable: () => void;
  onVariableChange: (variableId: string, field: keyof AgentVariable, value: string) => void;
  onDeleteVariable: (variableId: string) => void;
  onSaveOutputSchema?: () => void;
  isSavingOutput?: boolean;
  onStructuredOutputEnabledChange?: (enabled: boolean) => void;
}

export const OutputSettings: React.FC<OutputSettingsProps> = ({
  sessionId,
  outputVariables,
  onAddVariable,
  onVariableChange,
  onDeleteVariable,
  onSaveOutputSchema,
  isSavingOutput,
  onStructuredOutputEnabledChange
}) => {
  const [isOpen, setIsOpen] = React.useState(true);
  const [structuredOutputEnabled, setStructuredOutputEnabled] = React.useState(false);
  const [variableOpenStates, setVariableOpenStates] = React.useState<Record<string, boolean>>({});
  const [validationEnabled, setValidationEnabled] = React.useState<Record<string, boolean>>({});

  // Initialize validation enabled state based on existing validation values
  React.useEffect(() => {
    const newValidationEnabled: Record<string, boolean> = {};
    outputVariables.forEach(variable => {
      if (variable.validation) {
        newValidationEnabled[variable.id] = true;
      }
    });
    setValidationEnabled(prev => ({ ...prev, ...newValidationEnabled }));
  }, [outputVariables]);

  // Notify parent when structuredOutputEnabled changes
  React.useEffect(() => {
    onStructuredOutputEnabledChange?.(structuredOutputEnabled);
  }, [structuredOutputEnabled, onStructuredOutputEnabledChange]);

  return (
    <div className="flex flex-col justify-between h-full w-full">
      <div className='flex flex-col py-[1rem]'>
        <div className='flex flex-col gap-[1rem] border-b border-[#1F1F1F] pb-[1rem] px-[0.9375rem]'>
          <div
            className="flex flex-row items-center gap-[1rem] justify-between"
          >
            <div className="flex flex-row items-center gap-[.4rem] py-[.5rem]">
              <Text_16_400_EEEEEE>Output</Text_16_400_EEEEEE>
            </div>
            {structuredOutputEnabled && (
              <div className="flex flex-row items-center gap-[.5rem]">
                <PrimaryButton
                  size="small"
                  onClick={(e: React.MouseEvent) => {
                    e.stopPropagation();
                    onAddVariable();
                  }}
                  classNames="h-[1.375rem] rounded-[0.375rem]"
                  textClass="!text-[0.625rem] !font-[400]"
                >
                  + Add Variable
                </PrimaryButton>

              </div>
            )}
          </div>
          <div
            className="flex flex-row items-center gap-[1rem] justify-start cursor-pointer"
            onClick={() => setStructuredOutputEnabled(!structuredOutputEnabled)}
          >
            <div className="flex flex-row items-center gap-[.4rem] py-[.5rem]">
              <Text_12_400_B3B3B3>Structured output</Text_12_400_B3B3B3>
            </div>
            <Switch
              checked={structuredOutputEnabled}
              onChange={(checked) => setStructuredOutputEnabled(checked)}
            />
          </div>
        </div>
        {/* Output Variables Section - Only show if structured output is enabled */}
        {structuredOutputEnabled && (
          <div className="">
            {(outputVariables || []).map((variable, index) => (
              <div key={variable.id} className="border-b border-[#1F1F1F]">
                <div className='py-[1rem]'>
                  <div className='group flex justify-between items-center px-[.5rem] cursor-pointer' onClick={() => {
                    const newOpenStates = { ...variableOpenStates };
                    newOpenStates[variable.id] = !newOpenStates[variable.id];
                    setVariableOpenStates(newOpenStates);
                  }}>
                    <Text_14_400_757575>Output Variable {index + 1}</Text_14_400_757575>
                    <div className='flex justify-end items-center'>
                      {/* Delete button */}
                      {(outputVariables?.length || 0) > 1 && index + 1 > 1 && (
                        <button
                          onClick={() => onDeleteVariable(variable.id)}
                          className="opacity-0 transition-opacity z-10 p-0 mr-[.6rem] group-hover:opacity-100"
                        >
                          <CloseOutlined className="text-[#808080] hover:text-[#FF4444] text-xs" />
                        </button>
                      )}
                      <div className="flex items-center gap-2">
                        <Image
                          src="/icons/customArrow.png"
                          className={`w-[.75rem] transform transition-transform rotate-0 ${variableOpenStates[variable.id] ? "" : "rotate-180"}`}
                          preview={false}
                          alt="chevron"
                        />
                      </div>
                    </div>
                  </div>
                  {variableOpenStates[variable.id] && (
                    <div className="px-[.5rem] pt-4">
                      <div className="relative group rounded-lg transition-colors">
                        <div className="space-y-1.5">
                          {/* Variable Name */}
                          <div className="flex flex-col gap-1">
                            <TextInput
                              className="!w-full !max-w-full !h-[1.9375rem] placeholder-[#606060] !border-[#2A2A2A] hover:!border-[#965CDE] focus:!border-[#965CDE] text-[#EEEEEE] text-[.75rem] indent-[.625rem] px-[0] bg-[#FFFFFF08]"
                              value={variable.name || ''}
                              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                                onVariableChange(variable.id, "name", e.target.value)
                              }
                              placeholder="Enter variable name"
                            />
                          </div>

                          {/* Description */}
                          <div className="flex flex-col gap-1">
                            <TextInput
                              className="!w-full !max-w-full !h-[1.9375rem] placeholder-[#606060] !border-[#2A2A2A] hover:!border-[#965CDE] focus:!border-[#965CDE] text-[#EEEEEE] text-[.75rem] indent-[.625rem] px-[0] bg-[#FFFFFF08]"
                              value={variable.description || ''}
                              onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) =>
                                onVariableChange(variable.id, "description", e.target.value)
                              }
                              placeholder="Describe this variable"
                            />
                          </div>

                          {/* Type Select */}
                          <div className="flex flex-col gap-1">
                            <style jsx global>{`
                                .input-settings-select.ant-select .ant-select-selector {
                                padding-left: .625rem !important;
                                padding-right: .625rem !important;
                                background-color: #FFFFFF08 !important;
                              }
                            `}</style>
                            <Select
                              className="!w-full custom-select input-settings-select"
                              value={variable.dataType || 'string'}
                              onChange={(value) => onVariableChange(variable.id, "dataType", value)}
                              options={[
                                { value: 'string', label: 'String' },
                                { value: 'number', label: 'Number' },
                                { value: 'boolean', label: 'Boolean' },
                                { value: 'array', label: 'Array' },
                                { value: 'object', label: 'Object' }
                              ]}
                              style={{
                                height: '32px',
                                fontSize: '12px'
                              }}
                            />
                          </div>

                          {/* Default Value */}
                          <div className="flex flex-col gap-1">
                            <TextInput
                              className="!w-full !max-w-full !h-[1.9375rem] placeholder-[#606060] !border-[#2A2A2A] hover:!border-[#965CDE] focus:!border-[#965CDE] text-[#EEEEEE] text-[.75rem] indent-[.625rem] px-[0] bg-[#FFFFFF08]"
                              value={variable.defaultValue || ''}
                              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                                onVariableChange(variable.id, "defaultValue", e.target.value)
                              }
                              placeholder="Enter default value"
                            />
                          </div>
                        </div>
                      </div>
                      <div className='px-[.5rem] pt-4'>
                        {/* validation checkbox */}
                        <div className='flex justify-start gap-[.6rem] items-center mt-3'>
                          <Checkbox
                            checked={validationEnabled[variable.id] || false}
                            className=""
                            onChange={(e) => {
                              setValidationEnabled({ ...validationEnabled, [variable.id]: e.target.checked });
                              if (!e.target.checked) {
                                onVariableChange(variable.id, "validation", "");
                              }
                            }}
                          />
                          <Text_12_400_808080>Validation</Text_12_400_808080>
                        </div>
                        {/* validation input - only shown when checkbox is checked */}
                        {validationEnabled[variable.id] && (
                          <div className="flex flex-col gap-1 mt-2">
                            <TextInput
                              name={`variable-validation-${variable.id}`}
                              className="!w-full !max-w-full !h-[1.9375rem] placeholder-[#606060] !border-[#2A2A2A] hover:!border-[#965CDE] focus:!border-[#965CDE] text-[#EEEEEE] text-[.75rem] indent-[.625rem] px-[0] bg-[#FFFFFF08]"
                              value={variable.validation || ''}
                              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                                onVariableChange(variable.id, "validation", e.target.value)
                              }
                              placeholder="Enter validation pattern (e.g., regex, min/max)"
                            />
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
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
            onSaveOutputSchema?.();
          }}
          loading={isSavingOutput}
          disabled={isSavingOutput || !structuredOutputEnabled}
          style={{
            cursor: (isSavingOutput || !structuredOutputEnabled) ? 'not-allowed' : 'pointer',
          }}
          classNames="h-[1.375rem] rounded-[0.375rem]"
          textClass="!text-[0.625rem] !font-[400]"
        >
          {isSavingOutput ? 'Updating...' : 'Update'}
        </PrimaryButton>
      </div>
    </div>
  );
};

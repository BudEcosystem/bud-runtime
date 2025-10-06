'use client';

import React from 'react';
import { PlusOutlined, CloseOutlined } from "@ant-design/icons";
import { Image, Switch, Select, Checkbox } from "antd";
import { PrimaryButton } from "../../ui/bud/form/Buttons";
import { Text_12_400_808080, Text_12_400_B3B3B3, Text_14_400_757575, Text_14_400_EEEEEE, Text_16_400_EEEEEE } from "../../ui/text";
import { TextInput, TextAreaInput } from "../../ui/input";
import { AgentVariable } from "@/stores/useAgentStore";

interface InputSettingsProps {
  sessionId: string;
  inputVariables: AgentVariable[];
  onAddVariable: () => void;
  onVariableChange: (variableId: string, field: keyof AgentVariable, value: string) => void;
  onDeleteVariable: (variableId: string) => void;
}

export const InputSettings: React.FC<InputSettingsProps> = ({
  sessionId,
  inputVariables,
  onAddVariable,
  onVariableChange,
  onDeleteVariable
}) => {
  const [isOpen, setIsOpen] = React.useState(true);
  const [variableOpenStates, setVariableOpenStates] = React.useState<Record<string, boolean>>({});
  const [validationEnabled, setValidationEnabled] = React.useState<Record<string, boolean>>({});

  // Initialize validation enabled state based on existing validation values
  React.useEffect(() => {
    const newValidationEnabled: Record<string, boolean> = {};
    inputVariables.forEach(variable => {
      if (variable.validation) {
        newValidationEnabled[variable.id] = true;
      }
    });
    setValidationEnabled(prev => ({ ...prev, ...newValidationEnabled }));
  }, [inputVariables]);

  return (
    <div className="flex flex-col w-full px-[.4rem] py-[1rem]">
      <div className='flex flex-col gap-[1rem] border-b border-[#1F1F1F] pb-[1rem]'>
        <div
          className="flex flex-row items-center gap-[1rem] px-[.3rem] justify-between"
        >
          <div className="flex flex-row items-center gap-[.4rem] py-[.5rem]">
            <Text_16_400_EEEEEE>Input</Text_16_400_EEEEEE>
          </div>
          <div className="flex flex-row items-center gap-[.5rem]">
            <PrimaryButton
              size="small"
              onClick={(e: React.MouseEvent) => {
                e.stopPropagation();
                onAddVariable();
              }}
              className="bg-[#965CDE] border-none text-white hover:bg-[#8050C8] h-6 px-2 text-xs !rounded-[12px]"
            >
              + Add Variable
            </PrimaryButton>

          </div>
        </div>
        <div
          className="flex flex-row items-center gap-[1rem] px-[.3rem] justify-start cursor-pointer"
          onClick={() => setIsOpen(!isOpen)}
        >
          <div className="flex flex-row items-center gap-[.4rem] py-[.5rem]">
            <Text_12_400_B3B3B3>Structured input</Text_12_400_B3B3B3>
          </div>
          <Switch className="" />
        </div>
      </div>
      {/* Input Variables Section */}
      <div className="">
        {(inputVariables || []).map((variable, index) => (
          <div key={variable.id} className="border-b border-[#1F1F1F]">
            <div className='py-[1rem]'>
              <div className='flex justify-between items-center px-[.5rem] cursor-pointer' onClick={() => {
                const newOpenStates = { ...variableOpenStates };
                newOpenStates[variable.id] = !newOpenStates[variable.id];
                setVariableOpenStates(newOpenStates);
              }}>
                <Text_14_400_757575>Input Variable {index + 1}</Text_14_400_757575>
                <div className="flex items-center gap-2">
                  <Image
                    src="/icons/customArrow.png"
                    className={`w-[.75rem] transform transition-transform rotate-0 ${variableOpenStates[variable.id] ? "" : "rotate-180"}`}
                    preview={false}
                    alt="chevron"
                  />
                </div>
              </div>
              {variableOpenStates[variable.id] && (
                <>
                  <div className="px-[.5rem] pt-4">
                    <div className="relative group rounded-lg transition-colors">
                      {/* Delete button */}
                      {(inputVariables?.length || 0) > 1 && (
                        <button
                          onClick={() => onDeleteVariable(variable.id)}
                          className="absolute top-0 right-0 p-1 opacity-100 transition-opacity z-10"
                        >
                          <CloseOutlined className="text-[#808080] hover:text-[#FF4444] text-xs" />
                        </button>
                      )}

                      <div className="space-y-3">
                        {/* Variable Name */}
                        <div className="flex flex-col gap-1">
                          <TextInput
                            name={`variable-name-${variable.id}`}
                            className="!w-full !max-w-full !h-[2rem] placeholder-[#606060] !border-[#2A2A2A] hover:!border-[#965CDE] focus:!border-[#965CDE] px-[.4rem]"
                            value={variable.name || ''}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                              onVariableChange(variable.id, "name", e.target.value)
                            }
                            placeholder="Enter variable name"
                          />
                        </div>

                        {/* Description */}
                        <div className="flex flex-col gap-1">
                          <TextAreaInput
                            className="!w-full !max-w-full !min-h-[3rem] !text-[#EEEEEE] !text-xs !placeholder-[#606060] !border-[#2A2A2A] hover:!border-[#965CDE] focus:!border-[#965CDE] px-[.4rem]"
                            value={variable.description || ''}
                            onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) =>
                              onVariableChange(variable.id, "description", e.target.value)
                            }
                            placeholder="Describe this variable"
                          />
                        </div>

                        {/* Type Select */}
                        <div className="flex flex-col gap-1">
                          <Select
                            className="!w-full custom-select"
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
                            className="!w-full !max-w-full !h-[2rem] !text-[#EEEEEE] !text-xs !placeholder-[#606060] !border-[#2A2A2A] hover:!border-[#965CDE] focus:!border-[#965CDE] px-[.4rem]"
                            value={variable.defaultValue || ''}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                              onVariableChange(variable.id, "defaultValue", e.target.value)
                            }
                            placeholder="Enter default value"
                          />
                        </div>
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
                          className="!w-full !max-w-full !h-[2rem] !text-[#EEEEEE] !text-xs !placeholder-[#606060] !border-[#2A2A2A] hover:!border-[#965CDE] focus:!border-[#965CDE] px-[.4rem]"
                          value={variable.validation || ''}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                            onVariableChange(variable.id, "validation", e.target.value)
                          }
                          placeholder="Enter validation pattern (e.g., regex, min/max)"
                        />
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

'use client';

import React from 'react';
import { PlusOutlined, CloseOutlined } from "@ant-design/icons";
import { Image } from "antd";
import { PrimaryButton } from "../../ui/bud/form/Buttons";
import { Text_14_400_757575 } from "../../ui/text";
import { TextInput } from "../../ui/input";
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

  return (
    <div className="flex flex-col w-full px-[.4rem] py-[1.5rem] border-b border-[#1F1F1F]">
      <div
        className="flex flex-row items-center gap-[1rem] px-[.3rem] justify-between cursor-pointer"
        onClick={() => setIsOpen(!isOpen)}
      >
        <div className="flex flex-row items-center gap-[.4rem] py-[.5rem]">
          <Text_14_400_757575>Input</Text_14_400_757575>
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
          {(inputVariables || []).map((variable, idx) => (
            <div key={variable.id} className="relative group">
              <div className="relative">
                <TextInput
                  className="!w-full !max-w-full !h-[2rem] !text-[#EEEEEE] !text-xs !placeholder-[#606060] !border-[#2A2A2A] hover:!border-[#965CDE] focus:!border-[#965CDE] px-[.4rem]"
                  value={variable.value}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                    onVariableChange(variable.id, "value", e.target.value)
                  }
                  placeholder={`Input Variable ${idx + 1}`}
                />
                {(inputVariables?.length || 0) > 1 && (
                  <button
                    onClick={() => onDeleteVariable(variable.id)}
                    className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    <CloseOutlined className="text-[#808080] hover:text-[#FF4444] text-xs" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

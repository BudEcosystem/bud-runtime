import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Image } from "antd";
import { errorToast } from "@/components/toast";
import { Text_12_400_757575, Text_14_600_EEEEEE } from "@/components/ui/text";

type AgentType = 'simple_prompt' | 'prompt_workflow' | 'agent' | 'chatflow';

interface AgentTypeOption {
  value: AgentType;
  label: string;
  description: string;
  icon: string;
}

export default function SelectAgentType() {
  const { openDrawerWithStep, closeDrawer } = useDrawer();
  const [selectedType, setSelectedType] = useState<AgentType | null>(null);

  const agentTypes: AgentTypeOption[] = [
    {
      value: 'simple_prompt',
      label: 'Simple Prompt',
      description: 'Create simple text generation prompt for basic LLM interactions',
      icon: '/images/drawer/brain.png', // LLM icon from modalityTypeList
    },
    {
      value: 'prompt_workflow',
      label: 'Prompt Workflow',
      description: 'Create complex prompt chains with multiple models and steps',
      icon: '/images/drawer/compare.png', // Action transformers icon
    },
    {
      value: 'agent',
      label: 'Agent',
      description: 'Create autonomous agent with custom tools and capabilities',
      icon: '/images/drawer/embedding.png', // Embedding icon for agent intelligence
    },
    {
      value: 'chatflow',
      label: 'Chatflow',
      description: 'Create conversational flow with dialog management',
      icon: '/images/drawer/textToSpeach.png', // Text to speech for conversations
    },
  ];

  const handleNext = () => {
    if (!selectedType) {
      errorToast("Please select a model type");
      return;
    }

    // Store the selected type
    localStorage.setItem("addAgent_selectedType", selectedType);

    // Navigate based on selected type
    if (selectedType === 'agent') {
      // Continue with the existing agent creation flow
      openDrawerWithStep("add-agent-select-project");
    } else {
      // For other types, you might want different flows
      // For now, all go to the same flow
      openDrawerWithStep("add-agent-select-project");
    }
  };

  const handleBack = () => {
    closeDrawer();
  };

  return (
    <BudForm
      data={{}}
      onNext={handleNext}
      onBack={handleBack}
      backText="Cancel"
      nextText="Next"
      disableNext={!selectedType}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Select Model"
            description="Select model from the following list"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem] text-[#B3B3B3]"
          />

          <div className="px-[1.35rem] pb-[1.35rem]">
            <div className="grid grid-cols-1 gap-[1rem]">
              {agentTypes.map((type) => (
                <div
                  key={type.value}
                  onClick={() => setSelectedType(type.value)}
                  className={`
                    relative cursor-pointer transition-all duration-300
                    bg-[#101010] hover:bg-[#1F1F1F]
                    border rounded-[12px] p-[1rem]
                    hover:shadow-[0_4px_20px_rgba(150,92,222,0.15)]
                    ${selectedType === type.value
                      ? 'border-[#965CDE] bg-[#965CDE]/5 shadow-[0_4px_20px_rgba(150,92,222,0.2)]'
                      : 'border-[#1F1F1F] hover:border-[#757575]'
                    }
                  `}
                >
                  {/* Selection indicator */}
                  {selectedType === type.value && (
                    <div className="absolute top-3 right-3 w-5 h-5 rounded-full bg-[#965CDE] flex items-center justify-center">
                      <div className="w-2 h-2 rounded-full bg-white" />
                    </div>
                  )}

                  <div className="flex justify-start items-start gap-[1rem]">
                    {/* Icon */}
                    <div className="mb-[1rem]">
                      <div className="w-[3rem] h-[3rem] rounded-[8px] bg-[#1F1F1F] flex items-center justify-center overflow-hidden">
                        <Image
                          src={type.icon}
                          alt={type.label}
                          preview={false}
                          width={28}
                          height={28}
                          style={{ objectFit: 'contain' }}
                        />
                      </div>
                    </div>

                    {/* Content */}
                    <div className="flex flex-col">
                      <Text_14_600_EEEEEE className="mb-[0.5rem]">
                        {type.label}
                      </Text_14_600_EEEEEE>
                      <Text_12_400_757575 className="leading-[1.4]">
                        {type.description}
                      </Text_12_400_757575>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useState, useEffect } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Image } from "antd";
import { errorToast } from "@/components/toast";
import { Text_12_400_757575, Text_14_600_EEEEEE } from "@/components/ui/text";
import { useAddAgent } from "@/stores/useAddAgent";
import { useAgentStore } from "@/stores/useAgentStore";
import { AppRequest } from "src/pages/api/requests";
import { tempApiBaseUrl } from "@/components/environment";

type AgentType = 'simple_prompt' | 'prompt_workflow' | 'agent' | 'chatflow';

interface AgentTypeOption {
  value: AgentType;
  label: string;
  description: string;
  icon: string;
}

export default function SelectAgentType() {
  const { openDrawerWithStep, closeDrawer } = useDrawer();
  const { openAgentDrawer } = useAgentStore();
  const [selectedType, setSelectedType] = useState<AgentType | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Use the Add Agent store for workflow management
  const {
    currentWorkflow,
    selectedProject,
    setSelectedAgentType,
    getWorkflow,
    loading
  } = useAddAgent();

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

  // Load workflow on component mount if it exists
  useEffect(() => {
    if (currentWorkflow?.workflow_id) {
      getWorkflow(currentWorkflow.workflow_id);
    }
  }, [currentWorkflow?.workflow_id, getWorkflow]);

  const handleNext = async () => {
    if (!selectedType) {
      errorToast("Please select an agent type");
      return;
    }

    if (!currentWorkflow?.workflow_id) {
      errorToast("Workflow not initialized. Please start from the beginning.");
      return;
    }

    setIsSubmitting(true);

    try {
      // Store the selected type in local storage for reference
      localStorage.setItem("addAgent_selectedType", selectedType);

      // Store in the Add Agent store
      const selectedAgentOption = agentTypes.find(t => t.value === selectedType);
      if (selectedAgentOption) {
        setSelectedAgentType({
          id: selectedType,
          name: selectedAgentOption.label,
          description: selectedAgentOption.description,
          icon: selectedAgentOption.icon
        });
      }

      // Call the workflow API for step 2
      const response = await AppRequest.Post(
        `${tempApiBaseUrl}/prompts/prompt-workflow`,
        {
          workflow_id: currentWorkflow.workflow_id,
          step_number: 2,
          prompt_type: selectedType
        },
        {
          headers: {
            "x-resource-type": "project",
            "x-entity-id": selectedProject?.id || currentWorkflow.workflow_steps?.project?.id
          }
        }
      );

      if (response?.data) {
        // Update the workflow in the store
        await getWorkflow(currentWorkflow.workflow_id);

        // Open the agent drawer with workflow_id
        openAgentDrawer(currentWorkflow.workflow_id);

        // Navigate to the next step (Select Model)
        openDrawerWithStep("add-agent-select-model");
      } else {
        errorToast("Failed to update agent type");
      }
    } catch (error) {
      console.error("Failed to update agent type:", error);
      errorToast("Failed to update agent type");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleBack = () => {
    // Navigate back to Select Project (step 1)
    openDrawerWithStep("add-agent-select-project");
  };

  return (
    <BudForm
      data={{}}
      onNext={handleNext}
      onBack={handleBack}
      backText="Back"
      nextText="Next"
      disableNext={!selectedType || isSubmitting || loading}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Select Agent Type"
            description="Choose the type of agent you want to create"
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

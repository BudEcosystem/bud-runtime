import React, { useEffect } from "react";
import { Image, Tag } from "antd";
import { useDrawer } from "src/hooks/useDrawer";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { Text_12_400_B3B3B3, Text_16_600_FFFFFF, Text_14_400_EEEEEE } from "@/components/ui/text";
import { getChromeColor } from "@/components/ui/bud/dataEntry/TagsInputData";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { ModelFlowInfoCard } from "@/components/ui/bud/deploymentDrawer/DeployModelSpecificationInfo";
import { useAddAgent } from "@/stores/useAddAgent";

export default function AgentSuccess() {
  const { closeDrawer } = useDrawer();

  // Get data from the Add Agent store
  const {
    selectedProject,
    selectedModel,
    deploymentConfiguration,
    reset
  } = useAddAgent();

  useEffect(() => {
    // Clean up the store when component unmounts (drawer closes)
    return () => {
      reset();
    };
  }, [reset]);

  // Get model tags to display
  const getModelTags = () => {
    const tags = [];

    // Add LLM tag if it's a language model (text modality)
    if (selectedModel?.modality?.text?.input || selectedModel?.modality?.text?.output) {
      tags.push({ name: "LLM", color: "#965CDE" });
    }

    // Add model size tag (e.g., "7B")
    if (selectedModel?.model_size) {
      const sizeStr = typeof selectedModel.model_size === 'number'
        ? `${Math.round(selectedModel.model_size)}B`
        : selectedModel.model_size;
      tags.push({ name: sizeStr, color: "#FF9F00" });
    }

    // Add reasoning tag if applicable
    if (selectedModel?.tags?.some((tag: any) => tag.name?.toLowerCase().includes("reasoning"))) {
      tags.push({ name: "Reasoning", color: "#4CAF50" });
    }

    return tags;
  };

  return (
    <BudForm
      data={{}}
      backText="Close"
      onBack={() => {
        closeDrawer();
      }}
    >
      <BudWraperBox >
        <BudDrawerLayout>
          <DrawerTitleCard
              title={"Prompt Deployed"}
              description={`${deploymentConfiguration?.deploymentName} prompt has been deployed`}
            />
            <ModelFlowInfoCard
              selectedModel={selectedModel}
              informationSpecs={[
                {
                  name: "URI",
                  value: selectedModel?.uri,
                  full: true,
                  icon: "/images/drawer/tag.png",
                },
              ]}
            />
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

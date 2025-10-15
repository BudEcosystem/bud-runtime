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
import { usePromptsAgents } from "@/stores/usePromptsAgents";

export default function AgentSuccess() {
  const { closeDrawer } = useDrawer();
  const { fetchPrompts } = usePromptsAgents();

  // Get data from the Add Agent store
  const {
    currentWorkflow,
    deploymentConfiguration,
    reset
  } = useAddAgent();

  useEffect(() => {
    // Clean up the store when component unmounts (drawer closes)
    return () => {
      reset();
    };
  }, [reset]);

  // Get model from workflow steps
  const model = currentWorkflow?.workflow_steps?.model;

  const handleClose = () => {
    // Refresh the prompts list
    fetchPrompts();
    // Close the drawer
    closeDrawer();
  };

  return (
    <BudForm
      data={{}}
      backText="Close"
      onBack={handleClose}
    >
      <BudWraperBox >
        <BudDrawerLayout>
          <DrawerTitleCard
              title={"Prompt Deployed"}
              description={`${deploymentConfiguration?.deploymentName} prompt has been deployed`}
            />
            <ModelFlowInfoCard
              selectedModel={model}
              informationSpecs={[
                {
                  name: "URI",
                  value: model?.uri,
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

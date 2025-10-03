import React, { useEffect, useState } from "react";
import { Image, Tag } from "antd";
import { useDrawer } from "src/hooks/useDrawer";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { Text_12_400_B3B3B3, Text_16_600_FFFFFF, Text_14_400_EEEEEE } from "@/components/ui/text";
import { getChromeColor } from "@/components/ui/bud/dataEntry/TagsInputData";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { ModelFlowInfoCard } from "@/components/ui/bud/deploymentDrawer/DeployModelSpecificationInfo";

export default function AgentSuccess() {
  const { closeDrawer } = useDrawer();

  // Get stored data to display in success screen
  const [configData, setConfigData] = useState<any>(null);
  const [modelData, setModelData] = useState<any>(null);
  const [projectData, setProjectData] = useState<any>(null);

  useEffect(() => {
    // Retrieve stored data from localStorage (will be cleared after this)
    const config = localStorage.getItem("addAgent_configuration");
    const model = localStorage.getItem("addAgent_selectedModel");
    const project = localStorage.getItem("addAgent_selectedProject");

    if (config) setConfigData(JSON.parse(config));
    if (model) setModelData(JSON.parse(model));
    if (project) setProjectData(JSON.parse(project));

    // Clear localStorage after displaying success
    localStorage.removeItem("addAgent_selectedProject");
    localStorage.removeItem("addAgent_selectedModel");
    localStorage.removeItem("addAgent_selectedType");
    localStorage.removeItem("addAgent_configuration");
    localStorage.removeItem("addAgent_warnings");
  }, []);

  // Get model tags to display
  const getModelTags = () => {
    const tags = [];

    // Add LLM tag if it's a language model
    if (modelData?.modality?.includes("text") || modelData?.modality?.includes("llm")) {
      tags.push({ name: "LLM", color: "#965CDE" });
    }

    // Add model size tag (e.g., "7B")
    if (modelData?.model_size) {
      const sizeStr = typeof modelData.model_size === 'number'
        ? `${Math.round(modelData.model_size)}B`
        : modelData.model_size;
      tags.push({ name: sizeStr, color: "#FF9F00" });
    }

    // Add reasoning tag if applicable
    if (modelData?.tags?.some((tag: any) => tag.name?.toLowerCase().includes("reasoning"))) {
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
              description={`${configData?.deploymentName} prompt have been deployed`}
            />
            <ModelFlowInfoCard
              selectedModel={modelData}
              informationSpecs={[
                {
                  name: "URI",
                  value: modelData?.uri,
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

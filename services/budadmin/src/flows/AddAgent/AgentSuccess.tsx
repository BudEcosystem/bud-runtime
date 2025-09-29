import React, { useEffect, useState } from "react";
import { Image, Tag } from "antd";
import { useDrawer } from "src/hooks/useDrawer";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { Text_12_400_B3B3B3, Text_16_600_FFFFFF, Text_14_400_EEEEEE } from "@/components/ui/text";
import { getChromeColor } from "@/components/ui/bud/dataEntry/TagsInputData";

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
    localStorage.removeItem("addAgent_configuration");
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
      <BudWraperBox center={true}>
        <BudDrawerLayout>
          <div className="flex flex-col justify-center items-center px-[2.5rem] py-[3rem]">
            {/* Title Section */}
            <div className="text-center mb-[2rem]">
              <Text_16_600_FFFFFF className="text-[1.5rem] font-semibold">
                Prompt Deployed
              </Text_16_600_FFFFFF>
              <Text_12_400_B3B3B3 className="mt-[0.5rem]">
                Write a description
              </Text_12_400_B3B3B3>
            </div>

            {/* Model Card */}
            <div className="bg-[#1F1F1F] rounded-[12px] p-[1.5rem] w-full max-w-[400px]">
              <div className="flex items-start gap-[1rem]">
                {/* Model Icon */}
                <div className="w-[3.5rem] h-[3.5rem] rounded-[8px] bg-gradient-to-br from-[#965CDE] to-[#5CADFF] flex items-center justify-center flex-shrink-0">
                  {modelData?.icon ? (
                    <span className="text-[1.5rem]">{modelData.icon}</span>
                  ) : (
                    <span className="text-white text-[1.2rem] font-bold">AI</span>
                  )}
                </div>

                {/* Model Details */}
                <div className="flex-1">
                  {/* Model Name */}
                  <Text_16_600_FFFFFF className="mb-[0.5rem]">
                    {modelData?.name || configData?.deploymentName || "InternLM 2.5"}
                  </Text_16_600_FFFFFF>

                  {/* Tags */}
                  <div className="flex gap-[0.5rem] flex-wrap mb-[1rem]">
                    {getModelTags().map((tag, index) => (
                      <Tag
                        key={index}
                        className="border-0 rounded-[4px] px-2 py-1 text-xs"
                        style={{
                          backgroundColor: tag.color + '20',
                          color: tag.color,
                        }}
                      >
                        {tag.name}
                      </Tag>
                    ))}
                  </div>

                  {/* Description */}
                  <Text_12_400_B3B3B3 className="leading-[1.4]">
                    {modelData?.description ||
                     `${modelData?.name || "InternLM 2.5"} offers strong reasoning across the board as well as tool use for developers, while sitting at the sweet spot of size for those with 24GB GPUs.`}
                  </Text_12_400_B3B3B3>
                </div>
              </div>
            </div>

            {/* Additional Info */}
            <div className="mt-[2rem] text-center max-w-[400px]">
              <Text_14_400_EEEEEE className="mb-[0.5rem]">
                Agent Successfully Created
              </Text_14_400_EEEEEE>
              <Text_12_400_B3B3B3>
                Your agent <span className="text-[#965CDE]">{configData?.deploymentName}</span> has been successfully deployed
                to <span className="text-[#965CDE]">{projectData?.project?.name || "your project"}</span>.
                You can now use the agent for inference.
              </Text_12_400_B3B3B3>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

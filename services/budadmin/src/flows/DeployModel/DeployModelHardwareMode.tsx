import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { Text_14_400_EEEEEE, Text_10_400_B3B3B3 } from "@/components/ui/text";
import React, { useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useDeployModel } from "src/stores/useDeployModel";
import { Checkbox, Image } from "antd";

// Badge color configurations for hardware mode cards
const BADGE_STYLES: Record<string, { backgroundColor: string; color: string }> = {
  blue: { backgroundColor: "#1F3A5F", color: "#5B9FFF" },
  green: { backgroundColor: "#1F3F1F", color: "#52c41a" },
};

interface HardwareModeCardProps {
  mode: "dedicated" | "shared";
  title: string;
  description: string;
  icon: string;
  badge?: string;
  badgeColor?: string;
  benefits: string[];
  selected: boolean;
  onClick: () => void;
}

function HardwareModeCard({
  mode,
  title,
  description,
  icon,
  badge,
  badgeColor,
  benefits,
  selected,
  onClick,
}: HardwareModeCardProps) {
  const [hover, setHover] = useState(false);

  return (
    <div
      onMouseEnter={() => setHover(true)}
      onClick={onClick}
      onMouseLeave={() => setHover(false)}
      className="py-[1.1rem] hover:bg-[#FFFFFF03] cursor-pointer hover:shadow-lg px-[1.4rem] border-b-[0.5px] border-t-[0.5px] border-t-[transparent] border-b-[#1F1F1F] hover:border-t-[.5px] hover:border-[#757575] flex-row flex border-box"
    >
      <div className="mr-[.7rem]">
        <div className="bg-[#1F1F1F] w-[1.75rem] h-[1.75rem] rounded-[5px] flex justify-center items-center shrink-0 grow-0">
          <Image
            preview={false}
            src={icon}
            className="!w-[1.25rem] !h-[1.25rem]"
            style={{ width: "1.25rem", height: "1.25rem" }}
            alt={mode}
          />
        </div>
      </div>
      <div className="flex justify-between w-full flex-col">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Text_14_400_EEEEEE className="leading-[150%]">
              {title}
            </Text_14_400_EEEEEE>
            {badge && badgeColor && (
              <span
                className="px-2 py-0.5 rounded text-[10px] font-medium"
                style={BADGE_STYLES[badgeColor] || BADGE_STYLES.blue}
              >
                {badge}
              </span>
            )}
          </div>
          <div
            style={{
              display: hover || selected ? "flex" : "none",
            }}
          >
            <Checkbox
              checked={selected}
              className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]"
            />
          </div>
        </div>
        <Text_10_400_B3B3B3 className="overflow-hidden leading-[170%] mt-1">
          {description}
        </Text_10_400_B3B3B3>
        <div className="mt-2 space-y-1">
          {benefits.map((benefit, index) => (
            <div key={index} className="flex items-center gap-1.5">
              <span className="text-[#757575] text-[10px]">•</span>
              <Text_10_400_B3B3B3 className="text-[10px]">{benefit}</Text_10_400_B3B3B3>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function DeployModelHardwareMode() {
  const {
    hardwareMode,
    setHardwareMode,
    updateHardwareMode,
    selectedModel,
    setDeploymentSpecification,
    deploymentSpecifcation,
  } = useDeployModel();
  const { openDrawerWithStep, openDrawer } = useDrawer();

  // Local state to manage selection before saving to store
  const [selectedMode, setSelectedMode] = useState<"dedicated" | "shared">(
    hardwareMode || "dedicated"
  );

  // Check if model is embedding or audio type (skip template for these)
  const isEmbeddingModel = selectedModel?.supported_endpoints?.embedding?.enabled;
  const hasAudioTranscription = selectedModel?.supported_endpoints?.audio_transcription?.enabled;
  const hasAudioSpeech = selectedModel?.supported_endpoints?.audio_speech?.enabled;
  const isAudioModel = hasAudioTranscription || hasAudioSpeech;
  const skipTemplateStep = isEmbeddingModel || isAudioModel;

  // Get max context length for default values
  const getMaxContextLength = () => {
    const DEFAULT_MAX = 32000;
    if (isAudioModel && selectedModel?.architecture_audio_config) {
      const { max_source_positions, max_target_positions } =
        selectedModel.architecture_audio_config;
      const sum = (max_source_positions || 0) + (max_target_positions || 0);
      return sum > 0 ? sum : DEFAULT_MAX;
    }
    return selectedModel?.architecture_text_config?.context_length || DEFAULT_MAX;
  };

  return (
    <BudForm
      data={{}}
      disableNext={!selectedMode}
      onNext={async () => {
        // Save the selected mode to store
        setHardwareMode(selectedMode);

        // Persist hardware mode to backend
        await updateHardwareMode();

        // Skip template selection for embedding/audio models
        if (skipTemplateStep) {
          // Set default deployment specs since no template is selected
          const maxContext = getMaxContextLength();
          setDeploymentSpecification({
            ...deploymentSpecifcation,
            avg_context_length: maxContext,
            avg_sequence_length: Math.min(maxContext, 2000), // Reasonable default
            per_session_tokens_per_sec: [10, 50],
            ttft: [50, 200],
            e2e_latency: [100, 500],
          });
          openDrawerWithStep("deploy-model-specification");
        } else {
          openDrawerWithStep("deploy-model-template");
        }
      }}
      onBack={() => {
        openDrawer("deploy-model");
      }}
      backText="Back"
      nextText="Next"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Hardware Resource Mode"
            description="Choose how your model will use compute resources. This affects performance, cost, and resource sharing."
          />

          <div className="pt-[.6rem]">
            <HardwareModeCard
              mode="dedicated"
              title="Dedicated Hardware"
              description="Exclusive GPU/CPU allocation for your deployment only. Guarantees consistent performance with zero resource contention."
              icon="/images/deployRocket.png"
              badge="Recommended"
              badgeColor="blue"
              benefits={[
                "Best performance and predictability",
                "No resource sharing or context switching",
                "Ideal for production workloads",
                "Higher cost per deployment",
              ]}
              selected={selectedMode === "dedicated"}
              onClick={() => setSelectedMode("dedicated")}
            />

            <HardwareModeCard
              mode="shared"
              title="Shared Hardware"
              description="Multiple deployments share the same hardware through efficient scheduling."
              icon="/images/gift.png"
              badge="Cost Efficient"
              badgeColor="green"
              benefits={[
                "Lower cost per deployment",
                "Better resource utilization",
                "Ideal for development and testing",
                "Slight performance overhead from context switching",
              ]}
              selected={selectedMode === "shared"}
              onClick={() => setSelectedMode("shared")}
            />
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { Checkbox, Spin } from "antd";
import React, { useState, useEffect } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { errorToast } from "@/components/toast";
import { useCloudProviders } from "src/hooks/useCloudProviders";
import useGuardrails from "src/hooks/useGuardrails";
import {
  Text_12_400_757575,
  Text_14_400_EEEEEE,
  Text_12_400_B3B3B3,
  Text_14_600_FFFFFF,
} from "@/components/ui/text";
import IconRender from "../components/BudIconRender";

interface ProviderOption {
  id: string;
  name: string;
  description: string;
  category: "bud" | "third-party";
}

const providers: ProviderOption[] = [
  {
    id: "bud-sentinel",
    name: "Bud Sentinel",
    description:
      "Over 300+ Probes with the best Accuracy with latency than 10ms.",
    category: "bud",
  },
  {
    id: "custom-probe",
    name: "Create custom probe",
    description:
      "Create your custom probe with Bud sentinel for tools, agents, prompts, models or routes.",
    category: "bud",
  },
  {
    id: "azure-ai-foundry",
    name: "Azure AI Foundry",
    description:
      "Over 300+ Probes with the best Accuracy with latency than 10ms.",
    category: "third-party",
  },
  {
    id: "aws-bedrock",
    name: "AWS Bedrock",
    description:
      "Over 300+ Probes with the best Accuracy with latency than 10ms.",
    category: "third-party",
  },
];

export default function SelectProvider() {
  const { openDrawerWithStep } = useDrawer();
  const [selectedProvider, setSelectedProvider] = useState<string>("");
  const [selectedProviderData, setSelectedProviderData] = useState<any>(null);
  const [isCreatingWorkflow, setIsCreatingWorkflow] = useState(false);

  // Use the cloud providers hook to fetch providers from API
  const {
    providers: apiProviders,
    loading,
    getProviders,
  } = useCloudProviders();

  // Use guardrails hook for workflow
  const { createWorkflow, workflowLoading, setSelectedProvider: setSelectedProviderInStore } = useGuardrails();

  // Fetch providers on mount
  useEffect(() => {
    getProviders(1, 50, undefined, "moderation"); // Fetch first 50 providers with moderation capability
  }, []);

  const handleProviderSelect = (providerId: string, providerData?: any) => {
    setSelectedProvider(providerId);
    setSelectedProviderData(providerData);
    // Save provider to store for use in other steps
    setSelectedProviderInStore(providerData || { id: providerId });
  };

  const handleNext = async () => {
    if (!selectedProvider) {
      errorToast("Please select a provider");
      return;
    }

    // Custom probe flow: skip workflow creation here, it happens in SelectProbeType
    if (selectedProvider === "custom-probe") {
      openDrawerWithStep("select-probe-type");
      return;
    }

    setIsCreatingWorkflow(true);

    try {
      // Determine provider_type based on the selected provider's type
      let providerType = "cloud"; // Default to cloud

      if (selectedProviderData?.type === "bud_sentinel") {
        providerType = "bud";
      } else if (selectedProviderData?.type) {
        // For any other type that's not bud_sentinel, use cloud
        providerType = "cloud";
      }

      // Create workflow with the selected provider and provider_type
      await createWorkflow(selectedProvider, providerType);

      // Navigate to the Probes List screen — cloud providers use dedicated flow
      openDrawerWithStep(providerType === "cloud" ? "cloud-select-probes" : "bud-sentinel-probes");
    } catch (error) {
      console.error("Failed to create workflow:", error);
    } finally {
      setIsCreatingWorkflow(false);
    }
  };

  // Filter API providers for Bud section (exclude only aws_comprehend)
  const budProviders =
    apiProviders?.filter(
      (p) => p.type?.toLowerCase() !== "aws_comprehend"
    ) || [];

  // Add custom probe option to bud providers
  const customProbeOption = {
    id: "custom-probe",
    name: "Create custom probe",
    description:
      "Create your custom probe with Bud sentinel for tools, agents, prompts, models or routes.",
    icon: "⚙️",
    type: "custom",
  };

  const allBudProviders = budProviders.length > 0
    ? [budProviders[0], customProbeOption, ...budProviders.slice(1)]
    : [customProbeOption];

  // Keep static third-party providers for now
  const thirdPartyProviders = providers.filter(
    (p) => p.category === "third-party",
  );

  return (
    <BudForm
      data={{}}
      disableNext={!selectedProvider || isCreatingWorkflow || workflowLoading}
      onNext={handleNext}
      nextText={isCreatingWorkflow || workflowLoading ? "Creating..." : "Next"}
      showBack={false}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Select your Provider"
            description="We highly recommend using the Bud Sentinel probe, if it already exists with us as it provides the best accuracy in the least possible latency."
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem] text-[#B3B3B3]"
          />

          <div className="px-[1.35rem] pb-[1.35rem]">
            {/* Bud Section */}
            <div className="mb-[1.5rem] mt-[1.5rem]">
              {/* <Text_14_600_FFFFFF className="mb-[1rem]">Bud</Text_14_600_FFFFFF> */}
              {loading ? (
                <div className="flex justify-center py-[2rem]">
                  <Spin size="default" />
                </div>
              ) : (
                <div className="space-y-[0.75rem]">
                  {allBudProviders.map((provider) => (
                    <div
                      key={provider.id}
                      className={`p-[1rem] border rounded-[8px] cursor-pointer transition-all ${
                        selectedProvider === provider.id
                          ? "border-[#965CDE] bg-[#965CDE10]"
                          : "border-[#1F1F1F] hover:border-[#757575] bg-[#FFFFFF08]"
                      }`}
                      onClick={() =>
                        handleProviderSelect(provider.id, provider)
                      }
                    >
                      <div className="flex items-start gap-[0.75rem]">
                        {/* Icon for provider */}
                        <div className="mt-[2px]">
                          <IconRender
                            icon={provider.icon}
                            size={32}
                            imageSize={20}
                            type={provider.type}
                          />
                        </div>

                        <div className="flex-1">
                          <Text_14_400_EEEEEE className="mb-[0.25rem]">
                            {provider.name}
                          </Text_14_400_EEEEEE>
                          <Text_12_400_757575 className="leading-[1.4]">
                            {provider.description ||
                              "Cloud provider for model deployments"}
                          </Text_12_400_757575>
                        </div>

                        <Checkbox
                          checked={selectedProvider === provider.id}
                          className="AntCheckbox mt-[2px]"
                          onChange={(e) => {
                            e.stopPropagation();
                            handleProviderSelect(provider.id, provider);
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Third Party Section */}
            <div className="hidden">
              <Text_14_600_FFFFFF className="mb-[1rem]">
                Third party
              </Text_14_600_FFFFFF>
              <div className="space-y-[0.75rem]">
                {thirdPartyProviders.map((provider) => (
                  <div
                    key={provider.id}
                    className={`p-[1rem] border rounded-[8px] cursor-pointer transition-all ${
                      selectedProvider === provider.id
                        ? "border-[#965CDE] bg-[#965CDE10]"
                        : "border-[#1F1F1F] hover:border-[#757575] bg-[#FFFFFF08]"
                    }`}
                    onClick={() => handleProviderSelect(provider.id)}
                  >
                    <div className="flex items-start gap-[0.75rem]">
                      <Checkbox
                        checked={selectedProvider === provider.id}
                        className="AntCheckbox mt-[2px]"
                        onChange={(e) => {
                          e.stopPropagation();
                          handleProviderSelect(provider.id);
                        }}
                      />
                      <div className="flex-1">
                        <Text_14_400_EEEEEE className="mb-[0.25rem]">
                          {provider.name}
                        </Text_14_400_EEEEEE>
                        <Text_12_400_757575 className="leading-[1.4]">
                          {provider.description}
                        </Text_12_400_757575>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

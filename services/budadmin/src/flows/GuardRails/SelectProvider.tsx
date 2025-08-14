import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { Checkbox } from "antd";
import React, { useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { errorToast } from "@/components/toast";
import {
  Text_12_400_757575,
  Text_14_400_EEEEEE,
  Text_12_400_B3B3B3,
  Text_14_600_FFFFFF,
} from "@/components/ui/text";

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
    description: "Over 300+ Probes with the best Accuracy with latency than 10ms.",
    category: "bud",
  },
  {
    id: "custom-probe",
    name: "Create custom probe",
    description: "Create your custom probe with Bud sentinel for tools, agents, prompts, models or routes.",
    category: "bud",
  },
  {
    id: "azure-ai-foundry",
    name: "Azure AI Foundry",
    description: "Over 300+ Probes with the best Accuracy with latency than 10ms.",
    category: "third-party",
  },
  {
    id: "aws-bedrock",
    name: "AWS Bedrock",
    description: "Over 300+ Probes with the best Accuracy with latency than 10ms.",
    category: "third-party",
  },
];

export default function SelectProvider() {
  const { openDrawerWithStep } = useDrawer();
  const [selectedProvider, setSelectedProvider] = useState<string>("");

  const handleProviderSelect = (providerId: string) => {
    setSelectedProvider(providerId);
  };

  const handleNext = () => {
    if (!selectedProvider) {
      errorToast("Please select a provider");
      return;
    }

    // Navigate to the appropriate next step based on provider
    if (selectedProvider === "azure-ai-foundry") {
      openDrawerWithStep("politeness-detection");
    } else {
      // For other providers, we can add different flows later
      openDrawerWithStep("politeness-detection");
    }
  };

  const budProviders = providers.filter(p => p.category === "bud");
  const thirdPartyProviders = providers.filter(p => p.category === "third-party");

  return (
    <BudForm
      data={{}}
      disableNext={!selectedProvider}
      onNext={handleNext}
      nextText="Next"
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
            <div className="mb-[1.5rem]">
              <Text_14_600_FFFFFF className="mb-[1rem]">Bud</Text_14_600_FFFFFF>
              <div className="space-y-[0.75rem]">
                {budProviders.map((provider) => (
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

            {/* Third Party Section */}
            <div>
              <Text_14_600_FFFFFF className="mb-[1rem]">Third party</Text_14_600_FFFFFF>
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

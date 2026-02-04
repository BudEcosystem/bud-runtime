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
  Text_14_600_FFFFFF,
} from "@/components/ui/text";

interface ProbeTypeOption {
  id: string;
  name: string;
  description: string;
}

const probeTypes: ProbeTypeOption[] = [
  {
    id: "rule-based",
    name: "Create probe with policy",
    description:
      "You can define your own LLM policy",
  },
  // {
  //   id: "dataset",
  //   name: "Custom probe with dataset",
  //   description:
  //     "You can upload your custom dataset to train a classifier based probe.",
  // },
];

export default function SelectProbeType() {
  const { openDrawerWithStep } = useDrawer();
  const [selectedType, setSelectedType] = useState<string>("");

  const handleBack = () => {
    openDrawerWithStep("select-provider");
  };

  const handleNext = () => {
    if (!selectedType) {
      errorToast("Please select a probe type");
      return;
    }

    if (selectedType === "rule-based") {
      openDrawerWithStep("add-custom-guardrail");
    } else if (selectedType === "dataset") {
      openDrawerWithStep("upload-dataset");
    }
  };

  return (
    <BudForm
      data={{}}
      disableNext={!selectedType}
      onBack={handleBack}
      onNext={handleNext}
      backText="Back"
      nextText="Next"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Create Custom Probe"
            description="Create a custom probe for guardrailing Agents, prompts or models either by uploading your dataset or by setting custom rules."
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem] text-[#B3B3B3]"
          />

          <div className="px-[1.35rem] pb-[1.35rem] pt-[1.5rem]">
            <div className="space-y-[0.75rem]">
              {probeTypes.map((type) => (
                <div
                  key={type.id}
                  className={`p-[1rem] border rounded-[8px] cursor-pointer transition-all ${
                    selectedType === type.id
                      ? "border-[#965CDE] bg-[#965CDE10]"
                      : "border-[#1F1F1F] hover:border-[#757575] bg-[#FFFFFF08]"
                  }`}
                  onClick={() => setSelectedType(type.id)}
                >
                  <div className="flex items-start gap-[0.75rem]">
                    <Checkbox
                      checked={selectedType === type.id}
                      className="AntCheckbox mt-[2px]"
                      onChange={(e) => {
                        e.stopPropagation();
                        setSelectedType(type.id);
                      }}
                    />
                    <div className="flex-1">
                      <Text_14_600_FFFFFF className="mb-[0.25rem]">
                        {type.name}
                      </Text_14_600_FFFFFF>
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

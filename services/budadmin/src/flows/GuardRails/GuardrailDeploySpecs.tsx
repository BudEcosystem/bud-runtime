import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import {
  Text_14_400_EEEEEE,
} from "@/components/ui/text";

export default function GuardrailDeploySpecs() {
  const { openDrawerWithStep } = useDrawer();

  const handleBack = () => {
    openDrawerWithStep("guardrail-hardware-mode");
  };

  const handleNext = () => {
    openDrawerWithStep("guardrail-select-cluster");
  };

  return (
    <BudForm
      data={{}}
      onBack={handleBack}
      onNext={handleNext}
      backText="Back"
      nextText="Next"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Deployment Specifications"
            description="Configure deployment specifications for guardrail models"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem] text-[#B3B3B3]"
          />
          <div className="px-[1.35rem] pb-[1.35rem] pt-[1.5rem]">
            <div className="flex items-center justify-center py-[4rem]">
              <Text_14_400_EEEEEE className="text-[#757575]">
                Deployment specifications — coming soon
              </Text_14_400_EEEEEE>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

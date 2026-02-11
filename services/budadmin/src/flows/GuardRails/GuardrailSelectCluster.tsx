import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import {
  Text_14_400_EEEEEE,
} from "@/components/ui/text";

export default function GuardrailSelectCluster() {
  const { openDrawerWithStep } = useDrawer();

  const handleBack = () => {
    openDrawerWithStep("guardrail-deploy-specs");
  };

  const handleNext = () => {
    openDrawerWithStep("deployment-types");
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
            title="Select Cluster"
            description="Select a cluster for guardrail model deployment"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem] text-[#B3B3B3]"
          />
          <div className="px-[1.35rem] pb-[1.35rem] pt-[1.5rem]">
            <div className="flex items-center justify-center py-[4rem]">
              <Text_14_400_EEEEEE className="text-[#757575]">
                Cluster selection — coming soon
              </Text_14_400_EEEEEE>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import {
  ChooseModalitySource,
  ChooseModelSource,
} from "@/components/ui/bud/dataEntry/forAddModel/ChooseModelSource";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useDeployModel } from "src/stores/useDeployModel";

export default function ChooseModality() {
  const {
    modalityType,
    createModalityForWorkflow,
    currentWorkflow,
    updateProviderType,
    createLocalModelWorkflow,
    updateProviderTypeLocal,
    setCloudModelDetails,
    setLocalModelDetails,
  } = useDeployModel();

  const { openDrawerWithStep, previousStep } = useDrawer();

  const navigate = async () => {
    if (modalityType.id) {
      // const result = await createModalityForWorkflow();
      // if (!result) {
      //   return;
      // }
      openDrawerWithStep("model-source");
    }
  };

  return (
    <BudForm
      data={{
        name: "",
        description: "",
        tags: [],
        icon: "😍",
      }}
      nextText="Next"
      disableNext={!modalityType?.id}
      onNext={async () => {
        navigate();
      }}
      onBack={previousStep ? () => openDrawerWithStep(previousStep) : undefined}
    >
      <BudWraperBox center>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Select Modality"
            description="Pick the modality for which you would like to add the model"
          />
          <ChooseModalitySource />
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

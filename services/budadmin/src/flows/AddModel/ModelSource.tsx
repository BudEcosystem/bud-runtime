import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { ChooseModelSource } from "@/components/ui/bud/dataEntry/forAddModel/ChooseModelSource";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useDeployModel } from "src/stores/useDeployModel";

export default function ModelSource() {
  const {
    providerType,
    createCloudModelWorkflow,
    currentWorkflow,
    updateProviderType,
    createLocalModelWorkflow,
    updateProviderTypeLocal,
    setCloudModelDetails,
    setLocalModelDetails,
    modalityType
  } = useDeployModel();

  const { openDrawerWithStep, previousStep } = useDrawer();

  const navigate = async () => {
    if (providerType.id === "cloud_model") {
      const result = await createCloudModelWorkflow();
      if (!result) {
        return;
      }

      setCloudModelDetails({
        name: "",
        description: "",
        tags: [],
        icon: "🌐",
      });
      openDrawerWithStep("cloud-providers");
    } else {
      const result = await createLocalModelWorkflow();
      if (!result) {
        return;
      }

      setLocalModelDetails({
        name: "",
        description: "",
        tags: [],
        icon:
          currentWorkflow?.workflow_steps?.provider?.type == "huggingface"
            ? ""
            : "",
      });

      // Check if Document modality and Hugging Face are selected
      if (modalityType?.id === "document" && providerType?.id === "hugging_face") {
        openDrawerWithStep("document-model-list");
      } else {
        openDrawerWithStep("add-local-model");
      }
    }
  };

  return (
    <BudForm
      data={{
        name: "",
        description: "",
        tags: [],
        icon: "🌐",
      }}
      nextText="Next"
      disableNext={!providerType?.id}
      onNext={async () => {
        navigate();
      }}
      backText="Back"
      onBack={() => openDrawerWithStep("modality-source")}
    >
      <BudWraperBox center>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Select Model"
            description="Pick the source from which you would like to add the model"
          />
          <ChooseModelSource />
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

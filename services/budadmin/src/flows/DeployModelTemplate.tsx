import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DeployModelSpecificationInfo from "@/components/ui/bud/deploymentDrawer/DeployModelSpecificationInfo";
import DeployModelTemplateSelect from "@/components/ui/bud/deploymentDrawer/DeployModelTemplateSelect";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useDeployModel } from "src/stores/useDeployModel";

export default function DeployModelTemplate() {
  const { selectedTemplate, currentWorkflow, updateTemplate } =
    useDeployModel();
  const { openDrawer, openDrawerWithStep } = useDrawer();

  return (
    <BudForm
      data={{}}
      disableNext={!selectedTemplate}
      onNext={async (values) => {
        if (!currentWorkflow) {
          openDrawer("deploy-model");
        } else {
          await updateTemplate();
          openDrawerWithStep("deploy-model-specification");
        }
      }}
      onBack={() => {
        // Check if it's a cloud model or local model to navigate to the correct previous step
        if (currentWorkflow?.workflow_steps?.model?.provider_type === "cloud_model") {
          openDrawerWithStep("deploy-model-credential-select");
        } else {
          // For local models, go back to hardware mode selection
          openDrawerWithStep("deploy-model-hardware-mode");
        }
      }}
      backText="Back"
      nextText="Next"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DeployModelSpecificationInfo showTemplate={false} />
        </BudDrawerLayout>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Select Deployment templates"
            description="Templates help you set up deployments quickly. Choose one that matches your use case or create your own."
          />
          <DeployModelTemplateSelect />
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

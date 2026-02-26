/**
 * DeploymentName - Step 2 of the Deploy Use Case wizard
 *
 * Simple form for entering the deployment name.
 * Uses the same TextInput pattern as the Add Huggingface Model flow.
 */

import React from "react";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import TextInput from "src/flows/components/TextInput";
import { useUseCases } from "src/stores/useUseCases";
import { useDrawer } from "src/hooks/useDrawer";

export default function DeploymentName() {
  const { selectedTemplate, deploymentName, setDeploymentName } = useUseCases();
  const { openDrawerWithStep } = useDrawer();

  return (
    <BudForm
      data={{ deploymentName }}
      onBack={() => openDrawerWithStep("deploy-usecase-select-template")}
      backText="Back"
      nextText="Next"
      disableNext={!deploymentName.trim()}
      onNext={() => openDrawerWithStep("deploy-usecase-select-cluster")}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Deployment Name"
            description={`Name your deployment of "${selectedTemplate?.display_name || "template"}".`}
          />
          <DrawerCard>
            <TextInput
              name="deploymentName"
              label="Deployment Name"
              placeholder={`e.g. my-${selectedTemplate?.name || "usecase"}-deployment`}
              rules={[{ required: true, message: "Please enter a deployment name" }]}
              infoText="A unique name to identify this deployment"
              onChange={(value) => setDeploymentName(value)}
            />
          </DrawerCard>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

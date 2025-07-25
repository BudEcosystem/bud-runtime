
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DeployModelSpecificationInfo from "@/components/ui/bud/deploymentDrawer/DeployModelSpecificationInfo";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useDeployModel } from "src/stores/useDeployModel";
import ProprietaryCredentialsFormList from "../components/ProprietaryCredentialsFormList";

export default function DeployModelCredentialSelect() {
  const { selectedCredentials } = useDeployModel();
  const { currentWorkflow, updateCredentials } = useDeployModel();
  const { openDrawer, openDrawerWithStep } = useDrawer();

  return (
    <BudForm
      data={{}}
      disableNext={!selectedCredentials?.id}
      onNext={async () => {
        if (!currentWorkflow) {
          openDrawer("deploy-model");
        } else {
          await updateCredentials(selectedCredentials);
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
          <DeployModelSpecificationInfo showTemplate={false} showCredentials={false} />
        </BudDrawerLayout>
        <ProprietaryCredentialsFormList
            providerType={currentWorkflow?.workflow_steps?.model?.source}
          />
      </BudWraperBox>
    </BudForm>
  );
}

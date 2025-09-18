import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import ProprietaryCredentialsFormList from "src/flows/components/ProprietaryCredentialsFormList";
import { useDeployModel } from "src/stores/useDeployModel";

export default function SelectOrAddCredentials() {
  const { openDrawerWithStep, openDrawer } = useDrawer();
  const { selectedCredentials, currentWorkflow, updateCredentialsLocal } =
    useDeployModel();

  return (
    <BudForm
      data={{}}
      onNext={async () => {
        if (!currentWorkflow) {
          openDrawer("deploy-model");
        } else {
          const result = await updateCredentialsLocal(selectedCredentials);
          if (result) {
            openDrawerWithStep("extracting-model-status");
          }
          //   openDrawer('run-model-evaluations');
        }
      }}
      onBack={() => {
        openDrawerWithStep("add-local-model");
      }}
      backText="Back"
      nextText="Next"
    >
      <BudWraperBox>
        <ProprietaryCredentialsFormList
          providerType={currentWorkflow?.workflow_steps?.provider?.type}
        />
      </BudWraperBox>
    </BudForm>
  );
}

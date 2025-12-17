import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DeployModelSpecificationInfo from "@/components/ui/bud/deploymentDrawer/DeployModelSpecificationInfo";
import React, { useEffect } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import ProprietaryCredentialsFormList from "../components/ProprietaryCredentialsFormList";
import { usePerfomanceBenchmark } from "src/stores/usePerfomanceBenchmark";
import { useDeployModel } from "src/stores/useDeployModel";

export default function AddBenchmarkCredentialSelect() {
  const { currentWorkflow, updateCredentials } = usePerfomanceBenchmark();
  const { openDrawer, openDrawerWithStep } = useDrawer();
  const { selectedCredentials, setSelectedCredentials } = useDeployModel();
  useEffect(() => {
    console.log("selectedCredentials", selectedCredentials);
  }, [selectedCredentials]);
  return (
    <BudForm
      data={{}}
      disableNext={!selectedCredentials?.id}
      onNext={async () => {
        if (!currentWorkflow) {
          return;
        } else {
          await updateCredentials(selectedCredentials);
          openDrawerWithStep("Select-Configuration");
        }
      }}
      onBack={() => {
        openDrawerWithStep("Select-Model");
      }}
      backText="Back"
      nextText="Next"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          {/* <></> */}
          <DeployModelSpecificationInfo
            showTemplate={false}
            showCredentials={false}
          />
        </BudDrawerLayout>
        <ProprietaryCredentialsFormList
          providerType={currentWorkflow?.workflow_steps?.model?.source}
          provider={currentWorkflow?.workflow_steps?.model?.provider}
        />
      </BudWraperBox>
    </BudForm>
  );
}

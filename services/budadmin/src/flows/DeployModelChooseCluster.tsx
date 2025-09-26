import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import ChooseCluster from "@/components/ui/bud/deploymentDrawer/ChooseCluster";
import DeployModelSpecificationInfo from "@/components/ui/bud/deploymentDrawer/DeployModelSpecificationInfo";
import React from "react";
import { useCluster } from "src/hooks/useCluster";
import { useDrawer } from "src/hooks/useDrawer";
import { useDeployModel } from "src/stores/useDeployModel";

export default function DeployModelChooseCluster() {
  const { openDrawerWithStep } = useDrawer();
  const { deploymentCluster, updateCluster } = useDeployModel();
  const { recommendedCluster, getRecommendedClusterById, currentProcessId } =
    useCluster();

  return (
    <BudForm
      data={{}}
      onBack={() => {
        openDrawerWithStep("deploy-model-specification");
      }}
      onNext={async (values) => {
        const result = await updateCluster();
        if (result) {
          openDrawerWithStep("deploy-model-configuration", { direction: "forward" });
        }
      }}
      nextText="Next"
      backText="Back"
      disableNext={!deploymentCluster?.id}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DeployModelSpecificationInfo />
        </BudDrawerLayout>
        <BudDrawerLayout>
          <ChooseCluster />
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

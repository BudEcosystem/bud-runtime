import React, { useEffect } from "react";

import { useDrawer } from "src/hooks/useDrawer";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";

import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import BudStepAlert from "src/flows/components/BudStepAlert";
import { useDeployModel } from "src/stores/useDeployModel";
import { useEndPoints } from "src/hooks/useEndPoint";
import { useWorkers } from "src/hooks/useWorkers";
import { useRouter } from "next/router";

const AddWorkerSuccess: React.FC = () => {
  const { closeDrawer } = useDrawer();
  const { currentWorkflow, getWorkflow } = useDeployModel();
  const { getEndpointClusterDetails } = useEndPoints();
  const { getWorkers } = useWorkers();
  const router = useRouter();
  const projectId = router.query.projectId as string
  React.useEffect(() => {
    getWorkflow();
  }, []);

  useEffect(() => {
    if (currentWorkflow?.workflow_steps?.endpoint?.id) {
      getEndpointClusterDetails(currentWorkflow?.workflow_steps?.endpoint?.id, projectId);
      getWorkers(currentWorkflow?.workflow_steps?.endpoint?.id, projectId);
    }
  }, [currentWorkflow]);

  return (
    <BudForm
      data={{
      }}
      nextText={"View Workers"}
      onNext={async () => {
        closeDrawer();
      }}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <BudStepAlert
            title="Deployment successful"
            description={`Additional workers has been successfully added in the deployment.`}
            type="success"
          />
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
};

export default AddWorkerSuccess;

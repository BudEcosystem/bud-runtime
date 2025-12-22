import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import BudStepAlert from "src/flows/components/BudStepAlert";
import { useDeployModel } from "src/stores/useDeployModel";
import CommonStatus from "src/flows/components/CommonStatus";
import { useWorkers } from "src/hooks/useWorkers";
import { useRouter } from "next/router";

export default function AddWorkerDeployStatus() {
  const [isFailed, setIsFailed] = React.useState(false);
  const [showAlert, setShowAlert] = React.useState(false);
  const { currentWorkflow } = useDeployModel();
  const { openDrawerWithStep, closeDrawer } = useDrawer();
  const { getWorkers } = useWorkers();
  const router = useRouter();
  const projectId = router.query.projectId as string;

  if (!currentWorkflow?.workflow_id) {
    return null;
  }

  return (
    <BudForm
      data={{}}
      backText={isFailed ? "Close" : "Cancel"}
      onBack={() => {
        if (isFailed) {
          closeDrawer();
        } else {
          setShowAlert(true);
        }
      }}
    >
      <BudWraperBox>
        {showAlert && (
          <BudDrawerLayout>
            <BudStepAlert
              type="warning"
              title="You're about to stop the deployment process"
              description="We highly recommend that you continue the process to deploy the workers"
              cancelText="Continue Scanning"
              confirmText="Cancel Anyways"
              confirmAction={() => {
                // TODO: Add cancel action
                closeDrawer();
                getWorkers(
                  currentWorkflow?.workflow_steps?.endpoint?.id,
                  projectId,
                );
              }}
              cancelAction={() => {
                setShowAlert(false);
              }}
            />
          </BudDrawerLayout>
        )}
        <CommonStatus
          workflowId={currentWorkflow?.workflow_id}
          events_field_id="bud_serve_cluster_events"
          success_payload_type="add_worker"
          onCompleted={() => {
            openDrawerWithStep("add-worker-success");
          }}
          onFailed={() => {
            setIsFailed(true);
          }}
          title="Deploying the workers"
          description={
            "We’ve started deploying workers. This process may take a while, depending on your configuration. Feel free to minimize the screen we’ll notify you once it’s done."
          }
        />
      </BudWraperBox>
    </BudForm>
  );
}

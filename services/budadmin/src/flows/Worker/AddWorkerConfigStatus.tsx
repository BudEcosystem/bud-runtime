import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import BudStepAlert from "src/flows/components/BudStepAlert";
import { useDeployModel } from "src/stores/useDeployModel";
import CommonStatus from "src/flows/components/CommonStatus";

export default function AddWorkerConfigStatus() {
  const [isFailed, setIsFailed] = React.useState(false);
  const [showAlert, setShowAlert] = React.useState(false);
  const { currentWorkflow } = useDeployModel();
  const { openDrawerWithStep, closeDrawer } = useDrawer();

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
              title="You're about to stop finding the hardware for deployment"
              description="We highly recommend that you continue the process to find the best hardware for the required concurrency"
              cancelText="Continue Scanning"
              confirmText="Cancel Anyways"
              confirmAction={() => {
                openDrawerWithStep("add-worker-cluster-config");
              }}
              cancelAction={() => {
                setShowAlert(false);
              }}
            />
          </BudDrawerLayout>
        )}
        <CommonStatus
          workflowId={currentWorkflow?.workflow_id}
          events_field_id="bud_simulator_events"
          success_payload_type="get_cluster_recommendations"
          onCompleted={() => {
            openDrawerWithStep("add-worker-cluster-config");
          }}
          onFailed={() => {
            setIsFailed(true);
          }}
          title="Finding the hardware for deployment"
          description={
            "Based on the deployment specification, we are calculating what will be the best hardware for the required concurrency"
          }
        />
      </BudWraperBox>
    </BudForm>
  );
}

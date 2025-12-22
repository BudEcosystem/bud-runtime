import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useState } from "react";
import { useCluster } from "src/hooks/useCluster";
import { useDrawer } from "src/hooks/useDrawer";
import { useDeployModel } from "src/stores/useDeployModel";
import BudStepAlert from "./components/BudStepAlert";
import CommonStatus from "./components/CommonStatus";

export default function DeployClusterStatus() {
  const { getRecommendedClusterById } = useCluster();
  const { currentWorkflow } = useDeployModel();
  const { openDrawerWithStep } = useDrawer();
  const [showAlert, setShowAlert] = React.useState(false);
  const [isFailed, setIsFailed] = React.useState(false);

  return (
    <BudForm
      data={{}}
      // onBack={() => {
      //   openDrawerWithStep("deploy-model-specification");
      // }}
      // backText="Back"
      backText={isFailed ? "Back" : "Cancel"}
      onBack={() => {
        if (isFailed) {
          openDrawerWithStep("deploy-model-specification");
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
              title="You're about to cancel the finding best clusters process"
              description="Please note that if you cancel now, you will have to start the process again."
              cancelText="Continue Finding"
              confirmText="Cancel Anyways"
              confirmAction={() => {
                // TODO: Add cancel action
                openDrawerWithStep("deploy-model-specification");
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
            getRecommendedClusterById(currentWorkflow?.workflow_id).then(
              (result) => {
                if (result) {
                  openDrawerWithStep("deploy-model-choose-cluster");
                }
              },
            );
          }}
          onFailed={() => {
            setIsFailed(true);
          }}
          title="Finding best clusters for deployment"
          description="Based on the deployment specification and clusters available, we are calculating what will be the best clusters to deploy on."
        />
      </BudWraperBox>
    </BudForm>
  );
}

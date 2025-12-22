import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React from "react";
import { useCluster } from "src/hooks/useCluster";
import { useDrawer } from "src/hooks/useDrawer";
import { useWorkflow } from "src/stores/useWorkflow";
import BudStepAlert from "./components/BudStepAlert";
import CommonStatus from "./components/CommonStatus";
import { successToast } from "@/components/toast";
import { useDeployModel } from "src/stores/useDeployModel";

export default function CreateClusterStatus() {
  const { currentWorkflow, cancelClusterOnboarding } = useDeployModel();
  const { openDrawerWithStep, closeDrawer } = useDrawer();
  const { refresh } = useCluster();
  const [showAlert, setShowAlert] = React.useState(false);
  const [isFailed, setIsFailed] = React.useState(false);

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
              title="You're about to cancel the cluster creation process"
              description="Please note that this will stop the process of adding the cluster to the repository"
              cancelText="Continue Creating"
              confirmText="Cancel Anyways"
              confirmAction={async () => {
                if (currentWorkflow?.workflow_id) {
                  const response = await cancelClusterOnboarding(
                    currentWorkflow?.workflow_id,
                  );
                  if (response) {
                    successToast("Cluster onboarding cancelled successfully");
                    closeDrawer();
                    return;
                  }
                }
                closeDrawer();
              }}
              cancelAction={() => {
                setShowAlert(false);
              }}
            />
          </BudDrawerLayout>
        )}
        <CommonStatus
          workflowId={currentWorkflow?.workflow_id}
          events_field_id="create_cluster_events"
          onCompleted={() => {
            refresh();
            openDrawerWithStep("create-cluster-success");
          }}
          onFailed={() => {
            setIsFailed(true);
          }}
          success_payload_type="register_cluster"
          title={"Adding cluster to the repository"}
          description={
            <>In process of verification, downloading and scanning the model</>
          }
        />
      </BudWraperBox>
    </BudForm>
  );
}

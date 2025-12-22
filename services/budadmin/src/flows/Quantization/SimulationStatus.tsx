import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import BudStepAlert from "../components/BudStepAlert";
import CommonStatus from "../components/CommonStatus";
import { useDeployModel } from "src/stores/useDeployModel";
import { useCluster } from "src/hooks/useCluster";

export default function SimulationStatus() {
  const { openDrawerWithStep, closeDrawer } = useDrawer();
  const { currentWorkflow } = useDeployModel();
  const { getRecommendedClusterById } = useCluster();
  const [isFailed, setIsFailed] = React.useState(false);
  const [showAlert, setShowAlert] = React.useState(false);

  const handleBack = () => {
    if (isFailed) {
      openDrawerWithStep("advanced-settings");
    } else {
      closeDrawer();
    }
  };

  return (
    <BudForm
      data={{}}
      backText={isFailed ? "Back" : "Cancel"}
      onBack={handleBack}
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
                openDrawerWithStep("advanced-settings");
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
                  openDrawerWithStep("quantization-select-cluster");
                }
              },
            );
          }}
          onFailed={() => {
            setIsFailed(true);
          }}
          title="Finding best clusters for quantization"
          description="Based on the quantization specification and clusters available, we are calculating what will be the best clusters to run quantization on."
        />
      </BudWraperBox>
    </BudForm>
  );
}

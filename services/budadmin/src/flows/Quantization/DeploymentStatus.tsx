import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import BudStepAlert from "../components/BudStepAlert";
import CommonStatus from "../components/CommonStatus";
import { useDeployModel } from "src/stores/useDeployModel";
import { useCluster } from "src/hooks/useCluster";
import { successToast } from "@/components/toast";

export default function DeploymentStatus() {
  const { openDrawerWithStep, closeDrawer } = useDrawer();
  const { currentWorkflow, cancelQuantizationDeployment } = useDeployModel();
  const { getRecommendedClusterById } = useCluster();
  const [isFailed, setIsFailed] = React.useState(false);
  const [showAlert, setShowAlert] = React.useState(false);

  const handleBack = () => {
    if (isFailed) {
      openDrawerWithStep("quantization-select-cluster");
    } else {
      setShowAlert(true);
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
              title="You're about to cancel the quantization process"
              description="Please note that if you cancel now, you will have to start the process again."
              cancelText="Continue Finding"
              confirmText="Cancel Anyways"
              confirmAction={async () => {
                if (currentWorkflow?.workflow_id) {
                  const response = await cancelQuantizationDeployment(
                    currentWorkflow?.workflow_id,
                  );
                  if (response) {
                    successToast("Quantization cancelled successfully");
                    closeDrawer();
                    return;
                  }
                }
                openDrawerWithStep("quantization-select-cluster");
              }}
              cancelAction={() => {
                setShowAlert(false);
              }}
            />
          </BudDrawerLayout>
        )}
        <CommonStatus
          workflowId={currentWorkflow?.workflow_id}
          events_field_id="quantization_deployment_events"
          success_payload_type="deploy_quantization"
          onCompleted={() => {
            console.log("completed");
            openDrawerWithStep("quantization-result");
          }}
          onFailed={() => {
            setIsFailed(true);
          }}
          title="Quantizing the model"
          description="We've started quantising the model. This process may take a while, depending on the model size. Feel free to minimize the screen, we'll notify you once it's done."
        />
      </BudWraperBox>
    </BudForm>
  );
}

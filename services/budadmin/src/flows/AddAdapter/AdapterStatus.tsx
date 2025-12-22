import { successToast } from "@/components/toast";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import BudStepAlert from "../components/BudStepAlert";
import CommonStatus from "../components/CommonStatus";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useDeployModel } from "src/stores/useDeployModel";

export const AdapterStatus = () => {
  const { openDrawerWithStep, closeDrawer } = useDrawer();
  const { currentWorkflow, cancelQuantizationDeployment } = useDeployModel();

  const [isFailed, setIsFailed] = React.useState(false);
  const [showAlert, setShowAlert] = React.useState(false);

  const handleBack = () => {
    if (isFailed) {
      openDrawerWithStep("add-adapter-detail");
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
              title="You're about to cancel the deployment process"
              description="Please note that if you cancel now, you will have to start the process again."
              cancelText="Continue Finding"
              confirmText="Cancel Anyways"
              confirmAction={async () => {
                if (currentWorkflow?.workflow_id) {
                  const response = await cancelQuantizationDeployment(
                    currentWorkflow?.workflow_id,
                  );
                  if (response) {
                    successToast("Adapter deployment cancelled successfully");
                    closeDrawer();
                    return;
                  }
                }
                openDrawerWithStep("add-adapter-detail");
              }}
              cancelAction={() => {
                setShowAlert(false);
              }}
            />
          </BudDrawerLayout>
        )}
        <CommonStatus
          workflowId={currentWorkflow?.workflow_id}
          events_field_id="adapter_deployment_events"
          success_payload_type="add_adapter"
          onCompleted={() => {
            openDrawerWithStep("add-adapter-result");
          }}
          onFailed={() => {
            setIsFailed(true);
          }}
          title="Deploying the adapter"
          description="We've started deploying the adapter. This process may take a while, depending on the model size. Feel free to minimize the screen, we'll notify you once it's done."
        />
      </BudWraperBox>
    </BudForm>
  );
};

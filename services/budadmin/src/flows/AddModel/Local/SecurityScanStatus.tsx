import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import BudStepAlert from "src/flows/components/BudStepAlert";
import { useDeployModel } from "src/stores/useDeployModel";
import SelectedModeInfoCard from "src/flows/components/SelectedModeInfoCard";
import CommonStatus from "src/flows/components/CommonStatus";
import { useModels } from "src/hooks/useModels";

export default function SecurityScanning() {
  const [isFailed, setIsFailed] = React.useState(false);
  const [showAlert, setShowAlert] = React.useState(false);
  const { currentWorkflow } = useDeployModel();
  const { openDrawerWithStep, closeDrawer } = useDrawer();
  const { refresh } = useModels();

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
          setTimeout(() => {
            document
              .querySelector(".scrollBox")
              ?.scrollTo({ top: 0, behavior: "smooth" });
          }, 0);
        }
      }}
    >
      <BudWraperBox>
        {showAlert && (
          <BudDrawerLayout>
            <BudStepAlert
              type="warning"
              title="You're about to stop the security scanning process."
              description="We highly recommend that you continue the scanning process. However, if you cancel now, you can also perform a security scan before deployment."
              cancelText="Continue Scanning"
              confirmText="Cancel Anyways"
              confirmAction={() => {
                // TODO: Add cancel action
                refresh();
                closeDrawer();
              }}
              cancelAction={() => {
                setShowAlert(false);
              }}
            />
          </BudDrawerLayout>
        )}
        <SelectedModeInfoCard />
        <CommonStatus
          workflowId={currentWorkflow?.workflow_id}
          events_field_id="model_security_scan_events"
          onCompleted={() => {
            openDrawerWithStep("model-scan-completed");
          }}
          onFailed={() => {
            setIsFailed(true);
          }}
          success_payload_type="perform_model_scanning"
          // success_payload_type="perform_model_security_scan"
          title="Security Scanning In Progress"
          description={
            "Wise choice, this scan will give you the information on how secure is this model."
          }
          extraInfo={
            "This may take sometime, you can minimize this side screen and continue with the rest of your work. In-order to see your progress on your model uploading, you can visit the notification centre."
          }
        />
      </BudWraperBox>
    </BudForm>
  );
}

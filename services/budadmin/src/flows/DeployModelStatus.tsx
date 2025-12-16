import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useDeployModel } from "src/stores/useDeployModel";
import BudStepAlert from "./components/BudStepAlert";
import CommonStatus from "./components/CommonStatus";
import { errorToast, successToast } from "@/components/toast";
import { useRouter } from "next/router";

export default function DeployModeStatus() {
  const { currentWorkflow, cancelModelDeployment } = useDeployModel();
  const { openDrawerWithStep, closeDrawer, isFailed, setFailed } = useDrawer();
  const [showAlert, setShowAlert] = React.useState(false);
  const router = useRouter();
  const projectId = router.query.projectId as string;
  return (
    <BudForm
      data={{}}
      onBack={async () => {
        if (isFailed) {
          openDrawerWithStep("deploy-model-auto-scaling");
        } else {
          setShowAlert(true);
        }
      }}
      backText={isFailed ? "Back" : "Cancel"}
    >
      <BudWraperBox>
        {/* {isFailed && <BudDrawerLayout>
          <BudStepAlert
            type="failed"
            title="Deployment Failed"
            description="Oops! Something went wrong while deploying the model. Please try again."
            confirmText="Try Again"
            confirmAction={() => {
              // TODO: Add cancel action
              openDrawerWithStep("deploy-model-specification");
            }}
          />
        </BudDrawerLayout>} */}
        {showAlert && (
          <BudDrawerLayout>
            <BudStepAlert
              type="warning"
              title="You're about to cancel the deployment process"
              description="Please note that if you cancel now, you will have to start the process again."
              cancelText="Continue Deployment"
              confirmText="Cancel Anyways"
              confirmAction={async () => {
                if (currentWorkflow?.workflow_id) {
                  const response = await cancelModelDeployment(
                    currentWorkflow?.workflow_id,
                    projectId,
                  );
                  if (response) {
                    successToast("Deployment cancelled successfully");
                    closeDrawer();
                    return;
                  }
                }
                // TODO: Add cancel action
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
          events_field_id="budserve_cluster_events"
          onCompleted={() => {
            openDrawerWithStep("deploy-model-success");
          }}
          onFailed={() => {
            setFailed(true);
          }}
          success_payload_type="deploy_model"
          title={"Deployment In Progress"}
          description={
            <>
              We’ve started deploying{" "}
              {currentWorkflow?.workflow_steps?.model?.name} in{" "}
              {currentWorkflow?.workflow_steps?.cluster?.name || "Cluster"}.
              This process may take a while, depending on your configuration.
              Feel free to minimize the screen we’ll notify you once it’s done.
            </>
          }
        />
      </BudWraperBox>
    </BudForm>
  );
}

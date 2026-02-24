import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import useGuardrails from "src/hooks/useGuardrails";
import BudStepAlert from "src/flows/components/BudStepAlert";
import CommonStatus from "src/flows/components/CommonStatus";

export default function GuardrailDeploymentStatus() {
  const [showAlert, setShowAlert] = React.useState(false);
  const { closeDrawer, openDrawerWithStep } = useDrawer();
  const { currentWorkflow } = useGuardrails();
  const [isFailed, setIsFailed] = React.useState(false);

  return (
    <BudForm
      data={{}}
      onBack={() => {
        if (isFailed) {
          closeDrawer();
        } else {
          setShowAlert(true);
        }
      }}
      backText={isFailed ? "Close" : "Cancel"}
    >
      <BudWraperBox center={false}>
        {showAlert && (
          <BudDrawerLayout>
            <BudStepAlert
              type="warning"
              title="You're about to stop the deployment"
              description="If the deployment is stopped, the guardrail models will not be deployed to the cluster."
              cancelText="Continue Deployment"
              confirmText="Cancel Anyways"
              confirmAction={() => {
                closeDrawer();
              }}
              cancelAction={() => {
                setShowAlert(false);
              }}
            />
          </BudDrawerLayout>
        )}
        {isFailed && (
          <BudDrawerLayout>
            <BudStepAlert
              type="failed"
              title="Deployment Failed!"
              description="The guardrail model deployment failed. Please try again."
              confirmText="Go Back"
              confirmAction={() => {
                openDrawerWithStep("guardrail-select-cluster");
              }}
            />
          </BudDrawerLayout>
        )}
        <CommonStatus
          workflowId={currentWorkflow?.workflow_id}
          events_field_id="guardrail_deployment_events"
          onCompleted={() => {
            openDrawerWithStep("probe-deployment-success");
          }}
          onFailed={() => {
            setIsFailed(true);
          }}
          success_payload_type="guardrail_deployment"
          title="Deploying Guardrail Models"
          description={
            <>
              Deploying the guardrail models to the selected cluster. This
              includes provisioning resources and starting the inference
              services.
            </>
          }
          extraInfo="This may take some time..."
        />
      </BudWraperBox>
    </BudForm>
  );
}

import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import useGuardrails from "src/hooks/useGuardrails";
import BudStepAlert from "src/flows/components/BudStepAlert";
import CommonStatus from "src/flows/components/CommonStatus";

export default function GuardrailOnboardingStatus() {
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
              title="You're about to stop the onboarding process"
              description="If the onboarding process is stopped, the guardrail models will not be added to the repository."
              cancelText="Continue Onboarding"
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
              title="Model Onboarding Failed!"
              description="We were not able to onboard the guardrail models. Please try again."
              confirmText="Go Back"
              confirmAction={() => {
                openDrawerWithStep("guardrail-select-credentials");
              }}
            />
          </BudDrawerLayout>
        )}
        <CommonStatus
          workflowId={currentWorkflow?.workflow_id}
          events_field_id="guardrail_onboarding_events"
          onCompleted={() => {
            openDrawerWithStep("deployment-types");
          }}
          onFailed={() => {
            setIsFailed(true);
          }}
          success_payload_type="guardrail_model_onboarding"
          title="Onboarding Guardrail Models"
          description={
            <>
              In process of verification, downloading and onboarding the
              guardrail models required for the selected probes.
            </>
          }
          extraInfo="This may take some time..."
        />
      </BudWraperBox>
    </BudForm>
  );
}

import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import useGuardrails from "src/hooks/useGuardrails";
import BudStepAlert from "src/flows/components/BudStepAlert";
import CommonStatus from "src/flows/components/CommonStatus";

export default function GuardrailSimulationStatus() {
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
              title="You're about to stop the simulation"
              description="If the simulation is stopped, you will need to restart the deployment specifications step."
              cancelText="Continue Simulation"
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
              title="Simulation Failed!"
              description="The simulation process failed. Please try again."
              confirmText="Go Back"
            />
          </BudDrawerLayout>
        )}
        <CommonStatus
          workflowId={currentWorkflow?.workflow_id}
          events_field_id="guardrail_simulation_events"
          onCompleted={() => {
            openDrawerWithStep("guardrail-select-cluster");
          }}
          onFailed={() => {
            setIsFailed(true);
          }}
          success_payload_type="guardrail_simulation"
          title="Running Simulation"
          description={
            <>
              Running performance simulation to determine optimal cluster
              configuration for your guardrail models.
            </>
          }
          extraInfo="This may take some time..."
        />
      </BudWraperBox>
    </BudForm>
  );
}

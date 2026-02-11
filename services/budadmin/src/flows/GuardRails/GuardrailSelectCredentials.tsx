import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useDeployModel } from "src/stores/useDeployModel";
import useGuardrails from "src/hooks/useGuardrails";
import ProprietaryCredentialsFormList from "../components/ProprietaryCredentialsFormList";

export default function GuardrailSelectCredentials() {
  const { openDrawerWithStep } = useDrawer();
  const { selectedCredentials } = useDeployModel();
  const {
    updateWorkflow,
    workflowLoading,
    currentWorkflow,
    selectedProvider,
  } = useGuardrails();

  // Get the provider type for credentials from workflow response
  // After step 3, the backend derives model info from probe_selections + project_id
  const providerType =
    currentWorkflow?.models?.[0]?.source ||
    currentWorkflow?.model_source ||
    currentWorkflow?.provider_type ||
    selectedProvider?.provider_type ||
    "huggingface";

  const handleBack = () => {
    openDrawerWithStep("select-project");
  };

  const handleNext = async () => {
    if (!selectedCredentials?.id) return;

    try {
      const payload: any = {
        step_number: 4,
        credential_id: selectedCredentials.id,
        trigger_workflow: false,
      };

      if (currentWorkflow?.workflow_id) {
        payload.workflow_id = currentWorkflow.workflow_id;
      }

      if (selectedProvider?.id) {
        payload.provider_id = selectedProvider.id;
      }
      if (selectedProvider?.provider_type) {
        payload.provider_type = selectedProvider.provider_type;
      }

      if (currentWorkflow?.probe_selections) {
        payload.probe_selections = currentWorkflow.probe_selections;
      }

      if (currentWorkflow?.project_id) {
        payload.project_id = currentWorkflow.project_id;
      }

      const success = await updateWorkflow(payload);
      if (success) {
        openDrawerWithStep("guardrail-onboarding-status");
      }
    } catch (error) {
      console.error("Failed to update workflow:", error);
    }
  };

  return (
    <BudForm
      data={{}}
      onBack={handleBack}
      onNext={handleNext}
      backText="Back"
      nextText="Next"
      disableNext={!selectedCredentials?.id || workflowLoading}
    >
      <BudWraperBox>
        <ProprietaryCredentialsFormList providerType={providerType} />
      </BudWraperBox>
    </BudForm>
  );
}

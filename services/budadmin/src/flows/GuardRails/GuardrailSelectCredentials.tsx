import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useDeployModel } from "src/stores/useDeployModel";
import useGuardrails from "src/hooks/useGuardrails";
import ProprietaryCredentialsFormList from "../components/ProprietaryCredentialsFormList";

export default function GuardrailSelectCredentials() {
  const { openDrawerWithStep, currentFlow } = useDrawer();
  const isCloudFlow = currentFlow === "add-guardrail-cloud";
  const { selectedCredentials } = useDeployModel();
  const {
    updateWorkflow,
    workflowLoading,
    currentWorkflow,
    selectedProvider,
  } = useGuardrails();

  // Get the credential provider type from workflow model info (not the guardrail provider_type which is "bud")
  const providerType =
    currentWorkflow?.models?.[0]?.source ||
    currentWorkflow?.model_source ||
    "huggingface";

  const handleBack = () => {
    openDrawerWithStep(isCloudFlow ? "cloud-select-project" : "select-project");
  };

  const handleNext = async () => {
    if (!selectedCredentials?.id) return;

    try {
      // Backend accumulates data across steps, so only send step-specific fields
      const payload: any = {
        step_number: 4,
        credential_id: selectedCredentials.id,
      };

      const success = await updateWorkflow(payload);
      if (success) {
        if (isCloudFlow) {
          // Cloud flow: no onboarding step, go straight to deployment types
          openDrawerWithStep("cloud-deployment-types");
        } else {
          // Bud Sentinel flow: check if models need onboarding
          const { modelsRequiringOnboarding } = useGuardrails.getState();
          if (modelsRequiringOnboarding > 0) {
            openDrawerWithStep("guardrail-onboarding-status");
          } else {
            openDrawerWithStep("deployment-types");
          }
        }
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

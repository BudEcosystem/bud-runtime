
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DeploymentSpecificationConfig from "@/components/ui/bud/deploymentDrawer/DeploymentSpecificationConfig";
import DeployModelSpecificationInfo from "@/components/ui/bud/deploymentDrawer/DeployModelSpecificationInfo";
import React, { useContext } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useDeployModel } from "src/stores/useDeployModel";

export default function DeployModelSpecification() {
  const { selectedTemplate, selectedModel } = useDeployModel()
  const { deploymentSpecifcation, updateDeploymentSpecification, updateDeploymentSpecificationAndDeploy, currentWorkflow } = useDeployModel()

  // Check if model is embedding or audio type (these skip template selection)
  const isEmbeddingModel = selectedModel?.supported_endpoints?.embedding?.enabled;
  const hasAudioTranscription = selectedModel?.supported_endpoints?.audio_transcription?.enabled;
  const hasAudioSpeech = selectedModel?.supported_endpoints?.audio_speech?.enabled;
  const hasChatEndpoint = selectedModel?.supported_endpoints?.chat?.enabled;
  const hasCompletionEndpoint = selectedModel?.supported_endpoints?.completion?.enabled;

  const isAudioModel = hasAudioTranscription || hasAudioSpeech;
  const skipTemplateStep = isEmbeddingModel || isAudioModel;
  // Hide for pure audio models (transcription/TTS) that don't have chat/completion
  const hideContextSequence = isAudioModel && !hasChatEndpoint && !hasCompletionEndpoint;
  const { openDrawer, openDrawerWithStep, closeDrawer } = useDrawer();
  const {form} = useContext(BudFormContext);

  return (
    <BudForm
      data={{
        deployment_name: deploymentSpecifcation.deployment_name,
        concurrent_requests: deploymentSpecifcation.concurrent_requests,
        avg_context_length: deploymentSpecifcation.avg_context_length,
        avg_sequence_length: deploymentSpecifcation.avg_sequence_length,
        per_session_tokens_per_sec: deploymentSpecifcation.per_session_tokens_per_sec,
        ttft: deploymentSpecifcation.ttft,
        e2e_latency: deploymentSpecifcation.e2e_latency,
      }}
      disableNext={
        !deploymentSpecifcation.deployment_name ||
        !deploymentSpecifcation.concurrent_requests ||
        // Only require sequence length when context/sequence fields are visible
        (!hideContextSequence && !deploymentSpecifcation.avg_sequence_length)
      }
      onNext={async (values) => {
        // form.submit();
        if (currentWorkflow) {
          // Check if it's a cloud model and skip cluster steps
          if (currentWorkflow.workflow_steps.model.provider_type === "cloud_model") {
            const result = await updateDeploymentSpecificationAndDeploy();
            if (result) {
              openDrawerWithStep("deploy-model-success");
            }
            return;
          }

          // For local models, continue with cluster finding
          const result = await updateDeploymentSpecification();
          if (result) {
            openDrawerWithStep("deploy-cluster-status");
          }
          return;
        }
        openDrawer("deploy-model");
      }}
      onBack={() => {
        // Skip template step for embedding/audio models
        if (skipTemplateStep) {
          openDrawerWithStep("deploy-model-hardware-mode");
        } else {
          openDrawerWithStep("deploy-model-template");
        }
      }}
      backText="Back"
      nextText="Next"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DeployModelSpecificationInfo
            showDeployInfo={false}
          />
        </BudDrawerLayout>
        <BudDrawerLayout>
          <DeploymentSpecificationConfig />
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

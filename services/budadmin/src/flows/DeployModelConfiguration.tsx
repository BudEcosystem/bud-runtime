import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DeploymentConfigurationForm from "@/components/ui/bud/deploymentDrawer/DeploymentConfigurationForm";
import DeployModelSpecificationInfo from "@/components/ui/bud/deploymentDrawer/DeployModelSpecificationInfo";
import React, { useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useDeployModel } from "src/stores/useDeployModel";

export default function DeployModelConfiguration() {
  const { currentWorkflow, deploymentConfiguration, setDeploymentConfiguration, updateDeploymentConfiguration, deploymentCluster } = useDeployModel();
  const { openDrawer, openDrawerWithStep, drawerProps } = useDrawer();
  const [hasAvailableParsers, setHasAvailableParsers] = useState(false);

  useEffect(() => {
    // Check workflow_steps from API response for parser metadata
    const workflowSteps = currentWorkflow?.workflow_steps;

    // Check if simulator metadata contains parser information
    const simulatorEvents = workflowSteps?.bud_simulator_events;
    const simulatorMetadata = simulatorEvents?.metadata || {};

    // Also check the selected cluster for parser metadata as fallback
    const clusterMetadata = deploymentCluster || {};

    // Priority: Workflow steps from API > Simulator metadata > Current cluster metadata
    const toolParserType = (workflowSteps as any)?.tool_calling_parser_type || simulatorMetadata.tool_calling_parser_type || clusterMetadata.tool_calling_parser_type;
    const reasoningParserType = (workflowSteps as any)?.reasoning_parser_type || simulatorMetadata.reasoning_parser_type || clusterMetadata.reasoning_parser_type;
    const chatTemplate = (workflowSteps as any)?.chat_template || simulatorMetadata.chat_template || clusterMetadata.chat_template;

    // Extract capability flags with same priority
    const supportsLora = (workflowSteps as any)?.supports_lora ?? simulatorMetadata.supports_lora ?? clusterMetadata.supports_lora ?? false;
    const supportsPP = (workflowSteps as any)?.supports_pipeline_parallelism ?? simulatorMetadata.supports_pipeline_parallelism ?? clusterMetadata.supports_pipeline_parallelism ?? false;

    const hasToolParser = !!toolParserType;
    const hasReasoningParser = !!reasoningParserType;

    setHasAvailableParsers(hasToolParser || hasReasoningParser);

    // Update configuration with available parsers and capability flags from either source
    // Merge only derived fields; preserve user toggles in state
    setDeploymentConfiguration({
      available_tool_parser: toolParserType || null,
      available_reasoning_parser: reasoningParserType || null,
      chat_template: chatTemplate || null,
      supports_lora: supportsLora,
      supports_pipeline_parallelism: supportsPP,
    });

    // If no parsers available, skip this step based on navigation direction
    if (!hasToolParser && !hasReasoningParser) {
      const navigationDirection = drawerProps?.direction;

      if (navigationDirection === "backward") {
        // Coming from auto-scaling, go back to choose cluster
        openDrawerWithStep("deploy-model-choose-cluster");
      } else {
        // Coming from choose cluster or direct navigation, go forward to auto-scaling
        openDrawerWithStep("deploy-model-auto-scaling");
      }
    }
  }, [currentWorkflow]);

  return (
    <BudForm
      data={{
        // Prefer workflow values on refresh; fall back to store
        enable_tool_calling:
          (currentWorkflow?.workflow_steps as any)?.enable_tool_calling ??
          deploymentConfiguration?.enable_tool_calling ??
          false,
        enable_reasoning:
          (currentWorkflow?.workflow_steps as any)?.enable_reasoning ??
          deploymentConfiguration?.enable_reasoning ??
          false,
      }}
      onNext={async (values) => {
        // Save configuration (merged in store)
        setDeploymentConfiguration({
          enable_tool_calling: values.enable_tool_calling,
          enable_reasoning: values.enable_reasoning,
        });

        // Update via API with explicit values to avoid race
        const result = await updateDeploymentConfiguration({
          enable_tool_calling: values.enable_tool_calling,
          enable_reasoning: values.enable_reasoning,
        });
        if (result) {
          openDrawerWithStep("deploy-model-auto-scaling");
        }
      }}
      onBack={() => {
        openDrawerWithStep("deploy-model-choose-cluster");
      }}
      backText="Back"
      nextText="Next"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DeployModelSpecificationInfo
            showTemplate={true}
            showDeployInfo={false}
          />
        </BudDrawerLayout>
        {hasAvailableParsers && (
          <BudDrawerLayout>
            <DrawerTitleCard
              title="Configure Deployment Features"
              description="Enable advanced features for your model deployment. These features enhance the capabilities of your deployed model."
            />
            <DeploymentConfigurationForm />
          </BudDrawerLayout>
        )}
      </BudWraperBox>
    </BudForm>
  );
}

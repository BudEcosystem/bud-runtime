import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { Checkbox } from "antd";
import React, { useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { errorToast } from "@/components/toast";
import useGuardrails from "src/hooks/useGuardrails";
import { Text_14_400_EEEEEE } from "@/components/ui/text";

type DeploymentType = "guardrail-endpoint" | "existing-deployment" | "";

export default function DeploymentTypes() {
  const { openDrawerWithStep } = useDrawer();
  const [selectedType, setSelectedType] = useState<DeploymentType>("");

  // Use the guardrails hook
  const {
    updateWorkflow,
    workflowLoading,
    currentWorkflow,
    selectedProvider,
    selectedProbes,
    selectedProbe,
    setIsStandaloneDeployment
  } = useGuardrails();

  const handleBack = () => {
    // Get the selected probes
    const probesArray = selectedProbes?.length > 0 ? selectedProbes : (selectedProbe ? [selectedProbe] : []);

    // Check if any selected probe is a PII probe (same logic as BudSentinelProbes)
    const hasPIIProbe = probesArray.some(probe =>
      probe.name?.toLowerCase().includes("personal identifier") ||
      probe.name?.toLowerCase().includes("pii") ||
      probe.tags?.some(
        (tag: any) =>
          tag.name.toLowerCase().includes("dlp") ||
          tag.name.toLowerCase().includes("personal"),
      )
    );

    // Navigate back based on whether PII probes were selected
    if (hasPIIProbe) {
      openDrawerWithStep("pii-detection-config");
    } else {
      openDrawerWithStep("bud-sentinel-probes");
    }
  };

  const handleNext = async () => {
    if (!selectedType) {
      errorToast("Please select a deployment type");
      return;
    }

    try {
      // Map the selected type to deployment_type value and is_standalone
      const deploymentTypeMapping: Record<DeploymentType, { deployment_type: string; is_standalone: boolean }> = {
        "guardrail-endpoint": { deployment_type: "endpoint_mapped", is_standalone: true },
        "existing-deployment": { deployment_type: "existing_deployment", is_standalone: false },
        "": { deployment_type: "", is_standalone: false },
      };

      const mappedValues = deploymentTypeMapping[selectedType];

      // Store the standalone flag in the store (persists across workflow updates)
      setIsStandaloneDeployment(mappedValues.is_standalone);

      // Build the complete workflow payload
      const payload: any = {
        step_number: 3, // Deployment type selection is step 3
        deployment_type: mappedValues.deployment_type,
        is_standalone: mappedValues.is_standalone,
        trigger_workflow: false,
      };

      // Include workflow_id if available
      if (currentWorkflow?.workflow_id) {
        payload.workflow_id = currentWorkflow.workflow_id;
      }

      // Include provider data from previous steps
      if (selectedProvider?.id) {
        payload.provider_id = selectedProvider.id;
      }
      if (selectedProvider?.provider_type) {
        payload.provider_type = selectedProvider.provider_type;
      }

      // Include probe selections from previous steps
      if (currentWorkflow?.probe_selections) {
        // Use existing probe_selections from workflow (which should have rules)
        payload.probe_selections = currentWorkflow.probe_selections;
      } else {
        // Fallback: build from selectedProbes if needed
        const probesArray = selectedProbes?.length > 0 ? selectedProbes : (selectedProbe ? [selectedProbe] : []);
        if (probesArray.length > 0) {
          payload.probe_selections = probesArray.map(probe => ({
            id: probe.id
          }));
        }
      }

      // Update workflow with complete data
      await updateWorkflow(payload);

      // Both deployment types go to project selection
      openDrawerWithStep("select-project");
    } catch (error) {
      console.error("Failed to update workflow:", error);
    }
  };

  const deploymentOptions = [
    {
      value: "guardrail-endpoint",
      label: "GuardRail Endpoint",
    },
    {
      value: "existing-deployment",
      label: "Add to Existing Deployment",
    },
  ];

  return (
    <BudForm
      data={{}}
      onBack={handleBack}
      onNext={handleNext}
      backText="Back"
      nextText="Next"
      disableNext={!selectedType || workflowLoading}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Deployment Types"
            description="There are two different ways you can deploy a probe. Standalone endpoint exposes the probe as an endpoint that you can use outside the application, or you can add it to an existing deployment to protect that deployment."
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem] text-[#B3B3B3] leading-[1.5]"
          />

          <div className="px-[1.35rem] pb-[1.35rem] mt-[1.5rem]">
            <div className="space-y-[0.75rem]">
              {deploymentOptions.map((option) => (
                <div
                  key={option.value}
                  onClick={() =>
                    setSelectedType(option.value as DeploymentType)
                  }
                  className={`p-[1.5rem] border rounded-[8px] cursor-pointer transition-all ${
                    selectedType === option.value
                      ? "border-[#965CDE] bg-[#965CDE10]"
                      : "border-[#2A2A2A] hover:border-[#757575] bg-[#1A1A1A]"
                  }`}
                >
                  <div className="flex items-center gap-[0.75rem]">
                    <Checkbox
                      checked={selectedType === option.value}
                      onChange={() =>
                        setSelectedType(option.value as DeploymentType)
                      }
                      className="AntCheckbox"
                    />
                    <Text_14_400_EEEEEE>{option.label}</Text_14_400_EEEEEE>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

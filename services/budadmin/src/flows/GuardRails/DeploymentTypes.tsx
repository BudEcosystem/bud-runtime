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
  const { updateWorkflow, workflowLoading } = useGuardrails();

  const handleBack = () => {
    openDrawerWithStep("pii-detection-config");
  };

  const handleNext = async () => {
    if (!selectedType) {
      errorToast("Please select a deployment type");
      return;
    }

    try {
      // Map the selected type to deployment_type value
      const deploymentTypeMapping: Record<DeploymentType, string> = {
        "guardrail-endpoint": "endpoint_mapped",
        "existing-deployment": "existing_deployment",
        "": "",
      };

      // Update workflow with deployment type
      await updateWorkflow({
        step_number: 3, // Deployment type selection is step 3
        deployment_type: deploymentTypeMapping[selectedType],
        trigger_workflow: false,
      });

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

          <div className="px-[1.35rem] pb-[1.35rem]">
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

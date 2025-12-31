import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { Checkbox, Slider, Input } from "antd";
import React, { useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import useGuardrails from "src/hooks/useGuardrails";
import { errorToast } from "@/components/toast";
import {
  Text_12_400_757575,
  Text_14_400_EEEEEE,
  Text_14_600_FFFFFF,
} from "@/components/ui/text";

export default function ProbeSettings() {
  const { openDrawerWithStep } = useDrawer();
  const [selectedLifecycle, setSelectedLifecycle] = useState<string[]>(["input", "output"]);
  const [strictnessLevel, setStrictnessLevel] = useState(0.5);
  const [profileName, setProfileName] = useState("Guardrail Profile");
  const [profileDescription, setProfileDescription] = useState("");

  // Use the guardrails hook
  const { updateWorkflow, workflowLoading, selectedProbe, selectedDeployment, isStandaloneDeployment } =
    useGuardrails();

  const lifecycleOptions = [
    { value: "input", label: "Input" },
    { value: "output", label: "Output" },
    { value: "retrieval", label: "Retrieval" },
    { value: "tools", label: "Tools" },
  ];

  const handleBack = () => {
    // Check if this is a standalone guardrail endpoint (deployment selection was skipped)
    // Use the store flag which was set in DeploymentTypes step
    if (isStandaloneDeployment) {
      // Go back to project selection (deployment was skipped)
      openDrawerWithStep("select-project");
    } else {
      // Normal flow - go back to deployment selection
      openDrawerWithStep("select-deployment");
    }
  };

  const handleDeploy = async () => {
    // Validate required fields
    if (!profileName.trim()) {
      errorToast("Please enter a profile name");
      return;
    }

    if (selectedLifecycle.length === 0) {
      errorToast("Please select at least one lifecycle stage");
      return;
    }

    try {
      // Get all state from store to build complete payload
      const state = useGuardrails.getState();
      const { currentWorkflow, selectedProvider, selectedProject, selectedProbes } = state;

      // Build the complete payload with all required fields
      const payload: any = {
        step_number: 6, // Probe settings is the final step 6
        name: profileName.trim(),
        description: profileDescription.trim() || undefined,
        guard_types: selectedLifecycle,
        severity_threshold: strictnessLevel,
        trigger_workflow: true, // This triggers the actual deployment
      };

      // REQUIRED: Include workflow_id
      if (currentWorkflow?.workflow_id) {
        payload.workflow_id = currentWorkflow.workflow_id;
      } else {
        console.error("Missing workflow_id!");
        errorToast("Workflow ID missing. Please restart the process.");
        return;
      }

      // Include provider data
      payload.provider_type = selectedProvider?.provider_type || currentWorkflow?.provider_type || "bud";
      payload.provider_id = selectedProvider?.id || currentWorkflow?.provider_id;

      if (!payload.provider_id) {
        console.error("Missing provider_id!");
      }

      // Include probe selections with rules from previous steps
      let probeSelections = currentWorkflow?.probe_selections;

      // Try multiple sources for probe_selections
      if (!probeSelections || probeSelections.length === 0) {
        if (currentWorkflow?.workflow_data?.probe_selections) {
          probeSelections = currentWorkflow.workflow_data.probe_selections;
        } else if (selectedProbes && selectedProbes.length > 0) {
          // Reconstruct if needed (note: this is a fallback, ideally probe_selections should come from workflow)
          probeSelections = selectedProbes.map((probe: any) => {
            // Build probe selection object
            const probeSelection: any = { id: probe.id };

            // Add rules if available
            if (probe.rules && Array.isArray(probe.rules)) {
              probeSelection.rules = probe.rules;
            }

            return probeSelection;
          });
        }
      }

      if (probeSelections && probeSelections.length > 0) {
        payload.probe_selections = probeSelections;
      } else {
        console.error("Missing probe_selections!");
        errorToast("Probe selections missing. Please go back and select probes.");
        return;
      }

      // Include is_standalone from the store (set in DeploymentTypes step)
      payload.is_standalone = isStandaloneDeployment;

      // Include project_id
      const projectId = selectedProject?.project?.id || selectedProject?.id || currentWorkflow?.project_id;
      if (projectId) {
        payload.project_id = projectId;
      } else {
        console.error("Missing project_id!");
      }

      // Include endpoint_ids from previous step
      if (currentWorkflow?.endpoint_ids) {
        payload.endpoint_ids = currentWorkflow.endpoint_ids;
      } else if (currentWorkflow?.endpoint_id) {
        // Fallback to single endpoint_id as array
        payload.endpoint_ids = [currentWorkflow.endpoint_id];
      }

      console.log("=== FINAL DEPLOYMENT PAYLOAD (STEP 6) ===");
      console.log(JSON.stringify(payload, null, 2));
      console.log("=========================================");

      // Update workflow with complete payload and trigger deployment
      console.log("Calling updateWorkflow...");
      const success = await updateWorkflow(payload);

      console.log("updateWorkflow returned:", success);

      // Check if the update was successful
      if (success === true) {
        console.log("✅ Workflow update successful, navigating to deployment progress screen");

        // Navigate to deployment progress screen only on success
        openDrawerWithStep("probe-deployment-success");
      } else {
        console.error("❌ Workflow update failed - staying on current page");
        console.error("Success value was:", success, "Type:", typeof success);

        // Error toast is already shown by updateWorkflow function
        // User stays on current page to fix issues
      }
    } catch (error: any) {
      // This catch block should rarely be reached now since updateWorkflow returns false on error
      // But keeping it for any unexpected errors
      console.error("Unexpected error in handleDeploy:", error);

      // Show error message if not already shown
      const errorMessage = error?.response?.data?.detail ||
                          error?.response?.data?.message ||
                          error?.message ||
                          "An unexpected error occurred. Please try again.";

      errorToast(errorMessage);
    }
  };

  const handleLifecycleChange = (value: string, checked: boolean) => {
    if (checked) {
      setSelectedLifecycle([...selectedLifecycle, value]);
    } else {
      setSelectedLifecycle(selectedLifecycle.filter((item) => item !== value));
    }
  };

  const formatSliderValue = (value: number) => {
    return value.toFixed(2);
  };

  return (
    <BudForm
      data={{}}
      onBack={handleBack}
      onNext={handleDeploy}
      backText="Back"
      nextText="Deploy"
      disableNext={selectedLifecycle.length === 0 || workflowLoading}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Probe Settings"
            description={`You are now adding ${selectedProbe?.name || "selected"} Probe to ${selectedDeployment?.name || selectedDeployment?.endpoint_name || "selected"} deployment.`}
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem] text-[#B3B3B3]"
          />

          <div className="px-[1.35rem] pb-[1.35rem]">
            {/* Profile Name and Description Section */}
            <div className="mb-[2rem]">
              <div className="bg-[#ffffff07] border border-[#757575] rounded-[8px] p-[1.5rem]">
                <Text_14_600_FFFFFF className="mb-[1rem]">
                  Guardrail Profile
                </Text_14_600_FFFFFF>

                <div className="mb-[1rem]">
                  <Text_12_400_757575 className="mb-[0.5rem] block">
                    Profile Name *
                  </Text_12_400_757575>
                  <Input
                    placeholder="Enter guardrail profile name"
                    value={profileName}
                    onChange={(e) => setProfileName(e.target.value)}
                    className="bg-transparent text-[#EEEEEE] border-[#757575] hover:border-[#EEEEEE] focus:border-[#EEEEEE]"
                    style={{
                      backgroundColor: "transparent",
                      color: "#EEEEEE",
                    }}
                  />
                </div>

                <div>
                  <Text_12_400_757575 className="mb-[0.5rem] block">
                    Description (Optional)
                  </Text_12_400_757575>
                  <Input.TextArea
                    placeholder="Enter a description for this guardrail profile"
                    value={profileDescription}
                    onChange={(e) => setProfileDescription(e.target.value)}
                    rows={3}
                    className="bg-transparent text-[#EEEEEE] border-[#757575] hover:border-[#EEEEEE] focus:border-[#EEEEEE]"
                    style={{
                      backgroundColor: "transparent",
                      color: "#EEEEEE",
                    }}
                  />
                </div>
              </div>
            </div>

            {/* Add To Section */}
            <div className="mb-[2rem]">
              <div className="bg-[#ffffff07] border border-[#757575] rounded-[8px] p-[1.5rem]">
                <Text_14_600_FFFFFF className="mb-[0.5rem]">
                  Add To:
                </Text_14_600_FFFFFF>
                <Text_12_400_757575 className="mb-[1rem] block">
                  Select which part of Inference lifecycle you would like to add
                  the probe to
                </Text_12_400_757575>

                <div className="flex items-center gap-[2rem] flex-wrap">
                  {lifecycleOptions.map((option) => (
                    <div
                      key={option.value}
                      className="flex items-center gap-[0.5rem]"
                    >
                      <Checkbox
                        checked={selectedLifecycle.includes(option.value)}
                        onChange={(e) =>
                          handleLifecycleChange(option.value, e.target.checked)
                        }
                        className="AntCheckbox"
                      />
                      <Text_14_400_EEEEEE>{option.label}</Text_14_400_EEEEEE>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Strictness Level Section */}
            <div>
              <div className="bg-[#ffffff07] border border-[#757575] rounded-[8px] p-[1.5rem]">
                <Text_14_600_FFFFFF className="mb-[0.5rem]">
                  Strictness Level:
                </Text_14_600_FFFFFF>
                <Text_12_400_757575 className="mb-[1.5rem] block">
                  Level of strictness, the more strict it is more chance for
                  False negatives but better protection
                </Text_12_400_757575>

                <div className="relative px-[1rem]">
                  {/* Slider Value Display */}
                  <div
                    className="absolute -top-[2rem] bg-[#965CDE] text-white px-[0.5rem] py-[0.25rem] rounded-[4px] text-[12px] font-medium"
                    style={{
                      left: `calc(${strictnessLevel * 100}% - 1.5rem)`,
                      transition: "left 0.2s",
                    }}
                  >
                    {formatSliderValue(strictnessLevel)}
                  </div>

                  {/* Slider */}
                  <Slider
                    min={0}
                    max={1}
                    step={0.01}
                    value={strictnessLevel}
                    onChange={(value: number) => setStrictnessLevel(value)}
                    className="mb-[0.5rem] [&_.ant-slider-handle]:!w-[16px] [&_.ant-slider-handle]:!h-[16px] [&_.ant-slider-handle]:!bg-transparent [&_.ant-slider-handle]:!border-transparent [&_.ant-slider-handle]:!shadow-md [&_.ant-slider-handle]:!top-[50%] [&_.ant-slider-handle]:!transform [&_.ant-slider-handle]:!-translate-y-1/2 [&_.ant-slider-track]:!bg-[#965CDE] [&_.ant-slider-rail]:!bg-[#3F3F3F] [&_.ant-slider-track]:!h-[4px] [&_.ant-slider-rail]:!h-[4px]"
                    tooltip={{ open: false }}
                  />

                  {/* Labels */}
                  <div className="flex justify-between mt-[0.5rem]">
                    <Text_12_400_757575>Minimum</Text_12_400_757575>
                    <Text_12_400_757575>Moderate</Text_12_400_757575>
                    <Text_12_400_757575>Maximum</Text_12_400_757575>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

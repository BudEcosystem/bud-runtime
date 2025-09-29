import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useState, useEffect } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Text_12_400_757575, Text_14_400_EEEEEE } from "@/components/ui/text";
import { errorToast } from "@/components/toast";

export default function DeploymentWarning() {
  const { openDrawerWithStep, closeDrawer } = useDrawer();
  const [loading, setLoading] = useState(false);

  // Get stored configuration data
  const [configData, setConfigData] = useState<any>(null);
  const [modelData, setModelData] = useState<any>(null);
  const [projectData, setProjectData] = useState<any>(null);

  useEffect(() => {
    // Retrieve stored data from localStorage
    const config = localStorage.getItem("addAgent_configuration");
    const model = localStorage.getItem("addAgent_selectedModel");
    const project = localStorage.getItem("addAgent_selectedProject");

    if (config) setConfigData(JSON.parse(config));
    if (model) setModelData(JSON.parse(model));
    if (project) setProjectData(JSON.parse(project));
  }, []);

  const handleNext = async () => {
    setLoading(true);
    try {
      // Here you would typically make an API call to create the agent
      // For now, we'll simulate the process

      // Prepare the agent creation payload
      // const agentPayload = {
      //   project_id: projectData?.project?.id || projectData?.id,
      //   model_id: modelData?.id,
      //   name: configData?.deploymentName,
      //   tags: configData?.tags,
      //   description: configData?.description,
      //   configuration: {
      //     min_concurrency: configData?.minConcurrency,
      //     max_concurrency: configData?.maxConcurrency,
      //     auto_scale: configData?.autoScale,
      //     auto_caching: configData?.autoCaching,
      //     auto_logging: configData?.autoLogging,
      //   },
      //   // Auto-scale configuration based on warning
      //   auto_scale_config: {
      //     max_replicas: 8, // As shown in the warning
      //     concurrent_requests: 100,
      //   }
      // };

      // TODO: Replace with actual API call
      // const response = await AppRequest.Post("/agents", agentPayload);
      // Note: projectData will be used in the actual API call

      // Simulate success
      await new Promise(resolve => setTimeout(resolve, 1500));

      // Navigate to success screen (data will be cleared there)
      openDrawerWithStep("add-agent-success");

    } catch (error) {
      console.error("Failed to create agent:", error);
      errorToast("Failed to create agent. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    openDrawerWithStep("add-agent-configuration");
  };

  // Calculate warning details based on configuration
  const concurrentRequests = configData?.maxConcurrency || 10;
  const currentMaxReplicas = configData?.autoScale ? 4 : 1; // Default values
  const recommendedMaxReplicas = 8;
  const deploymentName = modelData?.name || "llama-8";

  return (
    <BudForm
      data={{}}
      onNext={handleNext}
      onBack={handleBack}
      backText="Back"
      nextText={loading ? "Creating..." : "Next"}
      disableNext={loading}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <div className="px-[1.35rem] pt-[1.5rem] pb-[1.35rem]">
            {/* Warning Header */}
            <div style={{ display: "flex", alignItems: "flex-start" }}>
              <img
                src="/images/drawer/warning.png"
                alt="Warning"
                style={{
                  width: "55px",
                  marginRight: 24,
                  marginLeft: 6,
                  marginTop: 11,
                }}
              />
              <div className="flex flex-col gap-y-[12px] pt-[5px]">
                <Text_14_400_EEEEEE>Warning</Text_14_400_EEEEEE>
                <Text_12_400_757575>The deployment is deployed with 100 concurrent request and auto scale to 4 replica which is not sufficient to support the given concurrency for the prompt. Do you like to increase the max replica of the llama-8 deployment auto scaling?</Text_12_400_757575>
              </div>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

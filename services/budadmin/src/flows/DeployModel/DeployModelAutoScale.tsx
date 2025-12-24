import { Image, Switch, ConfigProvider } from "antd";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DeployModelSpecificationInfo from "@/components/ui/bud/deploymentDrawer/DeployModelSpecificationInfo";
import { useDrawer } from "src/hooks/useDrawer";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudDropdownMenu } from "@/components/ui/dropDown";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import { useDeployModel } from "src/stores/useDeployModel";
import TextInput from "../components/TextInput";
import { Text_12_400_EEEEEE, Text_14_400_EEEEEE } from "@/components/ui/text";
import { useState, useEffect } from "react";

export default function DeployModelAutoScale() {
  const { openDrawerWithStep } = useDrawer();
  const {
    scalingSpecifcation,
    setScalingSpecification,
    updateScalingSpecification,
    currentWorkflow,
    selectedModel,
  } = useDeployModel();

  const [advancedSettings, setAdvancedSettings] = useState(false);

  // Get model from workflow or selectedModel to detect embedding models
  const model = currentWorkflow?.workflow_steps?.model || selectedModel;
  // Check if this is an embedding model using supported_endpoints
  const isEmbeddingModel = model?.supported_endpoints?.embedding?.enabled === true;

  // LLM metrics (vLLM, SGLang)
  const llmMetricItems = [
    { label: "TTFT", value: "bud:time_to_first_token_seconds_average" },
    { label: "E2E Latency", value: "bud:e2e_request_latency_seconds_average" },
    { label: "TPOT", value: "bud:time_per_output_token_seconds_average" },
    { label: "GPU Cache Usage", value: "bud:gpu_cache_usage_perc_average" },
  ];

  // Embedding metrics (LatentBud)
  const embeddingMetricItems = [
    { label: "Batch Queue Size", value: "embedding_batch_queue_size" },
    { label: "Active Requests", value: "embedding_requests_active" },
  ];

  // Select metrics based on model type
  const metricItems = isEmbeddingModel ? embeddingMetricItems : llmMetricItems;

  // Reset scaling metric to first available option when model type changes
  useEffect(() => {
    const currentMetric = scalingSpecifcation.scalingMetric;
    const isValidMetric = metricItems.some(item => item.value === currentMetric);

    // If current metric is not valid for this model type, reset to first available
    if (!isValidMetric && metricItems.length > 0) {
      setScalingSpecification({
        ...scalingSpecifcation,
        scalingMetric: metricItems[0].value,
      });
    }
  }, [isEmbeddingModel]);

  const handleChange = (key: string, value: string) => {
    setScalingSpecification({ ...scalingSpecifcation, [key]: value });
  };
  return (
    <BudForm
      data={{
        enabled: scalingSpecifcation.enabled,
        scalingType: scalingSpecifcation.scalingType,
        scalingMetric: scalingSpecifcation.scalingMetric,
        scalingValue: scalingSpecifcation.scalingValue,
        minReplicas: scalingSpecifcation.minReplicas,
        maxReplicas: scalingSpecifcation.maxReplicas,
        scaleUpTolerance: scalingSpecifcation.scaleUpTolerance,
        scaleDownTolerance: scalingSpecifcation.scaleDownTolerance,
        window: scalingSpecifcation.window,
      }}
      onBack={() => {
        openDrawerWithStep("deploy-model-configuration", { direction: "backward" });
      }}
      onNext={async (values) => {
        const result = await updateScalingSpecification();
        if (result) {
          openDrawerWithStep("deploy-model-status");
        }
      }}
      nextText="Deploy"
      backText="Back"
    //   disableNext={!deploymentCluster?.id}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DeployModelSpecificationInfo />
        </BudDrawerLayout>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Autoscaling Configuration"
            description="Set how your inference scales based on usage. Choose the autoscaling type, define the metric and its threshold value, and set the minimum and maximum number of replicas your inference can scale between. This ensures your inference maintains performance while optimizing resource usage."
            classNames="border-[0] border-b-[.5px]"
          />
          <DrawerCard>
            <div className="flex justify-between items-center mt-1">
              <Text_14_400_EEEEEE>Enable Autoscaling</Text_14_400_EEEEEE>
              <ConfigProvider
                theme={{
                  token: {
                    colorPrimary: "#965CDE",
                  },
                }}
              >
                <Switch
                  checked={scalingSpecifcation.enabled}
                  onChange={(checked) => {
                    setScalingSpecification({ ...scalingSpecifcation, enabled: checked });
                  }}
                />
              </ConfigProvider>
            </div>
          </DrawerCard>
          {scalingSpecifcation.enabled && (
            <>
              <DrawerCard>
                {/* Scaling Type hidden - defaulting to "metric" */}
                <BudDropdownMenu
                  name="scalingMetric"
                  label="Scale based on"
                  infoText="Choose the SLO to scale on"
                  placeholder="Scale based on"
                  items={metricItems}
                  onChange={(e) => handleChange("scalingMetric", e)}
                />
                <TextInput
                  name="scalingValue"
                  label="SLO Value"
                  placeholder="Enter SLO Value"
                  rules={[{ required: true, message: "Please enter SLO Value" }]}
                  ClassNames="mt-[.4rem]"
                  infoText="Enter the value of the SLO to scale on"
                  onChange={(e) => handleChange("scalingValue", e)}
                />
                <div className="flex flex-row gap-[1rem] justify-between w-full">
                  <TextInput
                    name="minReplicas"
                    label="Min Replicas"
                    placeholder="Enter Min Replicas"
                    rules={[
                      { required: true, message: "Please enter Min Replicas" },
                    ]}
                    ClassNames="mt-[.4rem]"
                    formItemClassnames="w-full"
                    infoText="Enter the minimum number of replicas your inference can scale down to"
                    onChange={(e) => handleChange("minReplicas", e)}
                  />
                  <TextInput
                    name="maxReplicas"
                    label="Max Replicas"
                    placeholder="Enter Max Replicas"
                    rules={[
                      { required: true, message: "Please enter Max Replicas" },
                    ]}
                    ClassNames="mt-[.4rem]"
                    formItemClassnames="w-full"
                    infoText="Enter the maximum number of replicas your inference can scale up to"
                    onChange={(e) => handleChange("maxReplicas", e)}
                  />
                </div>
                <div
                  className="flex items-center mb-[1rem] cursor-pointer opacity-70 hover:opacity-100"
                  onClick={() => {
                    setAdvancedSettings(!advancedSettings);
                  }}
                >
                  <Text_12_400_EEEEEE className="p-0 py-[.4rem] m-0 mr-[0.5rem]">
                    Advanced Settings
                  </Text_12_400_EEEEEE>
                  <Image
                    src="/icons/customArrow.png"
                    preview={false}
                    alt="info"
                    style={{
                      width: "0.65rem",
                      height: "auto",
                      marginTop: "0.1rem",
                      transform: advancedSettings
                        ? "rotate(180deg)"
                        : "rotate(0deg)",
                      transition: "transform 0.5s ease",
                    }}
                  />
                </div>
              </DrawerCard>

              {advancedSettings && (
                <DrawerCard>
                  <TextInput
                    name="scaleUpTolerance"
                    label="Scale Up Tolerance"
                    placeholder="Enter Scale Up Tolerance"
                    rules={[
                      {
                        required: true,
                        message: "Please enter Scale Up Tolerance",
                      },
                    ]}
                    ClassNames="mt-[.4rem]"
                    infoText="Enter the tolerance for scaling up"
                    onChange={(e) => handleChange("scaleUpTolerance", e)}
                  />
                  <TextInput
                    name="scaleDownTolerance"
                    label="Scale Down Tolerance"
                    placeholder="Enter Scale Down Tolerance"
                    rules={[
                      {
                        required: true,
                        message: "Please enter Scale Down Tolerance",
                      },
                    ]}
                    ClassNames="mt-[.4rem]"
                    infoText="Enter the tolerance for scaling down"
                    onChange={(e) => handleChange("scaleDownTolerance", e)}
                  />
                  <TextInput
                    name="window"
                    label="Window"
                    placeholder="Enter Window"
                    rules={[{ required: true, message: "Please enter Window" }]}
                    ClassNames="mt-[.4rem]"
                    infoText="Enter the window to scale on"
                    onChange={(e) => handleChange("window", e)}
                  />
                </DrawerCard>
              )}
            </>
          )}
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

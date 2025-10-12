import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useState, useEffect } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Form, InputNumber, Switch } from "antd";
import { errorToast } from "@/components/toast";
import TextInput from "../components/TextInput";
import TextAreaInput from "@/components/ui/bud/dataEntry/TextArea";
import InfoLabel from "@/components/ui/bud/dataEntry/InfoLabel";
import { Text_12_400_757575, Text_14_400_EEEEEE } from "@/components/ui/text";
import TagsInput, { Tag } from "@/components/ui/bud/dataEntry/TagsInput";
import { useAddAgent } from "@/stores/useAddAgent";
import { useAgentStore } from "@/stores/useAgentStore";
import { AppRequest } from "src/pages/api/requests";
import { tempApiBaseUrl } from "@/components/environment";

export default function AgentConfiguration() {
  const { openDrawerWithStep } = useDrawer();
  const [form] = Form.useForm();
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Use the Add Agent store for workflow management
  const {
    currentWorkflow,
    selectedProject,
    selectedModel,
    setAgentConfiguration,
    setDeploymentConfiguration,
    setWarningData,
    getWorkflow
  } = useAddAgent();

  // Get the active agent session to retrieve promptId
  const { sessions, activeSessionIds } = useAgentStore();

  // State for form values
  const [deploymentName, setDeploymentName] = useState("");
  const [tags, setTags] = useState<Tag[]>([]);
  const [description, setDescription] = useState("");
  const [minConcurrency, setMinConcurrency] = useState(1);
  const [maxConcurrency, setMaxConcurrency] = useState(10);
  const [autoScale, setAutoScale] = useState(true);
  const [autoCaching, setCaching] = useState(true);
  const [autoLogging, setAutoLogging] = useState(true);
  const [rateLimit, setRateLimit] = useState(false);
  const [rateLimitValue, setRateLimitValue] = useState(10);
  const [triggerWorkflow, setTriggerWorkflow] = useState(false);

  // Load workflow on component mount if it exists
  useEffect(() => {
    if (currentWorkflow?.workflow_id) {
      getWorkflow(currentWorkflow.workflow_id);
    }
  }, [currentWorkflow?.workflow_id, getWorkflow]);

  // Tag options for the tags input
  const tagOptions: Tag[] = [
    { name: "test", color: "#FF6B6B" },
    { name: "production", color: "#4ECDC4" },
    { name: "development", color: "#45B7D1" },
    { name: "staging", color: "#96CEB4" },
    { name: "hardware", color: "#EC7575" },
    { name: "intel", color: "#479D5F" },
    { name: "performance", color: "#DE5CD1" },
  ];

  const handleNext = async () => {
    try {
      await form.validateFields();

      if (!deploymentName) {
        errorToast("Please enter a deployment name");
        return;
      }

      if (tags.length === 0) {
        errorToast("Please add at least one tag");
        return;
      }

      if (!currentWorkflow?.workflow_id) {
        errorToast("Workflow not initialized. Please start from the beginning.");
        return;
      }

      setIsSubmitting(true);

      try {
        // Store configuration data in the Add Agent store
        const configData = {
          name: deploymentName,
          description,
          system_prompt: "", // Will be set in a later step
          temperature: 0.7,
          max_tokens: 2048,
          top_p: 1,
          frequency_penalty: 0,
          presence_penalty: 0,
          tools: [],
          knowledge_base: [],
        };
        setAgentConfiguration(configData);

        // Store deployment configuration in the store
        const deploymentConfig = {
          deploymentName,
          tags,
          description,
          minConcurrency,
          maxConcurrency,
          autoScale,
          autoCaching,
          autoLogging,
          rateLimit,
          rateLimitValue,
          triggerWorkflow,
        };
        setDeploymentConfiguration(deploymentConfig);

        // Prepare the workflow API payload
        const payload: any = {
          workflow_id: currentWorkflow.workflow_id,
          step_number: 4,
          name: deploymentName,
          description: description || "",
          tags: tags,
          auto_scale: autoScale,
          caching: autoCaching,
          concurrency: [minConcurrency, maxConcurrency],
          rate_limit: rateLimit,
          rate_limit_value: rateLimitValue,
          trigger_workflow: triggerWorkflow
        };

        // Get bud_prompt_id from the active agent session
        console.log("=== AgentConfiguration Debug ===");
        console.log("Active sessions:", sessions);
        console.log("Active session IDs:", activeSessionIds);

        // Find the session associated with this workflow
        const activeSession = sessions.find(
          s => s.workflowId === currentWorkflow.workflow_id
        ) || sessions.find(s => activeSessionIds.includes(s.id));

        console.log("Active session for workflow:", activeSession);
        console.log("Session promptId:", activeSession?.promptId);
        console.log("Session selectedDeployment:", activeSession?.selectedDeployment);

        // Use the session's promptId as bud_prompt_id
        const budPromptId = activeSession?.promptId || currentWorkflow.workflow_steps?.bud_prompt_id;

        if (budPromptId) {
          payload.bud_prompt_id = budPromptId;
          console.log("✓ bud_prompt_id included in payload:", payload.bud_prompt_id);
        } else {
          console.warn("⚠ bud_prompt_id is missing! No active session or workflow_steps.bud_prompt_id found");
        }

        // Include endpoint_id from the selected model in LoadModel
        const endpointId = activeSession?.selectedDeployment?.id || activeSession?.modelId;
        if (endpointId) {
          payload.endpoint_id = endpointId;
          console.log("✓ endpoint_id included in payload:", payload.endpoint_id);
        } else {
          console.warn("⚠ endpoint_id is missing! No model selected in LoadModel component");
        }

        console.log("Final payload for step 4:", payload);

        // Call the workflow API for step 4
        const response = await AppRequest.Post(
          `${tempApiBaseUrl}/prompts/prompt-workflow`,
          payload,
          {
            headers: {
              "x-resource-type": "project",
              "x-entity-id": selectedProject?.id || currentWorkflow.workflow_steps?.project?.id
            }
          }
        );

        if (response?.data) {
          // Update the workflow in the store
          await getWorkflow(currentWorkflow.workflow_id);

          // Check if there are warnings or errors in the response
          const hasWarnings = response.data.warnings && response.data.warnings.length > 0;
          const hasErrors = response.data.errors && response.data.errors.length > 0;
          const hasValidationIssues = response.data.validation_issues && response.data.validation_issues.length > 0;

          // Store warning/error data if present
          if (hasWarnings || hasErrors || hasValidationIssues) {
            const warningData = {
              warnings: response.data.warnings || [],
              errors: response.data.errors || [],
              validation_issues: response.data.validation_issues || [],
              recommendations: response.data.recommendations || {}
            };
            setWarningData(warningData);

            // Navigate to the deployment warning screen
            openDrawerWithStep("add-agent-deployment-warning");
          } else {
            // No warnings or errors, clear warning data and go directly to success screen
            setWarningData(null);
            openDrawerWithStep("add-agent-success");
          }
        } else {
          errorToast("Failed to save agent configuration");
        }
      } catch (error) {
        console.error("Failed to save agent configuration:", error);
        errorToast("Failed to save agent configuration");
      } finally {
        setIsSubmitting(false);
      }
    } catch (error) {
      console.error("Validation failed:", error);
    }
  };

  const handleBack = () => {
    openDrawerWithStep("add-agent-select-type");
  };

  return (
    <BudForm
      data={{}}
      onNext={handleNext}
      onBack={handleBack}
      backText="Back"
      nextText="Next"
      disableNext={isSubmitting}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Agent Configuration"
            description="Configure your agent's deployment settings and capabilities"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem] text-[#B3B3B3]"
          />

          <div className="px-[1.35rem] pb-[1.35rem]">
            {/* Deployment Name */}
            <div className="mb-[1.5rem]">
              <TextInput
                label="Deployment Name"
                name="deploymentName"
                placeholder="Enter deployment name"
                rules={[{ required: true, message: "Please enter deployment name" }]}
                value={deploymentName}
                onChange={(value: string) => setDeploymentName(value)}
                ClassNames="mt-[.3rem]"
                formItemClassnames="mb-[1rem]"
                infoText="Enter a unique name for your agent deployment"
                InputClasses="py-[.5rem]"
              />
            </div>

            {/* Tags */}
            <div className="mb-[1.5rem]">
              <Form.Item
                name="tags"
                rules={[{ required: true, message: "Please add at least one tag" }]}
                className="mb-[1rem]"
              >
                <TagsInput
                  label="Tags"
                  options={tagOptions}
                  defaultValue={tags}
                  onChange={setTags}
                  info="Add keywords to help organize and find your agent later"
                  name="tags"
                  required={true} placeholder={""} rules={[]}                />
              </Form.Item>
            </div>

            {/* Description */}
            <div className="mb-[1.5rem]">
              <TextAreaInput
                name="description"
                label="Description"
                required={false}
                info="Provide a detailed description of your agent's purpose and capabilities"
                placeholder="Enter description"
                value={description}
                onChange={(value: string) => setDescription(value)}
                rules={[]}
                formItemClassnames="mb-[1rem]"
              />
            </div>

            {/* Concurrency Settings */}
            <div className="mb-[1.5rem]">
              <InfoLabel
                text="Concurrency"
                content="Set the minimum and maximum concurrent requests"
              />
              <div className="flex gap-[1rem] mt-[.5rem]">
                <div className="flex-1">
                  <Text_12_400_757575 className="mb-[.25rem]">Min</Text_12_400_757575>
                  <InputNumber
                    min={1}
                    max={100}
                    value={minConcurrency}
                    onChange={(value) => setMinConcurrency(value || 1)}
                    controls={false}
                    className="w-full [&_input]:!bg-transparent [&_input]:!text-[#EEEEEE] [&]:!bg-transparent [&]:!border-[#757575] hover:[&]:!border-[#EEEEEE] focus-within:[&]:!border-[#EEEEEE]"
                    style={{
                      backgroundColor: "transparent",
                    }}
                  />
                </div>
                <div className="flex-1">
                  <Text_12_400_757575 className="mb-[.25rem]">Max</Text_12_400_757575>
                  <InputNumber
                    min={1}
                    max={100}
                    value={maxConcurrency}
                    onChange={(value) => setMaxConcurrency(value || 10)}
                    controls={false}
                    className="w-full [&_input]:!bg-transparent [&_input]:!text-[#EEEEEE] [&]:!bg-transparent [&]:!border-[#757575] hover:[&]:!border-[#EEEEEE] focus-within:[&]:!border-[#EEEEEE]"
                    style={{
                      backgroundColor: "transparent",
                    }}
                  />
                </div>
              </div>
            </div>

            {/* Toggle Switches */}
            <div className="space-y-[1rem]">
              {/* Auto Scale */}
              <div className="flex justify-between items-center py-[.5rem]">
                <div className="flex items-center gap-[.5rem]">
                  <Text_14_400_EEEEEE>Auto Scale</Text_14_400_EEEEEE>
                </div>
                <Switch
                  checked={autoScale}
                  onChange={setAutoScale}
                  style={{
                    backgroundColor: autoScale ? "#965CDE" : "#757575",
                  }}
                />
              </div>

              {/* Caching */}
              <div className="flex justify-between items-center py-[.5rem]">
                <div className="flex items-center gap-[.5rem]">
                  <Text_14_400_EEEEEE>Caching</Text_14_400_EEEEEE>
                </div>
                <Switch
                  checked={autoCaching}
                  onChange={setCaching}
                  style={{
                    backgroundColor: autoCaching ? "#965CDE" : "#757575",
                  }}
                />
              </div>

              {/* Auto Logging */}
              <div className="flex justify-between items-center py-[.5rem]">
                <div className="flex items-center gap-[.5rem]">
                  <Text_14_400_EEEEEE>Auto Logging</Text_14_400_EEEEEE>
                </div>
                <Switch
                  checked={autoLogging}
                  onChange={setAutoLogging}
                  style={{
                    backgroundColor: autoLogging ? "#965CDE" : "#757575",
                  }}
                />
              </div>

              {/* Rate Limiting */}
              <div className="flex justify-between items-center py-[.5rem]">
                <div className="flex items-center gap-[.5rem]">
                  <Text_14_400_EEEEEE>Rate Limiting</Text_14_400_EEEEEE>
                </div>
                <Switch
                  checked={rateLimit}
                  onChange={setRateLimit}
                  style={{
                    backgroundColor: rateLimit ? "#965CDE" : "#757575",
                  }}
                />
              </div>

              {/* Rate Limit Value */}
              {rateLimit && (
                <div className="ml-[2rem]">
                  <InfoLabel
                    text="Rate Limit (requests/second)"
                    content="Maximum number of requests per second"
                  />
                  <InputNumber
                    min={1}
                    max={1000}
                    value={rateLimitValue}
                    onChange={(value) => setRateLimitValue(value || 10)}
                    controls={false}
                    className="w-full mt-[.5rem] [&_input]:!bg-transparent [&_input]:!text-[#EEEEEE] [&]:!bg-transparent [&]:!border-[#757575] hover:[&]:!border-[#EEEEEE] focus-within:[&]:!border-[#EEEEEE]"
                    style={{
                      backgroundColor: "transparent",
                    }}
                  />
                </div>
              )}

              {/* Trigger Workflow */}
              <div className="flex justify-between items-center py-[.5rem]">
                <div className="flex items-center gap-[.5rem]">
                  <Text_14_400_EEEEEE>Trigger Workflow</Text_14_400_EEEEEE>
                </div>
                <Switch
                  checked={triggerWorkflow}
                  onChange={setTriggerWorkflow}
                  style={{
                    backgroundColor: triggerWorkflow ? "#965CDE" : "#757575",
                  }}
                />
              </div>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

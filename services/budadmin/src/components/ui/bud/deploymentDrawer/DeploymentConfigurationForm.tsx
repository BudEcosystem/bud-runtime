import React, { useContext } from "react";
import { Form } from "antd";
import { InfoCircleOutlined } from "@ant-design/icons";
import { Code, Brain } from "lucide-react";
import { BudFormContext } from "../context/BudFormContext";
import { useDeployModel } from "src/stores/useDeployModel";
import ParserConfigurationCard from "./ParserConfigurationCard";

const DeploymentConfigurationForm: React.FC = () => {
  const { form } = useContext(BudFormContext);
  const { deploymentConfiguration, currentWorkflow, deploymentCluster } = useDeployModel();

  // Check workflow_steps from API response for parser metadata
  const workflowSteps = currentWorkflow?.workflow_steps || {};

  // Extract simulator metadata
  const simulatorEvents = workflowSteps?.bud_simulator_events;
  const simulatorMetadata = simulatorEvents?.metadata || {};

  // Also check the selected cluster for parser metadata as fallback
  const clusterMetadata = deploymentCluster || {};

  // Priority: Workflow steps from API > Simulator metadata > Current cluster metadata
  const toolParserType = workflowSteps.tool_calling_parser_type || simulatorMetadata.tool_calling_parser_type || clusterMetadata.tool_calling_parser_type;
  const reasoningParserType = workflowSteps.reasoning_parser_type || simulatorMetadata.reasoning_parser_type || clusterMetadata.reasoning_parser_type;

  const hasToolParser = !!toolParserType;
  const hasReasoningParser = !!reasoningParserType;

  // Derive from context values so updates trigger re-render
  // Use Form.Item shouldUpdate to re-render when form values change

  const handleToolCallingChange = (checked: boolean) => {
    form.setFieldsValue({ enable_tool_calling: checked });
  };

  const handleReasoningChange = (checked: boolean) => {
    form.setFieldsValue({ enable_reasoning: checked });
  };


  if (!hasToolParser && !hasReasoningParser) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-center">
        <InfoCircleOutlined style={{ fontSize: "32px", color: "#757575", marginBottom: "16px" }} />
        <div className="text-[#EEEEEE] text-[0.875rem] mb-2">
          No Advanced Features Available
        </div>
        <div className="text-[#757575] text-[0.75rem]">
          This model does not support parser features
        </div>
      </div>
    );
  }

  return (
    <div className="pt-[.6rem]">

      {/* Register hidden fields so values are included in Form submissions */}
      <Form.Item name="enable_tool_calling" valuePropName="checked" style={{ display: 'none' }}>
        {/* Hidden binder to register boolean in form state */}
        <input type="checkbox" style={{ display: 'none' }} />
      </Form.Item>
      <Form.Item name="enable_reasoning" valuePropName="checked" style={{ display: 'none' }}>
        {/* Hidden binder to register boolean in form state */}
        <input type="checkbox" style={{ display: 'none' }} />
      </Form.Item>

      {hasToolParser && (
        <Form.Item noStyle shouldUpdate={(prev, next) => prev.enable_tool_calling !== next.enable_tool_calling}>
          {() => (
            <ParserConfigurationCard
              title="Tool Calling"
              description={"Enable tool calling for this deployment"}
              icon={<Code className="w-[1.25rem] h-[1.25rem] text-[#757575]" />}
              selected={form.getFieldValue("enable_tool_calling") || false}
              onChange={handleToolCallingChange}
            />
          )}
        </Form.Item>
      )}

      {hasReasoningParser && (
        <Form.Item noStyle shouldUpdate={(prev, next) => prev.enable_reasoning !== next.enable_reasoning}>
          {() => (
            <ParserConfigurationCard
              title="Reasoning Parser"
              description={"Enable reasoning parser for the model response."}
              icon={<Brain className="w-[1.25rem] h-[1.25rem] text-[#757575]" />}
              selected={form.getFieldValue("enable_reasoning") || false}
              onChange={handleReasoningChange}
            />
          )}
        </Form.Item>
      )}
    </div>
  );
};

export default DeploymentConfigurationForm;

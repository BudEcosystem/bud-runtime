import React, { useState, useEffect } from "react";
import { Modal, Form, Input, Select, InputNumber, message } from "antd";
import {
  useBlockingRules,
  BlockingRuleCreate,
  BlockingRuleType,
} from "@/stores/useBlockingRules";
import { useLoader } from "../../context/appContext";

const { Option } = Select;
const { TextArea } = Input;

interface CreateBlockingRuleModalProps {
  visible: boolean;
  onClose: () => void;
}

export const CreateBlockingRuleModal: React.FC<
  CreateBlockingRuleModalProps
> = ({ visible, onClose }) => {
  const [form] = Form.useForm();
  const { createRule, isCreating } = useBlockingRules();
  const { showLoader, hideLoader } = useLoader();
  const [ruleType, setRuleType] = useState<BlockingRuleType>("ip_blocking");

  useEffect(() => {
    if (visible) {
      // Reset form when modal opens
      form.resetFields();
    }
  }, [visible, form]);

  const handleSubmit = async () => {
    showLoader();
    try {
      const values = await form.validateFields();

      const ruleData: BlockingRuleCreate = {
        name: values.name,
        rule_type: ruleType,
        rule_config: values.rule_config,
        reason: values.reason,
        priority: values.priority || 0,
      };

      // Create global rule (no project_id)
      const success = await createRule(ruleData);
      if (success) {
        form.resetFields();
        onClose();
      }
    } catch (error) {
      console.error("Form validation failed:", error);
    } finally {
      hideLoader();
    }
  };

  const getRuleConfigFields = () => {
    switch (ruleType) {
      case "ip_blocking":
        return (
          <Form.Item
            name={["rule_config", "ip_addresses"]}
            label="IP Addresses"
            rules={[{ required: true, message: "Please enter IP addresses" }]}
            help="Enter IP addresses or CIDR ranges, one per line"
          >
            <TextArea
              rows={3}
              placeholder="192.168.1.1&#10;10.0.0.0/24"
            />
          </Form.Item>
        );

      case "country_blocking":
        return (
          <Form.Item
            name={["rule_config", "countries"]}
            label="Country Codes"
            rules={[{ required: true, message: "Please enter country codes" }]}
            help="Enter ISO country codes (e.g., CN, RU, US)"
          >
            <Select mode="tags" placeholder="Select or enter country codes">
              <Option value="CN">China</Option>
              <Option value="RU">Russia</Option>
              <Option value="US">United States</Option>
              <Option value="IN">India</Option>
              <Option value="BR">Brazil</Option>
            </Select>
          </Form.Item>
        );

      case "user_agent_blocking":
        return (
          <Form.Item
            name={["rule_config", "patterns"]}
            label="User Agent Patterns"
            rules={[{ required: true, message: "Please enter patterns" }]}
            help="Enter regex patterns, one per line"
          >
            <TextArea
              rows={3}
              placeholder=".*bot.*&#10;.*crawler.*"
            />
          </Form.Item>
        );

      case "rate_based_blocking":
        return (
          <>
            <Form.Item
              name={["rule_config", "threshold"]}
              label="Request Threshold"
              rules={[
                { required: true, message: "Please enter threshold" },
                {
                  type: "number",
                  min: 1,
                  max: 10000,
                  message: "Threshold must be between 1 and 10000",
                  transform: (value) => parseInt(value),
                },
              ]}
            >
              <Input
                type="number"
                min={1}
                placeholder="100"
                style={{ width: "100%" }}
              />
            </Form.Item>
            <Form.Item
              name={["rule_config", "window_seconds"]}
              label="Time Window (seconds)"
              rules={[
                { required: true, message: "Please enter time window" },
                {
                  type: "number",
                  min: 1,
                  max: 3600,
                  message: "Time window must be between 1 and 3600 seconds",
                  transform: (value) => parseInt(value),
                },
              ]}
            >
              <Input
                type="number"
                min={1}
                placeholder="60"
                style={{ width: "100%" }}
              />
            </Form.Item>
          </>
        );

      default:
        return null;
    }
  };

  const handleConfigChange = (changedValues: any) => {
    // Transform array inputs for IP and User Agent blocking
    if (changedValues.rule_config) {
      if (
        changedValues.rule_config.ip_addresses &&
        typeof changedValues.rule_config.ip_addresses === "string"
      ) {
        const ips = changedValues.rule_config.ip_addresses
          .split("\n")
          .filter((ip: string) => ip.trim());
        form.setFieldValue(["rule_config", "ip_addresses"], ips);
      }
      if (
        changedValues.rule_config.patterns &&
        typeof changedValues.rule_config.patterns === "string"
      ) {
        const patterns = changedValues.rule_config.patterns
          .split("\n")
          .filter((p: string) => p.trim());
        form.setFieldValue(["rule_config", "patterns"], patterns);
      }
    }
  };

  return (
    <Modal
      title="Create Global Blocking Rule"
      visible={visible}
      onOk={handleSubmit}
      onCancel={onClose}
      confirmLoading={isCreating}
      width={600}
    >
      <Form form={form} layout="vertical" onValuesChange={handleConfigChange}>
        <Form.Item
          name="name"
          label="Rule Name"
          rules={[{ required: true, message: "Please enter rule name" }]}
        >
          <Input placeholder="Enter rule name" />
        </Form.Item>

        <Form.Item label="Rule Type" required>
          <Select value={ruleType} onChange={setRuleType}>
            <Option value="ip_blocking">IP Blocking</Option>
            <Option value="country_blocking">Country Blocking</Option>
            <Option value="user_agent_blocking">User Agent Blocking</Option>
            <Option value="rate_based_blocking">Rate-Based Blocking</Option>
          </Select>
        </Form.Item>

        {getRuleConfigFields()}

        <Form.Item
          name="reason"
          label="Reason"
          rules={[
            { required: true, message: "Please enter reason for this rule" },
          ]}
        >
          <TextArea rows={2} placeholder="Why is this rule being created?" />
        </Form.Item>

        <Form.Item
          name="priority"
          label="Priority"
          help="Higher values are evaluated first"
        >
          <InputNumber min={0} placeholder="0" style={{ width: "100%" }} />
        </Form.Item>
      </Form>
    </Modal>
  );
};

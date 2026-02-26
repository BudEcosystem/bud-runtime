/**
 * HelmChartFields - Form fields for Helm chart configuration
 *
 * Renders Chart Reference (required), Chart Version (optional),
 * and Default Values (optional JSON textarea) when the component
 * type is "helm".
 *
 * Designed to be used inside an Ant Design <Form> context.
 */

import React from "react";
import { Form, Input } from "antd";
import FloatLabel from "@/components/ui/bud/dataEntry/FloatLabel";
import InfoLabel from "@/components/ui/bud/dataEntry/InfoLabel";

const { TextArea } = Input;

interface HelmChartFieldsProps {
  /** Field name prefix for nested form items (e.g., ["components", 0, "chart"]) */
  namePrefix?: (string | number)[];
  /** Whether all fields should be disabled */
  disabled?: boolean;
}

/**
 * Validates that a string is valid JSON (object or empty).
 * Returns a promise that resolves if valid, rejects with message if not.
 */
function validateJson(_: any, value: string): Promise<void> {
  if (!value || value.trim() === "") {
    return Promise.resolve();
  }
  try {
    const parsed = JSON.parse(value);
    if (typeof parsed !== "object" || Array.isArray(parsed)) {
      return Promise.reject(new Error("Values must be a JSON object (e.g. {\"key\": \"value\"})"));
    }
    return Promise.resolve();
  } catch {
    return Promise.reject(new Error("Invalid JSON format"));
  }
}

export default function HelmChartFields({ namePrefix = [], disabled }: HelmChartFieldsProps) {
  const fieldName = (field: string) => [...namePrefix, field];

  return (
    <div className="helm-chart-fields">
      {/* Chart Reference (required) */}
      <div className="floating-textarea mt-2">
        <FloatLabel
          label={
            <InfoLabel
              text="Chart Reference"
              content="OCI registry URL or Helm repository chart reference (e.g. oci://registry/chart or repo/chart)"
              required
            />
          }
        >
          <Form.Item
            name={fieldName("ref")}
            rules={[
              {
                required: true,
                message: "Chart reference is required for Helm components",
              },
              {
                pattern: /^[a-zA-Z0-9_./:@-]+$/,
                message: "Chart reference contains invalid characters",
              },
            ]}
            hasFeedback
          >
            <Input
              placeholder="oci://registry.example.com/charts/my-chart"
              disabled={disabled}
              className="drawerInp !bg-[transparent] text-[#EEEEEE] font-[300] text-[.75rem] shadow-none w-full indent-[.5rem] !border !border-[#757575] hover:!border-[#CFCFCF] hover:!bg-[#FFFFFF08] !placeholder-[#808080]"
              size="large"
            />
          </Form.Item>
        </FloatLabel>
      </div>

      {/* Chart Version (optional) */}
      <div className="floating-textarea mt-2">
        <FloatLabel
          label={
            <InfoLabel
              text="Chart Version"
              content="Semantic version constraint for the Helm chart (e.g. 1.2.3 or >=1.0.0). Leave empty for latest."
            />
          }
        >
          <Form.Item
            name={fieldName("version")}
            rules={[
              {
                pattern: /^[a-zA-Z0-9.*>=<~^|, -]+$/,
                message: "Invalid version format",
              },
            ]}
            hasFeedback
          >
            <Input
              placeholder="1.0.0 (leave empty for latest)"
              disabled={disabled}
              className="drawerInp !bg-[transparent] text-[#EEEEEE] font-[300] text-[.75rem] shadow-none w-full indent-[.5rem] !border !border-[#757575] hover:!border-[#CFCFCF] hover:!bg-[#FFFFFF08] !placeholder-[#808080]"
              size="large"
            />
          </Form.Item>
        </FloatLabel>
      </div>

      {/* Default Values (optional JSON) */}
      <div className="floating-textarea mt-2">
        <FloatLabel
          label={
            <InfoLabel
              text="Default Values"
              content="Default Helm values as a JSON object. These are passed as --set or values overrides during deployment."
            />
          }
        >
          <Form.Item
            name={fieldName("values")}
            rules={[
              {
                validator: validateJson,
              },
            ]}
            hasFeedback
          >
            <TextArea
              placeholder={'{\n  "replicaCount": 1,\n  "service.port": 8080\n}'}
              disabled={disabled}
              rows={5}
              className="min-h-[100px] resize-none !border !border-[#757575] hover:!border-[#CFCFCF] hover:!bg-[#FFFFFF08] shadow-none !placeholder-[#808080] !placeholder:text-[#808080] font-mono text-[.75rem]"
            />
          </Form.Item>
        </FloatLabel>
      </div>
    </div>
  );
}

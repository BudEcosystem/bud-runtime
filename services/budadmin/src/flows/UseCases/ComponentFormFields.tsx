/**
 * ComponentFormFields - Conditional form fields based on component type
 *
 * When type === "helm":  shows HelmChartFields (chart ref, version, values)
 * When type !== "helm":  shows standard fields (default_component, compatible_components)
 *
 * This component is designed to be used within the template creation /
 * editing form as part of a Form.List for template components.
 */

import React from "react";
import { Form, Input, Select, ConfigProvider, Image } from "antd";
import FloatLabel from "@/components/ui/bud/dataEntry/FloatLabel";
import InfoLabel from "@/components/ui/bud/dataEntry/InfoLabel";
import HelmChartFields from "./HelmChartFields";
import type { ComponentType } from "@/lib/budusecases";

const COMPONENT_TYPE_OPTIONS: Array<{ label: string; value: ComponentType }> = [
  { label: "Model (LLM)", value: "model" },
  { label: "LLM", value: "llm" },
  { label: "Embedder", value: "embedder" },
  { label: "Reranker", value: "reranker" },
  { label: "Vector DB", value: "vector_db" },
  { label: "Memory Store", value: "memory_store" },
  { label: "Helm Chart", value: "helm" },
];

interface ComponentFormFieldsProps {
  /** The currently selected component type */
  componentType: ComponentType | undefined;
  /** Callback when the component type changes */
  onComponentTypeChange: (value: ComponentType) => void;
  /**
   * Field name prefix for this component entry.
   * Typically the Form.List field name array, e.g. [fieldName]
   * which resolves to components[index].
   */
  fieldName: number;
  /** Whether the fields should be disabled */
  disabled?: boolean;
}

export default function ComponentFormFields({
  componentType,
  onComponentTypeChange,
  fieldName,
  disabled,
}: ComponentFormFieldsProps) {
  const isHelm = componentType === "helm";

  return (
    <div className="component-form-fields">
      {/* Component Name */}
      <div className="floating-textarea mt-2">
        <FloatLabel
          label={
            <InfoLabel
              text="Component Name"
              content="A unique identifier for this component within the template (e.g. llm, vector-db, rag-service)"
              required
            />
          }
        >
          <Form.Item
            name={[fieldName, "name"]}
            rules={[
              { required: true, message: "Component name is required" },
              {
                pattern: /^[a-z][a-z0-9_-]*$/,
                message: "Name must start with a lowercase letter and contain only lowercase alphanumeric, hyphens, or underscores",
              },
            ]}
            hasFeedback
          >
            <Input
              placeholder="e.g. vector-db"
              disabled={disabled}
              className="drawerInp !bg-[transparent] text-[#EEEEEE] font-[300] text-[.75rem] shadow-none w-full indent-[.5rem] !border !border-[#757575] hover:!border-[#CFCFCF] hover:!bg-[#FFFFFF08] !placeholder-[#808080]"
              size="large"
            />
          </Form.Item>
        </FloatLabel>
      </div>

      {/* Display Name */}
      <div className="floating-textarea mt-2">
        <FloatLabel
          label={
            <InfoLabel
              text="Display Name"
              content="Human-readable name shown in the UI"
              required
            />
          }
        >
          <Form.Item
            name={[fieldName, "display_name"]}
            rules={[{ required: true, message: "Display name is required" }]}
            hasFeedback
          >
            <Input
              placeholder="e.g. Vector Database"
              disabled={disabled}
              className="drawerInp !bg-[transparent] text-[#EEEEEE] font-[300] text-[.75rem] shadow-none w-full indent-[.5rem] !border !border-[#757575] hover:!border-[#CFCFCF] hover:!bg-[#FFFFFF08] !placeholder-[#808080]"
              size="large"
            />
          </Form.Item>
        </FloatLabel>
      </div>

      {/* Component Type selector */}
      <div className="floating-textarea mt-2">
        <div className="rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]">
          <div className="w-full">
            <span className="absolute h-[3px] bg-[#0d0d0d] top-[0rem] left-[.75rem] px-[0.025rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap pl-[.35rem] pr-[.55rem] text-[.75rem] font-[300] text-[#EEEEEE]">
              Component Type
              <b className="text-[#FF4D4F]">*</b>
            </span>
          </div>
          <div className="custom-select-two w-full rounded-[6px] relative">
            <ConfigProvider
              theme={{
                token: {
                  colorTextPlaceholder: "#808080",
                },
              }}
            >
              <Form.Item
                name={[fieldName, "type"]}
                rules={[{ required: true, message: "Component type is required" }]}
                hasFeedback
              >
                <Select
                  placeholder="Select component type"
                  style={{
                    backgroundColor: "transparent",
                    color: "#EEEEEE",
                    border: "0.5px solid #757575",
                    width: "100%",
                  }}
                  disabled={disabled}
                  size="large"
                  className="drawerInp !bg-[transparent] text-[#EEEEEE] font-[300] text-[.75rem] shadow-none w-full indent-[.5rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] outline-none"
                  options={COMPONENT_TYPE_OPTIONS}
                  onChange={(value: ComponentType) => {
                    onComponentTypeChange(value);
                  }}
                  suffixIcon={
                    <Image
                      src="/images/icons/dropD.png"
                      preview={false}
                      alt="dropdown"
                      style={{ width: "auto", height: "auto" }}
                    />
                  }
                />
              </Form.Item>
            </ConfigProvider>
          </div>
        </div>
      </div>

      {/* Description (optional, for all types) */}
      <div className="floating-textarea mt-2">
        <FloatLabel
          label={
            <InfoLabel
              text="Description"
              content="Optional description of this component's role in the template"
            />
          }
        >
          <Form.Item name={[fieldName, "description"]} hasFeedback>
            <Input
              placeholder="What does this component do?"
              disabled={disabled}
              className="drawerInp !bg-[transparent] text-[#EEEEEE] font-[300] text-[.75rem] shadow-none w-full indent-[.5rem] !border !border-[#757575] hover:!border-[#CFCFCF] hover:!bg-[#FFFFFF08] !placeholder-[#808080]"
              size="large"
            />
          </Form.Item>
        </FloatLabel>
      </div>

      {/* Required toggle */}
      <Form.Item
        name={[fieldName, "required"]}
        valuePropName="checked"
        initialValue={true}
      >
        <label className="flex items-center gap-2 cursor-pointer mt-1 ml-1">
          <input
            type="checkbox"
            defaultChecked
            disabled={disabled}
            className="w-4 h-4 rounded border-[#757575] bg-transparent accent-[#EEEEEE]"
          />
          <span className="text-[.75rem] text-[#B3B3B3]">Required component</span>
        </label>
      </Form.Item>

      {/* Conditional fields based on component type */}
      {isHelm ? (
        /* Helm-specific fields: chart ref, version, values */
        <HelmChartFields
          namePrefix={[fieldName, "chart"]}
          disabled={disabled}
        />
      ) : (
        /* Standard component fields: default_component, compatible_components */
        <>
          <div className="floating-textarea mt-2">
            <FloatLabel
              label={
                <InfoLabel
                  text="Default Component"
                  content="The pre-selected component for this slot (e.g. a specific model name). Users can change this during deployment."
                />
              }
            >
              <Form.Item name={[fieldName, "default_component"]} hasFeedback>
                <Input
                  placeholder="e.g. meta-llama/Llama-3.1-8B-Instruct"
                  disabled={disabled}
                  className="drawerInp !bg-[transparent] text-[#EEEEEE] font-[300] text-[.75rem] shadow-none w-full indent-[.5rem] !border !border-[#757575] hover:!border-[#CFCFCF] hover:!bg-[#FFFFFF08] !placeholder-[#808080]"
                  size="large"
                />
              </Form.Item>
            </FloatLabel>
          </div>

          <div className="floating-textarea mt-2">
            <FloatLabel
              label={
                <InfoLabel
                  text="Compatible Components"
                  content="Comma-separated list of compatible component identifiers that can fill this slot"
                />
              }
            >
              <Form.Item
                name={[fieldName, "compatible_components"]}
                hasFeedback
              >
                <Select
                  mode="tags"
                  placeholder="Type and press Enter to add"
                  disabled={disabled}
                  style={{
                    backgroundColor: "transparent",
                    color: "#EEEEEE",
                    border: "0.5px solid #757575",
                    width: "100%",
                  }}
                  size="large"
                  className="drawerInp !bg-[transparent] text-[#EEEEEE] font-[300] text-[.75rem] shadow-none w-full indent-[.5rem] border-0 outline-0"
                  open={false}
                />
              </Form.Item>
            </FloatLabel>
          </div>
        </>
      )}
    </div>
  );
}

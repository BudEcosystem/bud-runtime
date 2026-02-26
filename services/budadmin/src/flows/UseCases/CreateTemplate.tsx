/**
 * CreateTemplate - Template creation flow for BudUseCases
 *
 * A multi-section form that allows users to:
 * 1. Set basic template metadata (name, description, version, tags)
 * 2. Add one or more components to the template
 * 3. Each component can be a standard type (model, embedder, etc.) or "helm"
 * 4. Helm components get chart-specific fields instead of default/compatible component fields
 *
 * On submit, the form data is mapped to a CreateTemplateRequest and sent
 * to the BudUseCases API via the useUseCases store.
 */

import React, { useContext, useState } from "react";
import { Form, Button } from "antd";
import { PlusOutlined, DeleteOutlined } from "@ant-design/icons";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import ProjectNameInput from "@/components/ui/bud/dataEntry/ProjectNameInput";
import TextAreaInput from "@/components/ui/bud/dataEntry/TextArea";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { useDrawer } from "src/hooks/useDrawer";
import { useUseCases } from "src/stores/useUseCases";
import { successToast, errorToast } from "@/components/toast";
import ComponentFormFields from "./ComponentFormFields";
import type {
  ComponentType,
  TemplateComponentInput,
  CreateTemplateRequest,
} from "@/lib/budusecases";

/**
 * Maps the raw form values for a single component into a TemplateComponentInput.
 * For helm components, builds the chart object from nested chart fields.
 * For non-helm components, passes through default_component and compatible_components.
 */
function mapComponentToPayload(comp: any): TemplateComponentInput {
  const base: TemplateComponentInput = {
    name: comp.name,
    display_name: comp.display_name,
    description: comp.description || undefined,
    type: comp.type,
    required: comp.required !== false,
  };

  if (comp.type === "helm") {
    // Parse chart values JSON string into an object
    let chartValues: Record<string, any> | undefined;
    if (comp.chart?.values) {
      try {
        chartValues = JSON.parse(comp.chart.values);
      } catch {
        chartValues = undefined;
      }
    }

    base.chart = {
      ref: comp.chart?.ref || "",
      version: comp.chart?.version || undefined,
      values: chartValues,
    };
  } else {
    base.default_component = comp.default_component || undefined;
    base.compatible_components = comp.compatible_components || [];
  }

  return base;
}

export default function CreateTemplate() {
  const { closeDrawer } = useDrawer();
  const { form } = useContext(BudFormContext);
  const { createTemplate } = useUseCases();
  const [isCreating, setIsCreating] = useState(false);

  // Track component types per index for conditional rendering
  const [componentTypes, setComponentTypes] = useState<Record<number, ComponentType>>({});

  const handleComponentTypeChange = (index: number, value: ComponentType) => {
    setComponentTypes((prev) => ({ ...prev, [index]: value }));
  };

  return (
    <BudForm
      data={{
        name: "",
        icon: "",
        description: "",
        version: "1.0.0",
        components: [{}],
      }}
      drawerLoading={isCreating}
      onNext={async (values) => {
        if (isCreating) return;

        // Validate at least one component exists
        if (!values.components || values.components.length === 0) {
          errorToast("At least one component is required");
          return;
        }

        // Validate helm components have chart.ref and valid JSON values
        for (const comp of values.components) {
          if (comp.type === "helm") {
            if (!comp.chart?.ref || !comp.chart.ref.trim()) {
              errorToast(`Chart reference is required for Helm component "${comp.name || "unnamed"}"`);
              return;
            }
            if (comp.chart?.values) {
              try {
                JSON.parse(comp.chart.values);
              } catch {
                errorToast(`Invalid JSON in chart values for component "${comp.name || "unnamed"}"`);
                return;
              }
            }
          }
        }

        setIsCreating(true);
        try {
          const request: CreateTemplateRequest = {
            name: values.name,
            display_name: values.name,
            description: values.description || "",
            version: values.version || "1.0.0",
            tags: values.tags || [],
            category: values.category || undefined,
            components: values.components.map(mapComponentToPayload),
            deployment_order: values.components.map((c: any) => c.name).filter(Boolean),
            is_public: false,
          };

          const result = await createTemplate(request);
          if (result) {
            closeDrawer();
          }
        } catch (err) {
          console.error("Error creating template:", err);
          errorToast("Failed to create template");
        } finally {
          setIsCreating(false);
        }
      }}
      nextText="Create Template"
    >
      <BudWraperBox>
        {/* Section 1: Basic Template Info */}
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Create Template"
            description="Define a deployment template with components. Helm components deploy charts directly; other types deploy AI models or services."
          />
          <DrawerCard classNames="pb-0">
            <ProjectNameInput
              placeholder="Enter Template Name"
              isEdit={true}
            />
            <TextAreaInput
              name="description"
              label="Description"
              info="Describe what this template deploys and its use case"
              placeholder="e.g. RAG pipeline with LLM, embedder, and vector database"
              rules={[
                { required: true, message: "Description is required" },
              ]}
            />
            <div className="floating-textarea mt-2">
              <Form.Item name="version" initialValue="1.0.0">
                <label className="flex flex-col gap-1">
                  <span className="text-[.75rem] text-[#787B83] pl-1">Version</span>
                  <input
                    type="text"
                    placeholder="1.0.0"
                    className="w-full px-3 py-2 rounded-[6px] bg-transparent text-[#EEEEEE] text-[.75rem] border border-[#757575] hover:border-[#CFCFCF] focus:border-[#CFCFCF] outline-none placeholder-[#808080]"
                  />
                </label>
              </Form.Item>
            </div>
          </DrawerCard>
        </BudDrawerLayout>

        {/* Section 2: Components */}
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Components"
            description="Add the components this template needs. Choose 'Helm Chart' type for infrastructure services deployed via Helm."
          />
          <DrawerCard>
            <Form.List name="components">
              {(fields, { add, remove }) => (
                <>
                  {fields.map(({ key, name: fieldName }) => (
                    <div
                      key={key}
                      className="relative border border-[#1F1F1F] rounded-lg p-4 mb-4"
                    >
                      {/* Remove button */}
                      {fields.length > 1 && (
                        <Button
                          type="text"
                          icon={<DeleteOutlined />}
                          onClick={() => {
                            remove(fieldName);
                            // Clean up tracked type
                            setComponentTypes((prev) => {
                              const next = { ...prev };
                              delete next[fieldName];
                              return next;
                            });
                          }}
                          className="absolute top-2 right-2 text-[#757575] hover:text-[#FF4D4F] border-none"
                          size="small"
                        />
                      )}

                      <ComponentFormFields
                        fieldName={fieldName}
                        componentType={componentTypes[fieldName]}
                        onComponentTypeChange={(value) =>
                          handleComponentTypeChange(fieldName, value)
                        }
                        disabled={isCreating}
                      />
                    </div>
                  ))}

                  {/* Add Component button */}
                  <Button
                    type="dashed"
                    onClick={() => add({})}
                    block
                    icon={<PlusOutlined />}
                    className="!text-[#B3B3B3] !border-[#757575] hover:!border-[#CFCFCF] hover:!text-[#EEEEEE] !bg-transparent mt-2"
                  >
                    Add Component
                  </Button>
                </>
              )}
            </Form.List>
          </DrawerCard>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

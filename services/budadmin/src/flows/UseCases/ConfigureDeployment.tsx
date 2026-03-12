/**
 * ConfigureDeployment - Step 4 of the Deploy Use Case wizard (5-step flow)
 *
 * Combines model selection and parameter configuration into a single step.
 * For deploy_model components, renders clickable fields that open the
 * ModelPickerPanel expanded side drawer. Cloud models show a credential picker.
 * Below the Components section, template parameters are rendered as before.
 */

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ConfigProvider, Form, InputNumber, Select } from "antd";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import TextInput from "src/flows/components/TextInput";
import BudSwitch from "@/components/ui/bud/dataEntry/BudSwitch";
import FloatLabel from "@/components/ui/bud/dataEntry/FloatLabel";
import InfoLabel from "@/components/ui/bud/dataEntry/InfoLabel";
import {
  Text_10_400_B3B3B3,
  Text_12_400_757575,
  Text_12_600_EEEEEE,
  Text_14_400_EEEEEE,
} from "@/components/ui/text";
import IconRender from "src/flows/components/BudIconRender";
import { useUseCases } from "src/stores/useUseCases";
import { useDrawer } from "src/hooks/useDrawer";
import { errorToast } from "@/components/toast";
import {
  useProprietaryCredentials,
  Credentials,
} from "src/stores/useProprietaryCredentials";
import type { Model } from "src/hooks/useModels";
import type { TemplateComponent, TemplateParameter } from "@/lib/budusecases";

/** Same className used by TextInput and NumberInput components. */
const INPUT_CLASS =
  "border border-[#757575] hover:!border-[#CFCFCF] hover:!bg-[#FFFFFF08] shadow-none !placeholder-[#808080] !placeholder:text-[#808080] !placeholder:font-[300]";

// ---------------------------------------------------------------------------
// CredentialPicker (moved from SelectModels.tsx)
// ---------------------------------------------------------------------------

function CredentialPicker({
  componentName,
  providerType,
}: {
  componentName: string;
  providerType: string;
}) {
  const { credentials, getCredentials } = useProprietaryCredentials();
  const { credentialSelections, setCredentialSelection } = useUseCases();

  useEffect(() => {
    getCredentials({ type: providerType });
  }, [providerType]);

  const filtered = useMemo(
    () =>
      credentials?.filter(
        (c: Credentials) =>
          c.type?.toLowerCase() === providerType.toLowerCase(),
      ) || [],
    [credentials, providerType],
  );

  const selectedId = credentialSelections[componentName] || undefined;

  return (
    <div className="mt-[.6rem]">
      <Text_12_400_757575 className="mb-[.4rem] block">
        API Credential
      </Text_12_400_757575>
      <ConfigProvider
        theme={{
          token: {
            colorText: "#EEEEEE",
            colorTextPlaceholder: "#808080",
            colorBgContainer: "transparent",
            colorBgElevated: "#1F1F1F",
            colorBorder: "#757575",
          },
          components: {
            Select: {
              optionSelectedBg: "#965CDE20",
            },
          },
        }}
      >
        <Select
          placeholder="Select credential"
          value={selectedId}
          onChange={(value) => setCredentialSelection(componentName, value)}
          className="w-full"
          style={{ backgroundColor: "transparent" }}
          allowClear
          options={filtered.map((c: Credentials) => ({
            label: c.name,
            value: c.id,
          }))}
          notFoundContent={
            <Text_10_400_B3B3B3 className="p-2">
              No credentials found for {providerType}
            </Text_10_400_B3B3B3>
          }
        />
      </ConfigProvider>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ConfigureDeployment
// ---------------------------------------------------------------------------

export default function ConfigureDeployment() {
  const {
    selectedTemplate,
    deploymentName,
    deploymentParameters,
    selectedClusterId,
    selectedComponents,
    selectComponent,
    setDeploymentParameter,
    createDeployment,
    selectDeployment,
    fetchDeployments,
  } = useUseCases();
  const { openDrawerWithStep, openDrawerWithExpandedStep } = useDrawer();

  const [isDeploying, setIsDeploying] = useState(false);

  // Track selected model objects locally (for display name/provider_type)
  const [selectedModelObjects, setSelectedModelObjects] = useState<
    Record<string, Model | null>
  >({});

  // Filter deploy_model components from template
  const modelComponents: TemplateComponent[] = useMemo(
    () =>
      selectedTemplate?.components?.filter(
        (c) => c.component_type === "deploy_model",
      ) || [],
    [selectedTemplate],
  );

  // Auto-fill non-model component selections with defaults from the template
  useEffect(() => {
    if (selectedTemplate?.components) {
      for (const comp of selectedTemplate.components) {
        if (comp.component_type === "deploy_model") continue;
        const defaultVal = comp.default_component || comp.name;
        selectComponent(comp.name, defaultVal);
      }
    }
  }, [selectedTemplate]);

  // Populate parameter defaults in the zustand store
  useEffect(() => {
    if (selectedTemplate?.parameters) {
      Object.entries(selectedTemplate.parameters).forEach(([key, param]) => {
        if (deploymentParameters[key] === undefined && param.default !== undefined) {
          setDeploymentParameter(key, param.default);
        }
      });
    }
  }, [selectedTemplate]);

  // Handler for model selection from the expanded drawer
  const handleModelSelect = useCallback(
    (componentName: string, model: Model) => {
      selectComponent(componentName, model.id);
      setSelectedModelObjects((prev) => ({ ...prev, [componentName]: model }));
    },
    [selectComponent],
  );

  // Open expanded model picker for a component
  const openModelPicker = (comp: TemplateComponent) => {
    openDrawerWithExpandedStep("usecase-model-picker", {
      componentName: comp.name,
      displayName: comp.display_name,
      modelCapability: comp.model_capability,
      selectedModelId: selectedComponents[comp.name],
      onSelect: (model: Model) => handleModelSelect(comp.name, model),
    });
  };

  const handleDeploy = async () => {
    if (!deploymentName.trim()) {
      errorToast("Deployment name is required");
      return;
    }
    if (!selectedClusterId) {
      errorToast("Please select a cluster");
      return;
    }
    // Validate required model components
    const missingModels = modelComponents.filter(
      (comp) => comp.required && !selectedComponents[comp.name],
    );
    if (missingModels.length > 0) {
      errorToast(`Please select a model for: ${missingModels.map((c) => c.display_name).join(", ")}`);
      return;
    }

    setIsDeploying(true);
    try {
      const deployment = await createDeployment();
      if (deployment) {
        await fetchDeployments();
        selectDeployment(deployment);
        openDrawerWithStep("deploy-usecase-progress");
      }
    } finally {
      setIsDeploying(false);
    }
  };

  const templateParams = Object.entries(selectedTemplate?.parameters || {});

  const formatParamLabel = (key: string) =>
    key
      .split("_")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ");

  // Build initial form data with parameter defaults
  const formData = useMemo(() => {
    const data: Record<string, any> = {};
    templateParams.forEach(([key, param]) => {
      data[key] = deploymentParameters[key] ?? param.default;
    });
    return data;
  }, [deploymentParameters, selectedTemplate]);

  // Disable deploy if any required model component has no selection
  const disableDeploy =
    isDeploying ||
    modelComponents.some((comp) => comp.required && !selectedComponents[comp.name]);

  const renderParameterInput = (key: string, param: TemplateParameter) => {
    const label = formatParamLabel(key);

    if (param.type === "boolean") {
      return (
        <BudSwitch
          name={key}
          label={label}
          infoText={param.description}
          placeholder={param.description}
          defaultValue={!!param.default}
          onChange={(checked: boolean) => setDeploymentParameter(key, checked)}
        />
      );
    }

    if (param.type === "select" && param.options) {
      const selectValue = deploymentParameters[key] ?? param.default;
      return (
        <Form.Item name={key} rules={[]} hasFeedback>
          <div className="floating-textarea">
            <FloatLabel
              label={<InfoLabel text={label} content={param.description} />}
              value={selectValue}
            >
              <ConfigProvider
                theme={{
                  token: {
                    colorText: "#EEEEEE",
                    colorTextPlaceholder: "#808080",
                    colorBgContainer: "transparent",
                    colorBgElevated: "#1F1F1F",
                    colorBorder: "#757575",
                  },
                  components: {
                    Select: {
                      optionSelectedBg: "#965CDE20",
                    },
                  },
                }}
              >
                <Select
                  value={selectValue}
                  placeholder={param.description}
                  disabled={isDeploying}
                  onChange={(v) => setDeploymentParameter(key, v)}
                  className={`w-full ${INPUT_CLASS}`}
                  style={{ paddingTop: ".2rem", paddingBottom: ".2rem" }}
                  options={param.options.map((opt) => ({
                    label: opt.label,
                    value: opt.value,
                  }))}
                />
              </ConfigProvider>
            </FloatLabel>
          </div>
        </Form.Item>
      );
    }

    if (param.type === "integer" || param.type === "float") {
      const numValue = deploymentParameters[key] ?? param.default;
      return (
        <Form.Item name={key} rules={[]} hasFeedback>
          <div className="floating-textarea">
            <FloatLabel
              label={<InfoLabel text={label} content={param.description} />}
              value={numValue}
            >
              <ConfigProvider
                theme={{
                  token: { colorText: "white", colorTextPlaceholder: "#808080" },
                  components: {
                    InputNumber: { colorBgContainer: "transparent" },
                  },
                }}
              >
                <InputNumber
                  value={numValue}
                  min={param.min}
                  max={param.max}
                  step={param.type === "float" ? 0.1 : 1}
                  placeholder={param.description}
                  disabled={isDeploying}
                  onChange={(v) => setDeploymentParameter(key, v)}
                  className={`w-full ${INPUT_CLASS}`}
                  style={{ paddingTop: ".5rem", paddingBottom: ".5rem" }}
                />
              </ConfigProvider>
            </FloatLabel>
          </div>
        </Form.Item>
      );
    }

    return (
      <TextInput
        name={key}
        label={label}
        placeholder={param.description || `Enter ${label.toLowerCase()}`}
        infoText={param.description}
        rules={[]}
        disabled={isDeploying}
        onChange={(v) => setDeploymentParameter(key, v)}
      />
    );
  };

  return (
    <BudForm
      data={formData}
      onBack={() => openDrawerWithStep("deploy-usecase-select-cluster")}
      backText="Back"
      nextText={isDeploying ? "Deploying..." : "Deploy"}
      disableNext={disableDeploy}
      onNext={handleDeploy}
    >
      <BudWraperBox>
        {/* ── Components Section (deploy_model fields) ── */}
        {modelComponents.length > 0 && (
          <BudDrawerLayout>
            <DrawerTitleCard
              title="Components"
              description="Select models for each component in the template."
            />
            <DrawerCard>
              <div className="flex flex-col gap-5">
                {modelComponents.map((comp) => {
                  const selectedId = selectedComponents[comp.name];
                  const selectedModel = selectedModelObjects[comp.name] || null;
                  const showCredentials =
                    selectedModel?.provider_type === "cloud_model";

                  return (
                    <div key={comp.name}>
                      <Text_12_600_EEEEEE className="mb-[.4rem] block">
                        {comp.display_name}
                        {comp.required && (
                          <span className="text-[#FF6B6B] ml-1">*</span>
                        )}
                      </Text_12_600_EEEEEE>
                      {comp.model_capability && (
                        <span className="text-[0.525rem] font-[400] rounded-[6px] px-[.3rem] py-[.1rem] mb-[.4rem] inline-block bg-[#965CDE20] text-[#C9A0FF]">
                          {comp.model_capability}
                        </span>
                      )}

                      {/* Clickable model selector field */}
                      <div
                        onClick={() => openModelPicker(comp)}
                        className={`flex items-center gap-2 px-[.8rem] py-[.65rem] rounded-[6px] border cursor-pointer transition-colors ${
                          selectedId
                            ? "border-[#965CDE] bg-[#965CDE08]"
                            : "border-[#757575] hover:border-[#CFCFCF] bg-transparent"
                        }`}
                      >
                        {selectedModel ? (
                          <>
                            <IconRender
                              icon={selectedModel.icon}
                              size={22}
                              imageSize={14}
                            />
                            <div className="flex-1 min-w-0">
                              <Text_14_400_EEEEEE className="truncate block">
                                {selectedModel.name}
                              </Text_14_400_EEEEEE>
                              <Text_10_400_B3B3B3 className="truncate block">
                                {[selectedModel.author, selectedModel.provider_type]
                                  .filter(Boolean)
                                  .join(" \u00B7 ")}
                              </Text_10_400_B3B3B3>
                            </div>
                            <svg
                              width="14"
                              height="14"
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="#757575"
                              strokeWidth="2"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                            >
                              <polyline points="9 18 15 12 9 6" />
                            </svg>
                          </>
                        ) : (
                          <>
                            <Text_12_400_757575 className="flex-1">
                              Select model...
                            </Text_12_400_757575>
                            <svg
                              width="14"
                              height="14"
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="#757575"
                              strokeWidth="2"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                            >
                              <polyline points="9 18 15 12 9 6" />
                            </svg>
                          </>
                        )}
                      </div>

                      {/* Credential picker for cloud models */}
                      {showCredentials && (
                        <CredentialPicker
                          componentName={comp.name}
                          providerType={
                            selectedModel?.provider?.name ||
                            selectedModel?.provider_type ||
                            ""
                          }
                        />
                      )}
                    </div>
                  );
                })}
              </div>
            </DrawerCard>
          </BudDrawerLayout>
        )}

        {/* ── Parameters Section ── */}
        {templateParams.length > 0 && (
          <BudDrawerLayout>
            <DrawerTitleCard
              title="Configure Parameters"
              description="Adjust deployment parameters for your use case."
            />
            <DrawerCard>
              <div className="flex flex-col gap-5">
                {templateParams.map(([key, param]) => (
                  <React.Fragment key={key}>
                    {renderParameterInput(key, param)}
                  </React.Fragment>
                ))}
              </div>
            </DrawerCard>
          </BudDrawerLayout>
        )}

        {/* No components and no parameters — just show a simple message */}
        {modelComponents.length === 0 && templateParams.length === 0 && (
          <BudDrawerLayout>
            <DrawerTitleCard
              title="Configure Deployment"
              description="This template uses default settings. Click Deploy to proceed."
            />
          </BudDrawerLayout>
        )}
      </BudWraperBox>
    </BudForm>
  );
}

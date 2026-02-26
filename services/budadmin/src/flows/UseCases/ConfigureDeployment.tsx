/**
 * ConfigureDeployment - Step 4 of the Deploy Use Case wizard
 *
 * Parameter configuration step. Shows template parameters for user input.
 * Components are auto-configured from template defaults.
 * The "Deploy" button validates inputs, creates the deployment (which auto-starts),
 * and advances to the progress step.
 *
 * Uses the same TextInput / NumberInput / BudSwitch components as other drawer flows.
 */

import React, { useEffect, useMemo, useState } from "react";
import { ConfigProvider, Form, InputNumber } from "antd";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import TextInput from "src/flows/components/TextInput";
import BudSwitch from "@/components/ui/bud/dataEntry/BudSwitch";
import FloatLabel from "@/components/ui/bud/dataEntry/FloatLabel";
import InfoLabel from "@/components/ui/bud/dataEntry/InfoLabel";
import { useUseCases } from "src/stores/useUseCases";
import { useDrawer } from "src/hooks/useDrawer";
import { errorToast } from "@/components/toast";
import type { TemplateParameter } from "@/lib/budusecases";

/** Same className used by TextInput and NumberInput components. */
const INPUT_CLASS =
  "border border-[#757575] hover:!border-[#CFCFCF] hover:!bg-[#FFFFFF08] shadow-none !placeholder-[#808080] !placeholder:text-[#808080] !placeholder:font-[300]";

export default function ConfigureDeployment() {
  const {
    selectedTemplate,
    deploymentName,
    deploymentParameters,
    selectedClusterId,
    selectComponent,
    setDeploymentParameter,
    createDeployment,
    selectDeployment,
    fetchDeployments,
  } = useUseCases();
  const { openDrawerWithStep } = useDrawer();

  const [isDeploying, setIsDeploying] = useState(false);

  // Auto-fill component selections with defaults from the template
  useEffect(() => {
    if (selectedTemplate?.components) {
      for (const comp of selectedTemplate.components) {
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

  const handleDeploy = async () => {
    if (!deploymentName.trim()) {
      errorToast("Deployment name is required");
      return;
    }
    if (!selectedClusterId) {
      errorToast("Please select a cluster");
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

  const renderParameterInput = (key: string, param: TemplateParameter) => {
    const label = formatParamLabel(key);

    // Boolean — uses BudSwitch component (same as other flows)
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

    // Integer / Float — InputNumber with Form.Item for correct border rendering
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

    // String — uses TextInput component (same as other flows)
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
      disableNext={isDeploying}
      onNext={handleDeploy}
    >
      <BudWraperBox>
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

        {templateParams.length === 0 && (
          <BudDrawerLayout>
            <DrawerTitleCard
              title="Configure Parameters"
              description="This template uses default settings. Click Deploy to proceed."
            />
          </BudDrawerLayout>
        )}
      </BudWraperBox>
    </BudForm>
  );
}

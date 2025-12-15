import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { BudDropdownMenu } from "@/components/ui/dropDown";
import { Text_12_400_B3B3B3 } from "@/components/ui/text";
import TextInput from "src/flows/components/TextInput";
import React, { useContext, useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import {
  usePerfomanceBenchmark,
  TPPPOption,
  SelectedConfiguration,
} from "src/stores/usePerfomanceBenchmark";
import { Alert, Spin } from "antd";
import { LoadingOutlined } from "@ant-design/icons";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";

// Inner component that can access BudFormContext
function ConfigurationFormContent({
  nodeConfigurations,
  loadingConfigurations,
  configurationError,
  selectedConfiguration,
  hardwareMode,
  totalDatasetSamples,
  defaultNumPrompts,
  isConfigurationType,
  onConfigChange,
}: {
  nodeConfigurations: any;
  loadingConfigurations: boolean;
  configurationError: string | null;
  selectedConfiguration: SelectedConfiguration | null;
  hardwareMode: string | null;
  totalDatasetSamples: number;
  defaultNumPrompts: number;
  isConfigurationType: boolean;
  onConfigChange: (config: { deviceType: string | null; tppp: TPPPOption | null; replicas: number; numPrompts?: number }) => void;
}) {
  const { form } = useContext(BudFormContext);

  const [selectedDeviceType, setSelectedDeviceType] = useState<string | null>(
    selectedConfiguration?.device_type || null
  );
  const [selectedTPPP, setSelectedTPPP] = useState<TPPPOption | null>(null);
  const [replicas, setReplicas] = useState<number>(
    selectedConfiguration?.replicas || 1
  );
  const [numPrompts, setNumPrompts] = useState<number | undefined>(
    selectedConfiguration?.num_prompts || (isConfigurationType ? defaultNumPrompts : undefined)
  );

  // Get currently selected device config
  const currentDeviceConfig = nodeConfigurations?.device_configurations?.find(
    (d: any) => d.device_type === selectedDeviceType
  );

  // Get TP/PP options for selected device
  const tpppOptions = currentDeviceConfig?.tp_pp_options || [];

  // Auto-select all defaults when nodeConfigurations loads
  useEffect(() => {
    if (!nodeConfigurations?.device_configurations?.length) return;

    // Auto-select device type if only one available and not already selected
    if (nodeConfigurations.device_configurations.length === 1 && !selectedDeviceType) {
      const deviceType = nodeConfigurations.device_configurations[0].device_type;
      setSelectedDeviceType(deviceType);
      form?.setFieldsValue({ device_type: deviceType });
    }
  }, [nodeConfigurations, form]);

  // Auto-select TP/PP and replicas when device type changes
  useEffect(() => {
    if (!selectedDeviceType || !nodeConfigurations?.device_configurations) return;

    // Get options for the selected device type
    const deviceConfig = nodeConfigurations.device_configurations.find(
      (d: any) => d.device_type === selectedDeviceType
    );
    const options = deviceConfig?.tp_pp_options || [];

    if (options.length > 0) {
      let option: TPPPOption;
      // For shared mode, select TP=1, PP=1 if available
      if (hardwareMode === "shared") {
        const sharedOption = options.find(
          (opt: TPPPOption) => opt.tp_size === 1 && opt.pp_size === 1
        );
        option = sharedOption || options[0];
      } else {
        option = options[0];
      }
      setSelectedTPPP(option);
      form?.setFieldsValue({ tp_pp: `${option.tp_size}-${option.pp_size}` });

      // Also set replicas to max
      const maxReplicas = option.max_replicas;
      setReplicas(maxReplicas);
      form?.setFieldsValue({ replicas: String(maxReplicas) });
    }
  }, [selectedDeviceType, nodeConfigurations, hardwareMode, form]);

  // Update replicas when TP/PP changes manually
  useEffect(() => {
    if (selectedTPPP) {
      const maxReplicas = selectedTPPP.max_replicas;
      setReplicas(maxReplicas);
      form?.setFieldsValue({ replicas: String(maxReplicas) });
    }
  }, [selectedTPPP, form]);

  // Notify parent of config changes
  useEffect(() => {
    onConfigChange({ deviceType: selectedDeviceType, tppp: selectedTPPP, replicas, numPrompts });
  }, [selectedDeviceType, selectedTPPP, replicas, numPrompts]);

  // Set default num_prompts for configuration type
  useEffect(() => {
    if (isConfigurationType && !selectedConfiguration?.num_prompts) {
      setNumPrompts(defaultNumPrompts);
      form?.setFieldsValue({ num_prompts: String(defaultNumPrompts) });
    }
  }, [isConfigurationType, defaultNumPrompts, form]);

  // Transform device configurations to dropdown items
  const deviceTypeItems = nodeConfigurations?.device_configurations?.map((config: any) => ({
    label: `${config.device_name.toUpperCase()} - ${config.total_devices} devices`,
    value: config.device_type,
  })) || [];

  // Transform TP/PP options to dropdown items
  const tpppItems = tpppOptions.map((option: TPPPOption) => ({
    label: `TP=${option.tp_size}, PP=${option.pp_size}`,
    value: `${option.tp_size}-${option.pp_size}`,
  }));

  return (
    <>
      <DrawerTitleCard
        title="Configuration Options"
        description="Select the deployment configuration for your benchmark"
        classNames="pt-[.8rem]"
        descriptionClass="pt-[.3rem]"
      />

      {loadingConfigurations ? (
        <div className="flex justify-center items-center py-16">
          <Spin
            indicator={<LoadingOutlined style={{ fontSize: 32 }} spin />}
          />
          <Text_12_400_B3B3B3 className="ml-3">
            Loading configuration options...
          </Text_12_400_B3B3B3>
        </div>
      ) : !nodeConfigurations ? (
        <div className="px-[1.4rem] py-8">
          <Alert
            type="error"
            message="No device available"
            description={configurationError || "Please go back and ensure you have selected a cluster, nodes, and model."}
            showIcon
          />
        </div>
      ) : (
        <div className="px-[1.4rem] pt-4 space-y-6">

          {/* Device Type Selection - Dropdown */}
          {deviceTypeItems.length > 0 && (
            <BudDropdownMenu
              name="device_type"
              label="Device Type"
              infoText="Select the device type for deployment"
              placeholder="Select device type"
              items={deviceTypeItems}
              onChange={(value: string) => setSelectedDeviceType(value)}
            />
          )}

          {/* TP/PP Configuration - Dropdown */}
          {currentDeviceConfig && tpppItems.length > 0 && (
            <div>
              <BudDropdownMenu
                name="tp_pp"
                label="TP/PP Configuration"
                infoText="Select tensor and pipeline parallelism settings"
                placeholder="Select TP/PP configuration"
                items={tpppItems}
                onChange={(value: string) => {
                  const [tp, pp] = value.split("-").map(Number);
                  const option = tpppOptions.find(
                    (o: TPPPOption) => o.tp_size === tp && o.pp_size === pp
                  );
                  setSelectedTPPP(option || null);
                }}
              />
            </div>
          )}

          {/* Replica Count */}
          {selectedTPPP && (
            <TextInput
              name="replicas"
              label="Number of Replicas"
              placeholder="Enter number of replicas"
              infoText={`Maximum ${selectedTPPP.max_replicas} replicas available`}
              allowOnlyNumbers={true}
              rules={[
                { required: true, message: "Please enter number of replicas" },
              ]}
              onChange={(value) => {
                const numValue = parseInt(value) || 1;
                const clampedValue = Math.min(Math.max(numValue, 1), selectedTPPP.max_replicas);
                setReplicas(clampedValue);
                if (numValue !== clampedValue) {
                  form?.setFieldsValue({ replicas: String(clampedValue) });
                }
              }}
            />
          )}

          {/* Number of Prompts */}
          <TextInput
            name="num_prompts"
            label="Number of Prompts"
            placeholder={
              isConfigurationType
                ? `Default: ${defaultNumPrompts} (from concurrency)`
                : totalDatasetSamples > 0
                  ? `Default: ${totalDatasetSamples} (from datasets)`
                  : "Enter number of prompts"
            }
            infoText={
              isConfigurationType
                ? "Total prompts to run. Defaults to concurrency value."
                : "Total prompts to run. If not set, defaults to sum of dataset samples."
            }
            allowOnlyNumbers={true}
            rules={[
              { required: true, message: "Please enter number of prompts" },
            ]}
            onChange={(value) => {
              const numValue = value ? parseInt(value) : undefined;
              setNumPrompts(numValue);
            }}
          />
        </div>
      )}
    </>
  );
}

export default function SelectConfiguration() {
  const { openDrawerWithStep } = useDrawer();
  const {
    fetchNodeConfigurations,
    nodeConfigurations,
    loadingConfigurations,
    configurationError,
    selectedConfiguration,
    setSelectedConfiguration,
    stepConfigurationOptions,
    hardwareMode,
    setRunAsSimulation,
    stepSeven,
    stepEight,
    selectedDataset,
    evalWith,
    stepOneData,
  } = usePerfomanceBenchmark();

  const [currentConfig, setCurrentConfig] = useState<{
    deviceType: string | null;
    tppp: TPPPOption | null;
    replicas: number;
    numPrompts?: number;
  }>({ deviceType: null, tppp: null, replicas: 1, numPrompts: undefined });

  // Calculate total dataset samples for default placeholder
  const totalDatasetSamples = selectedDataset.reduce(
    (sum, dataset) => sum + (dataset.num_samples || 0),
    0
  );

  // For configuration type, default num_prompts to concurrency
  const isConfigurationType = evalWith !== "dataset";
  const defaultNumPrompts = isConfigurationType
    ? stepOneData?.concurrent_requests || 10
    : totalDatasetSamples;

  // Fetch configurations on mount
  useEffect(() => {
    fetchNodeConfigurations();
  }, []);

  // Validate, set configuration, and run benchmark
  const handleRun = async () => {
    if (!currentConfig.deviceType || !currentConfig.tppp) {
      return;
    }

    const config: SelectedConfiguration = {
      device_type: currentConfig.deviceType,
      tp_size: currentConfig.tppp.tp_size,
      pp_size: currentConfig.tppp.pp_size,
      replicas: currentConfig.replicas,
      num_prompts: currentConfig.numPrompts,
    };

    setSelectedConfiguration(config);

    // Save configuration options
    const configResult = await stepConfigurationOptions();
    if (!configResult) {
      return;
    }

    // Confirm the configuration (required by backend)
    const confirmResult = await stepSeven();
    if (!confirmResult) {
      return;
    }

    // Run the benchmark (not simulation)
    setRunAsSimulation(false);
    const runResult = await stepEight();
    if (runResult) {
      openDrawerWithStep("Benchmarking-Progress");
    }
  };

  const canProceed =
    currentConfig.deviceType && currentConfig.tppp && currentConfig.replicas > 0 && !loadingConfigurations;

  return (
    <BudForm
      data={{ replicas: String(selectedConfiguration?.replicas || 1) }}
      disableNext={!canProceed}
      onNext={handleRun}
      onBack={() => {
        openDrawerWithStep("Select-Model");
      }}
      backText="Back"
      nextText="Run"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <ConfigurationFormContent
            nodeConfigurations={nodeConfigurations}
            loadingConfigurations={loadingConfigurations}
            configurationError={configurationError}
            selectedConfiguration={selectedConfiguration}
            hardwareMode={hardwareMode}
            totalDatasetSamples={totalDatasetSamples}
            defaultNumPrompts={defaultNumPrompts}
            isConfigurationType={isConfigurationType}
            onConfigChange={setCurrentConfig}
          />
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

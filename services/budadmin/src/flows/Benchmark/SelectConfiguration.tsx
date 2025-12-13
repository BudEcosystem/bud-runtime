import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { BudDropdownMenu } from "@/components/ui/dropDown";
import {
  Text_12_400_B3B3B3,
  Text_10_400_B3B3B3,
} from "@/components/ui/text";
import React, { useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import {
  usePerfomanceBenchmark,
  TPPPOption,
  SelectedConfiguration,
} from "src/stores/usePerfomanceBenchmark";
import { Alert, InputNumber, Spin } from "antd";
import { LoadingOutlined } from "@ant-design/icons";

export default function SelectConfiguration() {
  const { openDrawerWithStep } = useDrawer();
  const {
    fetchNodeConfigurations,
    nodeConfigurations,
    loadingConfigurations,
    selectedConfiguration,
    setSelectedConfiguration,
    stepConfigurationOptions,
    hardwareMode,
  } = usePerfomanceBenchmark();

  const [selectedDeviceType, setSelectedDeviceType] = useState<string | null>(
    selectedConfiguration?.device_type || null
  );
  const [selectedTPPP, setSelectedTPPP] = useState<TPPPOption | null>(null);
  const [replicas, setReplicas] = useState<number>(
    selectedConfiguration?.replicas || 1
  );

  // Fetch configurations on mount
  useEffect(() => {
    fetchNodeConfigurations();
  }, []);

  // Auto-select device type if only one available
  useEffect(() => {
    if (
      nodeConfigurations?.device_configurations?.length === 1 &&
      !selectedDeviceType
    ) {
      setSelectedDeviceType(
        nodeConfigurations.device_configurations[0].device_type
      );
    }
  }, [nodeConfigurations, selectedDeviceType]);

  // Get currently selected device config
  const currentDeviceConfig = nodeConfigurations?.device_configurations?.find(
    (d) => d.device_type === selectedDeviceType
  );

  // Get TP/PP options for selected device
  const tpppOptions = currentDeviceConfig?.tp_pp_options || [];

  // Auto-select first TP/PP option when device type changes
  useEffect(() => {
    if (tpppOptions.length > 0 && !selectedTPPP) {
      // For shared mode, select TP=1, PP=1 if available
      if (hardwareMode === "shared") {
        const sharedOption = tpppOptions.find(
          (opt) => opt.tp_size === 1 && opt.pp_size === 1
        );
        setSelectedTPPP(sharedOption || tpppOptions[0]);
      } else {
        setSelectedTPPP(tpppOptions[0]);
      }
    }
  }, [tpppOptions, selectedTPPP, hardwareMode]);

  // Reset TP/PP selection when device type changes
  useEffect(() => {
    setSelectedTPPP(null);
    setReplicas(1);
  }, [selectedDeviceType]);

  // Update replicas when TP/PP changes
  useEffect(() => {
    if (selectedTPPP) {
      setReplicas(Math.min(replicas, selectedTPPP.max_replicas));
    }
  }, [selectedTPPP]);

  // Validate and set the configuration
  const handleNext = async () => {
    if (!selectedDeviceType || !selectedTPPP) {
      return;
    }

    const config: SelectedConfiguration = {
      device_type: selectedDeviceType,
      tp_size: selectedTPPP.tp_size,
      pp_size: selectedTPPP.pp_size,
      replicas: replicas,
    };

    setSelectedConfiguration(config);

    const result = await stepConfigurationOptions();
    if (result) {
      openDrawerWithStep("Benchmark-Configuration");
    }
  };

  const isSharedMode = hardwareMode === "shared";
  const canProceed =
    selectedDeviceType && selectedTPPP && replicas > 0 && !loadingConfigurations;

  // Transform device configurations to dropdown items
  const deviceTypeItems = nodeConfigurations?.device_configurations?.map((config) => ({
    label: `${config.device_type.toUpperCase()} - ${config.total_devices} devices (${config.memory_per_device_gb.toFixed(1)} GB each)`,
    value: config.device_type,
  })) || [];

  // Transform TP/PP options to dropdown items
  const tpppItems = tpppOptions.map((option) => ({
    label: `TP=${option.tp_size}, PP=${option.pp_size} (${option.description})`,
    value: `${option.tp_size}-${option.pp_size}`,
  }));

  return (
    <BudForm
      data={{}}
      disableNext={!canProceed}
      onNext={handleNext}
      onBack={() => {
        openDrawerWithStep("Select-Model");
      }}
      backText="Back"
      nextText="Next"
    >
      <BudWraperBox>
        <BudDrawerLayout>
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
                message="Failed to load configuration options"
                description="Please go back and ensure you have selected a cluster, nodes, and model."
                showIcon
              />
            </div>
          ) : (
            <div className="px-[1.4rem] pt-4 space-y-6">
              {/* Shared Mode Alert */}
              {isSharedMode && (
                <Alert
                  type="info"
                  message="Shared Hardware Mode"
                  description="In shared mode, only TP=1 and PP=1 configurations are available to ensure resource compatibility."
                  showIcon
                />
              )}

              {/* Model Memory Info */}
              {nodeConfigurations.model_info && (
                <div className="bg-[#1a1a1a] border border-[#333] rounded-lg p-4">
                  <Text_12_400_B3B3B3 className="mb-2 block">
                    Model Requirements
                  </Text_12_400_B3B3B3>
                  <div className="space-y-1">
                    <Text_10_400_B3B3B3>
                      {nodeConfigurations.model_info.model_name ||
                        nodeConfigurations.model_info.model_uri}
                    </Text_10_400_B3B3B3>
                    <Text_10_400_B3B3B3>
                      Estimated Memory:{" "}
                      {nodeConfigurations.model_info.estimated_weight_memory_gb.toFixed(
                        1
                      )}{" "}
                      GB
                    </Text_10_400_B3B3B3>
                    <Text_10_400_B3B3B3>
                      Minimum TP Required:{" "}
                      {nodeConfigurations.model_info.min_tp_for_model}
                    </Text_10_400_B3B3B3>
                  </div>
                </div>
              )}

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
                        (o) => o.tp_size === tp && o.pp_size === pp
                      );
                      setSelectedTPPP(option || null);
                    }}
                  />
                  {selectedTPPP && (
                    <Text_10_400_B3B3B3 className="mt-2 block">
                      Devices needed: {selectedTPPP.total_devices_needed} | Max
                      replicas: {selectedTPPP.max_replicas}
                    </Text_10_400_B3B3B3>
                  )}
                </div>
              )}

              {/* Replica Count */}
              {selectedTPPP && (
                <div>
                  <Text_12_400_B3B3B3 className="mb-3 block">
                    Number of Replicas
                  </Text_12_400_B3B3B3>
                  <InputNumber
                    className="w-full"
                    min={1}
                    max={selectedTPPP.max_replicas}
                    value={replicas}
                    onChange={(value) => setReplicas(value || 1)}
                  />
                  <Text_10_400_B3B3B3 className="mt-2 block">
                    Maximum {selectedTPPP.max_replicas} replicas available with
                    current TP/PP configuration
                  </Text_10_400_B3B3B3>
                </div>
              )}

              {/* Configuration Summary */}
              {selectedDeviceType && selectedTPPP && replicas > 0 && (
                <div className="bg-[#1F3A5F20] border border-[#5B9FFF30] rounded-lg p-4">
                  <Text_12_400_B3B3B3 className="mb-2 block font-medium">
                    Configuration Summary
                  </Text_12_400_B3B3B3>
                  <div className="space-y-1">
                    <Text_10_400_B3B3B3>
                      Device Type: {selectedDeviceType.toUpperCase()}
                    </Text_10_400_B3B3B3>
                    <Text_10_400_B3B3B3>
                      Tensor Parallelism (TP): {selectedTPPP.tp_size}
                    </Text_10_400_B3B3B3>
                    <Text_10_400_B3B3B3>
                      Pipeline Parallelism (PP): {selectedTPPP.pp_size}
                    </Text_10_400_B3B3B3>
                    <Text_10_400_B3B3B3>Replicas: {replicas}</Text_10_400_B3B3B3>
                    <Text_10_400_B3B3B3>
                      Total Devices Used:{" "}
                      {selectedTPPP.total_devices_needed * replicas}
                    </Text_10_400_B3B3B3>
                  </div>
                </div>
              )}
            </div>
          )}
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

import React, { useState, useEffect } from "react";
import { Switch, ConfigProvider, Select, InputNumber, Button, Spin, Collapse, TimePicker, Slider } from "antd";
import { PlusOutlined, DeleteOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { Text_12_300_EEEEEE, Text_12_400_EEEEEE, Text_14_400_EEEEEE } from "@/components/ui/text";
import CustomPopover from "src/flows/components/customPopover";
import { Image } from "antd";
import { successToast, errorToast } from "@/components/toast";
import { useConfirmAction } from "src/hooks/useConfirmAction";
import {
  useEndPoints,
  BudAIScalerConfig,
  BudAIScalerMetricSource,
  BudAIScalerScheduleHint,
} from "src/hooks/useEndPoint";

// Dark theme configuration for Ant Design components
const darkTheme = {
  token: {
    colorPrimary: "#965CDE",
    colorBgContainer: "#1a1a1a",
    colorBgElevated: "#1a1a1a",
    colorBorder: "#757575",
    colorText: "#EEEEEE",
    colorTextPlaceholder: "#808080",
    colorBorderSecondary: "#333",
    controlItemBgHover: "#FFFFFF08",
    colorTextQuaternary: "#808080",
  },
  components: {
    Select: {
      selectorBg: "transparent",
      optionSelectedBg: "#965CDE40",
      optionActiveBg: "#FFFFFF15",
      optionSelectedColor: "#EEEEEE",
    },
    InputNumber: {
      activeBg: "transparent",
      hoverBg: "#FFFFFF08",
    },
    Collapse: {
      headerBg: "transparent",
      contentBg: "transparent",
    },
    TimePicker: {
      activeBg: "transparent",
      cellActiveWithRangeBg: "#965CDE40",
      cellHoverBg: "#FFFFFF15",
      cellBg: "transparent",
    },
  },
};

// Common input styling - adjusted for consistent heights and vertical centering
const inputStyle: React.CSSProperties = {
  backgroundColor: "transparent",
  color: "#EEEEEE",
  border: "0.5px solid #757575",
  height: "2.25rem",
};

const selectStyle: React.CSSProperties = {
  backgroundColor: "transparent",
  color: "#EEEEEE",
  border: "0.5px solid #757575",
  height: "2.25rem",
  width: "100%",
};

const inputClassName = "!bg-transparent !shadow-none border border-[#757575] hover:!border-[#CFCFCF] hover:!bg-[#FFFFFF08] [&_input]:!text-[#EEEEEE] [&_input]:!leading-[2.25rem] [&_.ant-input-number-input]:!h-[2.25rem] [&_.ant-input-number-input]:!py-0";
const selectClassName = "drawerInp !bg-[transparent] text-[#EEEEEE] font-[300] text-[.75rem] shadow-none w-full border-0 outline-0 [&_.ant-select-selector]:!h-[2.25rem] [&_.ant-select-selector]:!flex [&_.ant-select-selector]:!items-center [&_.ant-select-selection-item]:!leading-normal";

// LLM metrics (vLLM, SGLang)
const metricItems = [
  { label: "Request in Queue", value: "bud:num_requests_waiting", type: "pod" as const, defaultValue: "5" },
  { label: "Running Requests", value: "bud:num_requests_running", type: "pod" as const, defaultValue: "10" },
  { label: "KV Cache Usage (%)", value: "bud:gpu_cache_usage_perc_average", type: "pod" as const, defaultValue: "0.8" },
  { label: "TTFT (s)", value: "bud:time_to_first_token_seconds_average", type: "pod" as const, defaultValue: "2" },
  { label: "TPOT (s)", value: "bud:time_per_output_token_seconds_average", type: "pod" as const, defaultValue: "0.1" },
  { label: "E2E Latency (s)", value: "bud:e2e_request_latency_seconds_average", type: "pod" as const, defaultValue: "10" },
];

// Select policy options
const selectPolicyOptions = [
  { label: "Max", value: "Max" },
  { label: "Min", value: "Min" },
  { label: "Disabled", value: "Disabled" },
];

// Schedule frequency options
const frequencyOptions = [
  { label: "Every day", value: "daily" },
  { label: "Weekdays (Mon-Fri)", value: "weekdays" },
  { label: "Weekends (Sat-Sun)", value: "weekends" },
  { label: "Specific days", value: "specific" },
];

// Days of week for specific day selection
const daysOfWeek = [
  { label: "Mon", value: "1" },
  { label: "Tue", value: "2" },
  { label: "Wed", value: "3" },
  { label: "Thu", value: "4" },
  { label: "Fri", value: "5" },
  { label: "Sat", value: "6" },
  { label: "Sun", value: "0" },
];

// Duration options
const durationOptions = [
  { label: "1 hour", value: "1h" },
  { label: "2 hours", value: "2h" },
  { label: "4 hours", value: "4h" },
  { label: "8 hours", value: "8h" },
  { label: "12 hours", value: "12h" },
  { label: "24 hours", value: "24h" },
];

// Parse cron expression to get schedule config
const parseCronExpression = (cron: string): { frequency: string; time: string; days: string[] } => {
  const parts = cron.split(" ");
  if (parts.length !== 5) {
    return { frequency: "daily", time: "09:00", days: [] };
  }

  const [minute, hour, , , dayOfWeek] = parts;
  const time = `${hour.padStart(2, "0")}:${minute.padStart(2, "0")}`;

  let frequency = "daily";
  let days: string[] = [];

  if (dayOfWeek === "*") {
    frequency = "daily";
  } else if (dayOfWeek === "1-5") {
    frequency = "weekdays";
  } else if (dayOfWeek === "0,6" || dayOfWeek === "6,0") {
    frequency = "weekends";
  } else {
    frequency = "specific";
    days = dayOfWeek.split(",");
  }

  return { frequency, time, days };
};

// Build cron expression from schedule config
const buildCronExpression = (frequency: string, time: string, days: string[]): string => {
  const [hour, minute] = time.split(":");
  const min = parseInt(minute) || 0;
  const hr = parseInt(hour) || 9;

  let dayOfWeek = "*";
  switch (frequency) {
    case "daily":
      dayOfWeek = "*";
      break;
    case "weekdays":
      dayOfWeek = "1-5";
      break;
    case "weekends":
      dayOfWeek = "0,6";
      break;
    case "specific":
      dayOfWeek = days.length > 0 ? days.join(",") : "*";
      break;
  }

  return `${min} ${hr} * * ${dayOfWeek}`;
};

// Default autoscale configuration with scale up stabilization = 30s
const defaultConfig: BudAIScalerConfig = {
  enabled: false,
  minReplicas: 1,
  maxReplicas: 10,
  scalingStrategy: "BudScaler",
  metricsSources: [],
  scheduleHints: [],
  predictionConfig: {
    enabled: false,
    lookAheadMinutes: 15,
    historyDays: 7,
    minConfidence: 0.7,
  },
  behavior: {
    scaleUp: {
      stabilizationWindowSeconds: 30, // Changed from 0 to 30
      policies: [
        { type: "Percent", value: 100, periodSeconds: 15 },
        { type: "Pods", value: 4, periodSeconds: 15 },
      ],
      selectPolicy: "Max",
    },
    scaleDown: {
      stabilizationWindowSeconds: 300,
      policies: [
        { type: "Percent", value: 100, periodSeconds: 15 },
      ],
      selectPolicy: "Min",
    },
  },
};

// Get default metric source
const getDefaultMetricSource = (): BudAIScalerMetricSource => {
  const defaultMetric = metricItems[0];
  return {
    type: defaultMetric.type,
    targetMetric: defaultMetric.value,
    targetValue: defaultMetric.defaultValue,  // Keep as string
  };
};

interface AutoscaleSettingsProps {
  deploymentId: string;
  projectId?: string;
}

export const AutoscaleSettings: React.FC<AutoscaleSettingsProps> = ({
  deploymentId,
  projectId,
}) => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [config, setConfig] = useState<BudAIScalerConfig>(defaultConfig);
  const [originalConfig, setOriginalConfig] = useState<BudAIScalerConfig>(defaultConfig);
  const [hasChanges, setHasChanges] = useState(false);

  const { getAutoscaleConfig, updateAutoscaleConfig } = useEndPoints();
  const { contextHolder, openConfirm } = useConfirmAction();

  // Load autoscale configuration
  useEffect(() => {
    const loadConfig = async () => {
      if (!deploymentId) return;

      setLoading(true);
      try {
        const response = await getAutoscaleConfig(deploymentId, projectId);
        if (response?.budaiscaler_config) {
          const loadedConfig = {
            ...defaultConfig,
            ...response.budaiscaler_config,
          };
          setConfig(loadedConfig);
          setOriginalConfig(loadedConfig);
        }
      } catch (error) {
        console.log("No existing autoscale config found, using defaults");
      } finally {
        setLoading(false);
      }
    };

    loadConfig();
  }, [deploymentId, projectId]);

  // Add default metric when autoscaling is enabled and no metrics exist
  useEffect(() => {
    if (config.enabled && (!config.metricsSources || config.metricsSources.length === 0)) {
      setConfig((prev) => ({
        ...prev,
        metricsSources: [getDefaultMetricSource()],
      }));
    }
  }, [config.enabled]);

  // Check for changes
  useEffect(() => {
    setHasChanges(JSON.stringify(config) !== JSON.stringify(originalConfig));
  }, [config, originalConfig]);

  // Update config helper
  const updateConfig = (updates: Partial<BudAIScalerConfig>) => {
    setConfig((prev) => ({ ...prev, ...updates }));
  };

  // Add a new metric source
  const addMetricSource = () => {
    updateConfig({
      metricsSources: [...(config.metricsSources || []), getDefaultMetricSource()],
    });
  };

  // Remove a metric source
  const removeMetricSource = (index: number) => {
    const sources = [...(config.metricsSources || [])];
    sources.splice(index, 1);
    updateConfig({ metricsSources: sources });
  };

  // Update a metric source
  const updateMetricSource = (index: number, updates: Partial<BudAIScalerMetricSource>) => {
    const sources = [...(config.metricsSources || [])];
    sources[index] = { ...sources[index], ...updates };
    updateConfig({ metricsSources: sources });
  };

  // Add a new schedule hint
  const addScheduleHint = () => {
    const newHint: BudAIScalerScheduleHint = {
      name: `schedule-${(config.scheduleHints?.length || 0) + 1}`,
      cronExpression: "0 9 * * 1-5",
      targetReplicas: 3,
      duration: "8h",
    };
    updateConfig({
      scheduleHints: [...(config.scheduleHints || []), newHint],
    });
  };

  // Remove a schedule hint
  const removeScheduleHint = (index: number) => {
    const hints = [...(config.scheduleHints || [])];
    hints.splice(index, 1);
    updateConfig({ scheduleHints: hints });
  };

  // Update a schedule hint
  const updateScheduleHint = (index: number, updates: Partial<BudAIScalerScheduleHint>) => {
    const hints = [...(config.scheduleHints || [])];
    hints[index] = { ...hints[index], ...updates };
    updateConfig({ scheduleHints: hints });
  };

  // Handle save
  const handleSave = async () => {
    openConfirm({
      message: "Update Autoscale Configuration",
      description: "Are you sure you want to update the autoscaling configuration? This will apply immediately to your deployment.",
      okText: "Yes, Update",
      cancelText: "Cancel",
      loading: saving,
      type: "warning",
      key: "update-autoscale",
      okAction: async () => {
        setSaving(true);
        try {
          await updateAutoscaleConfig(
            deploymentId,
            { budaiscaler_specification: config },
            projectId
          );
          setOriginalConfig(config);
          successToast("Autoscale configuration updated successfully");
        } catch (error: any) {
          const errorMessage = error?.response?.data?.message || error?.message || "Failed to update autoscale configuration";
          errorToast(errorMessage);
        } finally {
          setSaving(false);
        }
      },
      cancelAction: () => {},
    });
  };

  // Handle reset
  const handleReset = () => {
    setConfig(originalConfig);
  };

  if (loading) {
    return (
      <div className="mb-8 px-[1.4rem] py-[1.3rem] border border-[#1F1F1F] rounded-[.4rem] bg-[#101010] flex justify-center items-center min-h-[100px]">
        <Spin size="default" />
      </div>
    );
  }

  // Show saving overlay
  if (saving) {
    return (
      <div className="mb-8 px-[1.4rem] py-[1.3rem] border border-[#1F1F1F] rounded-[.4rem] bg-[#101010] flex flex-col justify-center items-center min-h-[100px] gap-2">
        <Spin size="default" />
        <Text_12_300_EEEEEE className="text-[#757575]">
          Updating autoscale configuration...
        </Text_12_300_EEEEEE>
      </div>
    );
  }

  return (
    <ConfigProvider theme={darkTheme}>
      {contextHolder}
      <div className="mb-8 px-[1.4rem] py-[1.3rem] border border-[#1F1F1F] rounded-[.4rem] bg-[#101010]">
        {/* Header with Enable Toggle */}
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2 flex-nowrap">
            <Text_12_300_EEEEEE className="whitespace-nowrap">
              Autoscaling
            </Text_12_300_EEEEEE>
            <CustomPopover title="Configure intelligent autoscaling with predictive scaling capabilities. Automatically adjusts replicas based on demand patterns and performance metrics.">
              <Image
                preview={false}
                src="/images/info.png"
                alt="info"
                style={{ width: ".75rem", height: ".75rem" }}
              />
            </CustomPopover>
          </div>

          <Switch
            size="small"
            className="[&_.ant-switch-checked]:bg-[#965CDE]"
            checked={config.enabled}
            onChange={(checked) => updateConfig({ enabled: checked })}
          />
        </div>

        {!config.enabled ? (
          <div className="text-center py-4">
            <Text_12_300_EEEEEE className="text-[#757575]">
              Autoscaling is disabled. Enable it to configure automatic replica scaling.
            </Text_12_300_EEEEEE>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Replica Limits */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-[#EEEEEE] text-xs mb-1">
                  Min Replicas
                  <CustomPopover title="Minimum number of replicas to maintain">
                    <Image
                      preview={false}
                      src="/images/info.png"
                      alt="info"
                      className="inline-block ml-1"
                      style={{ width: ".625rem", height: ".625rem" }}
                    />
                  </CustomPopover>
                </label>
                <InputNumber
                  value={config.minReplicas}
                  onChange={(value) => updateConfig({ minReplicas: value || 1 })}
                  min={0}
                  max={config.maxReplicas}
                  style={{ ...inputStyle, width: "100%" }}
                  className={inputClassName}
                />
              </div>
              <div>
                <label className="block text-[#EEEEEE] text-xs mb-1">
                  Max Replicas
                  <CustomPopover title="Maximum number of replicas to scale up to">
                    <Image
                      preview={false}
                      src="/images/info.png"
                      alt="info"
                      className="inline-block ml-1"
                      style={{ width: ".625rem", height: ".625rem" }}
                    />
                  </CustomPopover>
                </label>
                <InputNumber
                  value={config.maxReplicas}
                  onChange={(value) => updateConfig({ maxReplicas: value || 10 })}
                  min={config.minReplicas}
                  max={100}
                  style={{ ...inputStyle, width: "100%" }}
                  className={inputClassName}
                />
              </div>
            </div>

            {/* Metrics Sources */}
            <Collapse
              ghost
              className="bg-[#1a1a1a] border border-[#333] rounded-lg"
              items={[
                {
                  key: "metrics",
                  label: (
                    <div className="flex items-center justify-between w-full">
                      <Text_14_400_EEEEEE>Metrics Sources</Text_14_400_EEEEEE>
                      <span className="text-xs bg-[#965CDE] px-2 py-0.5 rounded text-white">
                        {config.metricsSources?.length || 0}
                      </span>
                    </div>
                  ),
                  children: (
                    <div className="space-y-3">
                      <Text_12_400_EEEEEE className="text-[#757575]">
                        Define metrics that trigger scaling decisions. At least one metric is required.
                      </Text_12_400_EEEEEE>

                      {config.metricsSources?.map((source, index) => (
                        <div key={index} className="border border-[#333] rounded-lg p-3">
                          <div className="flex justify-between items-center mb-2">
                            <Text_12_400_EEEEEE>Metric {index + 1}</Text_12_400_EEEEEE>
                            {(config.metricsSources?.length || 0) > 1 && (
                              <Button
                                type="text"
                                danger
                                icon={<DeleteOutlined />}
                                onClick={() => removeMetricSource(index)}
                                size="small"
                              />
                            )}
                          </div>
                          <div className="grid grid-cols-2 gap-3">
                            <div>
                              <label className="block text-[#EEEEEE] text-xs mb-1">Target Metric</label>
                              <Select
                                value={source.targetMetric}
                                onChange={(value) => {
                                  const selectedMetric = metricItems.find((m) => m.value === value);
                                  updateMetricSource(index, {
                                    targetMetric: value,
                                    type: selectedMetric?.type || "pod",
                                    targetValue: selectedMetric?.defaultValue || "0.8",
                                  });
                                }}
                                options={metricItems}
                                style={selectStyle}
                                className={selectClassName}
                              />
                            </div>
                            <div>
                              <label className="block text-[#EEEEEE] text-xs mb-1">Target Value</label>
                              <InputNumber
                                value={parseFloat(source.targetValue || "0.8")}
                                onChange={(value) => updateMetricSource(index, { targetValue: String(value || 0.8) })}
                                style={{ ...inputStyle, width: "100%" }}
                                className={inputClassName}
                                step={0.1}
                                min={0}
                              />
                            </div>
                          </div>
                        </div>
                      ))}

                      <Button
                        type="dashed"
                        icon={<PlusOutlined />}
                        onClick={addMetricSource}
                        className="w-full border-[#757575] text-[#EEEEEE] hover:border-[#965CDE] hover:text-[#965CDE]"
                      >
                        Add Metric Source
                      </Button>
                    </div>
                  ),
                },
              ]}
            />

            {/* Schedule Hints */}
            <Collapse
              ghost
              className="bg-[#1a1a1a] border border-[#333] rounded-lg"
              items={[
                {
                  key: "schedules",
                  label: (
                    <div className="flex items-center justify-between w-full">
                      <Text_14_400_EEEEEE>Schedule Hints</Text_14_400_EEEEEE>
                      <span className="text-xs bg-[#965CDE] px-2 py-0.5 rounded text-white">
                        {config.scheduleHints?.length || 0}
                      </span>
                    </div>
                  ),
                  children: (
                    <div className="space-y-3">
                      <Text_12_400_EEEEEE className="text-[#757575]">
                        Define time-based scaling rules for predictable traffic patterns like business hours or scheduled events.
                      </Text_12_400_EEEEEE>

                      {config.scheduleHints?.map((hint, index) => {
                        const { frequency, time, days } = parseCronExpression(hint.cronExpression);

                        const handleFrequencyChange = (newFrequency: string) => {
                          let newDays = days;
                          if (newFrequency === "specific" && days.length === 0) {
                            newDays = ["1"];
                          }
                          const newCron = buildCronExpression(newFrequency, time, newDays);
                          updateScheduleHint(index, { cronExpression: newCron });
                        };

                        const handleTimeChange = (newTime: dayjs.Dayjs | null) => {
                          if (newTime) {
                            const timeStr = newTime.format("HH:mm");
                            const newCron = buildCronExpression(frequency, timeStr, days);
                            updateScheduleHint(index, { cronExpression: newCron });
                          }
                        };

                        const toggleDay = (day: string) => {
                          let newDays = days.includes(day) ? days.filter((d) => d !== day) : [...days, day];
                          if (newDays.length === 0) {
                            newDays = [day];
                          }
                          const newCron = buildCronExpression(frequency, time, newDays);
                          updateScheduleHint(index, { cronExpression: newCron });
                        };

                        return (
                          <div key={index} className="border border-[#333] rounded-lg p-3">
                            <div className="flex justify-between items-center mb-3">
                              <Text_12_400_EEEEEE>Schedule {index + 1}</Text_12_400_EEEEEE>
                              <Button
                                type="text"
                                danger
                                icon={<DeleteOutlined />}
                                onClick={() => removeScheduleHint(index)}
                                size="small"
                              />
                            </div>

                            <div className="grid grid-cols-2 gap-3">
                              <div>
                                <label className="block text-[#EEEEEE] text-xs mb-1">Frequency</label>
                                <Select
                                  value={frequency}
                                  onChange={handleFrequencyChange}
                                  options={frequencyOptions}
                                  style={selectStyle}
                                  className={selectClassName}
                                />
                              </div>
                              <div>
                                <label className="block text-[#EEEEEE] text-xs mb-1">Start Time</label>
                                <TimePicker
                                  value={dayjs(time, "HH:mm")}
                                  onChange={handleTimeChange}
                                  format="HH:mm"
                                  style={{ ...inputStyle, width: "100%" }}
                                  className={inputClassName}
                                  popupClassName="dark-time-picker-dropdown"
                                />
                              </div>
                            </div>

                            {frequency === "specific" && (
                              <div className="mt-3">
                                <label className="block text-[#EEEEEE] text-xs mb-2">Select Days</label>
                                <div className="flex gap-2 w-full">
                                  {daysOfWeek.map((day) => (
                                    <button
                                      key={day.value}
                                      type="button"
                                      onClick={() => toggleDay(day.value)}
                                      className={`flex-1 px-2 py-1.5 rounded text-xs transition-colors ${
                                        days.includes(day.value)
                                          ? "bg-[#965CDE] text-white border border-[#965CDE]"
                                          : "bg-transparent text-[#EEEEEE] border border-[#757575] hover:border-[#965CDE]"
                                      }`}
                                    >
                                      {day.label}
                                    </button>
                                  ))}
                                </div>
                              </div>
                            )}

                            <div className="grid grid-cols-2 gap-3 mt-3">
                              <div>
                                <label className="block text-[#EEEEEE] text-xs mb-1">Target Replicas</label>
                                <InputNumber
                                  value={hint.targetReplicas}
                                  onChange={(value) => updateScheduleHint(index, { targetReplicas: value || 1 })}
                                  min={0}
                                  style={{ ...inputStyle, width: "100%" }}
                                  className={inputClassName}
                                />
                              </div>
                              <div>
                                <label className="block text-[#EEEEEE] text-xs mb-1">Duration</label>
                                <Select
                                  value={hint.duration || "8h"}
                                  onChange={(value) => updateScheduleHint(index, { duration: value })}
                                  options={durationOptions}
                                  style={selectStyle}
                                  className={selectClassName}
                                />
                              </div>
                            </div>
                          </div>
                        );
                      })}

                      <Button
                        type="dashed"
                        icon={<PlusOutlined />}
                        onClick={addScheduleHint}
                        className="w-full border-[#757575] text-[#EEEEEE] hover:border-[#965CDE] hover:text-[#965CDE]"
                      >
                        Add Schedule Hint
                      </Button>
                    </div>
                  ),
                },
              ]}
            />

            {/* Predictive Scaling */}
            <Collapse
              ghost
              className="bg-[#1a1a1a] border border-[#333] rounded-lg"
              items={[
                {
                  key: "prediction",
                  label: (
                    <div className="flex items-center justify-between w-full">
                      <Text_14_400_EEEEEE>Predictive Scaling</Text_14_400_EEEEEE>
                      <div onClick={(e) => e.stopPropagation()}>
                        <Switch
                          size="small"
                          checked={config.predictionConfig?.enabled}
                          onChange={(checked) =>
                            updateConfig({
                              predictionConfig: { ...config.predictionConfig!, enabled: checked },
                            })
                          }
                        />
                      </div>
                    </div>
                  ),
                  children: config.predictionConfig?.enabled ? (
                    <div className="space-y-3">
                      <Text_12_400_EEEEEE className="text-[#757575]">
                        Use ML-based predictions to proactively scale before traffic spikes.
                      </Text_12_400_EEEEEE>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="block text-[#EEEEEE] text-xs mb-1">Look Ahead (minutes)</label>
                          <InputNumber
                            value={config.predictionConfig?.lookAheadMinutes}
                            onChange={(value) =>
                              updateConfig({
                                predictionConfig: { ...config.predictionConfig!, lookAheadMinutes: value || 15 },
                              })
                            }
                            min={1}
                            max={60}
                            style={{ ...inputStyle, width: "100%" }}
                            className={inputClassName}
                          />
                        </div>
                        <div>
                          <label className="block text-[#EEEEEE] text-xs mb-1">History (days)</label>
                          <InputNumber
                            value={config.predictionConfig?.historyDays}
                            onChange={(value) =>
                              updateConfig({
                                predictionConfig: { ...config.predictionConfig!, historyDays: value || 7 },
                              })
                            }
                            min={1}
                            max={90}
                            style={{ ...inputStyle, width: "100%" }}
                            className={inputClassName}
                          />
                        </div>
                      </div>
                      <div>
                        <label className="block text-[#EEEEEE] text-xs mb-2">
                          Min Confidence: {((config.predictionConfig?.minConfidence || 0.7) * 100).toFixed(0)}%
                        </label>
                        <Slider
                          value={(config.predictionConfig?.minConfidence || 0.7) * 100}
                          onChange={(value) =>
                            updateConfig({
                              predictionConfig: { ...config.predictionConfig!, minConfidence: value / 100 },
                            })
                          }
                          min={0}
                          max={100}
                          tooltip={{
                            formatter: (value) => `${value}%`,
                          }}
                          styles={{
                            track: {
                              backgroundColor: "#965CDE",
                            },
                            rail: {
                              backgroundColor: "#333",
                            },
                          }}
                        />
                      </div>
                    </div>
                  ) : (
                    <Text_12_400_EEEEEE className="text-[#757575]">
                      Enable predictive scaling to configure ML-based predictions.
                    </Text_12_400_EEEEEE>
                  ),
                },
              ]}
            />

            {/* Scaling Behavior */}
            <Collapse
              ghost
              className="bg-[#1a1a1a] border border-[#333] rounded-lg"
              items={[
                {
                  key: "behavior",
                  label: <Text_14_400_EEEEEE>Scaling Behavior</Text_14_400_EEEEEE>,
                  children: (
                    <div className="space-y-4">
                      <Text_12_400_EEEEEE className="text-[#757575]">
                        Configure stabilization windows and scaling policies.
                      </Text_12_400_EEEEEE>

                      {/* Scale Up */}
                      <div className="border border-[#333] rounded-lg p-3">
                        <Text_12_400_EEEEEE className="mb-3 font-semibold block">Scale Up</Text_12_400_EEEEEE>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="block text-[#EEEEEE] text-xs mb-1">Stabilization (sec)</label>
                            <InputNumber
                              value={config.behavior?.scaleUp?.stabilizationWindowSeconds}
                              onChange={(value) =>
                                updateConfig({
                                  behavior: {
                                    ...config.behavior!,
                                    scaleUp: {
                                      ...config.behavior!.scaleUp!,
                                      stabilizationWindowSeconds: value || 0,
                                    },
                                  },
                                })
                              }
                              min={0}
                              max={3600}
                              style={{ ...inputStyle, width: "100%" }}
                              className={inputClassName}
                            />
                          </div>
                          <div>
                            <label className="block text-[#EEEEEE] text-xs mb-1">Select Policy</label>
                            <Select
                              value={config.behavior?.scaleUp?.selectPolicy}
                              onChange={(value) =>
                                updateConfig({
                                  behavior: {
                                    ...config.behavior!,
                                    scaleUp: {
                                      ...config.behavior!.scaleUp!,
                                      selectPolicy: value as "Max" | "Min" | "Disabled",
                                    },
                                  },
                                })
                              }
                              options={selectPolicyOptions}
                              style={selectStyle}
                              className={selectClassName}
                            />
                          </div>
                        </div>

                        {/* Scale Up Policies */}
                        <div className="grid grid-cols-2 gap-3 mt-3">
                          <div>
                            <label className="block text-[#EEEEEE] text-xs mb-1">Percent Value (%)</label>
                            <InputNumber
                              value={config.behavior?.scaleUp?.policies?.[0]?.value ?? 100}
                              onChange={(value) => {
                                const policies = [...(config.behavior?.scaleUp?.policies || [])];
                                policies[0] = { ...policies[0], type: "Percent", value: value || 100 };
                                updateConfig({
                                  behavior: {
                                    ...config.behavior!,
                                    scaleUp: { ...config.behavior!.scaleUp!, policies },
                                  },
                                });
                              }}
                              min={0}
                              max={100}
                              style={{ ...inputStyle, width: "100%" }}
                              className={inputClassName}
                            />
                          </div>
                          <div>
                            <label className="block text-[#EEEEEE] text-xs mb-1">Percent Period (sec)</label>
                            <InputNumber
                              value={config.behavior?.scaleUp?.policies?.[0]?.periodSeconds ?? 15}
                              onChange={(value) => {
                                const policies = [...(config.behavior?.scaleUp?.policies || [])];
                                policies[0] = { ...policies[0], type: "Percent", periodSeconds: value || 15 };
                                updateConfig({
                                  behavior: {
                                    ...config.behavior!,
                                    scaleUp: { ...config.behavior!.scaleUp!, policies },
                                  },
                                });
                              }}
                              min={1}
                              style={{ ...inputStyle, width: "100%" }}
                              className={inputClassName}
                            />
                          </div>
                          <div>
                            <label className="block text-[#EEEEEE] text-xs mb-1">Pods Value</label>
                            <InputNumber
                              value={config.behavior?.scaleUp?.policies?.[1]?.value ?? 4}
                              onChange={(value) => {
                                const policies = [...(config.behavior?.scaleUp?.policies || [])];
                                policies[1] = { ...policies[1], type: "Pods", value: value || 4 };
                                updateConfig({
                                  behavior: {
                                    ...config.behavior!,
                                    scaleUp: { ...config.behavior!.scaleUp!, policies },
                                  },
                                });
                              }}
                              min={1}
                              style={{ ...inputStyle, width: "100%" }}
                              className={inputClassName}
                            />
                          </div>
                          <div>
                            <label className="block text-[#EEEEEE] text-xs mb-1">Pods Period (sec)</label>
                            <InputNumber
                              value={config.behavior?.scaleUp?.policies?.[1]?.periodSeconds ?? 15}
                              onChange={(value) => {
                                const policies = [...(config.behavior?.scaleUp?.policies || [])];
                                policies[1] = { ...policies[1], type: "Pods", periodSeconds: value || 15 };
                                updateConfig({
                                  behavior: {
                                    ...config.behavior!,
                                    scaleUp: { ...config.behavior!.scaleUp!, policies },
                                  },
                                });
                              }}
                              min={1}
                              style={{ ...inputStyle, width: "100%" }}
                              className={inputClassName}
                            />
                          </div>
                        </div>
                      </div>

                      {/* Scale Down */}
                      <div className="border border-[#333] rounded-lg p-3">
                        <Text_12_400_EEEEEE className="mb-3 font-semibold block">Scale Down</Text_12_400_EEEEEE>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="block text-[#EEEEEE] text-xs mb-1">Stabilization (sec)</label>
                            <InputNumber
                              value={config.behavior?.scaleDown?.stabilizationWindowSeconds}
                              onChange={(value) =>
                                updateConfig({
                                  behavior: {
                                    ...config.behavior!,
                                    scaleDown: {
                                      ...config.behavior!.scaleDown!,
                                      stabilizationWindowSeconds: value || 0,
                                    },
                                  },
                                })
                              }
                              min={0}
                              max={3600}
                              style={{ ...inputStyle, width: "100%" }}
                              className={inputClassName}
                            />
                          </div>
                          <div>
                            <label className="block text-[#EEEEEE] text-xs mb-1">Select Policy</label>
                            <Select
                              value={config.behavior?.scaleDown?.selectPolicy}
                              onChange={(value) =>
                                updateConfig({
                                  behavior: {
                                    ...config.behavior!,
                                    scaleDown: {
                                      ...config.behavior!.scaleDown!,
                                      selectPolicy: value as "Max" | "Min" | "Disabled",
                                    },
                                  },
                                })
                              }
                              options={selectPolicyOptions}
                              style={selectStyle}
                              className={selectClassName}
                            />
                          </div>
                        </div>

                        {/* Scale Down Policies */}
                        <div className="grid grid-cols-2 gap-3 mt-3">
                          <div>
                            <label className="block text-[#EEEEEE] text-xs mb-1">Percent Value (%)</label>
                            <InputNumber
                              value={config.behavior?.scaleDown?.policies?.[0]?.value ?? 100}
                              onChange={(value) => {
                                const policies = [...(config.behavior?.scaleDown?.policies || [])];
                                policies[0] = { ...policies[0], type: "Percent", value: value || 100 };
                                updateConfig({
                                  behavior: {
                                    ...config.behavior!,
                                    scaleDown: { ...config.behavior!.scaleDown!, policies },
                                  },
                                });
                              }}
                              min={0}
                              max={100}
                              style={{ ...inputStyle, width: "100%" }}
                              className={inputClassName}
                            />
                          </div>
                          <div>
                            <label className="block text-[#EEEEEE] text-xs mb-1">Percent Period (sec)</label>
                            <InputNumber
                              value={config.behavior?.scaleDown?.policies?.[0]?.periodSeconds ?? 15}
                              onChange={(value) => {
                                const policies = [...(config.behavior?.scaleDown?.policies || [])];
                                policies[0] = { ...policies[0], type: "Percent", periodSeconds: value || 15 };
                                updateConfig({
                                  behavior: {
                                    ...config.behavior!,
                                    scaleDown: { ...config.behavior!.scaleDown!, policies },
                                  },
                                });
                              }}
                              min={1}
                              style={{ ...inputStyle, width: "100%" }}
                              className={inputClassName}
                            />
                          </div>
                        </div>
                      </div>
                    </div>
                  ),
                },
              ]}
            />

          </div>
        )}

        {/* Save/Reset Buttons - Outside enabled conditional so they show when disabling */}
        {hasChanges && (
          <div className="flex justify-end gap-3 pt-4 mt-4 border-t border-[#333]">
            <Button
              onClick={handleReset}
              className="bg-transparent border-[#757575] text-[#EEEEEE] hover:border-[#EEEEEE] hover:text-[#FFFFFF]"
            >
              Reset
            </Button>
            <Button
              type="primary"
              onClick={handleSave}
              loading={saving}
              className="bg-[#965CDE] !border-[#965CDE] hover:bg-[#7A4BC7] hover:!border-[#7A4BC7] !shadow-none"
            >
              Save Autoscale Settings
            </Button>
          </div>
        )}
      </div>
    </ConfigProvider>
  );
};

export default AutoscaleSettings;

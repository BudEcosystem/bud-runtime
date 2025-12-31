import { useEffect } from "react";
import { Switch, ConfigProvider, Select, InputNumber, Slider, Button, TimePicker, Input } from "antd";
import { PlusOutlined, DeleteOutlined } from "@ant-design/icons";
import dayjs from "dayjs";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DeployModelSpecificationInfo from "@/components/ui/bud/deploymentDrawer/DeployModelSpecificationInfo";
import { useDrawer } from "src/hooks/useDrawer";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import { useDeployModel, BudAIScalerSpecification, BudScalerMetricSource, BudScalerScheduleHint } from "src/stores/useDeployModel";
import TextInput from "../components/TextInput";
import FloatLabel from "@/components/ui/bud/dataEntry/FloatLabel";
import InfoLabel from "@/components/ui/bud/dataEntry/InfoLabel";
import { Text_12_400_EEEEEE, Text_14_400_EEEEEE, Text_14_600_EEEEEE } from "@/components/ui/text";

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
    TimePicker: {
      activeBg: "transparent",
      cellActiveWithRangeBg: "#965CDE40",
      cellHoverBg: "#FFFFFF15",
      cellBg: "transparent",
    },
    DatePicker: {
      cellActiveWithRangeBg: "#965CDE40",
      cellHoverBg: "#FFFFFF15",
      activeBg: "transparent",
    },
    Input: {
      activeBg: "transparent",
      hoverBg: "#FFFFFF08",
    },
  },
};

// Common input styling matching TextInput pattern
const selectStyle: React.CSSProperties = {
  backgroundColor: "transparent",
  color: "#EEEEEE",
  border: "0.5px solid #757575",
};

const selectClassName = "drawerInp !bg-[transparent] text-[#EEEEEE] font-[300] text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0";

// For InputNumber, TimePicker, and Input
const inputStyle: React.CSSProperties = {
  backgroundColor: "transparent",
  color: "#EEEEEE",
  border: "0.5px solid #757575",
  paddingTop: ".45rem",
  paddingBottom: ".45rem",
  paddingLeft: ".5rem",
  paddingRight: "1rem",
};

const inputClassName = "!bg-transparent !shadow-none border border-[#757575] hover:!border-[#CFCFCF] hover:!bg-[#FFFFFF08]";

// LLM/Audio metrics (vLLM, SGLang)
const llmMetricItems = [
  { label: "Request in Queue", value: "bud:num_requests_waiting", type: "pod" as const, defaultValue: "5" },
  { label: "Running Requests", value: "bud:num_requests_running", type: "pod" as const, defaultValue: "10" },
  { label: "KV Cache Usage", value: "bud:gpu_cache_usage_perc_average", type: "pod" as const, defaultValue: "0.8" },
  { label: "TTFT", value: "bud:time_to_first_token_seconds_average", type: "pod" as const, defaultValue: "2" },
  { label: "TPOT", value: "bud:time_per_output_token_seconds_average", type: "pod" as const, defaultValue: "0.1" },
  { label: "E2E Latency", value: "bud:e2e_request_latency_seconds_average", type: "pod" as const, defaultValue: "10" },
];

// Embedding metrics (LatentBud)
const embeddingMetricItems = [
  { label: "Request in Queue", value: "embedding_batch_queue_size", type: "pod" as const, defaultValue: "10" },
  { label: "Request Latency", value: "bud:e2e_request_latency_seconds_average", type: "pod" as const, defaultValue: "2" },
];

// Get metrics based on model type
const getMetricItems = (modelType: "llm" | "embedding" | "audio") => {
  if (modelType === "embedding") return embeddingMetricItems;
  return llmMetricItems; // LLM and Audio use same metrics
};

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

// Select policy options for scaling behavior
const selectPolicyOptions = [
  { label: "Max", value: "Max" },
  { label: "Min", value: "Min" },
  { label: "Disabled", value: "Disabled" },
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

// Schedule hint editor component
const ScheduleHintEditor = ({
  hint,
  index,
  onUpdate,
  onRemove,
}: {
  hint: BudScalerScheduleHint;
  index: number;
  onUpdate: (index: number, updates: Partial<BudScalerScheduleHint>) => void;
  onRemove: (index: number) => void;
}) => {
  const { frequency, time, days } = parseCronExpression(hint.cronExpression);

  const handleFrequencyChange = (newFrequency: string) => {
    // When switching to "specific", initialize with Monday selected if no days
    let newDays = days;
    if (newFrequency === "specific" && days.length === 0) {
      newDays = ["1"]; // Default to Monday
    }
    const newCron = buildCronExpression(newFrequency, time, newDays);
    onUpdate(index, { cronExpression: newCron });
  };

  const handleTimeChange = (newTime: dayjs.Dayjs | null) => {
    if (newTime) {
      const timeStr = newTime.format("HH:mm");
      const newCron = buildCronExpression(frequency, timeStr, days);
      onUpdate(index, { cronExpression: newCron });
    }
  };

  const toggleDay = (day: string) => {
    let newDays = days.includes(day) ? days.filter((d) => d !== day) : [...days, day];
    // Ensure at least one day is selected for "specific" frequency
    if (newDays.length === 0) {
      newDays = [day]; // Keep the clicked day if it would result in empty
    }
    const newCron = buildCronExpression(frequency, time, newDays);
    onUpdate(index, { cronExpression: newCron });
  };

  return (
    <ConfigProvider theme={darkTheme}>
      <div className="border border-[#333] rounded-lg p-3 mb-3">
        <div className="flex justify-between items-center mb-3">
          <Text_12_400_EEEEEE>Schedule {index + 1}</Text_12_400_EEEEEE>
          <Button
            type="text"
            danger
            icon={<DeleteOutlined />}
            onClick={() => onRemove(index)}
            size="small"
          />
        </div>

        <div className="grid grid-cols-2 gap-3 mt-2">
          <div className="floating-textarea">
            <FloatLabel
              label={<InfoLabel text="Frequency" content="How often the schedule runs" />}
              value={frequency}
            >
              <div className="custom-select-two w-full rounded-[6px]">
                <Select
                  value={frequency}
                  onChange={handleFrequencyChange}
                  options={frequencyOptions}
                  style={selectStyle}
                  size="large"
                  className={selectClassName}
                />
              </div>
            </FloatLabel>
          </div>
          <div className="floating-textarea">
            <FloatLabel
              label={<InfoLabel text="Start Time" content="Time when scaling begins" />}
              value={time}
            >
              <TimePicker
                value={dayjs(time, "HH:mm")}
                onChange={handleTimeChange}
                format="HH:mm"
                style={{ ...inputStyle, width: "100%", paddingTop: ".65rem", paddingBottom: ".65rem", paddingLeft: "1.25rem" }}
                className={inputClassName}
                popupClassName="dark-time-picker-dropdown"
              />
            </FloatLabel>
          </div>

          {frequency === "specific" && (
            <div className="col-span-2 mb-3">
              <Text_12_400_EEEEEE className="mb-2 block">Select Days</Text_12_400_EEEEEE>
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

          <div className="floating-textarea">
            <FloatLabel
              label={<InfoLabel text="Target Replicas" content="Number of replicas to scale to" />}
              value={hint.targetReplicas}
            >
              <InputNumber
                value={hint.targetReplicas}
                onChange={(value) => onUpdate(index, { targetReplicas: value || 1 })}
                min={0}
                style={{ ...inputStyle, width: "100%" }}
                className={inputClassName}
              />
            </FloatLabel>
          </div>
          <div className="floating-textarea">
            <FloatLabel
              label={<InfoLabel text="Duration" content="How long the schedule runs" />}
              value={hint.duration}
            >
              <div className="custom-select-two w-full rounded-[6px]">
                <Select
                  value={hint.duration || "8h"}
                  onChange={(value) => onUpdate(index, { duration: value })}
                  options={[
                    { label: "1 hour", value: "1h" },
                    { label: "2 hours", value: "2h" },
                    { label: "4 hours", value: "4h" },
                    { label: "8 hours", value: "8h" },
                    { label: "12 hours", value: "12h" },
                    { label: "24 hours", value: "24h" },
                  ]}
                  style={selectStyle}
                  size="large"
                  className={selectClassName}
                />
              </div>
            </FloatLabel>
          </div>
        </div>
      </div>
    </ConfigProvider>
  );
};

export default function DeployModelBudAIScaler() {
  const { openDrawerWithStep } = useDrawer();
  const {
    budaiscalerSpecification,
    setBudAIScalerSpecification,
    updateBudAIScalerSpecification,
    currentWorkflow,
    selectedModel,
  } = useDeployModel();

  // Use LLM/vLLM metrics for all model types since vLLM is the default engine
  // LatentBud-specific metrics (like embedding_batch_queue_size) require explicit engine selection
  const metricItems = getMetricItems("llm");

  // Update a specific field in the specification
  const updateSpec = (updates: Partial<BudAIScalerSpecification>) => {
    setBudAIScalerSpecification(updates);
  };

  // Initialize default metric source when autoscaling is enabled (1 metric is mandatory)
  useEffect(() => {
    if (budaiscalerSpecification.enabled && budaiscalerSpecification.metricsSources.length === 0) {
      const defaultMetric = metricItems[0];
      setBudAIScalerSpecification({
        metricsSources: [
          {
            type: defaultMetric.type,
            targetMetric: defaultMetric.value,
            targetValue: defaultMetric.defaultValue,
          },
        ],
      });
    }
  }, [budaiscalerSpecification.enabled, metricItems]);

  // Add a new metric source with model-specific defaults
  const addMetricSource = () => {
    const defaultMetric = metricItems[0];
    const newSource: BudScalerMetricSource = {
      type: defaultMetric.type,
      targetMetric: defaultMetric.value,
      targetValue: defaultMetric.defaultValue,
    };
    updateSpec({
      metricsSources: [...budaiscalerSpecification.metricsSources, newSource],
    });
  };

  // Remove a metric source
  const removeMetricSource = (index: number) => {
    const sources = [...budaiscalerSpecification.metricsSources];
    sources.splice(index, 1);
    updateSpec({ metricsSources: sources });
  };

  // Update a metric source
  const updateMetricSource = (index: number, updates: Partial<BudScalerMetricSource>) => {
    const sources = [...budaiscalerSpecification.metricsSources];
    sources[index] = { ...sources[index], ...updates };
    updateSpec({ metricsSources: sources });
  };

  // Add a new schedule hint
  const addScheduleHint = () => {
    const newHint: BudScalerScheduleHint = {
      name: `schedule-${budaiscalerSpecification.scheduleHints.length + 1}`,
      cronExpression: "0 9 * * 1-5",
      targetReplicas: 3,
      duration: "8h",
    };
    updateSpec({
      scheduleHints: [...budaiscalerSpecification.scheduleHints, newHint],
    });
  };

  // Remove a schedule hint
  const removeScheduleHint = (index: number) => {
    const hints = [...budaiscalerSpecification.scheduleHints];
    hints.splice(index, 1);
    updateSpec({ scheduleHints: hints });
  };

  // Update a schedule hint
  const updateScheduleHint = (index: number, updates: Partial<BudScalerScheduleHint>) => {
    const hints = [...budaiscalerSpecification.scheduleHints];
    hints[index] = { ...hints[index], ...updates };
    updateSpec({ scheduleHints: hints });
  };

  return (
    <BudForm
      data={{
        enabled: budaiscalerSpecification.enabled,
        minReplicas: budaiscalerSpecification.minReplicas,
        maxReplicas: budaiscalerSpecification.maxReplicas,
        lookAheadMinutes: budaiscalerSpecification.predictionConfig.lookAheadMinutes,
        historyDays: budaiscalerSpecification.predictionConfig.historyDays,
      }}
      onBack={() => {
        openDrawerWithStep("deploy-model-configuration", { direction: "backward" });
      }}
      onNext={async () => {
        const result = await updateBudAIScalerSpecification();
        if (result) {
          openDrawerWithStep("deploy-model-status");
        }
      }}
      nextText="Deploy"
      backText="Back"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DeployModelSpecificationInfo />
        </BudDrawerLayout>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="BudAI Scaler Configuration"
            description="Configure intelligent autoscaling with predictive scaling capabilities. BudAIScaler automatically adjusts your model replicas based on demand patterns and performance metrics."
            classNames="border-[0] border-b-[.5px]"
          />

          {/* Enable Autoscaling Toggle */}
          <DrawerCard>
            <div className="flex justify-between items-center mt-1">
              <Text_14_400_EEEEEE>Enable autoscaling</Text_14_400_EEEEEE>
              <ConfigProvider
                theme={{
                  token: {
                    colorPrimary: "#965CDE",
                  },
                }}
              >
                <Switch
                  checked={budaiscalerSpecification.enabled}
                  onChange={(checked) => updateSpec({ enabled: checked })}
                />
              </ConfigProvider>
            </div>
          </DrawerCard>

          {budaiscalerSpecification.enabled && (
            <>
              {/* Basic Configuration */}
              <DrawerCard>
                <Text_14_600_EEEEEE className="mb-4">Replica Limits</Text_14_600_EEEEEE>

                <div className="flex flex-row gap-[1rem] justify-between w-full">
                  <TextInput
                    name="minReplicas"
                    label="Min Replicas"
                    placeholder="Enter Min Replicas"
                    rules={[{ required: true, message: "Please enter Min Replicas" }]}
                    ClassNames="mt-[.4rem] w-1/2"
                    formItemClassnames="w-full"
                    infoText="Minimum number of replicas your inference can scale down to"
                    onChange={(e) => updateSpec({ minReplicas: parseInt(e) || 1 })}
                  />
                  <TextInput
                    name="maxReplicas"
                    label="Max Replicas"
                    placeholder="Enter Max Replicas"
                    rules={[{ required: true, message: "Please enter Max Replicas" }]}
                    ClassNames="mt-[.4rem] w-1/2"
                    formItemClassnames="w-full"
                    infoText="Maximum number of replicas your inference can scale up to"
                    onChange={(e) => updateSpec({ maxReplicas: parseInt(e) || 10 })}
                  />
                </div>
              </DrawerCard>

              {/* Metrics Sources */}
              <DrawerCard>
                <div className="flex justify-between items-center mb-2">
                  <Text_14_600_EEEEEE>Metrics Sources</Text_14_600_EEEEEE>
                  <Button
                    type="text"
                    icon={<PlusOutlined />}
                    onClick={addMetricSource}
                    style={{ color: "#965CDE" }}
                  >
                    Add Source
                  </Button>
                </div>
                <Text_12_400_EEEEEE className="opacity-60 mb-4">
                  Define the metrics used to trigger scaling decisions. Configure thresholds for GPU usage, latency, or custom metrics.
                </Text_12_400_EEEEEE>

                {budaiscalerSpecification.metricsSources.length === 0 ? (
                  <Text_12_400_EEEEEE className="opacity-60">
                    No metric sources configured. Default metrics will be used based on the model type.
                  </Text_12_400_EEEEEE>
                ) : (
                  <ConfigProvider theme={darkTheme}>
                    {budaiscalerSpecification.metricsSources.map((source, index) => (
                      <div key={index} className="border border-[#333] rounded-lg p-3 mb-3">
                        <div className="flex justify-between items-center mb-3">
                          <Text_12_400_EEEEEE>Source {index + 1}</Text_12_400_EEEEEE>
                          {budaiscalerSpecification.metricsSources.length > 1 && (
                            <Button
                              type="text"
                              danger
                              icon={<DeleteOutlined />}
                              onClick={() => removeMetricSource(index)}
                              size="small"
                            />
                          )}
                        </div>
                        <div className="grid grid-cols-2 gap-3 mt-2">
                          <div className="floating-textarea">
                            <FloatLabel
                              label={<InfoLabel text="Target Metric" content="Metric to monitor for scaling decisions" />}
                              value={source.targetMetric}
                            >
                              <div className="custom-select-two w-full rounded-[6px]">
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
                                  size="large"
                                  className={selectClassName}
                                />
                              </div>
                            </FloatLabel>
                          </div>
                          <div className="floating-textarea">
                            <FloatLabel
                              label={<InfoLabel text="Target Value" content="Threshold value that triggers scaling" />}
                              value={source.targetValue}
                            >
                              <InputNumber
                                value={parseFloat(source.targetValue || "0.8")}
                                onChange={(value) => updateMetricSource(index, { targetValue: String(value) })}
                                style={{ ...inputStyle, width: "100%" }}
                                className={inputClassName}
                                step={0.1}
                                min={0}
                                max={100}
                              />
                            </FloatLabel>
                          </div>
                        </div>
                      </div>
                    ))}
                  </ConfigProvider>
                )}
              </DrawerCard>

              {/* Predictive Scaling */}
              <DrawerCard>
                <ConfigProvider theme={darkTheme}>
                  <div className="flex justify-between items-center mb-2">
                    <Text_14_600_EEEEEE>Predictive Scaling</Text_14_600_EEEEEE>
                    <Switch
                      checked={budaiscalerSpecification.predictionConfig.enabled}
                      onChange={(checked) =>
                        updateSpec({
                          predictionConfig: { ...budaiscalerSpecification.predictionConfig, enabled: checked },
                        })
                      }
                      size="small"
                    />
                  </div>
                  <Text_12_400_EEEEEE className="opacity-60 mb-4">
                    Enable ML-based predictions to proactively scale before traffic spikes occur, based on historical patterns.
                  </Text_12_400_EEEEEE>

                  {budaiscalerSpecification.predictionConfig.enabled && (
                    <>
                      <div className="flex flex-row gap-[1rem] justify-between w-full">
                        <TextInput
                          name="lookAheadMinutes"
                          label="Look Ahead (minutes)"
                          placeholder="15"
                          rules={[]}
                          ClassNames="mt-[.4rem] w-1/2"
                          formItemClassnames="w-full"
                          infoText="How far ahead to predict scaling needs (1-60 minutes)"
                          onChange={(e) =>
                            updateSpec({
                              predictionConfig: { ...budaiscalerSpecification.predictionConfig, lookAheadMinutes: parseInt(e) || 15 },
                            })
                          }
                        />
                        <TextInput
                          name="historyDays"
                          label="History (days)"
                          placeholder="7"
                          rules={[]}
                          ClassNames="mt-[.4rem] w-1/2"
                          formItemClassnames="w-full"
                          infoText="Historical data window for predictions (1-90 days)"
                          onChange={(e) =>
                            updateSpec({
                              predictionConfig: { ...budaiscalerSpecification.predictionConfig, historyDays: parseInt(e) || 7 },
                            })
                          }
                        />
                      </div>

                      <div className="mt-2">
                        <Text_12_400_EEEEEE className="mb-1">
                          Min Confidence: {(budaiscalerSpecification.predictionConfig.minConfidence * 100).toFixed(0)}%
                        </Text_12_400_EEEEEE>
                        <Slider
                          value={budaiscalerSpecification.predictionConfig.minConfidence * 100}
                          onChange={(value) =>
                            updateSpec({
                              predictionConfig: { ...budaiscalerSpecification.predictionConfig, minConfidence: value / 100 },
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
                              backgroundColor: "#212225",
                            },
                          }}
                        />
                      </div>
                    </>
                  )}
                </ConfigProvider>
              </DrawerCard>

              {/* Schedule Hints */}
              <DrawerCard>
                <div className="flex justify-between items-center mb-2">
                  <div className="flex items-center gap-2">
                    <Text_14_600_EEEEEE>Schedule Hints</Text_14_600_EEEEEE>
                    {budaiscalerSpecification.scheduleHints.length > 0 && (
                      <span className="text-xs bg-[#965CDE] px-2 py-0.5 rounded text-white">
                        {budaiscalerSpecification.scheduleHints.length}
                      </span>
                    )}
                  </div>
                  <Button
                    type="text"
                    icon={<PlusOutlined />}
                    onClick={addScheduleHint}
                    size="small"
                    style={{ color: "#965CDE" }}
                  >
                    Add
                  </Button>
                </div>
                <Text_12_400_EEEEEE className="opacity-60 mb-4">
                  Define time-based scaling rules for predictable traffic patterns like business hours or scheduled events.
                </Text_12_400_EEEEEE>

                {budaiscalerSpecification.scheduleHints.length === 0 ? (
                  <Text_12_400_EEEEEE className="opacity-60">
                    No schedule hints configured. Add hints to pre-scale based on known traffic patterns.
                  </Text_12_400_EEEEEE>
                ) : (
                  budaiscalerSpecification.scheduleHints.map((hint, index) => (
                    <ScheduleHintEditor
                      key={index}
                      hint={hint}
                      index={index}
                      onUpdate={updateScheduleHint}
                      onRemove={removeScheduleHint}
                    />
                  ))
                )}
              </DrawerCard>

              {/* Scaling Behavior */}
              <DrawerCard>
                <Text_14_600_EEEEEE className="mb-2">Scaling Behavior</Text_14_600_EEEEEE>
                <Text_12_400_EEEEEE className="opacity-60 mb-4">
                  Configure stabilization windows and scaling policies to control how quickly replicas scale up or down.
                </Text_12_400_EEEEEE>

                <ConfigProvider theme={darkTheme}>
                  {/* Scale Up Section */}
                  <div className="border border-[#333] rounded-lg p-3 mb-3">
                    <Text_12_400_EEEEEE className="mb-3 block font-semibold">Scale Up</Text_12_400_EEEEEE>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="floating-textarea">
                        <FloatLabel
                          label={<InfoLabel text="Stabilization (sec)" content="Time to wait before scaling up after metrics trigger" />}
                          value={budaiscalerSpecification.behavior.scaleUp.stabilizationWindowSeconds}
                        >
                          <InputNumber
                            value={budaiscalerSpecification.behavior.scaleUp.stabilizationWindowSeconds}
                            onChange={(value) =>
                              updateSpec({
                                behavior: {
                                  ...budaiscalerSpecification.behavior,
                                  scaleUp: {
                                    ...budaiscalerSpecification.behavior.scaleUp,
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
                        </FloatLabel>
                      </div>
                      <div className="floating-textarea">
                        <FloatLabel
                          label={<InfoLabel text="Select Policy" content="How to select among multiple scaling policies" />}
                          value={budaiscalerSpecification.behavior.scaleUp.selectPolicy}
                        >
                          <div className="custom-select-two w-full rounded-[6px]">
                            <Select
                              value={budaiscalerSpecification.behavior.scaleUp.selectPolicy}
                              onChange={(value) =>
                                updateSpec({
                                  behavior: {
                                    ...budaiscalerSpecification.behavior,
                                    scaleUp: {
                                      ...budaiscalerSpecification.behavior.scaleUp,
                                      selectPolicy: value as "Max" | "Min" | "Disabled",
                                    },
                                  },
                                })
                              }
                              options={selectPolicyOptions}
                              style={selectStyle}
                              size="large"
                              className={selectClassName}
                            />
                          </div>
                        </FloatLabel>
                      </div>
                    </div>

                    {/* Scale Up Policies */}
                    <div className="grid grid-cols-2 gap-3 mt-3">
                      <div className="floating-textarea">
                        <FloatLabel
                          label={<InfoLabel text="Percent Value (%)" content="Max percentage of current replicas to add per scaling iteration" />}
                          value={budaiscalerSpecification.behavior.scaleUp.policies[0]?.value ?? 100}
                        >
                          <InputNumber
                            value={budaiscalerSpecification.behavior.scaleUp.policies[0]?.value ?? 100}
                            onChange={(value) => {
                              const policies = [...budaiscalerSpecification.behavior.scaleUp.policies];
                              policies[0] = { ...policies[0], type: "Percent", value: value || 100 };
                              updateSpec({
                                behavior: {
                                  ...budaiscalerSpecification.behavior,
                                  scaleUp: { ...budaiscalerSpecification.behavior.scaleUp, policies },
                                },
                              });
                            }}
                            min={0}
                            max={100}
                            style={{ ...inputStyle, width: "100%" }}
                            className={inputClassName}
                          />
                        </FloatLabel>
                      </div>
                      <div className="floating-textarea">
                        <FloatLabel
                          label={<InfoLabel text="Percent Period (sec)" content="Time interval between percent-based scaling iterations" />}
                          value={budaiscalerSpecification.behavior.scaleUp.policies[0]?.periodSeconds ?? 15}
                        >
                          <InputNumber
                            value={budaiscalerSpecification.behavior.scaleUp.policies[0]?.periodSeconds ?? 15}
                            onChange={(value) => {
                              const policies = [...budaiscalerSpecification.behavior.scaleUp.policies];
                              policies[0] = { ...policies[0], type: "Percent", periodSeconds: value || 15 };
                              updateSpec({
                                behavior: {
                                  ...budaiscalerSpecification.behavior,
                                  scaleUp: { ...budaiscalerSpecification.behavior.scaleUp, policies },
                                },
                              });
                            }}
                            min={1}
                            style={{ ...inputStyle, width: "100%" }}
                            className={inputClassName}
                          />
                        </FloatLabel>
                      </div>
                      <div className="floating-textarea">
                        <FloatLabel
                          label={<InfoLabel text="Pods Value" content="Max number of pods to add per scaling iteration" />}
                          value={budaiscalerSpecification.behavior.scaleUp.policies[1]?.value ?? 4}
                        >
                          <InputNumber
                            value={budaiscalerSpecification.behavior.scaleUp.policies[1]?.value ?? 4}
                            onChange={(value) => {
                              const policies = [...budaiscalerSpecification.behavior.scaleUp.policies];
                              policies[1] = { ...policies[1], type: "Pods", value: value || 4 };
                              updateSpec({
                                behavior: {
                                  ...budaiscalerSpecification.behavior,
                                  scaleUp: { ...budaiscalerSpecification.behavior.scaleUp, policies },
                                },
                              });
                            }}
                            min={1}
                            style={{ ...inputStyle, width: "100%" }}
                            className={inputClassName}
                          />
                        </FloatLabel>
                      </div>
                      <div className="floating-textarea">
                        <FloatLabel
                          label={<InfoLabel text="Pods Period (sec)" content="Time interval between pod-based scaling iterations" />}
                          value={budaiscalerSpecification.behavior.scaleUp.policies[1]?.periodSeconds ?? 15}
                        >
                          <InputNumber
                            value={budaiscalerSpecification.behavior.scaleUp.policies[1]?.periodSeconds ?? 15}
                            onChange={(value) => {
                              const policies = [...budaiscalerSpecification.behavior.scaleUp.policies];
                              policies[1] = { ...policies[1], type: "Pods", periodSeconds: value || 15 };
                              updateSpec({
                                behavior: {
                                  ...budaiscalerSpecification.behavior,
                                  scaleUp: { ...budaiscalerSpecification.behavior.scaleUp, policies },
                                },
                              });
                            }}
                            min={1}
                            style={{ ...inputStyle, width: "100%" }}
                            className={inputClassName}
                          />
                        </FloatLabel>
                      </div>
                    </div>
                  </div>

                  {/* Scale Down Section */}
                  <div className="border border-[#333] rounded-lg p-3">
                    <Text_12_400_EEEEEE className="mb-3 block font-semibold">Scale Down</Text_12_400_EEEEEE>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="floating-textarea">
                        <FloatLabel
                          label={<InfoLabel text="Stabilization (sec)" content="Time to wait before scaling down after metrics stabilize" />}
                          value={budaiscalerSpecification.behavior.scaleDown.stabilizationWindowSeconds}
                        >
                          <InputNumber
                            value={budaiscalerSpecification.behavior.scaleDown.stabilizationWindowSeconds}
                            onChange={(value) =>
                              updateSpec({
                                behavior: {
                                  ...budaiscalerSpecification.behavior,
                                  scaleDown: {
                                    ...budaiscalerSpecification.behavior.scaleDown,
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
                        </FloatLabel>
                      </div>
                      <div className="floating-textarea">
                        <FloatLabel
                          label={<InfoLabel text="Select Policy" content="How to select among multiple scaling policies" />}
                          value={budaiscalerSpecification.behavior.scaleDown.selectPolicy}
                        >
                          <div className="custom-select-two w-full rounded-[6px]">
                            <Select
                              value={budaiscalerSpecification.behavior.scaleDown.selectPolicy}
                              onChange={(value) =>
                                updateSpec({
                                  behavior: {
                                    ...budaiscalerSpecification.behavior,
                                    scaleDown: {
                                      ...budaiscalerSpecification.behavior.scaleDown,
                                      selectPolicy: value as "Max" | "Min" | "Disabled",
                                    },
                                  },
                                })
                              }
                              options={selectPolicyOptions}
                              style={selectStyle}
                              size="large"
                              className={selectClassName}
                            />
                          </div>
                        </FloatLabel>
                      </div>
                    </div>

                    {/* Scale Down Policies */}
                    <div className="grid grid-cols-2 gap-3 mt-3">
                      <div className="floating-textarea">
                        <FloatLabel
                          label={<InfoLabel text="Percent Value (%)" content="Max percentage of current replicas to remove per scaling iteration" />}
                          value={budaiscalerSpecification.behavior.scaleDown.policies[0]?.value ?? 100}
                        >
                          <InputNumber
                            value={budaiscalerSpecification.behavior.scaleDown.policies[0]?.value ?? 100}
                            onChange={(value) => {
                              const policies = [...budaiscalerSpecification.behavior.scaleDown.policies];
                              policies[0] = { ...policies[0], type: "Percent", value: value || 100 };
                              updateSpec({
                                behavior: {
                                  ...budaiscalerSpecification.behavior,
                                  scaleDown: { ...budaiscalerSpecification.behavior.scaleDown, policies },
                                },
                              });
                            }}
                            min={0}
                            max={100}
                            style={{ ...inputStyle, width: "100%" }}
                            className={inputClassName}
                          />
                        </FloatLabel>
                      </div>
                      <div className="floating-textarea">
                        <FloatLabel
                          label={<InfoLabel text="Percent Period (sec)" content="Time interval between percent-based scaling iterations" />}
                          value={budaiscalerSpecification.behavior.scaleDown.policies[0]?.periodSeconds ?? 15}
                        >
                          <InputNumber
                            value={budaiscalerSpecification.behavior.scaleDown.policies[0]?.periodSeconds ?? 15}
                            onChange={(value) => {
                              const policies = [...budaiscalerSpecification.behavior.scaleDown.policies];
                              policies[0] = { ...policies[0], type: "Percent", periodSeconds: value || 15 };
                              updateSpec({
                                behavior: {
                                  ...budaiscalerSpecification.behavior,
                                  scaleDown: { ...budaiscalerSpecification.behavior.scaleDown, policies },
                                },
                              });
                            }}
                            min={1}
                            style={{ ...inputStyle, width: "100%" }}
                            className={inputClassName}
                          />
                        </FloatLabel>
                      </div>
                      <div className="floating-textarea">
                        <FloatLabel
                          label={<InfoLabel text="Pods Value" content="Max number of pods to remove per scaling iteration" />}
                          value={budaiscalerSpecification.behavior.scaleDown.policies[1]?.value ?? 4}
                        >
                          <InputNumber
                            value={budaiscalerSpecification.behavior.scaleDown.policies[1]?.value ?? 4}
                            onChange={(value) => {
                              const policies = [...budaiscalerSpecification.behavior.scaleDown.policies];
                              policies[1] = { ...policies[1], type: "Pods", value: value || 4 };
                              updateSpec({
                                behavior: {
                                  ...budaiscalerSpecification.behavior,
                                  scaleDown: { ...budaiscalerSpecification.behavior.scaleDown, policies },
                                },
                              });
                            }}
                            min={1}
                            style={{ ...inputStyle, width: "100%" }}
                            className={inputClassName}
                          />
                        </FloatLabel>
                      </div>
                      <div className="floating-textarea">
                        <FloatLabel
                          label={<InfoLabel text="Pods Period (sec)" content="Time interval between pod-based scaling iterations" />}
                          value={budaiscalerSpecification.behavior.scaleDown.policies[1]?.periodSeconds ?? 15}
                        >
                          <InputNumber
                            value={budaiscalerSpecification.behavior.scaleDown.policies[1]?.periodSeconds ?? 15}
                            onChange={(value) => {
                              const policies = [...budaiscalerSpecification.behavior.scaleDown.policies];
                              policies[1] = { ...policies[1], type: "Pods", periodSeconds: value || 15 };
                              updateSpec({
                                behavior: {
                                  ...budaiscalerSpecification.behavior,
                                  scaleDown: { ...budaiscalerSpecification.behavior.scaleDown, policies },
                                },
                              });
                            }}
                            min={1}
                            style={{ ...inputStyle, width: "100%" }}
                            className={inputClassName}
                          />
                        </FloatLabel>
                      </div>
                    </div>
                  </div>
                </ConfigProvider>
              </DrawerCard>
            </>
          )}
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

"use client";
import { Box, Flex } from "@radix-ui/themes";
import { useState } from "react";
import React from "react";
import { useRouter } from "next/router";
import DashBoardLayout from "../layout";
import {
  Text_12_400_6A6E76,
  Text_17_600_FFFFFF,
} from "@/components/ui/text";
import { useLoader } from "src/context/appContext";
import {
  ArrowLeftOutlined,
  PlusOutlined,
  DeleteOutlined,
  SaveOutlined,
} from "@ant-design/icons";
import { useBudPipeline, DAGDefinition, PipelineStep, PipelineParameter } from "src/stores/useBudPipeline";
import {
  Button,
  Form,
  Input,
  Select,
  Card,
  Space,
  Divider,
  Alert,
  Tabs,
  Tag,
  Tooltip,
} from "antd";
import { successToast, errorToast } from "@/components/toast";

const { TextArea } = Input;
const { Option } = Select;

// Action types available
const actionTypes = [
  { value: "log", label: "Log", icon: "📝", description: "Log a message" },
  { value: "delay", label: "Delay", icon: "⏱️", description: "Wait for specified seconds" },
  { value: "transform", label: "Transform", icon: "🔄", description: "Transform data" },
  { value: "http_request", label: "HTTP Request", icon: "🌐", description: "Make HTTP request" },
  { value: "aggregate", label: "Aggregate", icon: "📊", description: "Aggregate multiple inputs" },
  { value: "set_output", label: "Set Output", icon: "📤", description: "Set workflow outputs" },
  { value: "conditional", label: "Conditional", icon: "🔀", description: "Conditional logic" },
];

// Parameter types
const parameterTypes = [
  { value: "string", label: "String" },
  { value: "integer", label: "Integer" },
  { value: "boolean", label: "Boolean" },
  { value: "object", label: "Object" },
  { value: "array", label: "Array" },
];

const NewPipeline = () => {
  const router = useRouter();
  const { showLoader, hideLoader } = useLoader();
  const { createWorkflow } = useBudPipeline();
  const [form] = Form.useForm();

  const [activeTab, setActiveTab] = useState("visual");
  const [jsonInput, setJsonInput] = useState("");
  const [jsonError, setJsonError] = useState<string | null>(null);

  // Form state
  const [parameters, setParameters] = useState<PipelineParameter[]>([]);
  const [steps, setSteps] = useState<Partial<PipelineStep>[]>([]);

  // Add parameter
  const addParameter = () => {
    setParameters([
      ...parameters,
      { name: "", type: "string", description: "", required: false },
    ]);
  };

  // Remove parameter
  const removeParameter = (index: number) => {
    setParameters(parameters.filter((_, i) => i !== index));
  };

  // Update parameter
  const updateParameter = (index: number, field: string, value: any) => {
    const updated = [...parameters];
    updated[index] = { ...updated[index], [field]: value };
    setParameters(updated);
  };

  // Add step
  const addStep = () => {
    setSteps([
      ...steps,
      {
        id: `step_${steps.length + 1}`,
        name: "",
        action: "log",
        params: {},
        depends_on: [],
      },
    ]);
  };

  // Remove step
  const removeStep = (index: number) => {
    setSteps(steps.filter((_, i) => i !== index));
  };

  // Update step
  const updateStep = (index: number, field: string, value: any) => {
    const updated = [...steps];
    updated[index] = { ...updated[index], [field]: value };
    setSteps(updated);
  };

  // Get available dependencies (steps before current)
  const getAvailableDeps = (currentIndex: number) => {
    return steps.slice(0, currentIndex).map((s) => s.id || "");
  };

  // Handle form submit
  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();

      // Validate parameters
      const validParams = parameters.filter((p) => p.name.trim() !== "");

      // Validate steps
      const validSteps = steps.filter(
        (s) => s.id && s.name && s.action
      ) as PipelineStep[];

      if (validSteps.length === 0) {
        errorToast("At least one step is required");
        return;
      }

      const dag: DAGDefinition = {
        name: values.name,
        version: values.version || "1.0.0",
        description: values.description,
        parameters: validParams,
        steps: validSteps,
        outputs: {},
      };

      showLoader();
      const result = await createWorkflow(dag);
      hideLoader();

      if (result) {
        successToast("Pipeline created successfully");
        router.push(`/pipelines/${result.id}`);
      } else {
        // Get error from store - createWorkflow returns null on failure
        const storeError = useBudPipeline.getState().error;
        errorToast(storeError || "Failed to create pipeline");
      }
    } catch (err) {
      console.error("Validation failed:", err);
      errorToast("Failed to create pipeline");
    }
  };

  // Handle JSON import
  const handleJsonImport = () => {
    try {
      const parsed = JSON.parse(jsonInput);
      setJsonError(null);

      // Validate structure
      if (!parsed.name || !parsed.steps) {
        setJsonError("Invalid DAG structure: name and steps are required");
        return;
      }

      // Populate form
      form.setFieldsValue({
        name: parsed.name,
        version: parsed.version || "1.0.0",
        description: parsed.description,
      });

      setParameters(parsed.parameters || []);
      setSteps(parsed.steps || []);

      successToast("DAG imported successfully");
      setActiveTab("visual");
    } catch (e) {
      setJsonError("Invalid JSON format");
    }
  };

  // Generate JSON from form
  const generateJson = () => {
    const values = form.getFieldsValue();
    const dag: DAGDefinition = {
      name: values.name || "Untitled Pipeline",
      version: values.version || "1.0.0",
      description: values.description,
      parameters: parameters.filter((p) => p.name.trim() !== ""),
      steps: steps.filter((s) => s.id && s.name && s.action) as PipelineStep[],
      outputs: {},
    };
    setJsonInput(JSON.stringify(dag, null, 2));
    setActiveTab("json");
  };

  return (
    <DashBoardLayout>
      <Box className="boardPageView">
        {/* Header */}
        <Flex
          justify="between"
          align="center"
          className="px-6 py-4 border-b border-[#1F1F1F] bg-[#0D0D0D]"
        >
          <Flex align="center" gap="4">
            <Button
              type="text"
              icon={<ArrowLeftOutlined />}
              onClick={() => router.push("/pipelines")}
              className="text-gray-400 hover:text-white"
            />
            <Box>
              <Text_17_600_FFFFFF>Create New Pipeline</Text_17_600_FFFFFF>
              <Text_12_400_6A6E76>
                Define a DAG pipeline with steps and dependencies
              </Text_12_400_6A6E76>
            </Box>
          </Flex>
          <Flex gap="2">
            <Button onClick={generateJson}>Export JSON</Button>
            <Button type="primary" icon={<SaveOutlined />} onClick={handleSubmit}>
              Create Pipeline
            </Button>
          </Flex>
        </Flex>

        {/* Content */}
        <Box className="p-6">
          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            items={[
              {
                key: "visual",
                label: "Visual Editor",
                children: (
                  <Box className="mt-4">
                    <Form form={form} layout="vertical" className="space-y-6">
                      {/* Basic Info */}
                      <Card
                        title="Pipeline Information"
                        className="bg-[#1A1A1A] border-[#2F3035]"
                        styles={{
                          header: { borderBottom: "1px solid #2F3035", color: "#fff" },
                          body: { backgroundColor: "#1A1A1A" },
                        }}
                      >
                        <Flex gap="4">
                          <Form.Item
                            name="name"
                            label={<span className="text-gray-300">Name</span>}
                            rules={[{ required: true, message: "Name is required" }]}
                            className="flex-1"
                          >
                            <Input placeholder="My Pipeline" />
                          </Form.Item>
                          <Form.Item
                            name="version"
                            label={<span className="text-gray-300">Version</span>}
                            initialValue="1.0.0"
                            className="w-32"
                          >
                            <Input placeholder="1.0.0" />
                          </Form.Item>
                        </Flex>
                        <Form.Item
                          name="description"
                          label={<span className="text-gray-300">Description</span>}
                        >
                          <TextArea rows={2} placeholder="Describe what this pipeline does..." />
                        </Form.Item>
                      </Card>

                      {/* Parameters */}
                      <Card
                        title={
                          <Flex justify="between" align="center">
                            <span>Parameters</span>
                            <Button
                              size="small"
                              icon={<PlusOutlined />}
                              onClick={addParameter}
                            >
                              Add Parameter
                            </Button>
                          </Flex>
                        }
                        className="bg-[#1A1A1A] border-[#2F3035]"
                        styles={{
                          header: { borderBottom: "1px solid #2F3035", color: "#fff" },
                          body: { backgroundColor: "#1A1A1A" },
                        }}
                      >
                        {parameters.length === 0 ? (
                          <div className="text-gray-500 text-center py-4">
                            No parameters defined. Parameters allow dynamic inputs when executing the pipeline.
                          </div>
                        ) : (
                          <Space direction="vertical" className="w-full">
                            {parameters.map((param, index) => (
                              <Flex key={index} gap="2" align="start" className="w-full">
                                <Input
                                  placeholder="Parameter name"
                                  value={param.name}
                                  onChange={(e) => updateParameter(index, "name", e.target.value)}
                                  className="flex-1"
                                />
                                <Select
                                  value={param.type}
                                  onChange={(v) => updateParameter(index, "type", v)}
                                  style={{ width: 120 }}
                                >
                                  {parameterTypes.map((t) => (
                                    <Option key={t.value} value={t.value}>
                                      {t.label}
                                    </Option>
                                  ))}
                                </Select>
                                <Input
                                  placeholder="Default value"
                                  value={param.default}
                                  onChange={(e) => updateParameter(index, "default", e.target.value)}
                                  style={{ width: 150 }}
                                />
                                <Button
                                  icon={<DeleteOutlined />}
                                  danger
                                  onClick={() => removeParameter(index)}
                                />
                              </Flex>
                            ))}
                          </Space>
                        )}
                      </Card>

                      {/* Steps */}
                      <Card
                        title={
                          <Flex justify="between" align="center">
                            <span>Steps</span>
                            <Button size="small" icon={<PlusOutlined />} onClick={addStep}>
                              Add Step
                            </Button>
                          </Flex>
                        }
                        className="bg-[#1A1A1A] border-[#2F3035]"
                        styles={{
                          header: { borderBottom: "1px solid #2F3035", color: "#fff" },
                          body: { backgroundColor: "#1A1A1A" },
                        }}
                      >
                        {steps.length === 0 ? (
                          <div className="text-gray-500 text-center py-8">
                            No steps defined. Add steps to build your pipeline.
                          </div>
                        ) : (
                          <Space direction="vertical" className="w-full" size="middle">
                            {steps.map((step, index) => (
                              <Card
                                key={index}
                                size="small"
                                className="bg-[#0D0D0D] border-[#2F3035]"
                                title={
                                  <Flex justify="between" align="center">
                                    <Flex align="center" gap="2">
                                      <Tag className="bg-blue-500/20 text-blue-400 border-0">
                                        Step {index + 1}
                                      </Tag>
                                      <span className="text-white text-sm">
                                        {step.name || "Unnamed Step"}
                                      </span>
                                    </Flex>
                                    <Button
                                      size="small"
                                      icon={<DeleteOutlined />}
                                      danger
                                      onClick={() => removeStep(index)}
                                    />
                                  </Flex>
                                }
                                styles={{
                                  header: { borderBottom: "1px solid #2F3035" },
                                  body: { backgroundColor: "#0D0D0D" },
                                }}
                              >
                                <Space direction="vertical" className="w-full">
                                  <Flex gap="2">
                                    <Input
                                      placeholder="Step ID"
                                      value={step.id}
                                      onChange={(e) => updateStep(index, "id", e.target.value)}
                                      style={{ width: 150 }}
                                    />
                                    <Input
                                      placeholder="Step Name"
                                      value={step.name}
                                      onChange={(e) => updateStep(index, "name", e.target.value)}
                                      className="flex-1"
                                    />
                                    <Select
                                      value={step.action}
                                      onChange={(v) => updateStep(index, "action", v)}
                                      style={{ width: 180 }}
                                    >
                                      {actionTypes.map((a) => (
                                        <Option key={a.value} value={a.value}>
                                          <Flex align="center" gap="2">
                                            <span>{a.icon}</span>
                                            <span>{a.label}</span>
                                          </Flex>
                                        </Option>
                                      ))}
                                    </Select>
                                  </Flex>
                                  <Flex gap="2">
                                    <Select
                                      mode="multiple"
                                      placeholder="Dependencies (steps that must complete first)"
                                      value={step.depends_on}
                                      onChange={(v) => updateStep(index, "depends_on", v)}
                                      className="flex-1"
                                      allowClear
                                    >
                                      {getAvailableDeps(index).map((depId) => (
                                        <Option key={depId} value={depId}>
                                          {depId}
                                        </Option>
                                      ))}
                                    </Select>
                                    <Input
                                      placeholder="Condition (optional)"
                                      value={step.condition}
                                      onChange={(e) => updateStep(index, "condition", e.target.value)}
                                      style={{ width: 250 }}
                                    />
                                  </Flex>
                                  <TextArea
                                    placeholder='Parameters (JSON): {"key": "value"}'
                                    value={
                                      typeof step.params === "object"
                                        ? JSON.stringify(step.params, null, 2)
                                        : ""
                                    }
                                    onChange={(e) => {
                                      try {
                                        const parsed = JSON.parse(e.target.value);
                                        updateStep(index, "params", parsed);
                                      } catch {
                                        // Keep as string if not valid JSON
                                      }
                                    }}
                                    rows={3}
                                    className="font-mono text-xs"
                                  />
                                </Space>
                              </Card>
                            ))}
                          </Space>
                        )}
                      </Card>
                    </Form>
                  </Box>
                ),
              },
              {
                key: "json",
                label: "JSON Editor",
                children: (
                  <Box className="mt-4">
                    <Alert
                      message="Import or edit DAG definition as JSON"
                      description="Paste a valid DAG JSON definition below and click Import to populate the visual editor."
                      type="info"
                      className="mb-4"
                    />
                    {jsonError && (
                      <Alert message={jsonError} type="error" className="mb-4" />
                    )}
                    <TextArea
                      value={jsonInput}
                      onChange={(e) => setJsonInput(e.target.value)}
                      rows={20}
                      className="font-mono text-sm bg-[#0D0D0D] border-[#2F3035]"
                      placeholder={`{
  "name": "My Pipeline",
  "version": "1.0.0",
  "description": "Pipeline description",
  "parameters": [],
  "steps": [
    {
      "id": "step1",
      "name": "First Step",
      "action": "log",
      "params": {"message": "Hello"},
      "depends_on": []
    }
  ]
}`}
                    />
                    <Flex justify="end" className="mt-4">
                      <Button type="primary" onClick={handleJsonImport}>
                        Import JSON
                      </Button>
                    </Flex>
                  </Box>
                ),
              },
            ]}
          />
        </Box>
      </Box>
    </DashBoardLayout>
  );
};

export default NewPipeline;

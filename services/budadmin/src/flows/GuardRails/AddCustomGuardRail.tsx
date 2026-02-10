import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import {
  Input,
  Button,
  Select,
  ConfigProvider,
  Switch,
  Collapse,
} from "antd";
import {
  PlusOutlined,
  DeleteOutlined,
  MinusCircleOutlined,
} from "@ant-design/icons";
import React, { useState, useCallback } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { errorToast, successToast } from "@/components/toast";
import useGuardrails from "src/hooks/useGuardrails";
import {
  Text_12_400_757575,
  Text_12_400_B3B3B3,
  Text_14_400_EEEEEE,
  Text_14_600_EEEEEE,
} from "@/components/ui/text";

const { TextArea } = Input;
const { Panel } = Collapse;

// Types based on the JSON schema
interface Definition {
  id: string;
  term: string;
  definition: string;
}

interface SafeContentItem {
  id: string;
  name: string;
  description: string;
  example: string;
}

interface Example {
  id: string;
  input: string;
  expectedOutput: string;
  rationale: string;
}

interface ViolationItem {
  id: string;
  name: string;
  description: string;
  example: string;
}

interface Violation {
  id: string;
  category: string;
  severity: "Moderate" | "Medium" | "High" | "Critical" | "Maximum";
  description: string;
  escalate: boolean;
  items: ViolationItem[];
  examples: Example[];
}

interface AmbiguityRule {
  id: string;
  condition: string;
  action: string;
}

interface CustomGuardRailFormData {
  task: string;
  definitions: Definition[];
  interpretation: string[];
  evaluation: {
    depiction: string;
    request: string;
    guidance: string;
  };
  safe_content: {
    category: string;
    description: string;
    items: SafeContentItem[];
    examples: Example[];
  };
  violations: Violation[];
  ambiguity: AmbiguityRule[];
}

const generateId = () => `${Date.now()}-${Math.random().toString(36).substring(2, 11)}`;

const SEVERITY_OPTIONS = [
  { label: "Moderate", value: "Moderate" },
  { label: "Medium", value: "Medium" },
  { label: "High", value: "High" },
  { label: "Critical", value: "Critical" },
  { label: "Maximum", value: "Maximum" },
];

const DEFAULT_INTERPRETATION = [
  "Apply these criteria exactly as written",
  "Do not assess content based on implications except where specifically instructed",
];

const DEFAULT_EVALUATION = {
  depiction: "Does the content CONTAIN policy violations?",
  request: "Is the user ASKING to generate violating content?",
  guidance: "Return the HIGHEST severity that applies. Include both aspects in your rationale.",
};

const DEFAULT_AMBIGUITY = [
  { id: generateId(), condition: "unclear", action: "downgrade severity by 1 level" },
];

// Reusable input styles
const inputClassName = "bg-transparent text-[#EEEEEE] border-[#757575] hover:border-[#EEEEEE] focus:border-[#EEEEEE]";
const inputStyle = { backgroundColor: "transparent", color: "#EEEEEE" };

export default function AddCustomGuardRail() {
  const { openDrawerWithStep } = useDrawer();
  const { updateCustomProbeWorkflow, setCustomProbePolicy, workflowLoading } = useGuardrails();

  // Form state
  const [formData, setFormData] = useState<CustomGuardRailFormData>({
    task: "",
    definitions: [{ id: generateId(), term: "", definition: "" }],
    interpretation: [...DEFAULT_INTERPRETATION],
    evaluation: { ...DEFAULT_EVALUATION },
    safe_content: {
      category: "safe",
      description: "",
      items: [{ id: generateId(), name: "", description: "", example: "" }],
      examples: [],
    },
    violations: [],
    ambiguity: [...DEFAULT_AMBIGUITY],
  });

  const [errors, setErrors] = useState<Record<string, string>>({});

  const handleBack = () => {
    openDrawerWithStep("select-probe-type");
  };

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    // Validate task
    if (!formData.task.trim()) {
      newErrors.task = "Task description is required";
    }

    // Validate definitions (minItems: 1)
    if (formData.definitions.length === 0) {
      newErrors.definitions = "At least one definition is required";
    } else {
      formData.definitions.forEach((def, index) => {
        if (!def.term.trim()) {
          newErrors[`definitions.${index}.term`] = "Term is required";
        }
        if (!def.definition.trim()) {
          newErrors[`definitions.${index}.definition`] = "Definition is required";
        }
      });
    }

    // Validate safe_content
    if (!formData.safe_content.description.trim()) {
      newErrors["safe_content.description"] = "Safe content description is required";
    }
    if (formData.safe_content.items.length === 0) {
      newErrors["safe_content.items"] = "At least one safe content item is required";
    } else {
      formData.safe_content.items.forEach((item, index) => {
        if (!item.name.trim()) {
          newErrors[`safe_content.items.${index}.name`] = "Name is required";
        }
        if (!item.description.trim()) {
          newErrors[`safe_content.items.${index}.description`] = "Description is required";
        }
        if (!item.example.trim()) {
          newErrors[`safe_content.items.${index}.example`] = "Example is required";
        }
      });
    }

    // Validate safe_content examples (minItems: 5)
    if (formData.safe_content.examples.length < 5) {
      newErrors["safe_content.examples"] = "At least 5 examples are required for safe content";
    }

    // Validate violations
    formData.violations.forEach((violation, vIndex) => {
      if (!violation.category.trim()) {
        newErrors[`violations.${vIndex}.category`] = "Category is required";
      }
      if (!violation.description.trim()) {
        newErrors[`violations.${vIndex}.description`] = "Description is required";
      }
      if (violation.items.length === 0) {
        newErrors[`violations.${vIndex}.items`] = "At least one item is required";
      }
      if (violation.examples.length < 3) {
        newErrors[`violations.${vIndex}.examples`] = "At least 3 examples are required";
      }
    });

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSave = async () => {
    if (!validateForm()) {
      errorToast("Please fill in all required fields");
      return;
    }

    // Build the output JSON according to the schema
    const outputJson = {
      task: formData.task,
      definitions: formData.definitions.map(({ term, definition }) => ({
        term,
        definition,
      })),
      interpretation: formData.interpretation,
      evaluation: formData.evaluation,
      safe_content: {
        category: "safe",
        description: formData.safe_content.description,
        items: formData.safe_content.items.map(({ name, description, example }) => ({
          name,
          description,
          example,
        })),
        examples: formData.safe_content.examples.map(({ input, expectedOutput, rationale }) => ({
          input,
          expected_output: expectedOutput,
          rationale,
        })),
      },
      violations: formData.violations.map((v) => ({
        category: v.category,
        severity: v.severity,
        description: v.description,
        escalate: v.escalate,
        items: v.items.map(({ name, description, example }) => ({
          name,
          description,
          example,
        })),
        examples: v.examples.map(({ input, expectedOutput, rationale }) => ({
          input,
          expected_output: expectedOutput,
          rationale,
        })),
      })),
      ambiguity: formData.ambiguity.map(({ condition, action }) => ({
        condition,
        action,
      })),
    };

    setCustomProbePolicy(outputJson);

    const success = await updateCustomProbeWorkflow({
      step_number: 2,
      trigger_workflow: false,
      probe_type_option: "llm_policy",
      policy: outputJson,
    });

    if (!success) return;

    successToast("Custom guardrail configuration saved");
    openDrawerWithStep("guardrail-details");
  };

  // Helper functions to update form data
  const updateField = useCallback(<K extends keyof CustomGuardRailFormData>(
    field: K,
    value: CustomGuardRailFormData[K]
  ) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  }, []);

  // Definitions handlers
  const addDefinition = () => {
    setFormData((prev) => ({
      ...prev,
      definitions: [...prev.definitions, { id: generateId(), term: "", definition: "" }],
    }));
  };

  const removeDefinition = (id: string) => {
    if (formData.definitions.length > 1) {
      setFormData((prev) => ({
        ...prev,
        definitions: prev.definitions.filter((d) => d.id !== id),
      }));
    }
  };

  const updateDefinition = (id: string, field: keyof Definition, value: string) => {
    setFormData((prev) => ({
      ...prev,
      definitions: prev.definitions.map((d) =>
        d.id === id ? { ...d, [field]: value } : d
      ),
    }));
  };

  // Interpretation handlers
  const addInterpretation = () => {
    setFormData((prev) => ({
      ...prev,
      interpretation: [...prev.interpretation, ""],
    }));
  };

  const removeInterpretation = (index: number) => {
    setFormData((prev) => ({
      ...prev,
      interpretation: prev.interpretation.filter((_, i) => i !== index),
    }));
  };

  const updateInterpretation = (index: number, value: string) => {
    setFormData((prev) => ({
      ...prev,
      interpretation: prev.interpretation.map((item, i) => (i === index ? value : item)),
    }));
  };

  // Safe content item handlers
  const addSafeContentItem = () => {
    setFormData((prev) => ({
      ...prev,
      safe_content: {
        ...prev.safe_content,
        items: [...prev.safe_content.items, { id: generateId(), name: "", description: "", example: "" }],
      },
    }));
  };

  const removeSafeContentItem = (id: string) => {
    if (formData.safe_content.items.length > 1) {
      setFormData((prev) => ({
        ...prev,
        safe_content: {
          ...prev.safe_content,
          items: prev.safe_content.items.filter((i) => i.id !== id),
        },
      }));
    }
  };

  const updateSafeContentItem = (id: string, field: keyof SafeContentItem, value: string) => {
    setFormData((prev) => ({
      ...prev,
      safe_content: {
        ...prev.safe_content,
        items: prev.safe_content.items.map((i) =>
          i.id === id ? { ...i, [field]: value } : i
        ),
      },
    }));
  };

  // Safe content examples handlers
  const addSafeContentExample = () => {
    setFormData((prev) => ({
      ...prev,
      safe_content: {
        ...prev.safe_content,
        examples: [...prev.safe_content.examples, { id: generateId(), input: "", expectedOutput: "", rationale: "" }],
      },
    }));
  };

  const removeSafeContentExample = (id: string) => {
    setFormData((prev) => ({
      ...prev,
      safe_content: {
        ...prev.safe_content,
        examples: prev.safe_content.examples.filter((e) => e.id !== id),
      },
    }));
  };

  const updateSafeContentExample = (id: string, field: keyof Example, value: string) => {
    setFormData((prev) => ({
      ...prev,
      safe_content: {
        ...prev.safe_content,
        examples: prev.safe_content.examples.map((e) =>
          e.id === id ? { ...e, [field]: value } : e
        ),
      },
    }));
  };

  // Violation handlers
  const addViolation = () => {
    setFormData((prev) => ({
      ...prev,
      violations: [
        ...prev.violations,
        {
          id: generateId(),
          category: "",
          severity: "Moderate",
          description: "",
          escalate: false,
          items: [{ id: generateId(), name: "", description: "", example: "" }],
          examples: [],
        },
      ],
    }));
  };

  const removeViolation = (id: string) => {
    setFormData((prev) => ({
      ...prev,
      violations: prev.violations.filter((v) => v.id !== id),
    }));
  };

  const updateViolation = (id: string, field: keyof Violation, value: any) => {
    setFormData((prev) => ({
      ...prev,
      violations: prev.violations.map((v) =>
        v.id === id ? { ...v, [field]: value } : v
      ),
    }));
  };

  // Violation item handlers
  const addViolationItem = (violationId: string) => {
    setFormData((prev) => ({
      ...prev,
      violations: prev.violations.map((v) =>
        v.id === violationId
          ? { ...v, items: [...v.items, { id: generateId(), name: "", description: "", example: "" }] }
          : v
      ),
    }));
  };

  const removeViolationItem = (violationId: string, itemId: string) => {
    setFormData((prev) => ({
      ...prev,
      violations: prev.violations.map((v) =>
        v.id === violationId && v.items.length > 1
          ? { ...v, items: v.items.filter((i) => i.id !== itemId) }
          : v
      ),
    }));
  };

  const updateViolationItem = (
    violationId: string,
    itemId: string,
    field: keyof ViolationItem,
    value: string
  ) => {
    setFormData((prev) => ({
      ...prev,
      violations: prev.violations.map((v) =>
        v.id === violationId
          ? {
              ...v,
              items: v.items.map((i) => (i.id === itemId ? { ...i, [field]: value } : i)),
            }
          : v
      ),
    }));
  };

  // Violation example handlers
  const addViolationExample = (violationId: string) => {
    setFormData((prev) => ({
      ...prev,
      violations: prev.violations.map((v) =>
        v.id === violationId
          ? { ...v, examples: [...v.examples, { id: generateId(), input: "", expectedOutput: "", rationale: "" }] }
          : v
      ),
    }));
  };

  const removeViolationExample = (violationId: string, exampleId: string) => {
    setFormData((prev) => ({
      ...prev,
      violations: prev.violations.map((v) =>
        v.id === violationId
          ? { ...v, examples: v.examples.filter((e) => e.id !== exampleId) }
          : v
      ),
    }));
  };

  const updateViolationExample = (
    violationId: string,
    exampleId: string,
    field: keyof Example,
    value: string
  ) => {
    setFormData((prev) => ({
      ...prev,
      violations: prev.violations.map((v) =>
        v.id === violationId
          ? {
              ...v,
              examples: v.examples.map((e) => (e.id === exampleId ? { ...e, [field]: value } : e)),
            }
          : v
      ),
    }));
  };

  // Ambiguity handlers
  const addAmbiguity = () => {
    setFormData((prev) => ({
      ...prev,
      ambiguity: [...prev.ambiguity, { id: generateId(), condition: "", action: "" }],
    }));
  };

  const removeAmbiguity = (id: string) => {
    setFormData((prev) => ({
      ...prev,
      ambiguity: prev.ambiguity.filter((a) => a.id !== id),
    }));
  };

  const updateAmbiguity = (id: string, field: keyof AmbiguityRule, value: string) => {
    setFormData((prev) => ({
      ...prev,
      ambiguity: prev.ambiguity.map((a) => (a.id === id ? { ...a, [field]: value } : a)),
    }));
  };

  const hasError = (path: string) => !!errors[path];

  return (
    <BudForm
      data={{}}
      disableNext={workflowLoading}
      onBack={handleBack}
      onNext={handleSave}
      backText="Back"
      nextText={workflowLoading ? "Saving..." : "Save"}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Add Custom GuardRail"
            description="Define a custom guardrail policy with task descriptions, definitions, and violation categories"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem]"
          />

          <div className="px-[1.35rem] pb-[1.35rem] space-y-[1.5rem] pt-[1.5rem]">
            {/* Task Section */}
            <div>
              <Text_14_600_EEEEEE className="mb-[0.75rem]">
                Task Description *
              </Text_14_600_EEEEEE>
              <Text_12_400_757575 className="mb-[0.5rem] block">
                Brief description of what to classify and identify
              </Text_12_400_757575>
              <TextArea
                value={formData.task}
                onChange={(e) => updateField("task", e.target.value)}
                placeholder="e.g., Classify content for policy violations related to harmful speech"
                rows={2}
                className={`${inputClassName} ${hasError("task") ? "!border-[#ec7575]" : ""}`}
                style={inputStyle}
              />
              {hasError("task") && (
                <Text_12_400_757575 className="text-[#ec7575] mt-[0.25rem]">
                  {errors.task}
                </Text_12_400_757575>
              )}
            </div>

            {/* Definitions Section */}
            <div className="bg-[#ffffff07] border border-[#757575] rounded-[8px] p-[1rem]">
              <div className="flex justify-between items-center mb-[1rem]">
                <div>
                  <Text_14_600_EEEEEE>Definitions *</Text_14_600_EEEEEE>
                  <Text_12_400_757575 className="mt-[0.25rem]">
                    Define key concepts precisely (at least 1 required)
                  </Text_12_400_757575>
                </div>
                <Button
                  icon={<PlusOutlined />}
                  onClick={addDefinition}
                  className="!bg-transparent text-[#965CDE] !border-[#965CDE] hover:!bg-[#965CDE10]"
                  size="small"
                >
                  Add
                </Button>
              </div>

              <div className="space-y-[1rem]">
                {formData.definitions.map((def, index) => (
                  <div key={def.id} className="p-[0.75rem] bg-[#FFFFFF05] rounded-[6px] border border-[#1F1F1F]">
                    <div className="flex justify-between items-start mb-[0.5rem]">
                      <Text_12_400_B3B3B3>Definition {index + 1}</Text_12_400_B3B3B3>
                      {formData.definitions.length > 1 && (
                        <MinusCircleOutlined
                          onClick={() => removeDefinition(def.id)}
                          className="text-[#B3B3B3] cursor-pointer hover:text-[#ec7575]"
                        />
                      )}
                    </div>
                    <div className="space-y-[0.5rem]">
                      <Input
                        value={def.term}
                        onChange={(e) => updateDefinition(def.id, "term", e.target.value)}
                        placeholder="Term"
                        className={`${inputClassName} ${hasError(`definitions.${index}.term`) ? "!border-[#ec7575]" : ""}`}
                        style={inputStyle}
                      />
                      <TextArea
                        value={def.definition}
                        onChange={(e) => updateDefinition(def.id, "definition", e.target.value)}
                        placeholder="Full definition - preserve verbatim from source policy"
                        rows={2}
                        className={`${inputClassName} ${hasError(`definitions.${index}.definition`) ? "!border-[#ec7575]" : ""}`}
                        style={inputStyle}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Interpretation Section (Optional) */}
            <ConfigProvider
              theme={{
                token: {
                  colorBgContainer: "#101010",
                  colorBorder: "#757575",
                  colorText: "#EEEEEE",
                },
              }}
            >
              <Collapse
                ghost
                className="bg-[#ffffff07] border border-[#757575] rounded-[8px]"
              >
                <Panel
                  header={
                    <div>
                      <Text_14_600_EEEEEE>Interpretation Rules</Text_14_600_EEEEEE>
                      <Text_12_400_757575 className="mt-[0.25rem] block">
                        Optional - How to apply criteria
                      </Text_12_400_757575>
                    </div>
                  }
                  key="interpretation"
                >
                  <div className="space-y-[0.5rem]">
                    {formData.interpretation.map((item, index) => (
                      <div key={index} className="flex items-center gap-[0.5rem]">
                        <Input
                          value={item}
                          onChange={(e) => updateInterpretation(index, e.target.value)}
                          placeholder="Interpretation rule"
                          className={inputClassName}
                          style={inputStyle}
                        />
                        <MinusCircleOutlined
                          onClick={() => removeInterpretation(index)}
                          className="text-[#B3B3B3] cursor-pointer hover:text-[#ec7575]"
                        />
                      </div>
                    ))}
                    <Button
                      type="dashed"
                      onClick={addInterpretation}
                      block
                      icon={<PlusOutlined />}
                      className="border-[#757575] text-[#B3B3B3] hover:border-[#EEEEEE] hover:text-[#EEEEEE] bg-transparent"
                    >
                      Add Interpretation Rule
                    </Button>
                  </div>
                </Panel>
              </Collapse>
            </ConfigProvider>

            {/* Evaluation Section (Optional) */}
            <ConfigProvider
              theme={{
                token: {
                  colorBgContainer: "#101010",
                  colorBorder: "#757575",
                  colorText: "#EEEEEE",
                },
              }}
            >
              <Collapse
                ghost
                className="bg-[#ffffff07] border border-[#757575] rounded-[8px]"
              >
                <Panel
                  header={
                    <div>
                      <Text_14_600_EEEEEE>Evaluation Approach</Text_14_600_EEEEEE>
                      <Text_12_400_757575 className="mt-[0.25rem] block">
                        Optional - Dual evaluation approach
                      </Text_12_400_757575>
                    </div>
                  }
                  key="evaluation"
                >
                  <div className="space-y-[0.75rem]">
                    <div>
                      <Text_12_400_B3B3B3 className="mb-[0.25rem] block">Depiction</Text_12_400_B3B3B3>
                      <Input
                        value={formData.evaluation.depiction}
                        onChange={(e) =>
                          updateField("evaluation", { ...formData.evaluation, depiction: e.target.value })
                        }
                        placeholder="Does the content CONTAIN policy violations?"
                        className={inputClassName}
                        style={inputStyle}
                      />
                    </div>
                    <div>
                      <Text_12_400_B3B3B3 className="mb-[0.25rem] block">Request</Text_12_400_B3B3B3>
                      <Input
                        value={formData.evaluation.request}
                        onChange={(e) =>
                          updateField("evaluation", { ...formData.evaluation, request: e.target.value })
                        }
                        placeholder="Is the user ASKING to generate violating content?"
                        className={inputClassName}
                        style={inputStyle}
                      />
                    </div>
                    <div>
                      <Text_12_400_B3B3B3 className="mb-[0.25rem] block">Guidance</Text_12_400_B3B3B3>
                      <TextArea
                        value={formData.evaluation.guidance}
                        onChange={(e) =>
                          updateField("evaluation", { ...formData.evaluation, guidance: e.target.value })
                        }
                        placeholder="Return the HIGHEST severity that applies..."
                        rows={2}
                        className={inputClassName}
                        style={inputStyle}
                      />
                    </div>
                  </div>
                </Panel>
              </Collapse>
            </ConfigProvider>

            {/* Safe Content Section */}
            <div className="bg-[#ffffff07] border border-[#757575] rounded-[8px] p-[1rem]">
              <Text_14_600_EEEEEE className="mb-[0.5rem]">Safe Content *</Text_14_600_EEEEEE>
              <Text_12_400_757575 className="mb-[1rem] block">
                Define what constitutes safe/legitimate content
              </Text_12_400_757575>

              {/* Safe Content Description */}
              <div className="mb-[1rem]">
                <Text_12_400_B3B3B3 className="mb-[0.25rem] block">Description *</Text_12_400_B3B3B3>
                <TextArea
                  value={formData.safe_content.description}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      safe_content: { ...prev.safe_content, description: e.target.value },
                    }))
                  }
                  placeholder="Summary of what constitutes safe/legitimate content"
                  rows={2}
                  className={`${inputClassName} ${hasError("safe_content.description") ? "!border-[#ec7575]" : ""}`}
                  style={inputStyle}
                />
              </div>

              {/* Safe Content Items */}
              <div className="mb-[1rem]">
                <div className="flex justify-between items-center mb-[0.5rem]">
                  <Text_12_400_B3B3B3>Safe Content Types *</Text_12_400_B3B3B3>
                  <Button
                    icon={<PlusOutlined />}
                    onClick={addSafeContentItem}
                    className="!bg-transparent text-[#965CDE] !border-[#965CDE] hover:!bg-[#965CDE10]"
                    size="small"
                  >
                    Add
                  </Button>
                </div>
                <div className="space-y-[0.75rem]">
                  {formData.safe_content.items.map((item, index) => (
                    <div key={item.id} className="p-[0.75rem] bg-[#FFFFFF05] rounded-[6px] border border-[#1F1F1F]">
                      <div className="flex justify-between items-start mb-[0.5rem]">
                        <Text_12_400_757575>Item {index + 1}</Text_12_400_757575>
                        {formData.safe_content.items.length > 1 && (
                          <MinusCircleOutlined
                            onClick={() => removeSafeContentItem(item.id)}
                            className="text-[#B3B3B3] cursor-pointer hover:text-[#ec7575]"
                          />
                        )}
                      </div>
                      <div className="space-y-[0.5rem]">
                        <Input
                          value={item.name}
                          onChange={(e) => updateSafeContentItem(item.id, "name", e.target.value)}
                          placeholder="Name"
                          className={inputClassName}
                          style={inputStyle}
                        />
                        <Input
                          value={item.description}
                          onChange={(e) => updateSafeContentItem(item.id, "description", e.target.value)}
                          placeholder="Description"
                          className={inputClassName}
                          style={inputStyle}
                        />
                        <Input
                          value={item.example}
                          onChange={(e) => updateSafeContentItem(item.id, "example", e.target.value)}
                          placeholder="Example"
                          className={inputClassName}
                          style={inputStyle}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Safe Content Examples */}
              <div>
                <div className="flex justify-between items-center mb-[0.5rem]">
                  <div>
                    <Text_12_400_B3B3B3>Training Examples *</Text_12_400_B3B3B3>
                    <Text_12_400_757575 className="text-[10px]">
                      5-7 examples recommended (min 5)
                    </Text_12_400_757575>
                  </div>
                  <Button
                    icon={<PlusOutlined />}
                    onClick={addSafeContentExample}
                    className="!bg-transparent text-[#965CDE] !border-[#965CDE] hover:!bg-[#965CDE10]"
                    size="small"
                  >
                    Add
                  </Button>
                </div>
                {hasError("safe_content.examples") && (
                  <Text_12_400_757575 className="text-[#ec7575] mb-[0.5rem] block">
                    {errors["safe_content.examples"]}
                  </Text_12_400_757575>
                )}
                <div className="space-y-[0.75rem]">
                  {formData.safe_content.examples.map((example, index) => (
                    <div key={example.id} className="p-[0.75rem] bg-[#FFFFFF05] rounded-[6px] border border-[#1F1F1F]">
                      <div className="flex justify-between items-start mb-[0.5rem]">
                        <Text_12_400_757575>Example {index + 1}</Text_12_400_757575>
                        <MinusCircleOutlined
                          onClick={() => removeSafeContentExample(example.id)}
                          className="text-[#B3B3B3] cursor-pointer hover:text-[#ec7575]"
                        />
                      </div>
                      <div className="space-y-[0.5rem]">
                        <TextArea
                          value={example.input}
                          onChange={(e) => updateSafeContentExample(example.id, "input", e.target.value)}
                          placeholder="Input text"
                          rows={2}
                          className={inputClassName}
                          style={inputStyle}
                        />
                        <Input
                          value={example.expectedOutput}
                          onChange={(e) => updateSafeContentExample(example.id, "expectedOutput", e.target.value)}
                          placeholder="Expected output"
                          className={inputClassName}
                          style={inputStyle}
                        />
                        <Input
                          value={example.rationale}
                          onChange={(e) => updateSafeContentExample(example.id, "rationale", e.target.value)}
                          placeholder="Rationale"
                          className={inputClassName}
                          style={inputStyle}
                        />
                      </div>
                    </div>
                  ))}
                  {formData.safe_content.examples.length === 0 && (
                    <div className="text-center py-[1rem] text-[#757575] text-[12px]">
                      Click "Add" to add training examples
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Violations Section */}
            <div className="bg-[#ffffff07] border border-[#757575] rounded-[8px] p-[1rem]">
              <div className="flex justify-between items-center mb-[1rem]">
                <div>
                  <Text_14_600_EEEEEE>Violations</Text_14_600_EEEEEE>
                  <Text_12_400_757575 className="mt-[0.25rem]">
                    Define violation categories in increasing severity
                  </Text_12_400_757575>
                </div>
                <Button
                  icon={<PlusOutlined />}
                  onClick={addViolation}
                  className="!bg-transparent text-[#965CDE] !border-[#965CDE] hover:!bg-[#965CDE10]"
                  size="small"
                >
                  Add Violation
                </Button>
              </div>

              <div className="space-y-[1rem]">
                {formData.violations.map((violation, vIndex) => (
                  <div key={violation.id} className="p-[1rem] bg-[#FFFFFF05] rounded-[8px] border border-[#1F1F1F]">
                    <div className="flex justify-between items-start mb-[1rem]">
                      <Text_14_400_EEEEEE>Violation Category {vIndex + 1}</Text_14_400_EEEEEE>
                      <Button
                        icon={<DeleteOutlined />}
                        onClick={() => removeViolation(violation.id)}
                        className="!bg-transparent hover:!bg-[#FF000010]"
                        style={{ color: "#ec7575", borderColor: "#ec7575" }}
                        size="small"
                        danger
                      />
                    </div>

                    <div className="space-y-[0.75rem]">
                      {/* Category Name */}
                      <div>
                        <Text_12_400_B3B3B3 className="mb-[0.25rem] block">
                          Category Name * (snake_case, e.g., hate_speech)
                        </Text_12_400_B3B3B3>
                        <Input
                          value={violation.category}
                          onChange={(e) => updateViolation(violation.id, "category", e.target.value)}
                          placeholder="hate_speech"
                          className={`${inputClassName} ${hasError(`violations.${vIndex}.category`) ? "!border-[#ec7575]" : ""}`}
                          style={inputStyle}
                        />
                      </div>

                      {/* Severity and Escalate */}
                      <div className="flex gap-[1rem]">
                        <div className="flex-1">
                          <Text_12_400_B3B3B3 className="mb-[0.25rem] block">Severity *</Text_12_400_B3B3B3>
                          <ConfigProvider
                            theme={{
                              token: {
                                colorTextPlaceholder: "#808080",
                                colorBgElevated: "#101010",
                                colorBorder: "#757575",
                              },
                            }}
                          >
                            <Select
                              value={violation.severity}
                              onChange={(value) => {
                                updateViolation(violation.id, "severity", value);
                                // Auto-set escalate for Critical severity
                                if (value === "Critical" || value === "Maximum") {
                                  updateViolation(violation.id, "escalate", true);
                                }
                              }}
                              options={SEVERITY_OPTIONS}
                              className="w-full"
                              style={{ backgroundColor: "transparent" }}
                            />
                          </ConfigProvider>
                        </div>
                        <div className="flex items-center gap-[0.5rem] pt-[1.5rem]">
                          <Switch
                            checked={violation.escalate}
                            onChange={(checked) => updateViolation(violation.id, "escalate", checked)}
                            size="small"
                          />
                          <Text_12_400_B3B3B3>Escalate</Text_12_400_B3B3B3>
                        </div>
                      </div>

                      {/* Description */}
                      <div>
                        <Text_12_400_B3B3B3 className="mb-[0.25rem] block">Description *</Text_12_400_B3B3B3>
                        <TextArea
                          value={violation.description}
                          onChange={(e) => updateViolation(violation.id, "description", e.target.value)}
                          placeholder="Description of this violation category"
                          rows={2}
                          className={`${inputClassName} ${hasError(`violations.${vIndex}.description`) ? "!border-[#ec7575]" : ""}`}
                          style={inputStyle}
                        />
                      </div>

                      {/* Violation Items */}
                      <div className="mt-[1rem]">
                        <div className="flex justify-between items-center mb-[0.5rem]">
                          <Text_12_400_B3B3B3>Violation Types *</Text_12_400_B3B3B3>
                          <Button
                            icon={<PlusOutlined />}
                            onClick={() => addViolationItem(violation.id)}
                            className="!bg-transparent text-[#965CDE] !border-[#965CDE] hover:!bg-[#965CDE10]"
                            size="small"
                          >
                            Add
                          </Button>
                        </div>
                        <div className="space-y-[0.5rem]">
                          {violation.items.map((item, iIndex) => (
                            <div key={item.id} className="p-[0.5rem] bg-[#FFFFFF03] rounded-[4px] border border-[#2A2A2A]">
                              <div className="flex justify-between items-start mb-[0.25rem]">
                                <Text_12_400_757575>Item {iIndex + 1}</Text_12_400_757575>
                                {violation.items.length > 1 && (
                                  <MinusCircleOutlined
                                    onClick={() => removeViolationItem(violation.id, item.id)}
                                    className="text-[#757575] cursor-pointer hover:text-[#ec7575] text-[12px]"
                                  />
                                )}
                              </div>
                              <div className="space-y-[0.25rem]">
                                <Input
                                  value={item.name}
                                  onChange={(e) => updateViolationItem(violation.id, item.id, "name", e.target.value)}
                                  placeholder="Name"
                                  size="small"
                                  className={inputClassName}
                                  style={inputStyle}
                                />
                                <Input
                                  value={item.description}
                                  onChange={(e) => updateViolationItem(violation.id, item.id, "description", e.target.value)}
                                  placeholder="Description"
                                  size="small"
                                  className={inputClassName}
                                  style={inputStyle}
                                />
                                <Input
                                  value={item.example}
                                  onChange={(e) => updateViolationItem(violation.id, item.id, "example", e.target.value)}
                                  placeholder="Example"
                                  size="small"
                                  className={inputClassName}
                                  style={inputStyle}
                                />
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Violation Examples */}
                      <div className="mt-[1rem]">
                        <div className="flex justify-between items-center mb-[0.5rem]">
                          <div>
                            <Text_12_400_B3B3B3>Training Examples *</Text_12_400_B3B3B3>
                            <Text_12_400_757575 className="text-[10px]">3-5 per category</Text_12_400_757575>
                          </div>
                          <Button
                            icon={<PlusOutlined />}
                            onClick={() => addViolationExample(violation.id)}
                            className="!bg-transparent text-[#965CDE] !border-[#965CDE] hover:!bg-[#965CDE10]"
                            size="small"
                          >
                            Add
                          </Button>
                        </div>
                        {hasError(`violations.${vIndex}.examples`) && (
                          <Text_12_400_757575 className="text-[#ec7575] mb-[0.25rem] block text-[10px]">
                            {errors[`violations.${vIndex}.examples`]}
                          </Text_12_400_757575>
                        )}
                        <div className="space-y-[0.5rem]">
                          {violation.examples.map((example, eIndex) => (
                            <div key={example.id} className="p-[0.5rem] bg-[#FFFFFF03] rounded-[4px] border border-[#2A2A2A]">
                              <div className="flex justify-between items-start mb-[0.25rem]">
                                <Text_12_400_757575>Example {eIndex + 1}</Text_12_400_757575>
                                <MinusCircleOutlined
                                  onClick={() => removeViolationExample(violation.id, example.id)}
                                  className="text-[#757575] cursor-pointer hover:text-[#ec7575] text-[12px]"
                                />
                              </div>
                              <div className="space-y-[0.25rem]">
                                <TextArea
                                  value={example.input}
                                  onChange={(e) => updateViolationExample(violation.id, example.id, "input", e.target.value)}
                                  placeholder="Input text"
                                  rows={2}
                                  size="small"
                                  className={inputClassName}
                                  style={inputStyle}
                                />
                                <Input
                                  value={example.expectedOutput}
                                  onChange={(e) => updateViolationExample(violation.id, example.id, "expectedOutput", e.target.value)}
                                  placeholder="Expected output"
                                  size="small"
                                  className={inputClassName}
                                  style={inputStyle}
                                />
                                <Input
                                  value={example.rationale}
                                  onChange={(e) => updateViolationExample(violation.id, example.id, "rationale", e.target.value)}
                                  placeholder="Rationale"
                                  size="small"
                                  className={inputClassName}
                                  style={inputStyle}
                                />
                              </div>
                            </div>
                          ))}
                          {violation.examples.length === 0 && (
                            <div className="text-center py-[0.5rem] text-[#757575] text-[10px]">
                              Click "Add" to add examples
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
                {formData.violations.length === 0 && (
                  <div className="text-center py-[2rem] text-[#757575] text-[12px]">
                    Click "Add Violation" to define violation categories
                  </div>
                )}
              </div>
            </div>

            {/* Ambiguity Section (Optional) */}
            <ConfigProvider
              theme={{
                token: {
                  colorBgContainer: "#101010",
                  colorBorder: "#757575",
                  colorText: "#EEEEEE",
                },
              }}
            >
              <Collapse
                ghost
                className="bg-[#ffffff07] border border-[#757575] rounded-[8px]"
              >
                <Panel
                  header={
                    <div>
                      <Text_14_600_EEEEEE>Ambiguity Handling</Text_14_600_EEEEEE>
                      <Text_12_400_757575 className="mt-[0.25rem] block">
                        Optional - How to handle ambiguous cases
                      </Text_12_400_757575>
                    </div>
                  }
                  key="ambiguity"
                >
                  <div className="space-y-[0.5rem]">
                    {formData.ambiguity.map((rule) => (
                      <div key={rule.id} className="flex items-start gap-[0.5rem]">
                        <div className="flex-1 space-y-[0.25rem]">
                          <Input
                            value={rule.condition}
                            onChange={(e) => updateAmbiguity(rule.id, "condition", e.target.value)}
                            placeholder="Condition (e.g., unclear)"
                            className={inputClassName}
                            style={inputStyle}
                          />
                          <Input
                            value={rule.action}
                            onChange={(e) => updateAmbiguity(rule.id, "action", e.target.value)}
                            placeholder="Action (e.g., downgrade severity by 1 level)"
                            className={inputClassName}
                            style={inputStyle}
                          />
                        </div>
                        <MinusCircleOutlined
                          onClick={() => removeAmbiguity(rule.id)}
                          className="text-[#B3B3B3] cursor-pointer hover:text-[#ec7575] mt-[0.5rem]"
                        />
                      </div>
                    ))}
                    <Button
                      type="dashed"
                      onClick={addAmbiguity}
                      block
                      icon={<PlusOutlined />}
                      className="border-[#757575] text-[#B3B3B3] hover:border-[#EEEEEE] hover:text-[#EEEEEE] bg-transparent"
                    >
                      Add Ambiguity Rule
                    </Button>
                  </div>
                </Panel>
              </Collapse>
            </ConfigProvider>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

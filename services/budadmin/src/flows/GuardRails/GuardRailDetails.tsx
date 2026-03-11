import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import React, { useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { errorToast } from "@/components/toast";
import useGuardrails from "src/hooks/useGuardrails";
import CustomSelect from "../components/CustomSelect";
import GuardTypeSelect from "../components/GuardTypeSelect";
import TextInput from "../components/TextInput";
import TextAreaInput from "@/components/ui/bud/dataEntry/TextArea";

// Modality options (single select)
const MODALITY_OPTIONS = [
  { label: "Text", value: "text" },
  { label: "Video", value: "video" },
  { label: "Image", value: "image" },
  { label: "Actions", value: "actions" },
  { label: "Code", value: "code" },
  { label: "Math", value: "math" },
];

export default function GuardRailDetails() {
  const { openDrawerWithStep } = useDrawer();
  const { updateCustomProbeWorkflow, customProbePolicy, workflowLoading } = useGuardrails();

  // Editable form state
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [guardTypes, setGuardTypes] = useState<string[]>([]);
  const [modality, setModality] = useState<string>("");

  const handleBack = () => {
    openDrawerWithStep("add-custom-guardrail");
  };

  const handleFinish = async () => {
    if (!name.trim()) {
      errorToast("Please enter a guard rail name");
      return;
    }
    if (!description.trim()) {
      errorToast("Please enter a description");
      return;
    }
    if (guardTypes.length === 0) {
      errorToast("Please select at least one guard type");
      return;
    }
    if (!modality) {
      errorToast("Please select a modality");
      return;
    }

    const success = await updateCustomProbeWorkflow({
      step_number: 3,
      trigger_workflow: true,
      probe_type_option: "llm_policy",
      policy: customProbePolicy,
      name: name.trim(),
      description: description.trim(),
      guard_types: guardTypes,
      modality_types: modality ? [modality] : [],
    });

    if (!success) return;
    openDrawerWithStep("custom-probe-success");
  };

  return (
    <BudForm
      data={{}}
      disableNext={workflowLoading}
      onBack={handleBack}
      onNext={handleFinish}
      backText="Back"
      nextText={workflowLoading ? "Creating..." : "Finish"}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Guard Rail details"
            description="Configure the details for your custom guardrail"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem]"
          />

          <div className="px-[1.35rem] pb-[1.35rem] pt-[1.5rem]">
            {/* Guard rail Name */}
            <div className="mb-[1.5rem]">
              <TextInput
                name="name"
                label="Guard rail Name"
                placeholder="Enter guard rail name"
                onChange={(value) => setName(value)}
                rules={[]}
              />
            </div>

            {/* Guardrail Description */}
            <div className="mb-[1.5rem]">
              <TextAreaInput
                name="description"
                label="Guardrail Description"
                placeholder="Enter guardrail description"
                info="Provide a brief description of what this guardrail does"
                rules={[]}
                onChange={(value) => setDescription(value)}
              />
            </div>

            {/* Guard Type (Multi-select with colored tags) */}
            <div className="mb-[1.5rem]">
              <GuardTypeSelect
                value={guardTypes}
                onChange={(values) => setGuardTypes(values)}
                placeholder="Select guard types"
                info="Select which part of inference lifecycle to guard"
              />
            </div>

            {/* Modality (Single select) */}
            <div className="mb-[1.5rem]">
              <CustomSelect
                name="modality"
                label="Modality"
                value={modality}
                onChange={(value) => setModality(value)}
                info="Select the modality for the guardrail"
                selectOptions={MODALITY_OPTIONS}
                placeholder="Select modality"
                InputClasses="h-[2.875rem]"
              />
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

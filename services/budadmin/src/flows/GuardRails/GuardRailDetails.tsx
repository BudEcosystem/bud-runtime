import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { Input } from "antd";
import React, { useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { errorToast, successToast } from "@/components/toast";
import useGuardrails from "src/hooks/useGuardrails";
import { Text_12_400_757575 } from "@/components/ui/text";
import CustomSelect from "../components/CustomSelect";
import GuardTypeSelect from "../components/GuardTypeSelect";
import TextInput from "../components/TextInput";

const { TextArea } = Input;

// Modality options (single select)
const MODALITY_OPTIONS = [
  { label: "Text", value: "text" },
  { label: "Video", value: "video" },
  { label: "Image", value: "image" },
  { label: "Actions", value: "actions" },
  { label: "Code", value: "code" },
  { label: "Math", value: "math" },
];

// Reusable input styles
const inputClassName = "bg-transparent text-[#EEEEEE] border-[#757575] hover:border-[#EEEEEE] focus:border-[#EEEEEE]";
const inputStyle = { backgroundColor: "transparent", color: "#EEEEEE" };

export default function GuardRailDetails() {
  const { closeDrawer, openDrawerWithStep } = useDrawer();
  const { updateCustomProbeWorkflow, customProbePolicy, workflowLoading, clearWorkflow } = useGuardrails();

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

    successToast("Guardrail created successfully!");
    clearWorkflow();
    closeDrawer();
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
              <Text_12_400_757575 className="mb-[0.5rem] block">
                Guardrail Description
              </Text_12_400_757575>
              <TextArea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Enter guardrail description"
                rows={4}
                className={inputClassName}
                style={inputStyle}
              />
            </div>

            {/* Guard Type (Multi-select with colored tags) */}
            <div className="mb-[1.5rem]">
              <GuardTypeSelect
                value={guardTypes}
                onChange={(values) => setGuardTypes(values)}
                placeholder="Select guard types"
              />
            </div>

            {/* Modality (Single select) */}
            <div className="mb-[1.5rem]">
              <CustomSelect
                name="modality"
                label="Modality"
                value={modality}
                onChange={(value) => setModality(value)}
                placeholder="Select modality"
                selectOptions={MODALITY_OPTIONS}
              />
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

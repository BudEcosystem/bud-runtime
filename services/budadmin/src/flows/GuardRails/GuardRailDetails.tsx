import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { Input, Select, ConfigProvider } from "antd";
import React, { useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { successToast } from "@/components/toast";
// import { errorToast } from "@/components/toast"; // TODO: Re-enable when validation is enabled
import { Text_12_400_757575 } from "@/components/ui/text";

const { TextArea } = Input;

// Guard type options (multi-select)
const GUARD_TYPE_OPTIONS = [
  { label: "Input", value: "input" },
  { label: "Output", value: "output" },
  { label: "Agents", value: "agents" },
  { label: "Retrieval", value: "retrieval" },
];

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

  // Editable form state
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [guardTypes, setGuardTypes] = useState<string[]>([]);
  const [modality, setModality] = useState<string>("");

  const handleBack = () => {
    openDrawerWithStep("add-custom-guardrail");
  };

  const handleFinish = () => {
    // TODO: Re-enable validation when ready
    // if (!name.trim()) {
    //   errorToast("Please enter a guard rail name");
    //   return;
    // }
    // if (!description.trim()) {
    //   errorToast("Please enter a description");
    //   return;
    // }
    // if (guardTypes.length === 0) {
    //   errorToast("Please select at least one guard type");
    //   return;
    // }
    // if (!modality) {
    //   errorToast("Please select a modality");
    //   return;
    // }

    // Build the guardrail details object
    const guardrailDetails = {
      name: name.trim(),
      description: description.trim(),
      guard_types: guardTypes,
      modality: modality,
    };

    console.log("GuardRail Details:", JSON.stringify(guardrailDetails, null, 2));
    successToast("Guardrail created successfully!");
    closeDrawer();
  };

  return (
    <BudForm
      data={{}}
      onBack={handleBack}
      onNext={handleFinish}
      backText="Back"
      nextText="Finish"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Guard Rail details"
            description="Configure the details for your custom guardrail"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem]"
          />

          <div className="px-[1.35rem] pb-[1.35rem]">
            {/* Guard rail Name */}
            <div className="mb-[1.5rem]">
              <Text_12_400_757575 className="mb-[0.5rem] block">
                Guard rail Name
              </Text_12_400_757575>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Enter guard rail name"
                className={inputClassName}
                style={inputStyle}
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

            {/* Guard Type (Multi-select) */}
            <div className="mb-[1.5rem]">
              <Text_12_400_757575 className="mb-[0.5rem] block">
                Guard type
              </Text_12_400_757575>
              <Text_12_400_757575 className="mb-[0.5rem] block text-[10px]">
                Multi-select: Input / Output / Agents / Retrieval
              </Text_12_400_757575>
              <ConfigProvider
                theme={{
                  token: {
                    colorTextPlaceholder: "#808080",
                    colorBgElevated: "#101010",
                    colorBorder: "#757575",
                    colorText: "#EEEEEE",
                    colorBgContainer: "transparent",
                  },
                }}
              >
                <Select
                  mode="multiple"
                  value={guardTypes}
                  onChange={(values) => setGuardTypes(values)}
                  placeholder="Select guard types"
                  options={GUARD_TYPE_OPTIONS}
                  className="w-full"
                  style={{ backgroundColor: "transparent" }}
                />
              </ConfigProvider>
            </div>

            {/* Modality (Single select) */}
            <div className="mb-[1.5rem]">
              <Text_12_400_757575 className="mb-[0.5rem] block">
                Modality
              </Text_12_400_757575>
              <Text_12_400_757575 className="mb-[0.5rem] block text-[10px]">
                Single Select: Text, Video, Image, Actions / Code / Math
              </Text_12_400_757575>
              <ConfigProvider
                theme={{
                  token: {
                    colorTextPlaceholder: "#808080",
                    colorBgElevated: "#101010",
                    colorBorder: "#757575",
                    colorText: "#EEEEEE",
                    colorBgContainer: "transparent",
                  },
                }}
              >
                <Select
                  value={modality || undefined}
                  onChange={(value) => setModality(value)}
                  placeholder="Select modality"
                  options={MODALITY_OPTIONS}
                  className="w-full"
                  style={{ backgroundColor: "transparent" }}
                />
              </ConfigProvider>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

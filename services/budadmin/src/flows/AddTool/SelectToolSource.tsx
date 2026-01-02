import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import React, { useState, useEffect } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import ProviderCardWithCheckBox from "src/flows/components/ProviderCardWithCheckBox";
import { Text_14_400_EEEEEE } from "@/components/ui/text";
import { useAddTool, ToolSourceType } from "@/stores/useAddTool";

interface ToolSourceOption {
  id: string;
  name: string;
  description: string;
  icon: string;
  iconLocal: boolean;
  status: "active" | "inactive";
  nextStep?: string;
  sourceType: ToolSourceType;
}

const budCateloge: ToolSourceOption[] = [
  {
    id: "bud-catalogue",
    name: "Bud Catalogue",
    description:
      "Bud ecosystem over 1000 tools API will be everything from Search, Code, and many integrations",
    icon: "/images/drawer/disk-2.png",
    iconLocal: true,
    status: "active",
    nextStep: "bud-tools-catalogue",
    sourceType: ToolSourceType.BUD_CATALOGUE,
  }
];

const toolSourceOptions: ToolSourceOption[] = [
  {
    id: "open-api-spec",
    name: "From Open API Spec",
    description:
      "Create a tool interconnection via API specification. You will be required to only send base URL and API key/token.",
    icon: "/images/drawer/url-2.png",
    iconLocal: true,
    status: "active",
    nextStep: "openapi-specification",
    sourceType: ToolSourceType.OPENAPI_URL,
  },
  {
    id: "from-documentation",
    name: "From Documentation",
    description:
      "We can extract an SDK/tool/callable for you by reading the documentation of a tool. You must not have a OpenAPI.",
    icon: "/images/drawer/disk-2.png",
    iconLocal: true,
    status: "active",
    nextStep: "openapi-specification",
    sourceType: ToolSourceType.API_DOCS_URL,
  },
];

export default function SelectToolSource() {
  const { openDrawerWithStep } = useDrawer();
  const [selectedSource, setSelectedSource] = useState<string>("");

  const {
    setSourceType,
    createWorkflow,
    reset,
    isLoading,
  } = useAddTool();

  // Reset store when component mounts (new flow)
  useEffect(() => {
    reset();
  }, [reset]);

  const getSelectedOption = (): ToolSourceOption | undefined => {
    const allOptions = [...budCateloge, ...toolSourceOptions];
    return allOptions.find((opt) => opt.id === selectedSource);
  };

  const handleNext = async () => {
    const selected = getSelectedOption();
    if (!selected) return;

    // Set source type in store
    setSourceType(selected.sourceType);

    // Create workflow
    const workflow = await createWorkflow();
    if (workflow && selected.nextStep) {
      openDrawerWithStep(selected.nextStep);
    }
  };

  return (
    <BudForm
      data={{}}
      nextText="Next"
      onNext={handleNext}
      disableNext={!selectedSource || isLoading}
      drawerLoading={isLoading}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Add Tools"
            description="Bud tool allows you to create custom tools or select tools from list of over 1000+ tools."
            classNames="pt-[.8rem] border-b-[.5px] border-b-[#1F1F1F]"
            descriptionClass="pt-[.3rem] text-[#B3B3B3]"
          />

          <div className="pt-[.4rem]">
            {budCateloge.map((option) => (
              <ProviderCardWithCheckBox
                key={option.id}
                data={option}
                selected={selectedSource === option.id}
                handleClick={() => setSelectedSource(option.id)}
              />
            ))}
          </div>
          <div className="px-[1.5rem] mt-[1.5rem]">
            <Text_14_400_EEEEEE>Create</Text_14_400_EEEEEE>
          </div>
          <div className="pt-[.4rem]">
            {toolSourceOptions.map((option) => (
              <ProviderCardWithCheckBox
                key={option.id}
                data={option}
                selected={selectedSource === option.id}
                handleClick={() => setSelectedSource(option.id)}
              />
            ))}
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

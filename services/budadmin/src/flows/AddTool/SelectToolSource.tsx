import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import React, { useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import ProviderCardWithCheckBox from "src/flows/components/ProviderCardWithCheckBox";
import { Text_14_400_EEEEEE } from "@/components/ui/text";

interface ToolSourceOption {
  id: string;
  name: string;
  description: string;
  icon: string;
  iconLocal: boolean;
  status: "active" | "inactive";
  nextStep?: string;
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
  },
  {
    id: "native-functions",
    name: "Create Native Functions",
    description:
      "You can create these functions by copy pasting the SDK/API functions",
    icon: "/images/drawer/brain.png",
    iconLocal: true,
    status: "active",
    nextStep: "openapi-specification",
  },
  {
    id: "natural-language",
    name: "Create with Natural Language",
    description:
      "Our intelligent tool creator guided/allow you to describe any tool through natural language, based on the description it can be built automatically. No coding.",
    icon: "/images/drawer/embedding.png",
    iconLocal: true,
    status: "active",
    nextStep: "openapi-specification",
  },
];

export default function SelectToolSource() {
  const { openDrawerWithStep } = useDrawer();
  const [selectedSource, setSelectedSource] = useState<string>("");

  const getNextStep = (): string | undefined => {
    const allOptions = [...budCateloge, ...toolSourceOptions];
    const selected = allOptions.find((opt) => opt.id === selectedSource);
    return selected?.nextStep;
  };

  const handleNext = () => {
    const nextStep = getNextStep();
    if (nextStep) {
      openDrawerWithStep(nextStep);
    }
  };

  return (
    <BudForm
      data={{}}
      nextText="Next"
      onNext={handleNext}
      disableNext={!selectedSource}
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

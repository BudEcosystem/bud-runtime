import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import React, { useContext } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import {
  Text_12_400_757575,
  Text_14_400_EEEEEE,
  Text_14_600_FFFFFF,
} from "@/components/ui/text";

interface ProbeDetailsProps {
  probeName?: string;
  probeData?: {
    name: string;
    description: string;
    modality: string[];
    scannerType: string;
    guardType: string[];
    examples?: Array<{
      id: string;
      title: string;
      content: string;
    }>;
  };
}

export default function ProbeDetails({ probeData }: ProbeDetailsProps) {
  const { isExpandedViewOpen } = useContext(BudFormContext);
  const { closeExpandedStep, closeDrawer } = useDrawer();

  // Default data if not provided
  const defaultProbeData = {
    name: "Politeness Detection",
    description: "Detects and filters impolite or offensive language in model outputs to ensure respectful communication.",
    modality: ["Text", "Image", "Audio", "Code"],
    scannerType: "Semantic | Text | Regex | Classifier",
    guardType: ["Input", "Output", "Retrieval", "Agent"],
    examples: [
      {
        id: "1",
        title: "Sample 1",
        content: "Example of polite response: 'Thank you for your question. I'd be happy to help you with that.'"
      },
      {
        id: "2",
        title: "Sample 2",
        content: "Example of impolite response: 'That's a stupid question.' - This would be flagged and filtered."
      }
    ]
  };

  const data = probeData || defaultProbeData;

  const handleClose = () => {
    if (isExpandedViewOpen) {
      closeExpandedStep();
    } else {
      closeDrawer();
    }
  };

  return (
    <BudForm
      data={{}}
      onNext={handleClose}
      nextText="Close"
      showBack={false}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title={data.name}
            description={data.description}
            classNames="pt-[.8rem]"
          />

          <div className="px-[1.35rem] pb-[1.35rem]">
            {/* Description Section */}
            <div className="mb-[1.5rem]">
              <Text_14_600_FFFFFF className="mb-[0.5rem]">Description</Text_14_600_FFFFFF>
              <Text_14_400_EEEEEE className="text-[#B3B3B3]">
                {data.description}
              </Text_14_400_EEEEEE>
            </div>

            {/* Modality Section */}
            <div className="mb-[1.5rem]">
              <div className="flex items-center gap-[0.5rem]">
                <Text_14_600_FFFFFF>Modality:</Text_14_600_FFFFFF>
                <div className="flex gap-[0.5rem]">
                  {data.modality.map((item, index) => (
                    <span key={index} className="text-[#B3B3B3]">
                      {item}{index < data.modality.length - 1 ? " |" : ""}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* Scanner Type Section */}
            <div className="mb-[1.5rem]">
              <div className="flex items-start gap-[0.5rem]">
                <Text_14_600_FFFFFF>Scanner type:</Text_14_600_FFFFFF>
                <Text_14_400_EEEEEE className="text-[#B3B3B3]">
                  {data.scannerType}
                </Text_14_400_EEEEEE>
              </div>
            </div>

            {/* Guard Type Section */}
            <div className="mb-[2rem]">
              <div className="flex items-center gap-[0.5rem]">
                <Text_14_600_FFFFFF>Guard type:</Text_14_600_FFFFFF>
                <div className="flex gap-[0.5rem]">
                  {data.guardType.map((item, index) => (
                    <span key={index} className="text-[#B3B3B3]">
                      {item}{index < data.guardType.length - 1 ? " |" : ""}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* Examples Section */}
            {data.examples && data.examples.length > 0 && (
              <div>
                <Text_14_600_FFFFFF className="mb-[1rem]">Examples</Text_14_600_FFFFFF>
                <div className="space-y-[1rem]">
                  {data.examples.map((example) => (
                    <div
                      key={example.id}
                      className="bg-[#1F1F1F] border border-[#757575] rounded-[6px] p-[1rem]"
                    >
                      <div className="flex items-center justify-between mb-[0.75rem]">
                        <Text_14_600_FFFFFF>{example.title}</Text_14_600_FFFFFF>
                        <div className="w-[40px] h-[40px] bg-[#2F2F2F] border border-[#757575] rounded-[4px]" />
                      </div>
                      <Text_12_400_757575>
                        {example.content}
                      </Text_12_400_757575>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

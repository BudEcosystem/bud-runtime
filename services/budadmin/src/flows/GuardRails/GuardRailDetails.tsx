import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { Tag } from "antd";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { successToast } from "@/components/toast";
import {
  Text_12_400_757575,
  Text_14_400_EEEEEE,
  Text_14_600_FFFFFF,
} from "@/components/ui/text";

export default function GuardRailDetails() {
  const { closeDrawer } = useDrawer();

  // This would typically come from the previous steps or context
  const guardrailData = {
    name: "Custom Greeting Filter",
    description: "A custom guardrail that filters greeting messages and validates input patterns using RegEx and semantic matching to ensure appropriate responses.",
    guardTypes: ["Input", "Output"],
    modality: "Text",
    rules: [
      { type: "RegEx", pattern: "[a-zA-Z0-9]+", status: "Active" },
      { type: "Text", words: ["Hi", "Hello", "Greetings"], status: "Active" },
    ],
    budExpression: "if (input.contains('greeting')) then validate()",
    createdAt: new Date().toLocaleDateString(),
    status: "Active",
  };

  const handleFinish = () => {
    successToast("Guardrail created successfully!");
    closeDrawer();
  };

  return (
    <BudForm
      data={{}}
      showBack={false}
      onNext={handleFinish}
      nextText="Finish"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Guard Rail details"
            description="Your custom guardrail has been successfully created"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem]"
          />

          <div className="px-[1.35rem] pb-[1.35rem]">
            {/* Success Status */}
            <div className="mb-[2rem] p-[1rem] bg-[#52C41A10] border border-[#52C41A] rounded-[6px] text-center">
              <Text_14_600_FFFFFF className="text-[#52C41A]">
                ✓ Guardrail Created Successfully
              </Text_14_600_FFFFFF>
            </div>

            {/* Guard rail Name */}
            <div className="mb-[1.5rem]">
              <Text_12_400_757575 className="mb-[0.25rem]">
                Guard rail Name
              </Text_12_400_757575>
              <div className="p-[0.75rem] bg-[#1A1A1A] border border-[#2A2A2A] rounded-[6px]">
                <Text_14_400_EEEEEE>{guardrailData.name}</Text_14_400_EEEEEE>
              </div>
            </div>

            {/* Guardrail Description */}
            <div className="mb-[1.5rem]">
              <Text_12_400_757575 className="mb-[0.25rem]">
                Guardrail Description
              </Text_12_400_757575>
              <div className="p-[0.75rem] bg-[#1A1A1A] border border-[#2A2A2A] rounded-[6px] min-h-[80px]">
                <Text_14_400_EEEEEE>{guardrailData.description}</Text_14_400_EEEEEE>
              </div>
            </div>

            {/* Guard Type */}
            <div className="mb-[1.5rem]">
              <Text_12_400_757575 className="mb-[0.25rem]">
                Guard type
              </Text_12_400_757575>
              <div className="p-[0.75rem] bg-[#1A1A1A] border border-[#2A2A2A] rounded-[6px]">
                <div className="flex gap-[0.5rem] flex-wrap">
                  {guardrailData.guardTypes.map((type) => (
                    <Tag key={type} className="bg-[#965CDE20] border-[#965CDE] text-[#EEEEEE]">
                      {type}
                    </Tag>
                  ))}
                </div>
              </div>
            </div>

            {/* Modality */}
            <div className="mb-[1.5rem]">
              <Text_12_400_757575 className="mb-[0.25rem]">
                Modality
              </Text_12_400_757575>
              <div className="p-[0.75rem] bg-[#1A1A1A] border border-[#2A2A2A] rounded-[6px]">
                <Text_14_400_EEEEEE>{guardrailData.modality}</Text_14_400_EEEEEE>
              </div>
            </div>

            {/* Rules Summary */}
            <div className="mb-[1.5rem]">
              <Text_12_400_757575 className="mb-[0.25rem]">
                Configured Rules
              </Text_12_400_757575>
              <div className="p-[0.75rem] bg-[#1A1A1A] border border-[#2A2A2A] rounded-[6px]">
                <div className="space-y-[0.5rem]">
                  {guardrailData.rules.map((rule, index) => (
                    <div key={index} className="flex items-center gap-[0.75rem]">
                      <Tag className="bg-[#757575] border-none text-[#EEEEEE]">
                        {rule.type}
                      </Tag>
                      <Text_12_400_757575>
                        {rule.type === "Text"
                          ? `Words: ${rule.words?.join(", ")}`
                          : `Pattern: ${rule.pattern}`}
                      </Text_12_400_757575>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Additional Info */}
            <div className="grid grid-cols-2 gap-[1rem]">
              <div>
                <Text_12_400_757575 className="mb-[0.25rem]">
                  Status
                </Text_12_400_757575>
                <div className="p-[0.5rem] bg-[#1A1A1A] border border-[#2A2A2A] rounded-[6px]">
                  <Tag className="bg-[#52C41A20] border-[#52C41A] text-[#52C41A]">
                    {guardrailData.status}
                  </Tag>
                </div>
              </div>
              <div>
                <Text_12_400_757575 className="mb-[0.25rem]">
                  Created Date
                </Text_12_400_757575>
                <div className="p-[0.5rem] bg-[#1A1A1A] border border-[#2A2A2A] rounded-[6px]">
                  <Text_14_400_EEEEEE>{guardrailData.createdAt}</Text_14_400_EEEEEE>
                </div>
              </div>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

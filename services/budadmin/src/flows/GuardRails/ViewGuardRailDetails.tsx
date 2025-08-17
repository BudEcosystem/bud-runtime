import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { Tag, Divider } from "antd";
import React, { useState, useEffect } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import {
  Text_11_400_808080,
  Text_12_400_757575,
  Text_12_400_B3B3B3,
  Text_13_400_B3B3B3,
  Text_14_400_EEEEEE,
  Text_14_600_FFFFFF,
  Text_16_600_FFFFFF,
} from "@/components/ui/text";

interface GuardRailDetail {
  id: string;
  name: string;
  type: string;
  category: string[];
  description?: string;
  provider?: string;
  deployments?: number;
  status?: "active" | "inactive" | "pending";
  modality?: string[];
  scannerType?: string[];
  guardType?: string[];
  typeCategories?: string[];
  examples?: {
    title: string;
    content: string;
    description?: string;
  }[];
}

export default function ViewGuardRailDetails() {
  const { openDrawerWithStep, closeDrawer, drawerProps } = useDrawer();
  const [guardrail, setGuardrail] = useState<GuardRailDetail | null>(null);

  // Get guardrail data - in real app, fetch from API based on ID
  useEffect(() => {
    // Using dummy data for now
    const dummyData: GuardRailDetail = drawerProps?.guardrail || {
      id: "1",
      name: "PII Detection",
      type: "pii",
      category: ["harm", "compliance", "privacy"],
      description: "Advanced PII detection guardrail that identifies and masks personal identifiable information including SSN, credit cards, emails, phone numbers, addresses, and other sensitive data.",
      provider: "Bud Sentinel",
      deployments: 12,
      status: "active",
      modality: ["Text", "Image", "Audio", "Code"],
      scannerType: ["Semantic", "Text", "RegEx", "Classifier"],
      guardType: ["Input", "Output", "Retrieval", "Agent"],
      typeCategories: ["PII", "Harm", "Prompt Injection", "Jailbreak"],
      examples: [
        {
          title: "Example 1",
          content: "Input: My credit card is 4532-1234-5678-9012\nOutput: My credit card is [REDACTED]",
          description: "Credit card detection and masking"
        },
        {
          title: "Example 2",
          content: "Input: SSN: 123-45-6789\nOutput: SSN: [REDACTED]",
          description: "Social security number redaction"
        }
      ]
    };
    setGuardrail(dummyData);
  }, [drawerProps]);

  const handleDeploy = () => {
    // Navigate to deployment flow starting with deployment types
    openDrawerWithStep("deployment-types");
  };

  const handleBack = () => {
    closeDrawer();
  };

  const getTypeIcon = (type?: string) => {
    switch(type) {
      case 'pii':
        return '🔒';
      case 'jailbreak':
        return '🚫';
      case 'toxicity':
        return '⚠️';
      case 'bias':
        return '⚖️';
      default:
        return '🛡️';
    }
  };

  if (!guardrail) {
    return null;
  }

  return (
    <BudForm
      data={{}}
      onBack={handleBack}
      onNext={handleDeploy}
      backText="Back"
      nextText="Deploy"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          {/* Header */}
          <div className="px-[1.35rem] pt-[1rem]">
            <div className="flex items-start gap-[1rem] mb-[1.5rem]">
              <div className="w-[3rem] h-[3rem] bg-[#1F1F1F] rounded-[8px] flex items-center justify-center text-[1.5rem]">
                {getTypeIcon(guardrail.type)}
              </div>
              <div className="flex-1">
                <Text_16_600_FFFFFF className="mb-[0.5rem]">
                  {guardrail.name}
                </Text_16_600_FFFFFF>
                <Text_13_400_B3B3B3 className="leading-[1.4]">
                  {guardrail.description}
                </Text_13_400_B3B3B3>
              </div>
            </div>

            <Divider className="bg-[#1F1F1F] my-[1.5rem]" />

            {/* Metadata Section */}
            <div className="space-y-[1.5rem] mb-[1.5rem]">
              {/* Modality */}
              <div>
                <Text_12_400_757575 className="mb-[0.5rem]">
                  Modality:
                </Text_12_400_757575>
                <div className="flex flex-wrap gap-[0.5rem]">
                  {guardrail.modality?.map((item, idx) => (
                    <span key={idx} className="text-[#EEEEEE] text-[0.75rem]">
                      {item}{idx < guardrail.modality!.length - 1 ? " | " : ""}
                    </span>
                  ))}
                </div>
              </div>

              {/* Scanner Type */}
              <div>
                <Text_12_400_757575 className="mb-[0.5rem]">
                  Scanner type:
                </Text_12_400_757575>
                <div className="flex flex-wrap gap-[0.5rem]">
                  {guardrail.scannerType?.map((item, idx) => (
                    <span key={idx} className="text-[#EEEEEE] text-[0.75rem]">
                      {item}{idx < guardrail.scannerType!.length - 1 ? " | " : ""}
                    </span>
                  ))}
                </div>
              </div>

              {/* Guard Type */}
              <div>
                <Text_12_400_757575 className="mb-[0.5rem]">
                  Guard type:
                </Text_12_400_757575>
                <div className="flex flex-wrap gap-[0.5rem]">
                  {guardrail.guardType?.map((item, idx) => (
                    <span key={idx} className="text-[#EEEEEE] text-[0.75rem]">
                      {item}{idx < guardrail.guardType!.length - 1 ? " | " : ""}
                    </span>
                  ))}
                </div>
              </div>

              {/* Type */}
              <div>
                <Text_12_400_757575 className="mb-[0.5rem]">
                  Type:
                </Text_12_400_757575>
                <div className="flex flex-wrap gap-[0.5rem]">
                  {guardrail.typeCategories?.map((item, idx) => (
                    <span key={idx} className="text-[#EEEEEE] text-[0.75rem]">
                      {item}{idx < guardrail.typeCategories!.length - 1 ? " | " : ""}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <Divider className="bg-[#1F1F1F] my-[1.5rem]" />

            {/* Examples Section */}
            <div className="mb-[1.5rem]">
              <Text_14_600_FFFFFF className="mb-[1rem]">
                Examples
              </Text_14_600_FFFFFF>

              <div className="space-y-[0.75rem]">
                {guardrail.examples?.map((example, idx) => (
                  <div
                    key={idx}
                    className="bg-[#0A0A0A] border border-[#1F1F1F] rounded-[6px] p-[1rem] hover:border-[#757575] transition-all"
                  >
                    <Text_12_400_B3B3B3 className="mb-[0.5rem]">
                      {example.title}
                    </Text_12_400_B3B3B3>
                    {example.description && (
                      <Text_11_400_808080 className="mb-[0.5rem]">
                        {example.description}
                      </Text_11_400_808080>
                    )}
                    <div className="bg-[#1F1F1F] rounded-[4px] p-[0.75rem]">
                      <pre className="text-[#B3B3B3] text-[0.75rem] whitespace-pre-wrap font-mono">
                        {example.content}
                      </pre>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Status and Deployments */}
            <div className="flex items-center justify-between p-[1rem] bg-[#0A0A0A] border border-[#1F1F1F] rounded-[6px] mb-[1rem]">
              <div className="flex items-center gap-[2rem]">
                <div>
                  <Text_11_400_808080>Provider</Text_11_400_808080>
                  <Text_12_400_B3B3B3>{guardrail.provider}</Text_12_400_B3B3B3>
                </div>
                <div>
                  <Text_11_400_808080>Status</Text_11_400_808080>
                  <Tag
                    className="!m-0 !mt-[0.25rem]"
                    color={guardrail.status === 'active' ? 'green' : 'orange'}
                  >
                    {guardrail.status}
                  </Tag>
                </div>
                <div>
                  <Text_11_400_808080>Deployments</Text_11_400_808080>
                  <Text_12_400_B3B3B3>{guardrail.deployments} active</Text_12_400_B3B3B3>
                </div>
              </div>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

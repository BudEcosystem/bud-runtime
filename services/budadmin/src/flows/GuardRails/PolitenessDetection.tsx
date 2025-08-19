import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import React, { useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { successToast } from "@/components/toast";
import {
  Text_12_400_757575,
  Text_14_400_EEEEEE,
  Text_12_400_B3B3B3,
  Text_12_300_EEEEEE,
} from "@/components/ui/text";
import { Input, Select, Slider, ConfigProvider } from "antd";

export default function PolitenessDetection() {
  const { openDrawerWithStep, closeDrawer } = useDrawer();
  const [config, setConfig] = useState({
    name: "",
    sensitivity: 50,
    action: "block",
  });

  const handleBack = () => {
    openDrawerWithStep("select-provider");
  };

  const handleNext = () => {
    // Here you would save the guardrail configuration
    successToast("Guardrail created successfully");
    closeDrawer();
  };

  return (
    <BudForm
      data={{}}
      onBack={handleBack}
      onNext={handleNext}
      backText="Back"
      nextText="Create"
      disableNext={!config.name}
    >
      <BudWraperBox >
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Politeness Detection"
            description="Configure the politeness detection guardrail for your model"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem]"
          />

          <div className="px-[1.35rem] pb-[1.35rem]">
            {/* Name Input */}
            <div className="mb-[1.5rem]">
              <Text_14_400_EEEEEE className="mb-[0.5rem]">Name</Text_14_400_EEEEEE>
              <Input
                placeholder="Enter guardrail name"
                value={config.name}
                onChange={(e) => setConfig({ ...config, name: e.target.value })}
                className="bg-transparent text-[#EEEEEE] border-[#757575] hover:border-[#EEEEEE] focus:border-[#EEEEEE]"
                style={{
                  backgroundColor: 'transparent',
                  color: '#EEEEEE',
                }}
              />
            </div>

            {/* Sensitivity Slider */}
            <div className="mb-[1.5rem]">
              <Text_14_400_EEEEEE className="mb-[0.5rem]">
                Sensitivity Level
              </Text_14_400_EEEEEE>
              <Text_12_400_757575 className="mb-[1rem]">
                Adjust how sensitive the politeness detection should be
              </Text_12_400_757575>
              <div className="flex items-center gap-4">
                <span className="text-[#757575] text-xs">Low</span>
                <Slider
                  className="flex-1"
                  value={config.sensitivity}
                  onChange={(value) => setConfig({ ...config, sensitivity: value })}
                  min={0}
                  max={100}
                  tooltip={{
                    formatter: (value) => `${value}%`,
                  }}
                  styles={{
                    track: {
                      backgroundColor: "#965CDE",
                    },
                    rail: {
                      backgroundColor: "#212225",
                    },
                  }}
                />
                <span className="text-[#757575] text-xs">High</span>
              </div>
            </div>

            {/* Action Select */}
            <div className="rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[1.5rem]">
              <div className="w-full">
                <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10">
                  Action on Detection
                </Text_12_300_EEEEEE>
              </div>
              <div className="custom-select-two w-full rounded-[6px] relative">
                <ConfigProvider
                  theme={{
                    token: {
                      colorTextPlaceholder: "#808080",
                      boxShadowSecondary: "none",
                    },
                  }}
                >
                  <Select
                    placeholder="Select Action"
                    value={config.action}
                    onChange={(value) => setConfig({ ...config, action: value })}
                    style={{
                      backgroundColor: "transparent",
                      color: "#EEEEEE",
                      border: "0.5px solid #757575",
                      width: "100%",
                    }}
                    size="large"
                    className="drawerInp !bg-[transparent] text-[#EEEEEE] py-[.6rem] font-[300] text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] h-[2.59338rem]"
                    options={[
                      { label: "Block Request", value: "block" },
                      { label: "Log and Continue", value: "log" },
                      { label: "Modify Response", value: "modify" },
                    ]}
                  />
                </ConfigProvider>
              </div>
            </div>

            {/* Configuration Summary */}
            <div className="p-[1rem] bg-[#FFFFFF08] rounded-[8px] border border-[#1F1F1F]">
              <Text_12_400_757575 className="mb-[0.5rem]">Configuration Summary</Text_12_400_757575>
              <div className="space-y-[0.25rem]">
                <Text_12_400_B3B3B3>• Provider: Azure AI Foundry</Text_12_400_B3B3B3>
                <Text_12_400_B3B3B3>• Type: Politeness Detection</Text_12_400_B3B3B3>
                <Text_12_400_B3B3B3>• Sensitivity: {config.sensitivity}%</Text_12_400_B3B3B3>
                <Text_12_400_B3B3B3>• Action: {config.action}</Text_12_400_B3B3B3>
              </div>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

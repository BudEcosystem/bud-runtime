import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { Checkbox, Slider } from "antd";
import React, { useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import {
  Text_12_400_757575,
  Text_14_400_EEEEEE,
  Text_14_600_FFFFFF,
} from "@/components/ui/text";

export default function ProbeSettings() {
  const { openDrawerWithStep } = useDrawer();
  const [selectedLifecycle, setSelectedLifecycle] = useState<string[]>([]);
  const [strictnessLevel, setStrictnessLevel] = useState(0.75);

  const lifecycleOptions = [
    { value: "input", label: "Input" },
    { value: "output", label: "Output" },
    { value: "retrieval", label: "Retrieval" },
    { value: "tools", label: "Tools" },
  ];

  const handleBack = () => {
    openDrawerWithStep("select-deployment");
  };

  const handleDeploy = () => {
    // Navigate to deployment progress screen
    openDrawerWithStep("deploying-probe");
  };

  const handleLifecycleChange = (value: string, checked: boolean) => {
    if (checked) {
      setSelectedLifecycle([...selectedLifecycle, value]);
    } else {
      setSelectedLifecycle(selectedLifecycle.filter(item => item !== value));
    }
  };

  const formatSliderValue = (value: number) => {
    return value.toFixed(2);
  };

  return (
    <BudForm
      data={{}}
      onBack={handleBack}
      onNext={handleDeploy}
      backText="Back"
      nextText="Deploy"
      disableNext={selectedLifecycle.length === 0}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Probe Settings"
            description="You are now adding {Probe Name} Probe to {Deployment Name} deployment."
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem] text-[#B3B3B3]"
          />

          <div className="px-[1.35rem] pb-[1.35rem]">
            {/* Add To Section */}
            <div className="mb-[2rem]">
              <div className="bg-[#ffffff07] border border-[#757575] rounded-[8px] p-[1.5rem]">
                <Text_14_600_FFFFFF className="mb-[0.5rem]">
                  Add To:
                </Text_14_600_FFFFFF>
                <Text_12_400_757575 className="mb-[1rem] block">
                  Select which part of Inference lifecycle you would like to add the probe to
                </Text_12_400_757575>

                <div className="flex items-center gap-[2rem] flex-wrap">
                  {lifecycleOptions.map((option) => (
                    <div key={option.value} className="flex items-center gap-[0.5rem]">
                      <Checkbox
                        checked={selectedLifecycle.includes(option.value)}
                        onChange={(e) => handleLifecycleChange(option.value, e.target.checked)}
                        className="AntCheckbox"
                      />
                      <Text_14_400_EEEEEE>{option.label}</Text_14_400_EEEEEE>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Strictness Level Section */}
            <div>
              <div className="bg-[#ffffff07] border border-[#757575] rounded-[8px] p-[1.5rem]">
                <Text_14_600_FFFFFF className="mb-[0.5rem]">
                  Strictness Level:
                </Text_14_600_FFFFFF>
                <Text_12_400_757575 className="mb-[1.5rem] block">
                  Level of strictness, the more strict it is more chance for False negatives but better protection
                </Text_12_400_757575>

                <div className="relative px-[1rem]">
                  {/* Slider Value Display */}
                  <div
                    className="absolute -top-[2rem] bg-[#965CDE] text-white px-[0.5rem] py-[0.25rem] rounded-[4px] text-[12px] font-medium"
                    style={{
                      left: `calc(${strictnessLevel * 100}% - 1.5rem)`,
                      transition: 'left 0.2s'
                    }}
                  >
                    {formatSliderValue(strictnessLevel)}
                  </div>

                  {/* Slider */}
                  <Slider
                    min={0}
                    max={1}
                    step={0.01}
                    value={strictnessLevel}
                    onChange={(value) => setStrictnessLevel(value)}
                    className="mb-[0.5rem] [&_.ant-slider-handle]:!w-[16px] [&_.ant-slider-handle]:!h-[16px] [&_.ant-slider-handle]:!bg-transparent [&_.ant-slider-handle]:!border-transparent [&_.ant-slider-handle]:!shadow-md [&_.ant-slider-handle]:!top-[50%] [&_.ant-slider-handle]:!transform [&_.ant-slider-handle]:!-translate-y-1/2 [&_.ant-slider-track]:!bg-[#965CDE] [&_.ant-slider-rail]:!bg-[#3F3F3F] [&_.ant-slider-track]:!h-[4px] [&_.ant-slider-rail]:!h-[4px]"
                    tooltip={{ open: false }}
                  />

                  {/* Labels */}
                  <div className="flex justify-between mt-[0.5rem]">
                    <Text_12_400_757575>Minimum</Text_12_400_757575>
                    <Text_12_400_757575>Moderate</Text_12_400_757575>
                    <Text_12_400_757575>Maximum</Text_12_400_757575>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

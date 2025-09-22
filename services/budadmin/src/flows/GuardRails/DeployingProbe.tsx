import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { Progress } from "antd";
import React, { useState, useEffect } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Text_14_400_EEEEEE, Text_16_600_FFFFFF } from "@/components/ui/text";

export default function DeployingProbe() {
  const { openDrawerWithStep } = useDrawer();
  const [progress, setProgress] = useState(0);
  const [remainingTime, setRemainingTime] = useState(5); // 30 secs
  const [isComplete, setIsComplete] = useState(false);

  useEffect(() => {
    // Simulate progress
    const progressInterval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          clearInterval(progressInterval);
          setIsComplete(true);
          return 100;
        }
        return prev + 100 / 30; // Complete in 30 seconds
      });
    }, 1000);

    // Update remaining time
    const timeInterval = setInterval(() => {
      setRemainingTime((prev) => {
        if (prev <= 0) {
          clearInterval(timeInterval);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      clearInterval(progressInterval);
      clearInterval(timeInterval);
    };
  }, []);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    if (mins > 0) {
      return `${mins} min${mins > 1 ? "s" : ""} ${secs} sec${secs !== 1 ? "s" : ""}`;
    }
    return `${secs} sec${secs !== 1 ? "s" : ""}`;
  };

  const handleFinish = () => {
    openDrawerWithStep("probe-deployment-success");
  };

  return (
    <BudForm
      data={{}}
      onNext={handleFinish}
      nextText="Finish"
      disableNext={!isComplete}
      showBack={false}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Deploying the Probe"
            description="Bud is deploying Probe to deployment."
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem] text-[#B3B3B3]"
          />

          <div className="px-[1.35rem] pb-[1.35rem]">
            {/* Progress Box */}
            <div className="bg-[#1F1F1F] border border-[#757575] rounded-[8px] p-[2rem] min-h-[150px] flex flex-col items-center justify-center">
              {/* ETA Display */}
              <Text_16_600_FFFFFF className="mb-[2rem]">
                ETA: {formatTime(remainingTime)}
              </Text_16_600_FFFFFF>

              {/* Progress Bar */}
              <div className="w-full">
                <Progress
                  percent={Math.round(progress)}
                  showInfo={false}
                  strokeColor="#965CDE"
                  trailColor="#3F3F3F"
                  strokeWidth={8}
                />
              </div>

              {/* Status Text */}
              {isComplete && (
                <Text_14_400_EEEEEE className="mt-[1.5rem] text-[#52C41A]">
                  Deployment Complete!
                </Text_14_400_EEEEEE>
              )}
            </div>

            {/* Additional Information */}
            <div className="mt-[2rem] space-y-[1rem]">
              <div className="flex items-center gap-[0.5rem]">
                <div
                  className={`w-[8px] h-[8px] rounded-full ${isComplete ? "bg-[#52C41A]" : "bg-[#965CDE]"} animate-pulse`}
                />
                <Text_14_400_EEEEEE>
                  {isComplete
                    ? "Probe successfully deployed"
                    : "Configuring probe settings..."}
                </Text_14_400_EEEEEE>
              </div>

              {!isComplete && (
                <>
                  <div className="flex items-center gap-[0.5rem]">
                    <div className="w-[8px] h-[8px] rounded-full bg-[#757575]" />
                    <Text_14_400_EEEEEE className="text-[#757575]">
                      Applying inference lifecycle rules
                    </Text_14_400_EEEEEE>
                  </div>
                  <div className="flex items-center gap-[0.5rem]">
                    <div className="w-[8px] h-[8px] rounded-full bg-[#757575]" />
                    <Text_14_400_EEEEEE className="text-[#757575]">
                      Setting strictness parameters
                    </Text_14_400_EEEEEE>
                  </div>
                </>
              )}
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

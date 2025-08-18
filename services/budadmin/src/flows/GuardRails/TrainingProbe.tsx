import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { Progress } from "antd";
import React, { useState, useEffect } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import {
  Text_12_400_757575,
  Text_14_400_EEEEEE,
  Text_14_600_FFFFFF,
} from "@/components/ui/text";

interface TrainingStep {
  id: string;
  label: string;
  status: "pending" | "in-progress" | "completed";
}

export default function TrainingProbe() {
  const { openDrawerWithStep } = useDrawer();
  const [progress, setProgress] = useState(0);
  const [eta, setEta] = useState({ minutes: 4, seconds: 20 });
  const [steps, setSteps] = useState<TrainingStep[]>([
    { id: "1", label: "Analysing the dataset", status: "in-progress" },
    { id: "2", label: "Pre-processing the dataset", status: "pending" },
    { id: "3", label: "Finding the best Architecture", status: "pending" },
    { id: "4", label: "Training the Model", status: "pending" },
    { id: "5", label: "Evaluating the Model", status: "pending" },
    { id: "6", label: "Cleaning up the resources", status: "pending" },
  ]);

  // Simulate training progress
  useEffect(() => {
    const timer = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          clearInterval(timer);
          return 100;
        }
        return prev + 2;
      });

      // Update ETA
      setEta((prev) => {
        const totalSeconds = prev.minutes * 60 + prev.seconds - 1;
        if (totalSeconds <= 0) return { minutes: 0, seconds: 0 };
        return {
          minutes: Math.floor(totalSeconds / 60),
          seconds: totalSeconds % 60,
        };
      });

      // Update step statuses
      setSteps((prevSteps) => {
        const newSteps = [...prevSteps];
        const progressPerStep = 100 / 6;
        const currentStepIndex = Math.floor(progress / progressPerStep);

        newSteps.forEach((step, index) => {
          if (index < currentStepIndex) {
            step.status = "completed";
          } else if (index === currentStepIndex) {
            step.status = "in-progress";
          } else {
            step.status = "pending";
          }
        });

        return newSteps;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [progress]);

  const handleNext = () => {
    openDrawerWithStep("guardrail-details");
  };

  const getStepIcon = (status: TrainingStep["status"]) => {
    switch (status) {
      case "completed":
        return (
          <div className="w-[16px] h-[16px] rounded-full bg-[#52C41A] flex items-center justify-center">
            <div className="w-[6px] h-[6px] bg-white rounded-full" />
          </div>
        );
      case "in-progress":
        return (
          <div className="w-[16px] h-[16px] rounded-full border-2 border-[#965CDE] flex items-center justify-center">
            <div className="w-[6px] h-[6px] bg-[#965CDE] rounded-full animate-pulse" />
          </div>
        );
      default:
        return <div className="w-[16px] h-[16px] rounded-full border border-[#757575]" />;
    }
  };

  return (
    <BudForm
      data={{}}
      showBack={false}
      onNext={handleNext}
      nextText="Next"
      disableNext={progress < 100}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Training Probe"
            description="We are currently training a new probe with the dataset you have shared. This may take a few minutes"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem] text-[#B3B3B3]"
          />

          <div className="px-[1.35rem] pb-[1.35rem]">
            {/* ETA Box */}
            <div className="mb-[2rem] p-[1.5rem] bg-[#1A1A1A] rounded-[8px] border border-[#2A2A2A]">
              <div className="text-center mb-[1.5rem]">
                <Text_14_600_FFFFFF>
                  ETA: {eta.minutes} mins {eta.seconds} secs
                </Text_14_600_FFFFFF>
              </div>

              {/* Progress Bar */}
              <div className="mb-[1.5rem]">
                <Progress
                  percent={progress}
                  strokeColor="#757575"
                  trailColor="#2A2A2A"
                  showInfo={false}
                  strokeWidth={8}
                />
              </div>

              {/* Training Steps List */}
              <div className="space-y-[0.75rem]">
                {steps.map((step) => (
                  <div
                    key={step.id}
                    className="flex items-center gap-[0.75rem]"
                  >
                    {getStepIcon(step.status)}
                    <Text_12_400_757575
                      className={
                        step.status === "completed"
                          ? "text-[#EEEEEE] line-through"
                          : step.status === "in-progress"
                          ? "text-[#EEEEEE]"
                          : "text-[#757575]"
                      }
                    >
                      {step.label}
                    </Text_12_400_757575>
                  </div>
                ))}
              </div>
            </div>

            {/* Info Message */}
            {progress === 100 && (
              <div className="p-[1rem] bg-[#52C41A10] border border-[#52C41A] rounded-[6px]">
                <Text_14_400_EEEEEE className="text-[#52C41A] text-center">
                  ✓ Training completed successfully!
                </Text_14_400_EEEEEE>
              </div>
            )}
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

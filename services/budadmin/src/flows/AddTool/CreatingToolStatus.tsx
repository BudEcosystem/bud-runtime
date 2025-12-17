import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import {
  Text_12_400_757575,
  Text_14_400_EEEEEE,
} from "@/components/ui/text";
import React, { useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { ProgressWithBudList } from "src/flows/components/ProgressWithBud";
import { StatusEstimatedTime } from "src/flows/components/StatusEstimatedTime";
import { StatusEvents } from "src/flows/components/StatusIcons";
import { BudSimulatorSteps } from "src/stores/useDeployModel";

// Helper to create a step with all required fields
const createStep = (
  id: string,
  title: string,
  description: string,
  status: string
): BudSimulatorSteps => ({
  id,
  title,
  description,
  payload: {
    category: "internal",
    type: "create_tool",
    event: id,
    workflow_id: "mock-workflow",
    source: "budadmin",
    content: {
      title,
      message: description,
      status,
      primary_action: "",
      secondary_action: "",
      progress: 0,
    },
  },
});

// Mock steps for tool creation progress
const mockToolCreationSteps: BudSimulatorSteps[] = [
  createStep(
    "analyse-docs",
    "Analysing the Documentation",
    "Reading and parsing the documentation",
    "IN_PROGRESS"
  ),
  createStep(
    "identify-tools",
    "Identifying the tools",
    "Extracting tool definitions from the documentation",
    "PENDING"
  ),
  createStep(
    "create-tools",
    "Creating tools",
    "Generating tool configurations",
    "PENDING"
  ),
  createStep(
    "build-mcps",
    "Building MCPs",
    "Building Model Context Protocol servers",
    "PENDING"
  ),
];

export default function CreatingToolStatus() {
  const { closeDrawer } = useDrawer();
  const [steps, setSteps] = useState(mockToolCreationSteps);
  const [eta, setEta] = useState("30 mins 40 Seconds");
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [isCompleted, setIsCompleted] = useState(false);

  // Simulate progress (mock implementation)
  useEffect(() => {
    if (currentStepIndex >= steps.length) {
      setIsCompleted(true);
      return;
    }

    const timer = setTimeout(() => {
      setSteps((prevSteps) => {
        const newSteps = prevSteps.map((step, index) => {
          if (index === currentStepIndex) {
            // Mark current step as completed
            return {
              ...step,
              payload: {
                ...step.payload,
                content: {
                  ...step.payload.content,
                  status: "COMPLETED",
                },
              },
            };
          } else if (index === currentStepIndex + 1) {
            // Mark next step as in progress
            return {
              ...step,
              payload: {
                ...step.payload,
                content: {
                  ...step.payload.content,
                  status: "IN_PROGRESS",
                },
              },
            };
          }
          return step;
        });
        return newSteps;
      });
      setCurrentStepIndex((prev) => prev + 1);
      // Update ETA
      setEta((prev) => {
        const remaining = steps.length - currentStepIndex - 1;
        return `${remaining * 8} mins ${Math.floor(Math.random() * 60)} Seconds`;
      });
    }, 2000); // Simulate 2 seconds per step

    return () => clearTimeout(timer);
  }, [currentStepIndex, steps.length]);

  const handleNext = () => {
    closeDrawer();
  };

  return (
    <BudForm
      data={{}}
      nextText="Next"
      onNext={handleNext}
      disableNext={!isCompleted}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <div className="flex flex-col justify-start items-center w-full">
            <div className="w-full p-[1.35rem] pb-[1.9rem] border-b border-[#1F1F1F]">
              <Text_14_400_EEEEEE>Creating Tool</Text_14_400_EEEEEE>
              <Text_12_400_757575 className="mt-[.6rem] leading-[150%]">
                Your tool is being created, it may take a few moments to finish
              </Text_12_400_757575>
            </div>
            <ProgressWithBudList events={steps} />
            <StatusEstimatedTime estimatedTime={eta} />
            <StatusEvents events={steps} />
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}

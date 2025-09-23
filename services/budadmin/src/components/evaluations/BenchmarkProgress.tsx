import React from "react";
import { Progress, Image } from "antd";
import {
  Text_16_600_FFFFFF,
  Text_12_400_B3B3B3,
  Text_14_400_EEEEEE,
  Text_12_400_EEEEEE,
  Text_12_600_EEEEEE,
  Text_10_400_B3B3B3,
} from "@/components/ui/text";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import ProjectTags from "src/flows/components/ProjectTags";
import { capitalize } from "@/lib/utils";
import { endpointStatusMapping } from "@/lib/colorMapping";

interface BenchmarkProgressProps {
  benchmark: {
    id: string;
    title: string;
    objective: string;
    currentEvaluation: string;
    currentModel: string;
    eta: string;
    processingRate: number;
    averageScore: number;
    status: string;
    progress: number;
    progressCompleted?: number;
    progressTotal?: number;
    canPause?: boolean;
    pauseUrl?: string;
  };
}

const BenchmarkProgress: React.FC<BenchmarkProgressProps> = ({ benchmark }) => {
  return (
    <div className="bg-[#101010] rounded-lg px-[1.5rem] py-[1.2rem] border border-[#1F1F1F]">
      <div className="flex justify-between items-start mb-[0.85rem]">
        <Text_14_400_EEEEEE className="">{benchmark.title}</Text_14_400_EEEEEE>
        {benchmark.status === "Running" && benchmark.canPause && (
          <PrimaryButton
            classNames="!px-[.55] !py-1 !text-xs mt-[.3rem]"
            onClick={() => {
              // TODO: Implement pause functionality using pauseUrl
              console.log("Pausing run:", benchmark.pauseUrl);
            }}
          >
            || Pause
          </PrimaryButton>
        )}
      </div>
      <div className="">
        <div className="flex items-center justify-start gap-x-[.3rem] mb-[0.7rem]">
          <Text_12_600_EEEEEE className="leading-[140%]">
            Objective:
          </Text_12_600_EEEEEE>
          <Text_12_400_EEEEEE className="leading-[140%]">
            {benchmark.objective}
          </Text_12_400_EEEEEE>
        </div>

        {/* Progress Bar */}
        <div className="mb-4">
          <Progress
            percent={benchmark.progress}
            strokeColor="#965CDE"
            trailColor="#1F1F1F"
            showInfo={false}
            size={{ height: 3 }}
          />
          <div className="flex items-center justify-start gap-x-[.2rem] mt-1">
            <div className="flex items-center justify-center w-[.75rem] h-[.75rem]">
              <Image
                preview={false}
                className="w-[.75rem] h-[.75rem]"
                src="/icons/loader.gif"
                alt="Logo"
              />
            </div>
            <Text_10_400_B3B3B3 className="leading-[140%]">
              {benchmark.progress}% {benchmark.progressCompleted ?? '013'}/{benchmark.progressTotal ?? '024'} completed
            </Text_10_400_B3B3B3>
          </div>
        </div>
      </div>

      {/* Details Grid */}
      <div className="grid grid-cols-2 gap-8 mt-[1.8rem]">
        <div className="space-y-[1.25rem]">
          <div className="flex justify-start">
            <div className="flex items-center justify-start gap-x-[.3rem] min-w-[36%]">
              <div className="flex items-center justify-center w-[.75rem] h-[.75rem]">
                <Image
                  preview={false}
                  className="w-[.75rem] h-[.75rem]"
                  src="/images/evaluations/icons/progress/lock.svg"
                  alt="Logo"
                />
              </div>
              <Text_12_400_B3B3B3>Current Evaluation</Text_12_400_B3B3B3>
            </div>
            <Text_12_400_EEEEEE>
              {benchmark.currentEvaluation}
            </Text_12_400_EEEEEE>
          </div>
          <div className="flex justify-start">
            <div className="flex items-center justify-start gap-x-[.3rem] min-w-[36%]">
              <div className="flex items-center justify-center w-[.75rem] h-[.75rem]">
                <Image
                  preview={false}
                  className="w-[.75rem] h-[.75rem]"
                  src="/images/evaluations/icons/progress/model.svg"
                  alt="Logo"
                />
              </div>
              <Text_12_400_B3B3B3>Current Model</Text_12_400_B3B3B3>
            </div>
            <Text_12_400_EEEEEE>{benchmark.currentModel}</Text_12_400_EEEEEE>
          </div>
          <div className="flex justify-start">
            <div className="flex items-center justify-start gap-x-[.3rem] min-w-[36%]">
              <div className="flex items-center justify-center w-[.75rem] h-[.75rem]">
                <Image
                  preview={false}
                  className="w-[.75rem] h-[.75rem]"
                  src="/images/evaluations/icons/progress/eta.svg"
                  alt="Logo"
                />
              </div>
              <Text_12_400_B3B3B3>ETA</Text_12_400_B3B3B3>
            </div>
            <Text_12_400_EEEEEE>{benchmark.eta}</Text_12_400_EEEEEE>
          </div>
        </div>

        <div className="space-y-[1.25rem]">
          <div className="flex justify-start">
            <div className="flex items-center justify-start gap-x-[.3rem] min-w-[36%]">
              <div className="flex items-center justify-center w-[.75rem] h-[.75rem]">
                <Image
                  preview={false}
                  className="w-[.75rem] h-[.75rem]"
                  src="/images/evaluations/icons/progress/processing.svg"
                  alt="Logo"
                />
              </div>
              <Text_12_400_B3B3B3>Processing Rate</Text_12_400_B3B3B3>
            </div>
            <Text_12_400_EEEEEE>
              {benchmark.processingRate} prompts/min
            </Text_12_400_EEEEEE>
          </div>
          <div className="flex justify-start">
            <div className="flex items-center justify-start gap-x-[.3rem] min-w-[36%]">
              <div className="flex items-center justify-center w-[.75rem] h-[.75rem]">
                <Image
                  preview={false}
                  className="w-[.75rem] h-[.75rem]"
                  src="/images/evaluations/icons/progress/average.svg"
                  alt="Logo"
                />
              </div>
              <Text_12_400_B3B3B3>Average Score</Text_12_400_B3B3B3>
            </div>
            <Text_12_400_EEEEEE>{benchmark.averageScore}%</Text_12_400_EEEEEE>
          </div>
          <div className="flex justify-start">
            <div className="flex items-center justify-start gap-x-[.3rem] min-w-[36%]">
              <div className="flex items-center justify-center w-[.75rem] h-[.75rem]">
                <Image
                  preview={false}
                  className="w-[.75rem] h-[.75rem]"
                  src="/images/evaluations/icons/progress/status.svg"
                  alt="Logo"
                />
              </div>
              <Text_12_400_B3B3B3>Status</Text_12_400_B3B3B3>
            </div>
            <div>
              <ProjectTags
                name={capitalize(benchmark.status)}
                color={endpointStatusMapping[capitalize(benchmark.status)]}
                textClass="text-[.75rem]"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default BenchmarkProgress;

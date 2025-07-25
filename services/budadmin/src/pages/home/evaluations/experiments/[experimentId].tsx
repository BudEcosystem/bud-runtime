"use client";
import React, { useEffect, useState } from "react";
import { useRouter } from "next/router";
import DashBoardLayout from "../../layout";
import { useEvaluations } from "src/hooks/useEvaluations";
import {
  Text_16_600_FFFFFF,
  Text_12_400_B3B3B3,
  Text_14_600_EEEEEE,
  Text_12_400_EEEEEE,
  Text_28_600_FFFFFF,
  Text_14_400_FFFFFF,
  Text_24_600_FFFFFF
} from "@/components/ui/text";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import MetricCard from "src/components/evaluations/MetricCard";
import CurrentMetricsTable from "src/components/evaluations/CurrentMetricsTable";
import BenchmarkProgress from "src/components/evaluations/BenchmarkProgress";
import RunsHistoryTable from "src/components/evaluations/RunsHistoryTable";
import { Image } from "antd";
import { CustomBreadcrumb } from "@/components/ui/bud/card/DrawerBreadCrumbNavigation";
import Tags from "src/flows/components/DrawerTags";
import { useDrawer } from "src/hooks/useDrawer";

interface ExperimentDetails {
  id: string;
  name: string;
  lastRun: string;
  createdBy: string;
  owner: string;
  metrics: {
    budgetUsed: number;
    budgetTotal: number;
    tokensProcessed: number;
    runtime: number;
    processingRate: number;
  };
  currentMetrics: Array<{
    evaluation: string;
    gpt4Score: number;
    claude3Score: number;
  }>;
  benchmarkProgress: Array<{
    id: string;
    title: string;
    objective: string;
    currentEvaluation: string;
    currentModel: string;
    eta: string;
    processingRate: number;
    averageScore: number;
    status: 'Running' | 'Completed';
    progress: number;
  }>;
  runsHistory: Array<{
    runId: string;
    model: string;
    status: 'Completed' | 'Failed' | 'Running';
    startedDate: string;
    duration: string;
    benchmarkScore: string;
  }>;
}

const sampletags = [
  { name: 'text', color: '#D1B854' },
  { name: 'image', color: '#D1B854' },
  { name: 'video', color: '#D1B854' },
  { name: 'actions', color: '#D1B854' },
  { name: 'embeddings', color: '#D1B854' },
  { name: 'text', color: '#D1B854' },
  { name: 'text', color: '#D1B854' },
  { name: 'text', color: '#D1B854' },
  { name: 'text', color: '#D1B854' },
  { name: 'text', color: '#D1B854' },
]

const ExperimentDetailsPage = () => {
  const { openDrawer } = useDrawer();
  const [isMounted, setIsMounted] = useState(false);
  const router = useRouter();
  const { experimentId } = router.query;
  const [experiment, setExperiment] = useState<ExperimentDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [showAllTags, setShowAllTags] = useState(false);

  // Mock data - replace with actual API calls
  useEffect(() => {
    if (experimentId) {
      setLoading(true);
      setIsMounted(true)
      // Simulate API call
      setTimeout(() => {
        const mockExperiment: ExperimentDetails = {
          id: experimentId as string,
          name: "Experiment 1",
          lastRun: "2024-01-15",
          createdBy: "user@example.com",
          owner: "Mark Louis",
          metrics: {
            budgetUsed: 45.20,
            budgetTotal: 100.00,
            tokensProcessed: 2100000,
            runtime: 135, // minutes
            processingRate: 47,
          },
          currentMetrics: [
            { evaluation: "GPT-4 Score", gpt4Score: 75, claude3Score: 75 },
            { evaluation: "name", gpt4Score: 75, claude3Score: 75 },
            { evaluation: "name", gpt4Score: 75, claude3Score: 75 },
            { evaluation: "name", gpt4Score: 75, claude3Score: 75 },
            { evaluation: "name", gpt4Score: 75, claude3Score: 75 },
            { evaluation: "name", gpt4Score: 75, claude3Score: 75 },
            { evaluation: "name", gpt4Score: 75, claude3Score: 75 },
            { evaluation: "name", gpt4Score: 75, claude3Score: 75 },
            { evaluation: "name", gpt4Score: 75, claude3Score: 75 },
          ],
          benchmarkProgress: [
            {
              id: "1",
              title: "Progress Overview of Run 1",
              objective: "Compare GPT-4 and Claude 3 performance across academic benchmarks",
              currentEvaluation: "TruthfulQA",
              currentModel: "GPT-4 Turbo",
              eta: "45 minutes remaining",
              processingRate: 47,
              averageScore: 78.5,
              status: "Running",
              progress: 65,
            },
            {
              id: "2",
              title: "Progress Overview of Run 2",
              objective: "Compare GPT-4 and Claude 3 performance across academic benchmarks",
              currentEvaluation: "TruthfulQA",
              currentModel: "GPT-4 Turbo",
              eta: "45 minutes remaining",
              processingRate: 47,
              averageScore: 78.5,
              status: "Running",
              progress: 65,
            },
          ],
          runsHistory: [
            {
              runId: "Run 3",
              model: "name",
              status: "Completed",
              startedDate: "Jan 13, 2024",
              duration: "1Hr 23Min",
              benchmarkScore: "Benchmark_Score",
            },
            {
              runId: "Run 4",
              model: "name",
              status: "Completed",
              startedDate: "Jan 13, 2024",
              duration: "1Hr 23Min",
              benchmarkScore: "Benchmark_Score",
            },
            {
              runId: "Run 5",
              model: "name",
              status: "Failed",
              startedDate: "Jan 13, 2024",
              duration: "1Hr 23Min",
              benchmarkScore: "Benchmark_Score",
            },
            {
              runId: "Run 6",
              model: "name",
              status: "Completed",
              startedDate: "Jan 13, 2024",
              duration: "1Hr 23Min",
              benchmarkScore: "Benchmark_Score",
            },
            {
              runId: "Run 7",
              model: "name",
              status: "Failed",
              startedDate: "Jan 13, 2024",
              duration: "1Hr 23Min",
              benchmarkScore: "Benchmark_Score",
            },
            {
              runId: "Run 8",
              model: "name",
              status: "Failed",
              startedDate: "Jan 13, 2024",
              duration: "1Hr 23Min",
              benchmarkScore: "Benchmark_Score",
            },
            {
              runId: "Run 9",
              model: "name",
              status: "Completed",
              startedDate: "Jan 13, 2024",
              duration: "1Hr 23Min",
              benchmarkScore: "Benchmark_Score",
            },
            {
              runId: "Run 10",
              model: "name",
              status: "Completed",
              startedDate: "Jan 13, 2024",
              duration: "1Hr 23Min",
              benchmarkScore: "Benchmark_Score",
            },
          ],
        };
        setExperiment(mockExperiment);
        setLoading(false);
      }, 10);
    }
  }, [experimentId]);

  const handleNewEvaluation = () => {
    // Navigate to new evaluation flow
    router.push("/home/evaluations?tab=experiments&action=new");
  };

  if (loading) {
    return (
      <DashBoardLayout>
        <div className="flex items-center justify-center h-64">
          <Text_14_600_EEEEEE>Loading experiment details...</Text_14_600_EEEEEE>
        </div>
      </DashBoardLayout>
    );
  }

  if (!experiment) {
    return (
      <DashBoardLayout>
        <div className="flex items-center justify-center h-64">
          <Text_14_600_EEEEEE>Experiment not found</Text_14_600_EEEEEE>
        </div>
      </DashBoardLayout>
    );
  }

  const goBack = () => {
    router.back();
  };

  // useEffect(() => {
  //   setIsMounted(true)
  // }, []);

  const ExperimentHeader = () => {
    return (
      <div className="flex justify-between items-center">
        {isMounted && (
          <div className="flex justify-start items-center">
            {/* <BackButton classNames="" onClick={goBack} /> */}
            <button
              className="mr-[1.25rem] flex items-center justify-center w-[1.125rem] h-[1.125rem] rounded-full border border-white/5 backdrop-blur-[34.4px] transition-opacity opacity-100 hover:bg-white/10"
              style={{ minWidth: 18, minHeight: 18 }}
              type="button"
              onClick={goBack}
            >
              <div className="flex justify-center h-[0.55rem] w-[auto]">
                <Image
                  preview={false}
                  className=""
                  style={{ width: "auto", height: "0.55rem" }}
                  src="/images/evaluations/icons/left.svg"
                  alt="Logo"
                />
              </div>
            </button>
            <CustomBreadcrumb
              urls={["/evaluations", `name`]}
              data={["experiments", `name`]} />
          </div>
        )}
      </div>
    );
  };

  return (
    <DashBoardLayout>
      <div className="temp-bg h-full w-full flex flex-col">
      {/* <div className="temp-bg h-full w-full flex flex-col"> */}
        {/* Header */}
        <div className="border-b-[1px] border-b-[#2c2654] px-[1.15rem] py-[1.05rem] flex-shrink-0">
          <ExperimentHeader />
        </div>
        <div className="w-full px-[3.6rem] flex-1 overflow-y-auto no-scrollbar">
          {/* Metrics Cards */}
          <div className="w-full pt-[1.8rem]">
            <div className="w-full flex justify-between items-center">
              <Text_28_600_FFFFFF>LiveMathBench</Text_28_600_FFFFFF>
              <PrimaryButton classNames="shadow-purple-glow" textClass="text-[0.8125rem]" onClick={() => openDrawer('run-evaluation')}>Run Evaluation</PrimaryButton>
            </div>
            <div className="flex flex-wrap justify-start items-center gap-[.45rem] mt-[0.8rem] max-w-[80%]">
              {(showAllTags ? sampletags : sampletags.slice(0, 5)).map((item, index) => (
                <Tags
                  key={index}
                  name={item.name}
                  color={item.color}
                  classNames={`${showAllTags && index >= 5 ? "animate-fadeIn" : ""} py-[.25rem]`}
                />
              ))}
              {sampletags.length > 5 && (
                <button
                  onClick={() => setShowAllTags(!showAllTags)}
                  className="px-3 py-1 text-[#EEEEEE] hover:text-[#FFFFFF] transition-colors duration-200 text-[.65rem] font-[400]"
                >
                  {showAllTags ? "Show less" : `+${sampletags.length - 5} more`}
                </button>
              )}
            </div>

          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mt-[3.1rem]">
            <MetricCard
              title="Budget Used / $100.00"
              value={`$${experiment.metrics.budgetUsed.toFixed(2)}`}
              subtitle={`/ $${experiment.metrics.budgetTotal.toFixed(2)}`}
              color="#965CDE"
            />
            <MetricCard
              title="Tokens Processed"
              value={`${(experiment.metrics.tokensProcessed / 1000000).toFixed(1)}M`}
              subtitle="tokens processed"
              color="#965CDE"
            />
            <MetricCard
              title="Runtime"
              value={`${Math.floor(experiment.metrics.runtime / 60)}h ${experiment.metrics.runtime % 60}m`}
              subtitle="total runtime"
              color="#965CDE"
            />
            <MetricCard
              title="Processing Rate"
              value={`${experiment.metrics.processingRate}/min`}
              subtitle="tokens per minute"
              color="#965CDE"
            />
          </div>

          {/* Current Metrics */}
          <div className="pt-[2.9rem]">
            <Text_24_600_FFFFFF className="mb-[.6rem]">Current Metrics</Text_24_600_FFFFFF>
            <Text_14_400_FFFFFF className="mb-[1rem] leading-[140%]">
              Current metrics description metrics description metrics description...
            </Text_14_400_FFFFFF>
            <CurrentMetricsTable data={experiment.currentMetrics} />
          </div>

          {/* Performance Benchmark Details */}
          <div className="pt-[2.9rem]">
            <Text_24_600_FFFFFF className="mb-[.6rem]">Performance Benchmark Details</Text_24_600_FFFFFF>
            <Text_14_400_FFFFFF className="mb-[1rem] leading-[140%]">
              Objective: Compare GPT-4 and Claude 3 performance across academic benchmarks
            </Text_14_400_FFFFFF>
            <div className="space-y-[1rem]">
              {experiment.benchmarkProgress.map((benchmark) => (
                <BenchmarkProgress key={benchmark.id} benchmark={benchmark} />
              ))}
            </div>
          </div>

          {/* Runs History */}
          <div className="pt-[2.9rem] pb-[3rem]">
            <Text_24_600_FFFFFF className="mb-[.6rem]">Runs History</Text_24_600_FFFFFF>
            <Text_14_400_FFFFFF className="mb-[1rem] leading-[140%]">
              Runs history description history description history description...
            </Text_14_400_FFFFFF>
            <RunsHistoryTable data={experiment.runsHistory} />
          </div>
        </div>
      </div>
    </DashBoardLayout>
  );
};

export default ExperimentDetailsPage;
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
    Text_24_600_FFFFFF,
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
import { capitalize } from "@/lib/utils";

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
        status: "Running" | "Completed";
        progress: number;
    }>;
    runsHistory: Array<{
        runId: string;
        model: string;
        status: "Completed" | "Failed" | "Running";
        startedDate: string;
        duration: string;
        benchmarkScore: string;
    }>;
}

const sampletags = [
    { name: "text", color: "#D1B854" },
    { name: "image", color: "#D1B854" },
    { name: "video", color: "#D1B854" },
    { name: "actions", color: "#D1B854" },
    { name: "embeddings", color: "#D1B854" },
    { name: "text", color: "#D1B854" },
    { name: "text", color: "#D1B854" },
    { name: "text", color: "#D1B854" },
    { name: "text", color: "#D1B854" },
    { name: "text", color: "#D1B854" },
];

const ExperimentDetailsPage = () => {
    const { openDrawer, openDrawerWithStep } = useDrawer();
    const [isMounted, setIsMounted] = useState(false);
    const router = useRouter();
    const { experimentId } = router.query;
    const [showAllTags, setShowAllTags] = useState(false);

    // Use the actual API data from useEvaluations hook
    const {
        loading,
        experimentDetails,
        experimentRuns,
        getExperimentDetails,
        getExperimentRuns,
        experimentSummary,
        getExperimentSummary,
    } = useEvaluations();

    // Use actual metrics from experimentDetails
    const experimentMetrics = experimentDetails
        ? {
              budgetUsed: experimentDetails.budget_used || 45.67,
              budgetTotal: experimentDetails.budget_total || 100.0,
              tokensProcessed: experimentDetails.tokens_processed || 2500000,
              runtime: experimentDetails.runtime || 185, // in minutes
              processingRate: experimentDetails.processing_rate || 13500,
          }
        : null;

    useEffect(() => {
        if (experimentId && typeof experimentId === "string") {
            setIsMounted(true);
            // Fetch all experiment data
            getExperimentDetails(experimentId);
            getExperimentRuns(experimentId);
            getExperimentSummary(experimentId)
        }
    }, [experimentId]);

    const refreshETA = (id) => {
        if (experimentId && typeof experimentId === "string") {
            getExperimentDetails(experimentId);
        }
    }

    if (loading) {
        return (
            <DashBoardLayout>
                <div className="flex items-center justify-center h-64">
                    <Text_14_600_EEEEEE>
                        Loading experiment details...
                    </Text_14_600_EEEEEE>
                </div>
            </DashBoardLayout>
        );
    }

    if (!experimentDetails) {
        return (
            <DashBoardLayout>
                <div className="flex items-center justify-center h-64">
                    <Text_14_600_EEEEEE>
                        Experiment not found
                    </Text_14_600_EEEEEE>
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
                            urls={[
                                "/evaluations",
                                experimentDetails?.name || "Experiment",
                            ]}
                            data={[
                                "Experiments",
                                experimentDetails?.name || "Experiment",
                            ]}
                        />
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
                            <Text_28_600_FFFFFF>
                                {experimentDetails?.name || "Loading..."}
                            </Text_28_600_FFFFFF>
                            <PrimaryButton
                                classNames="shadow-purple-glow"
                                textClass="text-[0.8125rem]"
                                onClick={() =>
                                    openDrawerWithStep("new-evaluation", {
                                        experimentId,
                                    })
                                }
                            >
                                Run Evaluation
                            </PrimaryButton>
                        </div>
                        <div className="flex flex-wrap justify-start items-center gap-[.45rem] mt-[0.8rem] max-w-[80%]">
                            {experimentDetails?.tags &&
                                (showAllTags
                                    ? experimentDetails.tags
                                    : experimentDetails.tags.slice(0, 5)
                                ).map((tag: string, index: number) => (
                                    <Tags
                                        key={index}
                                        name={tag}
                                        color="#D1B854"
                                        classNames={`${showAllTags && index >= 5 ? "animate-fadeIn" : ""} py-[.25rem]`}
                                    />
                                ))}
                            {experimentDetails?.tags &&
                                experimentDetails.tags.length > 5 && (
                                    <button
                                        onClick={() =>
                                            setShowAllTags(!showAllTags)
                                        }
                                        className="px-3 py-1 text-[#EEEEEE] hover:text-[#FFFFFF] transition-colors duration-200 text-[.65rem] font-[400]"
                                    >
                                        {showAllTags
                                            ? "Show less"
                                            : `+${experimentDetails.tags.length - 5} more`}
                                    </button>
                                )}
                        </div>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mt-[3.1rem]">
                        {experimentMetrics ? (
                            <>
                                {/* <MetricCard
                  title="Budget Used"
                  value={`$${experimentMetrics.budgetUsed?.toFixed(2) || "0.00"}`}
                  subtitle={`/ $${experimentMetrics.budgetTotal?.toFixed(2) || "100.00"}`}
                  color="#965CDE"
                /> */}
                                <MetricCard
                                    title="Tokens Processed"
                                    value={`${((experimentMetrics.tokensProcessed || 0) / 1000000).toFixed(1)}M`}
                                    subtitle="tokens processed"
                                    color="#965CDE"
                                />
                                <MetricCard
                                    title="Runs Count"
                                    value={`${(experimentSummary?.total_evaluations || 0)}`}
                                    subtitle="runs"
                                    color="#965CDE"
                                />
                                <MetricCard
                                    title="Runtime"
                                    value={`${Math.floor((experimentSummary?.total_duration_seconds || 0) / 3600)}h ${Math.floor(((experimentSummary?.total_duration_seconds || 0)  % 3600) / 60)}m`}
                                    subtitle="total runtime"
                                    color="#965CDE"
                                />
                                <MetricCard
                                    title="Processing Rate"
                                    value={`${experimentMetrics.processingRate || 0}/min`}
                                    subtitle="tokens per minute"
                                    color="#965CDE"
                                />
                            </>
                        ) : (
                            <>
                                <MetricCard
                                    title="Budget Used"
                                    value="$0.00"
                                    subtitle="/ $100.00"
                                    color="#965CDE"
                                />
                                <MetricCard
                                    title="Tokens Processed"
                                    value="0M"
                                    subtitle="tokens processed"
                                    color="#965CDE"
                                />
                                <MetricCard
                                    title="Runtime"
                                    value="0h 0m"
                                    subtitle="total runtime"
                                    color="#965CDE"
                                />
                                <MetricCard
                                    title="Processing Rate"
                                    value="0/min"
                                    subtitle="tokens per minute"
                                    color="#965CDE"
                                />
                            </>
                        )}
                    </div>

                    {/* Current Metrics */}
                    <div className="pt-[2.9rem]">
                        <Text_24_600_FFFFFF className="mb-[.6rem]">
                            Current Metrics
                        </Text_24_600_FFFFFF>
                        <Text_14_400_FFFFFF className="mb-[1rem] leading-[140%]">
                            Comparative performance scores across evaluation
                            categories for each model.
                        </Text_14_400_FFFFFF>
                        <CurrentMetricsTable
                            data={experimentDetails?.current_metrics || []}
                        />
                    </div>

                    {/* Performance Benchmark Details */}
                    <div className="pt-[2.9rem]">
                        <Text_24_600_FFFFFF className="mb-[.6rem]">
                            Performance Benchmark Details
                        </Text_24_600_FFFFFF>
                        <Text_14_400_FFFFFF className="mb-[1rem] leading-[140%]">
                            Objective: Compare GPT-4 and Claude 3 performance
                            across academic benchmarks
                        </Text_14_400_FFFFFF>
                        <div className="space-y-[1rem]">
                            {experimentDetails?.progress_overview?.length >
                            0 ? (
                                experimentDetails.progress_overview.map(
                                    (progressItem: any) => {
                                        // Map the API response to the BenchmarkProgress component's expected format
                                        const benchmark = {
                                            id: progressItem.run_id,
                                            title: progressItem.title,
                                            objective: progressItem.objective,
                                            currentEvaluation:
                                                progressItem.current_evaluation,
                                            currentModel:
                                                progressItem.current_model,
                                            eta: `${progressItem.eta_minutes} min`,
                                            processingRate:
                                                progressItem.processing_rate_per_min,
                                            averageScore:
                                                progressItem.average_score_pct,
                                            status: progressItem.status,
                                            progress:
                                                progressItem.progress.percent,
                                            progressCompleted:
                                                progressItem.progress.completed,
                                            progressTotal:
                                                progressItem.progress.total,
                                            canPause:
                                                progressItem.actions?.can_pause,
                                            pauseUrl:
                                                progressItem.actions?.pause_url,
                                        };
                                        return (
                                            <BenchmarkProgress
                                                key={benchmark.id}
                                                benchmark={benchmark}
                                                refreshETA={()=> refreshETA(benchmark.id)}
                                            />
                                        );
                                    },
                                )
                            ) : (
                                <Text_14_400_FFFFFF>
                                    No benchmark data available
                                </Text_14_400_FFFFFF>
                            )}
                        </div>
                    </div>

                    {/* Runs History */}
                    <div className="pt-[2.9rem] pb-[3rem]">
                        <Text_24_600_FFFFFF className="mb-[.6rem]">
                            Runs History
                        </Text_24_600_FFFFFF>
                        <Text_14_400_FFFFFF className="mb-[1rem] leading-[140%]">
                            Historical record of all evaluation runs with their
                            status, duration, and benchmark scores.
                        </Text_14_400_FFFFFF>
                        <RunsHistoryTable
                            data={
                                experimentRuns?.evaluations?.map(
                                    (evaluation: any) => ({
                                        runId: evaluation.evaluation_id,
                                        model: evaluation.model_name,
                                        traitName: evaluation.trait_name,
                                        status: evaluation.status,
                                        startedDate:
                                            new Date(
                                                evaluation.started_date,
                                            ).toLocaleDateString() +
                                            " " +
                                            new Date(
                                                evaluation.started_date,
                                            ).toLocaleTimeString(),
                                        duration: `${evaluation.duration_minutes}m`,
                                        benchmarkScore: `${evaluation.trait_score}`,
                                        runs: `${JSON.stringify(evaluation.runs)}`
                                    }),
                                ) || []
                            }
                        />
                    </div>
                </div>
            </div>
        </DashBoardLayout>
    );
};

export default ExperimentDetailsPage;

"use client";
import { useRouter } from "next/router";
import React, { useEffect, useState } from "react";
import {
  Text_11_400_808080,
  Text_12_400_757575,
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_12_600_EEEEEE,
  Text_13_400_757575,
  Text_14_400_757575,
  Text_14_400_EEEEEE,
  Text_15_600_EEEEEE,
  Text_16_400_757575,
  Text_16_400_EEEEEE,
  Text_19_600_EEEEEE,
  Text_20_400_EEEEEE,
  Text_24_400_EEEEEE,
  Text_26_400_EEEEEE,
} from "@/components/ui/text";
import { useDrawer } from "src/hooks/useDrawer";
import { Image } from "antd";
import Tags from "src/flows/components/DrawerTags";
import { CustomBreadcrumb } from "@/components/ui/bud/card/DrawerBreadCrumbNavigation";
import BackButton from "@/components/ui/bud/drawer/BackButton";
import { formatDate } from "src/utils/formatDate";
import { notification } from "antd";
import { useOverlay } from "src/context/overlayContext";
import { openWarning } from "@/components/warningMessage";
import useHandleRouteChange from "@/lib/useHandleRouteChange";
import { PermissionEnum, useUser } from "src/stores/useUser";
import { useCluster } from "src/hooks/useCluster";
import PageHeader from "@/components/ui/pageHeader";
import { millisecondsToSeconds, milliToSecUinit } from "@/lib/utils";
import DashBoardLayout from "../layout";
import { SharedWithProjectUsers } from "@/components/ui/bud/drawer/SharedWithUsers";
import { useModels } from "src/hooks/useModels";
import IconRender from "src/flows/components/BudIconRender";
import ModelTags from "src/flows/components/ModelTags";
import ClusterTags from "src/flows/components/ClusterTags";
import TagsList from "src/flows/components/TagsList";
import CardWithBgAndTag, {
  GeneralCardsProps,
} from "@/components/ui/CardWithBgAndTag";
import PerfomanceTable from "./components/PerfomanceTable";
import BarChart from "@/components/charts/barChart";
import NoChartData from "@/components/ui/noChartData";
import ScatterChart from "@/components/charts/scatterChart";
import LegendLineChart from "@/components/charts/lineChart/LegendLineChart";
import { useBenchmarks } from "src/hooks/useBenchmark";
import BenchmarkChart from "@/components/charts/benchmarkChart";

const costRequestDataSample = {
  data: ["1", "2", "3", "4"],
  categories: ["1", "2", "3", "4"],
  label1: "Api Calls",
  label2: "Projects",
  barColor: "#4077E6",
};

const ttftVsTokenSample = {
  data: [],
  categories: [],
  label1: "Mean TPOT in ms",
  label2: "Mean TTFT in ms",
  barColor: "#4077E6",
};
const accuracySampleData = {
  dimensions: [
    "product",
    "avg_ttft",
    "avg_tpot",
    "avg_latency",
    "avg_output_len",
    "p95_ttft",
    "p95_tpot",
    "p95_latency",
  ],
  source: [
    {
      product: "1",
      avg_ttft: 43.3,
      avg_tpot: 85.8,
      avg_latency: 93.7,
      avg_output_len: 36.7,
      p95_ttft: 36.7,
      p95_tpot: 36.7,
      p95_latency: 36.7,
    },
    {
      product: "2",
      avg_ttft: 43.3,
      avg_tpot: 85.8,
      avg_latency: 93.7,
      avg_output_len: 36.7,
      p95_ttft: 36.7,
      p95_tpot: 36.7,
      p95_latency: 36.7,
    },
  ],
};
const BenchmarkResult = () => {
  const [inputsizevsTTFTChart, setInputsizevsTTFTChart] = useState({
    categories: [],
    data: [],
    label1: "TTFT (ms)",
    label2: "Prompt Length",
    color: "#3F8EF7",
    smooth: false,
  });
  const [outputsizevsTTFTChart, setOutputsizevsTTFTChart] = useState({
    categories: [],
    data: [],
    label1: "TPOT (ms)",
    label2: "Prompt Length",
    color: "#3F8EF7",
    smooth: false,
  });
  const [outputsizevsLatencyChart, setOutputsizevsLatencyChart] = useState({
    categories: [],
    data: [],
    label1: "Latency (ms)",
    label2: "Prompt Length",
    color: "#3F8EF7",
    smooth: false,
  });
  const [costRequestData, setCostRequestData] = useState<any>(
    costRequestDataSample
  );
  const [ttftVsTokenData, setTtftVsTokenData] =
    useState<any>(ttftVsTokenSample);
  const [inputDistributonData, setInputDistributonData] =
    useState<any>(accuracySampleData);
  const [outputDistributonData, setOutputDistributonData] =
    useState<any>(accuracySampleData);
  const [showAll, setShowAll] = useState(false);
  const { hasProjectPermission, hasPermission } = useUser();
  const { setOverlayVisible } = useOverlay();
  const router = useRouter();

  const { benchmarkId } = router.query;
  const { openDrawer, openDrawerWithStep } = useDrawer();
  const { getClusterById } = useCluster();
  const { getModel } = useModels();
  const {
    getBenchmarkModelClusterDetails,
    modelClusterDetails,
    getBenchmarkResult,
    benchmarkResult,
    getBenchmarkAnalysisField1VsField2,
    benchmarkMetricsData,
    benchmarkAnalysisTtftVsTokenData,
    getTTFTvsTokens,

    getInputDistribution,
    inputDistribution,

    getOutputDistribution,
    outputDistribution,

    inputSizeVsTTFT,
    getInputSizeVsTTFT,

    outputSizeVsTPOT,
    getOutputSizeVsTPOT,

    outputSizeVsLatency,
    getOutputSizeVsLatency,

    selectedBenchmark,
  } = useBenchmarks();
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    if (!modelClusterDetails) {
      getBenchmarkModelClusterDetails(benchmarkId as string);
    }
  }, [benchmarkId, isMounted]);

  useEffect(() => {
    if (!benchmarkResult) {
      getBenchmarkResult(benchmarkId as string);
    }
  }, [benchmarkId, isMounted]);

  // inputSizeVsTTFT =======================================================
  useEffect(() => {
    prepareInputsizevsTTFT();
  }, [inputSizeVsTTFT]);

  const prepareInputsizevsTTFT = () => {
    if (!inputSizeVsTTFT) return;
    const sortedData = [...inputSizeVsTTFT].sort((a, b) => a.ttft - b.ttft);
    const categories = sortedData.map(({ prompt_len }) =>
      Number(prompt_len).toFixed(0)
    );
    const data = sortedData.map(({ ttft }) =>
      Number(ttft * 1000).toFixed(ttft * 1000 < 1 ? 2 : 0)
    );
    setInputsizevsTTFTChart({
      categories,
      data,
      label1: "",
      label2: "TTFT (ms)",
      color: "#3F8EF7",
      smooth: false,
    });
  };
  // inputSizeVsTTFT =======================================================

  // outputSizeVsTPOT =======================================================
  useEffect(() => {
    prepareOutputsizevsTPOT();
  }, [outputSizeVsTPOT]);
  useEffect(() => {
    console.log("outputsizevsTTFTChart", outputsizevsTTFTChart);
  }, [outputsizevsTTFTChart]);

  const prepareOutputsizevsTPOT = () => {
    if (!outputSizeVsTPOT) return;
    const sortedData = [...outputSizeVsTPOT].sort((a, b) => a.tpot - b.tpot);
    const categories = sortedData.map(({ output_len }) =>
      Number(output_len).toFixed(0)
    );
    const data = sortedData.map(({ tpot }) =>
      Number(tpot * 1000).toFixed(tpot * 1000 < 1 ? 2 : 0)
    );
    setOutputsizevsTTFTChart({
      categories,
      data,
      label1: "",
      label2: "TPOT (ms)",
      color: "#3F8EF7",
      smooth: false,
    });
  };
  // outputSizeVsTPOT =======================================================

  // outputSizeVsLatency =======================================================
  useEffect(() => {
    prepareOutputSizeVsLatency();
  }, [outputSizeVsLatency]);

  const prepareOutputSizeVsLatency = () => {
    if (!outputSizeVsLatency) return;
    const sortedData = [...outputSizeVsLatency].sort(
      (a, b) => a.latency - b.latency
    );
    const categories = sortedData.map(({ output_len }) =>
      Number(output_len).toFixed(0)
    );
    const data = sortedData.map(({ latency }) =>
      Number(latency * 1000).toFixed(latency * 1000 < 1 ? 2 : 0)
    );
    setOutputsizevsLatencyChart({
      categories,
      data,
      label1: "",
      label2: "Latency (ms)",
      color: "#3F8EF7",
      smooth: false,
    });
  };
  // outputSizeVsLatency =======================================================

  useEffect(() => {
    getTTFTvsTokens(benchmarkId as string);
    getInputSizeVsTTFT(benchmarkId as string);
    getOutputSizeVsTPOT(benchmarkId as string);
    getOutputSizeVsLatency(benchmarkId as string);
    if (selectedBenchmark?.eval_with == "dataset") {
      getInputDistribution({
        benchmark_id: benchmarkId as string,
      });
      getOutputDistribution({
        benchmark_id: benchmarkId as string,
      });
    }
  }, [benchmarkId]);

  useEffect(() => {
    // setTtftVsTokenData
    const chartData = benchmarkAnalysisTtftVsTokenData?.map(
      ({ ttft, tpot }) => [Number(ttft).toFixed(2), Number(tpot).toFixed(2)]
    );
    setTtftVsTokenData((prevState) => ({
      ...prevState,
      data: chartData,
    }));
  }, [benchmarkAnalysisTtftVsTokenData]);

  useHandleRouteChange(() => {
    notification.destroy();
  });

  const goBack = () => {
    router.back();
  };

  const GeneralCardData: GeneralCardsProps[] = [
    {
      name: "Successful requests",
      bg: "/images/benchmark/arrowBg.png",
      value: benchmarkResult?.successful_requests,
      ClassNames: "w-[47%] min-h-[150px] pt-[1.8rem] pb-[1.3rem]",
    },
    {
      name: "Benchmark duration",
      bg: "/images/benchmark/timeBg.png",
      value: `${benchmarkResult?.duration.toFixed(2)} s`,
      ClassNames: "w-auto flex-auto  min-h-[150px] pt-[1.8rem] pb-[1.3rem]",
    },
  ];

  const summaryValuesData: SummaryContent[] = [
    {
      title: "TTFT",
      tiles: [
        {
          value: `${millisecondsToSeconds(benchmarkResult?.mean_ttft_ms)}`,
          unit: `${milliToSecUinit(benchmarkResult?.mean_ttft_ms)}`,
          tagName: "Mean TTFT",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.median_ttft_ms)}`,
          unit: `${milliToSecUinit(benchmarkResult?.median_ttft_ms)}`,
          tagName: "Median TTFT",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.min_ttft_ms)}`,
          unit: `${milliToSecUinit(benchmarkResult?.min_ttft_ms)}`,
          tagName: "Min",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.max_ttft_ms)}`,
          unit: `${milliToSecUinit(benchmarkResult?.max_ttft_ms)}`,
          tagName: "Max",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.p25_ttft_ms)}`,
          unit: `requests/${milliToSecUinit(benchmarkResult?.p25_ttft_ms)}`,
          tagName: "25 Percentile",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.p75_ttft_ms)}`,
          unit: `requests/${milliToSecUinit(benchmarkResult?.p75_ttft_ms)}`,
          tagName: "75 Percentile",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.p95_ttft_ms)}`,
          unit: `requests/${milliToSecUinit(benchmarkResult?.p95_ttft_ms)}`,
          tagName: "95 Percentile",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.p99_ttft_ms)}`,
          unit: `requests/${milliToSecUinit(benchmarkResult?.p99_ttft_ms)}`,
          tagName: "99 Percentile",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.min_ttft_ms)}`,
          unit: `${milliToSecUinit(benchmarkResult?.min_ttft_ms)}`,
          tagName: "Min",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.max_ttft_ms)}`,
          unit: `${milliToSecUinit(benchmarkResult?.max_ttft_ms)}`,
          tagName: "Max",
        },
      ],
    },
    {
      title: "Throughput",
      tiles: [
        {
          value: `${millisecondsToSeconds(
            benchmarkResult?.request_throughput
          )}`,
          unit: `requests/${milliToSecUinit(
            benchmarkResult?.request_throughput
          )}`,
          tagName: "Request throughput",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.input_throughput)}`,
          unit: `tokens/${milliToSecUinit(benchmarkResult?.input_throughput)}`,
          tagName: "Input token throughput",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.output_throughput)}`,
          unit: `tokens/${milliToSecUinit(benchmarkResult?.output_throughput)}`,
          tagName: "Output token throughput",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.p25_throughput)}`,
          unit: `requests/${milliToSecUinit(benchmarkResult?.p25_throughput)}`,
          tagName: "25 Percentile",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.p75_throughput)}`,
          unit: `requests/${milliToSecUinit(benchmarkResult?.p75_throughput)}`,
          tagName: "75 Percentile",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.p95_throughput)}`,
          unit: `requests/${milliToSecUinit(benchmarkResult?.p95_throughput)}`,
          tagName: "95 Percentile",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.p99_throughput)}`,
          unit: `requests/${milliToSecUinit(benchmarkResult?.p99_throughput)}`,
          tagName: "99 Percentile",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.min_throughput)}`,
          unit: `requests/${milliToSecUinit(benchmarkResult?.min_throughput)}`,
          tagName: "Min",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.max_throughput)}`,
          unit: `requests/${milliToSecUinit(benchmarkResult?.max_throughput)}`,
          tagName: "Max",
        },
      ],
    },
  ];

  const summaryValuesDataTwo: SummaryContent[] = [
    {
      title: "TPOT",
      tiles: [
        {
          value: `${millisecondsToSeconds(benchmarkResult?.mean_tpot_ms)}`,
          unit: `${milliToSecUinit(benchmarkResult?.mean_tpot_ms)}`,
          tagName: "Mean TPOT",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.median_tpot_ms)}`,
          unit: `${milliToSecUinit(benchmarkResult?.median_tpot_ms)}`,
          tagName: "Median TPOT",
        },
      ],
    },
    // {
    //   title: 'Cache',
    //   tiles: [
    //     { value: '23', unit: '', tagName: 'Number of cache hit' },
    //     { value: '31.49', unit: 'tokens/s', tagName: 'Cache latency' },
    //   ]
    // },
    {
      title: "Tokens",
      tiles: [
        {
          value: `${benchmarkResult?.total_input_tokens}`,
          unit: "",
          tagName: "Total input tokens",
        },
        {
          value: `${benchmarkResult?.total_output_tokens}`,
          unit: "",
          tagName: "Total input tokens",
        },
      ],
    },
  ];

  const qaData = [
    {
      question: "Are the weights of the model truly open source?",
      description: "",
      answer: "YES",
    },
    {
      question:
        "Can I use it in production for my customers without any payments?",
      description: "",
      answer: "NO",
    },
    {
      question: "Are the weights of the model truly open source?",
      description: "",
      answer: "YES",
    },
  ];
  const HeaderContent = () => {
    return (
      <div className="flex justify-between items-center">
        {isMounted && (
          <div className="flex justify-start items-center">
            <BackButton onClick={goBack} />
            <CustomBreadcrumb
              urls={["/modelRepo", `/modelRepo/benchmarks-history`, ``]}
              data={[
                "Models",
                `Performance Benchmarks`,
                `${modelClusterDetails?.name}`,
              ]}
            />
          </div>
        )}
        <div className="flex items-center gap-2">
          {/* {selectedProject?.created_at && <Text_12_400_B3B3B3>{formatDate(selectedProject?.created_at)}</Text_12_400_B3B3B3>} */}
          {/* <SharedWithProjectUsers users={projectMembers} /> */}
          <>
            <button
              type="button"
              className="flex items-center "
              onClick={() => openDrawer("add-members")}
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width=".875rem"
                height=".875rem"
                viewBox="0 0 16 16"
                fill="none"
              >
                <path
                  fillRule="evenodd"
                  clipRule="evenodd"
                  d="M5.25446 8.68286C4.99393 9.26353 4.41073 9.66797 3.73307 9.66797C2.8126 9.66797 2.06641 8.92178 2.06641 8.0013C2.06641 7.08083 2.8126 6.33463 3.73307 6.33463C4.41192 6.33463 4.99597 6.74049 5.25583 7.32279L5.24709 7.32825L5.28125 7.38291C5.35769 7.57412 5.39974 7.7828 5.39974 8.0013C5.39974 8.22402 5.35606 8.43653 5.27679 8.63074L5.24709 8.67825L5.25446 8.68286ZM6.10761 9.21608C5.66574 10.0781 4.7683 10.668 3.73307 10.668C2.26031 10.668 1.06641 9.47406 1.06641 8.0013C1.06641 6.52854 2.26031 5.33463 3.73307 5.33463C4.76948 5.33463 5.6678 5.92588 6.10913 6.78948L9.72226 4.53127C9.64383 4.28001 9.60156 4.01278 9.60156 3.73568C9.60156 2.26292 10.7955 1.06901 12.2682 1.06901C13.741 1.06901 14.9349 2.26292 14.9349 3.73568C14.9349 5.20844 13.741 6.40234 12.2682 6.40234C11.3955 6.40234 10.6207 5.98313 10.1343 5.33509L6.38071 7.68106C6.39327 7.78606 6.39974 7.89292 6.39974 8.0013C6.39974 8.11093 6.39312 8.21901 6.38027 8.32517L10.1343 10.6714C10.6207 10.0234 11.3955 9.60417 12.2682 9.60417C13.741 9.60417 14.9349 10.7981 14.9349 12.2708C14.9349 13.7436 13.741 14.9375 12.2682 14.9375C10.7955 14.9375 9.60156 13.7436 9.60156 12.2708C9.60156 11.9937 9.64383 11.7265 9.72226 11.4752L6.10761 9.21608ZM12.2682 5.40234C13.1887 5.40234 13.9349 4.65615 13.9349 3.73568C13.9349 2.8152 13.1887 2.06901 12.2682 2.06901C11.3478 2.06901 10.6016 2.8152 10.6016 3.73568C10.6016 4.65615 11.3478 5.40234 12.2682 5.40234ZM13.9349 12.2708C13.9349 13.1913 13.1887 13.9375 12.2682 13.9375C11.3478 13.9375 10.6016 13.1913 10.6016 12.2708C10.6016 11.3504 11.3478 10.6042 12.2682 10.6042C13.1887 10.6042 13.9349 11.3504 13.9349 12.2708Z"
                  fill="#B3B3B3"
                />
              </svg>
            </button>
            <button
              type="button"
              className="flex items-center"
              onClick={async () => {
                triggerDeleteNotification();
                setOverlayVisible(true);
              }}
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width=".875rem"
                height=".875rem"
                viewBox="0 0 14 14"
                fill="none"
              >
                <path
                  fillRule="evenodd"
                  clipRule="evenodd"
                  d="M5.13327 0.898438C4.85713 0.898438 4.63327 1.1223 4.63327 1.39844C4.63327 1.67458 4.85713 1.89844 5.13327 1.89844H8.8666C9.14274 1.89844 9.3666 1.67458 9.3666 1.39844C9.3666 1.1223 9.14274 0.898438 8.8666 0.898438H5.13327ZM2.7666 3.2651C2.7666 2.98896 2.99046 2.7651 3.2666 2.7651H10.7333C11.0094 2.7651 11.2333 2.98896 11.2333 3.2651C11.2333 3.54125 11.0094 3.7651 10.7333 3.7651H10.2661C10.2664 3.77617 10.2666 3.78728 10.2666 3.79844V11.1318C10.2666 11.6841 9.81889 12.1318 9.2666 12.1318H4.73327C4.18098 12.1318 3.73327 11.6841 3.73327 11.1318V3.79844C3.73327 3.78728 3.73345 3.77617 3.73381 3.7651H3.2666C2.99046 3.7651 2.7666 3.54125 2.7666 3.2651ZM9.2666 3.79844L4.73327 3.79844V11.1318L9.2666 11.1318V3.79844Z"
                  fill="#B3B3B3"
                />
              </svg>
            </button>
          </>
        </div>
      </div>
    );
  };
  const triggerDeleteNotification = () => {
    let description =
      "The deployments are running and you will not be allowed to delete the benchmark. In order to delete the project, you will have to pause or delete all deployments in order to delete the benchmark.";
    // endPointsCount > 0 ? "The deployments are running and you will not be allowed to delete the project. In order to delete the project, you will have to pause or delete all deployments in order to delete the project." : "There are no running deployments, you can delete the project.";
    let title = "You’re not allowed to delete the benchmark";
    // let title = endPointsCount > 0 ? "You\’re not allowed to delete the Project" : "You\’re about to delete the Project"
    const updateNotificationMessage = openWarning({
      title: title, // Replace 'entityName' with the actual value
      description: description,
      // deleteDisabled: endPointsCount > 0,
      onDelete: () => {
        null;
      },
      onCancel: () => {
        setOverlayVisible(false);
      },
    });
  };
  const summaryTags = [
    { name: "Chat (QA)", color: "#D1B854" },
    { name: "RAG system", color: "#D1B854" },
    { name: "Batch processing", color: "#D1B854" },
  ];

  const summaryContent = [
    {
      icon: "/images/drawer/current.png",
      name: "Concurrent Request",
      value: "14",
    },
    { icon: "/images/drawer/time.png", name: "Sequence Length", value: "40" },
  ];

  const SummaryDataCards = ({
    icon,
    name,
    value,
  }: {
    icon: string;
    name: string;
    value: string | number;
  }) => {
    return (
      <div className="flex justify-start items-center mt-[1.95rem]">
        <div
          className="flex justify-start items-start mr-[.4rem]"
          style={{ width: ".75rem", height: ".75rem" }}
        >
          <Image
            preview={false}
            src={icon}
            alt="info"
            style={{ width: ".75rem", height: ".75rem" }}
          />
        </div>
        <Text_12_400_B3B3B3 className="mr-[2.2rem]">{name}</Text_12_400_B3B3B3>
        <Text_12_400_EEEEEE>{value}</Text_12_400_EEEEEE>
      </div>
    );
  };

  interface SummaryTile {
    value: string;
    unit: string;
    tagName: string;
  }

  interface SummaryContent {
    title: string;
    tiles: SummaryTile[];
  }

  interface SummaryValueCardsProps {
    title: string;
    tiles: SummaryTile[];
    tileClases?: string;
  }

  const SummaryValueCards: React.FC<SummaryValueCardsProps> = ({
    title,
    tiles,
    tileClases,
  }) => {
    return (
      <div className="border-[1px] border-[#1F1F1F] rounded-[0.53375rem] w-full px-[1.6rem] pt-[1.4rem] pb-[1.5rem] bg-[#101010]">
        <div>
          <Text_15_600_EEEEEE>{title}</Text_15_600_EEEEEE>
          <div className="h-[0.183125rem] bg-[#965CDE] w-[1.649375rem] mt-[.4rem]"></div>
        </div>
        <div className="flex justify-start items-top mt-[2.9rem] gap-x-[.6rem] gap-y-[2.8rem] w-full flex-wrap">
          {tiles.map((tile, index) => (
            <div
              key={index}
              className={`flex flex-col justify-start items-start gap-y-[.29rem] ${tileClases}`}
              style={{
                minWidth: "23.5%",
              }}
            >
              <div className="flex justify-start items-baseline gap-[.35rem]">
                <Text_20_400_EEEEEE>{tile.value}</Text_20_400_EEEEEE>
                <Text_16_400_EEEEEE>{tile.unit}</Text_16_400_EEEEEE>
              </div>
              <Tags
                name={tile.tagName}
                color="#479D5F"
                textClass="text-[0.8125rem]"
                classNames="px-[.35rem] py-[.18rem]"
              />
            </div>
          ))}
        </div>
      </div>
    );
  };

  const barAndDotChart = [
    {
      title: "Cost per Thousand Requests",
      description: "Description",
      value: "200",
      percentage: 2,
      chartContainer: <BarChart data={costRequestData} />, // Pass your chart data here
      chartData: costRequestData, // Pass your chart data here
      classNames: "",
    },
    {
      title: "TTFT vs Tokens In",
      description: "Description",
      value: "127K",
      percentage: "2",
      chartContainer: <ScatterChart data={ttftVsTokenData} />,
      chartData: ttftVsTokenData,
      classNames: "",
    },
  ];

  const BarAndDot = ({ data }: any) => {
    return (
      // <div className=" w-[49.1%] h-[380px]  py-[1.9rem] px-[1.65rem] border border-[#1F1F1F] rounded-md">
      <div className="cardBG w-[49.1%] h-[22rem]  py-[1.9rem] px-[1.65rem] border border-[#1F1F1F] rounded-md">
      {/* <div className="cardBG w-[49.1%] h-[25rem]  py-[1.9rem] px-[1.65rem] border border-[#1F1F1F] rounded-md"> */}
        {/* <div className="cardBG w-[49.1%] h-[23.75rem]  py-[1.9rem] px-[1.65rem] border border-[#1F1F1F] rounded-md"> */}
        <div className="flex justify-between align-center">
          <Text_19_600_EEEEEE>{data.title}</Text_19_600_EEEEEE>
        </div>
        <Text_13_400_757575 className="mt-[1.35rem]">
          {data.description}
        </Text_13_400_757575>
        {data?.chartData?.data?.length || data?.chartData?.source?.length ? (
          <>
            <div className="flex flex-col items-start	mt-[1.6rem] hidden">
              <Text_26_400_EEEEEE>{data.value}</Text_26_400_EEEEEE>
              <div
                className={`${
                  Number(data.percentage) >= 0
                    ? "text-[#479D5F] bg-[#122F1140]"
                    : "bg-[#861A1A33] text-[#EC7575]"
                } flex rounded-md items-center px-[.45rem] mb-[.1rem] h-[1.35rem] mt-[0.42rem]`}
              >
                <span className="font-[400] text-[0.8125rem] leading-[100%]">
                  Avg. {Number(data.percentage).toFixed(2)}%{" "}
                </span>
                {Number(1) >= 0 ? (
                  <Image
                    preview={false}
                    width={12}
                    src="/images/dashboard/greenArrow.png"
                    className="ml-[.2rem]"
                    alt=""
                  />
                ) : (
                  <Image
                    preview={false}
                    width={12}
                    src="/images/dashboard/redArrow.png"
                    className="ml-[.2rem]"
                    alt=""
                  />
                )}
              </div>
            </div>
            <div className="h-[11.5625rem] mt-[2rem]">{data.chartContainer}</div>
          </>
        ) : (
          <NoChartData
            textMessage="Once the data is available, we will populate a bar chart for you representing Number of API Calls"
            image="/images/dashboard/noData.png"
            classNamesInner="h-[7rem]"
            classNamesInnerTwo="h-[7rem]"
          ></NoChartData>
        )}
      </div>
    );
  };

  const legendLineCharts = [
    {
      title: "Input size vs TTFT",
      description: "Description",
      value: "200",
      percentage: 2,
      chartContainer: <LegendLineChart data={inputsizevsTTFTChart} />, // Pass your chart data here
      chartData: inputsizevsTTFTChart, // Pass your chart data here
      classNames: "",
    },
    {
      title: "Output size vs TPOT",
      description: "Description",
      value: "200",
      percentage: 2,
      chartContainer: <LegendLineChart data={outputsizevsTTFTChart} />, // Pass your chart data here
      chartData: outputsizevsTTFTChart, // Pass your chart data here
      classNames: "",
    },
    {
      title: "Output size vs End to end latency.",
      description: "Description",
      value: "200",
      percentage: 2,
      chartContainer: <LegendLineChart data={outputsizevsLatencyChart} />, // Pass your chart data here
      chartData: outputsizevsLatencyChart, // Pass your chart data here
      classNames: "",
    },
  ];
  const inputOutputCharts = [
    {
      title: "Input Token Distribution",
      description: "Description",
      value: "200",
      percentage: 2,
      chartContainer: <BenchmarkChart data={inputDistributonData} />, // Pass your chart data here
      chartData: inputDistributonData, // Pass your chart data here
      classNames: "",
    },
    {
      title: "Output Token Distribution",
      description: "Description",
      value: "200",
      percentage: 2,
      chartContainer: <BenchmarkChart data={outputDistributonData} />, // Pass your chart data here
      chartData: outputDistributonData, // Pass your chart data here
      classNames: "",
    },
  ];

  // const LegendLine = ({ data }: any) => {
  //   return (
  //     <div className="cardBG w-[49.1%] cardSetTwo h-[420px]  py-[1.9rem] px-[1.65rem] border border-[#1F1F1F] rounded-md flex flex-col items-start justify-between">
  //       <div>
  //         <div className="flex justify-between align-center">
  //           <Text_19_600_EEEEEE>{data.title}</Text_19_600_EEEEEE>
  //         </div>
  //         <Text_13_400_757575 className="mt-[.95rem]">{data.description}</Text_13_400_757575>
  //         {data.chartData.data.length && (
  //           <div className="flex flex-col items-start	mt-[1.6rem]">
  //             <Text_26_400_EEEEEE>{data.value}</Text_26_400_EEEEEE>
  //             <div className={`${Number(data.percentage) >= 0 ? 'text-[#479D5F] bg-[#122F1140]' : 'bg-[#861A1A33] text-[#EC7575]'} flex rounded-md items-center px-[.45rem] mb-[.1rem] h-[1.35rem] mt-[0.42rem]`}>
  //               <span className="font-[400] text-[0.8125rem] leading-[100%]">Avg. {Number(data.percentage).toFixed(2)}% </span>
  //               {Number(1) >= 0 ?
  //                 <Image
  //                   preview={false}
  //                   width={12}
  //                   src="/images/dashboard/greenArrow.png"
  //                   className="ml-[.2rem]"
  //                   alt=""
  //                 /> : <Image
  //                   preview={false}
  //                   width={12}
  //                   src="/images/dashboard/redArrow.png"
  //                   className="ml-[.2rem]"
  //                   alt=""
  //                 />}
  //             </div>
  //           </div>
  //         )}
  //       </div>
  //       <div className="h-[185px] w-full">
  //         {data.chartData.data.length ? (
  //           <>
  //             {data.chartContainer}
  //           </>
  //         ) : (
  //           <NoChartData
  //             textMessage="Once the data is available, we will populate a bar chart for you representing Number of API Calls"
  //             image="/images/dashboard/noData.png"
  //           ></NoChartData>
  //         )}
  //       </div>
  //     </div>
  //   );
  // };

  // useEffect(() => {
  //   openDrawerWithStep('Benchmarking-Progress')
  // }, []);

  const processChartData = (Data: any) => {
    const dimensions = [
      "product",
      "avg_ttft",
      "avg_tpot",
      "avg_latency",
      "avg_output_len",
      "p95_ttft",
      "p95_tpot",
      "p95_latency",
    ];

    const source =
      Data?.map((item: any) => ({
        product: String(item.bin_id),
        avg_ttft: item.avg_ttft ?? 0,
        avg_tpot: item.avg_tpot ?? 0,
        avg_latency: item.avg_latency ?? 0,
        avg_output_len: item.avg_output_len ?? 0,
        p95_ttft: item.p95_ttft ?? 0,
        p95_tpot: item.p95_tpot ?? 0,
        p95_latency: item.p95_latency ?? 0,
      })) || [];

    return { dimensions, source };
  };

  useEffect(() => {
    let data = processChartData(inputDistribution);
    if (data) {
      setInputDistributonData(data);
    }
  }, [inputDistribution]);

  useEffect(() => {
    let data = processChartData(outputDistribution);
    if (data) {
      setOutputDistributonData(data);
    }
  }, [outputDistribution]);

  useEffect(() => {
    setIsMounted(true);
  }, []);
  return (
    <DashBoardLayout>
      <div className="boardPageView ">
        <div className="boardPageTop pt-0 px-0 pb-[0]">
          <div className="px-[1.2rem] pt-[1.05rem] pb-[1.15rem] mb-[2.05rem] border-b-[1px] border-b-[#1F1F1F]">
            <HeaderContent />
          </div>
          <div className="px-[3.5rem] boardPageTop pt-[0]">
            <PageHeader
              headding="Performance Benchmarks"
              buttonLabel={"Benchmark History"}
              hClass="text-[1.625rem]"
              buttonAction={() => {
                openDrawer("model_benchmark");
                // reset();
              }}
            />
          </div>
        </div>
        <div className="projectDetailsDiv pt-[1rem]">
          {/* model cluster cards */}
          <div className="flex gap-[1rem]">
            <div
              className="flex items-center flex-col border border-[#1F1F1F] rounded-[.4rem] px-[1.4rem] py-[1.3rem] pb-[1.1rem] w-[50%] bg-[#101010] cursor-pointer  min-h-[12.125rem]"
              onClick={async (e) => {
                e.stopPropagation();
                const result = await getModel(modelClusterDetails?.model?.id);
                if (result) {
                  openDrawerWithStep("view-model-details");
                }
              }}
            >
              <div className="w-full">
                <div className="flex items-start justify-start w-full">
                  {modelClusterDetails ? (
                    <IconRender icon={modelClusterDetails?.model?.icon} />
                  ) : (
                    <div
                      className=" bg-[#1F1F1F] rounded-[.4rem]  flex items-center justify-center"
                      style={{ width: "1.75rem", height: "1.75rem" }}
                    >
                      <Image
                        preview={false}
                        src="/images/drawer/zephyr.png"
                        alt="info"
                        style={{ width: "1.125rem", height: "1.125rem" }}
                      />
                    </div>
                  )}
                  <div className="ml-[.75rem]">
                    <span className="block text-[0.875rem] font-[400] text-[#EEEEEE] leading-[.875rem]">
                      {modelClusterDetails
                        ? modelClusterDetails?.model?.name
                        : "InternLM 2.5"}
                    </span>
                    <Text_11_400_808080 className="mt-[.35rem]">
                      {formatDate(
                        modelClusterDetails?.model?.created_at || new Date()
                      )}
                    </Text_11_400_808080>
                  </div>
                </div>
                <div className="mt-[.6rem]">
                  <div className="flex items-center justify-start w-full">
                    <div className="flex items-center justify-start flex-wrap	gap-[.6rem]">
                      <ModelTags
                        hideEndPoints
                        maxTags={3}
                        model={modelClusterDetails?.model}
                        // showExternalLink showLicense
                      />
                    </div>
                  </div>
                </div>
                <Text_12_400_B3B3B3 className="mt-[1.15rem] leading-[1.05rem]">
                  {modelClusterDetails?.model?.description}
                </Text_12_400_B3B3B3>
              </div>
            </div>

            <div
              className="flex items-center  flex-col border  border-[#1F1F1F] rounded-[.4rem] px-[1.4rem] py-[1.3rem] w-[50%]  bg-[#101010] cursor-pointer min-h-[12.125rem]"
              onClick={async (e) => {
                e.stopPropagation();
                await getClusterById(modelClusterDetails?.cluster?.id);
                router.push(`/clusters/${modelClusterDetails?.cluster?.id}`);
              }}
            >
              <div className="flex items-start justify-start w-full">
                {modelClusterDetails ? (
                  <IconRender icon={modelClusterDetails?.model?.icon} />
                ) : (
                  <div
                    className=" bg-[#1F1F1F] rounded-[.4rem]  flex items-center justify-center"
                    style={{ width: "1.75rem", height: "1.75rem" }}
                  >
                    <Image
                      preview={false}
                      src="/images/drawer/zephyr.png"
                      alt="info"
                      style={{ width: "1.125rem", height: "1.125rem" }}
                    />
                  </div>
                )}

                <div className="ml-[.75rem]">
                  <span className="block text-[0.875rem] font-[400] text-[#EEEEEE] leading-[.875rem]">
                    {modelClusterDetails
                      ? modelClusterDetails?.cluster?.name
                      : "Cluster Name"}
                  </span>
                  <Text_11_400_808080 className="mt-[.35rem]">
                    {formatDate(
                      modelClusterDetails?.cluster?.created_at || new Date()
                    )}
                  </Text_11_400_808080>
                </div>
              </div>
              <div className="mt-[.5rem] self-start">
                <div className="flex items-center justify-start w-full">
                  <div>
                    <div className="flex items-center justify-start flex-wrap	gap-[.6rem]">
                      <ClusterTags
                        hideEndPoints
                        cluster={
                          modelClusterDetails?.cluster || {
                            cpu_count: 1,
                            gpu_count: 1,
                            hpu_count: 1,
                          }
                        }
                      />
                    </div>
                  </div>
                </div>
              </div>
              <div className="flex flex-grow items-center justify-between mt-[0]" />
              <div className="text-[#B3B3B3] flex flex-col items-start justify-start gap-[.5rem] mt-4 w-full text-[.75rem]">
                <Text_12_400_EEEEEE className="mb-[.1rem]">
                  Resource Availability
                </Text_12_400_EEEEEE>
                <div className="flex items-center justify-start gap-[.45rem]">
                  <TagsList
                    data={[
                      {
                        name: `${
                          modelClusterDetails?.cluster?.available_nodes || 0
                        } Available Nodes`,
                        color: "#EEEEEE",
                      },
                      {
                        name: `${
                          modelClusterDetails?.cluster?.total_nodes || 0
                        } Total Nodes`,
                        color: "#EEEEEE",
                      },
                    ]}
                  />
                </div>
              </div>
            </div>
          </div>
          {/* model cluster cards============== */}
          {/* Analysis Summary */}
          {/* <div className="flex items-start flex-col border border-[#1F1F1F] rounded-[.4rem] px-[1.4rem] py-[1.3rem] w-[100%]  bg-[#101010] min-h-[12.125rem]"> */}
          <div className="flex items-start flex-col border border-[#1F1F1F] rounded-[.4rem] px-[1.4rem] py-[1.3rem] pb-[.8rem] w-[100%] bg-[#101010] min-h-[12.125rem] mt-[1.45rem]">
            <div>
              <Text_20_400_EEEEEE>Analysis Summary</Text_20_400_EEEEEE>
              <Text_14_400_757575 className="mt-[.4rem]">
                Description
              </Text_14_400_757575>
            </div>
            <div className="flex justify-start items-center gap-[5.05rem]">
              {summaryContent.map((item, index) => (
                <SummaryDataCards {...item} key={index}></SummaryDataCards>
              ))}
            </div>
            <div className="mt-[1.55rem]">
              <Text_14_400_EEEEEE>Ideal Use Cases</Text_14_400_EEEEEE>
              <Text_12_400_757575 className="mt-[.3rem]">
                Following are some of the use cases this model has been used for
              </Text_12_400_757575>
              <div className="flex justify-start items-center gap-[.65rem] mt-[.75rem]">
                {summaryTags.map((item, index) => (
                  <Tags
                    color={item.color}
                    name={item.name}
                    key={index}
                    textClass="text-[.75rem]"
                  ></Tags>
                ))}
              </div>
            </div>
            <div className="mt-[1.85rem]">
              {qaData.map((item, index) => (
                <div
                  key={index}
                  className={`flex flex-col justify-end items-end px-[0.9rem] py-[.52rem] mb-[.75rem] rounded-[8px] gap-[.5rem] ${
                    showAll ? "bg-[#FFFFFF08]" : "bg-[#161616]"
                  }`}
                >
                  <div
                    key={index}
                    className="flex justify-between items-center gap-[.5rem] w-full"
                  >
                    <div className="mt-[.3rem] w-[2rem]">
                      <Image
                        preview={false}
                        className=""
                        src={
                          item.answer == "YES"
                            ? "/images/drawer/greenTick.png"
                            : "/images/drawer/redCross.png"
                        }
                        alt="Logo"
                        style={{ width: "1.5rem" }}
                      />
                    </div>
                    <div className="flex flex-auto justify-between items-center gap-[.8rem]">
                      <Text_12_600_EEEEEE className="!leading-[1.05rem]">
                        {item.question}
                      </Text_12_600_EEEEEE>
                      {/* {showAll && (
                      <div className="flex justify-end items-start"
                        onClick={() => setOpenDetail((prev) => (prev === index ? null : index))}
                      >
                        <div className="w-[0.9375rem] h-[0.9375rem] "
                        >
                          <Image
                            preview={false}
                            width={15}
                            src="/images/drawer/ChevronUp.png"
                            alt="Logo"
                            style={{
                              transform: expandAll || openDetail === index ? 'rotate(0deg)' : 'rotate(180deg)',
                              transition: 'transform 0.3s ease',
                            }}
                          />
                        </div>
                      </div>
                    )} */}
                    </div>
                  </div>
                  {/* <div
                  className={`overflow-hidden transition-all duration-300 ease-in-out ${expandAll || openDetail === index
                    ? 'max-h-[500px] opacity-100 overflow-y-auto'
                    : 'max-h-0 opacity-0'
                    }`}
                >
                  <div className="flex justify-start items-center gap-[.5rem]">
                    <div className="mt-[.3rem] w-[2rem]">
                      <div className="w-[1.9rem]"></div>
                    </div>
                    <div className="text-left flex flex-auto max-w-[90%]">
                      <Text_12_400_B3B3B3 className="leading-[1.05rem]">{item.description}</Text_12_400_B3B3B3>
                    </div>
                  </div>
                </div> */}
                </div>
              ))}
            </div>
          </div>
          {/* Analysis Summary============== */}
          {/* Summary cards */}
          <div className="flex justify-between items-start gap-[.8rem] w-full mt-[1.5rem]">
            <div className="w-[63.3%]">
              <div className="flex justify-between items-start gap-[.8rem]">
                {GeneralCardData?.map((item, index) => (
                  <CardWithBgAndTag
                    key={index}
                    {...item}
                    valueClassNames="pt-[2.9rem]"
                  />
                ))}
              </div>
              <div className="mt-[.75rem] flex flex-col justify-start items-start gap-y-[.8rem]">
                {summaryValuesData.map((item, index) => (
                  <SummaryValueCards
                    key={index}
                    title={item.title}
                    tiles={item.tiles}
                  />
                ))}
              </div>
            </div>
            <div className="flex flex-col justify-start items-start gap-y-[.8rem] flex-auto">
              {summaryValuesDataTwo.map((item, index) => (
                <SummaryValueCards
                  key={index}
                  title={item.title}
                  tiles={item.tiles}
                  tileClases="w-[44%]"
                />
              ))}
            </div>
          </div>
          {/* Summary cards============== */}
          <div className="hR my-[1.5rem]"></div>
          {/* perfomance table */}
          <div>
            <PerfomanceTable />
          </div>
          {/* perfomance table============== */}
          <div className="hR mt-[1.5rem] mb-[1.1rem]"></div>
          {/* Benchmark analysis */}
          <div>
            <div className="">
              <Text_20_400_EEEEEE>Benchmark Analysis</Text_20_400_EEEEEE>
              <Text_16_400_757575 className="pt-[.15rem]">
                Description
              </Text_16_400_757575>
            </div>
            <div className="flex justify-between items-start flex-wrap pt-[1.25rem] pb-[2rem] gap-y-[1.1rem]">
              {barAndDotChart.map((item, index) => (
                <BarAndDot key={index} data={item} />
              ))}
              {legendLineCharts.map((item, index) => (
                <BarAndDot key={index} data={item} />
              ))}
              {selectedBenchmark?.eval_with == "dataset" &&
                inputOutputCharts.map((item, index) => (
                  <BarAndDot key={index} data={item} />
                ))}
            </div>
          </div>
          {/* Benchmark analysis============== */}
        </div>
      </div>
    </DashBoardLayout>
  );
};

export default BenchmarkResult;

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
import { millisecondsToSeconds, milliToSecUinit } from "@/lib/utils";
import DashBoardLayout from "../layout";
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
    costRequestDataSample,
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
      Number(prompt_len).toFixed(0),
    );
    const data = sortedData.map(({ ttft }) =>
      Number(ttft * 1000).toFixed(ttft * 1000 < 1 ? 2 : 0),
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
      Number(output_len).toFixed(0),
    );
    const data = sortedData.map(({ tpot }) =>
      Number(tpot * 1000).toFixed(tpot * 1000 < 1 ? 2 : 0),
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
      (a, b) => a.latency - b.latency,
    );
    const categories = sortedData.map(({ output_len }) =>
      Number(output_len).toFixed(0),
    );
    const data = sortedData.map(({ latency }) =>
      Number(latency * 1000).toFixed(latency * 1000 < 1 ? 2 : 0),
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
      ({ ttft, tpot }) => [Number(ttft).toFixed(2), Number(tpot).toFixed(2)],
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
      value: `${benchmarkResult?.duration?.toFixed(2) || "-"} s`,
      ClassNames: "w-auto flex-auto min-h-[150px] pt-[1.8rem] pb-[1.3rem]",
    },
  ];

  const summaryValuesData: SummaryContent[] = [
    {
      title: "Time to First Token",
      tiles: [
        {
          value: `${millisecondsToSeconds(benchmarkResult?.min_ttft_ms)}`,
          unit: `${milliToSecUinit(benchmarkResult?.min_ttft_ms)}`,
          tagName: "Min",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.p25_ttft_ms)}`,
          unit: `${milliToSecUinit(benchmarkResult?.p25_ttft_ms)}`,
          tagName: "P25",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.mean_ttft_ms)}`,
          unit: `${milliToSecUinit(benchmarkResult?.mean_ttft_ms)}`,
          tagName: "Mean",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.p95_ttft_ms)}`,
          unit: `${milliToSecUinit(benchmarkResult?.p95_ttft_ms)}`,
          tagName: "P95",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.p99_ttft_ms)}`,
          unit: `${milliToSecUinit(benchmarkResult?.p99_ttft_ms)}`,
          tagName: "P99",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.max_ttft_ms)}`,
          unit: `${milliToSecUinit(benchmarkResult?.max_ttft_ms)}`,
          tagName: "Max",
        },
      ],
    },
    {
      title: "Throughput Per User",
      tiles: [
        {
          value: `${benchmarkResult?.min_output_throughput_per_user?.toFixed(2) || "-"}`,
          unit: `tok/s`,
          tagName: "Min",
        },
        {
          value: `${benchmarkResult?.p25_output_throughput_per_user?.toFixed(2) || "-"}`,
          unit: `tok/s`,
          tagName: "P25",
        },
        {
          value: `${benchmarkResult?.mean_output_throughput_per_user?.toFixed(2) || "-"}`,
          unit: `tok/s`,
          tagName: "Mean",
        },
        {
          value: `${benchmarkResult?.p95_output_throughput_per_user?.toFixed(2) || "-"}`,
          unit: `tok/s`,
          tagName: "P95",
        },
        {
          value: `${benchmarkResult?.p99_output_throughput_per_user?.toFixed(2) || "-"}`,
          unit: `tok/s`,
          tagName: "P99",
        },
        {
          value: `${benchmarkResult?.max_output_throughput_per_user?.toFixed(2) || "-"}`,
          unit: `tok/s`,
          tagName: "Max",
        },
      ],
    },
    {
      title: "Inter-Token Latency",
      tiles: [
        {
          value: `${millisecondsToSeconds(benchmarkResult?.min_itl_ms)}`,
          unit: `${milliToSecUinit(benchmarkResult?.min_itl_ms)}`,
          tagName: "Min",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.p25_itl_ms)}`,
          unit: `${milliToSecUinit(benchmarkResult?.p25_itl_ms)}`,
          tagName: "P25",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.mean_itl_ms)}`,
          unit: `${milliToSecUinit(benchmarkResult?.mean_itl_ms)}`,
          tagName: "Mean",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.p95_itl_ms)}`,
          unit: `${milliToSecUinit(benchmarkResult?.p95_itl_ms)}`,
          tagName: "P95",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.p99_itl_ms)}`,
          unit: `${milliToSecUinit(benchmarkResult?.p99_itl_ms)}`,
          tagName: "P99",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.max_itl_ms)}`,
          unit: `${milliToSecUinit(benchmarkResult?.max_itl_ms)}`,
          tagName: "Max",
        },
      ],
    },
  ];

  const summaryValuesDataTwo: SummaryContent[] = [
    {
      title: "Tokens",
      tiles: [
        {
          value: `${benchmarkResult?.total_input_tokens || "-"}`,
          unit: "",
          tagName: "Total input tokens",
        },
        {
          value: `${benchmarkResult?.total_output_tokens || "-"}`,
          unit: "",
          tagName: "Total output tokens",
        },
      ],
    },
    {
      title: "Throughput",
      tiles: [
        {
          value: `${benchmarkResult?.request_throughput?.toFixed(2) || "-"}`,
          unit: "req/s",
          tagName: "Request throughput",
        },
        {
          value: `${benchmarkResult?.input_throughput?.toFixed(2) || "-"}`,
          unit: "tok/s",
          tagName: "Input throughput",
        },
        {
          value: `${benchmarkResult?.output_throughput?.toFixed(2) || "-"}`,
          unit: "tok/s",
          tagName: "Output throughput",
        },
      ],
    },
    {
      title: "E2E Latency",
      tiles: [
        {
          value: `${millisecondsToSeconds(benchmarkResult?.min_e2el_ms)}`,
          unit: `${milliToSecUinit(benchmarkResult?.min_e2el_ms)}`,
          tagName: "Min",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.p25_e2el_ms)}`,
          unit: `${milliToSecUinit(benchmarkResult?.p25_e2el_ms)}`,
          tagName: "P25",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.mean_e2el_ms)}`,
          unit: `${milliToSecUinit(benchmarkResult?.mean_e2el_ms)}`,
          tagName: "Mean",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.p95_e2el_ms)}`,
          unit: `${milliToSecUinit(benchmarkResult?.p95_e2el_ms)}`,
          tagName: "P95",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.p99_e2el_ms)}`,
          unit: `${milliToSecUinit(benchmarkResult?.p99_e2el_ms)}`,
          tagName: "P99",
        },
        {
          value: `${millisecondsToSeconds(benchmarkResult?.max_e2el_ms)}`,
          unit: `${milliToSecUinit(benchmarkResult?.max_e2el_ms)}`,
          tagName: "Max",
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
                `Benchmark Results`,
                `${modelClusterDetails?.name || ""}`,
              ]}
            />
          </div>
        )}
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
        <div className="flex justify-start items-top mt-[1.5rem] gap-x-[.6rem] gap-y-[2.8rem] w-full flex-wrap">
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
      title: "TTFT vs TPOT",
      description: "Correlation between Time to First Token and Time Per Output Token across requests",
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
        <Text_13_400_757575 className="mt-[1.35rem] leading-5">
          {data.description}
        </Text_13_400_757575>
        {data?.chartData?.data?.length || data?.chartData?.source?.length ? (
          <>
            <div className="flex flex-col items-start	mt-[1.6rem] hidden">
              <Text_26_400_EEEEEE>{data.value}</Text_26_400_EEEEEE>
              <div
                className={`${Number(data.percentage) >= 0
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
            <div className="h-[11.5625rem] mt-[2rem]">
              {data.chartContainer}
            </div>
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
      description: "How input prompt length affects Time to First Token",
      value: "200",
      percentage: 2,
      chartContainer: <LegendLineChart data={inputsizevsTTFTChart} />, // Pass your chart data here
      chartData: inputsizevsTTFTChart, // Pass your chart data here
      classNames: "",
    },
    {
      title: "Output size vs TPOT",
      description: "How output length affects Time Per Output Token",
      value: "200",
      percentage: 2,
      chartContainer: <LegendLineChart data={outputsizevsTTFTChart} />, // Pass your chart data here
      chartData: outputsizevsTTFTChart, // Pass your chart data here
      classNames: "",
    },
    {
      title: "Output size vs E2E Latency",
      description: "How output length affects total end-to-end latency",
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
      description:
        "Shows how TTFT and TPOT vary across different input lengths.",
      value: "200",
      percentage: 2,
      chartContainer: <BenchmarkChart data={inputDistributonData} />,
      chartData: inputDistributonData,
      classNames: "",
    },
    {
      title: "Output Token Distribution",
      description:
        "Shows how TTFT and TPOT vary across different output lengths.",
      value: "200",
      percentage: 2,
      chartContainer: <BenchmarkChart data={outputDistributonData} />,
      chartData: outputDistributonData,
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

  const processChartData = (Data: any, chartType: "input" | "output") => {
    // Input: avg_ttft, avg_tpot (no latency)
    // Output: avg_tpot, avg_latency (no ttft)
    const dimensions =
      chartType === "input"
        ? ["product", "avg_ttft", "avg_tpot"]
        : ["product", "avg_tpot", "avg_latency"];

    // Helper to round bin_range values to integers (e.g., "0-26.1" -> "0-26")
    const formatBinRange = (binRange: string | undefined, binId: number) => {
      if (!binRange) return String(binId);
      const parts = binRange.split("-");
      if (parts.length === 2) {
        return `${Math.round(parseFloat(parts[0]))}-${Math.round(parseFloat(parts[1]))}`;
      }
      return binRange;
    };

    const source =
      Data?.map((item: any) => {
        const baseData: any = {
          product: formatBinRange(item.bin_range, item.bin_id),
          avg_tpot: item.avg_tpot ?? 0,
        };
        if (chartType === "input") {
          baseData.avg_ttft = item.avg_ttft ?? 0;
        } else {
          baseData.avg_latency = item.avg_latency ?? 0;
        }
        return baseData;
      }) || [];

    return { dimensions, source };
  };

  useEffect(() => {
    let data = processChartData(inputDistribution, "input");
    if (data) {
      setInputDistributonData(data);
    }
  }, [inputDistribution]);

  useEffect(() => {
    let data = processChartData(outputDistribution, "output");
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
          <div className="px-[1.2rem] pt-[1.05rem] pb-[1.15rem] mb-[2.1rem] border-b-[1px] border-b-[#1F1F1F]">
            <HeaderContent />
          </div>
          <div className="px-[3.5rem]">
            {/* Name and Status Header */}
            <div className="flex items-center gap-3">
              <Text_24_400_EEEEEE className="font-semibold">
                {modelClusterDetails?.name || "Benchmark Result"}
              </Text_24_400_EEEEEE>
              {modelClusterDetails?.status && (
                <Tags
                  name={modelClusterDetails.status}
                  color={modelClusterDetails.status === "success" ? "#479D5F" : modelClusterDetails.status === "failed" ? "#EC7575" : "#D1B854"}
                  textClass="text-[.75rem] capitalize"
                />
              )}
            </div>
            {/* Tags */}
            {modelClusterDetails?.tags?.length > 0 && (
              <div className="flex items-center gap-2 mt-[.8rem] mb-[.8rem] flex-wrap">
                {modelClusterDetails.tags.map((tag: any, index: number) => (
                  <Tags
                    key={index}
                    name={tag?.name || tag}
                    color={tag?.color || "#757575"}
                    textClass="text-[.75rem]"
                  />
                ))}
              </div>
            )}
            {/* Description */}
            {modelClusterDetails?.description && (
              <Text_12_400_B3B3B3 className="mt-[.5rem] mb-[1rem] max-w-[850px]">
                {modelClusterDetails.description}
              </Text_12_400_B3B3B3>
            )}
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
                        modelClusterDetails?.model?.created_at || new Date(),
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
                      modelClusterDetails?.cluster?.created_at || new Date(),
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
                        name: `${modelClusterDetails?.cluster?.available_nodes || 0
                          } Available Nodes`,
                        color: "#EEEEEE",
                      },
                      {
                        name: `${modelClusterDetails?.cluster?.total_nodes || 0
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
          {/* Benchmark Configuration */}
          <div className="flex items-center flex-wrap gap-x-[1.5rem] gap-y-[1rem] mt-[1.5rem] p-[1rem] border border-[#1F1F1F] rounded-[.4rem] bg-[#101010]">
            <div className="flex flex-col">
              <Text_12_400_757575>Concurrency</Text_12_400_757575>
              <Text_14_400_EEEEEE className="mt-[.25rem]">
                {modelClusterDetails?.concurrency || "-"}
              </Text_14_400_EEEEEE>
            </div>
            <div className="w-[1px] h-[2.5rem] bg-[#1F1F1F]" />
            <div className="flex flex-col">
              <Text_12_400_757575>Input Tokens</Text_12_400_757575>
              <Text_14_400_EEEEEE className="mt-[.25rem]">
                {modelClusterDetails?.max_input_tokens || "-"}
              </Text_14_400_EEEEEE>
            </div>
            <div className="w-[1px] h-[2.5rem] bg-[#1F1F1F]" />
            <div className="flex flex-col">
              <Text_12_400_757575>Output Tokens</Text_12_400_757575>
              <Text_14_400_EEEEEE className="mt-[.25rem]">
                {modelClusterDetails?.max_output_tokens || "-"}
              </Text_14_400_EEEEEE>
            </div>
            <div className="w-[1px] h-[2.5rem] bg-[#1F1F1F]" />
            <div className="flex flex-col">
              <Text_12_400_757575>Eval Method</Text_12_400_757575>
              <Text_14_400_EEEEEE className="mt-[.25rem] capitalize">
                {modelClusterDetails?.eval_with || "-"}
              </Text_14_400_EEEEEE>
            </div>
            {modelClusterDetails?.eval_with === "dataset" && modelClusterDetails?.dataset_ids && (
              <>
                <div className="w-[1px] h-[2.5rem] bg-[#1F1F1F]" />
                <div className="flex flex-col">
                  <Text_12_400_757575>Datasets</Text_12_400_757575>
                  <Text_14_400_EEEEEE className="mt-[.25rem]">
                    {modelClusterDetails?.dataset_ids?.length || 0}
                  </Text_14_400_EEEEEE>
                </div>
              </>
            )}
            <div className="w-[1px] h-[2.5rem] bg-[#1F1F1F]" />
            <div className="flex flex-col">
              <Text_12_400_757575>Hardware Mode</Text_12_400_757575>
              <Text_14_400_EEEEEE className="mt-[.25rem] capitalize">
                {modelClusterDetails?.nodes?.[0]?.hardware_mode || "-"}
              </Text_14_400_EEEEEE>
            </div>
            {/* <div className="w-[1px] h-[2.5rem] bg-[#1F1F1F]" />
            <div className="flex flex-col">
              <Text_12_400_757575>TP Size</Text_12_400_757575>
              <Text_14_400_EEEEEE className="mt-[.25rem]">
                {modelClusterDetails?.nodes?.[0]?.tp_size ?? "-"}
              </Text_14_400_EEEEEE>
            </div>
            <div className="w-[1px] h-[2.5rem] bg-[#1F1F1F]" />
            <div className="flex flex-col">
              <Text_12_400_757575>PP Size</Text_12_400_757575>
              <Text_14_400_EEEEEE className="mt-[.25rem]">
                {modelClusterDetails?.nodes?.[0]?.pp_size ?? "-"}
              </Text_14_400_EEEEEE>
            </div>
            <div className="w-[1px] h-[2.5rem] bg-[#1F1F1F]" />
            <div className="flex flex-col">
              <Text_12_400_757575>Replicas</Text_12_400_757575>
              <Text_14_400_EEEEEE className="mt-[.25rem]">
                {modelClusterDetails?.nodes?.[0]?.replicas ?? "-"}
              </Text_14_400_EEEEEE>
            </div> */}
          </div>
          {/* Analysis Summary */}
          {/* <div className="flex items-start flex-col border border-[#1F1F1F] rounded-[.4rem] px-[1.4rem] py-[1.3rem] w-[100%]  bg-[#101010] min-h-[12.125rem]"> */}
          <div className="hidden items-start flex-col border border-[#1F1F1F] rounded-[.4rem] px-[1.4rem] py-[1.3rem] pb-[.8rem] w-[100%] bg-[#101010] min-h-[12.125rem] mt-[1.45rem]">
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
                  className={`flex flex-col justify-end items-end px-[0.9rem] py-[.52rem] mb-[.75rem] rounded-[8px] gap-[.5rem] ${showAll ? "bg-[#FFFFFF08]" : "bg-[#161616]"
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
                // tileClases="w-[30%]"
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

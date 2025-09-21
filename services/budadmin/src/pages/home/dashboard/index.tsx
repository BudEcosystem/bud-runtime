/* eslint-disable react/no-unescaped-entities */
"use client";
import React, { useEffect, useState } from "react";
import { Box } from "@radix-ui/themes";
import DashBoardLayout from "../layout";

import AccuracyChart from "../../../components/charts/accuracyChart";
import ApiCallsChart from "../../../components/charts/regularBarChart";
import {
  Text_12_500_FFFFFF,
  Text_13_400_tag,
  Text_15_600_EEEEEE,
  Text_19_600_EEEEEE,
  Text_38_400_EEEEEE,
} from "@/components/ui/text";
import { SelectInput } from "@/components/ui/input";
import { Flex, Image, Segmented, Carousel } from "antd";
import BarChart from "@/components/charts/barChart";
import NoChartData from "@/components/ui/noChartData";
import { useCharts } from "src/hooks/useCharts";
import { useLoader } from "src/context/appContext";
import DirectionArrowChart from "@/components/charts/directionArrowChart";
import TokenMetricsChart from "@/components/charts/barChart/customBarChart";

const onChange = () => {};

const requestOptions = [
  { label: "DAILY", value: "daily" },
  { label: "WEEKLY", value: "weekly" },
  { label: "MONTHLY", value: "monthly" },
];

const segmentOptions = ["LAST 24 HRS", "LAST 7 DAYS", "LAST 30 DAYS"];

type AccuracyChartData = {
  dimensions: string[];
  source: Record<string, string | number>[];
};

const accuracySampleData: AccuracyChartData = {
  dimensions: ["product", "MMLU", "GSM8", "Reasoning", "Factuality"],
  source: [
    {
      product: "Model 1",
      MMLU: 43.3,
      GSM8: 85.8,
      Reasoning: 93.7,
      Factuality: 36.7,
    },
    {
      product: "Model 2",
      MMLU: 83.1,
      GSM8: 73.4,
      Reasoning: 55.1,
      Factuality: 86.7,
    },
    {
      product: "Model 3",
      MMLU: 86.4,
      GSM8: 65.2,
      Reasoning: 82.5,
      Factuality: 16.7,
    },
    {
      product: "Model 4",
      MMLU: 72.4,
      GSM8: 53.9,
      Reasoning: 39.1,
      Factuality: 96.7,
    },
    {
      product: "Model 5",
      MMLU: 62.4,
      GSM8: 85,
      Reasoning: 39.1,
      Factuality: 36.7,
    },
  ],
};

const tokenMetricsSampleData = {
  dimensions: ["product", "Input Tokens", "Output Tokens"],
  source: [
    {
      product: "Model 1",
      "Input Tokens": 43.3,
      "Output Tokens": 85.8,
    },
    {
      product: "Model 2",
      "Input Tokens": 83.1,
      "Output Tokens": 73.4,
    },
  ],
};

const apiChartDataSample = {
  data: [],
  categories: [],
  label1: "Api Calls",
  label2: "Projects",
  barColor: "#4077E6",
};

const totalRequData = {
  categories: [
    "27-12-2024",
    "28-12-2024",
    "29-12-2024",
    "30-12-2024",
    "31-12-2024",
    "01-01-2025",
    "02-01-2025",
  ],
  data: [0, 38, 16, 88, 0, 70, 30],
};

const modelDataSample = {
  data: [70, 20, 10, 30, 23],
  categories: ["Model 1", "Model 2", "Model 3", "Model 4", "Model 5"],
  label1: "Usage",
  label2: "Models",
  barColor: "#9462D5",
};

const throughputDataSample = {
  data: [],
  categories: [],
  label1: "Throughput",
  label2: "models",
  barColor: "#E36E4F",
};

const latencyDataSample = {
  data: [25.628000000000004, 16.9025],
  categories: ["GSM8", "zephyr"],
  label1: "Latency",
  label2: "models",
  barColor: "#479D5F",
};

const Dashboard = () => {
  const {
    tokenMetrics,
    getRequestCounts,
    requestCounts,
    getThroughputAndLatencyData,
    modelCounts,
    throughputCount,
    latencyCount,
    dashboardCount,
    getDashboardCountData,
    getTotalRequests,
    totalRequests,
    getAccuracyChart,
    accuracyData,
  } = useCharts();
  const { showLoader, hideLoader } = useLoader();
  const [accuracyChartData, setAccuracyChartData] =
    useState<AccuracyChartData>(accuracySampleData);

  const [apiChartData, setApiChartData] = useState(apiChartDataSample);
  const [tokenMetricsData, setTokenMetricsData] = useState(
    tokenMetricsSampleData,
  );
  const [apiRequestInterval, setApiRequestInterval] = useState("weekly");

  const [modelChartData, setModelChartData] = useState(modelDataSample);
  const [modelInterval, setModelInterval] = useState("weekly");
  const [tokenMetricsInterval, setTokenMetricsInterval] = useState("weekly");

  const [throughputChartData, setThroughputChartData] =
    useState(throughputDataSample);
  const [throughputInterval, setThroughputInterval] = useState("weekly");

  const [latencyChartData, setLatencyChartData] = useState(latencyDataSample);
  const [latencyInterval, setLatencyInterval] = useState("weekly");
  const [isMounted, setIsMounted] = useState(false);

  const [extraChartDetails, setExtraChartDetails] = useState({
    apiCalls: {
      total_value: "",
      avg: "",
    },
    throughPut: {
      total_value: "",
      avg: "",
    },
    latency: {
      total_value: "",
      avg: "",
    },
    models: {
      total_value: "",
      avg: "",
    },
    token_metrics: {
      total_input_value: "",
      total_output_value: "",
      input_avg: "",
      output_avg: "",
    },
  });
  // For delta calculations, we need double the time period
  const numberOfDaysForDelta: Record<string, number> = {
    daily: 2, // Last 48 hours (to get delta for last 24 hours)
    weekly: 14, // Last 14 days (to get delta for last 7 days)
    monthly: 60, // Last 60 days (to get delta for last 30 days)
  };
  const [totalRequestChartData, setTotalRequestChartData] =
    useState(totalRequData);

  const load = async (
    type: string = "project",
    metrics: string = "overall",
    frequency: string = (type === "project"
      ? apiRequestInterval
      : modelInterval) || "weekly",
    fromdate: string = calculateFromDate(
      numberOfDaysForDelta[
        type === "project" ? apiRequestInterval : modelInterval
      ] || 14,
    ),
  ) => {
    try {
      showLoader();
      await getRequestCounts({
        frequency: frequency,
        filter_by: type,
        filter_conditions: [],
        from_date: fromdate,
        top_k: 5,
        metrics: metrics,
      });
      hideLoader();
    } catch (error) {
      hideLoader();
    }
  };
  const getAccuracyChartData = async () => {
    try {
      showLoader();
      await getAccuracyChart({
        // benchmarks: 'mmmu',
        benchmarks: ["mmlu", "arcc", "gsm8k", "math", "humaneval"],
        // benchmarks: ['mmmu', 'hallucination_bench', 'lmsys_areana', 'math_vista', 'ai2d'],
        k: 5,
      });
      hideLoader();
    } catch (error) {
      hideLoader();
    }
  };
  const getRequests = async () => {
    try {
      showLoader();
      await getTotalRequests({
        frequency: "daily",
        from_date: calculateFromDate(14), // Get 14 days to calculate week-over-week
        metrics: "global",
        filter_by: "project",
      });
      hideLoader();
    } catch (error) {
      hideLoader();
    }
  };

  const throughPutReq = async (type: string) => {
    showLoader();
    try {
      await getThroughputAndLatencyData({
        frequency:
          (type === "throughput" ? throughputInterval : latencyInterval) ||
          "daily",
        filter_by: "project",
        filter_conditions: [],
        from_date: calculateFromDate(
          numberOfDaysForDelta[
            type === "throughput" ? throughputInterval : latencyInterval
          ] || 14,
        ),
        top_k: 5,
        metrics: type,
      });
      hideLoader();
    } catch (error) {
      hideLoader();
    }
  };

  const getDashboardCounts = async () => {
    showLoader();
    try {
      await getDashboardCountData();
      hideLoader();
    } catch (error) {
      hideLoader();
    }
  };

  const calculateFromDate = (daysToReduce: number) => {
    const now = new Date(); // Get current date and time
    const pastDate = new Date(now); // Create a copy
    pastDate.setUTCDate(now.getUTCDate() - daysToReduce); // Subtract days
    return pastDate.toISOString(); // Return full ISO string with time
  };
  useEffect(() => {
    throughPutReq("throughput");
  }, [throughputInterval]);

  useEffect(() => {
    throughPutReq("latency");
  }, [latencyInterval]);

  useEffect(() => {
    createApiChartData(requestCounts);
  }, [requestCounts]);

  useEffect(() => {
    createThroughputData(throughputCount);
  }, [throughputCount]);

  useEffect(() => {
    createLatencyData(latencyCount);
  }, [latencyCount]);

  useEffect(() => {
    let data = processLeaderboardData(accuracyData);
    if (data) {
      setAccuracyChartData(data);
    }
  }, [accuracyData]);

  useEffect(() => {
    createTokenMatricstData(tokenMetrics);
  }, [tokenMetrics]);

  //  for accuracy data
  type Benchmark = {
    field: string;
    value: number | null;
    type: string;
    label: string;
  };

  type Leaderboard = {
    benchmarks: Benchmark[];
    name: string;
    provider_type: string;
  };

  const processLeaderboardData = (
    accuracyData: Leaderboard[],
  ): AccuracyChartData => {
    // Extract unique benchmark labels as dimensions, with "product" as the first dimension
    const dimensions = [
      "product",
      ...Array.from(
        new Set(accuracyData?.flatMap((l) => l.benchmarks.map((b) => b.label))),
      ),
    ];
    // Transform leaderboard data into the required source format
    const source = accuracyData?.map((model) => {
      const entry: Record<string, number | string> = { product: model.name };

      model.benchmarks.forEach((benchmark) => {
        entry[benchmark.label] = benchmark.value ?? 0; // Default to 0 if value is null
      });

      return entry;
    });

    return { dimensions, source };
  };

  //  for accuracy data

  const getLastWeekDates = () => {
    const today = new Date();
    const days = [];
    for (let i = 0; i < 7; i++) {
      const previousDay = new Date();
      previousDay.setDate(today.getDate() - i);
      days.push(previousDay.toISOString().split("T")[0]);
    }
    return days.reverse();
  };

  useEffect(() => {
    if (totalRequests?.global_metrics) {
      const dates = getLastWeekDates();
      const lookup = totalRequests?.global_metrics?.items
        ? Object.fromEntries(
            totalRequests?.global_metrics?.items?.map((obj: any) => [
              obj?.time_period?.split("T")[0],
              obj?.items?.length ? obj.items[0].total_requests : 0,
            ]),
          )
        : [];
      const result = dates.map((key) => ({
        key: key,
        value: lookup[key] || 0,
      }));
      setTotalRequestChartData({
        categories: result.map((obj) => obj.key),
        data: result.map((obj) => obj.value),
      });
    } else {
      setTotalRequestChartData({ categories: [], data: [] });
    }
  }, [totalRequests]);

  const handleChartFilter = (val: string) => {
    if (val === "LAST 24 HRS") return "daily";
    if (val === "LAST 7 DAYS") return "weekly";
    if (val === "LAST 30 DAYS") return "monthly";
    return "weekly"; // Default fallback
  };

  // ApiRequestData code block ----------------------------------
  const createApiChartData = (data: any) => {
    if (data) {
      setExtraChartDetails((prev) => ({
        ...prev,
        apiCalls: {
          total_value: data?.overall_metrics?.summary_metrics?.total_value,
          avg: data?.overall_metrics?.summary_metrics?.delta_percentage,
        },
      }));
      setApiChartData((prevState) => ({
        ...prevState,
        categories:
          data?.overall_metrics?.summary_metrics?.items.map(
            (item: any) => item.name,
          ) || [],
        data:
          data?.overall_metrics?.summary_metrics?.items.map(
            (item: any) => item.total_value,
          ) || [],
      }));
    }
  };

  const createTokenMatricstData = (data: any) => {
    if (data) {
      // Update extra chart details (if needed)
      setExtraChartDetails((prev) => ({
        ...prev,
        token_metrics: {
          total_input_value:
            data.input_output_tokens_metrics.summary_metrics
              .input_tokens_delta_value,
          total_output_value:
            data.input_output_tokens_metrics.summary_metrics
              .output_tokens_delta_value,
          input_avg:
            data.input_output_tokens_metrics.summary_metrics
              .input_tokens_delta_percentage,
          output_avg:
            data.input_output_tokens_metrics.summary_metrics
              .output_tokens_delta_percentage,
        },
      }));

      // Create chart data using the summary_metrics.items array
      const dimensions = ["product", "Input Tokens", "Output Tokens"];
      const source = data.input_output_tokens_metrics.items[0]?.items.map(
        (item: any) => ({
          product: item.name,
          "Input Tokens": item.input_tokens,
          "Output Tokens": item.output_tokens,
        }),
      );

      setTokenMetricsData({
        dimensions,
        source,
        // You can add other options (like showLegend, barColor, etc.) as needed.
      });
    }
  };

  const handleApiRequestChange = (data: string) => {
    setApiRequestInterval(handleChartFilter(data));
  };

  useEffect(() => {
    load();
  }, [apiRequestInterval]);
  // getApiRequestData code block ----------------------------------

  // Model code block ----------------------------------
  const handleModelChange = (data: string) => {
    setModelInterval(handleChartFilter(data));
  };

  const handleMetricsChange = (data: string) => {
    setTokenMetricsInterval(handleChartFilter(data));
  };

  useEffect(() => {
    load("model");
  }, [modelInterval]);

  useEffect(() => {
    load(
      "model",
      "input_output_tokens",
      tokenMetricsInterval,
      calculateFromDate(numberOfDaysForDelta[tokenMetricsInterval] || 14),
    );
  }, [tokenMetricsInterval]);

  useEffect(() => {
    if (modelCounts) {
      setExtraChartDetails((prev) => ({
        ...prev,
        models: {
          total_value:
            modelCounts?.overall_metrics?.summary_metrics?.total_value,
          avg: modelCounts?.overall_metrics?.summary_metrics?.delta_percentage,
        },
      }));
      setModelChartData((prevState) => ({
        ...prevState,
        categories:
          modelCounts?.overall_metrics?.summary_metrics?.items.map(
            (item: any) => item.name,
          ) || [],
        data:
          modelCounts?.overall_metrics?.summary_metrics?.items.map(
            (item: any) => item.total_value,
          ) || [],
      }));
    }
  }, [modelCounts]);
  // Model code block ----------------------------------

  // throughputData code block ----------------------------------

  const createThroughputData = (data: any) => {
    if (data) {
      setExtraChartDetails((prev) => ({
        ...prev,
        throughPut: {
          total_value: data?.throughput_metrics?.summary_metrics?.total_value,
          avg: data?.throughput_metrics?.summary_metrics?.delta_percentage,
        },
      }));
      setThroughputChartData((prevState) => ({
        ...prevState,
        categories:
          data?.throughput_metrics?.summary_metrics?.items.map(
            (item: any) => item.name,
          ) || [],
        data:
          data?.throughput_metrics?.summary_metrics?.items.map(
            (item: any) => item.total_value,
          ) || [],
      }));
    }
  };
  const handleThroughputChange = (data: string) => {
    setThroughputInterval(handleChartFilter(data));
  };

  useEffect(() => {
    createThroughputData(throughputCount);
  }, [throughputCount]);
  // throughputData code block ----------------------------------

  // Latency code block ----------------------------------

  const createLatencyData = (data: any) => {
    if (data) {
      setExtraChartDetails((prev) => ({
        ...prev,
        latency: {
          total_value: data?.latency_metrics?.summary_metrics?.total_value || 0,
          avg: data?.latency_metrics?.summary_metrics?.delta_percentage || 0,
        },
      }));
      setLatencyChartData((prevState) => ({
        ...prevState,
        categories:
          data?.latency_metrics?.summary_metrics?.items.map(
            (item: any) => item.name,
          ) || [],
        data:
          data?.latency_metrics?.summary_metrics?.items.map(
            (item: any) => item.total_value,
          ) || [],
      }));
    }
  };
  const handleLatencyChange = (data: string) => {
    setLatencyInterval(handleChartFilter(data));
  };

  useEffect(() => {
    createLatencyData(latencyCount);
  }, [latencyCount]);

  // latency code block ----------------------------------

  const formatNumber = (value: number) => {
    if (value >= 1_000_000_000) {
      return { value: +(value / 1_000_000_000).toFixed(1), suffix: "B" };
    } else if (value >= 1_000_000) {
      return { value: +(value / 1_000_000).toFixed(1), suffix: "M" };
    } else if (value >= 1_000) {
      return { value: +(value / 1_000).toFixed(1), suffix: "K" };
    }
    return { value: value, suffix: "" };
  };

  const smallCardData = [
    {
      image: "/images/dashboard/mask2.png",
      title: "Endpoints",
      value: formatNumber(dashboardCount?.total_endpoints_count).value
        ? formatNumber(dashboardCount?.total_endpoints_count).value +
          formatNumber(dashboardCount?.total_endpoints_count).suffix
        : 0,
      tag: {
        value: `${formatNumber(dashboardCount?.running_endpoints_count).value ? formatNumber(dashboardCount?.running_endpoints_count).value + formatNumber(dashboardCount?.running_endpoints_count).suffix : 0} Running`,
        bg: "#122F1140",
        color: "#479D5F",
      },
    },
    {
      image: "/images/dashboard/mask3.png",
      title: "Clusters",
      value: formatNumber(dashboardCount?.total_clusters).value
        ? formatNumber(dashboardCount?.total_clusters).value +
          formatNumber(dashboardCount?.total_clusters).suffix
        : 0,
      tag: {
        value: `${formatNumber(dashboardCount?.inactive_clusters).value ? formatNumber(dashboardCount?.inactive_clusters).value + formatNumber(dashboardCount?.inactive_clusters).suffix : 0} Not Available`,
        bg: "#861A1A33",
        color: "#EC7575",
      },
    },
    {
      image: "/images/dashboard/mask4.png",
      title: "Projects",
      value: formatNumber(dashboardCount?.total_projects).value
        ? formatNumber(dashboardCount?.total_projects).value +
          formatNumber(dashboardCount?.total_projects).suffix
        : 0,
      tag: {
        value: `${formatNumber(dashboardCount?.total_project_users).value ? formatNumber(dashboardCount?.total_project_users).value + formatNumber(dashboardCount?.total_project_users).suffix : 0} Members`,
        bg: "#1B325140",
        color: "#4077E6",
      },
    },
  ];

  interface SmallCardData {
    image: string;
    title: string;
    value: string | number;
    tag: {
      value: string;
      bg: string;
      color: string;
    };
  }

  const SmallCard = ({ data }: { data: SmallCardData }) => {
    return (
      <Flex className="cardBG w-[32%] h-[49.3%] border border-[#1F1F1F] rounded-md pt-[1.6rem] pb-[1.3rem] px-[1.5rem] relative">
        <div className="absolute w-full h-full top-[0] right-[0] z-1">
          <Image
            preview={false}
            width={"100%"}
            src={data.image}
            className="w-full h-full"
            alt=""
          />
        </div>
        <Flex vertical className="relative z-50 justify-between">
          <div>
            <Text_15_600_EEEEEE>{data.title}</Text_15_600_EEEEEE>
          </div>
          <Flex className="justify-between w-full items-end	">
            <div>
              <Flex className="mb-[.7rem] items-end">
                <Text_38_400_EEEEEE>{data.value}</Text_38_400_EEEEEE>
              </Flex>
              <Flex gap={8}>
                <Flex
                  style={{ backgroundColor: data.tag.bg }}
                  className={` rounded-md items-center px-[.45rem] mb-[.1rem] h-[1.35rem]`}
                >
                  <Text_13_400_tag
                    style={{ color: data.tag.color }}
                    className={``}
                  >
                    {data.tag.value}
                  </Text_13_400_tag>
                </Flex>
              </Flex>
            </div>
          </Flex>
        </Flex>
      </Flex>
    );
  };

  // Removed unused chartCardData and ChartUsageCard components

  useEffect(() => {
    setIsMounted(true);
    getRequests();
    getDashboardCounts();
    getAccuracyChartData();
  }, []);

  if (!isMounted) {
    return false;
  }

  return (
    <DashBoardLayout>
      <div className="boardPageView">
        <div className="boardMainContainer pt-[2.25rem]">
          <Flex className="h-[67.5%] justify-between">
            <div className="cardOne relative cardBG w-[37.4%] px-[2.7%] h-full border-[#1F1F1F] rounded-md">
              <Carousel arrows afterChange={onChange} className="h-full">
                <div className="pt-[4.8rem]">
                  <div className="text-[3.3125rem] text-[#EEEEEE] leading-[100%] font-[400]">
                    89 %
                  </div>
                  <Flex className="pt-[0.85rem] pl-[0.4rem]">
                    <p className="text-[0.9375rem] text-[#479D5F] leading-[100%] font-[400] mr-[0.3rem]">
                      Savings
                    </p>
                    <Image
                      preview={false}
                      width={15}
                      src="/images/dashboard/greenArrow.png"
                      alt=""
                    />
                  </Flex>
                  <p className="text-[0.9375rem] text-[#EEEEEE] font-[600] pt-[2.3rem] leading-[1.22rem] pr-[2rem]">
                    Increase in your revenue
                    <span className="font-[400] text-[#757575]">
                      {" "}
                      by end of this month is forecasted.
                    </span>
                  </p>
                  <p className="text-[0.8125rem] text-[#757575] font-[400] leading-[1.22rem] pt-[1.8rem]">
                    Harver is about to receive 15k new customers which results
                    in 78% increase in revenue
                  </p>
                </div>
                <div className="pt-[4.8rem]">
                  <div className="text-[3.3125rem] text-[#EEEEEE] leading-[100%] font-[400]">
                    900 %
                  </div>
                  <Flex className="pt-[0.85rem] pl-[0.4rem]">
                    <p className="text-[0.9375rem] text-[#479D5F] leading-[100%] font-[400] mr-[0.3rem]">
                      Savings
                    </p>
                    <Image
                      preview={false}
                      width={15}
                      src="/images/dashboard/greenArrow.png"
                      alt=""
                    />
                  </Flex>
                  <p className="text-[0.9375rem] text-[#EEEEEE] font-[600] pt-[2.3rem] leading-[1.22rem] pr-[2rem]">
                    Increase in your revenue
                    <span className="font-[400] text-[#757575]">
                      {" "}
                      by end of this month is forecasted.
                    </span>
                  </p>
                  <p className="text-[0.8125rem] text-[#757575] font-[400] leading-[1.22rem] pt-[1.8rem]">
                    Harver is about to receive 15k new customers which results
                    in 78% increase in revenue
                  </p>
                </div>
                <div className="pt-[4.8rem]">
                  <div className="text-[3.3125rem] text-[#EEEEEE] leading-[100%] font-[400]">
                    999 %
                  </div>
                  <Flex className="pt-[0.85rem] pl-[0.4rem]">
                    <p className="text-[0.9375rem] text-[#479D5F] leading-[100%] font-[400] mr-[0.3rem]">
                      Savings
                    </p>
                    <Image
                      preview={false}
                      width={15}
                      src="/images/dashboard/greenArrow.png"
                      alt=""
                    />
                  </Flex>
                  <p className="text-[0.9375rem] text-[#EEEEEE] font-[600] pt-[2.3rem] leading-[1.22rem] pr-[2rem]">
                    Increase in your revenue
                    <span className="font-[400] text-[#757575]">
                      {" "}
                      by end of this month is forecasted.
                    </span>
                  </p>
                  <p className="text-[0.8125rem] text-[#757575] font-[400] leading-[1.22rem] pt-[1.8rem]">
                    Harver is about to receive 15k new customers which results
                    in 78% increase in revenue
                  </p>
                </div>
              </Carousel>
            </div>
            <Flex className="w-[61.3%] justify-between flex-wrap" gap={".7rem"}>
              <Flex
                vertical
                className="cardBG w-[57.8%] h-[47.3%] border border-[#1F1F1F] rounded-md pt-[1.2rem] pb-[1.3rem] px-[1.5rem] justify-between	"
              >
                <div>
                  <p className=" text-[0.9375rem]text-[#EEEEEE]">
                    Total Requests
                  </p>
                  <span className="block h-[3px] bg-[#965CDE] w-[1.6875rem] mt-[.1em] ml-[.1rem]"></span>
                </div>
                <Flex className="justify-between w-full items-end	">
                  <div>
                    <Flex className="mb-[.2rem] items-end">
                      <span className="text-[2.375rem] text-[#EEEEEE] leading-[100%] font-[400]">
                        {totalRequests?.global_metrics?.summary_metrics
                          ?.total_value
                          ? formatNumber(
                              totalRequests?.global_metrics?.summary_metrics
                                ?.total_value,
                            ).value
                          : 0}
                        <span className="text-[#757575] leading-[100%]">
                          {
                            formatNumber(
                              totalRequests?.global_metrics?.summary_metrics
                                ?.total_value,
                            ).suffix
                          }
                        </span>
                      </span>
                      <Flex className="ml-[.7rem] mb-[.4rem]">
                        {totalRequests?.global_metrics?.summary_metrics
                          ?.delta_percentage >= 0 ? (
                          <Image
                            preview={false}
                            width={13}
                            src="/images/dashboard/up.png"
                            alt=""
                          />
                        ) : (
                          <Image
                            preview={false}
                            width={13}
                            src="/images/dashboard/down.png"
                            alt=""
                          />
                        )}
                        <span
                          className={`text-[0.8125rem] leading-[100%] font-[400] ml-[.2rem] ${Number(totalRequests?.global_metrics?.summary_metrics?.delta_percentage) >= 0 ? "text-[#479D5F]" : "text-[#EC7575]"}`}
                        >
                          {Number(
                            totalRequests?.global_metrics?.summary_metrics
                              ?.delta_percentage || 0,
                          ).toFixed(2)}
                          %{" "}
                        </span>
                      </Flex>
                    </Flex>
                    <span className="text-[0.8125rem] text-[#757575] leading-[100%] font-[400]">
                      Last 7 days
                    </span>
                  </div>
                  <div className="w-[7rem]">
                    {/* <Image
                      preview={false}
                      src="/images/dashboard/purpleArrow.png"
                      alt=""
                    /> */}
                    <DirectionArrowChart
                      categories={totalRequestChartData.categories}
                      data={totalRequestChartData.data}
                    />
                  </div>
                </Flex>
              </Flex>
              <Flex
                vertical
                className="cardBG w-[40.2%] h-[47.3%] border border-[#1F1F1F] rounded-md pt-[1.2rem] pb-[1.3rem] px-[1.5rem] justify-between	"
              >
                <div>
                  <p className=" text-[0.9375rem]text-[#EEEEEE]">Models</p>
                  <span className="block h-[3px] bg-[#965CDE] w-[1.6875rem] mt-[.1em] ml-[.1rem]"></span>
                </div>
                <Flex className="justify-between w-full items-end	">
                  <div>
                    <Flex className="mb-[.2rem] items-end">
                      <span className="text-[2.375rem] text-[#EEEEEE] leading-[100%] font-[400]">
                        {dashboardCount?.total_model_count || 0}
                      </span>
                    </Flex>
                    <Flex gap={8}>
                      <Flex className="bg-[#8F55D62B] rounded-md items-center px-[.45rem] mb-[.1rem] h-[1.35rem]">
                        <div className="w-[0.8125rem] mr-[.25rem]">
                          <Image
                            preview={false}
                            src="/images/dashboard/purpleCloud.png"
                            alt=""
                          />
                        </div>
                        <span className="text-[#965CDE] font-[400] text-[0.8125rem] leading-[100%]">
                          {dashboardCount?.cloud_model_count || 0} Cloud
                        </span>
                      </Flex>
                      <Flex className="bg-[#423A1A40] rounded-md items-center px-[.45rem] mb-[.1rem] h-[1.35rem]">
                        <div className="w-[0.8125rem] mr-[.25rem]">
                          <Image
                            preview={false}
                            src="/images/dashboard/hug.png"
                            alt=""
                          />
                        </div>
                        <span className="text-[#D1B854] font-[400] text-[0.8125rem] leading-[100%]">
                          {dashboardCount?.local_model_count || 0} Local
                        </span>
                      </Flex>
                    </Flex>
                  </div>
                </Flex>
              </Flex>
              {/* small blocks */}
              {smallCardData.length > 0 && (
                <>
                  {smallCardData.map((item, index) => (
                    <SmallCard key={index} data={item} />
                  ))}
                </>
              )}
              {/* small blocks */}
            </Flex>
          </Flex>
          {/* dashboard section 2 start*/}
          <Flex
            gap={"1.1rem"}
            className="mt-[1.2rem] justify-between flex-wrap pb-[45px]"
          >
            {/* accuracy chart */}

            {/* number of api calls chart */}
            <div className="cardBG w-[49.1%] cardSetTwo  py-[1.9rem] px-[1.65rem] border border-[#1F1F1F] rounded-md">
              <Flex className="justify-between align-center">
                <Text_19_600_EEEEEE>Number of API Calls</Text_19_600_EEEEEE>
                <Segmented
                  options={segmentOptions}
                  value={segmentOptions.find(
                    (opt) => handleChartFilter(opt) === apiRequestInterval,
                  )} // Ensure correct default selection
                  onChange={(value) => {
                    handleApiRequestChange(value); // string
                  }}
                  className="antSegmented rounded-md text-[#EEEEEE] font-[400] bg-[transparent] border border-[#4D4D4D] border-[.53px] p-[0]"
                />
              </Flex>
              {apiChartData.data.length ? (
                <>
                  <Flex vertical className="items-start	mt-[1.3rem]">
                    <p className="text-[1.625rem] text-[#EEEEEE] leading-[100%] font-[400] mb-0">
                      {Number(extraChartDetails.apiCalls.total_value).toFixed(
                        2,
                      )}
                    </p>
                    <Flex
                      className={`${Number(extraChartDetails.apiCalls.avg) >= 0 ? "text-[#479D5F] bg-[#122F1140]" : "bg-[#861A1A33] text-[#EC7575]"} rounded-md items-center px-[.45rem] mb-[.1rem] h-[1.35rem] mt-[0.82rem]`}
                    >
                      <span className="font-[400] text-[0.8125rem] leading-[100%]">
                        Avg. {Number(extraChartDetails.apiCalls.avg).toFixed(2)}
                        %{" "}
                      </span>
                      {Number(extraChartDetails.apiCalls.avg) >= 0 ? (
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
                    </Flex>
                  </Flex>
                  <div className="h-[232px]">
                    <BarChart data={apiChartData} />
                  </div>
                </>
              ) : (
                <NoChartData
                  textMessage="Once the data is available, we will populate a bar chart for you representing Number of API Calls"
                  image="/images/dashboard/noData.png"
                ></NoChartData>
              )}
            </div>
            {/* latency chart */}
            <div className="cardBG w-[49.1%] cardSetTwo  py-[1.9rem] px-[1.65rem] border border-[#1F1F1F] rounded-md">
              <Flex className="justify-between align-center">
                <Text_19_600_EEEEEE>Latency</Text_19_600_EEEEEE>
                <Segmented
                  options={segmentOptions}
                  value={segmentOptions.find(
                    (opt) => handleChartFilter(opt) === latencyInterval,
                  )} // Ensure correct default selection
                  onChange={(newValue) => handleLatencyChange(newValue)}
                  className="antSegmented rounded-md text-[#EEEEEE] font-[400] bg-[transparent] border border-[#4D4D4D] border-[.53px] p-[0]"
                />
              </Flex>
              {latencyChartData.data.length ? (
                <>
                  <Flex vertical className="items-start	mt-[1.3rem]">
                    <p className="text-[1.625rem] text-[#EEEEEE] leading-[100%] font-[400] mb-0">
                      {Number(extraChartDetails.latency.total_value).toFixed(2)}{" "}
                      ms
                    </p>
                    <Flex
                      className={`${Number(extraChartDetails.latency.avg) >= 0 ? "text-[#479D5F] bg-[#122F1140]" : "bg-[#861A1A33] text-[#EC7575]"} rounded-md items-center px-[.45rem] mb-[.1rem] h-[1.35rem] mt-[0.82rem]`}
                    >
                      <span className="font-[400] text-[0.8125rem] leading-[100%]">
                        Avg. {Number(extraChartDetails.latency.avg).toFixed(2)}
                        %{" "}
                      </span>
                      {Number(extraChartDetails.latency.avg) >= 0 ? (
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
                    </Flex>
                  </Flex>
                  <div className="h-[232px]">
                    <BarChart data={latencyChartData} />
                  </div>
                </>
              ) : (
                <NoChartData
                  textMessage="Once the data is available, we will populate a bar chart for you representing Latency"
                  image="/images/dashboard/noData.png"
                ></NoChartData>
              )}
            </div>
            {/* throughput chart */}
            <div className="cardBG w-[49.1%] cardSetTwo py-[1.9rem] px-[1.65rem] border border-[#1F1F1F] rounded-md">
              <Flex className="justify-between align-center">
                <Text_19_600_EEEEEE>Throughput</Text_19_600_EEEEEE>
                <Segmented
                  options={segmentOptions}
                  value={segmentOptions.find(
                    (opt) => handleChartFilter(opt) === throughputInterval,
                  )} // Ensure correct default selection
                  onChange={(value) => {
                    handleThroughputChange(value); // string
                  }}
                  className="antSegmented rounded-md text-[#EEEEEE] font-[400] bg-[transparent] border border-[#4D4D4D] border-[.53px] p-[0]"
                />
              </Flex>
              {throughputChartData.data.length ? (
                <>
                  <Flex vertical className="items-start	mt-[1.3rem]">
                    <p className="text-[1.625rem] text-[#EEEEEE] leading-[100%] font-[400] mb-0">
                      {Number(extraChartDetails.throughPut.total_value).toFixed(
                        2,
                      )}{" "}
                      tokens/s
                    </p>
                    <Flex
                      className={`${Number(extraChartDetails.throughPut.avg) >= 0 ? "text-[#479D5F] bg-[#122F1140]" : "bg-[#861A1A33] text-[#EC7575]"} rounded-md items-center px-[.45rem] mb-[.1rem] h-[1.35rem] mt-[0.82rem]`}
                    >
                      <span className="font-[400] text-[0.8125rem] leading-[100%]">
                        Avg.{" "}
                        {Number(extraChartDetails.throughPut.avg).toFixed(2)}
                        %{" "}
                      </span>
                      {Number(extraChartDetails.throughPut.avg) >= 0 ? (
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
                    </Flex>
                  </Flex>
                  <div className="h-[232px]">
                    <BarChart data={throughputChartData} />
                  </div>
                </>
              ) : (
                <NoChartData
                  textMessage="Once the data is available, we will populate a bar chart for you representing Throughput."
                  image="/images/dashboard/noData.png"
                ></NoChartData>
              )}
            </div>

            {/* model usage chart */}
            <div className="relative cardBG w-[49.1%] cardSetTwo  py-[1.9rem] px-[1.65rem] border border-[#1F1F1F] rounded-md">
              <Flex className="justify-between align-center">
                <Text_19_600_EEEEEE>Model Usage</Text_19_600_EEEEEE>
                <Segmented
                  options={segmentOptions}
                  value={segmentOptions.find(
                    (opt) => handleChartFilter(opt) === modelInterval,
                  )} // Ensure correct default selection
                  onChange={(value) => {
                    handleModelChange(value); // string
                  }}
                  className="antSegmented rounded-md text-[#EEEEEE] font-[400] bg-[transparent] border border-[#4D4D4D] border-[.53px] p-[0]"
                />
              </Flex>
              {modelChartData.data.length ? (
                <>
                  <Flex vertical className="items-start	mt-[1.3rem]">
                    <p className="text-[1.625rem] text-[#EEEEEE] leading-[100%] font-[400] mb-0">
                      {Number(extraChartDetails.models.total_value).toFixed(2)}
                    </p>
                    <Flex
                      className={`${Number(extraChartDetails.models.avg) >= 0 ? "text-[#479D5F] bg-[#122F1140]" : "bg-[#861A1A33] text-[#EC7575]"} rounded-md items-center px-[.45rem] mb-[.1rem] h-[1.35rem] mt-[0.82rem]`}
                    >
                      <span className="font-[400] text-[0.8125rem] leading-[100%]">
                        Avg. {Number(extraChartDetails.models.avg).toFixed(2)}
                        %{" "}
                      </span>
                      {Number(extraChartDetails.models.avg) >= 0 ? (
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
                    </Flex>
                  </Flex>
                  <div className="h-[232px]">
                    <BarChart data={modelChartData} />
                  </div>
                </>
              ) : (
                <NoChartData
                  textMessage="Once the data is available, we will populate a bar chart for you representing Model Usage."
                  image="/images/dashboard/noData.png"
                ></NoChartData>
              )}
            </div>

            {/* Accuracy chart */}
            <div className="relative cardBG w-[49.1%] cardSetTwo py-[1.9rem] px-[1.65rem] border border-[#1F1F1F] rounded-md">
              <div>
                <Text_19_600_EEEEEE>Accuracy</Text_19_600_EEEEEE>
              </div>
              {accuracyChartData?.source?.length ? (
                <>
                  <p className="text-[0.8125rem] text-[#757575] leading-[100%] font-[400] mt-[0.95rem]">
                    For the top 5 models
                  </p>
                  {/* <Flex vertical className="items-start	mt-[2.03rem]">
                    <p className="text-[1.625rem] text-[#EEEEEE] leading-[100%] font-[400] mb-0">127K</p>
                    <Flex className="bg-[#122F1140] rounded-md items-center px-[.45rem] mb-[.1rem] h-[1.35rem] mt-[0.82rem]">
                      <span className="text-[#479D5F] font-[400] text-[0.8125rem] leading-[100%]">Avg. +21.01% </span>
                      <Image
                        preview={false}
                        width={12}
                        src="/images/dashboard/greenArrow.png"
                        className="ml-[.2rem]"
                        alt=""
                      />
                    </Flex>
                  </Flex> */}
                  <div className="h-[232px] mt-[3.5rem]">
                    <AccuracyChart data={accuracyChartData} />
                  </div>
                </>
              ) : (
                <NoChartData
                  textMessage="Once the data is available, we will populate a bar comparison chart for you representing accuracy of top 5 models"
                  image="/images/dashboard/noData.png"
                ></NoChartData>
              )}
            </div>
            {/* latency chart */}

            {/* token metrics chart */}
            <div className=" w-[49.1%] cardBG cardSetTwo  py-[1.9rem] px-[1.65rem] border border-[#1F1F1F] rounded-md">
              <Flex className="justify-between align-center">
                <div>
                  <Text_19_600_EEEEEE>Token Metrics</Text_19_600_EEEEEE>
                </div>
                <Segmented
                  options={segmentOptions}
                  value={segmentOptions.find(
                    (opt) => handleChartFilter(opt) === tokenMetricsInterval,
                  )} // Ensure correct default selection
                  onChange={(value) => {
                    handleMetricsChange(value); // string
                  }}
                  className="antSegmented rounded-md text-[#EEEEEE] font-[400] bg-[transparent] border border-[#4D4D4D] border-[.53px] p-[0]"
                />
              </Flex>
              <p className="text-[0.8125rem] text-[#757575] leading-[100%] font-[400] mt-[0.35rem] mb-[.25rem]">
                For the top 5 models
              </p>

              {tokenMetricsData?.source?.length ? (
                <>
                  {/* <div className="flex justify-start items-start	mt-[1.5rem] gap-[.7rem]">
                    <div className={`flex flex-col border pt-[.2rem] pb-[.5rem] px-[.6rem] rounded-md`}
                      style={{
                        backgroundColor: getChromeColorHex('#ffff00', .05),
                        borderColor: getChromeColorHex('#ffff00', .5)
                      }}
                    >
                      <Text_26_400_EEEEEE>{Number(extraChartDetails.token_metrics.total_input_value).toFixed(2)}</Text_26_400_EEEEEE>
                      <div className={`flex ${Number(extraChartDetails.token_metrics.input_avg) >= 0 ? 'text-[#479D5F] bg-[#122F1140]' : 'bg-[#861A1A33] text-[#EC7575]'} rounded-md items-center px-[.45rem] mb-[.1rem] h-[1.35rem] mt-[0.2rem]`}>
                        <span className="font-[400] text-[0.8125rem] leading-[100%]">Avg. {Number(extraChartDetails.token_metrics.input_avg).toFixed(2)}% </span>
                        {Number(extraChartDetails.token_metrics.input_avg) >= 0 ?
                          <Image
                            preview={false}
                            width={12}
                            src="/images/dashboard/greenArrow.png"
                            className="ml-[.2rem]"
                            alt=""
                          /> : <Image
                            preview={false}
                            width={12}
                            src="/images/dashboard/redArrow.png"
                            className="ml-[.2rem]"
                            alt=""
                          />}
                      </div>
                    </div>
                    <div className={`flex flex-col border pt-[.2rem] pb-[.5rem] px-[.6rem] rounded-md`}
                      style={{
                        backgroundColor: getChromeColorHex('#33FF57', .05),
                        borderColor: getChromeColorHex('#33FF57', .5)
                      }}
                    >
                      <Text_26_400_EEEEEE>{Number(extraChartDetails.token_metrics.total_output_value).toFixed(2)}</Text_26_400_EEEEEE>
                      <div className={`flex ${Number(extraChartDetails.token_metrics.output_avg) >= 0 ? 'text-[#479D5F] bg-[#122F1140]' : 'bg-[#861A1A33] text-[#EC7575]'} rounded-md items-center px-[.45rem] mb-[.1rem] h-[1.35rem] mt-[0.2rem]`}>
                        <span className="font-[400] text-[0.8125rem] leading-[100%]">Avg. {Number(extraChartDetails.token_metrics.output_avg).toFixed(2)}% </span>
                        {Number(extraChartDetails.token_metrics.output_avg) >= 0 ?
                          <Image
                            preview={false}
                            width={12}
                            src="/images/dashboard/greenArrow.png"
                            className="ml-[.2rem]"
                            alt=""
                          /> : <Image
                            preview={false}
                            width={12}
                            src="/images/dashboard/redArrow.png"
                            className="ml-[.2rem]"
                            alt=""
                          />}
                      </div>
                    </div>
                  </div> */}
                  <div className="h-[232px] mt-[1.5rem]">
                    {/* <CustomBarChart data={tokenMetricsData} /> */}
                    <TokenMetricsChart
                      data={tokenMetricsData}
                      extraChartDetails={extraChartDetails}
                    />
                  </div>
                </>
              ) : (
                <NoChartData
                  textMessage="Once the data is available, we will populate a bar chart for you representing Number of API Calls"
                  image="/images/dashboard/noData.png"
                ></NoChartData>
              )}
            </div>
            {/* token metrics chart */}

            {/* temp hidden */}

            {/* <div className="relative cardBG w-[49.1%] cardSetOne h-[425px] py-[1.9rem] px-[1.65rem] border border-[#1F1F1F] rounded-md">
              <ComingSoon shrink={true} scaleValue={.9} />
              <div>
                <Text_19_600_EEEEEE>Latency Distribution Over Task</Text_19_600_EEEEEE>
                <p className="text-[0.8125rem] text-[#757575] leading-[100%] font-[400] mt-[0.95rem]">Three most recent tasks that were done</p>
              </div>
              {latencyDistribuitionData.series.length ? (
                <>
                  <Flex vertical className="items-start	mt-[2.03rem]">
                    <p className="text-[1.625rem] text-[#EEEEEE] leading-[100%] font-[400]">127K</p>
                    <Flex className="bg-[#122F1140] rounded-md items-center px-[.45rem] mb-[.1rem] h-[1.35rem] mt-[0.82rem]">
                      <span className="text-[#479D5F] font-[400] text-[0.8125rem] leading-[100%]">Avg. +21.01% </span>
                      <Image
                        preview={false}
                        width={12}
                        src="/images/dashboard/greenArrow.png"
                        className="ml-[.2rem]"
                        alt=""
                      />
                    </Flex>
                  </Flex>
                  <div className="h-[232px] mt-[1.95rem]">
                    <LatencyChart data={latencyDistribuitionData} />
                  </div>
                </>
              ) : (
                <NoChartData
                  textMessage="Once the data is available, we will populate a line chart for you representing latency distribution over the most recent 3 tasks"
                  image="/images/dashboard/noLatency.png"
                ></NoChartData>
              )}

            </div> */}
          </Flex>
          {/* dashboard section 2 end */}
          <Flex gap="3" wrap="wrap" justify="between" className="hidden">
            <Box className="w-[62%] h-[230px] min-[1680]:h-[300px] pt-[1.7%] px-[0] relative rounded overflow-hidden bg-[#18191b]">
              <Text_12_500_FFFFFF className="block m-0 p-0 pt-[.85rem] pl-[2.4rem] absolute">
                Accuracy
              </Text_12_500_FFFFFF>
              <AccuracyChart data={accuracyChartData} />
            </Box>
            <Box className="w-[30%] flex-auto h-[230px] min-[1680]:h-[300px] pt-[1.7%] px-[0] relative rounded overflow-hidden bg-[#18191b]">
              <Flex
                className="absolute pt-[.2rem] pl-[1.4rem] pr-[.5rem] w-full"
                justify="between"
                align="center"
              >
                <Text_12_500_FFFFFF className="block">
                  No. of API calls
                </Text_12_500_FFFFFF>
                <Box className="w-[6.7rem] z-50">
                  <SelectInput
                    size="2"
                    value={
                      requestOptions.find(
                        (option) => option.value === apiRequestInterval,
                      )?.label
                    }
                    onValueChange={(newValue: any) =>
                      handleApiRequestChange(newValue)
                    }
                    placeholder={`Select`}
                    showSearch={false}
                    selectItems={requestOptions}
                    renderItem=""
                  />
                </Box>
              </Flex>
              <ApiCallsChart data={apiChartData} />
            </Box>
            {/* <Box className="w-[49.35%] h-[230px] min-[1680]:h-[300px] pt-[1.7%] px-[0] relative rounded overflow-hidden bg-[#18191b]">
              <Text className='block m-0 p-0 pt-[.85rem] pl-[2.4rem] text-xs text-[#FFFFFF] font-medium leading-[100%] absolute'>Latency Distribution</Text>
              <LatencyChart data={latencyDistribuitionData} />
            </Box>
            <Box className="w-[49.35%] h-[230px] min-[1680]:h-[300px] pt-[1.7%] px-[0] relative rounded overflow-hidden bg-[#18191b]">
              <Text className='block m-0 p-0 pt-[.85rem] pl-[2.4rem] text-xs text-[#FFFFFF] font-medium leading-[100%] absolute'>Overall flops vs Utilized flops</Text>
              <OverallVsUtillizedChart data={OverallVsUtillizedChartData} />
            </Box> */}
            <Box className="w-[49.35%] h-[230px] min-[1680]:h-[300px] pt-[1.7%] px-[0] relative rounded overflow-hidden bg-[#18191b]">
              <Flex
                className="absolute pt-[.2rem] pl-[1.4rem] pr-[.5rem] w-full"
                justify="between"
                align="center"
              >
                <Text_12_500_FFFFFF className="block">
                  Model usage
                </Text_12_500_FFFFFF>
                <Box className="w-[6.7rem] z-50">
                  <SelectInput
                    size="2"
                    value={
                      requestOptions.find(
                        (option) => option.value === modelInterval,
                      )?.label
                    }
                    showSearch={false}
                    onValueChange={(newValue: any) =>
                      handleModelChange(newValue)
                    }
                    placeholder={`Select`}
                    selectItems={requestOptions}
                    renderItem=""
                  />
                </Box>
              </Flex>
              <ApiCallsChart data={modelChartData} />
            </Box>
            <Box className="w-[49.35%] h-[230px] min-[1680]:h-[300px] pt-[1.7%] px-[0] relative rounded overflow-hidden bg-[#18191b]">
              <Flex
                className="absolute pt-[.2rem] pl-[1.4rem] pr-[.5rem] w-full"
                justify="between"
                align="center"
              >
                <Text_12_500_FFFFFF className="block">
                  Throughput
                </Text_12_500_FFFFFF>
                <Box className="w-[6.7rem] z-50">
                  <SelectInput
                    size="2"
                    value={
                      requestOptions.find(
                        (option) => option.value === throughputInterval,
                      )?.label
                    }
                    showSearch={false}
                    onValueChange={(newValue: any) =>
                      handleThroughputChange(newValue)
                    }
                    placeholder={`Select`}
                    selectItems={requestOptions}
                    renderItem=""
                  />
                </Box>
              </Flex>
              <ApiCallsChart data={throughputChartData} />
            </Box>
            <Box className="w-[49.35%] h-[230px] min-[1680]:h-[300px] pt-[1.7%] px-[0] relative rounded overflow-hidden bg-[#18191b]">
              <Flex
                className="absolute pt-[.2rem] pl-[1.4rem] pr-[.5rem] w-full"
                justify="between"
                align="center"
              >
                <Text_12_500_FFFFFF className="block">
                  Latency
                </Text_12_500_FFFFFF>
                <Box className="w-[6.7rem] z-50">
                  <SelectInput
                    size="2"
                    value={
                      requestOptions.find(
                        (option) => option.value === latencyInterval,
                      )?.label
                    }
                    showSearch={false}
                    onValueChange={(newValue: any) =>
                      handleLatencyChange(newValue)
                    }
                    placeholder={`Select`}
                    selectItems={requestOptions}
                    renderItem=""
                  />
                </Box>
              </Flex>
              <ApiCallsChart data={latencyChartData} />
            </Box>
          </Flex>
        </div>
      </div>
      {/* <div className="homeWraper">
        <div className="topBox">
          <div className="rounded-lg">
            <span className="font-bold text-2xl">2</span>
            <span className="font-light text-sm">End Points</span>
          </div>
          <div className="rounded-lg">
            <span className="font-bold text-2xl">1</span>
            <span className="font-light text-sm">Cluster</span>
          </div>
          <div className="rounded-lg">
            <span className="font-bold text-2xl">4</span>
            <span className="font-light text-sm">Users</span>
          </div>
          <div className="rounded-lg">
            <span className="font-bold text-2xl">9</span>
            <span className="font-light text-sm">Models</span>
          </div>
        </div>
        <div className="bottomBox">
          <Flex className="h-full w-full justify-between chartFlexBox">
            <div className="chartDiv rounded-lg">
              <ResponsiveContainer width="100%" height={330}>
                <BarChart data={data}>
                  <XAxis
                    dataKey="name"
                    stroke="#888888"
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    stroke="#888888"
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(value) => `${value}`}
                  />
                  <Bar
                    dataKey="total"
                    fill="currentColor"
                    radius={[4, 4, 0, 0]}
                    className="fill-primary"
                  />
                </BarChart>
              </ResponsiveContainer>
              <label>API Requests</label>
            </div>
            <div className="chartDiv rounded-lg">
              <ResponsiveContainer width="100%" height={330}>
                <BarChart data={dataTwo}>
                  <XAxis
                    dataKey="name"
                    stroke="#888888"
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    stroke="#888888"
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(value) => `${value}`}
                  />
                  <Bar
                    dataKey="total"
                    fill="currentColor"
                    radius={[4, 4, 0, 0]}
                    className="fill-primary"
                  />
                </BarChart>
              </ResponsiveContainer>
              <label>Model Usage</label>
            </div>
          </Flex>
        </div>
      </div> */}
    </DashBoardLayout>
  );
};
export default Dashboard; //redirect to login page if user is unauthorized

// mmmu , hallusination, lmsys, math, ai2d

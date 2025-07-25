"use client";
import { useCallback, useEffect, useState } from "react";
import { AppRequest } from "./../../../../api/requests";

import {
  Text_12_500_FFFFFF,
  Text_19_600_EEEEEE,
  Text_20_400_FFFFFF,
  Text_32_700_FFFFFF,
} from "@/components/ui/text";

import { useLoader } from "src/context/appContext";
import { useRouter } from "next/router";
import ComingSoon from "@/components/ui/comingSoon";
import { Project, useProjects } from "src/hooks/useProjects";
import { Segmented, Image } from "antd";
import NoChartData from "@/components/ui/noChartData";
import BarChart from "@/components/charts/barChart";
import { tempApiBaseUrl } from "@/components/environment";
import LegendLineChart from "@/components/charts/lineChart/LegendLineChart";
import TokenMetricsChart from "@/components/charts/barChart/customBarChart";

const modelDataSample = {
  data: [46.06, 34.065],
  categories: ["zephyr", "budecosystem/code-millenials-8b"],
  label1: "Usage",
  label2: "Models",
};

interface AnalyticsProps {
  data: Project;
}

const AnalyticsComponent: React.FC<AnalyticsProps> = ({ data }) => {
  const {
    getProjectMetrics,
    projectMetricsData,
    getQueingMetrics,
    averageMetricsData,
    getTtftMetrics,
    ttftMetricsData,
    getLatencyMetrics,
    latencyMetricsData,
    getThroughputMetrics,
    throughputMetricsData,
  } = useProjects();
  const router = useRouter();
  const { projectId } = router.query;
  const [modelRequestInterval, setModelRequestInterval] =
    useState<any>("daily");
  const [modleRequestData, setModleRequestData] = useState<any>();
  const [modleChartData, setModleChartData] = useState<any>(null);

  const [averageInterval, setAverageInterval] = useState<any>("daily");
  const [averageRequestData, setAverageRequestData] = useState<any>();
  const [averageChartData, setAverageChartData] = useState<any>(null);

  
  const [ttftInterval, setTtftInterval] = useState<any>("daily");
  const [ttftRequestData, setTtftRequestData] = useState<any>();
  const [ttftChartData, setTtftChartData] = useState<any>(null);
  
  const [latencyInterval, setLatencyInterval] = useState<any>("daily");
  const [latencyRequestData, setLatencyRequestData] = useState<any>();
  const [latencyChartData, setLatencyChartData] = useState<any>(null);
  
  const [throughputInterval, setThroughputInterval] = useState<any>("daily");
  const [throughputRequestData, setThroughputRequestData] = useState<any>();
  const [throughputChartData, setThroughputChartData] = useState<any>(null);

  const [extraChartDetails, setExtraChartDetails] = useState({
    modelUsage: {
      total_value: "",
      avg: "",
    },
    average: {
      total_value: "",
      avg: "",
    },
    token_metrics: {
      total_input_value: "",
      total_output_value: "",
      input_avg: "",
      output_avg: ""
    },
    ttft: {
      total_value: "",
      avg: "",
    },
    latency: {
      total_value: "",
      avg: "",
    },
    throughput: {
      total_value: "",
      avg: "",
    }
  });
  const segmentOptions = ["LAST 24 HRS", "LAST 7 DAYS", "LAST 30 DAYS"];
  
  // Reset all chart data when project changes
  useEffect(() => {
    setModleChartData(null);
    setAverageChartData(null);
    setTtftChartData(null);
    setLatencyChartData(null);
    setThroughputChartData(null);
    setExtraChartDetails({
      modelUsage: {
        total_value: "",
        avg: "",
      },
      average: {
        total_value: "",
        avg: "",
      },
      token_metrics: {
        total_input_value: "",
        total_output_value: "",
        input_avg: "",
        output_avg: ""
      },
      ttft: {
        total_value: "",
        avg: "",
      },
      latency: {
        total_value: "",
        avg: "",
      },
      throughput: {
        total_value: "",
        avg: "",
      }
    });
  }, [projectId]);
  const requestOptions = [
    { label: "Last 24 hrs", value: "daily" },
    { label: "Last 7 days", value: "weekly" },
    { label: "Last 30 days", value: "monthly" },
  ];
  // For delta calculations, we need double the time period
  const numberOfDaysForDelta = {
    daily: 2,    // Last 48 hours (to get delta for last 24 hours)
    weekly: 14,   // Last 14 days (to get delta for last 7 days)
    monthly: 60  // Last 60 days (to get delta for last 30 days)
  };

  const handleChartFilter = (val: any) => {
    if (val === "LAST 24 HRS") return "daily";
    if (val === "LAST 7 DAYS") return "weekly";
    if (val === "LAST 30 DAYS") return "monthly";
    return "weekly"; // Default fallback
  };

  const getDateSubtracted = (days) => {
    const date = new Date();
    date.setDate(date.getDate() - days);
    return date.toISOString().split("T")[0];
  };

  const calculateFromDate = (daysToReduce: number) => {
    const now = new Date(); // Get current date and time
    const pastDate = new Date(now); // Create a copy
    pastDate.setUTCDate(now.getUTCDate() - daysToReduce); // Subtract days
    return pastDate.toISOString(); // Return full ISO string with time
  };
  // model usage code block ----------------------------------
  const getModelUsageData = async () => {
    const to_date = new Date().toISOString();
    await getProjectMetrics({
      frequency: modelRequestInterval,
      filter_by: "endpoint",
      filter_conditions: [],
      from_date: calculateFromDate(numberOfDaysForDelta[modelRequestInterval]),
      top_k: 5,
      metrics: "overall",
      project_id: projectId,
      to_date: to_date,
    });
  };

  useEffect(() => {
    getModelUsageData();
  }, [modelRequestInterval, projectId]);

  useEffect(() => {
    setModleRequestData(projectMetricsData);
  }, [projectMetricsData]);

  const createModelChartData = (data) => {
    console.log("Model usage data received:", data);
    
    let chartData = null;
    
    // Check if we have converted format
    if (data?.overall_metrics?.summary_metrics?.items?.length) {
      const items = data.overall_metrics.summary_metrics.items;

      setExtraChartDetails((prev) => ({
        ...prev,
        modelUsage: {
          total_value: data.overall_metrics.summary_metrics.total_value,
          avg: data.overall_metrics.summary_metrics.delta_percentage,
        },
      }));

      chartData = {
        categories: items.map((item) => item.name),
        data: items.map((item) => item.total_value),
      };
    }
    // Handle raw observability format
    else if (data?.items?.length) {
      console.log("Using raw observability format for model usage");
      
      const endpointMap = {};
      
      // Aggregate request counts across all time periods
      data.items.forEach((timePeriod) => {
        timePeriod.items.forEach((item) => {
          const name = item.endpoint_name || item.model_name || 'Unknown';
          const requestCount = item.data?.request_count?.count || 0;
          
          if (!endpointMap[name]) {
            endpointMap[name] = 0;
          }
          
          endpointMap[name] += requestCount;
        });
      });
      
      const endpoints = Object.keys(endpointMap);
      const counts = endpoints.map(name => endpointMap[name]);
      
      // Calculate total requests
      const totalRequests = counts.reduce((sum, count) => sum + count, 0);
      
      chartData = {
        categories: endpoints,
        data: counts,
      };
      
      setExtraChartDetails((prev) => ({
        ...prev,
        modelUsage: {
          total_value: totalRequests.toString(),
          avg: "0", // No delta in raw format
        },
      }));
    }
    
    if (chartData && chartData.categories.length > 0) {
      setModleChartData({
        ...chartData,
        label1: "Requests",
        label2: "Endpoints",
        barColor: "#9462D5"
      });
    } else {
      // Clear the data when empty
      setExtraChartDetails((prev) => ({
        ...prev,
        modelUsage: {
          total_value: "0",
          avg: "0",
        },
      }));
      
      setModleChartData({
        categories: [],
        data: [],
        label1: "Requests",
        label2: "Endpoints",
        barColor: "#9462D5"
      });
    }
  };

  useEffect(() => {
    createModelChartData(modleRequestData);
  }, [modleRequestData]);

  const handleModelChange = (data) => {
    setModelRequestInterval(handleChartFilter(data));
  };
  // model usage code block ----------------------------------

  // token metrics code block ----------------------------------
  const getAverageUsageData = async () => {
    const to_date = new Date().toISOString();
    await getQueingMetrics({
      frequency: averageInterval,
      filter_by: "endpoint",
      filter_conditions: [],
      from_date: calculateFromDate(numberOfDaysForDelta[averageInterval]),
      top_k: 5,
      metrics: "input_output_tokens",
      project_id: projectId,
      to_date: to_date,
    });
  };

  useEffect(() => {
    getAverageUsageData();
  }, [averageInterval, projectId]);

  useEffect(() => {
    setAverageRequestData(averageMetricsData);
  }, [averageMetricsData]);

  const createAverageChartData = (data) => {
    if (data?.input_output_tokens_metrics?.items?.length && data.input_output_tokens_metrics.items[0]?.items?.length) {
      const items = data.input_output_tokens_metrics.items[0].items;
      const summaryMetrics = data.input_output_tokens_metrics.summary_metrics;

      setExtraChartDetails((prev) => ({
        ...prev,
        average: {
          total_value: `${summaryMetrics.input_tokens_delta_value || 0} / ${summaryMetrics.output_tokens_delta_value || 0}`,
          avg: `${summaryMetrics.input_tokens_delta_percentage || 0} / ${summaryMetrics.output_tokens_delta_percentage || 0}`,
        },
        token_metrics: {
          total_input_value: summaryMetrics.input_tokens_delta_value || 0,
          total_output_value: summaryMetrics.output_tokens_delta_value || 0,
          input_avg: summaryMetrics.input_tokens_delta_percentage || 0,
          output_avg: summaryMetrics.output_tokens_delta_percentage || 0
        }
      }));

      // Create data structure for token metrics chart
      const dimensions = ["endpoint", "Input Tokens", "Output Tokens"];
      const source = items.map((item) => ({
        endpoint: item.name,
        "Input Tokens": item.input_tokens || 0,
        "Output Tokens": item.output_tokens || 0,
      }));

      setAverageChartData({
        dimensions,
        source,
        showLegend: true,
      });
    } else {
      // Clear the data when empty
      setExtraChartDetails((prev) => ({
        ...prev,
        average: {
          total_value: "0 / 0",
          avg: "0 / 0",
        },
        token_metrics: {
          total_input_value: "0",
          total_output_value: "0",
          input_avg: "0",
          output_avg: "0"
        }
      }));
      
      setAverageChartData({
        dimensions: ["endpoint", "Input Tokens", "Output Tokens"],
        source: [],
        showLegend: true,
      });
    }
  };

  useEffect(() => {
    createAverageChartData(averageRequestData);
  }, [averageRequestData]);

  const handleAverageChange = (data) => {
    setAverageInterval(handleChartFilter(data));
  };
  // token metrics code block ----------------------------------
  

  // TTFT code block ----------------------------------
  const getTtftData = async () => {
    const to_date = new Date().toISOString();
    await getTtftMetrics({
      frequency: ttftInterval,
      filter_by: "endpoint",
      filter_conditions: [],
      from_date: calculateFromDate(numberOfDaysForDelta[ttftInterval]),
      top_k: 5,
      metrics: "ttft",
      project_id: projectId,
      to_date: to_date,
    });
  };

  useEffect(() => {
    getTtftData();
  }, [ttftInterval, projectId]);

  useEffect(() => {
    setTtftRequestData(ttftMetricsData);
  }, [ttftMetricsData]);

  const createTtftChartData = (data) => {
    console.log("TTFT data received:", data);
    
    // Handle both converted format and raw observability format
    let chartData = null;
    
    // Check if we have converted format
    if (data?.ttft_metrics?.items?.length) {
      console.log("Using converted TTFT format");
      
      // Use summary items if available
      if (data.ttft_metrics.summary_metrics?.items?.length) {
        const items = data.ttft_metrics.summary_metrics.items;
        chartData = {
          categories: items.map((item) => item.name),
          data: items.map((item) => item.total_value || 0),
        };
      } else {
        // Aggregate from time series data
        const endpointTotals = {};
        const endpointCounts = {};
        
        data.ttft_metrics.items.forEach((timePeriod) => {
          timePeriod.items.forEach((item) => {
            const name = item.name;
            const value = item.avg_ttft_ms || item.total_value || 0;
            
            if (!endpointTotals[name]) {
              endpointTotals[name] = 0;
              endpointCounts[name] = 0;
            }
            
            endpointTotals[name] += value;
            endpointCounts[name] += 1;
          });
        });
        
        const endpoints = Object.keys(endpointTotals);
        const averages = endpoints.map(name => 
          endpointCounts[name] > 0 ? endpointTotals[name] / endpointCounts[name] : 0
        );
        
        chartData = {
          categories: endpoints,
          data: averages,
        };
      }
      
      setExtraChartDetails((prev) => ({
        ...prev,
        ttft: {
          total_value: data.ttft_metrics.summary_metrics?.total_value || "0",
          avg: data.ttft_metrics.summary_metrics?.delta_percentage || "0",
        },
      }));
    } 
    // Handle raw observability format
    else if (data?.items?.length) {
      console.log("Using raw observability format for TTFT");
      
      const endpointMap = {};
      
      // Aggregate data across all time periods
      data.items.forEach((timePeriod) => {
        timePeriod.items.forEach((item) => {
          const name = item.endpoint_name || item.model_name || 'Unknown';
          const ttftData = item.data?.ttft;
          const value = ttftData?.avg || 0;
          
          if (!endpointMap[name]) {
            endpointMap[name] = { total: 0, count: 0 };
          }
          
          endpointMap[name].total += value;
          endpointMap[name].count += 1;
        });
      });
      
      const endpoints = Object.keys(endpointMap);
      const values = endpoints.map(name => 
        endpointMap[name].count > 0 ? endpointMap[name].total / endpointMap[name].count : 0
      );
      
      // Calculate overall average
      const overallTotal = values.reduce((sum, val) => sum + val, 0);
      const overallAvg = values.length > 0 ? overallTotal / values.length : 0;
      
      chartData = {
        categories: endpoints,
        data: values,
      };
      
      setExtraChartDetails((prev) => ({
        ...prev,
        ttft: {
          total_value: overallAvg.toFixed(2),
          avg: "0", // No delta in raw format
        },
      }));
    }
    
    if (chartData && chartData.categories.length > 0) {
      console.log("TTFT chart data:", chartData);
      setTtftChartData({
        ...chartData,
        label1: "TTFT (ms)",
        label2: "Endpoints",
        barColor: "#32D583"
      });
    } else {
      // Clear the data when empty
      setExtraChartDetails((prev) => ({
        ...prev,
        ttft: {
          total_value: "0",
          avg: "0",
        },
      }));
      
      setTtftChartData({
        categories: [],
        data: [],
        label1: "TTFT (ms)",
        label2: "Endpoints",
        barColor: "#32D583"
      });
    }
  };

  useEffect(() => {
    createTtftChartData(ttftRequestData);
  }, [ttftRequestData]);

  const handleTtftChange = (data) => {
    setTtftInterval(handleChartFilter(data));
  };
  // TTFT code block ----------------------------------

  // Latency code block ----------------------------------
  const getLatencyData = async () => {
    const to_date = new Date().toISOString();
    await getLatencyMetrics({
      frequency: latencyInterval,
      filter_by: "endpoint",
      filter_conditions: [],
      from_date: calculateFromDate(numberOfDaysForDelta[latencyInterval]),
      top_k: 5,
      metrics: "latency",
      project_id: projectId,
      to_date: to_date,
    });
  };

  useEffect(() => {
    getLatencyData();
  }, [latencyInterval, projectId]);

  useEffect(() => {
    setLatencyRequestData(latencyMetricsData);
  }, [latencyMetricsData]);

  const createLatencyChartData = (data) => {
    console.log("Latency data received:", data);
    if (data?.latency_metrics?.summary_metrics?.items?.length) {
      const items = data.latency_metrics.summary_metrics.items;

      setExtraChartDetails((prev) => ({
        ...prev,
        latency: {
          total_value: data.latency_metrics.summary_metrics.total_value || "0",
          avg: data.latency_metrics.summary_metrics.delta_percentage || "0",
        },
      }));

      // Format for BarChart: categories are names, data are values
      setLatencyChartData({
        categories: items.map((item) => item.name),
        data: items.map((item) => item.total_value || 0),
        label1: "Latency (ms)",
        label2: "Endpoints",
        barColor: "#4A90E2"
      });
    } else {
      // Clear the data when empty
      setExtraChartDetails((prev) => ({
        ...prev,
        latency: {
          total_value: "0",
          avg: "0",
        },
      }));
      
      setLatencyChartData({
        categories: [],
        data: [],
        label1: "Latency (ms)",
        label2: "Endpoints",
        barColor: "#4A90E2"
      });
    }
  };

  useEffect(() => {
    createLatencyChartData(latencyRequestData);
  }, [latencyRequestData]);

  const handleLatencyChange = (data) => {
    setLatencyInterval(handleChartFilter(data));
  };
  // Latency code block ----------------------------------

  // Throughput code block ----------------------------------
  const getThroughputData = async () => {
    const to_date = new Date().toISOString();
    await getThroughputMetrics({
      frequency: throughputInterval,
      filter_by: "endpoint",
      filter_conditions: [],
      from_date: calculateFromDate(numberOfDaysForDelta[throughputInterval]),
      top_k: 5,
      metrics: "throughput",
      project_id: projectId,
      to_date: to_date,
    });
  };

  useEffect(() => {
    getThroughputData();
  }, [throughputInterval, projectId]);

  useEffect(() => {
    setThroughputRequestData(throughputMetricsData);
  }, [throughputMetricsData]);

  const createThroughputChartData = (data) => {
    console.log("Throughput data received:", data);
    if (data?.throughput_metrics?.summary_metrics?.items?.length) {
      const items = data.throughput_metrics.summary_metrics.items;

      setExtraChartDetails((prev) => ({
        ...prev,
        throughput: {
          total_value: data.throughput_metrics.summary_metrics.total_value || "0",
          avg: data.throughput_metrics.summary_metrics.delta_percentage || "0",
        },
      }));

      // Format for BarChart: categories are names, data are values
      setThroughputChartData({
        categories: items.map((item) => item.name),
        data: items.map((item) => item.total_value || 0),
        label1: "Throughput (tokens/s)",
        label2: "Endpoints",
        barColor: "#F39C12"
      });
    } else {
      // Clear the data when empty
      setExtraChartDetails((prev) => ({
        ...prev,
        throughput: {
          total_value: "0",
          avg: "0",
        },
      }));
      
      setThroughputChartData({
        categories: [],
        data: [],
        label1: "Throughput (tokens/s)",
        label2: "Endpoints",
        barColor: "#F39C12"
      });
    }
  };

  useEffect(() => {
    createThroughputChartData(throughputRequestData);
  }, [throughputRequestData]);

  const handleThroughputChange = (data) => {
    setThroughputInterval(handleChartFilter(data));
  };
  // Throughput code block ----------------------------------

  return (
    <div className="relative">
      {/* <ComingSoon shrink={true} scaleValue={.9} comingYpos='-20%' /> */}
      <div className="flex items-center px-[1.8rem] py-[1rem] rounded overflow-hidden bg-[#18191b] max-w-[50%] w-[19.0625rem]">
        <div className="flex justify-center items-center rounded rounded-full border border-[3px] border-[#41361c] w-[4.5rem] h-[4.5rem]">
          <Image
            preview={false}
            width={20}
            className="w-[1.5em] h-[1.5e]"
            src="/icons/yellowPencil.png"
            alt="Logo"
          />
        </div>
        <div className="flex items-baseline justify-start ml-[1.3rem] mt-[.25rem]">
          <Text_32_700_FFFFFF>
            {data?.endpoints_count ? data?.endpoints_count : 0}
          </Text_32_700_FFFFFF>
          <Text_20_400_FFFFFF className="ml-[.6rem] tracking-wider">
            {data?.endpoints_count == 1 ? "Endpoint" : "Endpoints"}
          </Text_20_400_FFFFFF>
        </div>
      </div>
      <div className="flex flex-wrap align-start justify-between gap-[1.1rem] pt-[0.9375rem] pb-[2rem]">
        <div className="cardBG w-[49.1%] cardSetTwo  py-[1.9rem] px-[1.65rem] border border-[#1F1F1F] rounded-md">
          <div className="flex justify-between align-center">
            <Text_19_600_EEEEEE>Request count</Text_19_600_EEEEEE>
            <Segmented
              options={segmentOptions}
              value={segmentOptions.find(
                (opt) => handleChartFilter(opt) === modelRequestInterval
              )} // Ensure correct default selection
              onChange={(value) => {
                handleModelChange(value); // string
              }}
              className="antSegmented rounded-md text-[#EEEEEE] font-[400] bg-[transparent] border border-[#4D4D4D] border-[.53px] p-[0]"
            />
          </div>
          {/* <p className="text-[0.8125rem] text-[#757575] leading-[100%] font-[400] mt-[0.95rem]">For the top 5 models</p> */}
          {modleChartData?.data?.length ? (
            <>
              <div className="flex flex-col items-start	mt-[1.3rem]">
                <p className="text-[1.625rem] text-[#EEEEEE] leading-[100%] font-[400] mb-0">
                  {Number(extraChartDetails.modelUsage.total_value).toFixed(2)}
                </p>
                <div
                  className={`flex ${
                    Number(extraChartDetails.modelUsage.avg) >= 0
                      ? "text-[#479D5F] bg-[#122F1140]"
                      : "bg-[#861A1A33] text-[#EC7575]"
                  } rounded-md items-center px-[.45rem] mb-[.1rem] h-[1.35rem] mt-[0.82rem]`}
                >
                  <span className="font-[400] text-[0.8125rem] leading-[100%]">
                    Avg. {Number(extraChartDetails.modelUsage.avg).toFixed(2)}%{" "}
                  </span>
                  {Number(extraChartDetails.modelUsage.avg) >= 0 ? (
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
              <div className="h-[232px]">
                <BarChart
                  key={modleChartData?.data.length}
                  data={modleChartData}
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
        <div className="cardBG w-[49.1%] cardSetTwo  py-[1.9rem] px-[1.65rem] border border-[#1F1F1F] rounded-md">
          <div className="flex justify-between align-center">
            <Text_19_600_EEEEEE>Token Metrics</Text_19_600_EEEEEE>
            <Segmented
              options={segmentOptions}
              value={segmentOptions.find(
                (opt) => handleChartFilter(opt) === averageInterval
              )} // Ensure correct default selection
              onChange={(value) => {
                handleAverageChange(value); // string
              }}
              className="antSegmented rounded-md text-[#EEEEEE] font-[400] bg-[transparent] border border-[#4D4D4D] border-[.53px] p-[0]"
            />
          </div>
          {averageChartData?.source?.length ? (
            <>
              
              <div className="h-[232px]">
                <TokenMetricsChart
                  key={averageChartData?.source?.length}
                  data={averageChartData}
                  extraChartDetails={extraChartDetails}
                />
              </div>
            </>
          ) : (
            <NoChartData
              textMessage="Once the data is available, we will populate a bar chart for you representing Token Metrics"
              image="/images/dashboard/noData.png"
            ></NoChartData>
          )}
        </div>
        
        {/* TTFT Chart */}
        <div className="cardBG w-[49.1%] cardSetTwo  py-[1.9rem] px-[1.65rem] border border-[#1F1F1F] rounded-md">
          <div className="flex justify-between align-center">
            <Text_19_600_EEEEEE>TTFT</Text_19_600_EEEEEE>
            <Segmented
              options={segmentOptions}
              value={segmentOptions.find(
                (opt) => handleChartFilter(opt) === ttftInterval
              )}
              onChange={(value) => {
                handleTtftChange(value);
              }}
              className="antSegmented rounded-md text-[#EEEEEE] font-[400] bg-[transparent] border border-[#4D4D4D] border-[.53px] p-[0]"
            />
          </div>
          {ttftChartData?.data?.length ? (
            <>
              <div className="flex flex-col items-start	mt-[1.3rem]">
                <p className="text-[1.625rem] text-[#EEEEEE] leading-[100%] font-[400] mb-0">
                  {Number(extraChartDetails.ttft.total_value).toFixed(2)} ms
                </p>
                <div
                  className={`flex ${
                    Number(extraChartDetails.ttft.avg) >= 0
                      ? "text-[#479D5F] bg-[#122F1140]"
                      : "bg-[#861A1A33] text-[#EC7575]"
                  } rounded-md items-center px-[.45rem] mb-[.1rem] h-[1.35rem] mt-[0.82rem]`}
                >
                  <span className="font-[400] text-[0.8125rem] leading-[100%]">
                    Avg. {Number(extraChartDetails.ttft.avg).toFixed(2)}%{" "}
                  </span>
                  {Number(extraChartDetails.ttft.avg) >= 0 ? (
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
              <div className="h-[232px]">
                <BarChart
                  key={ttftChartData?.data.length}
                  data={ttftChartData}
                />
              </div>
            </>
          ) : (
            <NoChartData
              textMessage="Once the data is available, we will populate a chart for you representing TTFT metrics"
              image="/images/dashboard/noData.png"
            ></NoChartData>
          )}
        </div>

        {/* Latency Chart */}
        <div className="cardBG w-[49.1%] cardSetTwo  py-[1.9rem] px-[1.65rem] border border-[#1F1F1F] rounded-md">
          <div className="flex justify-between align-center">
            <Text_19_600_EEEEEE>Latency</Text_19_600_EEEEEE>
            <Segmented
              options={segmentOptions}
              value={segmentOptions.find(
                (opt) => handleChartFilter(opt) === latencyInterval
              )}
              onChange={(value) => {
                handleLatencyChange(value);
              }}
              className="antSegmented rounded-md text-[#EEEEEE] font-[400] bg-[transparent] border border-[#4D4D4D] border-[.53px] p-[0]"
            />
          </div>
          {latencyChartData?.data?.length ? (
            <>
              <div className="flex flex-col items-start	mt-[1.3rem]">
                <p className="text-[1.625rem] text-[#EEEEEE] leading-[100%] font-[400] mb-0">
                  {Number(extraChartDetails.latency.total_value).toFixed(2)} ms
                </p>
                <div
                  className={`flex ${
                    Number(extraChartDetails.latency.avg) >= 0
                      ? "text-[#479D5F] bg-[#122F1140]"
                      : "bg-[#861A1A33] text-[#EC7575]"
                  } rounded-md items-center px-[.45rem] mb-[.1rem] h-[1.35rem] mt-[0.82rem]`}
                >
                  <span className="font-[400] text-[0.8125rem] leading-[100%]">
                    Avg. {Number(extraChartDetails.latency.avg).toFixed(2)}%{" "}
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
                </div>
              </div>
              <div className="h-[232px]">
                <BarChart
                  key={latencyChartData?.data.length}
                  data={latencyChartData}
                />
              </div>
            </>
          ) : (
            <NoChartData
              textMessage="Once the data is available, we will populate a chart for you representing Latency metrics"
              image="/images/dashboard/noData.png"
            ></NoChartData>
          )}
        </div>

        {/* Throughput Chart */}
        <div className="cardBG w-[49.1%] cardSetTwo  py-[1.9rem] px-[1.65rem] border border-[#1F1F1F] rounded-md">
          <div className="flex justify-between align-center">
            <Text_19_600_EEEEEE>Throughput</Text_19_600_EEEEEE>
            <Segmented
              options={segmentOptions}
              value={segmentOptions.find(
                (opt) => handleChartFilter(opt) === throughputInterval
              )}
              onChange={(value) => {
                handleThroughputChange(value);
              }}
              className="antSegmented rounded-md text-[#EEEEEE] font-[400] bg-[transparent] border border-[#4D4D4D] border-[.53px] p-[0]"
            />
          </div>
          {throughputChartData?.data?.length ? (
            <>
              <div className="flex flex-col items-start	mt-[1.3rem]">
                <p className="text-[1.625rem] text-[#EEEEEE] leading-[100%] font-[400] mb-0">
                  {Number(extraChartDetails.throughput.total_value).toFixed(2)} tokens/s
                </p>
                <div
                  className={`flex ${
                    Number(extraChartDetails.throughput.avg) >= 0
                      ? "text-[#479D5F] bg-[#122F1140]"
                      : "bg-[#861A1A33] text-[#EC7575]"
                  } rounded-md items-center px-[.45rem] mb-[.1rem] h-[1.35rem] mt-[0.82rem]`}
                >
                  <span className="font-[400] text-[0.8125rem] leading-[100%]">
                    Avg. {Number(extraChartDetails.throughput.avg).toFixed(2)}%{" "}
                  </span>
                  {Number(extraChartDetails.throughput.avg) >= 0 ? (
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
              <div className="h-[232px]">
                <BarChart
                  key={throughputChartData?.data.length}
                  data={throughputChartData}
                />
              </div>
            </>
          ) : (
            <NoChartData
              textMessage="Once the data is available, we will populate a chart for you representing Throughput metrics"
              image="/images/dashboard/noData.png"
            ></NoChartData>
          )}
        </div>
      </div>
    </div>
  );
};

export default AnalyticsComponent;

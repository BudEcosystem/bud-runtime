import React, { useEffect, useState } from "react";
import { useRouter } from "next/router";
import { Card, Row, Col, Statistic, Segmented, Spin } from "antd";
import {
  Text_14_600_EEEEEE,
  Text_12_400_B3B3B3,
  Text_12_600_EEEEEE,
  Text_20_400_FFFFFF,
  Text_26_600_FFFFFF,
} from "@/components/ui/text";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import Tags from "src/flows/components/DrawerTags";
import { usePrompts } from "src/hooks/usePrompts";
import ProjectTags from "src/flows/components/ProjectTags";
import { endpointStatusMapping } from "@/lib/colorMapping";

const segmentOptions = ["LAST 24 HRS", "LAST 7 DAYS", "LAST 30 DAYS"];

interface OverviewTabProps {}
const capitalize = (str: string) => str?.charAt(0).toUpperCase() + str?.slice(1).toLowerCase();

const OverviewTab: React.FC<OverviewTabProps> = () => {
  const router = useRouter();
  const { id, projectId } = router.query;
  const [timeRange, setTimeRange] = useState("weekly");
  const [agentData, setAgentData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { getPromptById } = usePrompts();

  // Check if we're in development mode
  const isDevelopmentMode = process.env.NEXT_PUBLIC_VERCEL_ENV === "development" ||
                           process.env.NODE_ENV === "development";

  const fetchAgentDetails = async () => {
    if (id && typeof id === "string") {
      try {
        setLoading(true);
        setError(null);
        const data = await getPromptById(id, projectId as string);
        setAgentData(data);
      } catch (error: any) {
        console.error("Error fetching agent details:", error);
        const errorMessage = error?.response?.data?.detail ||
                            error?.message ||
                            "Failed to load agent details. Please try again.";
        setError(errorMessage);

        // Only set fallback data in development mode
        if (isDevelopmentMode) {
          console.warn("Development mode: Using fallback data");
          setAgentData({
            id: id,
            name: "Agent Name (Dev Fallback)",
            description: "LiveMathBench can capture LLM capabilities in complex reasoning tasks, including challenging latest question sets from various mathematical competitions.",
            tags: [
              { name: "tag 1", color: "#965CDE" },
              { name: "tag 2", color: "#5CADFF" },
              { name: "tag 3", color: "#22C55E" },
            ],
            status: "Active",
            created_at: new Date().toISOString(),
            modified_at: new Date().toISOString(),
          });
        }
      } finally {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    fetchAgentDetails();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, projectId]);

  const handleChartFilter = (val: string) => {
    if (val === "LAST 24 HRS") return "daily";
    if (val === "LAST 7 DAYS") return "weekly";
    if (val === "LAST 30 DAYS") return "monthly";
    return "weekly"; // Default fallback
  };

  const handleTimeRangeChange = (value: string) => {
    setTimeRange(handleChartFilter(value));
  };

  // Mock data for charts
  const callsData = [
    { time: "03:13:55", value: 0.5 },
    { time: "09:32:55", value: 1.0 },
    { time: "09:33:55", value: 1.5 },
    { time: "09:34:55", value: 1.2 },
    { time: "09:35:55", value: 1.8 },
    { time: "09:38:55", value: 2.0 },
  ];

  const usersData = [
    { day: "Day 1", value: 10 },
    { day: "Day 2", value: 25 },
    { day: "Day 3", value: 45 },
    { day: "Day 4", value: 60 },
    { day: "Day 5", value: 75 },
    { day: "Day 6", value: 80 },
  ];

  const tokenUsageData = [
    { req: "Req 1", value: 60 },
    { req: "Req 2", value: 45 },
    { req: "Req 3", value: 55 },
    { req: "Req 4", value: 50 },
    { req: "Req 5", value: 62 },
    { req: "Req 6", value: 58 },
  ];

  const errorVsSuccessData = [
    { day: "Day 1", errors: 10, success: 40 },
    { day: "Day 2", errors: 15, success: 50 },
    { day: "Day 3", errors: 12, success: 60 },
    { day: "Day 4", errors: 18, success: 65 },
    { day: "Day 5", errors: 20, success: 70 },
    { day: "Day 6", errors: 25, success: 80 },
  ];

  const latencyData = [
    { req: "Req 1", value: 20 },
    { req: "Req 2", value: 35 },
    { req: "Req 3", value: 45 },
    { req: "Req 4", value: 60 },
    { req: "Req 5", value: 65 },
    { req: "Req 6", value: 70 },
  ];

  const ttftData = [
    { input: 10, value: 20 },
    { input: 20, value: 30 },
    { input: 30, value: 40 },
    { input: 40, value: 50 },
    { input: 50, value: 60 },
    { input: 60, value: 80 },
  ];

  const throughputData = [
    { concurrency: 10, value: 70 },
    { concurrency: 20, value: 60 },
    { concurrency: 30, value: 55 },
    { concurrency: 40, value: 58 },
    { concurrency: 50, value: 62 },
    { concurrency: 60, value: 65 },
  ];

  const TimeRangeSelector = () => (
    <Segmented
      options={segmentOptions}
      value={segmentOptions.find(
        (opt) => handleChartFilter(opt) === timeRange,
      )}
      onChange={(value) => {
        handleTimeRangeChange(value);
      }}
      className="antSegmented rounded-md text-[#EEEEEE] font-[400] bg-[transparent] border border-[#4D4D4D] border-[.53px] p-[0]"
    />
  );

  if (loading) {
    return (
      <div className="flex justify-center items-center h-96">
        <Spin size="large" />
      </div>
    );
  }

  // Error state display with retry functionality
  if (error && !agentData) {
    return (
      <div className="flex flex-col justify-center items-center h-96 gap-4">
        <div className="text-center max-w-md">
          <div className="text-[#EF4444] text-5xl mb-4">⚠️</div>
          <Text_14_600_EEEEEE className="block mb-2">
            Unable to Load Agent Details
          </Text_14_600_EEEEEE>
          <Text_12_400_B3B3B3 className="block mb-4">
            {error}
          </Text_12_400_B3B3B3>
          <button
            onClick={fetchAgentDetails}
            className="px-6 py-2 bg-[#965CDE] hover:bg-[#7B4AB8] text-white rounded-md transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Show warning banner if using fallback data in development
  const showDevWarning = isDevelopmentMode && error && agentData;

  return (
    <div className="pb-8">
      {/* Development Mode Warning Banner */}
      {showDevWarning && (
        <div className="mb-4 p-4 bg-[#FFA500] bg-opacity-10 border border-[#FFA500] rounded-lg flex items-start gap-3">
          <div className="text-[#FFA500] text-xl">⚠️</div>
          <div className="flex-1">
            <Text_12_600_EEEEEE className="block mb-1 text-[#FFA500]">
              Development Mode - Using Fallback Data
            </Text_12_600_EEEEEE>
            <Text_12_400_B3B3B3 className="block">
              {error}
            </Text_12_400_B3B3B3>
          </div>
          <button
            onClick={fetchAgentDetails}
            className="px-4 py-1 bg-[#FFA500] hover:bg-[#FF8C00] text-white rounded text-xs transition-colors"
          >
            Retry
          </button>
        </div>
      )}
      {/* Agent Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2 pt-[.5rem]">
          <Text_26_600_FFFFFF className="text-[#EEE]">
            {agentData?.name}
          </Text_26_600_FFFFFF>
          <ProjectTags color={endpointStatusMapping[capitalize(agentData?.status)]} name={capitalize(agentData?.status)}/>
        </div>
        <Text_12_400_B3B3B3 className="max-w-[850px] mb-3">
          {agentData?.description || 'LiveMathBench can capture LLM capabilities in complex reasoning tasks, including challenging latest question sets from various mathematical competitions.'}
        </Text_12_400_B3B3B3>
        <div className="flex items-center gap-2 flex-wrap">
          {agentData?.tags?.map((tag: any, index: number) => (
            <Tags
              textClass="text-[.75rem]"
              key={index}
              name={tag.name}
              color={tag.color}
            />
          ))}
        </div>
      </div>

      {/* Cost Metrics */}
      <Row gutter={[16, 16]} className="mb-6">
        <Col span={8}>
          <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6">
            <Text_12_400_B3B3B3 className="mb-2">P 95 Cost / Request</Text_12_400_B3B3B3>
            <Text_20_400_FFFFFF>2.4k USD</Text_20_400_FFFFFF>
          </div>
        </Col>
        <Col span={8}>
          <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6">
            <Text_12_400_B3B3B3 className="mb-2">Max Cost / Request</Text_12_400_B3B3B3>
            <Text_20_400_FFFFFF>2.4k USD</Text_20_400_FFFFFF>
          </div>
        </Col>
        <Col span={8}>
          <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6">
            <Text_12_400_B3B3B3 className="mb-2">Max Cost / Request</Text_12_400_B3B3B3>
            <Text_20_400_FFFFFF>2.4k USD</Text_20_400_FFFFFF>
          </div>
        </Col>
      </Row>

      {/* Charts Grid */}
      <Row gutter={[16, 16]}>
        {/* Calls Chart */}
        <Col span={24}>
          <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6">
            <div className="flex justify-between items-center mb-4">
              <div>
                <Text_14_600_EEEEEE>Calls</Text_14_600_EEEEEE>
                <Text_12_400_B3B3B3 className="block mt-1">Description</Text_12_400_B3B3B3>
              </div>
              <TimeRangeSelector />
            </div>
            <Text_20_400_FFFFFF className="mb-4">127 Calls</Text_20_400_FFFFFF>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={callsData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1F1F1F" />
                <XAxis dataKey="time" stroke="#B3B3B3" style={{ fontSize: '12px' }} />
                <YAxis stroke="#B3B3B3" style={{ fontSize: '12px' }} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#101010", border: "1px solid #1F1F1F" }}
                  labelStyle={{ color: "#EEEEEE" }}
                />
                <Line type="monotone" dataKey="value" stroke="#965CDE" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Col>

        {/* Users Chart */}
        <Col span={12}>
          <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6">
            <div className="flex justify-between items-center mb-4">
              <div>
                <Text_14_600_EEEEEE>Users</Text_14_600_EEEEEE>
                <Text_12_400_B3B3B3 className="block mt-1">Description</Text_12_400_B3B3B3>
              </div>
              <TimeRangeSelector />
            </div>
            <div className="mb-2">
              <Text_20_400_FFFFFF>50</Text_20_400_FFFFFF>
              <Text_12_400_B3B3B3 className="text-green-500 ml-2">+61.05%</Text_12_400_B3B3B3>
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={usersData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1F1F1F" />
                <XAxis dataKey="day" stroke="#B3B3B3" style={{ fontSize: '12px' }} />
                <YAxis stroke="#B3B3B3" style={{ fontSize: '12px' }} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#101010", border: "1px solid #1F1F1F" }}
                  labelStyle={{ color: "#EEEEEE" }}
                />
                <Line type="monotone" dataKey="value" stroke="#965CDE" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Col>

        {/* Token Usage Chart */}
        <Col span={12}>
          <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6">
            <div className="flex justify-between items-center mb-4">
              <div>
                <Text_14_600_EEEEEE>Token Usage</Text_14_600_EEEEEE>
                <Text_12_400_B3B3B3 className="block mt-1">For the top 6 models</Text_12_400_B3B3B3>
              </div>
              <TimeRangeSelector />
            </div>
            <div className="mb-2">
              <Text_20_400_FFFFFF>127K</Text_20_400_FFFFFF>
              <Text_12_400_B3B3B3 className="text-green-500 ml-2">+17.01%</Text_12_400_B3B3B3>
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={tokenUsageData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1F1F1F" />
                <XAxis dataKey="req" stroke="#B3B3B3" style={{ fontSize: '12px' }} />
                <YAxis stroke="#B3B3B3" style={{ fontSize: '12px' }} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#101010", border: "1px solid #1F1F1F" }}
                  labelStyle={{ color: "#EEEEEE" }}
                />
                <Bar dataKey="value" fill="#965CDE" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Col>

        {/* Error vs Successful Requests */}
        <Col span={12}>
          <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6">
            <div className="flex justify-between items-center mb-4">
              <div>
                <Text_14_600_EEEEEE>Error vs Successful requests</Text_14_600_EEEEEE>
                <Text_12_400_B3B3B3 className="block mt-1">Description</Text_12_400_B3B3B3>
              </div>
              <TimeRangeSelector />
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={errorVsSuccessData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1F1F1F" />
                <XAxis dataKey="day" stroke="#B3B3B3" style={{ fontSize: '12px' }} />
                <YAxis stroke="#B3B3B3" style={{ fontSize: '12px' }} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#101010", border: "1px solid #1F1F1F" }}
                  labelStyle={{ color: "#EEEEEE" }}
                />
                <Legend wrapperStyle={{ color: "#B3B3B3", fontSize: "12px" }} />
                <Line type="monotone" dataKey="errors" stroke="#EF4444" strokeWidth={2} name="Error Requests" />
                <Line type="monotone" dataKey="success" stroke="#22C55E" strokeWidth={2} name="Successful Requests" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Col>

        {/* E2E Latency vs Requests */}
        <Col span={12}>
          <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6">
            <div className="flex justify-between items-center mb-4">
              <div>
                <Text_14_600_EEEEEE>E2E Latency vs Requests</Text_14_600_EEEEEE>
                <Text_12_400_B3B3B3 className="block mt-1">Description</Text_12_400_B3B3B3>
              </div>
              <TimeRangeSelector />
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={latencyData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1F1F1F" />
                <XAxis dataKey="req" stroke="#B3B3B3" style={{ fontSize: '12px' }} />
                <YAxis stroke="#B3B3B3" style={{ fontSize: '12px' }} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#101010", border: "1px solid #1F1F1F" }}
                  labelStyle={{ color: "#EEEEEE" }}
                />
                <Line type="monotone" dataKey="value" stroke="#965CDE" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Col>

        {/* TTFT vs Inputs */}
        <Col span={12}>
          <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6">
            <div className="flex justify-between items-center mb-4">
              <div>
                <Text_14_600_EEEEEE>TTFT vs Inputs</Text_14_600_EEEEEE>
                <Text_12_400_B3B3B3 className="block mt-1">Description</Text_12_400_B3B3B3>
              </div>
              <TimeRangeSelector />
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={ttftData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1F1F1F" />
                <XAxis dataKey="input" label={{ value: "Input Tokens", position: "insideBottom", offset: -5, fill: "#B3B3B3" }} stroke="#B3B3B3" style={{ fontSize: '12px' }} />
                <YAxis label={{ value: "TTFT", angle: -90, position: "insideLeft", fill: "#B3B3B3" }} stroke="#B3B3B3" style={{ fontSize: '12px' }} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#101010", border: "1px solid #1F1F1F" }}
                  labelStyle={{ color: "#EEEEEE" }}
                />
                <Line type="monotone" dataKey="value" stroke="#965CDE" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Col>

        {/* Average Throughput/User by Concurrency */}
        <Col span={12}>
          <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6">
            <div className="flex justify-between items-center mb-4">
              <div>
                <Text_14_600_EEEEEE>Average Throughput/User by Concurrency</Text_14_600_EEEEEE>
                <Text_12_400_B3B3B3 className="block mt-1">Description</Text_12_400_B3B3B3>
              </div>
              <TimeRangeSelector />
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={throughputData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1F1F1F" />
                <XAxis dataKey="concurrency" label={{ value: "Average Throughput/User", position: "insideBottom", offset: -5, fill: "#B3B3B3" }} stroke="#B3B3B3" style={{ fontSize: '12px' }} />
                <YAxis label={{ value: "Concurrency", angle: -90, position: "insideLeft", fill: "#B3B3B3" }} stroke="#B3B3B3" style={{ fontSize: '12px' }} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#101010", border: "1px solid #1F1F1F" }}
                  labelStyle={{ color: "#EEEEEE" }}
                />
                <Bar dataKey="value" fill="#965CDE" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Col>

        {/* Placeholder Charts */}
        <Col span={12}>
          <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6">
            <div className="flex justify-between items-center mb-4">
              <div>
                <Text_14_600_EEEEEE>Lorem Ipsum</Text_14_600_EEEEEE>
                <Text_12_400_B3B3B3 className="block mt-1">Once the data is available, we will populate a line chart for you representing.</Text_12_400_B3B3B3>
              </div>
            </div>
            <div className="h-[200px] flex items-center justify-center border border-dashed border-[#2F2F2F] rounded">
              <div className="text-center">
                <div className="text-[#606060] text-4xl mb-2">📊</div>
                <Text_12_400_B3B3B3>No data available</Text_12_400_B3B3B3>
              </div>
            </div>
          </div>
        </Col>

        <Col span={12}>
          <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6">
            <div className="flex justify-between items-center mb-4">
              <div>
                <Text_14_600_EEEEEE>Lorem Ipsum</Text_14_600_EEEEEE>
                <Text_12_400_B3B3B3 className="block mt-1">Once the data is available, we will populate a line chart for you representing.</Text_12_400_B3B3B3>
              </div>
            </div>
            <div className="h-[200px] flex items-center justify-center border border-dashed border-[#2F2F2F] rounded">
              <div className="text-center">
                <div className="text-[#606060] text-4xl mb-2">📊</div>
                <Text_12_400_B3B3B3>No data available</Text_12_400_B3B3B3>
              </div>
            </div>
          </div>
        </Col>
      </Row>
    </div>
  );
};

export default OverviewTab;

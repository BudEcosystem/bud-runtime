import React, { useEffect, useState } from "react";
import { useRouter } from "next/router";
import {
  Card,
  Descriptions,
  Tag,
  Spin,
  Button,
  Divider,
  Typography,
  Row,
  Col,
  Statistic,
  message,
  Tooltip,
  Flex,
  Alert,
} from "antd";
import {
  ArrowLeftOutlined,
  CopyOutlined,
  DownloadOutlined,
} from "@ant-design/icons";
import { format } from "date-fns";
import { formatTimestampWithTZ } from "@/utils/formatDate";
import { copyToClipboard as copyText } from "@/utils/clipboard";
import { AppRequest } from "src/pages/api/requests";
import { useLoaderOnLoding } from "src/hooks/useLoaderOnLoading";
import {
  Text_11_400_808080,
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_12_600_EEEEEE,
  Text_14_600_EEEEEE,
  Text_16_600_FFFFFF,
  Text_20_400_FFFFFF,
  Text_26_600_FFFFFF,
} from "@/components/ui/text";
import DashBoardLayout from "../../home/layout";
import { CustomBreadcrumb } from "@/components/ui/bud/card/DrawerBreadCrumbNavigation";
import BackButton from "@/components/ui/bud/drawer/BackButton";
import ProjectTags from "src/flows/components/ProjectTags";
import { endpointStatusMapping } from "@/lib/colorMapping";
import { errorToast } from "@/components/toast";

const { Title, Text, Paragraph } = Typography;

interface GatewayMetadata {
  // Network & Request Info
  client_ip?: string | null;
  proxy_chain?: string | null;
  protocol_version?: string | null;
  method?: string | null;
  path?: string | null;
  query_params?: string | null;
  request_headers?: Record<string, string> | null;
  body_size?: number | null;

  // Authentication
  api_key_id?: string | null;
  auth_method?: string | null;
  user_id?: string | null;

  // Client Information
  user_agent?: string | null;
  device_type?: string | null;
  browser_name?: string | null;
  browser_version?: string | null;
  os_name?: string | null;
  os_version?: string | null;
  is_bot?: boolean;

  // Geographic Information
  country_code?: string | null;
  country_name?: string | null;
  region?: string | null;
  city?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  timezone?: string | null;
  asn?: number | null;
  isp?: string | null;

  // Performance Metrics
  gateway_processing_ms?: number;
  total_duration_ms?: number;
  status_code?: number;
  response_size?: number | null;
  response_headers?: Record<string, string> | null;

  // Model & Routing
  routing_decision?: string | null;
  model_version?: string | null;

  // Error Information
  error_type?: string | null;
  error_message?: string | null;

  // Blocking Information
  is_blocked?: boolean;
  block_reason?: string | null;
  block_rule_id?: string | null;

  // Additional
  tags?: Record<string, string> | null;
}

interface InferenceDetail {
  inference_id: string;
  timestamp: string;
  model_name: string;
  model_display_name?: string;
  model_provider: string;
  model_id: string;
  project_id: string;
  project_name?: string;
  endpoint_id: string;
  endpoint_name?: string;
  endpoint_type?: string;
  system_prompt?: string;
  messages: Array<{ role: string; content: any }>;
  output: string;
  function_name?: string;
  variant_name?: string;
  episode_id?: string;
  input_tokens: number;
  output_tokens: number;
  response_time_ms: number;
  ttft_ms?: number;
  processing_time_ms?: number;
  request_ip?: string;
  request_arrival_time: string;
  request_forward_time: string;
  is_success: boolean;
  cached: boolean;
  finish_reason?: string;
  cost?: number;
  error_code?: string;
  error_message?: string;
  error_type?: string;
  status_code?: number;
  raw_request?: string;
  raw_response?: string;
  gateway_request?: any;
  gateway_response?: any;
  gateway_metadata?: GatewayMetadata;
  feedback_count: number;
  average_rating?: number;
}

const ObservabilityDetailPage: React.FC = () => {
  const router = useRouter();
  const { id } = router.query;
  const [inferenceData, setInferenceData] = useState<InferenceDetail | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isMounted, setIsMounted] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  useLoaderOnLoding(loading);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  useEffect(() => {
    if (id && typeof id === "string") {
      fetchInferenceDetail(id);
    }
  }, [id]);

  const fetchInferenceDetail = async (inferenceId: string) => {
    try {
      setLoading(true);
      setError(null);
      const response = await AppRequest.Get(
        `/metrics/inferences/${inferenceId}`,
      );
      if (response.data) {
        setInferenceData(response.data);
      }
    } catch (error: any) {
      const errorMsg =
        error?.response?.data?.message ||
        error?.message ||
        "Failed to fetch observability details";
      errorToast(errorMsg);
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = async (text: string, id: string) => {
    await copyText(text, {
      onSuccess: () => {
        setCopiedId(id);
        setTimeout(() => {
          setCopiedId(null);
        }, 2000);
      },
      onError: () => errorToast("Failed to copy to clipboard"),
    });
  };

  const downloadJson = (data: any, filename: string) => {
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${filename}_${inferenceData?.inference_id}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const goBack = () => {
    router.push("/observability");
  };

  const HeaderContent = () => {
    return (
      <Flex align="center" justify="between">
        {isMounted && (
          <Flex align="center" justify="start">
            <BackButton onClick={goBack} />
            <CustomBreadcrumb
              data={["Observability", "Details"]}
              urls={["/observability", ""]}
            />
          </Flex>
        )}
      </Flex>
    );
  };

  if (loading) {
    return (
      <DashBoardLayout>
        <div>Loading...</div>
      </DashBoardLayout>
    );
  }

  if (error || !inferenceData) {
    return (
      <DashBoardLayout>
        <div className="boardPageView">
          <div className="boardPageTop pt-0 !mb-[.4rem] px-[0]">
            <div className="px-[1.2rem] pt-[1.05rem] pb-[1.15rem] mb-[2.1rem] border-b-[1px] border-b-[#1F1F1F]">
              <HeaderContent />
            </div>
          </div>
          <div className="px-[3.5rem]">
            <div className="flex items-center flex-col border border-[#1F1F1F] rounded-[.4rem] px-[1.4rem] py-[1.3rem] bg-[#101010] text-center">
              <div className="py-12">
                <Text_16_600_FFFFFF className="text-red-500 mb-4">
                  {error || "Failed to load observability details"}
                </Text_16_600_FFFFFF>
                <Text_12_400_EEEEEE className="text-gray-400 mb-6">
                  The observability details could not be loaded. This might be
                  due to a temporary service issue.
                </Text_12_400_EEEEEE>
                <Button
                  type="primary"
                  onClick={() => fetchInferenceDetail(id as string)}
                >
                  Try Again
                </Button>
              </div>
            </div>
          </div>
        </div>
      </DashBoardLayout>
    );
  }

  return (
    <DashBoardLayout>
      <div className="boardPageView">
        <div className="boardPageTop pt-0 !mb-[.4rem] px-[0]">
          <div className="px-[1.2rem] pt-[1.05rem] pb-[1.15rem] mb-[2.1rem] border-b-[1px] border-b-[#1F1F1F]">
            <HeaderContent />
          </div>
          <div className="flex items-center gap-4 justify-between flex-row px-[3.5rem]">
            <div className="w-full">
              <Text_26_600_FFFFFF className="text-[#EEE]">
                Observability Details
              </Text_26_600_FFFFFF>
            </div>
          </div>
        </div>
        <div className="projectDetailsDiv pb-3 mt-[1.1rem] px-[3.5rem] relative">
          {/* Overview & Details - Combined Section */}
          <div className="flex items-center flex-col border border-[#1F1F1F] rounded-[.4rem] px-[1.4rem] py-[1.3rem] pb-[1.1rem] w-full bg-[#101010] mb-[1.6rem]">
            <div className="w-full">
              <Text_14_600_EEEEEE className="text-[#EEEEEE] mb-4">
                Overview
              </Text_14_600_EEEEEE>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <Text_12_400_B3B3B3 className="mb-1">
                    Inference ID
                  </Text_12_400_B3B3B3>
                  <div className="flex items-center gap-2">
                    <Text_12_600_EEEEEE
                      className="truncate max-w-[200px]"
                      title={inferenceData.inference_id}
                    >
                      {inferenceData.inference_id}
                    </Text_12_600_EEEEEE>
                    <Tooltip
                      title={copiedId === "inference_id" ? "Copied!" : "Copy"}
                      placement="top"
                    >
                      <Button
                        type="text"
                        size="small"
                        icon={<CopyOutlined />}
                        onClick={() =>
                          copyToClipboard(
                            inferenceData.inference_id,
                            "inference_id",
                          )
                        }
                        className="text-[#B3B3B3] hover:text-[#EEEEEE] min-w-[24px]"
                      />
                    </Tooltip>
                  </div>
                </div>

                <div>
                  <Text_12_400_B3B3B3 className="mb-1">
                    Model
                  </Text_12_400_B3B3B3>
                  <Text_12_600_EEEEEE>
                    {inferenceData.model_display_name ||
                      inferenceData.model_name}
                  </Text_12_600_EEEEEE>
                </div>

                <div>
                  <Text_12_400_B3B3B3 className="mb-1">
                    Endpoint
                  </Text_12_400_B3B3B3>
                  <Text_12_600_EEEEEE>
                    {inferenceData.endpoint_name || "Unknown Endpoint"}
                  </Text_12_600_EEEEEE>
                </div>

                <div>
                  <Text_12_400_B3B3B3 className="mb-1">Type</Text_12_400_B3B3B3>
                  <Tag
                    color={
                      inferenceData.endpoint_type === "embedding"
                        ? "purple"
                        : "blue"
                    }
                  >
                    {inferenceData.endpoint_type || "chat"}
                  </Tag>
                </div>

                <div>
                  <Text_12_400_B3B3B3 className="mb-1">
                    Project
                  </Text_12_400_B3B3B3>
                  <Text_12_600_EEEEEE>
                    {inferenceData.project_name || "Unknown Project"}
                  </Text_12_600_EEEEEE>
                </div>

                <div>
                  <Text_12_400_B3B3B3 className="mb-1">
                    Timestamp
                  </Text_12_400_B3B3B3>
                  <Text_12_600_EEEEEE>
                    {formatTimestampWithTZ(inferenceData.timestamp)}
                  </Text_12_600_EEEEEE>
                </div>

                <div>
                  <Text_12_400_B3B3B3 className="mb-1">
                    Cached
                  </Text_12_400_B3B3B3>
                  <div>
                    <Tag color={inferenceData.cached ? "success" : "default"}>
                      {inferenceData.cached ? "Yes" : "No"}
                    </Tag>
                  </div>
                </div>

                {inferenceData.finish_reason && (
                  <div>
                    <Text_12_400_B3B3B3 className="mb-1">
                      Finish Reason
                    </Text_12_400_B3B3B3>
                    <Text_12_600_EEEEEE>
                      {inferenceData.finish_reason}
                    </Text_12_600_EEEEEE>
                  </div>
                )}

                <div>
                  <Text_12_400_B3B3B3 className="mb-1">
                    Status
                  </Text_12_400_B3B3B3>
                  <div>
                    <ProjectTags
                      name={inferenceData.is_success ? "Success" : "Failed"}
                      color={
                        endpointStatusMapping[
                          inferenceData.is_success ? "Success" : "Failed"
                        ]
                      }
                      textClass="text-[.75rem]"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Gateway Metadata */}
          {inferenceData.gateway_metadata && inferenceData.gateway_metadata?.client_ip && (
            <div className="flex items-center flex-col border border-[#1F1F1F] rounded-[.4rem] px-[1.4rem] py-[1.3rem] pb-[1.1rem] w-full bg-[#101010] mb-[1.6rem]">
              <div className="w-full">
                <Text_14_600_EEEEEE className="text-[#EEEEEE] mb-4">
                  Request Metadata
                </Text_14_600_EEEEEE>

                <div className="grid grid-cols-3 gap-4">
                  {/* Network Information */}
                  {inferenceData.gateway_metadata.client_ip && (
                    <div>
                      <Text_12_400_B3B3B3 className="mb-1">
                        Client IP
                      </Text_12_400_B3B3B3>
                      <Text_12_600_EEEEEE>
                        {inferenceData.gateway_metadata.client_ip}
                      </Text_12_600_EEEEEE>
                    </div>
                  )}
                  {inferenceData.gateway_metadata.method && (
                    <div>
                      <Text_12_400_B3B3B3 className="mb-1">
                        Method
                      </Text_12_400_B3B3B3>
                      <Tag
                        color={
                          inferenceData.gateway_metadata.method === "POST"
                            ? "blue"
                            : "green"
                        }
                      >
                        {inferenceData.gateway_metadata.method}
                      </Tag>
                    </div>
                  )}
                  {inferenceData.gateway_metadata.path && (
                    <div>
                      <Text_12_400_B3B3B3 className="mb-1">
                        Path
                      </Text_12_400_B3B3B3>
                      <Text_12_600_EEEEEE className="font-mono text-xs">
                        {inferenceData.gateway_metadata.path}
                      </Text_12_600_EEEEEE>
                    </div>
                  )}
                  {inferenceData.gateway_metadata.protocol_version && (
                    <div>
                      <Text_12_400_B3B3B3 className="mb-1">
                        Protocol
                      </Text_12_400_B3B3B3>
                      <Text_12_600_EEEEEE>
                        {inferenceData.gateway_metadata.protocol_version}
                      </Text_12_600_EEEEEE>
                    </div>
                  )}
                  {inferenceData.gateway_metadata.status_code && (
                    <div>
                      <Text_12_400_B3B3B3 className="mb-1">
                        Status Code
                      </Text_12_400_B3B3B3>
                      <Tag
                        color={
                          inferenceData.gateway_metadata.status_code >= 200 &&
                          inferenceData.gateway_metadata.status_code < 300
                            ? "success"
                            : "error"
                        }
                      >
                        {inferenceData.gateway_metadata.status_code}
                      </Tag>
                    </div>
                  )}

                  {/* Client Information */}
                  {inferenceData.gateway_metadata.device_type && (
                    <div>
                      <Text_12_400_B3B3B3 className="mb-1">
                        Device Type
                      </Text_12_400_B3B3B3>
                      <Tag
                        color={
                          inferenceData.gateway_metadata.device_type ===
                          "mobile"
                            ? "green"
                            : inferenceData.gateway_metadata.device_type ===
                                "tablet"
                              ? "blue"
                              : inferenceData.gateway_metadata.device_type ===
                                  "desktop"
                                ? "purple"
                                : "default"
                        }
                      >
                        {inferenceData.gateway_metadata.device_type}
                        {inferenceData.gateway_metadata.is_bot && " (Bot)"}
                      </Tag>
                    </div>
                  )}
                  {inferenceData.gateway_metadata.browser_name && (
                    <div>
                      <Text_12_400_B3B3B3 className="mb-1">
                        Browser
                      </Text_12_400_B3B3B3>
                      <Text_12_600_EEEEEE>
                        {inferenceData.gateway_metadata.browser_name}
                        {inferenceData.gateway_metadata.browser_version &&
                          ` v${inferenceData.gateway_metadata.browser_version}`}
                      </Text_12_600_EEEEEE>
                    </div>
                  )}
                  {inferenceData.gateway_metadata.os_name && (
                    <div>
                      <Text_12_400_B3B3B3 className="mb-1">
                        Operating System
                      </Text_12_400_B3B3B3>
                      <Text_12_600_EEEEEE>
                        {inferenceData.gateway_metadata.os_name}
                        {inferenceData.gateway_metadata.os_version &&
                          ` v${inferenceData.gateway_metadata.os_version}`}
                      </Text_12_600_EEEEEE>
                    </div>
                  )}

                  {/* Geographic Information */}
                  {(inferenceData.gateway_metadata.city ||
                    inferenceData.gateway_metadata.region ||
                    inferenceData.gateway_metadata.country_name) && (
                    <div>
                      <Text_12_400_B3B3B3 className="mb-1">
                        Location
                      </Text_12_400_B3B3B3>
                      <Text_12_600_EEEEEE>
                        {[
                          inferenceData.gateway_metadata.city,
                          inferenceData.gateway_metadata.region,
                          inferenceData.gateway_metadata.country_name,
                        ]
                          .filter(Boolean)
                          .join(", ")}
                        {inferenceData.gateway_metadata.country_code &&
                          ` (${inferenceData.gateway_metadata.country_code.toUpperCase()})`}
                      </Text_12_600_EEEEEE>
                    </div>
                  )}
                  {inferenceData.gateway_metadata.timezone && (
                    <div>
                      <Text_12_400_B3B3B3 className="mb-1">
                        Timezone
                      </Text_12_400_B3B3B3>
                      <Text_12_600_EEEEEE>
                        {inferenceData.gateway_metadata.timezone}
                      </Text_12_600_EEEEEE>
                    </div>
                  )}
                  {inferenceData.gateway_metadata.isp && (
                    <div>
                      <Text_12_400_B3B3B3 className="mb-1">
                        ISP
                      </Text_12_400_B3B3B3>
                      <Text_12_600_EEEEEE>
                        {inferenceData.gateway_metadata.isp}
                      </Text_12_600_EEEEEE>
                    </div>
                  )}
                  {inferenceData.gateway_metadata.asn && (
                    <div>
                      <Text_12_400_B3B3B3 className="mb-1">
                        AS Number
                      </Text_12_400_B3B3B3>
                      <Text_12_600_EEEEEE>
                        AS{inferenceData.gateway_metadata.asn}
                      </Text_12_600_EEEEEE>
                    </div>
                  )}

                  {/* Authentication Information */}
                  {inferenceData.gateway_metadata.auth_method && (
                    <div>
                      <Text_12_400_B3B3B3 className="mb-1">
                        Auth Method
                      </Text_12_400_B3B3B3>
                      <Text_12_600_EEEEEE>
                        {inferenceData.gateway_metadata.auth_method}
                      </Text_12_600_EEEEEE>
                    </div>
                  )}
                  {inferenceData.gateway_metadata.api_key_id && (
                    <div>
                      <Text_12_400_B3B3B3 className="mb-1">
                        API Key ID
                      </Text_12_400_B3B3B3>
                      <Text_12_600_EEEEEE className="font-mono text-xs">
                        {inferenceData.gateway_metadata.api_key_id}
                      </Text_12_600_EEEEEE>
                    </div>
                  )}
                  {inferenceData.gateway_metadata.user_id && (
                    <div>
                      <Text_12_400_B3B3B3 className="mb-1">
                        User ID
                      </Text_12_400_B3B3B3>
                      <Text_12_600_EEEEEE className="font-mono text-xs">
                        {inferenceData.gateway_metadata.user_id}
                      </Text_12_600_EEEEEE>
                    </div>
                  )}
                </div>

                {/* User Agent - full width at the bottom if exists */}
                {inferenceData.gateway_metadata.user_agent && (
                  <div className="mt-4">
                    <Text_12_400_B3B3B3 className="mb-1">
                      User Agent
                    </Text_12_400_B3B3B3>
                    <div className="bg-[#1A1A1A] p-2 rounded">
                      <Text_12_400_B3B3B3 className="font-mono text-xs break-all">
                        {inferenceData.gateway_metadata.user_agent}
                      </Text_12_400_B3B3B3>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Performance Metrics */}
          <div className="flex items-center flex-col border border-[#1F1F1F] rounded-[.4rem] px-[1.4rem] py-[1.3rem] pb-[1.1rem] w-full bg-[#101010] mb-[1.6rem]">
            <div className="w-full">
              <Text_14_600_EEEEEE className="text-[#EEEEEE] mb-4">
                Performance Metrics
              </Text_14_600_EEEEEE>

              <div className="flex justify-between items-center">
                {inferenceData.endpoint_type !== "embedding" &&
                  inferenceData.endpoint_type !== "audio_transcription" &&
                  inferenceData.endpoint_type !== "audio_translation" &&
                  inferenceData.endpoint_type !== "text_to_speech" &&
                  inferenceData.endpoint_type !== "image_generation" &&
                  inferenceData.endpoint_type !== "moderation" && (
                    <>
                      <div className="text-center">
                        <div className="text-[1.25rem] font-[600] text-[#3b82f6] mb-1">
                          {inferenceData.input_tokens.toLocaleString()}
                        </div>
                        <Text_12_400_B3B3B3>Input Tokens</Text_12_400_B3B3B3>
                      </div>

                      <div className="text-center">
                        <div className="text-[1.25rem] font-[600] text-[#3b82f6] mb-1">
                          {inferenceData.output_tokens.toLocaleString()}
                        </div>
                        <Text_12_400_B3B3B3>Output Tokens</Text_12_400_B3B3B3>
                      </div>

                      <div className="text-center">
                        <div className="text-[1.25rem] font-[600] text-[#8b5cf6] mb-1">
                          {(
                            inferenceData.input_tokens +
                            inferenceData.output_tokens
                          ).toLocaleString()}
                        </div>
                        <Text_12_400_B3B3B3>Total Tokens</Text_12_400_B3B3B3>
                      </div>
                    </>
                  )}

                {inferenceData.ttft_ms && (
                  <div className="text-center">
                    <div className="text-[1.25rem] font-[600] text-[#06b6d4] mb-1">
                      {formatDuration(inferenceData.ttft_ms)}
                    </div>
                    <Text_12_400_B3B3B3>TTFT</Text_12_400_B3B3B3>
                  </div>
                )}
                <div className="text-center">
                  <div className="text-[1.25rem] font-[600] text-[#22c55e] mb-1">
                    {formatDuration(inferenceData.response_time_ms)}
                  </div>
                  <Text_12_400_B3B3B3>End to End Latency</Text_12_400_B3B3B3>
                </div>
              </div>
            </div>
          </div>

          {/* Conversation - Only show for chat endpoint type */}
          {(!inferenceData.endpoint_type ||
            inferenceData.endpoint_type === "chat") && (inferenceData.messages && inferenceData?.messages?.length > 0) && (
            <div className="flex items-center flex-col border border-[#1F1F1F] rounded-[.4rem] px-[1.4rem] py-[1.3rem] pb-[1.1rem] w-full bg-[#101010] mb-[1.6rem]">
              <div className="w-full">
                <div className="flex justify-between items-center mb-4">
                  <Text_14_600_EEEEEE className="text-[#EEEEEE]">
                    Conversation
                  </Text_14_600_EEEEEE>
                  <Button
                    size="small"
                    icon={<DownloadOutlined />}
                    onClick={() =>
                      downloadJson(inferenceData.messages, "conversation")
                    }
                    className="bg-[#1F1F1F] border-[#1F1F1F] text-[#EEEEEE] hover:bg-[#2F2F2F]"
                  >
                    Download
                  </Button>
                </div>

                <div className="space-y-3">
                  {inferenceData.messages.map((message, index) => (
                    <div
                      key={index}
                      className={`border rounded-md p-3 ${
                        message.role === "system"
                          ? "bg-purple-900/10 border-purple-800/30"
                          : message.role === "user"
                            ? "bg-blue-900/10 border-blue-800/30"
                            : message.role === "assistant"
                              ? "bg-green-900/10 border-green-800/30"
                              : "bg-[#1A1A1A] border-[#2F2F2F]"
                      }`}
                    >
                      <div className="flex justify-between items-start mb-2">
                        <Tag
                          color={
                            message.role === "system"
                              ? "purple"
                              : message.role === "user"
                                ? "blue"
                                : message.role === "assistant"
                                  ? "green"
                                  : "default"
                          }
                        >
                          {message.role.toUpperCase()}
                        </Tag>
                        <Tooltip
                          title={
                            copiedId === `message_${index}` ? "Copied!" : "Copy"
                          }
                          placement="top"
                        >
                          <Button
                            type="text"
                            size="small"
                            icon={<CopyOutlined />}
                            onClick={() => {
                              let textToCopy = "";
                              if (typeof message.content === "string") {
                                textToCopy = message.content;
                              } else if (Array.isArray(message.content)) {
                                textToCopy = message.content
                                  .map((item: any) => {
                                    if (
                                      typeof item === "object" &&
                                      item !== null
                                    ) {
                                      return (
                                        item.text ||
                                        item.value ||
                                        JSON.stringify(item)
                                      );
                                    }
                                    return String(item);
                                  })
                                  .join("\n\n");
                              } else {
                                textToCopy = JSON.stringify(
                                  message.content,
                                  null,
                                  2,
                                );
                              }
                              copyToClipboard(textToCopy, `message_${index}`);
                            }}
                            className="text-[#B3B3B3] hover:text-[#EEEEEE]"
                          />
                        </Tooltip>
                      </div>
                      <div className="text-[#EEEEEE]">
                        {(() => {
                          // Handle different content formats
                          if (typeof message.content === "string") {
                            return (
                              <Paragraph className="mb-0 whitespace-pre-wrap text-sm text-[#EEEEEE]">
                                {message.content}
                              </Paragraph>
                            );
                          } else if (Array.isArray(message.content)) {
                            // Extract text from array of objects with either 'text' or 'value' keys
                            const textParts = message.content
                              .map((item: any) => {
                                if (typeof item === "object" && item !== null) {
                                  return (
                                    item.text ||
                                    item.value ||
                                    JSON.stringify(item)
                                  );
                                }
                                return String(item);
                              })
                              .join("\n\n");

                            return (
                              <Paragraph className="mb-0 whitespace-pre-wrap text-sm text-[#EEEEEE]">
                                {textParts}
                              </Paragraph>
                            );
                          } else {
                            // Fallback for other formats
                            return (
                              <pre className="bg-[#1A1A1A] p-3 rounded overflow-x-auto text-sm">
                                <code className="text-[#EEEEEE]">
                                  {JSON.stringify(message.content, null, 2)}
                                </code>
                              </pre>
                            );
                          }
                        })()}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Gateway Request */}
          {inferenceData.gateway_request && (
            <div className="flex items-center flex-col border border-[#1F1F1F] rounded-[.4rem] px-[1.4rem] py-[1.3rem] pb-[1.1rem] w-full bg-[#101010] mb-[1.6rem]">
              <div className="w-full">
                <div className="flex justify-between items-center mb-4">
                  <Text_14_600_EEEEEE className="text-[#EEEEEE]">
                    Raw Request
                  </Text_14_600_EEEEEE>
                  <div className="flex gap-2">
                    <Tooltip
                      title={
                        copiedId === "gateway_request" ? "Copied!" : "Copy"
                      }
                      placement="top"
                    >
                      <Button
                        size="small"
                        icon={<CopyOutlined />}
                        onClick={() => {
                          try {
                            copyToClipboard(
                              JSON.stringify(
                                inferenceData.gateway_request,
                                null,
                                2,
                              ),
                              "gateway_request",
                            );
                          } catch {
                            copyToClipboard(
                              JSON.stringify(inferenceData.gateway_request),
                              "gateway_request",
                            );
                          }
                        }}
                        className="bg-[#1F1F1F] border-[#1F1F1F] text-[#EEEEEE] hover:bg-[#2F2F2F]"
                      >
                        Copy
                      </Button>
                    </Tooltip>
                    <Button
                      size="small"
                      icon={<DownloadOutlined />}
                      onClick={() => {
                        try {
                          downloadJson(
                            inferenceData.gateway_request,
                            "gateway_request",
                          );
                        } catch {
                          downloadJson(
                            inferenceData.gateway_request,
                            "gateway_request",
                          );
                        }
                      }}
                      className="bg-[#1F1F1F] border-[#1F1F1F] text-[#EEEEEE] hover:bg-[#2F2F2F]"
                    >
                      Download
                    </Button>
                  </div>
                </div>
                <div className="bg-[#1A1A1A] border border-[#2F2F2F] rounded-md p-3 overflow-x-auto">
                  <pre className="text-[#B3B3B3] mb-0 text-sm">
                    <code>
                      {(() => {
                        try {
                          return JSON.stringify(
                            inferenceData.gateway_request,
                            null,
                            2,
                          );
                        } catch {
                          return JSON.stringify(inferenceData.gateway_request);
                        }
                      })()}
                    </code>
                  </pre>
                </div>
              </div>
            </div>
          )}

          {/* Gateway Response */}
          {inferenceData.gateway_response && (
            <div className="flex items-center flex-col border border-[#1F1F1F] rounded-[.4rem] px-[1.4rem] py-[1.3rem] pb-[1.1rem] w-full bg-[#101010] mb-[1.6rem]">
              <div className="w-full">
                <div className="flex justify-between items-center mb-4">
                  <Text_14_600_EEEEEE className="text-[#EEEEEE]">
                    Raw Response
                  </Text_14_600_EEEEEE>
                  <div className="flex gap-2">
                    <Tooltip
                      title={
                        copiedId === "gateway_response" ? "Copied!" : "Copy"
                      }
                      placement="top"
                    >
                      <Button
                        size="small"
                        icon={<CopyOutlined />}
                        onClick={() => {
                          try {
                            copyToClipboard(
                              JSON.stringify(
                                inferenceData.gateway_response,
                                null,
                                2,
                              ),
                              "gateway_response",
                            );
                          } catch {
                            copyToClipboard(
                              JSON.stringify(inferenceData.gateway_response),
                              "gateway_response",
                            );
                          }
                        }}
                        className="bg-[#1F1F1F] border-[#1F1F1F] text-[#EEEEEE] hover:bg-[#2F2F2F]"
                      >
                        Copy
                      </Button>
                    </Tooltip>
                    <Button
                      size="small"
                      icon={<DownloadOutlined />}
                      onClick={() => {
                        try {
                          downloadJson(
                            inferenceData.gateway_response,
                            "gateway_response",
                          );
                        } catch {
                          downloadJson(
                            inferenceData.gateway_response,
                            "gateway_response",
                          );
                        }
                      }}
                      className="bg-[#1F1F1F] border-[#1F1F1F] text-[#EEEEEE] hover:bg-[#2F2F2F]"
                    >
                      Download
                    </Button>
                  </div>
                </div>
                <div className="bg-[#1A1A1A] border border-[#2F2F2F] rounded-md p-3 overflow-x-auto">
                  <pre className="text-[#B3B3B3] mb-0 text-sm">
                    <code>
                      {(() => {
                        try {
                          return JSON.stringify(
                            inferenceData.gateway_response,
                            null,
                            2,
                          );
                        } catch {
                          return JSON.stringify(inferenceData.gateway_response);
                        }
                      })()}
                    </code>
                  </pre>
                </div>
              </div>
            </div>
          )}

          <div className="h-[4rem]" />
        </div>
      </div>
    </DashBoardLayout>
  );
};

export default ObservabilityDetailPage;

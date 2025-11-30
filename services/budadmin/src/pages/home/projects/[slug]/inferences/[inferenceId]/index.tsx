import React, { useEffect, useState } from "react";
import { useRouter } from "next/router";
import {
  Tag,
  Spin,
  Button,
  Typography,
  message,
  Tooltip,
  Flex,
  Alert,
} from "antd";
import {
  CopyOutlined,
  DownloadOutlined,
} from "@ant-design/icons";
import { formatTimestampWithTZ } from "@/utils/formatDate";
import { copyToClipboard as copyText } from "@/utils/clipboard";
import { AppRequest } from "src/pages/api/requests";
import { useLoaderOnLoding } from "src/hooks/useLoaderOnLoading";
import {
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_12_600_EEEEEE,
  Text_14_600_EEEEEE,
  Text_16_600_FFFFFF,
  Text_26_600_FFFFFF,
} from "@/components/ui/text";
import DashBoardLayout from "../../../../layout";
import { CustomBreadcrumb } from "@/components/ui/bud/card/DrawerBreadCrumbNavigation";
import BackButton from "@/components/ui/bud/drawer/BackButton";
import ProjectTags from "src/flows/components/ProjectTags";
import { endpointStatusMapping } from "@/lib/colorMapping";

const { Paragraph } = Typography;

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
  endpoint_type?: string;
  error_code?: string;
  error_message?: string;
  error_type?: string;
  status_code?: number;
  raw_request?: string;
  raw_response?: string;
  gateway_request?: any;
  gateway_response?: any;
  feedback_count: number;
  average_rating?: number;
}

const InferenceDetailPage: React.FC = () => {
  const router = useRouter();
  const { slug, inferenceId } = router.query;
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
    if (inferenceId && typeof inferenceId === "string") {
      fetchInferenceDetail(inferenceId);
    }
  }, [inferenceId]);

  const fetchInferenceDetail = async (id: string) => {
    try {
      setLoading(true);
      setError(null);
      const response = await AppRequest.Get(`/metrics/inferences/${id}`);
      if (response.data) {
        setInferenceData(response.data);
      }
    } catch (error: any) {
      const errorMsg =
        error?.response?.data?.message ||
        error?.message ||
        "Failed to fetch observability details";
      message.error(errorMsg);
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
      onError: () => message.error("Failed to copy to clipboard"),
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
    router.push(`/home/projects/${slug}/inferences`);
  };

  const HeaderContent = () => {
    return (
      <Flex align="center" justify="between">
        {isMounted && (
          <Flex align="center" justify="start">
            <BackButton onClick={goBack} />
            <CustomBreadcrumb
              data={["Projects", `${inferenceData?.project_name || slug || ""}`, "Observability", "Details"]}
              urls={["/projects", `/projects/${slug}`, "", ""]}
            />
          </Flex>
        )}
      </Flex>
    );
  };

  if (loading) {
    return (
      <DashBoardLayout>
        <div className="flex justify-center items-center h-96">
          <Spin size="large" />
        </div>
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
                  onClick={() => fetchInferenceDetail(inferenceId as string)}
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

          {/* Performance Metrics */}
          <div className="flex items-center flex-col border border-[#1F1F1F] rounded-[.4rem] px-[1.4rem] py-[1.3rem] pb-[1.1rem] w-full bg-[#101010] mb-[1.6rem]">
            <div className="w-full">
              <Text_14_600_EEEEEE className="text-[#EEEEEE] mb-4">
                Performance Metrics
              </Text_14_600_EEEEEE>

              <div className="flex justify-between items-center">
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
                      inferenceData.input_tokens + inferenceData.output_tokens
                    ).toLocaleString()}
                  </div>
                  <Text_12_400_B3B3B3>Total Tokens</Text_12_400_B3B3B3>
                </div>

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

          {/* Error Details - Only show for failed requests */}
          {inferenceData.is_success === false && (
            <div className="flex items-center flex-col border border-red-500 rounded-[.4rem] px-[1.4rem] py-[1.3rem] pb-[1.1rem] w-full bg-red-950/20 mb-[1.6rem]">
              <div className="w-full">
                <Alert
                  message="Request Failed"
                  description={`This inference request failed with error code ${inferenceData.error_code || 'unknown'}`}
                  type="error"
                  showIcon
                  className="mb-4"
                />

                <Text_14_600_EEEEEE className="text-red-400 mb-4">
                  Error Details
                </Text_14_600_EEEEEE>

                <div className="space-y-3">
                  {inferenceData.error_code && (
                    <div>
                      <Text_12_400_B3B3B3 className="mb-1">
                        Error Code
                      </Text_12_400_B3B3B3>
                      <Tag color="error" className="text-base">
                        {inferenceData.error_code}
                      </Tag>
                    </div>
                  )}

                  {inferenceData.error_type && (
                    <div>
                      <Text_12_400_B3B3B3 className="mb-1">
                        Error Type
                      </Text_12_400_B3B3B3>
                      <Text_12_600_EEEEEE className="text-red-400">
                        {inferenceData.error_type}
                      </Text_12_600_EEEEEE>
                    </div>
                  )}

                  {inferenceData.error_message && (
                    <div>
                      <Text_12_400_B3B3B3 className="mb-1">
                        Error Message
                      </Text_12_400_B3B3B3>
                      <div className="bg-red-950/30 border border-red-800 rounded-md p-3 mt-1">
                        <Text_12_600_EEEEEE className="text-red-300 font-mono whitespace-pre-wrap">
                          {inferenceData.error_message}
                        </Text_12_600_EEEEEE>
                      </div>
                    </div>
                  )}

                  {inferenceData.raw_response && (
                    <div>
                      <Text_12_400_B3B3B3 className="mb-1">
                        Error Response Details
                      </Text_12_400_B3B3B3>
                      <div className="bg-red-950/30 border border-red-800 rounded-md p-3 mt-1 max-h-64 overflow-auto">
                        <Text_12_600_EEEEEE className="text-red-300 font-mono text-xs whitespace-pre-wrap">
                          {inferenceData.raw_response}
                        </Text_12_600_EEEEEE>
                      </div>
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-4 mt-3">
                    <div>
                      <Text_12_400_B3B3B3 className="mb-1">
                        Failed Request ID
                      </Text_12_400_B3B3B3>
                      <Text_12_600_EEEEEE className="font-mono text-xs">
                        {inferenceData.inference_id}
                      </Text_12_600_EEEEEE>
                    </div>

                    <div>
                      <Text_12_400_B3B3B3 className="mb-1">
                        Failed At
                      </Text_12_400_B3B3B3>
                      <Text_12_600_EEEEEE>
                        {formatTimestampWithTZ(inferenceData.timestamp)}
                      </Text_12_600_EEEEEE>
                    </div>
                  </div>

                  {inferenceData.messages && inferenceData.messages.length > 0 && (
                    <div>
                      <Text_12_400_B3B3B3 className="mb-1">
                        Failed Request Preview
                      </Text_12_400_B3B3B3>
                      <div className="bg-[#1A1A1A] border border-[#2F2F2F] rounded-md p-3 mt-1">
                        <Text_12_600_EEEEEE className="font-mono text-xs">
                          {JSON.stringify(inferenceData.messages[0], null, 2).substring(0, 200)}...
                        </Text_12_600_EEEEEE>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Conversation */}
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

          {/* Gateway Request */}
          {inferenceData.gateway_request && (
            <div className="flex items-center flex-col border border-[#1F1F1F] rounded-[.4rem] px-[1.4rem] py-[1.3rem] pb-[1.1rem] w-full bg-[#101010] mb-[1.6rem]">
              <div className="w-full">
                <div className="flex justify-between items-center mb-4">
                  <Text_14_600_EEEEEE className="text-[#EEEEEE]">
                    Gateway Request
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
                    Gateway Response
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

export default InferenceDetailPage;

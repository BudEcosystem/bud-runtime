"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
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
} from "antd";
import {
  ArrowLeftOutlined,
  CopyOutlined,
  DownloadOutlined,
} from "@ant-design/icons";
import { format } from "date-fns";
import { formatTimestampWithTZ } from "@/utils/formatDateNew";
import { AppRequest } from "@/services/api/requests";
import { useLoaderOnLoading } from "@/hooks/useLoaderOnLoading";
import { copyToClipboard } from "@/utils/clipboard";
import {
  Text_11_400_808080,
  Text_12_400_B3B3B3,
  Text_12_600_EEEEEE,
  Text_14_400_EEEEEE,
  Text_14_600_EEEEEE,
} from "@/components/ui/text";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import ProjectTags from "@/flows/components/ProjectTags";
import { errorToast } from "@/components/toast";

const { Paragraph } = Typography;

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

export default function ObservabilityDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const router = useRouter();
  const [id, setId] = useState<string | null>(null);
  const [inferenceData, setInferenceData] = useState<InferenceDetail | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isMounted, setIsMounted] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  useLoaderOnLoading(loading);

  useEffect(() => {
    setIsMounted(true);
    // Handle async params
    params.then((resolvedParams) => {
      setId(resolvedParams.id);
    });
  }, [params]);

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
        console.log("Inference data:", response.data);
        console.log("Endpoint type:", response.data.endpoint_type);
        console.log(
          "Type of endpoint_type:",
          typeof response.data.endpoint_type,
        );
        console.log("Is chat?", response.data.endpoint_type === "chat");
        console.log("Is undefined?", response.data.endpoint_type === undefined);
        console.log("Is null?", response.data.endpoint_type === null);
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

  const handleCopyToClipboard = async (text: string, id: string) => {
    await copyToClipboard(text, {
      onSuccess: () => {
        setCopiedId(id);
        setTimeout(() => {
          setCopiedId(null);
        }, 2000);
      },
      onError: () => {
        message.error("Failed to copy to clipboard");
      },
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
    router.push("/logs");
  };

  const HeaderContent = () => {
    return (
      <Flex align="center" justify="between">
        {isMounted && (
          <Flex align="center" justify="start">
            <Button
              onClick={goBack}
              type="text"
              shape="circle"
              icon={<ArrowLeftOutlined />}
              className="mr-4 !w-10 !h-10 !flex !items-center !justify-center hover:!bg-[var(--bg-hover)] !border-[var(--border-color)] text-[var(--text-primary)]"
            />
            <span
              className="text-2xl font-semibold"
              style={{
                color: "var(--text-primary)",
              }}
            >
              Observability Details
            </span>
          </Flex>
        )}
      </Flex>
    );
  };

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex justify-center items-center h-64">
          <Spin size="large" />
        </div>
      </DashboardLayout>
    );
  }

  if (error || !inferenceData) {
    return (
      <DashboardLayout>
        <div className="p-8">
          <HeaderContent />
          <div className="flex items-center flex-col border border-[var(--border-color)] rounded-lg p-6 mt-8 bg-[var(--bg-tertiary)] dark:bg-[#101010] text-center">
            <div className="py-12">
              <span className="text-base font-semibold text-red-500 mb-4 block">
                {error || "Failed to load observability details"}
              </span>
              <span
                className="mb-6 block"
                style={{
                  color: "var(--text-muted)",
                }}
              >
                The observability details could not be loaded. This might be due
                to a temporary service issue.
              </span>
              <PrimaryButton onClick={() => fetchInferenceDetail(id as string)}>
                Try Again
              </PrimaryButton>
            </div>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="p-8">
        <HeaderContent />

        {/* Overview & Details - Combined Section */}
        <div className="flex items-center flex-col border border-[var(--border-color)] rounded-lg p-6 w-full bg-[var(--bg-tertiary)] dark:bg-[#101010] mb-6 mt-8">
          <div className="w-full">
            <Text_14_600_EEEEEE className="text-[var(--text-primary)] mb-4">
              Overview
            </Text_14_600_EEEEEE>

            <div className="grid grid-cols-3 gap-4">
              <div>
                <Text_12_400_B3B3B3 className="mb-1 text-[var(--text-muted)]">
                  Inference ID
                </Text_12_400_B3B3B3>
                <div className="flex items-center gap-2">
                  <Text_12_600_EEEEEE
                    className="truncate max-w-[200px] text-[var(--text-primary)]"
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
                        handleCopyToClipboard(
                          inferenceData.inference_id,
                          "inference_id",
                        )
                      }
                      className="text-[var(--text-muted)] hover:text-[var(--text-primary)] min-w-[24px]"
                    />
                  </Tooltip>
                </div>
              </div>

              <div>
                <Text_12_400_B3B3B3 className="mb-1 text-[var(--text-muted)]">
                  Model
                </Text_12_400_B3B3B3>
                <Text_12_600_EEEEEE className="text-[var(--text-primary)]">
                  {inferenceData.model_display_name || inferenceData.model_name}
                </Text_12_600_EEEEEE>
              </div>

              <div>
                <Text_12_400_B3B3B3 className="mb-1 text-[var(--text-muted)]">
                  Endpoint
                </Text_12_400_B3B3B3>
                <Text_12_600_EEEEEE className="text-[var(--text-primary)]">
                  {inferenceData.endpoint_name || "Unknown Endpoint"}
                </Text_12_600_EEEEEE>
              </div>

              <div>
                <Text_12_400_B3B3B3 className="mb-1 text-[var(--text-muted)]">
                  Type
                </Text_12_400_B3B3B3>
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
                <Text_12_400_B3B3B3 className="mb-1 text-[var(--text-muted)]">
                  Project
                </Text_12_400_B3B3B3>
                <Text_12_600_EEEEEE className="text-[var(--text-primary)]">
                  {inferenceData.project_name || "Unknown Project"}
                </Text_12_600_EEEEEE>
              </div>

              <div>
                <Text_12_400_B3B3B3 className="mb-1 text-[var(--text-muted)]">
                  Timestamp
                </Text_12_400_B3B3B3>
                <Text_12_600_EEEEEE className="text-[var(--text-primary)]">
                  {formatTimestampWithTZ(inferenceData.timestamp)}
                </Text_12_600_EEEEEE>
              </div>

              <div>
                <Text_12_400_B3B3B3 className="mb-1 text-[var(--text-muted)]">
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
                  <Text_12_400_B3B3B3 className="mb-1 text-[var(--text-muted)]">
                    Finish Reason
                  </Text_12_400_B3B3B3>
                  <Text_12_600_EEEEEE className="text-[var(--text-primary)]">
                    {inferenceData.finish_reason}
                  </Text_12_600_EEEEEE>
                </div>
              )}

              <div>
                <Text_12_400_B3B3B3 className="mb-1 text-[var(--text-muted)]">
                  Status
                </Text_12_400_B3B3B3>
                <div>
                  <ProjectTags
                    name={inferenceData.is_success ? "Success" : "Failed"}
                    color={
                      inferenceData.is_success
                        ? "var(--color-success)"
                        : "var(--color-error)"
                    }
                    textClass="text-[.75rem]"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Gateway Metadata */}
        {inferenceData.gateway_metadata && inferenceData.gateway_metadata.client_ip && (
          <div className="flex items-center flex-col border border-[var(--border-color)] rounded-lg p-6 w-full bg-[var(--bg-tertiary)] dark:bg-[#101010] mb-6">
            <div className="w-full">
              <Text_14_600_EEEEEE className="text-[var(--text-primary)] mb-4">
                Request Metadata
              </Text_14_600_EEEEEE>

              <div className="grid grid-cols-3 gap-4">
                {/* Network Information */}
                {inferenceData.gateway_metadata.client_ip && (
                  <div>
                    <Text_12_400_B3B3B3 className="mb-1 text-[var(--text-muted)]">
                      Client IP
                    </Text_12_400_B3B3B3>
                    <Text_12_600_EEEEEE className="text-[var(--text-primary)]">
                      {inferenceData.gateway_metadata.client_ip}
                    </Text_12_600_EEEEEE>
                  </div>
                )}
                {inferenceData.gateway_metadata.method && (
                  <div>
                    <Text_12_400_B3B3B3 className="mb-1 text-[var(--text-muted)]">
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
                    <Text_12_400_B3B3B3 className="mb-1 text-[var(--text-muted)]">
                      Path
                    </Text_12_400_B3B3B3>
                    <Text_12_600_EEEEEE className="font-mono text-xs text-[var(--text-primary)]">
                      {inferenceData.gateway_metadata.path}
                    </Text_12_600_EEEEEE>
                  </div>
                )}
                {inferenceData.gateway_metadata.protocol_version && (
                  <div>
                    <Text_12_400_B3B3B3 className="mb-1 text-[var(--text-muted)]">
                      Protocol
                    </Text_12_400_B3B3B3>
                    <Text_12_600_EEEEEE className="text-[var(--text-primary)]">
                      {inferenceData.gateway_metadata.protocol_version}
                    </Text_12_600_EEEEEE>
                  </div>
                )}
                {inferenceData.gateway_metadata.status_code && (
                  <div>
                    <Text_12_400_B3B3B3 className="mb-1 text-[var(--text-muted)]">
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
                    <Text_12_400_B3B3B3 className="mb-1 text-[var(--text-muted)]">
                      Device Type
                    </Text_12_400_B3B3B3>
                    <Tag
                      color={
                        inferenceData.gateway_metadata.device_type === "mobile"
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
                    <Text_12_400_B3B3B3 className="mb-1 text-[var(--text-muted)]">
                      Browser
                    </Text_12_400_B3B3B3>
                    <Text_12_600_EEEEEE className="text-[var(--text-primary)]">
                      {inferenceData.gateway_metadata.browser_name}
                      {inferenceData.gateway_metadata.browser_version &&
                        ` v${inferenceData.gateway_metadata.browser_version}`}
                    </Text_12_600_EEEEEE>
                  </div>
                )}
                {inferenceData.gateway_metadata.os_name && (
                  <div>
                    <Text_12_400_B3B3B3 className="mb-1 text-[var(--text-muted)]">
                      Operating System
                    </Text_12_400_B3B3B3>
                    <Text_12_600_EEEEEE className="text-[var(--text-primary)]">
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
                    <Text_12_400_B3B3B3 className="mb-1 text-[var(--text-muted)]">
                      Location
                    </Text_12_400_B3B3B3>
                    <Text_12_600_EEEEEE className="text-[var(--text-primary)]">
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
                    <Text_12_400_B3B3B3 className="mb-1 text-[var(--text-muted)]">
                      Timezone
                    </Text_12_400_B3B3B3>
                    <Text_12_600_EEEEEE className="text-[var(--text-primary)]">
                      {inferenceData.gateway_metadata.timezone}
                    </Text_12_600_EEEEEE>
                  </div>
                )}
                {inferenceData.gateway_metadata.isp && (
                  <div>
                    <Text_12_400_B3B3B3 className="mb-1 text-[var(--text-muted)]">
                      ISP
                    </Text_12_400_B3B3B3>
                    <Text_12_600_EEEEEE className="text-[var(--text-primary)]">
                      {inferenceData.gateway_metadata.isp}
                    </Text_12_600_EEEEEE>
                  </div>
                )}
                {inferenceData.gateway_metadata.asn && (
                  <div>
                    <Text_12_400_B3B3B3 className="mb-1 text-[var(--text-muted)]">
                      AS Number
                    </Text_12_400_B3B3B3>
                    <Text_12_600_EEEEEE className="text-[var(--text-primary)]">
                      AS{inferenceData.gateway_metadata.asn}
                    </Text_12_600_EEEEEE>
                  </div>
                )}

                {/* Authentication Information */}
                {inferenceData.gateway_metadata.auth_method && (
                  <div>
                    <Text_12_400_B3B3B3 className="mb-1 text-[var(--text-muted)]">
                      Auth Method
                    </Text_12_400_B3B3B3>
                    <Text_12_600_EEEEEE className="text-[var(--text-primary)]">
                      {inferenceData.gateway_metadata.auth_method}
                    </Text_12_600_EEEEEE>
                  </div>
                )}
                {inferenceData.gateway_metadata.api_key_id && (
                  <div>
                    <Text_12_400_B3B3B3 className="mb-1 text-[var(--text-muted)]">
                      API Key ID
                    </Text_12_400_B3B3B3>
                    <Text_12_600_EEEEEE className="font-mono text-xs text-[var(--text-primary)]">
                      {inferenceData.gateway_metadata.api_key_id}
                    </Text_12_600_EEEEEE>
                  </div>
                )}
                {inferenceData.gateway_metadata.user_id && (
                  <div>
                    <Text_12_400_B3B3B3 className="mb-1 text-[var(--text-muted)]">
                      User ID
                    </Text_12_400_B3B3B3>
                    <Text_12_600_EEEEEE className="font-mono text-xs text-[var(--text-primary)]">
                      {inferenceData.gateway_metadata.user_id}
                    </Text_12_600_EEEEEE>
                  </div>
                )}
              </div>

              {/* User Agent - full width at the bottom if exists */}
              {inferenceData.gateway_metadata.user_agent && (
                <div className="mt-4">
                  <Text_12_400_B3B3B3 className="mb-1 text-[var(--text-muted)]">
                    User Agent
                  </Text_12_400_B3B3B3>
                  <div className="bg-[var(--bg-secondary)] p-2 rounded">
                    <Text_12_400_B3B3B3 className="font-mono text-xs break-all text-[var(--text-muted)]">
                      {inferenceData.gateway_metadata.user_agent}
                    </Text_12_400_B3B3B3>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Performance Metrics */}
        <div className="flex items-center flex-col border border-[var(--border-color)] rounded-lg p-6 w-full bg-[var(--bg-tertiary)] dark:bg-[#101010] mb-6">
          <div className="w-full">
            <Text_14_600_EEEEEE className="text-[var(--text-primary)] mb-4">
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
                      <div
                        className="text-[1.25rem] font-[600] mb-1"
                        style={{ color: "#3b82f6" }}
                      >
                        {inferenceData.input_tokens.toLocaleString()}
                      </div>
                      <Text_12_400_B3B3B3 className="text-[var(--text-muted)]">
                        Input Tokens
                      </Text_12_400_B3B3B3>
                    </div>

                    <div className="text-center">
                      <div
                        className="text-[1.25rem] font-[600] mb-1"
                        style={{ color: "#3b82f6" }}
                      >
                        {inferenceData.output_tokens.toLocaleString()}
                      </div>
                      <Text_12_400_B3B3B3 className="text-[var(--text-muted)]">
                        Output Tokens
                      </Text_12_400_B3B3B3>
                    </div>

                    <div className="text-center">
                      <div
                        className="text-[1.25rem] font-[600] mb-1"
                        style={{ color: "#8b5cf6" }}
                      >
                        {(
                          inferenceData.input_tokens +
                          inferenceData.output_tokens
                        ).toLocaleString()}
                      </div>
                      <Text_12_400_B3B3B3 className="text-[var(--text-muted)]">
                        Total Tokens
                      </Text_12_400_B3B3B3>
                    </div>
                  </>
                )}

              {inferenceData.ttft_ms && (
                <div className="text-center">
                  <div
                    className="text-[1.25rem] font-[600] mb-1"
                    style={{ color: "#06b6d4" }}
                  >
                    {formatDuration(inferenceData.ttft_ms)}
                  </div>
                  <Text_12_400_B3B3B3 className="text-[var(--text-muted)]">
                    TTFT
                  </Text_12_400_B3B3B3>
                </div>
              )}
              <div className="text-center">
                <div
                  className="text-[1.25rem] font-[600] mb-1"
                  style={{ color: "#22c55e" }}
                >
                  {formatDuration(inferenceData.response_time_ms)}
                </div>
                <Text_12_400_B3B3B3 className="text-[var(--text-muted)]">
                  End to End Latency
                </Text_12_400_B3B3B3>
              </div>
            </div>
          </div>
        </div>

        {/* Error Details - Only show for failed requests */}
        {inferenceData.is_success === false && (
          <div className="flex items-center flex-col border border-red-500 rounded-lg p-6 w-full bg-red-50 dark:bg-red-950/20 mb-6">
            <div className="w-full">
              <Text_14_600_EEEEEE className="text-red-600 dark:text-red-400 mb-4">
                Error Details
              </Text_14_600_EEEEEE>

              <div className="space-y-4">
                {inferenceData.error_code && (
                  <div>
                    <Text_12_400_B3B3B3 className="text-[var(--text-muted)] mb-1">
                      Error Code
                    </Text_12_400_B3B3B3>
                    <Text_14_400_EEEEEE className="text-red-600 dark:text-red-400 font-semibold text-lg">
                      {inferenceData.error_code}
                    </Text_14_400_EEEEEE>
                  </div>
                )}

                {inferenceData.error_type && (
                  <div>
                    <Text_12_400_B3B3B3 className="text-[var(--text-muted)] mb-1">
                      Error Type
                    </Text_12_400_B3B3B3>
                    <Text_14_400_EEEEEE className="text-red-600 dark:text-red-400">
                      {inferenceData.error_type}
                    </Text_14_400_EEEEEE>
                  </div>
                )}

                {inferenceData.error_message && (
                  <div>
                    <Text_12_400_B3B3B3 className="text-[var(--text-muted)] mb-1">
                      Error Message
                    </Text_12_400_B3B3B3>
                    <div className="bg-red-100 dark:bg-red-950/30 border border-red-300 dark:border-red-800 rounded-md p-3 mt-1">
                      <Text_14_400_EEEEEE className="text-red-700 dark:text-red-300 font-mono text-[0.85rem] whitespace-pre-wrap">
                        {inferenceData.error_message}
                      </Text_14_400_EEEEEE>
                    </div>
                  </div>
                )}

                <div>
                  <Text_12_400_B3B3B3 className="text-[var(--text-muted)] mb-1">
                    Failed Request ID
                  </Text_12_400_B3B3B3>
                  <Text_14_400_EEEEEE className="text-[var(--text-primary)] font-mono text-[0.8rem]">
                    {inferenceData.inference_id}
                  </Text_14_400_EEEEEE>
                </div>

                <div>
                  <Text_12_400_B3B3B3 className="text-[var(--text-muted)] mb-1">
                    Failed At
                  </Text_12_400_B3B3B3>
                  <Text_14_400_EEEEEE className="text-[var(--text-primary)]">
                    {formatTimestampWithTZ(inferenceData.timestamp)}
                  </Text_14_400_EEEEEE>
                </div>

                {inferenceData.raw_response && (
                  <div>
                    <Text_12_400_B3B3B3 className="text-[var(--text-muted)] mb-1">
                      Error Response Details
                    </Text_12_400_B3B3B3>
                    <div className="bg-red-100 dark:bg-red-950/30 border border-red-300 dark:border-red-800 rounded-md p-3 mt-1 max-h-64 overflow-auto">
                      <Text_14_400_EEEEEE className="text-red-700 dark:text-red-300 font-mono text-[0.75rem] whitespace-pre-wrap">
                        {inferenceData.raw_response}
                      </Text_14_400_EEEEEE>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Conversation - Only show for chat endpoint type */}
        {(!inferenceData.endpoint_type ||
          inferenceData.endpoint_type === "chat") && (inferenceData.messages && inferenceData?.messages?.length > 0) && (
          <div className="flex items-center flex-col border border-[var(--border-color)] rounded-lg p-6 w-full bg-[var(--bg-tertiary)] dark:bg-[#101010] mb-6">
            <div className="w-full">
              <div className="flex justify-between items-center mb-4">
                <Text_14_600_EEEEEE className="text-[var(--text-primary)]">
                  Conversation
                </Text_14_600_EEEEEE>
                <Button
                  size="small"
                  icon={<DownloadOutlined />}
                  onClick={() =>{
                    if(inferenceData.messages && inferenceData?.messages?.length > 0){
                      downloadJson(inferenceData.messages, "conversation")
                    }
                    else {
                      errorToast("No conversation data to download")
                    }
                  }}
                  className="!bg-[var(--bg-secondary)] !border-[var(--border-color)] text-[var(--text-primary)] hover:!bg-[var(--bg-hover)]"
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
                        ? "bg-[var(--role-system-bg)] border-[var(--role-system-border)]"
                        : message.role === "user"
                          ? "bg-[var(--role-user-bg)] border-[var(--role-user-border)]"
                          : message.role === "assistant"
                            ? "bg-[var(--role-assistant-bg)] border-[var(--role-assistant-border)]"
                            : "bg-[var(--bg-secondary)] border-[var(--border-color)]"
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
                            handleCopyToClipboard(textToCopy, `message_${index}`);
                          }}
                          className="text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                        />
                      </Tooltip>
                    </div>
                    <div className="text-[var(--text-primary)]">
                      {(() => {
                        // Handle different content formats
                        if (typeof message.content === "string") {
                          return (
                            <Paragraph className="mb-0 whitespace-pre-wrap text-sm text-[var(--text-primary)]">
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
                            <Paragraph className="mb-0 whitespace-pre-wrap text-sm text-[var(--text-primary)]">
                              {textParts}
                            </Paragraph>
                          );
                        } else {
                          // Fallback for other formats
                          return (
                            <pre className="bg-[var(--bg-secondary)] p-3 rounded overflow-x-auto text-sm">
                              <code className="text-[var(--text-primary)]">
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
          <div className="flex items-center flex-col border border-[var(--border-color)] rounded-lg p-6 w-full bg-[var(--bg-tertiary)] dark:bg-[#101010] mb-6">
            <div className="w-full">
              <div className="flex justify-between items-center mb-4">
                <Text_14_600_EEEEEE className="text-[var(--text-primary)]">
                  Raw Request
                </Text_14_600_EEEEEE>
                <div className="flex gap-2">
                  <Tooltip
                    title={copiedId === "gateway_request" ? "Copied!" : "Copy"}
                    placement="top"
                  >
                    <Button
                      size="small"
                      icon={<CopyOutlined />}
                      onClick={() => {
                        try {
                          handleCopyToClipboard(
                            JSON.stringify(
                              inferenceData.gateway_request,
                              null,
                              2,
                            ),
                            "gateway_request",
                          );
                        } catch {
                          handleCopyToClipboard(
                            JSON.stringify(inferenceData.gateway_request),
                            "gateway_request",
                          );
                        }
                      }}
                      className="!bg-[var(--bg-secondary)] !border-[var(--border-color)] text-[var(--text-primary)] hover:!bg-[var(--bg-hover)]"
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
                    className="!bg-[var(--bg-secondary)] !border-[var(--border-color)] text-[var(--text-primary)] hover:!bg-[var(--bg-hover)]"
                  >
                    Download
                  </Button>
                </div>
              </div>
              <div className="bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-md p-3 overflow-x-auto">
                <pre className="text-[var(--text-muted)] mb-0 text-sm">
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
          <div className="flex items-center flex-col border border-[var(--border-color)] rounded-lg p-6 w-full bg-[var(--bg-tertiary)] dark:bg-[#101010] mb-6">
            <div className="w-full">
              <div className="flex justify-between items-center mb-4">
                <Text_14_600_EEEEEE className="text-[var(--text-primary)]">
                  Raw Response
                </Text_14_600_EEEEEE>
                <div className="flex gap-2">
                  <Tooltip
                    title={copiedId === "gateway_response" ? "Copied!" : "Copy"}
                    placement="top"
                  >
                    <Button
                      size="small"
                      icon={<CopyOutlined />}
                      onClick={() => {
                        try {
                          handleCopyToClipboard(
                            JSON.stringify(
                              inferenceData.gateway_response,
                              null,
                              2,
                            ),
                            "gateway_response",
                          );
                        } catch {
                          handleCopyToClipboard(
                            JSON.stringify(inferenceData.gateway_response),
                            "gateway_response",
                          );
                        }
                      }}
                      className="!bg-[var(--bg-secondary)] !border-[var(--border-color)] text-[var(--text-primary)] hover:!bg-[var(--bg-hover)]"
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
                    className="!bg-[var(--bg-secondary)] !border-[var(--border-color)] text-[var(--text-primary)] hover:!bg-[var(--bg-hover)]"
                  >
                    Download
                  </Button>
                </div>
              </div>
              <div className="bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-md p-3 overflow-x-auto">
                <pre className="text-[var(--text-muted)] mb-0 text-sm">
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
    </DashboardLayout>
  );
}

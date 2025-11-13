import React, { useEffect, useState } from "react";
import {
  Modal,
  Tabs,
  Spin,
  Descriptions,
  Tag,
  Space,
  Typography,
  Button,
  message,
  Divider,
  Rate,
  Timeline,
  Empty,
  Alert,
} from "antd";
import { CopyOutlined, DownloadOutlined } from "@ant-design/icons";
import { format } from "date-fns";
import { formatTimestamp, formatTimestampWithTZ } from "@/utils/formatDate";
import { copyToClipboard as copyText } from "@/utils/clipboard";
import { useInferences } from "@/stores/useInferences";
import SyntaxHighlighter from "react-syntax-highlighter";
import { monokai } from "react-syntax-highlighter/dist/cjs/styles/hljs";
import RequestMetadata from "./RequestMetadata";
import ClientInfo from "./ClientInfo";
import GeographicInfo from "./GeographicInfo";

const { Text, Title, Paragraph } = Typography;
const { TabPane } = Tabs;

interface InferenceDetailModalProps {
  inferenceId: string;
  visible: boolean;
  onClose: () => void;
}

const InferenceDetailModal: React.FC<InferenceDetailModalProps> = ({
  inferenceId,
  visible,
  onClose,
}) => {
  const [activeTab, setActiveTab] = useState("overview");
  const {
    selectedInference,
    inferenceFeedback,
    isLoadingDetail,
    isLoadingFeedback,
    fetchInferenceDetail,
    fetchInferenceFeedback,
    clearSelectedInference,
  } = useInferences();

  useEffect(() => {
    if (visible && inferenceId) {
      fetchInferenceDetail(inferenceId);
      fetchInferenceFeedback(inferenceId);
    }

    return () => {
      if (!visible) {
        clearSelectedInference();
      }
    };
  }, [
    visible,
    inferenceId,
    fetchInferenceDetail,
    fetchInferenceFeedback,
    clearSelectedInference,
  ]);

  const copyToClipboard = async (text: string, label: string = "Content") => {
    await copyText(text, {
      onSuccess: () => message.success(`${label} copied to clipboard`),
      onError: () => message.error(`Failed to copy ${label}`),
    });
  };

  const downloadAsFile = (content: string, filename: string) => {
    const blob = new Blob([content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const renderMessages = () => {
    if (
      !selectedInference?.messages ||
      selectedInference.messages.length === 0
    ) {
      return <Empty description="No messages available" />;
    }

    return (
      <div style={{ maxHeight: "60vh", overflowY: "auto" }}>
        {selectedInference.system_prompt && (
          <div style={{ marginBottom: 16 }}>
            <Text strong>System Prompt:</Text>
            <div
              style={{
                marginTop: 8,
                padding: 12,
                backgroundColor: "#f5f5f5",
                borderRadius: 8,
              }}
            >
              <Paragraph style={{ margin: 0, whiteSpace: "pre-wrap" }}>
                {selectedInference.system_prompt}
              </Paragraph>
              <Button
                size="small"
                icon={<CopyOutlined />}
                onClick={() =>
                  copyToClipboard(
                    selectedInference.system_prompt!,
                    "System prompt",
                  )
                }
                style={{ marginTop: 8 }}
              >
                Copy
              </Button>
            </div>
          </div>
        )}

        {selectedInference.messages.map((message, index) => (
          <div key={index} style={{ marginBottom: 16 }}>
            <Text strong>
              {message.role === "user" ? "User" : "Assistant"}:
            </Text>
            <div
              style={{
                marginTop: 8,
                padding: 12,
                backgroundColor:
                  message.role === "user" ? "#e6f7ff" : "#f6ffed",
                borderRadius: 8,
                border: `1px solid ${message.role === "user" ? "#91d5ff" : "#b7eb8f"}`,
              }}
            >
              <Paragraph style={{ margin: 0, whiteSpace: "pre-wrap" }}>
                {message.content || JSON.stringify(message, null, 2)}
              </Paragraph>
              <Button
                size="small"
                icon={<CopyOutlined />}
                onClick={() =>
                  copyToClipboard(
                    message.content || JSON.stringify(message, null, 2),
                    `${message.role === "user" ? "User" : "Assistant"} message`,
                  )
                }
                style={{ marginTop: 8 }}
              >
                Copy
              </Button>
            </div>
          </div>
        ))}

        {selectedInference.output && (
          <div style={{ marginBottom: 16 }}>
            <Text strong>Final Output:</Text>
            <div
              style={{
                marginTop: 8,
                padding: 12,
                backgroundColor: "#f6ffed",
                borderRadius: 8,
              }}
            >
              <Paragraph style={{ margin: 0, whiteSpace: "pre-wrap" }}>
                {selectedInference.output}
              </Paragraph>
              <Button
                size="small"
                icon={<CopyOutlined />}
                onClick={() =>
                  copyToClipboard(selectedInference.output, "Output")
                }
                style={{ marginTop: 8 }}
              >
                Copy
              </Button>
            </div>
          </div>
        )}
      </div>
    );
  };

  const renderPerformanceMetrics = () => {
    if (!selectedInference) return null;

    return (
      <div>
        <Descriptions bordered column={2}>
          <Descriptions.Item label="Input Tokens">
            {selectedInference.input_tokens.toLocaleString()}
          </Descriptions.Item>
          <Descriptions.Item label="Output Tokens">
            {selectedInference.output_tokens.toLocaleString()}
          </Descriptions.Item>
          <Descriptions.Item label="Total Tokens">
            {(
              selectedInference.input_tokens + selectedInference.output_tokens
            ).toLocaleString()}
          </Descriptions.Item>
          <Descriptions.Item label="Response Time">
            {selectedInference.response_time_ms.toLocaleString()} ms
          </Descriptions.Item>
          {selectedInference.ttft_ms && (
            <Descriptions.Item label="Time to First Token">
              {selectedInference.ttft_ms.toLocaleString()} ms
            </Descriptions.Item>
          )}
          {selectedInference.processing_time_ms && (
            <Descriptions.Item label="Processing Time">
              {selectedInference.processing_time_ms.toLocaleString()} ms
            </Descriptions.Item>
          )}
          <Descriptions.Item label="Cost" span={2}>
            {selectedInference.cost
              ? `$${selectedInference.cost.toFixed(6)}`
              : "N/A"}
          </Descriptions.Item>
        </Descriptions>

        {selectedInference.cached && (
          <Tag color="blue" style={{ marginTop: 16 }}>
            Response was cached
          </Tag>
        )}
      </div>
    );
  };

  const renderRawData = () => {
    if (!selectedInference) return null;

    return (
      <div>
        {selectedInference.gateway_request && (
          <div style={{ marginBottom: 24 }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 8,
              }}
            >
              <Title level={5}>Gateway Request</Title>
              <Space>
                <Button
                  size="small"
                  icon={<CopyOutlined />}
                  onClick={() =>
                    copyToClipboard(
                      JSON.stringify(
                        selectedInference.gateway_request,
                        null,
                        2,
                      ),
                      "Gateway request",
                    )
                  }
                >
                  Copy
                </Button>
                <Button
                  size="small"
                  icon={<DownloadOutlined />}
                  onClick={() =>
                    downloadAsFile(
                      JSON.stringify(
                        selectedInference.gateway_request,
                        null,
                        2,
                      ),
                      `request_${selectedInference.inference_id}.json`,
                    )
                  }
                >
                  Download
                </Button>
              </Space>
            </div>
            <div style={{ maxHeight: "40vh", overflowY: "auto" }}>
              <SyntaxHighlighter
                language="json"
                style={monokai}
                customStyle={{ borderRadius: 8 }}
              >
                {JSON.stringify(selectedInference.gateway_request, null, 2)}
              </SyntaxHighlighter>
            </div>
          </div>
        )}

        {selectedInference.gateway_response && (
          <div style={{ marginBottom: 24 }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 8,
              }}
            >
              <Title level={5}>Gateway Response</Title>
              <Space>
                <Button
                  size="small"
                  icon={<CopyOutlined />}
                  onClick={() =>
                    copyToClipboard(
                      JSON.stringify(
                        selectedInference.gateway_response,
                        null,
                        2,
                      ),
                      "Gateway response",
                    )
                  }
                >
                  Copy
                </Button>
                <Button
                  size="small"
                  icon={<DownloadOutlined />}
                  onClick={() =>
                    downloadAsFile(
                      JSON.stringify(
                        selectedInference.gateway_response,
                        null,
                        2,
                      ),
                      `response_${selectedInference.inference_id}.json`,
                    )
                  }
                >
                  Download
                </Button>
              </Space>
            </div>
            <div style={{ maxHeight: "40vh", overflowY: "auto" }}>
              <SyntaxHighlighter
                language="json"
                style={monokai}
                customStyle={{ borderRadius: 8 }}
              >
                {JSON.stringify(selectedInference.gateway_response, null, 2)}
              </SyntaxHighlighter>
            </div>
          </div>
        )}

        {selectedInference.raw_response && (
          <div>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 8,
              }}
            >
              <Title level={5}>Raw Response (Streaming Data)</Title>
              <Space>
                <Button
                  size="small"
                  icon={<CopyOutlined />}
                  onClick={() =>
                    copyToClipboard(
                      selectedInference.raw_response,
                      "Raw response",
                    )
                  }
                >
                  Copy
                </Button>
                <Button
                  size="small"
                  icon={<DownloadOutlined />}
                  onClick={() =>
                    downloadAsFile(
                      selectedInference.raw_response,
                      `raw_response_${selectedInference.inference_id}.txt`,
                    )
                  }
                >
                  Download
                </Button>
              </Space>
            </div>
            <div style={{ maxHeight: "40vh", overflowY: "auto" }}>
              <SyntaxHighlighter
                language="text"
                style={monokai}
                customStyle={{ borderRadius: 8, fontSize: 12 }}
              >
                {selectedInference.raw_response}
              </SyntaxHighlighter>
            </div>
          </div>
        )}
      </div>
    );
  };

  const renderGatewayMetadata = () => {
    if (!selectedInference?.gateway_metadata) {
      return <Empty description="No gateway metadata available" />;
    }

    const { gateway_metadata } = selectedInference;

    // Transform flat gateway_metadata into nested structure for components
    const requestMetadata = {
      client_ip: gateway_metadata.client_ip,
      proxy_chain: gateway_metadata.proxy_chain,
      protocol_version: gateway_metadata.protocol_version,
      method: gateway_metadata.method,
      path: gateway_metadata.path,
      query_params: gateway_metadata.query_params,
      request_headers: gateway_metadata.request_headers,
      body_size: gateway_metadata.body_size,
      api_key_id: gateway_metadata.api_key_id,
      auth_method: gateway_metadata.auth_method,
      user_id: gateway_metadata.user_id,
      gateway_processing_ms: gateway_metadata.gateway_processing_ms,
      total_duration_ms: gateway_metadata.total_duration_ms,
      status_code: gateway_metadata.status_code,
      response_size: gateway_metadata.response_size,
      response_headers: gateway_metadata.response_headers,
    };

    const clientInfo = {
      user_agent: gateway_metadata.user_agent,
      device_type: gateway_metadata.device_type,
      browser_name: gateway_metadata.browser_name,
      browser_version: gateway_metadata.browser_version,
      os_name: gateway_metadata.os_name,
      os_version: gateway_metadata.os_version,
      is_bot: gateway_metadata.is_bot,
    };

    const geographicInfo = {
      country_code: gateway_metadata.country_code,
      country_name: gateway_metadata.country_name,
      region: gateway_metadata.region,
      city: gateway_metadata.city,
      latitude: gateway_metadata.latitude,
      longitude: gateway_metadata.longitude,
      timezone: gateway_metadata.timezone,
      asn: gateway_metadata.asn,
      isp: gateway_metadata.isp,
    };

    // Check if we have any data to display
    const hasRequestMetadata =
      requestMetadata.client_ip ||
      requestMetadata.method ||
      requestMetadata.path;
    const hasClientInfo =
      clientInfo.user_agent ||
      clientInfo.device_type ||
      clientInfo.browser_name;
    const hasGeographicInfo =
      geographicInfo.country_code || geographicInfo.city || geographicInfo.isp;

    return (
      <div>
        {hasRequestMetadata && (
          <div style={{ marginBottom: 24 }}>
            <RequestMetadata data={requestMetadata} onCopy={copyToClipboard} />
          </div>
        )}

        {hasClientInfo && (
          <div style={{ marginBottom: 24 }}>
            <ClientInfo data={clientInfo} onCopy={copyToClipboard} />
          </div>
        )}

        {hasGeographicInfo && (
          <div style={{ marginBottom: 24 }}>
            <GeographicInfo data={geographicInfo} onCopy={copyToClipboard} />
          </div>
        )}

        {/* Additional metadata can be added here if needed */}
      </div>
    );
  };

  const renderFeedback = () => {
    if (!inferenceFeedback || inferenceFeedback.length === 0) {
      return <Empty description="No feedback available for this inference" />;
    }

    const feedbackByType = inferenceFeedback.reduce(
      (acc, item) => {
        if (!acc[item.feedback_type]) {
          acc[item.feedback_type] = [];
        }
        acc[item.feedback_type].push(item);
        return acc;
      },
      {} as Record<string, typeof inferenceFeedback>,
    );

    return (
      <div>
        {feedbackByType.boolean && feedbackByType.boolean.length > 0 && (
          <div style={{ marginBottom: 24 }}>
            <Title level={5}>Boolean Metrics</Title>
            <Space direction="vertical" style={{ width: "100%" }}>
              {feedbackByType.boolean.map((item) => (
                <div
                  key={item.feedback_id}
                  style={{
                    padding: 8,
                    backgroundColor: "#fafafa",
                    borderRadius: 4,
                  }}
                >
                  <Text strong>{item.metric_name}: </Text>
                  <Tag color={item.value ? "success" : "error"}>
                    {item.value ? "Yes" : "No"}
                  </Tag>
                  <Text
                    type="secondary"
                    style={{ fontSize: 12, marginLeft: 8 }}
                  >
                    {format(new Date(item.created_at), "MMM dd, yyyy HH:mm")}
                  </Text>
                </div>
              ))}
            </Space>
          </div>
        )}

        {feedbackByType.float && feedbackByType.float.length > 0 && (
          <div style={{ marginBottom: 24 }}>
            <Title level={5}>Numeric Ratings</Title>
            <Space direction="vertical" style={{ width: "100%" }}>
              {feedbackByType.float.map((item) => (
                <div
                  key={item.feedback_id}
                  style={{
                    padding: 8,
                    backgroundColor: "#fafafa",
                    borderRadius: 4,
                  }}
                >
                  <Text strong>{item.metric_name}: </Text>
                  {item.metric_name?.toLowerCase().includes("rating") ? (
                    <Rate disabled value={Number(item.value)} />
                  ) : (
                    <Text>{Number(item.value).toFixed(2)}</Text>
                  )}
                  <Text
                    type="secondary"
                    style={{ fontSize: 12, marginLeft: 8 }}
                  >
                    {format(new Date(item.created_at), "MMM dd, yyyy HH:mm")}
                  </Text>
                </div>
              ))}
            </Space>
          </div>
        )}

        {feedbackByType.comment && feedbackByType.comment.length > 0 && (
          <div style={{ marginBottom: 24 }}>
            <Title level={5}>Comments</Title>
            <Timeline>
              {feedbackByType.comment.map((item) => (
                <Timeline.Item key={item.feedback_id}>
                  <Paragraph style={{ margin: 0 }}>
                    {String(item.value)}
                  </Paragraph>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {format(new Date(item.created_at), "MMM dd, yyyy HH:mm")}
                  </Text>
                </Timeline.Item>
              ))}
            </Timeline>
          </div>
        )}

        {feedbackByType.demonstration &&
          feedbackByType.demonstration.length > 0 && (
            <div>
              <Title level={5}>Demonstrations</Title>
              <Space direction="vertical" style={{ width: "100%" }}>
                {feedbackByType.demonstration.map((item) => (
                  <div
                    key={item.feedback_id}
                    style={{
                      padding: 12,
                      backgroundColor: "#fafafa",
                      borderRadius: 4,
                    }}
                  >
                    <Paragraph style={{ margin: 0, whiteSpace: "pre-wrap" }}>
                      {String(item.value)}
                    </Paragraph>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {format(new Date(item.created_at), "MMM dd, yyyy HH:mm")}
                    </Text>
                  </div>
                ))}
              </Space>
            </div>
          )}
      </div>
    );
  };

  return (
    <Modal
      title="Observability Details"
      visible={visible}
      onCancel={onClose}
      width={900}
      footer={null}
      bodyStyle={{ padding: 0 }}
    >
      {isLoadingDetail || (activeTab === "feedback" && isLoadingFeedback) ? (
        <div style={{ textAlign: "center", padding: 50 }}>
          <Spin size="large" />
        </div>
      ) : selectedInference ? (
        <Tabs activeKey={activeTab} onChange={setActiveTab}>
          <TabPane tab="Overview" key="overview">
            <div style={{ padding: 24 }}>
              <Descriptions bordered column={2}>
                <Descriptions.Item label="Inference ID" span={2}>
                  <Space>
                    <Text copyable>{selectedInference.inference_id}</Text>
                  </Space>
                </Descriptions.Item>
                <Descriptions.Item label="Timestamp" span={2}>
                  {formatTimestampWithTZ(selectedInference.timestamp)}
                </Descriptions.Item>
                <Descriptions.Item label="Model">
                  {selectedInference.model_display_name ||
                    selectedInference.model_name}
                </Descriptions.Item>
                <Descriptions.Item label="Provider">
                  {selectedInference.model_provider}
                </Descriptions.Item>
                <Descriptions.Item label="Project">
                  {selectedInference.project_name ||
                    selectedInference.project_id}
                </Descriptions.Item>
                <Descriptions.Item label="Endpoint">
                  {selectedInference.endpoint_name ||
                    selectedInference.endpoint_id}
                </Descriptions.Item>
                <Descriptions.Item label="Status">
                  <Tag
                    color={selectedInference.is_success ? "success" : "error"}
                  >
                    {selectedInference.is_success ? "Success" : "Failed"}
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="Cached">
                  <Tag color={selectedInference.cached ? "blue" : "default"}>
                    {selectedInference.cached ? "Yes" : "No"}
                  </Tag>
                </Descriptions.Item>
                {selectedInference.finish_reason && (
                  <Descriptions.Item label="Finish Reason" span={2}>
                    {selectedInference.finish_reason}
                  </Descriptions.Item>
                )}
                <Descriptions.Item label="Feedback">
                  {selectedInference.feedback_count} items
                  {selectedInference.average_rating && (
                    <span>
                      {" "}
                      (Avg: {selectedInference.average_rating.toFixed(1)})
                    </span>
                  )}
                </Descriptions.Item>
                {selectedInference.gateway_metadata?.country_name && (
                  <Descriptions.Item label="Origin Country">
                    <Space>
                      {selectedInference.gateway_metadata.country_code && (
                        <span style={{ fontSize: "16px" }}>
                          {selectedInference.gateway_metadata.country_code
                            .toUpperCase()
                            .replace(/./g, (char) =>
                              String.fromCodePoint(char.charCodeAt(0) + 127397),
                            )}
                        </span>
                      )}
                      <Text>
                        {selectedInference.gateway_metadata.country_name}
                      </Text>
                      {selectedInference.gateway_metadata.city && (
                        <Text type="secondary">
                          ({selectedInference.gateway_metadata.city})
                        </Text>
                      )}
                    </Space>
                  </Descriptions.Item>
                )}
                {selectedInference.gateway_metadata?.device_type && (
                  <Descriptions.Item label="Device Type">
                    <Tag
                      color={
                        selectedInference.gateway_metadata.device_type ===
                        "mobile"
                          ? "green"
                          : selectedInference.gateway_metadata.device_type ===
                              "tablet"
                            ? "blue"
                            : selectedInference.gateway_metadata.device_type ===
                                "desktop"
                              ? "purple"
                              : "default"
                      }
                    >
                      {selectedInference.gateway_metadata.device_type}
                      {selectedInference.gateway_metadata.is_bot && " (Bot)"}
                    </Tag>
                  </Descriptions.Item>
                )}
              </Descriptions>
            </div>
          </TabPane>

          {selectedInference?.endpoint_type === "chat" && (
            <TabPane tab="Messages" key="messages">
              <div style={{ padding: 24 }}>{renderMessages()}</div>
            </TabPane>
          )}

          <TabPane tab="Performance" key="performance">
            <div style={{ padding: 24 }}>{renderPerformanceMetrics()}</div>
          </TabPane>

          <TabPane tab="Gateway Data" key="raw">
            <div style={{ padding: 24 }}>{renderRawData()}</div>
          </TabPane>

          <TabPane tab="Gateway Metadata" key="metadata">
            <div style={{ padding: 24 }}>{renderGatewayMetadata()}</div>
          </TabPane>

          <TabPane tab="Feedback" key="feedback">
            <div style={{ padding: 24 }}>{renderFeedback()}</div>
          </TabPane>
        </Tabs>
      ) : (
        <Empty description="Failed to load observability details" />
      )}
    </Modal>
  );
};

export default InferenceDetailModal;

import React from "react";
import {
  Descriptions,
  Tag,
  Space,
  Typography,
  Button,
  Tooltip,
  Empty,
} from "antd";
import {
  CopyOutlined,
  LinkOutlined,
  GlobalOutlined,
  SecurityScanOutlined,
} from "@ant-design/icons";
import { RequestMetadata as RequestMetadataType } from "@/stores/useInferences";
import { copyToClipboard } from "@/utils/clipboard";

const { Text, Title } = Typography;

interface RequestMetadataProps {
  data: RequestMetadataType;
  onCopy?: (content: string, label: string) => void;
}

const RequestMetadata: React.FC<RequestMetadataProps> = ({ data, onCopy }) => {
  if (!data) {
    return <Empty description="No request metadata available" />;
  }

  const handleCopy = async (content: string, label: string) => {
    if (onCopy) {
      onCopy(content, label);
    } else {
      await copyToClipboard(content);
    }
  };

  const getProtocolIcon = (protocol: string | null | undefined) => {
    if (!protocol) return <GlobalOutlined style={{ color: "#999" }} />;
    const isSecure =
      protocol.toLowerCase().includes("https") ||
      protocol.toLowerCase().includes("2");
    return isSecure ? (
      <SecurityScanOutlined style={{ color: "#52c41a" }} />
    ) : (
      <GlobalOutlined style={{ color: "#faad14" }} />
    );
  };

  const formatHeaders = () => {
    if (
      !data.request_headers ||
      Object.keys(data.request_headers).length === 0
    ) {
      return "No headers available";
    }

    return Object.entries(data.request_headers)
      .map(([key, value]) => `${key}: ${value}`)
      .join("\n");
  };

  const renderProxyChain = () => {
    if (!data.proxy_chain) {
      return <Text type="secondary">Direct connection</Text>;
    }

    // Handle proxy_chain as a string (comma-separated list)
    const proxies = data.proxy_chain
      .split(",")
      .map((p) => p.trim())
      .filter((p) => p);
    if (proxies.length === 0) {
      return <Text type="secondary">Direct connection</Text>;
    }

    return (
      <Space direction="vertical" size="small" style={{ width: "100%" }}>
        {proxies.map((proxy, index) => (
          <Tag key={index} color="blue" style={{ marginBottom: 4 }}>
            <LinkOutlined style={{ marginRight: 4 }} />
            {proxy}
          </Tag>
        ))}
      </Space>
    );
  };

  const renderQueryParams = () => {
    if (!data.query_params) {
      return <Text type="secondary">No query parameters</Text>;
    }

    // Handle query_params as a string
    return (
      <Text code style={{ fontSize: "12px" }}>
        {data.query_params}
      </Text>
    );
  };

  return (
    <div>
      <Title level={5} style={{ marginBottom: 16 }}>
        <GlobalOutlined style={{ marginRight: 8 }} />
        Network Information
      </Title>

      <Descriptions bordered column={2} size="small">
        <Descriptions.Item label="IP Address" span={2}>
          <Space>
            <Text strong>{data.client_ip || "Unknown"}</Text>
            {data.client_ip && (
              <Button
                size="small"
                type="link"
                icon={<CopyOutlined />}
                onClick={() => handleCopy(data.client_ip!, "IP Address")}
              />
            )}
            {data.proxy_chain && (
              <Tooltip title="Via Proxy">
                <Tag color="processing">Proxied</Tag>
              </Tooltip>
            )}
          </Space>
        </Descriptions.Item>

        <Descriptions.Item label="Protocol">
          <Space>
            {getProtocolIcon(data.protocol_version)}
            <Text strong>{data.protocol_version || "Unknown"}</Text>
          </Space>
        </Descriptions.Item>

        <Descriptions.Item label="Method">
          <Tag
            color={
              data.method === "POST"
                ? "blue"
                : data.method === "GET"
                  ? "green"
                  : "default"
            }
          >
            {data.method || "Unknown"}
          </Tag>
        </Descriptions.Item>

        <Descriptions.Item label="Path" span={2}>
          <Space style={{ width: "100%" }}>
            <Text code style={{ flex: 1 }}>
              {data.path || "N/A"}
            </Text>
            {data.path && (
              <Button
                size="small"
                type="link"
                icon={<CopyOutlined />}
                onClick={() => handleCopy(data.path!, "Request Path")}
              />
            )}
          </Space>
        </Descriptions.Item>

        {data.body_size && (
          <Descriptions.Item label="Body Size">
            <Text>{data.body_size.toLocaleString()} bytes</Text>
          </Descriptions.Item>
        )}

        {data.status_code && (
          <Descriptions.Item label="Status Code">
            <Tag
              color={
                data.status_code >= 200 && data.status_code < 300
                  ? "success"
                  : data.status_code >= 400
                    ? "error"
                    : "warning"
              }
            >
              {data.status_code}
            </Tag>
          </Descriptions.Item>
        )}

        <Descriptions.Item label="Proxy Chain" span={2}>
          {renderProxyChain()}
        </Descriptions.Item>

        {data.total_duration_ms !== undefined && (
          <Descriptions.Item label="Total Duration">
            <Text>{data.total_duration_ms} ms</Text>
          </Descriptions.Item>
        )}

        {data.query_params && (
          <Descriptions.Item label="Query Parameters" span={2}>
            <div style={{ maxHeight: "150px", overflowY: "auto" }}>
              {renderQueryParams()}
            </div>
          </Descriptions.Item>
        )}

        <Descriptions.Item label="Headers" span={2}>
          <div style={{ maxHeight: "200px", overflowY: "auto" }}>
            <Space style={{ width: "100%" }}>
              <pre
                style={{
                  margin: 0,
                  fontSize: "12px",
                  flex: 1,
                  backgroundColor: "#f5f5f5",
                  padding: "8px",
                  borderRadius: "4px",
                  wordBreak: "break-all",
                  whiteSpace: "pre-wrap",
                }}
              >
                {formatHeaders()}
              </pre>
              <Button
                size="small"
                type="link"
                icon={<CopyOutlined />}
                onClick={() => handleCopy(formatHeaders(), "Request Headers")}
              />
            </Space>
          </div>
        </Descriptions.Item>
      </Descriptions>
    </div>
  );
};

export default RequestMetadata;

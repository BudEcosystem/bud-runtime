import React from "react";
import {
  Descriptions,
  Tag,
  Space,
  Typography,
  Button,
  Empty,
  Avatar,
} from "antd";
import {
  CopyOutlined,
  MobileOutlined,
  TabletOutlined,
  DesktopOutlined,
  RobotOutlined,
  ChromeOutlined,
  AppleOutlined,
  WindowsOutlined,
  AndroidOutlined,
  QuestionCircleOutlined,
} from "@ant-design/icons";
import { ClientInfo as ClientInfoType } from "@/stores/useInferences";
import { copyToClipboard } from "@/utils/clipboard";

const { Text, Title } = Typography;

interface ClientInfoProps {
  data: ClientInfoType;
  onCopy?: (content: string, label: string) => void;
}

const ClientInfo: React.FC<ClientInfoProps> = ({ data, onCopy }) => {
  if (!data) {
    return <Empty description="No client information available" />;
  }

  const handleCopy = async (content: string, label: string) => {
    if (onCopy) {
      onCopy(content, label);
    } else {
      await copyToClipboard(content);
    }
  };

  const getDeviceIcon = (deviceType: string) => {
    switch (deviceType) {
      case "mobile":
        return <MobileOutlined style={{ color: "#52c41a" }} />;
      case "tablet":
        return <TabletOutlined style={{ color: "#1890ff" }} />;
      case "desktop":
        return <DesktopOutlined style={{ color: "#722ed1" }} />;
      default:
        return <QuestionCircleOutlined style={{ color: "#8c8c8c" }} />;
    }
  };

  const getBrowserIcon = (browserName?: string) => {
    if (!browserName) return <QuestionCircleOutlined />;

    const browser = browserName.toLowerCase();
    if (browser.includes("chrome"))
      return <ChromeOutlined style={{ color: "#4285f4" }} />;
    if (browser.includes("firefox"))
      return <Avatar size="small" src="/icons/firefox.png" />;
    if (browser.includes("safari"))
      return <AppleOutlined style={{ color: "#007aff" }} />;
    if (browser.includes("edge"))
      return <Avatar size="small" src="/icons/edge.png" />;
    return <QuestionCircleOutlined style={{ color: "#8c8c8c" }} />;
  };

  const getOSIcon = (osName?: string) => {
    if (!osName) return <QuestionCircleOutlined />;

    const os = osName.toLowerCase();
    if (os.includes("windows"))
      return <WindowsOutlined style={{ color: "#0078d4" }} />;
    if (os.includes("mac") || os.includes("ios"))
      return <AppleOutlined style={{ color: "#007aff" }} />;
    if (os.includes("android"))
      return <AndroidOutlined style={{ color: "#3ddc84" }} />;
    if (os.includes("linux"))
      return <Avatar size="small" src="/icons/linux.png" />;
    return <QuestionCircleOutlined style={{ color: "#8c8c8c" }} />;
  };

  const getDeviceTypeTag = () => {
    const { device_type, is_bot } = data;

    if (is_bot)
      return (
        <Tag color="red" icon={<RobotOutlined />}>
          Bot/Crawler
        </Tag>
      );

    const type = device_type?.toLowerCase();
    if (type === "mobile")
      return (
        <Tag color="green" icon={<MobileOutlined />}>
          Mobile
        </Tag>
      );
    if (type === "tablet")
      return (
        <Tag color="blue" icon={<TabletOutlined />}>
          Tablet
        </Tag>
      );
    if (type === "desktop")
      return (
        <Tag color="purple" icon={<DesktopOutlined />}>
          Desktop
        </Tag>
      );

    return (
      <Tag color="default" icon={<QuestionCircleOutlined />}>
        {device_type || "Unknown"}
      </Tag>
    );
  };

  const renderBrowserInfo = () => {
    if (!data.browser_name && !data.browser_version) {
      return <Text type="secondary">Unknown browser</Text>;
    }

    return (
      <Space>
        {getBrowserIcon(data.browser_name)}
        <Text strong>{data.browser_name || "Unknown"}</Text>
        {data.browser_version && (
          <Text type="secondary">v{data.browser_version}</Text>
        )}
      </Space>
    );
  };

  const renderOSInfo = () => {
    if (!data.os_name && !data.os_version) {
      return <Text type="secondary">Unknown OS</Text>;
    }

    return (
      <Space>
        {getOSIcon(data.os_name)}
        <Text strong>{data.os_name || "Unknown"}</Text>
        {data.os_version && <Text type="secondary">v{data.os_version}</Text>}
      </Space>
    );
  };

  return (
    <div>
      <Title level={5} style={{ marginBottom: 16 }}>
        {getDeviceIcon(data.device_type || "unknown")}
        <span style={{ marginLeft: 8 }}>Client Information</span>
      </Title>

      <Descriptions bordered column={2} size="small">
        <Descriptions.Item label="Device Type" span={2}>
          {getDeviceTypeTag()}
        </Descriptions.Item>

        <Descriptions.Item label="Browser">
          {renderBrowserInfo()}
        </Descriptions.Item>

        <Descriptions.Item label="Operating System">
          {renderOSInfo()}
        </Descriptions.Item>

        {data.is_bot !== undefined && (
          <Descriptions.Item label="Bot Detection" span={2}>
            <Tag color={data.is_bot ? "warning" : "success"}>
              {data.is_bot ? "Bot/Crawler Detected" : "Human User"}
            </Tag>
          </Descriptions.Item>
        )}

        {data.user_agent && (
          <Descriptions.Item label="User Agent" span={2}>
            <div style={{ maxHeight: "100px", overflowY: "auto" }}>
              <Space style={{ width: "100%" }}>
                <Text
                  code
                  style={{
                    flex: 1,
                    wordBreak: "break-all",
                    fontSize: "12px",
                    backgroundColor: "#f5f5f5",
                    padding: "4px 8px",
                    borderRadius: "4px",
                  }}
                >
                  {data.user_agent}
                </Text>
                <Button
                  size="small"
                  type="link"
                  icon={<CopyOutlined />}
                  onClick={() => handleCopy(data.user_agent, "User Agent")}
                />
              </Space>
            </div>
          </Descriptions.Item>
        )}
      </Descriptions>
    </div>
  );
};

export default ClientInfo;

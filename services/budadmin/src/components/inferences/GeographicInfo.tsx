import React from "react";
import {
  Descriptions,
  Tag,
  Space,
  Typography,
  Button,
  Empty,
  Avatar,
  Tooltip,
} from "antd";
import {
  CopyOutlined,
  GlobalOutlined,
  EnvironmentOutlined,
  ClockCircleOutlined,
  WifiOutlined,
  BankOutlined,
  InfoCircleOutlined,
  AimOutlined,
} from "@ant-design/icons";
import { GeographicInfo as GeographicInfoType } from "@/stores/useInferences";
import { copyToClipboard } from "@/utils/clipboard";

const { Text, Title } = Typography;

interface GeographicInfoProps {
  data: GeographicInfoType;
  onCopy?: (content: string, label: string) => void;
}

const GeographicInfo: React.FC<GeographicInfoProps> = ({ data, onCopy }) => {
  if (!data) {
    return <Empty description="No geographic information available" />;
  }

  const handleCopy = async (content: string, label: string) => {
    if (onCopy) {
      onCopy(content, label);
    } else {
      await copyToClipboard(content);
    }
  };

  const getCountryFlag = (countryCode?: string) => {
    if (!countryCode) return null;

    // Convert country code to flag emoji
    const flag = countryCode
      .toUpperCase()
      .replace(/./g, (char) =>
        String.fromCodePoint(char.charCodeAt(0) + 127397),
      );

    return <span style={{ fontSize: "16px", marginRight: "8px" }}>{flag}</span>;
  };

  const renderLocation = () => {
    const locationParts = [];

    if (data.city) locationParts.push(data.city);
    if (data.region) locationParts.push(data.region);
    if (data.country_name) locationParts.push(data.country_name);

    if (locationParts.length === 0) {
      return <Text type="secondary">Unknown location</Text>;
    }

    return (
      <Space>
        <EnvironmentOutlined style={{ color: "#52c41a" }} />
        {getCountryFlag(data.country_code)}
        <Text strong>{locationParts.join(", ")}</Text>
      </Space>
    );
  };

  const renderCoordinates = () => {
    if (!data.latitude || !data.longitude) {
      return <Text type="secondary">Not available</Text>;
    }

    const coordinates = `${data.latitude.toFixed(6)}, ${data.longitude.toFixed(6)}`;
    const mapsUrl = `https://www.google.com/maps?q=${data.latitude},${data.longitude}`;

    return (
      <Space>
        <AimOutlined style={{ color: "#1890ff" }} />
        <Text code>{coordinates}</Text>
        <Button
          size="small"
          type="link"
          icon={<CopyOutlined />}
          onClick={() => handleCopy(coordinates, "Coordinates")}
        />
        <Button
          size="small"
          type="link"
          onClick={() => window.open(mapsUrl, "_blank")}
        >
          View on Maps
        </Button>
      </Space>
    );
  };

  const renderTimezone = () => {
    if (!data.timezone) {
      return <Text type="secondary">Unknown timezone</Text>;
    }

    try {
      const now = new Date();
      const timeInZone = now.toLocaleString("en-US", {
        timeZone: data.timezone,
        weekday: "short",
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        timeZoneName: "short",
      });

      return (
        <Space>
          <ClockCircleOutlined style={{ color: "#722ed1" }} />
          <Text strong>{data.timezone}</Text>
          <Text type="secondary">({timeInZone})</Text>
        </Space>
      );
    } catch (error) {
      return (
        <Space>
          <ClockCircleOutlined style={{ color: "#722ed1" }} />
          <Text strong>{data.timezone}</Text>
        </Space>
      );
    }
  };

  const renderISPInfo = () => {
    if (!data.isp && !data.asn) {
      return <Text type="secondary">Unknown ISP</Text>;
    }

    return (
      <Space direction="vertical" size="small">
        {data.isp && (
          <div>
            <WifiOutlined style={{ color: "#1890ff", marginRight: 8 }} />
            <Text strong>ISP:</Text> <Text>{data.isp}</Text>
          </div>
        )}
        {data.asn && (
          <div>
            <Text strong>AS Number:</Text> <Text code>AS{data.asn}</Text>
          </div>
        )}
      </Space>
    );
  };

  return (
    <div>
      <Title level={5} style={{ marginBottom: 16 }}>
        <GlobalOutlined style={{ marginRight: 8 }} />
        Geographic Information
      </Title>

      <Descriptions bordered column={1} size="small">
        <Descriptions.Item label="Location">
          {renderLocation()}
        </Descriptions.Item>

        <Descriptions.Item label="Country Details">
          <Space>
            {data.country_name && (
              <Tag color="blue">
                {getCountryFlag(data.country_code)}
                {data.country_name}
                {data.country_code && ` (${data.country_code.toUpperCase()})`}
              </Tag>
            )}
            {data.region && <Tag color="cyan">{data.region}</Tag>}
          </Space>
        </Descriptions.Item>

        <Descriptions.Item label="Coordinates">
          {renderCoordinates()}
        </Descriptions.Item>

        <Descriptions.Item label="Timezone">
          {renderTimezone()}
        </Descriptions.Item>

        <Descriptions.Item label="Network Provider">
          {renderISPInfo()}
        </Descriptions.Item>
      </Descriptions>
    </div>
  );
};

export default GeographicInfo;

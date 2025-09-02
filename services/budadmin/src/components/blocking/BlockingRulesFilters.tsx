import React, { useState, useEffect } from "react";
import { Card, Select, Button, Row, Col, Form, ConfigProvider } from "antd";
import { FilterOutlined, ClearOutlined } from "@ant-design/icons";
import {
  BlockingRuleType,
  BlockingRuleStatus,
} from "@/stores/useBlockingRules";
import { RULE_TYPE_VALUES, RULE_TYPE_LABELS } from "@/constants/blockingRules";

const { Option } = Select;

interface BlockingRulesFiltersProps {
  onFiltersChange: (filters: any) => void;
}

const BlockingRulesFilters: React.FC<BlockingRulesFiltersProps> = ({
  onFiltersChange,
}) => {
  const [form] = Form.useForm();
  const [filters, setFiltersState] = useState<any>({});

  const handleFilterChange = (changedValues: any) => {
    const newFilters = { ...filters };

    // Handle filters
    const filterMap: Record<string, string> = {
      ruleType: "rule_type",
      status: "status",
    };

    Object.keys(changedValues).forEach((key) => {
      if (filterMap[key]) {
        if (
          changedValues[key] === undefined ||
          changedValues[key] === null ||
          changedValues[key] === ""
        ) {
          delete newFilters[filterMap[key]];
        } else {
          newFilters[filterMap[key]] = changedValues[key];
        }
      }
    });

    setFiltersState(newFilters);
    onFiltersChange(newFilters);
  };

  const handleReset = () => {
    form.resetFields();
    setFiltersState({});
    onFiltersChange({});
  };

  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: "#965CDE",
          colorPrimaryHover: "#a873e5",
          colorPrimaryActive: "#8348c7",
        },
        components: {
          Card: {
            colorBgContainer: "#101010",
            colorBorder: "#1F1F1F",
            colorText: "#EEEEEE",
            colorTextHeading: "#EEEEEE",
          },
          Select: {
            colorBgContainer: "#1A1A1A",
            colorBorder: "#1F1F1F",
            colorText: "#EEEEEE",
            colorTextPlaceholder: "#666666",
            colorBgElevated: "#1A1A1A",
            controlItemBgHover: "#2F2F2F",
            optionSelectedBg: "#2A1F3D",
          },
          Button: {
            colorBgContainer: "#1F1F1F",
            colorBorder: "#1F1F1F",
            colorText: "#EEEEEE",
            colorPrimaryBg: "#1F1F1F",
            colorPrimaryText: "#EEEEEE",
          },
          Form: {
            labelColor: "#B3B3B3",
          },
        },
      }}
    >
      <Card
        size="small"
        className="bg-[#101010] border-[#1F1F1F]"
        title={
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <FilterOutlined
              className="text-[#EEEEEE]"
              style={{ fontSize: "14px", display: "flex" }}
            />
            <span className="text-[#EEEEEE]">Filters</span>
          </div>
        }
        extra={
          <Button
            size="small"
            icon={<ClearOutlined />}
            onClick={handleReset}
            className="bg-[#1F1F1F] border-[#1F1F1F] text-[#EEEEEE] hover:bg-[#2F2F2F] hover:border-[#2F2F2F]"
          >
            Clear All
          </Button>
        }
        styles={{
          header: {
            borderBottom: "1px solid #1F1F1F",
            paddingTop: "8px",
            paddingBottom: "8px",
          },
        }}
      >
        <Form form={form} layout="vertical" onValuesChange={handleFilterChange}>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                label={<span className="text-[#B3B3B3]">Rule Type</span>}
                name="ruleType"
              >
                <Select
                  style={{ width: "100%" }}
                  placeholder="All Types"
                  allowClear
                  className="bg-[#1A1A1A]"
                  dropdownStyle={{ backgroundColor: "#1A1A1A" }}
                >
                  {Object.entries(RULE_TYPE_VALUES).map(([key, value]) => (
                    <Option key={value} value={value}>
                      {RULE_TYPE_LABELS[value]}
                    </Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>

            <Col span={12}>
              <Form.Item
                label={<span className="text-[#B3B3B3]">Status</span>}
                name="status"
              >
                <Select
                  style={{ width: "100%" }}
                  placeholder="All Status"
                  allowClear
                  className="bg-[#1A1A1A]"
                  dropdownStyle={{ backgroundColor: "#1A1A1A" }}
                >
                  <Option value="ACTIVE">Active</Option>
                  <Option value="INACTIVE">Inactive</Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Card>
    </ConfigProvider>
  );
};

export default BlockingRulesFilters;

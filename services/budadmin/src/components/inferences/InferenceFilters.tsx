import React, { useState, useEffect } from 'react';
import { Card, DatePicker, Select, InputNumber, Switch, Space, Button, Row, Col, Form, ConfigProvider } from 'antd';
import { FilterOutlined, ClearOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { useInferences } from '@/stores/useInferences';
import { useEndPoints } from 'src/hooks/useEndPoint';

const { RangePicker } = DatePicker;
const { Option } = Select;

interface InferenceFiltersProps {
  projectId: string;
  onFiltersChange: () => void;
}

const InferenceFilters: React.FC<InferenceFiltersProps> = ({ projectId, onFiltersChange }) => {
  const [form] = Form.useForm();

  const { filters, setFilters, resetFilters } = useInferences();
  const { endPoints, getEndPoints } = useEndPoints();

  // Fetch endpoints when component mounts or projectId changes
  useEffect(() => {
    if (projectId === 'all') {
      // Fetch all endpoints across all projects (no project_id parameter)
      getEndPoints({
        id: null, // Pass null to fetch all endpoints
        page: 1,
        limit: 1000, // Get more endpoints for global view
      });
    } else if (projectId) {
      // Fetch endpoints for specific project
      getEndPoints({
        id: projectId,
        page: 1,
        limit: 100,
      });
    }
  }, [projectId]);

  const handleFilterChange = (changedValues: any) => {
    // Handle date range
    if (changedValues.dateRange) {
      const [fromDate, toDate] = changedValues.dateRange;
      setFilters({
        from_date: fromDate ? fromDate.toISOString() : undefined,
        to_date: toDate ? toDate.toISOString() : undefined,
      });
    }

    // Handle other filters
    const filterMap: Record<string, string> = {
      isSuccess: 'is_success',
      minTokens: 'min_tokens',
      maxTokens: 'max_tokens',
      maxLatency: 'max_latency_ms',
      endpointId: 'endpoint_id',
    };

    Object.keys(changedValues).forEach((key) => {
      if (key !== 'dateRange' && filterMap[key]) {
        // Special handling for isSuccess - if false/undefined, remove the filter
        if (key === 'isSuccess') {
          setFilters({ [filterMap[key]]: changedValues[key] || undefined });
        } else {
          setFilters({ [filterMap[key]]: changedValues[key] });
        }
      }
    });

    // Trigger data refresh
    onFiltersChange();
  };

  const handleReset = () => {
    form.resetFields();
    resetFilters();
    onFiltersChange();
  };

  const quickDateOptions = [
    { label: 'Last 1 hour', value: 1 },
    { label: 'Last 6 hours', value: 6 },
    { label: 'Last 24 hours', value: 24 },
    { label: 'Last 7 days', value: 24 * 7 },
    { label: 'Last 30 days', value: 24 * 30 },
  ];

  const handleQuickDate = (hours: number) => {
    const now = dayjs();
    const fromDate = now.subtract(hours, 'hour');

    form.setFieldsValue({
      dateRange: [fromDate, now],
    });

    setFilters({
      from_date: fromDate.toISOString(),
      to_date: now.toISOString(),
    });

    onFiltersChange();
  };

  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#965CDE',
          colorPrimaryHover: '#a873e5',
          colorPrimaryActive: '#8348c7',
        },
        components: {
          Card: {
            colorBgContainer: '#101010',
            colorBorder: '#1F1F1F',
            colorText: '#EEEEEE',
            colorTextHeading: '#EEEEEE',
          },
          DatePicker: {
            colorBgContainer: '#1A1A1A',
            colorBorder: '#1F1F1F',
            colorText: '#EEEEEE',
            colorTextPlaceholder: '#666666',
            colorBgElevated: '#1A1A1A',
            colorPrimary: '#965CDE',
            colorPrimaryBg: '#2A1F3D',
            colorPrimaryBgHover: '#3A2F4D',
            colorTextLightSolid: '#FFFFFF',
            controlItemBgActive: '#965CDE',
            colorLink: '#965CDE',
            colorLinkHover: '#a873e5',
            colorLinkActive: '#8348c7',
          },
          InputNumber: {
            colorBgContainer: '#1A1A1A',
            colorBorder: '#1F1F1F',
            colorText: '#EEEEEE',
            colorTextPlaceholder: '#666666',
          },
          Select: {
            colorBgContainer: '#1A1A1A',
            colorBorder: '#1F1F1F',
            colorText: '#EEEEEE',
            colorTextPlaceholder: '#666666',
            colorBgElevated: '#1A1A1A',
            controlItemBgHover: '#2F2F2F',
            optionSelectedBg: '#2A1F3D',
          },
          Switch: {
            colorPrimary: '#965CDE',
            colorPrimaryHover: '#a873e5',
          },
          Button: {
            colorBgContainer: '#1F1F1F',
            colorBorder: '#1F1F1F',
            colorText: '#EEEEEE',
            colorPrimaryBg: '#1F1F1F',
            colorPrimaryText: '#EEEEEE',
          },
          Form: {
            labelColor: '#B3B3B3',
          },
        },
      }}
    >
      <Card
        size="small"
        className="bg-[#101010] border-[#1F1F1F]"
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FilterOutlined className="text-[#EEEEEE]" style={{ fontSize: '14px', display: 'flex' }} />
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
            borderBottom: '1px solid #1F1F1F',
            paddingTop: '8px',
            paddingBottom: '8px'
          }
        }}
      >
      <Form
        form={form}
        layout="vertical"
        onValuesChange={handleFilterChange}
        initialValues={{
          dateRange: filters.from_date ? [dayjs(filters.from_date), filters.to_date ? dayjs(filters.to_date) : null] : null,
          isSuccess: filters.is_success,
          minTokens: filters.min_tokens,
          maxTokens: filters.max_tokens,
          maxLatency: filters.max_latency_ms,
          endpointId: filters.endpoint_id,
        }}
      >
        <Row gutter={16}>
          <Col span={8}>
            <Form.Item
              label={<span className="text-[#B3B3B3]">Date Range</span>}
              name="dateRange"
            >
              <RangePicker
                showTime
                style={{ width: '100%' }}
                format="YYYY-MM-DD HH:mm"
                placeholder={['Start Date', 'End Date']}
                className="bg-[#1A1A1A] border-[#1F1F1F] hover:border-[#3F3F3F]"
              />
            </Form.Item>
          </Col>

          <Col span={5}>
            <Form.Item
              label={<span className="text-[#B3B3B3]">Deployment</span>}
              name="endpointId"
            >
              <Select
                style={{ width: '100%' }}
                placeholder="All Deployments"
                allowClear
                className="bg-[#1A1A1A]"
                dropdownStyle={{ backgroundColor: '#1A1A1A' }}
                showSearch
                filterOption={(input, option) =>
                  option?.children?.toString().toLowerCase().includes(input.toLowerCase()) ?? false
                }
              >
                {endPoints?.map((endpoint: any) => (
                  <Option key={endpoint.id} value={endpoint.id}>
                    {endpoint.name}
                  </Option>
                ))}
              </Select>
            </Form.Item>
          </Col>

          <Col span={3}>
            <Form.Item
              label={<span className="text-[#B3B3B3]">Min Tokens</span>}
              name="minTokens"
            >
              <InputNumber
                style={{ width: '100%' }}
                min={0}
                placeholder="Min"
                className="bg-[#1A1A1A] border-[#1F1F1F] hover:border-[#3F3F3F] text-[#EEEEEE]"
              />
            </Form.Item>
          </Col>

          <Col span={3}>
            <Form.Item
              label={<span className="text-[#B3B3B3]">Max Tokens</span>}
              name="maxTokens"
            >
              <InputNumber
                style={{ width: '100%' }}
                min={0}
                placeholder="Max"
                className="bg-[#1A1A1A] border-[#1F1F1F] hover:border-[#3F3F3F] text-[#EEEEEE]"
              />
            </Form.Item>
          </Col>

          <Col span={5}>
            <Form.Item
              label={<span className="text-[#B3B3B3]">Max Latency (ms)</span>}
              name="maxLatency"
            >
              <InputNumber
                style={{ width: '100%' }}
                min={0}
                placeholder="Max latency"
                className="bg-[#1A1A1A] border-[#1F1F1F] hover:border-[#3F3F3F] text-[#EEEEEE]"
              />
            </Form.Item>
          </Col>
        </Row>

        <Row gutter={16} align="middle">
          <Col span={24}>
            <Space wrap style={{ marginBottom: 16 }}>
              {quickDateOptions.map((option) => (
                <Button
                  key={option.value}
                  size="small"
                  onClick={() => handleQuickDate(option.value)}
                  className="bg-[#1F1F1F] border-[#1F1F1F] text-[#B3B3B3] hover:bg-[#2F2F2F] hover:border-[#2F2F2F] hover:text-[#EEEEEE]"
                >
                  {option.label}
                </Button>
              ))}

              <div style={{ marginLeft: '16px', display: 'inline-flex', alignItems: 'center' }}>
                <span className="text-[#EEEEEE]" style={{ marginRight: '8px' }}>Show only successful:</span>
                <Form.Item name="isSuccess" valuePropName="checked" noStyle>
                  <Switch className="bg-[#1F1F1F]" />
                </Form.Item>
              </div>
            </Space>
          </Col>
        </Row>
      </Form>
    </Card>
    </ConfigProvider>
  );
};

export default InferenceFilters;

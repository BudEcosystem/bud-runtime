import React, { useState } from 'react';
import { Card, DatePicker, Select, InputNumber, Switch, Space, Button, Row, Col, Form } from 'antd';
import { FilterOutlined, ClearOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { useInferences } from '@/stores/useInferences';

const { RangePicker } = DatePicker;
const { Option } = Select;

interface InferenceFiltersProps {
  projectId: string;
  onFiltersChange: () => void;
}

const InferenceFilters: React.FC<InferenceFiltersProps> = ({ projectId, onFiltersChange }) => {
  const [form] = Form.useForm();
  const [showAdvanced, setShowAdvanced] = useState(false);
  
  const { filters, setFilters, resetFilters } = useInferences();
  
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
    };
    
    Object.keys(changedValues).forEach((key) => {
      if (key !== 'dateRange' && filterMap[key]) {
        setFilters({ [filterMap[key]]: changedValues[key] });
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
    <Card
      size="small"
      title={
        <Space>
          <FilterOutlined />
          <span>Filters</span>
        </Space>
      }
      extra={
        <Space>
          <Button size="small" onClick={() => setShowAdvanced(!showAdvanced)}>
            {showAdvanced ? 'Hide' : 'Show'} Advanced
          </Button>
          <Button size="small" icon={<ClearOutlined />} onClick={handleReset}>
            Clear
          </Button>
        </Space>
      }
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
        }}
      >
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item label="Date Range" name="dateRange">
              <RangePicker
                showTime
                style={{ width: '100%' }}
                format="YYYY-MM-DD HH:mm"
                placeholder={['Start Date', 'End Date']}
              />
            </Form.Item>
            <Space wrap style={{ marginBottom: 16 }}>
              {quickDateOptions.map((option) => (
                <Button
                  key={option.value}
                  size="small"
                  onClick={() => handleQuickDate(option.value)}
                >
                  {option.label}
                </Button>
              ))}
            </Space>
          </Col>
          
          <Col span={12}>
            <Form.Item label="Status Filter">
              <Space>
                <span>Show only successful:</span>
                <Form.Item name="isSuccess" valuePropName="checked" noStyle>
                  <Switch />
                </Form.Item>
              </Space>
            </Form.Item>
          </Col>
        </Row>
        
        {showAdvanced && (
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item label="Min Tokens" name="minTokens">
                <InputNumber
                  style={{ width: '100%' }}
                  min={0}
                  placeholder="Minimum token count"
                />
              </Form.Item>
            </Col>
            
            <Col span={8}>
              <Form.Item label="Max Tokens" name="maxTokens">
                <InputNumber
                  style={{ width: '100%' }}
                  min={0}
                  placeholder="Maximum token count"
                />
              </Form.Item>
            </Col>
            
            <Col span={8}>
              <Form.Item label="Max Latency (ms)" name="maxLatency">
                <InputNumber
                  style={{ width: '100%' }}
                  min={0}
                  placeholder="Maximum latency"
                />
              </Form.Item>
            </Col>
          </Row>
        )}
      </Form>
    </Card>
  );
};

export default InferenceFilters;
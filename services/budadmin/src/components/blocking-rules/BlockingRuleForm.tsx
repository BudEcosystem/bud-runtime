import React, { useState, useEffect } from 'react';
import { Form, Input, Select, InputNumber, Button, Space, Tag, Switch, Alert } from 'antd';
import { PlusOutlined, MinusCircleOutlined } from '@ant-design/icons';
import { BlockingRuleType, BlockingRuleStatus, BlockingRuleCreate, BlockingRuleUpdate } from '@/stores/useBlockingRules';
import { PrimaryButton, SecondaryButton } from '@/components/ui/bud/form/Buttons';

const { TextArea } = Input;
const { Option } = Select;

interface BlockingRuleFormProps {
  initialValues?: any;
  onSubmit: (values: BlockingRuleCreate | BlockingRuleUpdate) => Promise<void>;
  onCancel: () => void;
  isLoading: boolean;
}

// Country codes for country blocking
const COUNTRY_CODES = [
  { code: 'US', name: 'United States' },
  { code: 'CN', name: 'China' },
  { code: 'RU', name: 'Russia' },
  { code: 'IN', name: 'India' },
  { code: 'JP', name: 'Japan' },
  { code: 'DE', name: 'Germany' },
  { code: 'GB', name: 'United Kingdom' },
  { code: 'FR', name: 'France' },
  { code: 'BR', name: 'Brazil' },
  { code: 'CA', name: 'Canada' },
  { code: 'AU', name: 'Australia' },
  { code: 'KR', name: 'South Korea' },
  { code: 'MX', name: 'Mexico' },
  { code: 'ES', name: 'Spain' },
  { code: 'IT', name: 'Italy' },
  // Add more as needed
];

const BlockingRuleForm: React.FC<BlockingRuleFormProps> = ({
  initialValues,
  onSubmit,
  onCancel,
  isLoading,
}) => {
  const [form] = Form.useForm();
  const [ruleType, setRuleType] = useState<BlockingRuleType>(
    initialValues?.rule_type || 'IP_BLOCKING'
  );

  useEffect(() => {
    if (initialValues) {
      // Transform the rule_config based on type for form display
      const formValues = {
        ...initialValues,
        ...transformConfigForForm(initialValues.rule_type, initialValues.rule_config),
      };
      form.setFieldsValue(formValues);
      setRuleType(initialValues.rule_type);
    }
  }, [initialValues, form]);

  const transformConfigForForm = (type: BlockingRuleType, config: any) => {
    if (!config) return {};

    switch (type) {
      case 'IP_BLOCKING':
        return { ip_addresses: config.ip_addresses || [] };
      case 'COUNTRY_BLOCKING':
        return { countries: config.countries || [] };
      case 'USER_AGENT_BLOCKING':
        return { patterns: config.patterns || [] };
      case 'RATE_BASED_BLOCKING':
        return {
          threshold: config.threshold || 100,
          window_seconds: config.window_seconds || 60,
        };
      default:
        return {};
    }
  };

  const transformFormToConfig = (type: BlockingRuleType, values: any) => {
    switch (type) {
      case 'IP_BLOCKING':
        return { ip_addresses: values.ip_addresses || [] };
      case 'COUNTRY_BLOCKING':
        return { countries: values.countries || [] };
      case 'USER_AGENT_BLOCKING':
        return { patterns: values.patterns || [] };
      case 'RATE_BASED_BLOCKING':
        return {
          threshold: values.threshold || 100,
          window_seconds: values.window_seconds || 60,
        };
      default:
        return {};
    }
  };

  const handleSubmit = async (values: any) => {
    const rule_config = transformFormToConfig(values.rule_type, values);

    const submitData = {
      name: values.name,
      description: values.description,
      rule_type: values.rule_type,
      rule_config,
      status: values.status || 'ACTIVE',
      reason: values.reason,
      priority: values.priority || 50,
      endpoint_id: values.endpoint_id,
    };

    await onSubmit(submitData);
  };

  const validateIPAddress = (_: any, value: string) => {
    if (!value) return Promise.resolve();

    // Basic IP or CIDR validation
    const ipRegex = /^(\d{1,3}\.){3}\d{1,3}(\/\d{1,2})?$/;
    if (!ipRegex.test(value)) {
      return Promise.reject(new Error('Invalid IP address or CIDR format'));
    }

    // Check if octets are valid
    const parts = value.split(/[\.\/]/);
    for (let i = 0; i < 4; i++) {
      const octet = parseInt(parts[i]);
      if (octet < 0 || octet > 255) {
        return Promise.reject(new Error('Invalid IP address'));
      }
    }

    // Check CIDR if present
    if (value.includes('/')) {
      const cidr = parseInt(parts[4]);
      if (cidr < 0 || cidr > 32) {
        return Promise.reject(new Error('Invalid CIDR notation'));
      }
    }

    return Promise.resolve();
  };

  const renderRuleTypeConfig = () => {
    switch (ruleType) {
      case 'IP_BLOCKING':
        return (
          <>
            <Form.List name="ip_addresses">
              {(fields, { add, remove }) => (
                <>
                  <Form.Item label="IP Addresses / CIDR Blocks">
                    <Space direction="vertical" style={{ width: '100%' }}>
                      {fields.map((field, index) => (
                        <Space key={field.key} style={{ display: 'flex' }} align="baseline">
                          <Form.Item
                            {...field}
                            validateTrigger={['onChange', 'onBlur']}
                            rules={[
                              { required: true, message: 'IP address is required' },
                              { validator: validateIPAddress },
                            ]}
                            noStyle
                          >
                            <Input
                              placeholder="e.g., 192.168.1.1 or 10.0.0.0/24"
                              style={{ width: 300 }}
                            />
                          </Form.Item>
                          <MinusCircleOutlined onClick={() => remove(field.name)} />
                        </Space>
                      ))}
                      <Button type="dashed" onClick={() => add()} icon={<PlusOutlined />}>
                        Add IP Address
                      </Button>
                    </Space>
                  </Form.Item>
                </>
              )}
            </Form.List>
          </>
        );

      case 'COUNTRY_BLOCKING':
        return (
          <Form.Item
            name="countries"
            label="Countries to Block"
            rules={[{ required: true, message: 'Please select at least one country' }]}
          >
            <Select
              mode="multiple"
              placeholder="Select countries"
              style={{ width: '100%' }}
              showSearch
              filterOption={(input, option) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
              options={COUNTRY_CODES.map(country => ({
                label: `${country.name} (${country.code})`,
                value: country.code,
              }))}
            />
          </Form.Item>
        );

      case 'USER_AGENT_BLOCKING':
        return (
          <Form.List name="patterns">
            {(fields, { add, remove }) => (
              <>
                <Form.Item label="User Agent Patterns (Regex)">
                  <Space direction="vertical" style={{ width: '100%' }}>
                    {fields.map((field, index) => (
                      <Space key={field.key} style={{ display: 'flex' }} align="baseline">
                        <Form.Item
                          {...field}
                          rules={[{ required: true, message: 'Pattern is required' }]}
                          noStyle
                        >
                          <Input
                            placeholder="e.g., bot|crawler|spider"
                            style={{ width: 400 }}
                          />
                        </Form.Item>
                        <MinusCircleOutlined onClick={() => remove(field.name)} />
                      </Space>
                    ))}
                    <Button type="dashed" onClick={() => add()} icon={<PlusOutlined />}>
                      Add Pattern
                    </Button>
                  </Space>
                </Form.Item>
                <Alert
                  message="Use regex patterns to match user agents. Example: 'bot|crawler' will block any user agent containing 'bot' or 'crawler'."
                  type="info"
                  showIcon
                  className="mt-2"
                />
              </>
            )}
          </Form.List>
        );

      case 'RATE_BASED_BLOCKING':
        return (
          <>
            <Form.Item
              name="threshold"
              label="Request Threshold"
              rules={[{ required: true, message: 'Threshold is required' }]}
            >
              <InputNumber
                min={1}
                max={10000}
                style={{ width: 200 }}
                placeholder="e.g., 100"
                addonAfter="requests"
              />
            </Form.Item>
            <Form.Item
              name="window_seconds"
              label="Time Window"
              rules={[{ required: true, message: 'Time window is required' }]}
            >
              <InputNumber
                min={1}
                max={3600}
                style={{ width: 200 }}
                placeholder="e.g., 60"
                addonAfter="seconds"
              />
            </Form.Item>
            <Alert
              message="Block clients that exceed the specified number of requests within the time window."
              type="info"
              showIcon
              className="mt-2"
            />
          </>
        );

      default:
        return null;
    }
  };

  return (
    <Form
      form={form}
      layout="vertical"
      onFinish={handleSubmit}
      initialValues={{
        rule_type: 'IP_BLOCKING',
        status: 'ACTIVE',
        priority: 50,
      }}
    >
      <Form.Item
        name="name"
        label="Rule Name"
        rules={[{ required: true, message: 'Rule name is required' }]}
      >
        <Input placeholder="e.g., Block suspicious IPs" />
      </Form.Item>

      <Form.Item
        name="description"
        label="Description"
      >
        <TextArea
          rows={2}
          placeholder="Optional description of what this rule does"
        />
      </Form.Item>

      <Form.Item
        name="rule_type"
        label="Rule Type"
        rules={[{ required: true, message: 'Rule type is required' }]}
      >
        <Select
          onChange={setRuleType}
          disabled={!!initialValues}
        >
          <Option value="IP_BLOCKING">IP Blocking</Option>
          <Option value="COUNTRY_BLOCKING">Country Blocking</Option>
          <Option value="USER_AGENT_BLOCKING">User Agent Blocking</Option>
          <Option value="RATE_BASED_BLOCKING">Rate-based Blocking</Option>
        </Select>
      </Form.Item>

      {renderRuleTypeConfig()}

      <Form.Item
        name="reason"
        label="Reason for Blocking"
        rules={[{ required: true, message: 'Reason is required' }]}
      >
        <Input placeholder="e.g., Security threat, Abuse prevention" />
      </Form.Item>

      <Form.Item
        name="priority"
        label="Priority"
        tooltip="Lower numbers have higher priority (1-100)"
      >
        <InputNumber
          min={1}
          max={100}
          style={{ width: 120 }}
        />
      </Form.Item>

      <Form.Item
        name="status"
        label="Status"
        valuePropName="checked"
      >
        <Select defaultValue="ACTIVE">
          <Option value="ACTIVE">
            <Tag color="success">Active</Tag>
          </Option>
          <Option value="INACTIVE">
            <Tag color="default">Inactive</Tag>
          </Option>
        </Select>
      </Form.Item>

      <Form.Item>
        <Space>
          <PrimaryButton htmlType="submit" loading={isLoading}>
            {initialValues ? 'Update Rule' : 'Create Rule'}
          </PrimaryButton>
          <SecondaryButton onClick={onCancel}>
            Cancel
          </SecondaryButton>
        </Space>
      </Form.Item>
    </Form>
  );
};

export default BlockingRuleForm;

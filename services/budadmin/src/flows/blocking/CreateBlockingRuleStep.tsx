import React, { useState, useEffect, useContext, useMemo } from 'react';
import { Form, Input, Select, InputNumber, Space, Tag, message, Button, Image, ConfigProvider } from 'antd';
import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons';
import { useBlockingRules, BlockingRuleType, BlockingRuleStatus } from '@/stores/useBlockingRules';
import { RULE_TYPE_VALUES, RULE_TYPE_LABELS, COUNTRY_CODES } from '@/constants/blockingRules';
import { useDrawer } from '@/hooks/useDrawer';
import { useLoader } from '../../context/appContext';
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { Text_12_300_EEEEEE, Text_12_400_B3B3B3 } from '@/components/ui/text';
import CustomPopover from "src/flows/components/customPopover";

const { TextArea } = Input;
const { Option } = Select;

interface CreateBlockingRuleStepProps {}

function RuleForm({ setDisableNext }) {
  const { form } = useContext(BudFormContext);
  const { createRule } = useBlockingRules();
  const { drawerProps } = useDrawer();

  // Check if we're in edit mode
  const isEditMode = drawerProps?.editMode;
  const editRule = drawerProps?.rule;
  const { showLoader, hideLoader } = useLoader();

  // Watch specific form fields to ensure they're displayed
  const nameValue = Form.useWatch('name', form);
  const reasonValue = Form.useWatch('reason', form);
  const priorityValue = Form.useWatch('priority', form);

  const [ruleType, setRuleType] = useState<BlockingRuleType>(
    isEditMode && editRule ? editRule.rule_type : RULE_TYPE_VALUES.IP_BLOCKING
  );

  // Force re-render when form values change
  const [, forceUpdate] = useState({});

  useEffect(() => {
    if (isEditMode && editRule) {
      // Set rule type to ensure correct fields are rendered
      setRuleType(editRule.rule_type);

      // Manually set form values here as a fallback
      // This ensures values are set even if BudForm's setting was overridden
      setTimeout(() => {
        const currentValues = form.getFieldsValue();

        // If form values are empty but we have edit data, set them manually
        if (!currentValues.name && editRule.name) {
          const formData: any = {
            name: editRule.name,
            rule_type: editRule.rule_type,
            reason: editRule.reason,
            priority: editRule.priority || 100,
          };

          // Add rule-specific configuration
          if (editRule.rule_config) {
            switch (editRule.rule_type) {
              case RULE_TYPE_VALUES.IP_BLOCKING:
                formData.ip_addresses = editRule.rule_config.ip_addresses || [];
                break;
              case RULE_TYPE_VALUES.COUNTRY_BLOCKING:
                formData.countries = editRule.rule_config.countries || [];
                break;
              case RULE_TYPE_VALUES.USER_AGENT_BLOCKING:
                formData.patterns = editRule.rule_config.patterns || [];
                break;
              case RULE_TYPE_VALUES.RATE_BASED_BLOCKING:
                formData.threshold = editRule.rule_config.threshold?.toString() || '';
                formData.window_seconds = editRule.rule_config.window_seconds?.toString() || '';
                break;
            }
          }

          form.setFieldsValue(formData);
        }

        // Force component re-render to display the values
        forceUpdate({});
        handleFieldsChange();
      }, 300);
    } else {
      // Set default rule type for new rules
      setRuleType(RULE_TYPE_VALUES.IP_BLOCKING);
      setTimeout(() => {
        handleFieldsChange();
      }, 200);
    }
  }, [isEditMode, editRule]);

  const handleFieldsChange = () => {
    const fieldsValue = form.getFieldsValue(true);
    const hasErrors = form.getFieldsError().some(({ errors }) => errors.length > 0);

    // Check required fields for global rules
    let requiredFieldsFilled = fieldsValue.name && fieldsValue.reason && fieldsValue.rule_type;

    // Check rule-specific fields
    switch (fieldsValue.rule_type || ruleType) {
      case RULE_TYPE_VALUES.IP_BLOCKING:
        requiredFieldsFilled = requiredFieldsFilled && fieldsValue.ip_addresses && fieldsValue.ip_addresses.length > 0;
        break;
      case RULE_TYPE_VALUES.COUNTRY_BLOCKING:
        requiredFieldsFilled = requiredFieldsFilled && fieldsValue.countries && fieldsValue.countries.length > 0;
        break;
      case RULE_TYPE_VALUES.USER_AGENT_BLOCKING:
        requiredFieldsFilled = requiredFieldsFilled && fieldsValue.patterns && fieldsValue.patterns.length > 0;
        break;
      case RULE_TYPE_VALUES.RATE_BASED_BLOCKING:
        requiredFieldsFilled = requiredFieldsFilled &&
          fieldsValue.threshold && fieldsValue.threshold.toString().trim() !== '' &&
          fieldsValue.window_seconds && fieldsValue.window_seconds.toString().trim() !== '';
        break;
    }

    setDisableNext(!requiredFieldsFilled || hasErrors);
  };

  const getRuleConfigFields = () => {
    switch (ruleType) {
      case RULE_TYPE_VALUES.IP_BLOCKING:
        return (
          <Form.Item
            className="flex items-start rounded-[6px] relative !bg-[transparent] w-[100%] mb-[0]"
          >
            <div className="w-full">
              <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap">
                IP Addresses to Block
                <CustomPopover title="Add IP addresses to block">
                  <Image src="/images/info.png" preview={false} alt="info" style={{ width: '.75rem', height: '.75rem' }} />
                </CustomPopover>
              </Text_12_300_EEEEEE>
            </div>
            <div className="w-full pt-2">
              <Form.List name="ip_addresses" initialValue={isEditMode && editRule?.rule_config?.ip_addresses ? editRule.rule_config.ip_addresses : []}>
                {(fields, { add, remove }) => (
                  <>
                    {fields.map(({ key, name, ...restField }) => (
                      <div key={key} className="flex items-center gap-2 mb-2">
                        <Form.Item
                          {...restField}
                          name={[name]}
                          rules={[
                            { required: true, message: 'Please enter IP address' },
                            {
                              pattern: /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/,
                              message: 'Please enter a valid IP address'
                            }
                          ]}
                          className="mb-0 flex-1"
                        >
                          <Input
                            placeholder="192.168.1.1"
                            className="drawerInp py-[.65rem] bg-transparent text-[#EEEEEE] font-[300] border-[0.5px] border-[#757575] rounded-[6px] hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] text-[.75rem] shadow-none indent-[1.1rem]"
                            style={{ backgroundColor: "transparent", color: "#EEEEEE", border: "0.5px solid #757575" }}
                            size="large"
                            onChange={() => {
                              setTimeout(() => {
                                form.validateFields(['ip_addresses']);
                                handleFieldsChange();
                              }, 100);
                            }}
                          />
                        </Form.Item>
                        <MinusCircleOutlined onClick={() => {
                          remove(name);
                          setTimeout(() => handleFieldsChange(), 100);
                        }} className="text-[#B3B3B3] cursor-pointer hover:text-[#ef4444]" />
                      </div>
                    ))}
                    <Form.Item className="mb-0">
                      <Button
                        type="dashed"
                        onClick={() => {
                          add();
                          setTimeout(() => handleFieldsChange(), 100);
                        }}
                        block
                        icon={<PlusOutlined />}
                        className="border-[#757575] text-[#B3B3B3] hover:border-[#EEEEEE] hover:text-[#EEEEEE] bg-transparent"
                      >
                        Add IP Address
                      </Button>
                    </Form.Item>
                  </>
                )}
              </Form.List>
            </div>
          </Form.Item>
        );

      case RULE_TYPE_VALUES.COUNTRY_BLOCKING:
        return (
          <Form.Item
            name="countries"
            rules={[{ required: true, message: 'Please select at least one country' }]}
            className="flex items-center rounded-[6px] relative !bg-[transparent] w-[100%] mb-[0]"
            initialValue={isEditMode && editRule?.rule_config?.countries ? editRule.rule_config.countries : []}
          >
            <div className="w-full">
              <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap">
                Countries to Block
                <CustomPopover title="Select countries to block access from">
                  <Image src="/images/info.png" preview={false} alt="info" style={{ width: '.75rem', height: '.75rem' }} />
                </CustomPopover>
              </Text_12_300_EEEEEE>
            </div>
            <div className="custom-select-two w-full rounded-[6px] relative">
              <ConfigProvider theme={{ token: { colorTextPlaceholder: '#808080' } }}>
                <Select
                  mode="multiple"
                  placeholder="Select countries"
                  className="drawerInp !bg-[transparent] text-[#EEEEEE] font-[300] text-[.75rem] shadow-none w-full indent-[1.1rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE]"
                  style={{ backgroundColor: "transparent", color: "#EEEEEE", border: "0.5px solid #757575" }}
                  size="large"
                  onChange={(value) => {
                    form.setFieldValue('countries', value);
                    setTimeout(() => {
                      form.validateFields(['countries']);
                      handleFieldsChange();
                    }, 100);
                  }}
                >
                  {COUNTRY_CODES.map(country => (
                    <Option key={country.code} value={country.code}>
                      {country.name} ({country.code})
                    </Option>
                  ))}
                </Select>
              </ConfigProvider>
            </div>
          </Form.Item>
        );

      case RULE_TYPE_VALUES.USER_AGENT_BLOCKING:
        return (
          <Form.Item
            className="flex items-start rounded-[6px] relative !bg-[transparent] w-[100%] mb-[0]"
          >
            <div className="w-full">
              <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap">
                User Agent Patterns
                <CustomPopover title="Add regex patterns to match user agents">
                  <Image src="/images/info.png" preview={false} alt="info" style={{ width: '.75rem', height: '.75rem' }} />
                </CustomPopover>
              </Text_12_300_EEEEEE>
            </div>
            <div className="w-full pt-2">
              <Form.List name="patterns" initialValue={isEditMode && editRule?.rule_config?.patterns ? editRule.rule_config.patterns : []}>
                {(fields, { add, remove }) => (
                  <>
                    {fields.map(({ key, name, ...restField }) => (
                      <div key={key} className="flex items-center gap-2 mb-2">
                        <Form.Item
                          {...restField}
                          name={[name]}
                          rules={[{ required: true, message: 'Please enter pattern' }]}
                          className="mb-0 flex-1"
                        >
                          <Input
                            placeholder=".*bot.*"
                            className="drawerInp py-[.65rem] bg-transparent text-[#EEEEEE] font-[300] border-[0.5px] border-[#757575] rounded-[6px] hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] text-[.75rem] shadow-none indent-[1.1rem]"
                            style={{ backgroundColor: "transparent", color: "#EEEEEE", border: "0.5px solid #757575" }}
                            size="large"
                            onChange={() => {
                              setTimeout(() => {
                                form.validateFields(['patterns']);
                                handleFieldsChange();
                              }, 100);
                            }}
                          />
                        </Form.Item>
                        <MinusCircleOutlined onClick={() => {
                          remove(name);
                          setTimeout(() => handleFieldsChange(), 100);
                        }} className="text-[#B3B3B3] cursor-pointer hover:text-[#ef4444]" />
                      </div>
                    ))}
                    <Form.Item className="mb-0">
                      <Button
                        type="dashed"
                        onClick={() => {
                          add();
                          setTimeout(() => handleFieldsChange(), 100);
                        }}
                        block
                        icon={<PlusOutlined />}
                        className="border-[#757575] text-[#B3B3B3] hover:border-[#EEEEEE] hover:text-[#EEEEEE] bg-transparent"
                      >
                        Add Pattern
                      </Button>
                    </Form.Item>
                  </>
                )}
              </Form.List>
            </div>
          </Form.Item>
        );

      case RULE_TYPE_VALUES.RATE_BASED_BLOCKING:
        return (
          <>
            <div className="relative">
              <div className="w-full">
                <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap">
                  Request Threshold
                  <CustomPopover title="Maximum number of requests allowed within the time window">
                    <Image src="/images/info.png" preview={false} alt="info" style={{ width: '.75rem', height: '.75rem' }} />
                  </CustomPopover>
                </Text_12_300_EEEEEE>
              </div>
              <Form.Item
                hasFeedback
                name="threshold"
                rules={[
                  { required: true, message: 'Please enter threshold' },
                  { type: 'number', min: 1, max: 10000, message: 'Threshold must be between 1 and 10000', transform: value => parseInt(value) }
                ]}
                className="flex items-center rounded-[6px] relative !bg-[transparent] w-[100%] mb-[0]"
                initialValue={isEditMode && editRule?.rule_config?.threshold ? editRule.rule_config.threshold.toString() : ''}
              >
                <Input
                  type="number"
                  min={1}
                  max={10000}
                  placeholder="100"
                  className="drawerInp py-[.65rem] pt-[.8rem] pb-[.45rem] bg-transparent text-[#EEEEEE] font-[300] border-[0.5px] border-[#757575] rounded-[6px] hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] text-[.75rem] shadow-none w-full px-[1.1rem]"
                  style={{ backgroundColor: "transparent", color: "#EEEEEE", border: "0.5px solid #757575" }}
                  size="large"
                  onChange={() => {
                    handleFieldsChange();
                  }}
                />
              </Form.Item>
            </div>
            <div className="relative">
              <div className="w-full">
                <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap">
                  Time Window (seconds)
                  <CustomPopover title="Time period in which to count requests">
                    <Image src="/images/info.png" preview={false} alt="info" style={{ width: '.75rem', height: '.75rem' }} />
                  </CustomPopover>
                </Text_12_300_EEEEEE>
              </div>
              <Form.Item
                hasFeedback
                name="window_seconds"
                rules={[
                  { required: true, message: 'Please enter time window' },
                  { type: 'number', min: 1, max: 3600, message: 'Time window must be between 1 and 3600 seconds', transform: value => parseInt(value) }
                ]}
                className="flex items-center rounded-[6px] relative !bg-[transparent] w-[100%] mb-[0]"
                initialValue={isEditMode && editRule?.rule_config?.window_seconds ? editRule.rule_config.window_seconds.toString() : ''}
              >
                <Input
                  type="number"
                  min={1}
                  max={3600}
                  placeholder="60"
                  className="drawerInp py-[.65rem] pt-[.8rem] pb-[.45rem] bg-transparent text-[#EEEEEE] font-[300] border-[0.5px] border-[#757575] rounded-[6px] hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] text-[.75rem] shadow-none w-full px-[1.1rem]"
                  style={{ backgroundColor: "transparent", color: "#EEEEEE", border: "0.5px solid #757575" }}
                  size="large"
                  onChange={() => {
                    handleFieldsChange();
                  }}
                />
              </Form.Item>
            </div>
          </>
        );

      default:
        return null;
    }
  };

  // Force re-render when switching between create and edit mode
  const formKey = `${isEditMode ? 'edit' : 'create'}-${editRule?.id || 'new'}`;

  return (
    <div key={formKey} className="px-[1.4rem] py-[2.1rem] flex flex-col gap-[1.6rem]">
      {/* Rule Name */}
      <div className="relative">
        <div className="w-full">
          <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap">
            Rule Name
            <CustomPopover title="Enter a descriptive name for this blocking rule">
              <Image src="/images/info.png" preview={false} alt="info" style={{ width: '.75rem', height: '.75rem' }} />
            </CustomPopover>
          </Text_12_300_EEEEEE>
        </div>
        <Form.Item
          hasFeedback
          name="name"
          rules={[{ required: true, message: 'Please enter rule name' }]}
          className="flex items-center rounded-[6px] relative !bg-[transparent] w-[100%] mb-[0]"
          initialValue={isEditMode ? editRule?.name : undefined}
        >
          <Input
            placeholder="e.g., Block suspicious IPs"
            className="drawerInp py-[.65rem] pt-[.8rem] pb-[.45rem] bg-transparent text-[#EEEEEE] font-[300] border-[0.5px] border-[#757575] rounded-[6px] hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] text-[.75rem] shadow-none w-full px-[1.1rem]"
            style={{ backgroundColor: "transparent", color: "#EEEEEE", border: "0.5px solid #757575" }}
            size="large"
            onChange={() => {
              handleFieldsChange();
            }}
          />
        </Form.Item>
      </div>


      {/* Rule Type */}
      <Form.Item
        hasFeedback
        name="rule_type"
        rules={[{ required: true, message: 'Please select rule type' }]}
        className="flex items-center rounded-[6px] relative !bg-[transparent] w-[100%] mb-[0]"
      >
        <div className="w-full">
          <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap">
            Rule Type
            <CustomPopover title="Select the type of blocking rule">
              <Image src="/images/info.png" preview={false} alt="info" style={{ width: '.75rem', height: '.75rem' }} />
            </CustomPopover>
          </Text_12_300_EEEEEE>
        </div>
        <div className="custom-select-two w-full rounded-[6px] relative">
          <ConfigProvider theme={{ token: { colorTextPlaceholder: '#808080' } }}>
            <Select
              value={ruleType}
              onChange={(value) => {
                setRuleType(value);
                form.setFieldValue('rule_type', value);
                // Reset rule-specific fields when type changes
                if (value === RULE_TYPE_VALUES.IP_BLOCKING) {
                  form.setFieldValue('ip_addresses', []);
                } else if (value === RULE_TYPE_VALUES.COUNTRY_BLOCKING) {
                  form.setFieldValue('countries', []);
                } else if (value === RULE_TYPE_VALUES.USER_AGENT_BLOCKING) {
                  form.setFieldValue('patterns', []);
                } else if (value === RULE_TYPE_VALUES.RATE_BASED_BLOCKING) {
                  form.setFieldValue('threshold', '');
                  form.setFieldValue('window_seconds', '');
                }
                form.validateFields(['rule_type']);
                setTimeout(() => handleFieldsChange(), 100);
              }}
              className="drawerInp !bg-[transparent] text-[#EEEEEE] font-[300] text-[.75rem] shadow-none w-full border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] py-[1rem] px-[0.3rem]"
              style={{ backgroundColor: "transparent", color: "#EEEEEE", border: "0.5px solid #757575" }}
              size="large"
            >
              {Object.entries(RULE_TYPE_VALUES).map(([key, value]) => (
                <Option key={value} value={value}>
                  {RULE_TYPE_LABELS[value]}
                </Option>
              ))}
            </Select>
          </ConfigProvider>
        </div>
      </Form.Item>

      {/* Rule Configuration Fields */}
      {getRuleConfigFields()}

      {/* Reason */}
      <div className="relative">
        <div className="w-full">
          <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap">
            Reason for Blocking
            <CustomPopover title="Explain why this rule is being created">
              <Image src="/images/info.png" preview={false} alt="info" style={{ width: '.75rem', height: '.75rem' }} />
            </CustomPopover>
          </Text_12_300_EEEEEE>
        </div>
        <Form.Item
          name="reason"
          rules={[{ required: true, message: 'Please enter reason' }]}
          className="flex items-start rounded-[6px] relative !bg-[transparent] w-[100%] mb-[0]"
          initialValue={isEditMode ? editRule?.reason : undefined}
        >
          <TextArea
            rows={2}
            placeholder="e.g., Security threat, Abuse prevention"
            className="drawerInp py-[.65rem] pt-[.8rem] pb-[.45rem] bg-transparent text-[#EEEEEE] font-[300] rounded-[6px] hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] text-[.75rem] shadow-none w-full px-[1.1rem]"
            style={{ backgroundColor: "transparent", color: "#EEEEEE", border: "0.5px solid #757575", resize: 'none' }}
            onChange={() => {
              handleFieldsChange();
            }}
          />
        </Form.Item>
      </div>

      {/* Priority */}
      <div className="relative">
        <div className="w-full">
          <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap">
            Priority
            <CustomPopover title="Lower numbers have higher priority">
              <Image src="/images/info.png" preview={false} alt="info" style={{ width: '.75rem', height: '.75rem' }} />
            </CustomPopover>
          </Text_12_300_EEEEEE>
        </div>
        <Form.Item
          name="priority"
          className="flex items-center rounded-[6px] relative !bg-[transparent] w-[100%] mb-[0]"
          initialValue={isEditMode ? (editRule?.priority || 100) : 100}
        >
          <Input
            type="number"
            min={0}
            max={1000}
            placeholder="100"
            className="drawerInp py-[.65rem] pt-[.8rem] pb-[.45rem] bg-transparent text-[#EEEEEE] font-[300] border-[0.5px] border-[#757575] rounded-[6px] hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] text-[.75rem] shadow-none w-full px-[1.1rem]"
            style={{ backgroundColor: "transparent", color: "#EEEEEE", border: "0.5px solid #757575" }}
            size="large"
            onChange={() => {
              handleFieldsChange();
            }}
          />
        </Form.Item>
      </div>
    </div>
  );
}

const CreateBlockingRuleStep: React.FC<CreateBlockingRuleStepProps> = () => {
  const { createRule, updateRule } = useBlockingRules();
  const { openDrawerWithStep, closeDrawer, drawerProps } = useDrawer();
  const { showLoader, hideLoader } = useLoader();
  const [disableNext, setDisableNext] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Check if we're in edit mode
  const isEditMode = drawerProps?.editMode;
  const editRule = drawerProps?.rule;
  const editRuleId = drawerProps?.ruleId;

  // Transform edit rule data to form format or provide defaults for create mode
  const formData = useMemo(() => {
    if (!isEditMode || !editRule) {
      // Default values for create mode
      return {
        priority: 100,
        rule_type: RULE_TYPE_VALUES.IP_BLOCKING,
        ip_addresses: []
      };
    }

    const data: any = {
      name: editRule.name,
      rule_type: editRule.rule_type,
      reason: editRule.reason,
      priority: editRule.priority || 100,
    };

    // Add rule-specific configuration
    if (editRule.rule_config) {
      switch (editRule.rule_type) {
        case RULE_TYPE_VALUES.IP_BLOCKING:
          data.ip_addresses = editRule.rule_config.ip_addresses || [];
          break;
        case RULE_TYPE_VALUES.COUNTRY_BLOCKING:
          data.countries = editRule.rule_config.countries || [];
          break;
        case RULE_TYPE_VALUES.USER_AGENT_BLOCKING:
          data.patterns = editRule.rule_config.patterns || [];
          break;
        case RULE_TYPE_VALUES.RATE_BASED_BLOCKING:
          data.threshold = editRule.rule_config.threshold?.toString() || '';
          data.window_seconds = editRule.rule_config.window_seconds?.toString() || '';
          break;
      }
    }

    return data;
  }, [isEditMode, editRule, drawerProps]);

  const transformFormToConfig = (type: BlockingRuleType, values: any) => {
    switch (type) {
      case RULE_TYPE_VALUES.IP_BLOCKING:
        return { ip_addresses: values.ip_addresses || [] };
      case RULE_TYPE_VALUES.COUNTRY_BLOCKING:
        return { countries: values.countries || [] };
      case RULE_TYPE_VALUES.USER_AGENT_BLOCKING:
        return { patterns: values.patterns || [] };
      case RULE_TYPE_VALUES.RATE_BASED_BLOCKING:
        return {
          threshold: parseInt(values.threshold) || 100,
          window_seconds: parseInt(values.window_seconds) || 60,
        };
      default:
        return {};
    }
  };

  const handleSubmit = async (values: any) => {
    try {
      setIsSubmitting(true);
      showLoader();

      const rule_config = transformFormToConfig(values.rule_type, values);

      const ruleData = {
        name: values.name,
        rule_type: values.rule_type,
        rule_config,
        reason: values.reason,
        priority: values.priority || 100,
      };

      // Create or update rule
      const success = isEditMode
        ? await updateRule(editRuleId, ruleData)
        : await createRule(ruleData);

      if (success) {
        if (isEditMode) {
          // For edit mode, just close the drawer (toast is shown by updateRule)
          closeDrawer();
        } else {
          // For create mode, move to success step
          openDrawerWithStep('blocking-rule-success', {
            ruleName: values.name,
            ruleType: values.rule_type,
            isEdit: false,
          });
        }
      }
    } catch (error) {
      console.error('Failed to create rule:', error);
      message.error('Failed to create blocking rule');
    } finally {
      setIsSubmitting(false);
      hideLoader();
    }
  };

  const handleCancel = () => {
    closeDrawer();
  };

  return (
    <BudForm
      data={formData}
      disableNext={disableNext}
      onNext={handleSubmit}
      onBack={handleCancel}
      nextText={isEditMode ? "Update Rule" : "Create Rule"}
      backText="Cancel"
      drawerLoading={isSubmitting}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title={isEditMode ? "Edit Blocking Rule" : "Create Blocking Rule"}
            description={isEditMode ? "Modify the rule to control access to your gateway" : "Set up a new rule to control access to your gateway"}
          />
          <RuleForm setDisableNext={setDisableNext} />
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
};

export default CreateBlockingRuleStep;

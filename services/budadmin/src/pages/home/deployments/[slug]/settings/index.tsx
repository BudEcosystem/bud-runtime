import React, { useState, useEffect } from "react";
import { Form, Button, Row, Col, Spin, Switch } from "antd";
import {
  Text_20_400_EEEEEE,
  Text_12_400_757575,
  Text_12_300_EEEEEE,
  Text_14_400_EEEEEE,
} from "@/components/ui/text";
import { useEndPoints } from "src/hooks/useEndPoint";
import { useRouter } from "next/router";
import { successToast, errorToast } from "@/components/toast";
import CustomPopover from "src/flows/components/customPopover";
import { Image } from "antd";
import { useDrawer } from "src/hooks/useDrawer";
import { IconOnlyRender } from "src/flows/components/BudIconRender";
import ProjectTags from "src/flows/components/ProjectTags";
import Tags from "src/flows/components/DrawerTags";
import { endpointStatusMapping } from "@/lib/colorMapping";
import TextInput from "src/flows/components/TextInput";
import { BudDropdownMenu } from "@/components/ui/dropDown";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { useConfirmAction } from "src/hooks/useConfirmAction";

const capitalize = (str: string) =>
  str?.charAt(0).toUpperCase() + str?.slice(1).toLowerCase();

interface DeploymentSettings {
  rate_limits?: {
    enabled?: boolean;
    algorithm?: "fixed_window" | "sliding_window" | "token_bucket";
    requests_per_minute?: number | null;
    requests_per_second?: number | null;
    requests_per_hour?: number | null;
    burst_size?: number | null;
  };
  retry_config?: {
    num_retries?: number;
    max_delay_s?: number;
  } | null;
  fallback_config?: {
    fallback_models?: string[];
  };
}

const DeploymentSettings: React.FC = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [saveLoading, setSaveLoading] = useState(false);
  const [selectedDeployment, setSelectedDeployment] = useState<any>(null);
  const [isRateLimitEnabled, setIsRateLimitEnabled] = useState(false);
  const {
    getEndpointSettings,
    updateEndpointSettings,
    endPoints,
    getEndPoints,
  } = useEndPoints();
  const { openDrawerWithStep } = useDrawer();
  const { contextHolder, openConfirm } = useConfirmAction();
  const router = useRouter();
  const { deploymentId } = router.query;

  // Extract project ID from the route
  const projectId =
    router.query.projectId ||
    (router.asPath.includes("/projects/")
      ? router.asPath.split("/projects/")[1]?.split("/")[0]
      : null);

  const [settings, setSettings] = useState<DeploymentSettings>({
    rate_limits: {
      enabled: false,
      algorithm: "token_bucket",
      requests_per_minute: null,
      requests_per_second: null,
      requests_per_hour: null,
      burst_size: null,
    },
    retry_config: null,
    fallback_config: {
      fallback_models: [],
    },
  });

  useEffect(() => {
    // Fetch fallback deployment details when settings are loaded
    const fetchFallbackDeploymentDetails = async () => {
      const fallbackId = settings.fallback_config?.fallback_models?.[0];
      if (
        fallbackId &&
        projectId &&
        (!selectedDeployment || selectedDeployment.id !== fallbackId)
      ) {
        // Fetch all deployments to find the fallback one
        await getEndPoints({
          id: projectId as string,
          page: 1,
          limit: 100,
          name: "",
          order_by: "-created_at",
        });
      }
    };

    fetchFallbackDeploymentDetails();
  }, [settings.fallback_config?.fallback_models, projectId]);

  useEffect(() => {
    // Find and set the fallback deployment from the endpoints list
    const fallbackId = settings.fallback_config?.fallback_models?.[0];
    if (fallbackId && endPoints && endPoints.length > 0) {
      const fallbackDeployment = endPoints.find((ep) => ep.id === fallbackId);
      if (
        fallbackDeployment &&
        (!selectedDeployment || selectedDeployment.id !== fallbackId)
      ) {
        setSelectedDeployment(fallbackDeployment);
      }
    }
  }, [endPoints, settings.fallback_config?.fallback_models]);

  useEffect(() => {
    // Load existing settings when component mounts
    const loadSettings = async () => {
      if (!deploymentId) return;

      setLoading(true);
      try {
        const response = await getEndpointSettings(deploymentId as string);
        if (response?.deployment_settings) {
          const deploymentSettings = response.deployment_settings;
          // Map the API response to our state structure, handling null values
          setSettings({
            rate_limits: deploymentSettings.rate_limits || {
              enabled: false,
              algorithm: "token_bucket",
              requests_per_minute: null,
              requests_per_second: null,
              requests_per_hour: null,
              burst_size: null,
            },
            retry_config: deploymentSettings.retry_config || null,
            fallback_config: deploymentSettings.fallback_config || {
              fallback_models: [],
            },
          });
        }
      } catch (error) {
        // Settings might not exist yet - that's ok, use defaults
        console.log("No existing settings found, using defaults");
        errorToast("Failed to load settings. Using default values.");
      } finally {
        setLoading(false);
      }
    };

    loadSettings();
  }, [deploymentId, getEndpointSettings]);

  // Update rate limit enabled state when settings change
  useEffect(() => {
    setIsRateLimitEnabled(settings.rate_limits?.enabled ?? false);
  }, [settings]);

  useEffect(() => {
    // Initialize form values
    const formValues = {
      rate_limit_enabled: settings.rate_limits?.enabled ?? false,
      algorithm: settings.rate_limits?.algorithm || "token_bucket",
      requests_per_minute:
        settings.rate_limits?.requests_per_minute !== null &&
        settings.rate_limits?.requests_per_minute !== undefined
          ? String(settings.rate_limits.requests_per_minute)
          : "",
      requests_per_second:
        settings.rate_limits?.requests_per_second !== null &&
        settings.rate_limits?.requests_per_second !== undefined
          ? String(settings.rate_limits.requests_per_second)
          : "",
      requests_per_hour:
        settings.rate_limits?.requests_per_hour !== null &&
        settings.rate_limits?.requests_per_hour !== undefined
          ? String(settings.rate_limits.requests_per_hour)
          : "",
      burst_size:
        settings.rate_limits?.burst_size !== null &&
        settings.rate_limits?.burst_size !== undefined
          ? String(settings.rate_limits.burst_size)
          : "",
      fallback_deployment_id:
        settings.fallback_config?.fallback_models?.[0] || "",
      num_retries:
        settings.retry_config?.num_retries !== null &&
        settings.retry_config?.num_retries !== undefined
          ? String(settings.retry_config.num_retries)
          : "",
      max_delay_s:
        settings.retry_config?.max_delay_s !== null &&
        settings.retry_config?.max_delay_s !== undefined
          ? String(settings.retry_config.max_delay_s)
          : "",
    };
    form.setFieldsValue(formValues);
  }, [settings, form]);

  const handleFormSubmit = () => {
    form
      .validateFields()
      .then((values) => {
        // Additional validation for rate limiting
        if (isRateLimitEnabled) {
          const hasAnyRateLimit =
            values.requests_per_second ||
            values.requests_per_minute ||
            values.requests_per_hour;
          if (!hasAnyRateLimit) {
            form.setFields([
              {
                name: "requests_per_second",
                errors: [
                  "At least one rate limit value is required when rate limiting is enabled",
                ],
              },
              {
                name: "requests_per_minute",
                errors: [
                  "At least one rate limit value is required when rate limiting is enabled",
                ],
              },
              {
                name: "requests_per_hour",
                errors: [
                  "At least one rate limit value is required when rate limiting is enabled",
                ],
              },
            ]);
            return;
          }
        }

        openConfirm({
          message: "Save Deployment Settings",
          description:
            "Are you sure you want to save these deployment settings? This will affect how your deployment handles requests.",
          okText: "Yes, Save Settings",
          cancelText: "Cancel",
          loading: saveLoading,
          type: "warning",
          key: "save-deployment-settings",
          okAction: async () => {
            const success = await handleSave(values);
            if (success) {
              successToast("Settings updated successfully");
            }
            // Error handling is already done in handleSave if it fails
          },
          cancelAction: () => {
            // No action needed for cancel
          },
        });
      })
      .catch(() => {
        // Form validation failed, don't proceed
      });
  };

  const handleSave = async (values: any) => {
    if (!deploymentId) return false;

    setSaveLoading(true);
    try {
      const updatedSettings = {
        rate_limits: {
          enabled: isRateLimitEnabled,
          algorithm: values.algorithm,
          requests_per_minute: values.requests_per_minute
            ? parseInt(values.requests_per_minute)
            : null,
          requests_per_second: values.requests_per_second
            ? parseInt(values.requests_per_second)
            : null,
          requests_per_hour: values.requests_per_hour
            ? parseInt(values.requests_per_hour)
            : null,
          burst_size: values.burst_size ? parseInt(values.burst_size) : null,
        },
        retry_config:
          values.num_retries || values.max_delay_s
            ? {
                num_retries: values.num_retries
                  ? parseInt(values.num_retries)
                  : undefined,
                max_delay_s: values.max_delay_s
                  ? parseFloat(values.max_delay_s)
                  : undefined,
              }
            : undefined,
        fallback_config: {
          fallback_models: selectedDeployment?.id
            ? [selectedDeployment.id]
            : [],
        },
      };

      await updateEndpointSettings(deploymentId as string, updatedSettings);
      // Update settings but preserve the selectedDeployment details
      setSettings(updatedSettings);
      // Don't clear selectedDeployment after save
      return true; // Success
    } catch (error: any) {
      console.error("Error updating settings:", error);
      const errorMessage =
        error?.response?.data?.message ||
        error?.message ||
        "Failed to update settings";
      errorToast(errorMessage);
      return false; // Failure
    } finally {
      setSaveLoading(false);
    }
  };

  const handleReset = () => {
    // Reset to current settings values
    const formValues = {
      rate_limit_enabled: settings.rate_limits?.enabled ?? false,
      algorithm: settings.rate_limits?.algorithm || "token_bucket",
      requests_per_minute:
        settings.rate_limits?.requests_per_minute !== null &&
        settings.rate_limits?.requests_per_minute !== undefined
          ? String(settings.rate_limits.requests_per_minute)
          : "",
      requests_per_second:
        settings.rate_limits?.requests_per_second !== null &&
        settings.rate_limits?.requests_per_second !== undefined
          ? String(settings.rate_limits.requests_per_second)
          : "",
      requests_per_hour:
        settings.rate_limits?.requests_per_hour !== null &&
        settings.rate_limits?.requests_per_hour !== undefined
          ? String(settings.rate_limits.requests_per_hour)
          : "",
      burst_size:
        settings.rate_limits?.burst_size !== null &&
        settings.rate_limits?.burst_size !== undefined
          ? String(settings.rate_limits.burst_size)
          : "",
      fallback_deployment_id:
        settings.fallback_config?.fallback_models?.[0] || "",
      num_retries:
        settings.retry_config?.num_retries !== null &&
        settings.retry_config?.num_retries !== undefined
          ? String(settings.retry_config.num_retries)
          : "",
      max_delay_s:
        settings.retry_config?.max_delay_s !== null &&
        settings.retry_config?.max_delay_s !== undefined
          ? String(settings.retry_config.max_delay_s)
          : "",
    };
    form.setFieldsValue(formValues);
  };

  const handleDeploymentSelect = (deployment: any) => {
    setSelectedDeployment(deployment);
    form.setFieldValue("fallback_deployment_id", deployment.id);
  };

  const clearDeploymentSelection = () => {
    setSelectedDeployment(null);
    form.setFieldValue("fallback_deployment_id", "");
  };

  const openDeploymentDrawer = () => {
    // Update router query to include projectId if it's not there
    if (projectId && !router.query.projectId) {
      router.replace(
        {
          pathname: router.pathname,
          query: { ...router.query, projectId },
        },
        undefined,
        { shallow: true },
      );
    }

    openDrawerWithStep("select-fallback-deployment", {
      onSelect: handleDeploymentSelect,
      currentDeploymentId: deploymentId,
    });
  };

  if (loading) {
    return (
      <div className="p-6 flex justify-center items-center min-h-[400px]">
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div className="py-6">
      <div className="mb-6 flex justify-between items-start">
        <div>
          <Text_20_400_EEEEEE className="w-full mb-[.1rem] tracking-[.025rem]">
            Deployment Settings
          </Text_20_400_EEEEEE>
          <Text_12_400_757575>
            Configure rate limiting, fallback options, and retry behavior for
            this deployment.
          </Text_12_400_757575>
        </div>
        <div className="flex gap-3">
          <Button
            onClick={handleReset}
            className="bg-transparent border-[#757575] text-[#EEEEEE] hover:border-[#EEEEEE] hover:text-[#FFFFFF]"
          >
            Reset
          </Button>
          <Button
            type="primary"
            onClick={handleFormSubmit}
            loading={saveLoading}
            className="bg-[#965CDE] border-[#965CDE] hover:bg-[#7A4BC7] hover:border-[#7A4BC7]"
          >
            Save Settings
          </Button>
        </div>
      </div>

      <BudFormContext.Provider
        value={{
          form: form,
          submittable: true,
          loading: false,
          setLoading: () => {},
          values: form.getFieldsValue(),
          isExpandedView: false,
          isExpandedViewOpen: false,
        }}
      >
        {contextHolder}
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSave}
          className="deployment-settings-form"
          initialValues={{
            rate_limit_enabled: false,
            algorithm: "token_bucket",
            requests_per_minute: "",
            requests_per_second: "",
            requests_per_hour: "",
            burst_size: "",
            fallback_deployment_id: "",
            num_retries: "",
            max_delay_s: "",
          }}
        >
          {/* Rate Limiting Section */}
          <div className="mb-8 px-[1.4rem] py-[1.3rem] border border-[#1F1F1F] rounded-[.4rem] bg-[#101010]">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2 flex-nowrap">
                <Text_12_300_EEEEEE className="whitespace-nowrap">
                  Rate Limiting
                </Text_12_300_EEEEEE>
                <CustomPopover title="Controls how many requests can be processed within a time window. When enabled, provide at least one rate limit value.">
                  <Image
                    preview={false}
                    src="/images/info.png"
                    alt="info"
                    style={{ width: ".75rem", height: ".75rem" }}
                  />
                </CustomPopover>
              </div>

              <Switch
                size="small"
                className="[&_.ant-switch-checked]:bg-[#965CDE]"
                checked={isRateLimitEnabled}
                onChange={setIsRateLimitEnabled}
              />
            </div>

            {!isRateLimitEnabled ? (
              <div className="text-center py-4">
                <Text_12_300_EEEEEE className="text-[#757575]">
                  Rate limiting is disabled. Enable it to configure limits.
                </Text_12_300_EEEEEE>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Algorithm Selection */}
                <BudDropdownMenu
                  name="algorithm"
                  label="Algorithm"
                  placeholder="Select algorithm"
                  infoText="Rate limiting algorithm type"
                  rules={[
                    { required: true, message: "Please select an algorithm" },
                  ]}
                  items={[
                    { label: "Fixed Window", value: "fixed_window" },
                    { label: "Sliding Window", value: "sliding_window" },
                    { label: "Token Bucket", value: "token_bucket" },
                  ]}
                  formItemClassnames="[&_.ant-form-item-feedback-icon]:hidden"
                />

                {/* Requests Configuration */}
                <Row gutter={16}>
                  <Col span={8}>
                    <TextInput
                      name="requests_per_second"
                      label="Requests per Second"
                      placeholder="e.g., 100"
                      allowOnlyNumbers={true}
                      rules={[
                        {
                          pattern: /^[1-9]\d*$/,
                          message: "Must be a positive integer",
                        },
                      ]}
                      formItemClassnames="[&_.ant-form-item-feedback-icon]:hidden"
                    />
                  </Col>
                  <Col span={8}>
                    <TextInput
                      name="requests_per_minute"
                      label="Requests per Minute"
                      placeholder="e.g., 1000"
                      allowOnlyNumbers={true}
                      rules={[
                        {
                          pattern: /^[1-9]\d*$/,
                          message: "Must be a positive integer",
                        },
                      ]}
                      formItemClassnames="[&_.ant-form-item-feedback-icon]:hidden"
                    />
                  </Col>
                  <Col span={8}>
                    <TextInput
                      name="requests_per_hour"
                      label="Requests per Hour"
                      placeholder="e.g., 10000"
                      allowOnlyNumbers={true}
                      rules={[
                        {
                          pattern: /^[1-9]\d*$/,
                          message: "Must be a positive integer",
                        },
                      ]}
                      formItemClassnames="[&_.ant-form-item-feedback-icon]:hidden"
                    />
                  </Col>
                </Row>

                {/* Burst Size - Only show for token bucket algorithm */}
                <Form.Item
                  shouldUpdate={(prevValues, currentValues) =>
                    prevValues.algorithm !== currentValues.algorithm
                  }
                >
                  {({ getFieldValue }) => {
                    const algorithm = getFieldValue("algorithm");
                    if (algorithm !== "token_bucket") return null;

                    return (
                      <TextInput
                        name="burst_size"
                        label="Burst Size"
                        placeholder="e.g., 50"
                        infoText="Maximum burst capacity for token bucket algorithm"
                        allowOnlyNumbers={true}
                        rules={[
                          {
                            pattern: /^[1-9]\d*$/,
                            message: "Must be a positive integer",
                          },
                        ]}
                        formItemClassnames="[&_.ant-form-item-feedback-icon]:hidden"
                      />
                    );
                  }}
                </Form.Item>
              </div>
            )}
          </div>

          {/* Fallback Deployment Section */}
          <div className="mb-8 px-[1.4rem] py-[1.3rem] border border-[#1F1F1F] rounded-[.4rem] bg-[#101010]">
            <div className="mb-4 flex items-center gap-2 flex-nowrap">
              <Text_12_300_EEEEEE className="whitespace-nowrap">
                Fallback Deployment
              </Text_12_300_EEEEEE>
              <CustomPopover title="Alternative deployment to use when the primary deployment is unavailable or overloaded">
                <Image
                  preview={false}
                  src="/images/info.png"
                  alt="info"
                  style={{ width: ".75rem", height: ".75rem" }}
                />
              </CustomPopover>
            </div>

            <Form.Item name="fallback_deployment_id">
              <div className="space-y-3">
                {selectedDeployment ? (
                  <div className="py-[.85rem] px-[1.4rem] border border-[#1F1F1F] bg-[#101010] rounded-[.4rem] flex-row flex items-start">
                    <div className="mr-[1rem] flex flex-col justify-center">
                      <div className="bg-[#1F1F1F] w-[2.6875rem] h-[2.6875rem] rounded-[.52rem] flex justify-center items-center grow-0 shrink-0">
                        <IconOnlyRender
                          icon={selectedDeployment.model?.icon}
                          model={selectedDeployment.model}
                          type={selectedDeployment.model?.provider_type}
                          imageSize={27}
                        />
                      </div>
                    </div>

                    <div className="flex-auto">
                      <div className="flex items-center justify-between max-w-[100%]">
                        <div className="flex justify-start items-center gap-[.6rem] pb-[0.625rem]">
                          <Text_14_400_EEEEEE className="leading-[100%]">
                            {selectedDeployment.name || "Selected Deployment"}
                          </Text_14_400_EEEEEE>
                          {selectedDeployment.status && (
                            <ProjectTags
                              name={capitalize(selectedDeployment.status)}
                              color={
                                endpointStatusMapping[
                                  capitalize(selectedDeployment.status)
                                ]
                              }
                              textClass="text-[.625rem]"
                            />
                          )}
                          <div className="flex justify-start items-center gap-[.5rem]">
                            {selectedDeployment.cluster?.name && (
                              <Tags
                                name={selectedDeployment.cluster.name}
                                color="#D1B854"
                                classNames="py-[.32rem]"
                                textClass="leading-[100%] text-[.625rem] font-[400]"
                              />
                            )}
                          </div>
                        </div>
                        <Button
                          type="text"
                          size="small"
                          onClick={clearDeploymentSelection}
                          className="text-[#757575] hover:text-[#EEEEEE] p-1"
                        >
                          <svg
                            width="12"
                            height="12"
                            viewBox="0 0 12 12"
                            fill="currentColor"
                          >
                            <path
                              d="M9 3L3 9M3 3l6 6"
                              stroke="currentColor"
                              strokeWidth="1.5"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                            />
                          </svg>
                        </Button>
                      </div>
                      <Text_12_300_EEEEEE className="overflow-hidden truncate max-w-[95%]">
                        {selectedDeployment.model?.name ||
                          "No model information"}
                      </Text_12_300_EEEEEE>
                    </div>
                  </div>
                ) : (
                  <Button
                    type="dashed"
                    onClick={openDeploymentDrawer}
                    className="w-full h-12 border-[#757575] text-[#EEEEEE] hover:border-[#EEEEEE] hover:text-[#FFFFFF] bg-transparent"
                  >
                    Select Deployment
                  </Button>
                )}

                {selectedDeployment && (
                  <Button
                    type="text"
                    size="small"
                    onClick={openDeploymentDrawer}
                    className="text-[#965CDE] hover:text-[#7A4BC7]"
                  >
                    Change Selection
                  </Button>
                )}
              </div>
            </Form.Item>
          </div>

          {/* Retry Configuration Section */}
          <div className="mb-8 px-[1.4rem] py-[1.3rem] border border-[#1F1F1F] rounded-[.4rem] bg-[#101010]">
            <div className="mb-4 flex items-center gap-2 flex-nowrap">
              <Text_12_300_EEEEEE className="whitespace-nowrap">
                Retry Configuration (Optional)
              </Text_12_300_EEEEEE>
              <CustomPopover title="Number of times to retry failed requests and maximum delay between retries. Leave empty to disable retries.">
                <Image
                  preview={false}
                  src="/images/info.png"
                  alt="info"
                  style={{ width: ".75rem", height: ".75rem" }}
                />
              </CustomPopover>
            </div>

            <Row gutter={16}>
              <Col span={12}>
                <TextInput
                  name="num_retries"
                  label="Max Retry Attempts"
                  placeholder="Leave empty to disable retries"
                  allowOnlyNumbers={true}
                  rules={[
                    {
                      pattern: /^([0-9]|10)$/,
                      message: "Must be between 0 and 10 retries",
                    },
                  ]}
                  formItemClassnames="[&_.ant-form-item-feedback-icon]:hidden"
                />
              </Col>
              <Col span={12}>
                <TextInput
                  name="max_delay_s"
                  label="Max Delay (seconds)"
                  placeholder="Optional (0.1-60 seconds)"
                  rules={[
                    {
                      validator: (_, value) => {
                        if (!value) return Promise.resolve(); // Allow empty values
                        const num = parseFloat(value);
                        if (isNaN(num) || num < 0.1 || num > 60) {
                          return Promise.reject(
                            "Must be between 0.1 and 60 seconds",
                          );
                        }
                        return Promise.resolve();
                      },
                    },
                  ]}
                  formItemClassnames="[&_.ant-form-item-feedback-icon]:hidden"
                />
              </Col>
            </Row>
          </div>
        </Form>
      </BudFormContext.Provider>
    </div>
  );
};

export default DeploymentSettings;

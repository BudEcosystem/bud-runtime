"use client";
import React, { useState } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import {
  Flex,
  Select,
  DatePicker,
  Card,
  Progress,
  Button,
  Modal,
  Input,
  Switch,
  Table,
} from "antd";
import { Typography } from "antd";

const { Text, Title } = Typography;
import { Icon } from "@iconify/react/dist/iconify.js";
import styles from "./usage.module.scss";
import dayjs from "dayjs";

const { RangePicker } = DatePicker;

interface UsageData {
  date: string;
  tokens: number;
  cost: number;
  requests: number;
  model: string;
  endpoint: string;
}

interface BillingAlert {
  id: string;
  type: "cost" | "usage" | "requests";
  threshold: number;
  isActive: boolean;
  lastTriggered?: string;
}

export default function UsagePage() {
  const [timeRange, setTimeRange] = useState("7d");
  const [selectedModel, setSelectedModel] = useState("all");
  const [showAlertModal, setShowAlertModal] = useState(false);
  const [alertType, setAlertType] = useState<"cost" | "usage" | "requests">(
    "cost",
  );
  const [alertThreshold, setAlertThreshold] = useState(100);

  // Mock billing plan data
  const billingPlan = {
    name: "Pro Plan",
    cost: "$49/month",
    quotaLimit: 1000000, // tokens
    quotaUsed: 750000,
    requestsLimit: 10000,
    requestsUsed: 7500,
    billingCycle: "Monthly",
    nextBilling: "2024-02-15",
  };

  // Mock usage data
  const usageData: UsageData[] = [
    {
      date: "2024-01-20",
      tokens: 15420,
      cost: 12.5,
      requests: 150,
      model: "gpt-4",
      endpoint: "/v1/chat/completions",
    },
    {
      date: "2024-01-19",
      tokens: 12800,
      cost: 10.2,
      requests: 120,
      model: "claude-3-opus",
      endpoint: "/v1/chat/completions",
    },
    {
      date: "2024-01-18",
      tokens: 9200,
      cost: 7.8,
      requests: 95,
      model: "gpt-3.5-turbo",
      endpoint: "/v1/chat/completions",
    },
    {
      date: "2024-01-17",
      tokens: 18500,
      cost: 15.4,
      requests: 180,
      model: "gpt-4",
      endpoint: "/v1/chat/completions",
    },
    {
      date: "2024-01-16",
      tokens: 11300,
      cost: 9.1,
      requests: 110,
      model: "claude-3-sonnet",
      endpoint: "/v1/chat/completions",
    },
  ];

  // Mock alerts
  const [alerts, setAlerts] = useState<BillingAlert[]>([
    { id: "1", type: "cost", threshold: 100, isActive: true },
    { id: "2", type: "usage", threshold: 800000, isActive: true },
    { id: "3", type: "requests", threshold: 8000, isActive: false },
  ]);

  const totalCost = usageData.reduce((acc, item) => acc + item.cost, 0);
  const totalTokens = usageData.reduce((acc, item) => acc + item.tokens, 0);
  const totalRequests = usageData.reduce((acc, item) => acc + item.requests, 0);

  const getUsagePercentage = () =>
    (billingPlan.quotaUsed / billingPlan.quotaLimit) * 100;
  const getRequestsPercentage = () =>
    (billingPlan.requestsUsed / billingPlan.requestsLimit) * 100;

  const handleCreateAlert = () => {
    const newAlert: BillingAlert = {
      id: Date.now().toString(),
      type: alertType,
      threshold: alertThreshold,
      isActive: true,
    };
    setAlerts([...alerts, newAlert]);
    setShowAlertModal(false);
    setAlertThreshold(100);
  };

  const toggleAlert = (id: string) => {
    setAlerts(
      alerts.map((alert) =>
        alert.id === id ? { ...alert, isActive: !alert.isActive } : alert,
      ),
    );
  };

  const columns = [
    {
      title: (
        <Text className="text-bud-text-disabled text-[12px] uppercase">
          DATE
        </Text>
      ),
      dataIndex: "date",
      key: "date",
      render: (date: string) => (
        <Text className="text-bud-text-primary text-[13px]">
          {dayjs(date).format("MMM DD, YYYY")}
        </Text>
      ),
    },
    {
      title: (
        <Text className="text-bud-text-disabled text-[12px] uppercase">
          MODEL
        </Text>
      ),
      dataIndex: "model",
      key: "model",
      render: (model: string) => (
        <Text className="text-bud-text-primary text-[13px]">{model}</Text>
      ),
    },
    {
      title: (
        <Text className="text-bud-text-disabled text-[12px] uppercase">
          TOKENS
        </Text>
      ),
      dataIndex: "tokens",
      key: "tokens",
      render: (tokens: number) => (
        <Text className="text-bud-text-primary text-[13px]">
          {tokens.toLocaleString()}
        </Text>
      ),
    },
    {
      title: (
        <Text className="text-bud-text-disabled text-[12px] uppercase">
          REQUESTS
        </Text>
      ),
      dataIndex: "requests",
      key: "requests",
      render: (requests: number) => (
        <Text className="text-bud-text-primary text-[13px]">{requests}</Text>
      ),
    },
    {
      title: (
        <Text className="text-bud-text-disabled text-[12px] uppercase">
          COST
        </Text>
      ),
      dataIndex: "cost",
      key: "cost",
      render: (cost: number) => (
        <Text className="text-bud-purple text-[13px]">${cost.toFixed(2)}</Text>
      ),
    },
  ];

  return (
    <DashboardLayout>
      <div className="boardPageView">
        <div className="boardMainContainer pt-[2.25rem]">
          {/* Header */}
          <Flex justify="space-between" align="center" className="mb-[2rem]">
            <div>
              <Title level={2} className="!text-bud-text-primary !mb-0">
                Usage & Billing
              </Title>
              <Text className="text-bud-text-muted text-[14px] mt-[0.5rem] block">
                Track your usage, costs, and manage billing alerts
              </Text>
            </div>
            <Button
              type="primary"
              icon={<Icon icon="ph:bell" />}
              className="bg-bud-purple border-bud-purple hover:bg-bud-purple-hover h-[2.5rem] px-[1.5rem]"
              onClick={() => setShowAlertModal(true)}
            >
              Set Alert
            </Button>
          </Flex>

          {/* Current Plan & Quota */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-[1.5rem] mb-[2rem]">
            {/* Plan Info */}
            <Card className="bg-bud-bg-secondary border-bud-border rounded-[12px]">
              <Flex align="center" gap={12} className="mb-[1rem]">
                <Icon
                  icon="ph:crown"
                  className="text-[#965CDE] text-[1.5rem]"
                />
                <Text className="text-bud-text-primary font-semibold text-[15px]">
                  Current Plan
                </Text>
              </Flex>
              <Text className="text-bud-text-primary text-[24px] font-medium mb-[0.5rem] block">
                {billingPlan.name}
              </Text>
              <Text className="text-bud-text-muted text-[14px] mb-[1rem] block">
                {billingPlan.cost}
              </Text>
              <Text className="text-bud-text-disabled text-[12px]">
                Next billing: {billingPlan.nextBilling}
              </Text>
            </Card>

            {/* Token Usage */}
            <Card className="bg-bud-bg-secondary border-bud-border rounded-[12px]">
              <Flex align="center" gap={12} className="mb-[1rem]">
                <Icon
                  icon="ph:coins"
                  className="text-[#4077E6] text-[1.5rem]"
                />
                <Text className="text-bud-text-primary font-semibold text-[15px]">
                  Token Usage
                </Text>
              </Flex>
              <Text className="text-bud-text-primary text-[24px] font-medium mb-[0.5rem] block">
                {(billingPlan.quotaUsed / 1000).toFixed(0)}K
              </Text>
              <Text className="text-bud-text-muted text-[12px] mb-[1rem] block">
                of {(billingPlan.quotaLimit / 1000).toFixed(0)}K tokens
              </Text>
              <Progress
                percent={getUsagePercentage()}
                strokeColor="#4077E6"
                trailColor="var(--bud-border-secondary)"
                showInfo={false}
                size="small"
              />
            </Card>

            {/* API Requests */}
            <Card className="bg-bud-bg-secondary border-bud-border rounded-[12px]">
              <Flex align="center" gap={12} className="mb-[1rem]">
                <Icon
                  icon="ph:chart-line"
                  className="text-[#479D5F] text-[1.5rem]"
                />
                <Text className="text-bud-text-primary font-semibold text-[15px]">
                  API Requests
                </Text>
              </Flex>
              <Text className="text-bud-text-primary text-[24px] font-medium mb-[0.5rem] block">
                {billingPlan.requestsUsed.toLocaleString()}
              </Text>
              <Text className="text-bud-text-muted text-[12px] mb-[1rem] block">
                of {billingPlan.requestsLimit.toLocaleString()} requests
              </Text>
              <Progress
                percent={getRequestsPercentage()}
                strokeColor="#479D5F"
                trailColor="var(--bud-border-secondary)"
                showInfo={false}
                size="small"
              />
            </Card>
          </div>

          {/* Usage Statistics */}
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-[1rem] mb-[2rem]">
            <div className="bg-bud-bg-secondary border-bud-border rounded-[8px] px-[1.5rem] py-[1rem]">
              <Text className="text-bud-text-disabled text-[12px]">
                Total Cost (7d)
              </Text>
              <Text className="text-bud-purple text-[24px] font-medium mt-[0.5rem] block">
                ${totalCost.toFixed(2)}
              </Text>
            </div>
            <div className="bg-bud-bg-secondary border-bud-border rounded-[8px] px-[1.5rem] py-[1rem]">
              <Text className="text-bud-text-disabled text-[12px]">
                Total Tokens
              </Text>
              <Text className="text-bud-text-primary text-[24px] font-medium mt-[0.5rem] block">
                {totalTokens.toLocaleString()}
              </Text>
            </div>
            <div className="bg-bud-bg-secondary border-bud-border rounded-[8px] px-[1.5rem] py-[1rem]">
              <Text className="text-bud-text-disabled text-[12px]">
                Total Requests
              </Text>
              <Text className="text-bud-text-primary text-[24px] font-medium mt-[0.5rem] block">
                {totalRequests}
              </Text>
            </div>
            <div className="bg-bud-bg-secondary border-bud-border rounded-[8px] px-[1.5rem] py-[1rem]">
              <Text className="text-bud-text-disabled text-[12px]">
                Avg Cost/Token
              </Text>
              <Text className="text-bud-text-primary text-[24px] font-medium mt-[0.5rem] block">
                ${((totalCost / totalTokens) * 1000).toFixed(3)}
              </Text>
            </div>
          </div>

          {/* Filters */}
          <Flex gap={16} className="mb-[2rem]" wrap="wrap">
            <Select
              value={timeRange}
              onChange={setTimeRange}
              style={{ width: 150 }}
              className={styles.selectFilter}
              options={[
                { value: "1d", label: "Last 24h" },
                { value: "7d", label: "Last 7 days" },
                { value: "30d", label: "Last 30 days" },
                { value: "90d", label: "Last 90 days" },
              ]}
            />

            <Select
              value={selectedModel}
              onChange={setSelectedModel}
              style={{ width: 200 }}
              className={styles.selectFilter}
              options={[
                { value: "all", label: "All Models" },
                { value: "gpt-4", label: "GPT-4" },
                { value: "gpt-3.5-turbo", label: "GPT-3.5 Turbo" },
                { value: "claude-3-opus", label: "Claude 3 Opus" },
                { value: "claude-3-sonnet", label: "Claude 3 Sonnet" },
              ]}
            />
          </Flex>

          {/* Billing Alerts */}
          <Card className="bg-bud-bg-secondary border-bud-border rounded-[12px] mb-[2rem]">
            <Flex
              justify="space-between"
              align="center"
              className="mb-[1.5rem]"
            >
              <Text className="text-bud-text-primary font-semibold text-[15px]">
                Billing Alerts
              </Text>
              <Button
                type="text"
                icon={<Icon icon="ph:plus" />}
                onClick={() => setShowAlertModal(true)}
                className="text-bud-purple hover:text-bud-purple-hover"
              >
                Add Alert
              </Button>
            </Flex>

            <div className="space-y-[1rem]">
              {alerts.map((alert) => (
                <div
                  key={alert.id}
                  className="bg-bud-bg-tertiary rounded-[8px] p-[1rem]"
                >
                  <Flex justify="space-between" align="center">
                    <div>
                      <Text className="text-bud-text-primary font-medium text-[14px] capitalize">
                        {alert.type} Alert
                      </Text>
                      <Text className="text-bud-text-muted text-[12px] mt-[0.25rem] block">
                        Triggers when {alert.type} reaches {alert.threshold}
                        {alert.type === "cost"
                          ? " USD"
                          : alert.type === "usage"
                            ? " tokens"
                            : " requests"}
                      </Text>
                    </div>
                    <Switch
                      checked={alert.isActive}
                      onChange={() => toggleAlert(alert.id)}
                      style={{
                        backgroundColor: alert.isActive
                          ? "var(--color-purple)"
                          : "var(--border-secondary)",
                      }}
                    />
                  </Flex>
                </div>
              ))}
            </div>
          </Card>

          {/* Usage History Table */}
          <Card className="bg-bud-bg-secondary border-bud-border rounded-[12px]">
            <Text className="text-bud-text-primary font-semibold text-[15px] mb-[1.5rem] block">
              Usage History
            </Text>
            <Table
              dataSource={usageData}
              columns={columns}
              rowKey="date"
              pagination={false}
              className={styles.usageTable}
            />
          </Card>

          {/* Create Alert Modal */}
          <Modal
            title={
              <Text className="text-bud-text-primary font-semibold text-[19px]">
                Create Billing Alert
              </Text>
            }
            open={showAlertModal}
            onCancel={() => setShowAlertModal(false)}
            footer={[
              <Button key="cancel" onClick={() => setShowAlertModal(false)}>
                Cancel
              </Button>,
              <Button
                key="create"
                type="primary"
                onClick={handleCreateAlert}
                className="bg-bud-purple border-bud-purple hover:bg-bud-purple-hover"
              >
                Create Alert
              </Button>,
            ]}
            className={styles.modal}
          >
            <div className="space-y-[1rem]">
              <div>
                <Text className="text-bud-text-muted text-[12px] mb-[0.5rem] block">
                  Alert Type
                </Text>
                <Select
                  value={alertType}
                  onChange={setAlertType}
                  className="w-full"
                  options={[
                    { value: "cost", label: "Cost Alert" },
                    { value: "usage", label: "Token Usage Alert" },
                    { value: "requests", label: "Request Count Alert" },
                  ]}
                />
              </div>

              <div>
                <Text className="text-bud-text-muted text-[12px] mb-[0.5rem] block">
                  Threshold
                </Text>
                <Input
                  type="number"
                  value={alertThreshold}
                  onChange={(e) => setAlertThreshold(Number(e.target.value))}
                  placeholder="Enter threshold value"
                  className="bg-bud-bg-tertiary border-bud-border-secondary"
                  suffix={
                    <Text className="text-bud-text-disabled text-[12px]">
                      {alertType === "cost"
                        ? "USD"
                        : alertType === "usage"
                          ? "tokens"
                          : "requests"}
                    </Text>
                  }
                />
              </div>
            </div>
          </Modal>
        </div>
      </div>
    </DashboardLayout>
  );
}

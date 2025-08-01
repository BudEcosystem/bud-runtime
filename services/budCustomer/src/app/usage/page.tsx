"use client";
import React, { useState } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { Flex, Select, DatePicker, Card, Progress, Button, Modal, Input, Switch, Table } from "antd";
import {
  Text_12_400_757575,
  Text_12_400_B3B3B3,
  Text_13_400_EEEEEE,
  Text_14_400_B3B3B3,
  Text_14_400_EEEEEE,
  Text_14_500_EEEEEE,
  Text_15_600_EEEEEE,
  Text_19_600_EEEEEE,
  Text_24_500_EEEEEE
} from "@/components/ui/text";
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
  const [alertType, setAlertType] = useState<"cost" | "usage" | "requests">("cost");
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
    nextBilling: "2024-02-15"
  };

  // Mock usage data
  const usageData: UsageData[] = [
    { date: "2024-01-20", tokens: 15420, cost: 12.50, requests: 150, model: "gpt-4", endpoint: "/v1/chat/completions" },
    { date: "2024-01-19", tokens: 12800, cost: 10.20, requests: 120, model: "claude-3-opus", endpoint: "/v1/chat/completions" },
    { date: "2024-01-18", tokens: 9200, cost: 7.80, requests: 95, model: "gpt-3.5-turbo", endpoint: "/v1/chat/completions" },
    { date: "2024-01-17", tokens: 18500, cost: 15.40, requests: 180, model: "gpt-4", endpoint: "/v1/chat/completions" },
    { date: "2024-01-16", tokens: 11300, cost: 9.10, requests: 110, model: "claude-3-sonnet", endpoint: "/v1/chat/completions" },
  ];

  // Mock alerts
  const [alerts, setAlerts] = useState<BillingAlert[]>([
    { id: "1", type: "cost", threshold: 100, isActive: true },
    { id: "2", type: "usage", threshold: 800000, isActive: true },
    { id: "3", type: "requests", threshold: 8000, isActive: false }
  ]);

  const totalCost = usageData.reduce((acc, item) => acc + item.cost, 0);
  const totalTokens = usageData.reduce((acc, item) => acc + item.tokens, 0);
  const totalRequests = usageData.reduce((acc, item) => acc + item.requests, 0);

  const getUsagePercentage = () => (billingPlan.quotaUsed / billingPlan.quotaLimit) * 100;
  const getRequestsPercentage = () => (billingPlan.requestsUsed / billingPlan.requestsLimit) * 100;

  const handleCreateAlert = () => {
    const newAlert: BillingAlert = {
      id: Date.now().toString(),
      type: alertType,
      threshold: alertThreshold,
      isActive: true
    };
    setAlerts([...alerts, newAlert]);
    setShowAlertModal(false);
    setAlertThreshold(100);
  };

  const toggleAlert = (id: string) => {
    setAlerts(alerts.map(alert => 
      alert.id === id ? { ...alert, isActive: !alert.isActive } : alert
    ));
  };

  const columns = [
    {
      title: <Text_12_400_757575>DATE</Text_12_400_757575>,
      dataIndex: 'date',
      key: 'date',
      render: (date: string) => <Text_13_400_EEEEEE>{dayjs(date).format('MMM DD, YYYY')}</Text_13_400_EEEEEE>
    },
    {
      title: <Text_12_400_757575>MODEL</Text_12_400_757575>,
      dataIndex: 'model',
      key: 'model',
      render: (model: string) => <Text_13_400_EEEEEE>{model}</Text_13_400_EEEEEE>
    },
    {
      title: <Text_12_400_757575>TOKENS</Text_12_400_757575>,
      dataIndex: 'tokens',
      key: 'tokens',
      render: (tokens: number) => <Text_13_400_EEEEEE>{tokens.toLocaleString()}</Text_13_400_EEEEEE>
    },
    {
      title: <Text_12_400_757575>REQUESTS</Text_12_400_757575>,
      dataIndex: 'requests',
      key: 'requests',
      render: (requests: number) => <Text_13_400_EEEEEE>{requests}</Text_13_400_EEEEEE>
    },
    {
      title: <Text_12_400_757575>COST</Text_12_400_757575>,
      dataIndex: 'cost',
      key: 'cost',
      render: (cost: number) => <Text_13_400_EEEEEE className="text-[#965CDE]">${cost.toFixed(2)}</Text_13_400_EEEEEE>
    }
  ];

  return (
    <DashboardLayout>
      <div className="boardPageView">
        <div className="boardMainContainer pt-[2.25rem]">
          {/* Header */}
          <Flex justify="space-between" align="center" className="mb-[2rem]">
            <div>
              <Text_24_500_EEEEEE>Usage & Billing</Text_24_500_EEEEEE>
              <Text_14_400_B3B3B3 className="mt-[0.5rem]">
                Track your usage, costs, and manage billing alerts
              </Text_14_400_B3B3B3>
            </div>
            <Button
              type="primary"
              icon={<Icon icon="ph:bell" />}
              className="bg-[#965CDE] border-[#965CDE] h-[2.5rem] px-[1.5rem]"
              onClick={() => setShowAlertModal(true)}
            >
              Set Alert
            </Button>
          </Flex>

          {/* Current Plan & Quota */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-[1.5rem] mb-[2rem]">
            {/* Plan Info */}
            <Card className="cardBG border border-[#1F1F1F] rounded-[12px]">
              <Flex align="center" gap={12} className="mb-[1rem]">
                <Icon icon="ph:crown" className="text-[#965CDE] text-[1.5rem]" />
                <Text_15_600_EEEEEE>Current Plan</Text_15_600_EEEEEE>
              </Flex>
              <Text_24_500_EEEEEE className="mb-[0.5rem]">{billingPlan.name}</Text_24_500_EEEEEE>
              <Text_14_400_B3B3B3 className="mb-[1rem]">{billingPlan.cost}</Text_14_400_B3B3B3>
              <Text_12_400_757575>Next billing: {billingPlan.nextBilling}</Text_12_400_757575>
            </Card>

            {/* Token Usage */}
            <Card className="cardBG border border-[#1F1F1F] rounded-[12px]">
              <Flex align="center" gap={12} className="mb-[1rem]">
                <Icon icon="ph:coins" className="text-[#4077E6] text-[1.5rem]" />
                <Text_15_600_EEEEEE>Token Usage</Text_15_600_EEEEEE>
              </Flex>
              <Text_24_500_EEEEEE className="mb-[0.5rem]">
                {(billingPlan.quotaUsed / 1000).toFixed(0)}K
              </Text_24_500_EEEEEE>
              <Text_12_400_B3B3B3 className="mb-[1rem]">
                of {(billingPlan.quotaLimit / 1000).toFixed(0)}K tokens
              </Text_12_400_B3B3B3>
              <Progress 
                percent={getUsagePercentage()} 
                strokeColor="#4077E6"
                trailColor="#2F2F2F"
                showInfo={false}
                size="small"
              />
            </Card>

            {/* API Requests */}
            <Card className="cardBG border border-[#1F1F1F] rounded-[12px]">
              <Flex align="center" gap={12} className="mb-[1rem]">
                <Icon icon="ph:chart-line" className="text-[#479D5F] text-[1.5rem]" />
                <Text_15_600_EEEEEE>API Requests</Text_15_600_EEEEEE>
              </Flex>
              <Text_24_500_EEEEEE className="mb-[0.5rem]">
                {billingPlan.requestsUsed.toLocaleString()}
              </Text_24_500_EEEEEE>
              <Text_12_400_B3B3B3 className="mb-[1rem]">
                of {billingPlan.requestsLimit.toLocaleString()} requests
              </Text_12_400_B3B3B3>
              <Progress 
                percent={getRequestsPercentage()} 
                strokeColor="#479D5F"
                trailColor="#2F2F2F"
                showInfo={false}
                size="small"
              />
            </Card>
          </div>

          {/* Usage Statistics */}
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-[1rem] mb-[2rem]">
            <div className="cardBG border border-[#1F1F1F] rounded-[8px] px-[1.5rem] py-[1rem]">
              <Text_12_400_757575>Total Cost (7d)</Text_12_400_757575>
              <Text_24_500_EEEEEE className="mt-[0.5rem] text-[#965CDE]">${totalCost.toFixed(2)}</Text_24_500_EEEEEE>
            </div>
            <div className="cardBG border border-[#1F1F1F] rounded-[8px] px-[1.5rem] py-[1rem]">
              <Text_12_400_757575>Total Tokens</Text_12_400_757575>
              <Text_24_500_EEEEEE className="mt-[0.5rem]">{totalTokens.toLocaleString()}</Text_24_500_EEEEEE>
            </div>
            <div className="cardBG border border-[#1F1F1F] rounded-[8px] px-[1.5rem] py-[1rem]">
              <Text_12_400_757575>Total Requests</Text_12_400_757575>
              <Text_24_500_EEEEEE className="mt-[0.5rem]">{totalRequests}</Text_24_500_EEEEEE>
            </div>
            <div className="cardBG border border-[#1F1F1F] rounded-[8px] px-[1.5rem] py-[1rem]">
              <Text_12_400_757575>Avg Cost/Token</Text_12_400_757575>
              <Text_24_500_EEEEEE className="mt-[0.5rem]">${(totalCost / totalTokens * 1000).toFixed(3)}</Text_24_500_EEEEEE>
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
                { value: "90d", label: "Last 90 days" }
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
                { value: "claude-3-sonnet", label: "Claude 3 Sonnet" }
              ]}
            />
          </Flex>

          {/* Billing Alerts */}
          <Card className="cardBG border border-[#1F1F1F] rounded-[12px] mb-[2rem]">
            <Flex justify="space-between" align="center" className="mb-[1.5rem]">
              <Text_15_600_EEEEEE>Billing Alerts</Text_15_600_EEEEEE>
              <Button
                type="text"
                icon={<Icon icon="ph:plus" />}
                onClick={() => setShowAlertModal(true)}
                className="text-[#965CDE]"
              >
                Add Alert
              </Button>
            </Flex>
            
            <div className="space-y-[1rem]">
              {alerts.map((alert) => (
                <div key={alert.id} className="bg-[#1F1F1F] rounded-[8px] p-[1rem]">
                  <Flex justify="space-between" align="center">
                    <div>
                      <Text_14_500_EEEEEE className="capitalize">
                        {alert.type} Alert
                      </Text_14_500_EEEEEE>
                      <Text_12_400_B3B3B3 className="mt-[0.25rem]">
                        Triggers when {alert.type} reaches {alert.threshold}
                        {alert.type === 'cost' ? ' USD' : alert.type === 'usage' ? ' tokens' : ' requests'}
                      </Text_12_400_B3B3B3>
                    </div>
                    <Switch
                      checked={alert.isActive}
                      onChange={() => toggleAlert(alert.id)}
                      style={{
                        backgroundColor: alert.isActive ? '#965CDE' : '#2F2F2F'
                      }}
                    />
                  </Flex>
                </div>
              ))}
            </div>
          </Card>

          {/* Usage History Table */}
          <Card className="cardBG border border-[#1F1F1F] rounded-[12px]">
            <Text_15_600_EEEEEE className="mb-[1.5rem]">Usage History</Text_15_600_EEEEEE>
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
            title={<Text_19_600_EEEEEE>Create Billing Alert</Text_19_600_EEEEEE>}
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
                className="bg-[#965CDE] border-[#965CDE]"
              >
                Create Alert
              </Button>
            ]}
            className={styles.modal}
          >
            <div className="space-y-[1rem]">
              <div>
                <Text_12_400_B3B3B3 className="mb-[0.5rem]">Alert Type</Text_12_400_B3B3B3>
                <Select
                  value={alertType}
                  onChange={setAlertType}
                  className="w-full"
                  options={[
                    { value: "cost", label: "Cost Alert" },
                    { value: "usage", label: "Token Usage Alert" },
                    { value: "requests", label: "Request Count Alert" }
                  ]}
                />
              </div>
              
              <div>
                <Text_12_400_B3B3B3 className="mb-[0.5rem]">Threshold</Text_12_400_B3B3B3>
                <Input
                  type="number"
                  value={alertThreshold}
                  onChange={(e) => setAlertThreshold(Number(e.target.value))}
                  placeholder="Enter threshold value"
                  className="bg-[#1F1F1F] border-[#2F2F2F]"
                  suffix={
                    <Text_12_400_757575>
                      {alertType === 'cost' ? 'USD' : alertType === 'usage' ? 'tokens' : 'requests'}
                    </Text_12_400_757575>
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
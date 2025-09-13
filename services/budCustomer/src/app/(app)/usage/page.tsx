"use client";
import React, { use, useEffect, useState } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import {
  Flex,
  Select,
  Button,
  ConfigProvider,
  Tabs,
  Skeleton,
  Card,
  Switch,
  App,
} from "antd";
import { Typography } from "antd";
import { Icon } from "@iconify/react/dist/iconify.js";
import styles from "./usage.module.scss";
import dayjs from "dayjs";
import { AppRequest } from "@/services/api/requests";
import { useProjects } from "@/hooks/useProjects";
import { useBillingAlerts } from "@/hooks/useBillingAlerts";
import { useNotification, successToast } from "@/components/toast";
import { openWarning } from "@/components/warningMessage";
import { useDrawer } from "@/hooks/useDrawer";
import BudDrawer from "@/components/ui/bud/drawer/BudDrawer";
import { motion, AnimatePresence } from "framer-motion";
import dynamic from "next/dynamic";

const { Text, Title } = Typography;

// Dynamic imports for chart components
const UsageChart = dynamic(() => import("./components/UsageChart"), {
  ssr: false,
  loading: () => <Skeleton.Node active className="h-[300px] w-full" />,
});

const MetricCard = dynamic(() => import("./components/MetricCard"), {
  ssr: false,
});

const UsageTable = dynamic(() => import("./components/UsageTable"), {
  ssr: false,
});

interface UsageData {
  date: string;
  tokens: number;
  cost: number;
  requests: number;
  model: string;
  endpoint: string;
}

interface UsageMetrics {
  totalSpend: number;
  totalTokens: number;
  totalRequests: number;
  previousSpend?: number;
  previousTokens?: number;
  previousRequests?: number;
}

export default function UsagePage() {
  const { notification: antNotification } = App.useApp();
  const { openDrawer } = useDrawer();
  const { globalProjects, getGlobalProjects, loading } = useProjects();
  const {
    alerts,
    loading: alertsLoading,
    getBillingAlerts,
    updateBillingAlertStatus,
    deleteBillingAlert,
  } = useBillingAlerts();
  const notification = useNotification();
  const [timeRange, setTimeRange] = useState("30d");
  const [selectedProject, setSelectedProject] = useState("all");
  const [availableProjects, setAvailableProjects] = useState<any>([]);
  const [activeTab, setActiveTab] = useState("spend");
  const [isLoading, setIsLoading] = useState(true);
  const [chartLoading, setChartLoading] = useState(false);

  // Usage metrics
  const [metrics, setMetrics] = useState<UsageMetrics>({
    totalSpend: 0,
    totalTokens: 0,
    totalRequests: 0,
  });

  // Billing plan data
  const [billingPlan, setBillingPlan] = useState({
    has_billing: false,
    billing_period_start: "",
    billing_period_end: "",
    plan_name: "Free",
    base_monthly_price: 0.0,
    usage: {
      tokens_used: 0,
      tokens_quota: 0,
      tokens_usage_percent: 0,
      cost_used: 0,
      cost_quota: 0,
      cost_usage_percent: 0,
      request_count: 0,
      success_rate: 0,
    },
    is_suspended: false,
    suspension_reason: null,
  });

  // Usage data for charts and table
  const [usageData, setUsageData] = useState<UsageData[]>([]);
  const [chartData, setChartData] = useState<any[]>([]);

  const themeConfig = {
    components: {
      Select: {
        colorBgContainer: "var(--bg-tertiary)",
        colorBorder: "var(--border-secondary)",
        optionSelectedBg: "var(--bg-hover)",
        colorBgElevated: "var(--bg-hover)",
        colorText: "var(--text-primary)",
        optionSelectedColor: "var(--text-primary)",
        optionActiveBg: "var(--bg-hover)",
      },
      Tabs: {
        colorBorderSecondary: "transparent",
        itemSelectedColor: "var(--text-primary)",
        itemColor: "var(--text-muted)",
        inkBarColor: "var(--text-primary)",
      },
    },
  };

  const fetchUsageData = async () => {
    try {
      setIsLoading(true);
      const response = await AppRequest.Get("/billing/current");
      setBillingPlan(response.data.result);

      // Calculate metrics with proper values
      const currentMetrics = response.data.result.usage;
      setMetrics({
        totalSpend: currentMetrics.cost_used || 0,
        totalTokens: currentMetrics.tokens_used || 0,
        totalRequests: currentMetrics.request_count || 0,
        previousSpend: 0, // Would need historical data
        previousTokens: 0,
        previousRequests: 0,
      });
    } catch (error) {
      console.error("Failed to fetch usage data:", error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    console.log("Updated metrics:", metrics);
  }, [metrics]);

  const generateDateRange = (startDate: string, endDate: string) => {
    const dates = [];
    const start = dayjs(startDate);
    const end = dayjs(endDate);
    let current = start;

    while (current.isBefore(end) || current.isSame(end, "day")) {
      dates.push(current.format("YYYY-MM-DD"));
      current = current.add(1, "day");
    }
    return dates;
  };

  const fetchBillingHistoryData = async (params: any) => {
    try {
      setChartLoading(true);
      const response = await AppRequest.Post("/billing/history", params);
      const data = response.data.result.data || [];
      setUsageData(data);

      // Generate complete date range
      const allDates = generateDateRange(
        params.start_date.split(" ")[0],
        params.end_date.split(" ")[0],
      );

      // Create a map of existing data
      const dataMap = new Map();
      data.forEach((item: UsageData) => {
        const dateKey = dayjs(item.date).format("YYYY-MM-DD");
        dataMap.set(dateKey, item);
      });

      // Fill in missing dates with zero values
      const completeData = allDates.map((date) => {
        const existingData = dataMap.get(date);
        if (existingData) {
          // Only mark as hasData: true if there's actual usage (cost > 0)
          const hasUsage =
            existingData.cost > 0 ||
            existingData.tokens > 0 ||
            existingData.requests > 0;
          return {
            date: existingData.date,
            displayDate: dayjs(existingData.date).format("MMM DD"),
            cost: existingData.cost || 0,
            tokens: existingData.tokens || 0,
            requests: existingData.requests || 0,
            hasData: hasUsage,
          };
        } else {
          return {
            date: date,
            displayDate: dayjs(date).format("MMM DD"),
            cost: 0,
            tokens: 0,
            requests: 0,
            hasData: false,
          };
        }
      });

      setChartData(completeData);
    } catch (error) {
      console.error("Failed to fetch usage data:", error);
    } finally {
      setChartLoading(false);
    }
  };

  useEffect(() => {
    const projectsList: any = globalProjects.map((item) => ({
      value: item.project.id,
      label: item.project.name,
    }));
    setAvailableProjects([
      { value: "all", label: "All Projects" },
      ...projectsList,
    ]);
  }, [globalProjects]);

  useEffect(() => {
    fetchUsageData();
    getGlobalProjects(1, 1000);
    getBillingAlerts();
  }, []);

  const getDateRange = (option: string) => {
    const now = new Date();
    const end = new Date(now);
    end.setHours(23, 59, 59, 999);

    let start = new Date(now);

    switch (option) {
      case "1d":
        start.setDate(start.getDate() - 1);
        start.setHours(0, 0, 0, 0);
        break;
      case "7d":
        start.setDate(start.getDate() - 7);
        start.setHours(0, 0, 0, 0);
        break;
      case "30d":
        start.setDate(start.getDate() - 30);
        start.setHours(0, 0, 0, 0);
        break;
      case "90d":
        start.setDate(start.getDate() - 90);
        start.setHours(0, 0, 0, 0);
        break;
      default:
        break;
    }

    const formatDateString = (date: Date, endOfDay = false) => {
      const y = date.getFullYear();
      const m = String(date.getMonth() + 1).padStart(2, "0");
      const d = String(date.getDate()).padStart(2, "0");
      return endOfDay ? `${y}-${m}-${d} 23:59:59` : `${y}-${m}-${d} 00:00:00`;
    };

    return {
      start: formatDateString(start, false),
      end: formatDateString(end, true),
    };
  };

  useEffect(() => {
    const dateRanges = getDateRange(timeRange);
    let params: any = {
      granularity: "daily",
      start_date: dateRanges.start,
      end_date: dateRanges.end,
    };
    if (selectedProject !== "all") {
      params = { ...params, project_id: selectedProject };
    }
    fetchBillingHistoryData(params);
  }, [timeRange, selectedProject]);

  const tabItems = [
    {
      key: "spend",
      label: "Total Spend",
      children: (
        <div className="mt-6">
          <UsageChart
            data={chartData}
            type="spend"
            loading={chartLoading}
            timeRange={timeRange}
          />
        </div>
      ),
    },
  ];

  const handleExport = () => {
    // Export functionality
    const dataStr = JSON.stringify(usageData, null, 2);
    const dataUri =
      "data:application/json;charset=utf-8," + encodeURIComponent(dataStr);
    const exportFileDefaultName = `usage-data-${dayjs().format("YYYY-MM-DD")}.json`;
    const linkElement = document.createElement("a");
    linkElement.setAttribute("href", dataUri);
    linkElement.setAttribute("download", exportFileDefaultName);
    linkElement.click();
  };

  const toggleAlert = async (id: string, currentStatus: boolean) => {
    try {
      await updateBillingAlertStatus(id, !currentStatus);
      notification.successToast(
        `Alert ${!currentStatus ? "enabled" : "disabled"} successfully`,
      );
    } catch (error: any) {
      notification.errorToast(error.message || "Failed to update alert status");
    }
  };

  const handleDeleteAlert = (id: string, name: string) => {
    const title = `You're about to delete "${name}"`;
    const description =
      "This billing alert will be permanently removed and will no longer notify you when usage thresholds are reached.";

    const updateNotificationMessage = openWarning({
      title: title,
      description: description,
      deleteDisabled: false,
      notification: antNotification,
      onDelete: () => {
        deleteBillingAlert(id)
          .then(() => {
            successToast("Billing alert deleted successfully");
            antNotification.destroy(`${title}-delete-notification`);
          })
          .catch((error) => {
            console.error("Error deleting alert:", error);
            updateNotificationMessage(
              error.message || "Failed to delete alert",
            );
          });
      },
      onCancel: () => {
        // No action needed on cancel
      },
    });
  };

  const handleOpenCreateAlert = () => {
    openDrawer("create-billing-alert");
  };

  return (
    <App>
      <DashboardLayout>
        <div className={styles.usageContainer}>
          <div className={styles.pageContent}>
            {/* Header */}
            <div className={styles.header}>
              <div>
                <Title level={2} className={styles.pageTitle}>
                  Usage
                </Title>
              </div>
              <div className={styles.headerActions}>
                <ConfigProvider theme={themeConfig}>
                  <Select
                    value={selectedProject}
                    onChange={setSelectedProject}
                    style={{ width: 200 }}
                    className={styles.projectSelect}
                    options={availableProjects}
                  />
                </ConfigProvider>
                <ConfigProvider theme={themeConfig}>
                  <Select
                    value={timeRange}
                    onChange={setTimeRange}
                    style={{ width: 150 }}
                    className={styles.dateSelect}
                    options={[
                      { value: "1d", label: "1d" },
                      { value: "7d", label: "7d" },
                      { value: "30d", label: "30d" },
                      { value: "90d", label: "90d" },
                    ]}
                  />
                </ConfigProvider>
                <Button
                  icon={<Icon icon="ph:export" />}
                  className={styles.exportBtn}
                  onClick={handleExport}
                >
                  Export
                </Button>
                {/* <Button
                type="primary"
                icon={<Icon icon="ph:bell" />}
                className="bg-bud-purple border-bud-purple hover:bg-bud-purple-hover h-[2.5rem] px-[1.5rem]"
                onClick={handleOpenCreateAlert}
              >
                Set Alert
              </Button> */}
              </div>
            </div>

            {/* Metrics Section */}
            <div className={styles.metricsSection}>
              <MetricCard
                title="Total Spend"
                value={`$${metrics.totalSpend.toFixed(2)}\nof $${billingPlan.usage.cost_quota.toFixed(2)}`}
                loading={isLoading}
                trend={
                  metrics.previousSpend
                    ? ((metrics.totalSpend - metrics.previousSpend) /
                        metrics.previousSpend) *
                      100
                    : 0
                }
              />
              <MetricCard
                title="Total tokens"
                value={
                  metrics.totalTokens < 10000
                    ? `${(metrics.totalTokens / 1000).toFixed(1)}K\nof ${(billingPlan.usage.tokens_quota / 1000).toFixed(1)}K`
                    : `${(metrics.totalTokens / 1000).toFixed(0)}K\nof ${(billingPlan.usage.tokens_quota / 1000).toFixed(0)}K`
                }
                loading={isLoading}
                trend={
                  metrics.previousTokens
                    ? ((metrics.totalTokens - metrics.previousTokens) /
                        metrics.previousTokens) *
                      100
                    : 0
                }
              />
              <MetricCard
                title="Total requests"
                value={metrics.totalRequests.toLocaleString()}
                loading={isLoading}
                trend={
                  metrics.previousRequests
                    ? ((metrics.totalRequests - metrics.previousRequests) /
                        metrics.previousRequests) *
                      100
                    : 0
                }
              />

              {/* Current Plan Section */}
              <div className={styles.planSection}>
                <div className={styles.sectionHeader}>
                  <Text className={styles.sectionTitle}>Current Plan</Text>
                  {billingPlan.billing_period_end && (
                    <Text className={styles.nextBilling}>
                      Next billing:{" "}
                      {dayjs(billingPlan.billing_period_end).format(
                        "MMM DD, YYYY",
                      )}
                    </Text>
                  )}
                </div>
                <div className={styles.planDetails}>
                  {isLoading ? (
                    <Skeleton active paragraph={{ rows: 2 }} />
                  ) : (
                    <>
                      <div className={styles.planName}>
                        <Icon
                          icon="ph:crown-simple"
                          className={styles.planIcon}
                        />
                        <Text className={styles.planTitle}>Free</Text>
                      </div>
                      <Text className={styles.planPrice}>$0/month</Text>
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* Charts Section */}
            <div className={styles.chartsSection}>
              <ConfigProvider theme={themeConfig}>
                <Tabs
                  activeKey={activeTab}
                  onChange={setActiveTab}
                  items={tabItems}
                  className={styles.chartTabs}
                />
              </ConfigProvider>
            </div>

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
                  onClick={handleOpenCreateAlert}
                  className="text-bud-purple hover:text-bud-purple-hover"
                >
                  Add Alert
                </Button>
              </Flex>

              <div className="space-y-[1rem]">
                {alertsLoading ? (
                  <div className="text-center py-[2rem]">
                    <Text className="text-bud-text-muted">
                      Loading alerts...
                    </Text>
                  </div>
                ) : alerts.length === 0 ? (
                  <div className="text-center py-[2rem]">
                    <Text className="text-bud-text-muted">
                      No billing alerts configured
                    </Text>
                  </div>
                ) : (
                  alerts.map((alert) => (
                    <div
                      key={alert.id}
                      className="bg-bud-bg-tertiary rounded-[8px] p-[1rem]"
                    >
                      <Flex justify="space-between" align="center">
                        <div className="flex-1">
                          <div className="flex items-center justify-between mb-[0.5rem]">
                            <Text className="text-bud-text-primary font-medium text-[14px]">
                              {alert.name}
                            </Text>
                          </div>
                          <Text className="text-bud-text-muted text-[12px] block">
                            {alert.alert_type === "cost_usage"
                              ? "Cost"
                              : "Token Usage"}{" "}
                            Alert - Triggers at {alert.threshold_percent}%
                          </Text>
                          {alert.last_triggered_at && (
                            <Text className="text-bud-text-disabled text-[11px] block mt-[0.25rem]">
                              Last triggered:{" "}
                              {new Date(
                                alert.last_triggered_at,
                              ).toLocaleDateString()}
                            </Text>
                          )}
                        </div>
                        <Switch
                          checked={alert.is_active}
                          loading={alertsLoading}
                          onChange={() =>
                            toggleAlert(alert.id, alert.is_active)
                          }
                          style={{
                            backgroundColor: alert.is_active
                              ? "var(--color-purple)"
                              : "var(--border-secondary)",
                          }}
                        />
                        <Button
                          type="text"
                          size="small"
                          danger
                          icon={
                            <img
                              src="/images/icons/deleteRed.png"
                              alt="Delete"
                              style={{ width: 16, height: 16 }}
                            />
                          }
                          onClick={() =>
                            handleDeleteAlert(alert.id, alert.name)
                          }
                          className="text-red-400 hover:text-red-300"
                        />
                      </Flex>
                    </div>
                  ))
                )}
              </div>
            </Card>

            {/* Usage Table */}
            <div className={styles.tableSection}>
              <UsageTable data={usageData} loading={chartLoading} />
            </div>
          </div>
        </div>
        <BudDrawer />
      </DashboardLayout>
    </App>
  );
}

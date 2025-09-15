"use client";
import React, { useState, useMemo, useEffect } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import {
  Table,
  Button,
  Select,
  DatePicker,
  Input,
  Card,
  Tag,
  Space,
  Dropdown,
  Tooltip,
  Typography,
  Badge,
  Empty,
  ConfigProvider,
  Pagination,
  Skeleton,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  SearchOutlined,
  FilterOutlined,
  DownloadOutlined,
  CalendarOutlined,
  ClockCircleOutlined,
  UserOutlined,
  KeyOutlined,
  FileTextOutlined,
  DatabaseOutlined,
  LoginOutlined,
  LogoutOutlined,
  EditOutlined,
  DeleteOutlined,
  PlusOutlined,
  EyeOutlined,
  ExportOutlined,
} from "@ant-design/icons";
import { Icon } from "@iconify/react/dist/iconify.js";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import isToday from "dayjs/plugin/isToday";
import isYesterday from "dayjs/plugin/isYesterday";
import styles from "./audit.module.scss";
import { AppRequest } from "@/services/api/requests";
import Tags from "@/components/ui/Tags";
import { motion, AnimatePresence } from "framer-motion";

dayjs.extend(relativeTime);
dayjs.extend(isToday);
dayjs.extend(isYesterday);

const { RangePicker } = DatePicker;
const { Text, Title } = Typography;

// Enums for audit actions and resource types
enum AuditAction {
  CREATE = "create",
  UPDATE = "update",
  DELETE = "delete",
  ACCESS = "access",
  EXPORT = "export",
  LOGIN = "login",
  LOGOUT = "logout",
  REGENERATE = "regenerate",
  LOGIN_FAILED = "login_failed",
}

enum ResourceType {
  API_KEY = "api_key",
  PROJECT = "project",
  USER = "user",
  SESSION = "session",
}

// Audit log interface
interface AuditLog {
  id: string;
  user_id: string;
  user_name: string;
  action: AuditAction;
  resource_type: ResourceType;
  resource_id: string;
  resource_name: string;
  project_id?: string;
  project_name?: string;
  timestamp: string;
  metadata?: Record<string, any>;
  ip_address?: string;
  user_agent?: string;
  status: "success" | "failed";
}

// Mock data generator
const generateMockAuditLogs = (): AuditLog[] => {
  const logs: AuditLog[] = [];
  const users = [
    "admin@bud.studio",
    "john.doe@company.com",
    "jane.smith@company.com",
  ];
  const projects = ["E-commerce AI", "Content Generator", "Document Analysis"];

  // Generate logs for different time periods
  const now = dayjs();

  // Today's logs
  for (let i = 0; i < 15; i++) {
    logs.push({
      id: `audit_${Date.now()}_${i}`,
      user_id: `user_${i % 3}`,
      user_name: users[i % 3],
      action: Object.values(AuditAction)[
        Math.floor(Math.random() * 8)
      ] as AuditAction,
      resource_type: Object.values(ResourceType)[
        Math.floor(Math.random() * 7)
      ] as ResourceType,
      resource_id: `res_${Math.random().toString(36).substr(2, 9)}`,
      resource_name: `Resource ${i + 1}`,
      project_id: i % 2 === 0 ? `proj_${i}` : undefined,
      project_name: i % 2 === 0 ? projects[i % 3] : undefined,
      timestamp: now.subtract(i * 2, "hours").toISOString(),
      ip_address: `192.168.1.${100 + i}`,
      user_agent: "Mozilla/5.0",
      status: Math.random() > 0.1 ? "success" : "failed",
      metadata: {
        changes: Math.floor(Math.random() * 10),
        duration: Math.floor(Math.random() * 1000) + "ms",
      },
    });
  }

  // Yesterday's logs
  for (let i = 0; i < 10; i++) {
    logs.push({
      id: `audit_yesterday_${i}`,
      user_id: `user_${i % 3}`,
      user_name: users[i % 3],
      action: Object.values(AuditAction)[
        Math.floor(Math.random() * 8)
      ] as AuditAction,
      resource_type: Object.values(ResourceType)[
        Math.floor(Math.random() * 7)
      ] as ResourceType,
      resource_id: `res_${Math.random().toString(36).substr(2, 9)}`,
      resource_name: `Resource Y${i + 1}`,
      project_id: `proj_${i}`,
      project_name: projects[i % 3],
      timestamp: now.subtract(1, "day").subtract(i, "hours").toISOString(),
      ip_address: `192.168.1.${50 + i}`,
      user_agent: "Chrome/96.0",
      status: "success",
      metadata: {},
    });
  }

  // This week's logs
  for (let i = 0; i < 20; i++) {
    logs.push({
      id: `audit_week_${i}`,
      user_id: `user_${i % 3}`,
      user_name: users[i % 3],
      action: Object.values(AuditAction)[
        Math.floor(Math.random() * 8)
      ] as AuditAction,
      resource_type: Object.values(ResourceType)[
        Math.floor(Math.random() * 7)
      ] as ResourceType,
      resource_id: `res_${Math.random().toString(36).substr(2, 9)}`,
      resource_name: `Resource W${i + 1}`,
      timestamp: now.subtract(2 + Math.floor(i / 5), "days").toISOString(),
      ip_address: `192.168.2.${i}`,
      user_agent: "Safari/15.0",
      status: "success",
      metadata: {},
    });
  }

  return logs;
};

export default function AuditPage() {
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [selectedAction, setSelectedAction] = useState<string | undefined>(
    undefined,
  );
  const [selectedResource, setSelectedResource] = useState<string | undefined>(
    undefined,
  );
  const [dateRange, setDateRange] = useState<
    [dayjs.Dayjs | null, dayjs.Dayjs | null] | null
  >(null);
  const [searchText, setSearchText] = useState("");
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
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
    },
  };

  const [dayFilter, setDayFilter] = useState([
    {
      label: "Today",
      value: "today",
      active: true,
    },
    {
      label: "Yesterday",
      value: "yesterday",
    },
    {
      label: "This week",
      value: "week",
    },
  ]);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [totalNumber, setTotalNumber] = useState(0);
  const [isStatsLoading, setIsStatsLoading] = useState(false);
  const [loading, setLoading] = useState(false);

  const setCurrentDayFilter = (val: any) => {
    setDayFilter(
      dayFilter.map((item) => ({ ...item, active: item.value == val })),
    );
  };
  // Get action icon and color
  const getActionDisplay = (action: AuditAction) => {
    const config = {
      [AuditAction.CREATE]: {
        icon: <PlusOutlined />,
        color: "green",
        label: "Created",
      },
      [AuditAction.UPDATE]: {
        icon: <EditOutlined />,
        color: "blue",
        label: "Updated",
      },
      [AuditAction.DELETE]: {
        icon: <DeleteOutlined />,
        color: "red",
        label: "Deleted",
      },
      [AuditAction.ACCESS]: {
        icon: <EyeOutlined />,
        color: "cyan",
        label: "Accessed",
      },
      [AuditAction.EXPORT]: {
        icon: <ExportOutlined />,
        color: "purple",
        label: "Exported",
      },
      [AuditAction.LOGIN]: {
        icon: <LoginOutlined />,
        color: "green",
        label: "Logged In",
      },
      [AuditAction.LOGOUT]: {
        icon: <LogoutOutlined />,
        color: "orange",
        label: "Logged Out",
      },
      [AuditAction.REGENERATE]: {
        icon: <Icon icon="ph:arrows-clockwise" />,
        color: "blue",
        label: "Regenerated",
      },
      [AuditAction.LOGIN_FAILED]: {
        icon: <LoginOutlined />,
        color: "red",
        label: "Login Failed",
      },
    };
    return config[action] || { icon: null, color: "default", label: action };
  };

  // Get resource icon
  const getResourceIcon = (resourceType: ResourceType) => {
    const icons = {
      [ResourceType.API_KEY]: <KeyOutlined />,
      [ResourceType.PROJECT]: <Icon icon="ph:folder" />,
      [ResourceType.USER]: <UserOutlined />,
      [ResourceType.SESSION]: <Icon icon="ph:stack" />,
    };
    return icons[resourceType] || <DatabaseOutlined />;
  };

  // Filter logs based on selected filters
  const filteredLogs = useMemo(() => {
    let filtered = [...auditLogs];

    if (selectedAction) {
      filtered = filtered.filter((log) => log.action === selectedAction);
    }

    if (selectedResource) {
      filtered = filtered.filter(
        (log) => log.resource_type === selectedResource,
      );
    }

    if (dateRange && dateRange[0] && dateRange[1]) {
      filtered = filtered.filter((log) => {
        const logDate = dayjs(log.timestamp);
        return logDate.isAfter(dateRange[0]) && logDate.isBefore(dateRange[1]);
      });
    }

    if (searchText) {
      filtered = filtered.filter(
        (log) =>
          log.resource_name
            ?.toLowerCase()
            .includes(searchText?.toLowerCase()) ||
          log.user_name?.toLowerCase().includes(searchText?.toLowerCase()) ||
          log.resource_id?.toLowerCase().includes(searchText?.toLowerCase()),
      );
    }

    return filtered.sort(
      (a, b) =>
        new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
    );
  }, [auditLogs, selectedAction, selectedResource, dateRange, searchText]);

  // Group logs by date
  const groupedLogs = useMemo(() => {
    const groups: Record<string, AuditLog[]> = {
      today: [],
      yesterday: [],
      thisWeek: [],
      older: [],
    };

    filteredLogs.forEach((log) => {
      const logDate = dayjs(log.timestamp);
      if (logDate.isToday()) {
        groups.today.push(log);
      } else if (logDate.isYesterday()) {
        groups.yesterday.push(log);
      } else if (logDate.isAfter(dayjs().subtract(7, "days"))) {
        groups.thisWeek.push(log);
      } else {
        groups.older.push(log);
      }
    });

    return groups;
  }, [filteredLogs]);

  const pad = (n: number) => {
    return n < 10 ? "0" + n : n;
  };

  const formatDateString = (date: Date | null, endOfDay = false) => {
    if (!date) return undefined;
    const y = date.getFullYear();
    const m = pad(date.getMonth() + 1);
    const d = pad(date.getDate());

    if (endOfDay) {
      return `${y}-${m}-${d} 23:59:59`;
    } else {
      return `${y}-${m}-${d} 00:00:00`;
    }
  };

  const getAuditList = async () => {
    setLoading(true);
    try {
      const params = {
        page: currentPage,
        limit: pageSize,
        action: selectedAction,
        resource_type: selectedResource,
        search: searchText,
        start_date: dateRange?.[0]
          ? formatDateString(dateRange[0]?.toDate(), false)
          : undefined,
        end_date: dateRange?.[1]
          ? formatDateString(dateRange[1]?.toDate(), true)
          : undefined,
      };
      const response = await AppRequest.Get("/audit/records", { params });
      setAuditLogs(
        response.data.data.map((item: any) => ({
          ...item,
          status: item.details?.success === false ? "failed" : "success",
        })),
      );
      setTotalNumber(response.data.total_record);
    } catch (error) {
      console.error("Failed to fetch usage data:", error);
    } finally {
      setLoading(false);
    }
  };

  const [statistics, setStatistics] = useState({
    totalEvents: 0,
    failedActions: 0,
    resourcesModified: 0,
  });
  const getAuditSummary = async () => {
    setIsStatsLoading(true);
    try {
      // const params = {
      //   start_date: dateRange?.[0] ? formatDateString(dateRange[0]?.toDate(), false) : undefined,
      //   end_date: dateRange?.[1] ? formatDateString(dateRange[1]?.toDate(), true) : undefined
      // }
      const { data } = await AppRequest.Get("/audit/summary");
      setStatistics({
        totalEvents: data.data.total_records || 0,
        failedActions: data.data.failure_events_count || 0,
        resourcesModified: data.data.unique_resources_updated || 0,
      });
    } catch (error) {
      console.error("Failed to fetch usage data:", error);
    } finally {
      setIsStatsLoading(false);
    }
  };
  // Table columns
  const columns: ColumnsType<AuditLog> = [
    {
      title: "Time",
      dataIndex: "timestamp",
      key: "timestamp",
      width: 180,
      render: (timestamp: string) => (
        <div className="flex flex-col">
          <Text className="text-bud-text-primary text-sm">
            {dayjs(timestamp).format("HH:mm:ss")}
          </Text>
          <Text className="text-bud-text-disabled text-xs">
            {dayjs(timestamp).format("MMM DD, YYYY")}
          </Text>
        </div>
      ),
    },
    // {
    //   title: "User",
    //   dataIndex: "user_name",
    //   key: "user_name",
    //   width: 200,
    //   render: (userName: string) => (
    //     <div className="flex items-center gap-2">
    //       <UserOutlined className="text-bud-text-disabled" />
    //       <Text className="text-bud-text-primary text-sm">{userName}</Text>
    //     </div>
    //   ),
    // },
    {
      title: "Action",
      dataIndex: "action",
      key: "action",
      width: 150,
      render: (action: AuditAction, record: AuditLog) => {
        const display = getActionDisplay(action);
        return (
          <div className="flex items-center">
            <Tags
              // icon={display.icon}
              color={record.status === "failed" ? "error" : display.color}
              name={display.label}
            />
          </div>
        );
      },
    },
    {
      title: "Resource",
      key: "resource",
      width: 250,
      render: (_, record: AuditLog) => (
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            {/* {getResourceIcon(record.resource_type)} */}
            <Text className="text-bud-text-disabled text-xs">
              {record.resource_type.replace("_", " ").toUpperCase()} -
            </Text>
            <Text className="text-bud-text-primary text-sm font-medium">
              {record.resource_name}
            </Text>
          </div>
        </div>
      ),
    },
    // {
    //   title: "Project",
    //   dataIndex: "project_name",
    //   key: "project_name",
    //   width: 180,
    //   render: (projectName?: string) =>
    //     projectName ? (
    //       <div className="flex items-center gap-2">
    //         <Icon icon="ph:folder" className="text-bud-text-disabled" />
    //         <Text className="text-bud-text-primary text-sm">{projectName}</Text>
    //       </div>
    //     ) : (
    //       <Text className="text-bud-text-disabled text-sm">—</Text>
    //     ),
    // },
    {
      title: "IP Address",
      dataIndex: "ip_address",
      key: "ip_address",
      width: 140,
      render: (ip?: string) => (
        <Text className="text-bud-text-muted text-xs font-mono">
          {ip || "—"}
        </Text>
      ),
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      width: 100,
      render: (status: string) => (
        <div className="flex items-center">
          <Tags
            color={status === "success" ? "#3EC564" : "#EC7575"}
            name={status?.charAt(0).toUpperCase() + status?.slice(1)}
          />
        </div>
      ),
    },
  ];

  const handlePageChange = (currentPage: any, pageSize: any) => {
    setCurrentPage(currentPage);
    setPageSize(pageSize);
  };

  // Export to CSV
  const exportToCSV = () => {
    const csvContent = [
      [
        "Timestamp",
        "User",
        "Action",
        "Resource Type",
        "Resource Name",
        // "Resource ID",
        // "Project",
        "IP Address",
        "Status",
      ],
      ...filteredLogs.map((log) => [
        dayjs(log.timestamp).format("YYYY-MM-DD HH:mm:ss"),
        log.user_name,
        getActionDisplay(log.action).label,
        log.resource_type,
        log.resource_name,
        // log.resource_id,
        // log.project_name || "",
        log.ip_address || "",
        log.status,
      ]),
    ]
      .map((row) => row.join(","))
      .join("\n");

    const blob = new Blob([csvContent], { type: "text/csv" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `audit_logs_${dayjs().format("YYYY-MM-DD")}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  // Clear all filters
  const clearFilters = () => {
    setSelectedAction(undefined);
    setSelectedResource(undefined);
    setDateRange(null);
    setSearchText("");
  };

  const hasActiveFilters =
    selectedAction || selectedResource || dateRange || searchText;

  useEffect(() => {
    getAuditList();
    getAuditSummary();
  }, [selectedAction, selectedResource, dateRange, currentPage, pageSize]);

  useEffect(() => {
    const timer = setTimeout(() => {
      getAuditList();
      getAuditSummary();
    }, 500);
    return () => clearTimeout(timer);
  }, [searchText]);

  return (
    <DashboardLayout>
      <style
        dangerouslySetInnerHTML={{
          __html: `
        /* Theme-aware pagination styling for Audit page */
        .CommonCustomPagination .ant-pagination {
          color: var(--text-primary) !important;
        }

        /* Pagination items */
        .CommonCustomPagination .ant-pagination-item a {
          color: var(--text-primary) !important;
        }
        .CommonCustomPagination .ant-pagination-item-active {
          background-color: var(--color-purple) !important;
          border-color: var(--color-purple) !important;
        }
        .CommonCustomPagination .ant-pagination-item-active a {
          color: #ffffff !important;
        }

        /* Previous/Next buttons */
        .CommonCustomPagination .ant-pagination-prev .ant-pagination-item-link,
        .CommonCustomPagination .ant-pagination-next .ant-pagination-item-link {
          color: var(--text-primary) !important;
        }

        /* Size changer and options */
        .CommonCustomPagination .ant-pagination-options {
          color: var(--text-primary) !important;
        }
        .CommonCustomPagination .ant-pagination-options-size-changer {
          color: var(--text-primary) !important;
        }
        .CommonCustomPagination .ant-pagination-options-size-changer .ant-select {
          color: var(--text-primary) !important;
        }
        .CommonCustomPagination .ant-select-selector {
          background-color: var(--bg-tertiary) !important;
          border-color: var(--border-secondary) !important;
          color: var(--text-primary) !important;
        }
        .CommonCustomPagination .ant-select-selection-item {
          color: var(--text-primary) !important;
        }
        .CommonCustomPagination .ant-select-arrow {
          color: var(--text-primary) !important;
        }

        /* Dropdown menu */
        .ant-select-dropdown {
          background-color: var(--bg-tertiary) !important;
        }
        .ant-select-item {
          color: var(--text-primary) !important;
        }
        .ant-select-item-option-selected {
          background-color: var(--bg-hover) !important;
        }
        .ant-select-item-option-active {
          background-color: var(--bg-hover) !important;
        }

        /* Jump input */
        .CommonCustomPagination .ant-pagination-options-quick-jumper input {
          background-color: var(--bg-tertiary) !important;
          border-color: var(--border-secondary) !important;
          color: var(--text-primary) !important;
        }

        /* Light theme specific overrides */
        [data-theme="light"] .CommonCustomPagination .ant-pagination-item a {
          color: #1a1a1a !important;
        }
        [data-theme="light"] .CommonCustomPagination .ant-pagination-prev .ant-pagination-item-link,
        [data-theme="light"] .CommonCustomPagination .ant-pagination-next .ant-pagination-item-link {
          color: #1a1a1a !important;
        }
        [data-theme="light"] .CommonCustomPagination .ant-pagination-options {
          color: #1a1a1a !important;
        }
        [data-theme="light"] .CommonCustomPagination .ant-pagination-options-size-changer {
          color: #1a1a1a !important;
        }
        [data-theme="light"] .CommonCustomPagination .ant-select-selector {
          background-color: #fafafa !important;
          border-color: #d0d0d0 !important;
          color: #1a1a1a !important;
        }
        [data-theme="light"] .CommonCustomPagination .ant-select-selection-item {
          color: #1a1a1a !important;
        }
        [data-theme="light"] .CommonCustomPagination .ant-select-arrow {
          color: #1a1a1a !important;
        }
        [data-theme="light"] .ant-select-dropdown {
          background-color: #fafafa !important;
        }
        [data-theme="light"] .ant-select-item {
          color: #1a1a1a !important;
        }
        [data-theme="light"] .ant-select-item-option-selected {
          background-color: #f0f0f0 !important;
        }
        [data-theme="light"] .ant-select-item-option-active {
          background-color: #f0f0f0 !important;
        }

        /* Dark theme specific overrides */
        [data-theme="dark"] .CommonCustomPagination .ant-pagination-item a {
          color: #ffffff !important;
        }
        [data-theme="dark"] .CommonCustomPagination .ant-pagination-prev .ant-pagination-item-link,
        [data-theme="dark"] .CommonCustomPagination .ant-pagination-next .ant-pagination-item-link {
          color: #ffffff !important;
        }
        [data-theme="dark"] .CommonCustomPagination .ant-pagination-options {
          color: #ffffff !important;
        }
        [data-theme="dark"] .CommonCustomPagination .ant-pagination-options-size-changer {
          color: #ffffff !important;
        }
        [data-theme="dark"] .CommonCustomPagination .ant-select-selector {
          background-color: #1f1f1f !important;
          border-color: #2f2f2f !important;
          color: #ffffff !important;
        }
        [data-theme="dark"] .CommonCustomPagination .ant-select-selection-item {
          color: #ffffff !important;
        }
        [data-theme="dark"] .CommonCustomPagination .ant-select-arrow {
          color: #ffffff !important;
        }
        [data-theme="dark"] .ant-select-dropdown {
          background-color: #1f1f1f !important;
        }
        [data-theme="dark"] .ant-select-item {
          color: #ffffff !important;
        }
        [data-theme="dark"] .ant-select-item-option-selected {
          background-color: #2f2f2f !important;
        }
        [data-theme="dark"] .ant-select-item-option-active {
          background-color: #2f2f2f !important;
        }

        /* Disabled states */
        .CommonCustomPagination .ant-pagination-disabled .ant-pagination-item-link {
          color: var(--text-disabled) !important;
        }
      `,
        }}
      />
      <div className="p-8 bg-bud-bg-primary min-h-full">
        {/* Header */}
        <div className="mb-6">
          <Title level={2} className="!text-bud-text-primary !mb-2">
            Monitoring & Audit
          </Title>
          <Text className="text-bud-text-muted text-sm">
            Track and review all system activities, user actions, and resource
            changes
          </Text>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          <Card className="bg-bud-bg-secondary border-bud-border relative">
            {isStatsLoading ? (
              <LoadingWrapper />
            ) : (
              <div className="flex items-center justify-between">
                <div>
                  <Text className="text-bud-text-disabled text-xs block mb-1">
                    Today&apos;s Events
                  </Text>
                  <Text className="text-bud-text-primary text-2xl font-semibold">
                    {statistics.totalEvents}
                  </Text>
                </div>
                <CalendarOutlined className="text-2xl text-bud-purple" />
              </div>
            )}
          </Card>

          <Card className="bg-bud-bg-secondary border-bud-border relative">
            {isStatsLoading ? (
              <LoadingWrapper />
            ) : (
              <div className="flex items-center justify-between">
                <div>
                  <Text className="text-bud-text-disabled text-xs block mb-1">
                    Failed Actions
                  </Text>
                  <Text className="text-bud-text-primary text-2xl font-semibold">
                    {statistics.failedActions}
                  </Text>
                </div>
                <Icon
                  icon="ph:warning-circle"
                  className="text-2xl text-red-500"
                />
              </div>
            )}
          </Card>

          <Card className="bg-bud-bg-secondary border-bud-border hidden relative">
            {isStatsLoading ? (
              <LoadingWrapper />
            ) : (
              <div className="flex items-center justify-between">
                <div>
                  <Text className="text-bud-text-disabled text-xs block mb-1">
                    Active Users
                  </Text>
                  <Text className="text-bud-text-primary text-2xl font-semibold">
                    {statistics.resourcesModified}
                  </Text>
                </div>
                <UserOutlined className="text-2xl text-blue-500" />
              </div>
            )}
          </Card>

          <Card className="bg-bud-bg-secondary border-bud-border relative">
            {isStatsLoading ? (
              <LoadingWrapper />
            ) : (
              <div className="flex items-center justify-between">
                <div>
                  <Text className="text-bud-text-disabled text-xs block mb-1">
                    Resources Modified
                  </Text>
                  <Text className="text-bud-text-primary text-2xl font-semibold">
                    {
                      filteredLogs.filter((log) =>
                        [
                          AuditAction.CREATE,
                          AuditAction.UPDATE,
                          AuditAction.DELETE,
                        ].includes(log.action),
                      ).length
                    }
                  </Text>
                </div>
                <Icon icon="ph:database" className="text-2xl text-green-500" />
              </div>
            )}
          </Card>
        </div>

        {/* Filters */}
        <Card className="bg-bud-bg-secondary border-bud-border mb-6 relative">
          {isStatsLoading ? (
            <LoadingWrapper />
          ) : (
            <div className="flex items-center gap-4">
              <Input
                placeholder="Search by resources"
                prefix={<SearchOutlined className="text-bud-text-disabled" />}
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                className="w-80 bg-bud-bg-tertiary border-bud-border-secondary text-bud-text-primary placeholder:text-bud-text-disabled"
                allowClear
              />
              <ConfigProvider theme={themeConfig}>
                <Select
                  placeholder="Filter by action"
                  value={selectedAction}
                  onChange={setSelectedAction}
                  className="w-48"
                  allowClear
                  options={Object.values(AuditAction)
                    .filter(
                      (action) =>
                        action !== AuditAction.REGENERATE &&
                        action !== AuditAction.LOGOUT,
                    )
                    .map((action) => ({
                      label: getActionDisplay(action).label,
                      value:
                        action === AuditAction.ACCESS
                          ? "access_granted"
                          : action === AuditAction.EXPORT
                            ? "data_export"
                            : action,
                    }))}
                />
              </ConfigProvider>
              <ConfigProvider theme={themeConfig}>
                <Select
                  placeholder="Filter by resource"
                  value={selectedResource}
                  onChange={setSelectedResource}
                  className="w-48"
                  allowClear
                  options={Object.values(ResourceType).map((type) => ({
                    label: type.replace("_", " ").toUpperCase(),
                    value: type,
                  }))}
                />
              </ConfigProvider>

              <RangePicker
                value={dateRange}
                onChange={(dates) => setDateRange(dates)}
                className="bg-bud-bg-tertiary border-bud-border-secondary"
                format="YYYY-MM-DD"
              />

              {hasActiveFilters && (
                <Button
                  onClick={clearFilters}
                  className="text-bud-text-muted border-bud-border"
                >
                  Clear Filters
                </Button>
              )}

              <div className="ml-auto">
                <Button
                  icon={<DownloadOutlined />}
                  onClick={exportToCSV}
                  className="bg-bud-purple text-white border-bud-purple hover:bg-bud-purple-hover"
                >
                  Export CSV
                </Button>
              </div>
            </div>
          )}
        </Card>

        {/* Audit Table */}
        <div className="bg-bud-bg-secondary border border-bud-border rounded-[12px] overflow-hidden mb-[2rem]">
          <div className="space-y-6">
            {/* {Object.entries(groupedLogs).map(([group, logs]) => {
              if (logs.length === 0) return null;

              const groupLabels = {
                today: "Today",
                yesterday: "Yesterday",
                thisWeek: "This Week",
                older: "Older",
              };

              return ( */}
            {loading ? (
              <div className="p-8">
                <Skeleton active paragraph={{ rows: 8 }} />
              </div>
            ) : (
              <div className="pb-6">
                <div className="flex items-center gap-2 mb-3 hidden">
                  <ClockCircleOutlined className="text-bud-text-disabled" />
                  {dayFilter.map((item: any) => (
                    <Tag
                      key={item.value}
                      onClick={() => setCurrentDayFilter(item.value)}
                      color={item.active ? "green-inverse" : "red"}
                      className="flex items-center gap-1 w-fit"
                    >
                      {item.label}
                    </Tag>
                  ))}
                  {/* <Text className="text-bud-text-primary font-medium">
                      {groupLabels[group as keyof typeof groupLabels]}
                    </Text>
                    <Badge count={logs.length} className="bg-bud-bg-tertiary" /> */}
                </div>

                <Table
                  columns={columns}
                  dataSource={auditLogs}
                  rowKey="id"
                  pagination={false}
                  size="small"
                  className={styles.auditTable}
                  rowSelection={{
                    selectedRowKeys,
                    onChange: setSelectedRowKeys,
                  }}
                  rowClassName={(record) =>
                    record.status === "failed" ? "bg-red-500/5" : ""
                  }
                />
                {/* Pagination */}
                <div className="flex justify-end mt-4 mr-4 CommonCustomPagination">
                  <Pagination
                    className="small-pagination"
                    current={currentPage}
                    pageSize={pageSize}
                    total={totalNumber}
                    onChange={handlePageChange}
                    showSizeChanger
                    pageSizeOptions={["5", "10", "20", "50"]}
                  />
                </div>
              </div>
            )}

            {/* {filteredLogs.length === 0 && (
              <Empty
                description={
                  <Text className="text-bud-text-disabled">
                    No audit logs found matching your filters
                  </Text>
                }
              />
            )} */}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

export const LoadingWrapper = () => {
  return <div className={styles.loadingWrapper}>
    <div className={styles.loadingContainer}>
      <motion.div
        className={styles.loadingBar}
        initial={{ width: "0%" }}
        animate={{ width: "100%" }}
        transition={{
          duration: 1.5,
          ease: "easeInOut",
          repeat: Infinity,
        }}
      />
    </div>
  </div>
}
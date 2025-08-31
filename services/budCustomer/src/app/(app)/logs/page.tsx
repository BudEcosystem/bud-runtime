"use client";

import React, { useEffect, useState } from 'react';
import { Tabs, Button, Table, Tag, Tooltip, Typography, message, Card, Row, Col, Statistic, Select, DatePicker, Space, Segmented, Image, ConfigProvider } from 'antd';
import { DownloadOutlined, ReloadOutlined, ArrowUpOutlined, ArrowDownOutlined, BarChartOutlined, LineChartOutlined, PieChartOutlined, GlobalOutlined, FilterOutlined, UserOutlined, AppstoreOutlined, RocketOutlined, CodeOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { format } from 'date-fns';
import { formatTimestamp } from '@/utils/formatDateNew';
import { useRouter } from 'next/navigation';
import { useInferences, InferenceListItem } from '@/stores/useInferences';
import InferenceFilters from '@/components/inferences/InferenceFilters';
import { Text_12_400_EEEEEE, Text_16_600_FFFFFF, Text_14_600_EEEEEE, Text_14_600_B3B3B3, Text_12_400_808080 } from '@/components/ui/text';
import SearchHeaderInput from 'src/flows/components/SearchHeaderInput';
import NoDataFount from '@/components/ui/noDataFount';
import { PrimaryButton, SecondaryButton } from '@/components/ui/bud/form/Buttons';
import ProjectTags from 'src/flows/components/ProjectTags';
import { SortIcon } from '@/components/ui/bud/table/SortIcon';
import { formatDate } from 'src/utils/formatDate';
import { useLoaderOnLoading } from 'src/hooks/useLoaderOnLoading';
import DashboardLayout from "@/components/layout/DashboardLayout";
import PageHeader from '@/components/ui/pageHeader';
import { useTheme } from '@/context/themeContext';
import { ClientTimestamp } from '@/components/ui/ClientTimestamp';
import MetricsTab from './MetricsTab';
import RulesTab from './RulesTab';
import type { RangePickerProps } from 'antd/es/date-picker';
import dayjs from 'dayjs';

const { Text } = Typography;
const { RangePicker } = DatePicker;

export default function ObservabilityPage() {
  const router = useRouter();
  const { effectiveTheme } = useTheme();
  const [searchValue, setSearchValue] = useState('');
  const [activeTab, setActiveTab] = useState('metrics');
  // Initialize with consistent rounded times
  const [timeRange, setTimeRange] = useState<[dayjs.Dayjs, dayjs.Dayjs]>([
    dayjs().startOf('day').subtract(7, 'days'),
    dayjs().startOf('hour')
  ]);
  const [viewBy, setViewBy] = useState<'model' | 'deployment' | 'project' | 'user'>('model');
  const [selectedPreset, setSelectedPreset] = useState<string>('Last 7 days');

  const {
    inferences,
    pagination,
    isLoading,
    fetchInferences,
    setPagination,
    exportInferences,
    setFilters,
    filters,
  } = useInferences();

  // Show global loader for both tabs
  useLoaderOnLoading(isLoading);

  // Sync filters with timeRange on mount and fetch inferences
  useEffect(() => {
    // Create initial filters based on timeRange
    const initialFilters = {
      from_date: timeRange[0].toISOString(),
      to_date: timeRange[1].toISOString(),
      sort_by: 'timestamp' as const,
      sort_order: 'desc' as const
    };
    // Set filters in store
    setFilters(initialFilters);
    // Fetch with the same filters to ensure consistency
    fetchInferences(undefined, initialFilters);
  }, []); // Run only on mount

  // Handle search with debounce
  useEffect(() => {
    const timer = setTimeout(() => {
      fetchInferences(); // Fetch all with current filters
    }, 500);
    return () => clearTimeout(timer);
  }, [searchValue, fetchInferences]);

  // Copy inference ID to clipboard
  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    message.success('Copied to clipboard');
  };

  // Handle time range change
  const handleTimeRangeChange: RangePickerProps['onChange'] = (dates) => {
    if (dates && dates[0] && dates[1]) {
      setTimeRange([dates[0], dates[1]]);
      setSelectedPreset(''); // Clear preset selection when using date picker
      // Create the new filters
      const newFilters = {
        from_date: dates[0].toISOString(),
        to_date: dates[1].toISOString(),
        sort_by: 'timestamp' as const,
        sort_order: 'desc' as const
      };
      // Update filters in store
      setFilters(newFilters);
      // Fetch with the same filters to ensure consistency
      fetchInferences(undefined, newFilters);
    }
  };

  // Predefined time ranges - using function to return value for TypeScript compatibility
  // Round times to consistent boundaries to prevent data shifting
  const timeRangePresets = [
    {
      label: 'Last 1 hour',
      value: () => {
        const now = dayjs(); // Use exact current time
        return [now.subtract(1, 'hours'), now] as [dayjs.Dayjs, dayjs.Dayjs];
      }
    },
    {
      label: 'Last 6 hours',
      value: () => {
        const now = dayjs(); // Use exact current time
        return [now.subtract(6, 'hours'), now] as [dayjs.Dayjs, dayjs.Dayjs];
      }
    },
    {
      label: 'Last 24 hours',
      value: () => {
        const now = dayjs(); // Use exact current time
        return [now.subtract(24, 'hours'), now] as [dayjs.Dayjs, dayjs.Dayjs];
      }
    },
    {
      label: 'Last 7 days',
      value: () => {
        const now = dayjs().startOf('day'); // Round to start of current day
        return [now.subtract(7, 'days'), now] as [dayjs.Dayjs, dayjs.Dayjs];
      }
    },
    {
      label: 'Last 30 days',
      value: () => {
        const now = dayjs().startOf('day'); // Round to start of current day
        return [now.subtract(30, 'days'), now] as [dayjs.Dayjs, dayjs.Dayjs];
      }
    },
    {
      label: 'Last 3 months',
      value: () => {
        const now = dayjs().startOf('day'); // Round to start of current day
        return [now.subtract(3, 'months'), now] as [dayjs.Dayjs, dayjs.Dayjs];
      }
    },
  ];

  // View by options with appropriate icons
  const viewByOptions = [
    {
      label: 'Model',
      value: 'model',
      icon: (active: boolean) => (
        <Image
          preview={false}
          src={active ? '/images/icons/modelRepoWhite.png' : '/images/icons/modelRepo.png'}
          style={{ width: "14px", height: "14px" }}
          alt="Model"
        />
      )
    },
    // {
    //   label: 'Deployment',
    //   value: 'deployment',
    //   icon: (active: boolean) => (
    //     <Image
    //       preview={false}
    //       src={active ? '/images/icons/clustersWhite.png' : '/images/icons/cluster.png'}
    //       style={{ width: "14px", height: "14px" }}
    //       alt="Deployment"
    //     />
    //   )
    // },
    {
      label: 'Project',
      value: 'project',
      icon: (active: boolean) => (
        <Image
          preview={false}
          src={active ? '/images/icons/projectIconWhite.png' : '/images/icons/projectIcon.png'}
          style={{ width: "14px", height: "14px" }}
          alt="Project"
        />
      )
    },
    // {
    //   label: 'User',
    //   value: 'user',
    //   icon: (active: boolean) => (
    //     <Image
    //       preview={false}
    //       src={active ? '/images/icons/userWhite.png' : '/images/icons/user.png'}
    //       style={{ width: "14px", height: "14px" }}
    //       alt="User"
    //     />
    //   )
    // },
  ];

  // Table columns definition
  const columns: ColumnsType<InferenceListItem> = [
    {
      title: 'Timestamp',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 180,
      render: (timestamp: string) => (
        <Text_12_400_EEEEEE className="!text-[var(--text-primary)]"><ClientTimestamp timestamp={timestamp} /></Text_12_400_EEEEEE>
      ),
      sorter: true,
      sortIcon: SortIcon,
    },
    {
      title: 'Project',
      dataIndex: 'project_name',
      key: 'project_name',
      width: 150,
      render: (project_name: string) => (
        <Tooltip title={project_name || 'N/A'}>
          <Text_12_400_EEEEEE className="truncate max-w-[130px] !text-[var(--text-primary)]">
            {project_name || '-'}
          </Text_12_400_EEEEEE>
        </Tooltip>
      ),
    },
    {
      title: 'Deployment',
      dataIndex: 'endpoint_name',
      key: 'endpoint_name',
      width: 200,
      render: (endpoint_name: string) => (
        <Tooltip title={endpoint_name || 'N/A'}>
          <Text_12_400_EEEEEE className="truncate max-w-[180px] !text-[var(--text-primary)]">
            {endpoint_name || '-'}
          </Text_12_400_EEEEEE>
        </Tooltip>
      ),
    },
    {
      title: 'Prompt Preview',
      dataIndex: 'prompt_preview',
      key: 'prompt_preview',
      width: 350,
      render: (prompt: string) => (
        <Tooltip title={prompt}>
          <Text_12_400_EEEEEE className="truncate max-w-[330px] !text-[var(--text-primary)]">
            {prompt}
          </Text_12_400_EEEEEE>
        </Tooltip>
      ),
    },
    {
      title: 'Response Time',
      dataIndex: 'response_time_ms',
      key: 'response_time_ms',
      width: 120,
      render: (response_time_ms: number) => (
        <Text_12_400_EEEEEE className="!text-[var(--text-primary)]">
          {response_time_ms ? `${response_time_ms.toLocaleString()} ms` : '-'}
        </Text_12_400_EEEEEE>
      ),
      sorter: true,
      sortIcon: SortIcon,
    },
    {
      title: 'Tokens',
      key: 'tokens',
      width: 120,
      render: (_, record) => (
        <Text_12_400_EEEEEE className="!text-[var(--text-primary)]">
          {record.input_tokens + record.output_tokens || '-'}
        </Text_12_400_EEEEEE>
      ),
    },
    {
      title: 'Status',
      key: 'status',
      width: 100,
      render: (_, record) => (
        <ProjectTags
          name={record.is_success ? 'Success' : 'Failed'}
          color={record.is_success ? '#22c55e' : '#ef4444'}
          textClass="text-[.75rem]"
        />
      ),
    },
  ];

  // Handle table change (pagination, sorting)
  const handleTableChange = (newPagination: any, _filters: any, sorter: any) => {
    // Handle sorting
    if (sorter.field) {
      const sortMap: Record<string, string> = {
        timestamp: 'timestamp',
        response_time_ms: 'latency',
      };

      const sortBy = sortMap[sorter.field] || 'timestamp';
      const sortOrder = sorter.order === 'ascend' ? 'asc' : 'desc';

      setFilters({
        sort_by: sortBy as any,
        sort_order: sortOrder as any,
      });
      fetchInferences(); // Fetch all with new sorting
    }
  };

  // Export menu items
  const exportMenu = [
    {
      key: 'csv',
      label: 'Export as CSV',
      onClick: () => exportInferences('csv'),
    },
    {
      key: 'json',
      label: 'Export as JSON',
      onClick: () => exportInferences('json'),
    },
  ];

  return (
    <DashboardLayout>
      <style dangerouslySetInnerHTML={{ __html: `
        /* Override Ant Design hardcoded colors for theme support */
        .ant-card.bg-\\[\\#101010\\] {
          background-color: var(--bg-secondary) !important;
        }
        .ant-card.border-\\[\\#1F1F1F\\] {
          border-color: var(--border-color) !important;
        }
        /* Specific fix for the Requests tab card */
        .ant-card-small.bg-\\[\\#101010\\] {
          background-color: var(--bg-secondary) !important;
        }
        [data-theme="light"] .ant-card-small.bg-\\[\\#101010\\] {
          background-color: #f5f5f5 !important;
        }
        [data-theme="dark"] .ant-card-small.bg-\\[\\#101010\\] {
          background-color: #161616 !important;
        }
        /* Fallback for any ant-card with dark backgrounds */
        .ant-card[class*="bg-\\[\\#101010\\]"],
        .ant-card[class*="bg-\\[\\#1A1A1A\\]"],
        .ant-card[class*="bg-\\[\\#0A0A0A\\]"] {
          background-color: var(--bg-secondary) !important;
        }
        [data-theme="light"] .ant-card[class*="bg-\\[\\#101010\\]"],
        [data-theme="light"] .ant-card[class*="bg-\\[\\#1A1A1A\\]"],
        [data-theme="light"] .ant-card[class*="bg-\\[\\#0A0A0A\\]"] {
          background-color: #f5f5f5 !important;
        }
        .ant-table-wrapper .ant-table {
          background: var(--bg-card) !important;
        }
        .ant-table-wrapper .ant-table-thead > tr > th {
          background: var(--bg-tertiary) !important;
          color: var(--text-primary) !important;
          border-bottom: 1px solid var(--border-color) !important;
        }
        .ant-table-wrapper .ant-table-tbody > tr > td {
          border-bottom: 1px solid var(--border-color) !important;
          background: var(--bg-card) !important;
        }
        .ant-table-wrapper .ant-table-tbody > tr:hover > td {
          background: var(--bg-hover) !important;
        }
        .ant-table-title {
          background: var(--bg-secondary) !important;
          border-bottom: 1px solid var(--border-color) !important;
        }
        /* Light theme specific table styling */
        [data-theme="light"] .ant-table-title {
          background: #f5f5f5 !important;
        }
        [data-theme="light"] .ant-table-wrapper .ant-table-thead > tr > th {
          background: #fafafa !important;
        }
        /* Fix button colors */
        .ant-btn {
          color: var(--text-primary) !important;
          border-color: var(--border-color) !important;
        }
        .ant-btn:not(.ant-btn-primary):not(.ant-btn-dangerous) {
          background: var(--bg-secondary) !important;
        }
        .ant-btn:hover:not(.ant-btn-primary):not(.ant-btn-dangerous) {
          background: var(--bg-hover) !important;
          border-color: var(--border-secondary) !important;
        }
        /* Fix Primary Button */
        button[class*="bg-\\[\\#1E0C34\\]"] {
          background: var(--color-purple) !important;
          opacity: 0.9;
        }
        button[class*="bg-\\[\\#1E0C34\\]"]:hover {
          background: var(--color-purple-hover) !important;
          opacity: 1;
        }
        /* Button text - dark theme */
        [data-theme="dark"] button[class*="bg-\\[\\#1E0C34\\]"] div,
        [data-theme="dark"] button[class*="bg-\\[\\#1E0C34\\]"] span,
        [data-theme="dark"] button[class*="bg-\\[\\#1E0C34\\]"] .anticon {
          color: white !important;
        }
        /* Button text - light theme */
        [data-theme="light"] button[class*="bg-\\[\\#1E0C34\\]"] div,
        [data-theme="light"] button[class*="bg-\\[\\#1E0C34\\]"] span,
        [data-theme="light"] button[class*="bg-\\[\\#1E0C34\\]"] .anticon {
          color: #000000 !important;
        }
        /* Specific fix for refresh and export buttons */
        [data-theme="dark"] .ant-btn span.ml-2 {
          color: white !important;
          margin-left: 0.5rem !important;
        }
        [data-theme="light"] .ant-btn span.ml-2 {
          color: #000000 !important;
          margin-left: 0.5rem !important;
        }
        [data-theme="dark"] .ant-btn[class*="bg-\\[\\#1E0C34\\]"] * {
          color: white !important;
        }
        [data-theme="light"] .ant-btn[class*="bg-\\[\\#1E0C34\\]"] * {
          color: #000000 !important;
        }
        /* Fix Secondary Button */
        button[class*="bg-\\[\\#1F1F1F\\]"] {
          background: var(--bg-secondary) !important;
          border-color: var(--border-secondary) !important;
        }
        button[class*="bg-\\[\\#1F1F1F\\]"]:hover {
          background: var(--bg-hover) !important;
          border-color: var(--border-color) !important;
        }
        [data-theme="dark"] button[class*="bg-\\[\\#1F1F1F\\]"] span,
        [data-theme="dark"] button[class*="bg-\\[\\#1F1F1F\\]"] .anticon {
          color: #EEEEEE !important;
        }
        [data-theme="light"] button[class*="bg-\\[\\#1F1F1F\\]"] span,
        [data-theme="light"] button[class*="bg-\\[\\#1F1F1F\\]"] .anticon {
          color: #000000 !important;
        }
        /* Ensure all Ant Design icons in buttons are visible */
        .ant-btn .anticon {
          color: inherit !important;
        }
        /* Fix segmented control */
        .antSegmented {
          background: var(--bg-secondary) !important;
        }
        .antSegmented .ant-segmented-item {
          color: var(--text-muted) !important;
        }
        .antSegmented .ant-segmented-item-selected {
          background: var(--bg-hover) !important;
          color: var(--text-primary) !important;
        }
        /* Fix date picker */
        .ant-picker {
          background: var(--bg-tertiary) !important;
          border-color: var(--border-secondary) !important;
        }
        .ant-picker-input > input {
          color: var(--text-primary) !important;
        }
        .ant-picker-suffix {
          color: var(--text-muted) !important;
        }
        /* Fix Input fields */
        .ant-input {
          background: var(--bg-tertiary) !important;
          border-color: var(--border-secondary) !important;
          color: var(--text-primary) !important;
        }
        .ant-input::placeholder {
          color: var(--text-disabled) !important;
        }
        .ant-input:hover {
          border-color: var(--border-color) !important;
        }
        .ant-input:focus {
          border-color: var(--color-purple) !important;
          box-shadow: 0 0 0 2px rgba(150, 92, 222, 0.2) !important;
        }
        .ant-input-prefix {
          color: var(--text-muted) !important;
        }
        /* Fix tabs */
        .ant-tabs-tab {
          color: var(--text-muted) !important;
        }
        .ant-tabs-tab.ant-tabs-tab-active {
          color: var(--text-primary) !important;
        }
        .ant-tabs-ink-bar {
          background: var(--color-purple) !important;
        }
        /* Ensure key text elements are dark black in light theme */
        [data-theme="light"] .logs-page h1,
        [data-theme="light"] .logs-page h2,
        [data-theme="light"] .logs-page h3,
        [data-theme="light"] .logs-page .ant-table-tbody > tr > td,
        [data-theme="light"] .logs-page .ant-table-thead > tr > th,
        [data-theme="light"] .logs-page .ant-table-title,
        [data-theme="light"] .logs-page [class*="Text_"] {
          color: #000000 !important;
        }
        [data-theme="light"] .logs-page .ant-tabs-tab {
          color: #666666 !important;
        }
        [data-theme="light"] .logs-page .ant-tabs-tab.ant-tabs-tab-active {
          color: #000000 !important;
        }
        /* Fix input placeholder in light theme */
        [data-theme="light"] .logs-page .ant-input::placeholder {
          color: #999999 !important;
        }
        /* Filter section background to match Inference Requests section */
        .filter-section-bg {
          background: var(--bg-secondary) !important;
          border: 1px solid var(--border-color) !important;
        }
        [data-theme="light"] .filter-section-bg {
          background: #f5f5f5 !important;
          border: 1px solid #e0e0e0 !important;
        }
        [data-theme="dark"] .filter-section-bg {
          background: #161616 !important;
          border: 1px solid #1f1f1f !important;
        }
        /* Comprehensive fix for InferenceFilters component hardcoded colors */
        [data-theme="light"] .filter-section-bg .ant-card {
          background: #ffffff !important;
          border-color: #d9d9d9 !important;
        }
        [data-theme="light"] .filter-section-bg .ant-card-head {
          background: #fafafa !important;
          border-bottom: 1px solid #d9d9d9 !important;
        }
        [data-theme="light"] .filter-section-bg .ant-card-body {
          background: #ffffff !important;
        }
        [data-theme="light"] .filter-section-bg [class*="bg-\\[\\#1A1A1A\\]"],
        [data-theme="light"] .filter-section-bg [class*="bg-\\[\\#101010\\]"],
        [data-theme="light"] .filter-section-bg [class*="bg-\\[\\#1F1F1F\\]"],
        [data-theme="light"] .filter-section-bg [class*="bg-\\[\\#2F2F2F\\]"] {
          background: #ffffff !important;
        }
        [data-theme="light"] .filter-section-bg [class*="border-\\[\\#1F1F1F\\]"],
        [data-theme="light"] .filter-section-bg [class*="border-\\[\\#2F2F2F\\]"],
        [data-theme="light"] .filter-section-bg [class*="border-\\[\\#3F3F3F\\]"] {
          border-color: #d9d9d9 !important;
        }
        [data-theme="light"] .filter-section-bg [class*="text-\\[\\#EEEEEE\\]"],
        [data-theme="light"] .filter-section-bg [class*="text-\\[\\#B3B3B3\\]"] {
          color: #000000 !important;
        }
        /* Make ALL text dark black in light theme filter section */
        [data-theme="light"] .filter-section-bg * {
          color: #000000 !important;
        }
        [data-theme="light"] .filter-section-bg .ant-card-head-title {
          color: #000000 !important;
        }
        [data-theme="light"] .filter-section-bg .ant-card-head-title span {
          color: #000000 !important;
        }
        [data-theme="light"] .filter-section-bg input {
          color: #000000 !important;
        }
        [data-theme="light"] .filter-section-bg input::placeholder {
          color: #666666 !important;
        }
        /* Fix all input elements in filter section */
        [data-theme="light"] .filter-section-bg .ant-input,
        [data-theme="light"] .filter-section-bg .ant-select-selector,
        [data-theme="light"] .filter-section-bg .ant-picker,
        [data-theme="light"] .filter-section-bg .ant-input-number,
        [data-theme="light"] .filter-section-bg .ant-switch {
          background: #ffffff !important;
          border-color: #d9d9d9 !important;
          color: #000000 !important;
        }
        [data-theme="light"] .filter-section-bg .ant-input-number-input {
          color: #000000 !important;
        }
        [data-theme="light"] .filter-section-bg .ant-btn {
          background: #ffffff !important;
          border-color: #d9d9d9 !important;
          color: #000000 !important;
        }
        [data-theme="light"] .filter-section-bg .ant-btn:hover {
          background: #f5f5f5 !important;
          border-color: #40a9ff !important;
          color: #000000 !important;
        }
        [data-theme="light"] .filter-section-bg .ant-btn span {
          color: #000000 !important;
        }
        [data-theme="light"] .filter-section-bg .ant-btn:hover span {
          color: #000000 !important;
        }
        /* Fix form labels */
        [data-theme="light"] .filter-section-bg .ant-form-item-label > label {
          color: #000000 !important;
        }
        [data-theme="light"] .filter-section-bg .ant-form-item-label > label > span {
          color: #000000 !important;
        }
        /* Fix select dropdown text */
        [data-theme="light"] .filter-section-bg .ant-select-selection-placeholder {
          color: #999999 !important;
        }
        [data-theme="light"] .filter-section-bg .ant-select-selection-item {
          color: #000000 !important;
        }
        /* Fix picker text */
        [data-theme="light"] .filter-section-bg .ant-picker-input input {
          color: #000000 !important;
        }
        /* Additional text in filter components */
        [data-theme="light"] .filter-section-bg .ant-space-item span {
          color: #000000 !important;
        }
        /* Fix antd icons in filter section */
        [data-theme="light"] .filter-section-bg .anticon {
          color: #666666 !important;
        }
        /* Fix switch component */
        [data-theme="light"] .filter-section-bg .ant-switch {
          background: #ffffff !important;
        }
        [data-theme="light"] .filter-section-bg .ant-switch-checked {
          background: #1890ff !important;
        }
      ` }} />
      <div className="h-full flex flex-col p-8 logs-page">
        <div className="boardPageTop">
          <div className="logs-header-override">
            <PageHeader
              headding="Logs"
            />
          </div>
        </div>
        <style dangerouslySetInnerHTML={{ __html: `
          .logs-header-override .pageHeader h1,
          .logs-header-override .pageHeader h2,
          .logs-header-override .pageHeader h3,
          .logs-header-override .pageHeader div[class*="Heading"],
          .logs-header-override .pageHeader * {
            color: var(--text-primary) !important;
          }
        ` }} />
        <style dangerouslySetInnerHTML={{ __html: `
          .theme-aware-logs *,
          .theme-aware-logs div,
          .theme-aware-logs span,
          .theme-aware-logs p,
          .theme-aware-logs h1,
          .theme-aware-logs h2,
          .theme-aware-logs h3,
          .theme-aware-logs h4,
          .theme-aware-logs h5,
          .theme-aware-logs h6 {
            color: var(--text-primary) !important;
          }

          /* Override specific hardcoded text components */
          .theme-aware-logs [class*="Text_"][class*="_FFFFFF"],
          .theme-aware-logs [class*="Text_"][class*="_EEEEEE"],
          .theme-aware-logs [class*="Heading_"][class*="_FFFFFF"] {
            color: var(--text-primary) !important;
          }

          .theme-aware-logs [class*="Text_"][class*="_B3B3B3"],
          .theme-aware-logs [class*="Text_"][class*="_808080"],
          .theme-aware-logs [class*="Text_"][class*="_757575"] {
            color: var(--text-muted) !important;
          }

          /* Ant Design components */
          .theme-aware-logs .ant-tabs-tab {
            color: var(--text-muted) !important;
          }
          .theme-aware-logs .ant-tabs-tab-active {
            color: var(--text-primary) !important;
          }
          .theme-aware-logs .ant-table {
            color: var(--text-primary) !important;
          }
          .theme-aware-logs .ant-table-thead > tr > th {
            color: var(--text-primary) !important;
          }
          .theme-aware-logs .ant-table-tbody > tr > td {
            color: var(--text-primary) !important;
          }
          .theme-aware-logs .ant-empty-description {
            color: var(--text-muted) !important;
          }
          .theme-aware-logs .ant-segmented-item {
            color: var(--text-muted) !important;
          }
          .theme-aware-logs .ant-segmented-item-selected {
            color: var(--text-primary) !important;
          }

          /* Input components and form elements */
          .theme-aware-logs .ant-input,
          .theme-aware-logs .ant-input:focus,
          .theme-aware-logs .ant-input:hover,
          .theme-aware-logs .ant-input-affix-wrapper,
          .theme-aware-logs .ant-input-affix-wrapper:focus,
          .theme-aware-logs .ant-input-affix-wrapper:hover {
            color: var(--text-primary) !important;
            background-color: var(--bg-tertiary) !important;
            border-color: var(--border-secondary) !important;
          }

          .theme-aware-logs .ant-input::placeholder,
          .theme-aware-logs .ant-input-affix-wrapper input::placeholder {
            color: var(--text-disabled) !important;
          }

          /* Button components */
          .theme-aware-logs .ant-btn,
          .theme-aware-logs .ant-btn span {
            color: var(--text-primary) !important;
          }

          .theme-aware-logs .ant-btn-default {
            background-color: var(--bg-tertiary) !important;
            border-color: var(--border-secondary) !important;
            color: var(--text-primary) !important;
          }

          .theme-aware-logs .ant-btn-default:hover {
            background-color: var(--bg-hover) !important;
            border-color: var(--border-color) !important;
            color: var(--text-primary) !important;
          }

          /* Dropdown and Select components */
          .theme-aware-logs .ant-select,
          .theme-aware-logs .ant-select:hover,
          .theme-aware-logs .ant-select:focus {
            color: var(--text-primary) !important;
          }

          .theme-aware-logs .ant-select-selector {
            background-color: var(--bg-tertiary) !important;
            border-color: var(--border-secondary) !important;
            color: var(--text-primary) !important;
          }

          .theme-aware-logs .ant-select-selection-placeholder {
            color: var(--text-disabled) !important;
          }

          .theme-aware-logs .ant-select-selection-item {
            color: var(--text-primary) !important;
          }

          /* Date picker components */
          .theme-aware-logs .ant-picker,
          .theme-aware-logs .ant-picker:hover,
          .theme-aware-logs .ant-picker:focus {
            background-color: var(--bg-tertiary) !important;
            border-color: var(--border-secondary) !important;
            color: var(--text-primary) !important;
          }

          .theme-aware-logs .ant-picker input {
            color: var(--text-primary) !important;
          }

          .theme-aware-logs .ant-picker-input > input::placeholder {
            color: var(--text-disabled) !important;
          }

          /* Filter components specific */
          .theme-aware-logs .ant-form-item-label > label {
            color: var(--text-primary) !important;
          }

          .theme-aware-logs .ant-checkbox-wrapper {
            color: var(--text-primary) !important;
          }

          .theme-aware-logs .ant-radio-wrapper {
            color: var(--text-primary) !important;
          }

          /* Search header specific */
          .theme-aware-logs .ant-input-search .ant-input {
            color: var(--text-primary) !important;
            background-color: var(--bg-tertiary) !important;
          }

          /* Any remaining text elements */
          .theme-aware-logs label,
          .theme-aware-logs .ant-form-item-label,
          .theme-aware-logs .ant-form-item-control {
            color: var(--text-primary) !important;
          }

          /* SearchHeaderInput component override */
          .theme-aware-logs .ant-input[style*="#1A1A1A"],
          .theme-aware-logs .ant-input[class*="bg-[#1A1A1A]"] {
            background-color: var(--bg-tertiary) !important;
            border-color: var(--border-secondary) !important;
            color: var(--text-primary) !important;
          }

          /* Icon color override */
          .theme-aware-logs .ant-input-prefix,
          .theme-aware-logs .ant-input-prefix * {
            color: var(--text-muted) !important;
          }

          /* Button text specific overrides */
          .theme-aware-logs .ant-btn .ml-2,
          .theme-aware-logs button span {
            color: var(--text-primary) !important;
          }

          /* Ensure all divs and spans in buttons are visible */
          .theme-aware-logs .ant-btn div,
          .theme-aware-logs .ant-btn span,
          .theme-aware-logs button div,
          .theme-aware-logs button span {
            color: inherit !important;
          }

          /* Custom button components override */
          .theme-aware-logs button[class*="bg-[#"],
          .theme-aware-logs .ant-btn[class*="bg-[#"] {
            background-color: var(--bg-tertiary) !important;
            border-color: var(--border-secondary) !important;
            color: var(--text-primary) !important;
          }

          .theme-aware-logs button[class*="bg-[#1E0C34"] {
            background-color: var(--color-purple) !important;
            border-color: var(--color-purple) !important;
            color: white !important;
          }

          /* Override hardcoded text colors in buttons */
          .theme-aware-logs button div[class*="text-[#EEEEEE]"],
          .theme-aware-logs button span[class*="text-[#EEEEEE]"],
          .theme-aware-logs .ant-btn div[class*="text-[#EEEEEE]"],
          .theme-aware-logs .ant-btn span[class*="text-[#EEEEEE]"] {
            color: var(--text-primary) !important;
          }

          /* Force visibility for all interactive elements */
          .theme-aware-logs input,
          .theme-aware-logs textarea,
          .theme-aware-logs select,
          .theme-aware-logs button,
          .theme-aware-logs .ant-input,
          .theme-aware-logs .ant-btn,
          .theme-aware-logs .ant-select,
          .theme-aware-logs .ant-picker {
            color: var(--text-primary) !important;
          }

          /* InferenceFilters component specific */
          .theme-aware-logs [class*="InferenceFilters"] *,
          .theme-aware-logs [class*="filters"] * {
            color: var(--text-primary) !important;
          }

          /* SearchHeaderInput specific override */
          .theme-aware-logs .theme-search-override,
          .theme-aware-logs .theme-search-override input,
          .theme-aware-logs .theme-search-override .ant-input {
            background-color: var(--bg-tertiary) !important;
            border-color: var(--border-secondary) !important;
            color: var(--text-primary) !important;
          }

          .theme-aware-logs .theme-search-override input::placeholder {
            color: var(--text-disabled) !important;
          }

          /* Ant Design Card components with hardcoded dark colors */
          .theme-aware-logs .ant-card,
          .theme-aware-logs .ant-card.ant-card-bordered,
          .theme-aware-logs .ant-card.ant-card-small,
          .theme-aware-logs .ant-card[class*="bg-[#101010]"],
          .theme-aware-logs .ant-card[class*="bg-[#1A1A1A]"],
          .theme-aware-logs .ant-card[class*="bg-[#161616]"],
          .theme-aware-logs div[class*="bg-[#101010]"],
          .theme-aware-logs div[class*="bg-[#1A1A1A]"],
          .theme-aware-logs div[class*="bg-[#161616]"] {
            background-color: var(--bg-card) !important;
            border-color: var(--border-color) !important;
            color: var(--text-primary) !important;
          }

          /* Card borders with hardcoded dark colors */
          .theme-aware-logs .ant-card[class*="border-[#1F1F1F]"],
          .theme-aware-logs .ant-card[class*="border-[#2F2F2F]"],
          .theme-aware-logs div[class*="border-[#1F1F1F]"],
          .theme-aware-logs div[class*="border-[#2F2F2F]"] {
            border-color: var(--border-color) !important;
          }

          /* Card headers and content */
          .theme-aware-logs .ant-card-head,
          .theme-aware-logs .ant-card-body,
          .theme-aware-logs .ant-card-head-title {
            background-color: var(--bg-card) !important;
            border-color: var(--border-color) !important;
            color: var(--text-primary) !important;
          }

          /* All nested elements in cards */
          .theme-aware-logs .ant-card *,
          .theme-aware-logs .ant-card .ant-card-body *,
          .theme-aware-logs div[class*="bg-[#101010]"] *,
          .theme-aware-logs div[class*="bg-[#1A1A1A]"] * {
            color: var(--text-primary) !important;
          }

          /* Specific override for the problematic div class */
          .theme-aware-logs .ant-card.bg-\[\#101010\],
          .theme-aware-logs .ant-card.border-\[\#1F1F1F\] {
            background-color: var(--bg-card) !important;
            border-color: var(--border-color) !important;
          }

          /* Global override for ANY element with hardcoded dark backgrounds */
          .theme-aware-logs *[style*="background-color: rgb(16, 16, 16)"],
          .theme-aware-logs *[style*="background-color: #101010"],
          .theme-aware-logs *[style*="background-color: #1A1A1A"],
          .theme-aware-logs *[style*="background-color: #161616"],
          .theme-aware-logs *[style*="border-color: rgb(31, 31, 31)"],
          .theme-aware-logs *[style*="border-color: #1F1F1F"],
          .theme-aware-logs *[style*="border-color: #2F2F2F"] {
            background-color: var(--bg-card) !important;
            border-color: var(--border-color) !important;
            color: var(--text-primary) !important;
          }

          /* Catch-all for any missed dark backgrounds */
          .theme-aware-logs [class*="bg-black"],
          .theme-aware-logs [class*="bg-gray-900"],
          .theme-aware-logs [class*="bg-slate-900"] {
            background-color: var(--bg-card) !important;
          }

          /* Specific fixes for inference filters */
          .theme-aware-logs .inference-filters-container *,
          .theme-aware-logs .filters-wrapper *,
          .theme-aware-logs .inference-filters-container .ant-card,
          .theme-aware-logs .filters-wrapper .ant-card {
            background-color: var(--bg-card) !important;
            border-color: var(--border-color) !important;
            color: var(--text-primary) !important;
          }

          /* Force override for any stubborn components */
          .theme-aware-logs .ant-card.css-dev-only-do-not-override-nvrefq {
            background-color: var(--bg-card) !important;
            border-color: var(--border-color) !important;
            color: var(--text-primary) !important;
          }
        ` }} />

        <div className="projectDetailsDiv antTabWrap mt-4">
          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            items={[
              {
                label: (
                  <div className="flex items-center gap-[0.375rem] px-2">
                    <svg xmlns="http://www.w3.org/2000/svg" width=".875rem" height=".875rem" viewBox="0 0 14 14" fill="none">
                      <path d="M12.6875 12.3672C12.6842 12.6073 12.4901 12.8014 12.25 12.8047H2.33352C1.77079 12.8014 1.31579 12.3464 1.3125 11.7837V1.86719C1.3125 1.62546 1.50828 1.42969 1.75 1.42969C1.99172 1.42969 2.1875 1.62546 2.1875 1.86719V7.40867L3.08602 6.73765V6.73819C3.07672 6.67038 3.07672 6.60148 3.08602 6.53367C3.08602 5.96985 3.54266 5.5132 4.10649 5.5132C4.67032 5.5132 5.12751 5.96983 5.12751 6.53367C5.12751 6.61843 5.11603 6.7032 5.09251 6.78469L7.18103 8.53469C7.31447 8.47344 7.45994 8.44172 7.60651 8.44117C7.69565 8.44281 7.78424 8.45649 7.86901 8.48219L10.15 5.78117C10.0942 5.65047 10.0647 5.50937 10.0625 5.36719C10.0625 4.9543 10.3114 4.58187 10.6925 4.42383C11.0743 4.26633 11.5134 4.35328 11.8054 4.64531C12.0969 4.93733 12.1844 5.37648 12.0264 5.75765C11.8683 6.13937 11.4964 6.3882 11.0835 6.3882C10.9944 6.38655 10.9058 6.37288 10.821 6.34718L8.48751 9.03616C8.5433 9.16741 8.57283 9.30796 8.57501 9.45069C8.57501 10.0145 8.11783 10.4712 7.55399 10.4712C6.99017 10.4712 6.53352 10.0145 6.53352 9.45069C6.53297 9.36592 6.545 9.28116 6.56852 9.19967L4.48 7.44967C4.34656 7.51092 4.20109 7.54263 4.05398 7.54318C3.88882 7.54099 3.72695 7.49943 3.58148 7.42068L2.1875 8.50568V11.7836C2.1875 11.8225 2.20281 11.8597 2.23016 11.887C2.2575 11.9143 2.29469 11.9297 2.33352 11.9297H12.25C12.4901 11.9329 12.6842 12.1271 12.6875 12.3672Z" fill={activeTab === "metrics" ? (effectiveTheme === 'dark' ? "#EEEEEE" : "#1a1a1a") : (effectiveTheme === 'dark' ? "#B3B3B3" : "#666666")} />
                    </svg>
                    {activeTab === "metrics" ? (
                      <span className="font-semibold text-sm" style={{ color: effectiveTheme === 'light' ? '#000000' : '#EEEEEE' }}>Metrics</span>
                    ) : (
                      <span className="font-semibold text-sm" style={{ color: effectiveTheme === 'light' ? '#666666' : '#B3B3B3' }}>Metrics</span>
                    )}
                  </div>
                ),
                key: 'metrics',
                children: (
                  <>
              {/* Enhanced Filters Section - Single Row */}
              <div className="mb-8 mt-2 flex justify-between items-end gap-6 p-6 rounded-lg filter-section-bg">
                {/* View By Section */}
                <div className="flex flex-col gap-2">
                  <Text_12_400_808080 className="!text-[var(--text-muted)]">View by</Text_12_400_808080>
                  <Segmented
                    options={viewByOptions.map(opt => ({
                      label: (
                        <span className="flex items-center gap-2">
                          {opt.icon(viewBy === opt.value)}
                          {opt.label}
                        </span>
                      ),
                      value: opt.value
                    }))}
                    value={viewBy}
                    onChange={(value) => setViewBy(value as any)}
                    className="antSegmented"
                  />
                </div>

                {/* Time Range Section */}
                <div className="flex flex-col gap-2 flex-1">
                  <Text_12_400_808080 className="!text-[var(--text-muted)]">Time Range</Text_12_400_808080>
                  <div className="flex items-center gap-3">
                    <ConfigProvider
                      theme={{
                        token: {
                          colorPrimary: '#965CDE',
                          colorPrimaryHover: '#a873e5',
                          colorPrimaryActive: '#8348c7',
                        },
                        components: {
                          DatePicker: {
                            colorBgContainer: 'var(--bg-tertiary)',
                            colorBorder: 'var(--border-secondary)',
                            colorText: 'var(--text-primary)',
                            colorTextPlaceholder: 'var(--text-disabled)',
                            colorBgElevated: 'var(--bg-tertiary)',
                            colorPrimary: 'var(--color-purple)',
                            colorPrimaryBg: 'var(--bg-hover)',
                            colorPrimaryBgHover: 'var(--bg-hover)',
                            colorTextLightSolid: 'var(--text-primary)',
                            controlItemBgActive: 'var(--color-purple)',
                            colorLink: 'var(--color-purple)',
                            colorLinkHover: 'var(--color-purple-hover)',
                            colorLinkActive: 'var(--color-purple-active)',
                          },
                        },
                      }}
                    >
                      <RangePicker
                        value={timeRange}
                        onChange={handleTimeRangeChange}
                        presets={timeRangePresets}
                        showTime
                        format="YYYY-MM-DD HH:mm"
                        className="bg-[var(--bg-tertiary)] border-[var(--border-secondary)] hover:border-[var(--border-color)] flex-1 h-7"
                        placeholder={['Start Date', 'End Date']}
                      />
                    </ConfigProvider>
                    <div className="flex gap-2">
                      {timeRangePresets.slice(0, 3).map((preset) => {
                        const isSelected = selectedPreset === preset.label;
                        return (
                          <Button
                            key={preset.label}
                            size="small"
                            style={{
                              height: '34px',
                              backgroundColor: isSelected ? 'var(--bg-hover)' : 'transparent',
                              borderColor: isSelected ? 'var(--color-purple)' : 'var(--border-color)',
                              color: isSelected ? 'var(--text-primary)' : 'var(--text-muted)'
                            }}
                            onClick={() => {
                              // Skip if already selected and using the same preset
                              if (selectedPreset === preset.label) {
                                return;
                              }

                              const timeValue = preset.value();
                              setTimeRange(timeValue);
                              setSelectedPreset(preset.label);
                              // Create the new filters
                              const newFilters = {
                                from_date: timeValue[0].toISOString(),
                                to_date: timeValue[1].toISOString(),
                                sort_by: 'timestamp' as const,
                                sort_order: 'desc' as const
                              };
                              // Update filters in store
                              setFilters(newFilters);
                              // Fetch with the same filters to ensure consistency
                              fetchInferences(undefined, newFilters);
                            }}
                            className="text-xs hover:text-[var(--text-primary)] hover:border-[var(--border-secondary)]"
                          >
                            {preset.label}
                          </Button>
                        );
                      })}
                    </div>
                  </div>
                </div>

                {/* Refresh Button */}
                <div style={{ color: 'var(--text-primary)' }}>
                  <PrimaryButton
                    onClick={() => fetchInferences()}
                    style={{ color: 'var(--text-primary)' }}
                  >
                    <ReloadOutlined style={{ color: 'var(--text-primary)' }} />
                    <span className="ml-2" style={{ color: 'var(--text-primary)' }}>Refresh</span>
                  </PrimaryButton>
                </div>
              </div>

                    <MetricsTab
                      timeRange={timeRange}
                      inferences={inferences}
                      isLoading={isLoading}
                      viewBy={viewBy}
                      isActive={activeTab === 'metrics'}
                      filters={filters}
                    />
                  </>
                )
              },
              {
                label: (
                  <div className="flex items-center gap-[0.375rem] px-2">
                    <svg xmlns="http://www.w3.org/2000/svg" width=".875rem" height=".875rem" viewBox="0 0 14 14" fill="none">
                      <path fillRule="evenodd" clipRule="evenodd" d="M1.75 2.11719C1.50828 2.11719 1.3125 2.31296 1.3125 2.55469V12.4922C1.3125 12.7339 1.50828 12.9297 1.75 12.9297H12.25C12.4917 12.9297 12.6875 12.7339 12.6875 12.4922V4.74219C12.6875 4.50046 12.4917 4.30469 12.25 4.30469H7.875C7.71148 4.30469 7.56147 4.21718 7.48353 4.07718L6.39147 2.11719H1.75ZM0.4375 2.55469C0.4375 1.82951 1.02483 1.24219 1.75 1.24219H6.625C6.78852 1.24219 6.93853 1.3297 7.01647 1.4697L8.10853 3.42969H12.25C12.9752 3.42969 13.5625 4.01701 13.5625 4.74219V12.4922C13.5625 13.2174 12.9752 13.8047 12.25 13.8047H1.75C1.02483 13.8047 0.4375 13.2174 0.4375 12.4922V2.55469Z" fill={activeTab === "requests" ? (effectiveTheme === 'dark' ? "#EEEEEE" : "#1a1a1a") : (effectiveTheme === 'dark' ? "#B3B3B3" : "#666666")}/>
                    </svg>
                    {activeTab === "requests" ? (
                      <span className="font-semibold text-sm" style={{ color: effectiveTheme === 'light' ? '#000000' : '#EEEEEE' }}>Requests</span>
                    ) : (
                      <span className="font-semibold text-sm" style={{ color: effectiveTheme === 'light' ? '#666666' : '#B3B3B3' }}>Requests</span>
                    )}
                  </div>
                ),
                key: 'requests',
                children: (
              <div className="listingContainer">
                <div className="mb-4 p-6 rounded-lg filter-section-bg">
                  <InferenceFilters
                    projectId={'all'} // Pass a dummy ID for global view
                    onFiltersChange={() => fetchInferences()}
                  />
                </div>

                <Table<InferenceListItem>
                  columns={columns}
                  dataSource={inferences}
                  rowKey="inference_id"
                  loading={false}
                  pagination={false}
                  virtual
                  bordered={false}
                  footer={undefined}
                  onChange={handleTableChange}
                  scroll={{ x: 1200 }}
                  showSorterTooltip={true}
                  onRow={(record) => ({
                    onClick: (e) => {
                      e.preventDefault();
                      router.push(`/observability/${record.inference_id}`);
                    },
                    className: 'cursor-pointer hover:bg-[var(--bg-hover)]',
                  })}
                  title={() => (
                    <div className="flex justify-between items-center px-[0.75rem] py-[1rem]">
                      <Text_16_600_FFFFFF className="!text-[var(--text-primary)]">
                        Inference Requests
                      </Text_16_600_FFFFFF>
                      <div className="flex items-center justify-between gap-x-[.8rem]">
                        <div style={{ color: 'var(--text-primary)' }}>
                          <SearchHeaderInput
                            placeholder={"Search by prompt or response"}
                            searchValue={searchValue}
                            setSearchValue={setSearchValue}
                            classNames="mr-[.6rem] theme-search-override"
                          />
                        </div>
                        <div style={{ color: 'var(--text-primary)' }}>
                          <PrimaryButton
                            onClick={() => fetchInferences()}
                            style={{ color: 'var(--text-primary)' }}
                          >
                            <ReloadOutlined style={{ color: 'var(--text-primary)' }} />
                            <span className="ml-2" style={{ color: 'var(--text-primary)' }}>Refresh</span>
                          </PrimaryButton>
                        </div>
                        <div style={{ color: 'var(--text-primary)' }}>
                          <SecondaryButton
                            onClick={() => exportInferences('csv')}
                            style={{ color: 'var(--text-primary)' }}
                          >
                            <DownloadOutlined style={{ color: 'var(--text-primary)' }} />
                            <span className="ml-2" style={{ color: 'var(--text-primary)' }}>Export</span>
                          </SecondaryButton>
                        </div>
                      </div>
                    </div>
                  )}
                  locale={{
                    emptyText: (
                      <NoDataFount
                        className="h-[20vh]"
                        message="No observability data found"
                      />
                    ),
                  }}
                />
              </div>
                )
              },
              // {
              //   label: (
              //     <div className="flex items-center gap-[0.375rem] px-2">
              //       <svg xmlns="http://www.w3.org/2000/svg" width=".875rem" height=".875rem" viewBox="0 0 14 14" fill="none">
              //         <path d="M7 1.75C7 1.33579 6.66421 1 6.25 1C5.83579 1 5.5 1.33579 5.5 1.75V2.5H3.75C3.33579 2.5 3 2.83579 3 3.25V4H11V3.25C11 2.83579 10.6642 2.5 10.25 2.5H8.5V1.75C8.5 1.33579 8.16421 1 7.75 1C7.33579 1 7 1.33579 7 1.75ZM3 5.5V11.75C3 12.1642 3.33579 12.5 3.75 12.5H10.25C10.6642 12.5 11 12.1642 11 11.75V5.5H3ZM5.5 7C5.5 6.72386 5.72386 6.5 6 6.5C6.27614 6.5 6.5 6.72386 6.5 7V10C6.5 10.2761 6.27614 10.5 6 10.5C5.72386 10.5 5.5 10.2761 5.5 10V7ZM7.5 7C7.5 6.72386 7.72386 6.5 8 6.5C8.27614 6.5 8.5 6.72386 8.5 7V10C8.5 10.2761 8.27614 10.5 8 10.5C7.72386 10.5 7.5 10.2761 7.5 10V7Z" fill={activeTab === "rules" ? "#EEEEEE" : "#B3B3B3"}/>
              //       </svg>
              //       {activeTab === "rules" ? (
              //         <Text_14_600_EEEEEE>Rules</Text_14_600_EEEEEE>
              //       ) : (
              //         <Text_14_600_B3B3B3>Rules</Text_14_600_B3B3B3>
              //       )}
              //     </div>
              //   ),
              //   key: 'rules',
              //   children: (
              //     <RulesTab
              //       timeRange={timeRange}
              //       isActive={activeTab === 'rules'}
              //     />
              //   )
              // }
            ]}
          />
        </div>
      </div>
    </DashboardLayout>
  );
};

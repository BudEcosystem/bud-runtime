"use client";
import React, { useState, useEffect } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import {
  Table,
  Select,
  DatePicker,
  Popover,
  ConfigProvider,
  TableProps,
  Input,
  Tag,
} from "antd";
import { Typography } from "antd";
import styles from "./logs.module.scss";

const { Text, Title } = Typography;
import { MixerHorizontalIcon } from "@radix-ui/react-icons";
import { PrimaryButton, SecondaryButton } from "@/components/ui/button";
import NoDataFount from "@/components/ui/noChartData";
import dayjs from "dayjs";
import { errorToast, successToast } from "@/components/toast";
import { copyToClipboard } from "@/utils/clipboard";
const { RangePicker } = DatePicker;

interface APIKey {
  id: string;
  name: string;
  key: string;
  user_id: string;
  created_at: string;
  last_used: string | null;
  expires_at: string | null;
  status: "active" | "revoked" | "expired";
  usage_limit: number | null;
  usage_count: number;
  rate_limit: number;
  allowed_models: string[];
  allowed_endpoints: string[];
  description: string;
}

type ColumnsType<T extends object> = TableProps<T>["columns"];

const defaultFilter = {
  status: "",
  model: "",
  dateRange: null as [dayjs.Dayjs, dayjs.Dayjs] | null,
};

function SortIcon({ sortOrder }: { sortOrder: string | null | undefined }) {
  if (!sortOrder) return null;

  return sortOrder === "descend" ? (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="12"
      height="13"
      viewBox="0 0 12 13"
      fill="none"
    >
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M6.00078 2.10938C6.27692 2.10938 6.50078 2.33324 6.50078 2.60938L6.50078 9.40223L8.84723 7.05578C9.04249 6.86052 9.35907 6.86052 9.55433 7.05578C9.7496 7.25104 9.7496 7.56763 9.55433 7.76289L6.35433 10.9629C6.15907 11.1582 5.84249 11.1582 5.64723 10.9629L2.44723 7.76289C2.25197 7.56763 2.25197 7.25104 2.44723 7.05578C2.64249 6.86052 2.95907 6.86052 3.15433 7.05578L5.50078 9.40223L5.50078 2.60938C5.50078 2.33324 5.72464 2.10938 6.00078 2.10938Z"
        fill="#B3B3B3"
      />
    </svg>
  ) : (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="12"
      height="13"
      viewBox="0 0 12 13"
      fill="none"
    >
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M6.00078 10.8906C6.27692 10.8906 6.50078 10.6668 6.50078 10.3906L6.50078 3.59773L8.84723 5.94418C9.04249 6.13944 9.35907 6.13944 9.55433 5.94418C9.7496 5.74892 9.7496 5.43233 9.55433 5.23707L6.35433 2.03707C6.15907 1.84181 5.84249 1.84181 5.64723 2.03707L2.44723 5.23707C2.25197 5.43233 2.25197 5.74892 2.44723 5.94418C2.64249 6.13944 2.95907 6.13944 3.15433 5.94418L5.50078 3.59773L5.50078 10.3906C5.50078 10.6668 5.72464 10.8906 6.00078 10.8906Z"
        fill="#B3B3B3"
      />
    </svg>
  );
}

export default function APIKeysPage() {
  const [filter, setFilter] = useState<{
    status: string;
    model: string;
    dateRange: [dayjs.Dayjs, dayjs.Dayjs] | null;
  }>(defaultFilter);
  const [tempFilter, setTempFilter] = useState<any>(defaultFilter);
  const [filterOpen, setFilterOpen] = useState(false);
  const [filterReset, setFilterReset] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedRows, setExpandedRows] = useState<string[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  // Mock data
  const apiKeys: APIKey[] = [
    {
      id: "key_001",
      name: "Production API Key",
      key: "sk-proj-abc123...xyz789",
      user_id: "user_123",
      created_at: "2024-01-15T10:30:45.123Z",
      last_used: "2024-01-20T14:30:00.000Z",
      expires_at: "2025-01-15T10:30:45.123Z",
      status: "active",
      usage_limit: 1000000,
      usage_count: 45230,
      rate_limit: 60,
      allowed_models: ["gpt-4", "gpt-3.5-turbo", "dall-e-3"],
      allowed_endpoints: ["/v1/chat/completions", "/v1/images/generations"],
      description: "Main production key for customer-facing applications",
    },
    {
      id: "key_002",
      name: "Development API Key",
      key: "sk-dev-def456...uvw012",
      user_id: "user_456",
      created_at: "2024-01-10T08:15:30.456Z",
      last_used: "2024-01-20T10:00:00.000Z",
      expires_at: null,
      status: "active",
      usage_limit: 50000,
      usage_count: 12500,
      rate_limit: 30,
      allowed_models: ["gpt-3.5-turbo", "claude-3-opus"],
      allowed_endpoints: ["/v1/chat/completions"],
      description: "Development and testing purposes only",
    },
    {
      id: "key_003",
      name: "Analytics API Key",
      key: "sk-anly-ghi789...rst345",
      user_id: "user_789",
      created_at: "2023-12-01T12:00:00.000Z",
      last_used: "2024-01-19T18:45:00.000Z",
      expires_at: "2024-02-01T12:00:00.000Z",
      status: "active",
      usage_limit: null,
      usage_count: 89450,
      rate_limit: 120,
      allowed_models: ["gpt-4", "gpt-3.5-turbo"],
      allowed_endpoints: ["/v1/chat/completions", "/v1/embeddings"],
      description: "Used for data analytics and reporting dashboards",
    },
    {
      id: "key_004",
      name: "Mobile App Key",
      key: "sk-mob-jkl012...opq678",
      user_id: "user_123",
      created_at: "2023-11-20T09:30:00.000Z",
      last_used: null,
      expires_at: "2023-12-20T09:30:00.000Z",
      status: "expired",
      usage_limit: 100000,
      usage_count: 95000,
      rate_limit: 20,
      allowed_models: ["gpt-3.5-turbo"],
      allowed_endpoints: ["/v1/chat/completions"],
      description: "Mobile application integration - iOS and Android",
    },
    {
      id: "key_005",
      name: "Webhook Integration",
      key: "sk-whk-mno345...lmn901",
      user_id: "user_456",
      created_at: "2024-01-05T14:20:00.000Z",
      last_used: "2024-01-18T16:30:00.000Z",
      expires_at: null,
      status: "revoked",
      usage_limit: 25000,
      usage_count: 18500,
      rate_limit: 10,
      allowed_models: ["gpt-3.5-turbo"],
      allowed_endpoints: ["/v1/chat/completions"],
      description: "Revoked due to suspicious activity",
    },
  ];

  const getStatusColor = (status: string) => {
    switch (status) {
      case "active":
        return "#479D5F";
      case "revoked":
        return "#EC7575";
      case "expired":
        return "#DE9C5C";
      default:
        return "var(--bud-text-disabled)";
    }
  };

  const handleOpenChange = (open: boolean) => {
    setFilterOpen(open);
    if (open) {
      setTempFilter(filter);
    }
  };

  const resetFilter = () => {
    setCurrentPage(1);
    setFilterReset(true);
    setTempFilter(defaultFilter);
    setFilter(defaultFilter);
  };

  const applyFilter = () => {
    setFilterReset(false);
    setFilter(tempFilter);
    setCurrentPage(1);
    setFilterOpen(false);
  };

  useEffect(() => {
    if (filterReset) {
      applyFilter();
    }
  }, [filterReset]);

  const handlePageChange = (currentPage: number, pageSize: number) => {
    setCurrentPage(currentPage);
    setPageSize(pageSize);
  };

  const filteredKeys = apiKeys.filter((key) => {
    const statusMatch = !filter.status || key.status === filter.status;
    const searchMatch =
      searchQuery === "" ||
      key.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      key.key.toLowerCase().includes(searchQuery.toLowerCase()) ||
      key.user_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      key.description.toLowerCase().includes(searchQuery.toLowerCase());

    let dateMatch = true;
    if (filter.dateRange) {
      const keyDate = dayjs(key.created_at);
      dateMatch =
        keyDate.isAfter(filter.dateRange[0]) &&
        keyDate.isBefore(filter.dateRange[1]);
    }

    return statusMatch && searchMatch && dateMatch;
  });

  const columns: ColumnsType<APIKey> = [
    {
      title: "Name",
      dataIndex: "name",
      key: "name",
      width: 200,
      render: (name: string) => (
        <Text className="whitespace-nowrap font-medium text-bud-text-primary text-[12px]">
          {name}
        </Text>
      ),
      sorter: (a, b) => a.name.localeCompare(b.name),
      sortIcon: SortIcon as any,
    },
    {
      title: "API Key",
      dataIndex: "key",
      key: "key",
      width: 250,
      render: (key: string) => (
        <div className="flex items-center gap-2">
          <Text className="font-mono text-xs text-bud-text-primary">{key}</Text>
          <button
            className="text-bud-purple hover:text-bud-purple-hover text-xs"
            onClick={async (e) => {
              e.stopPropagation();
              await copyToClipboard(key, {
                onSuccess: () => successToast("API key copied to clipboard."),
                onError: () => errorToast("Failed to copy API key."),
              });
            }}
          >
            Copy
          </button>
        </div>
      ),
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      width: 100,
      render: (status: string) => (
        <Tag
          color={getStatusColor(status)}
          className="border-0 px-[0.5rem] py-[0.125rem] text-[0.75rem]"
        >
          {status.toUpperCase()}
        </Tag>
      ),
      sorter: (a, b) => a.status.localeCompare(b.status),
      sortIcon: SortIcon as any,
    },
    {
      title: "Usage",
      key: "usage",
      width: 150,
      render: (_: any, record: APIKey) => {
        const percentage = record.usage_limit
          ? Math.round((record.usage_count / record.usage_limit) * 100)
          : 0;
        return (
          <div className="flex flex-col gap-1">
            <Text className="whitespace-nowrap text-bud-text-primary text-[12px]">
              {record.usage_count.toLocaleString()}
              {record.usage_limit
                ? ` / ${record.usage_limit.toLocaleString()}`
                : " (Unlimited)"}
            </Text>
            {record.usage_limit && (
              <div className="w-full bg-bud-border rounded-full h-1.5">
                <div
                  className="bg-bud-purple h-1.5 rounded-full"
                  style={{ width: `${Math.min(percentage, 100)}%` }}
                />
              </div>
            )}
          </div>
        );
      },
      sorter: (a, b) => a.usage_count - b.usage_count,
      sortIcon: SortIcon as any,
    },
    {
      title: "Rate Limit",
      dataIndex: "rate_limit",
      key: "rate_limit",
      width: 100,
      render: (rate_limit: number) => (
        <Text className="whitespace-nowrap text-bud-text-primary text-[12px]">
          {rate_limit} req/min
        </Text>
      ),
      sorter: (a, b) => a.rate_limit - b.rate_limit,
      sortIcon: SortIcon as any,
    },
    {
      title: "Last Used",
      dataIndex: "last_used",
      key: "last_used",
      width: 150,
      render: (last_used: string | null) => (
        <Text className="whitespace-nowrap text-bud-text-primary text-[12px]">
          {last_used ? dayjs(last_used).format("YYYY-MM-DD HH:mm") : "Never"}
        </Text>
      ),
      sorter: (a, b) => {
        const aTime = a.last_used ? dayjs(a.last_used).unix() : 0;
        const bTime = b.last_used ? dayjs(b.last_used).unix() : 0;
        return aTime - bTime;
      },
      sortIcon: SortIcon as any,
    },
    {
      title: "Expires",
      dataIndex: "expires_at",
      key: "expires_at",
      width: 120,
      render: (expires_at: string | null) => (
        <Text className="whitespace-nowrap text-bud-text-primary text-[12px]">
          {expires_at ? dayjs(expires_at).format("YYYY-MM-DD") : "Never"}
        </Text>
      ),
      sorter: (a, b) => {
        const aTime = a.expires_at
          ? dayjs(a.expires_at).unix()
          : Number.MAX_SAFE_INTEGER;
        const bTime = b.expires_at
          ? dayjs(b.expires_at).unix()
          : Number.MAX_SAFE_INTEGER;
        return aTime - bTime;
      },
      sortIcon: SortIcon as any,
    },
    {
      title: "Created",
      dataIndex: "created_at",
      key: "created_at",
      width: 120,
      render: (created_at: string) => (
        <Text className="whitespace-nowrap text-bud-text-primary text-[12px]">
          {dayjs(created_at).format("YYYY-MM-DD")}
        </Text>
      ),
      sorter: (a, b) => dayjs(a.created_at).unix() - dayjs(b.created_at).unix(),
      sortIcon: SortIcon as any,
    },
  ];

  const expandedRowRender = (record: APIKey) => {
    return (
      <div className="bg-bud-bg-tertiary p-[1.5rem] rounded-[8px]">
        <div className="flex flex-col gap-4">
          <div>
            <Text className="text-bud-text-disabled text-[12px]">
              Description
            </Text>
            <Text className="mt-[0.25rem] text-bud-text-primary text-[14px] block">
              {record.description}
            </Text>
          </div>
          <div className="flex gap-6 flex-wrap">
            <div>
              <Text className="text-bud-text-disabled text-[12px]">Key ID</Text>
              <Text className="mt-[0.25rem] font-mono text-bud-text-primary text-[14px] block">
                {record.id}
              </Text>
            </div>
            <div>
              <Text className="text-bud-text-disabled text-[12px]">
                User ID
              </Text>
              <Text className="mt-[0.25rem] text-bud-text-primary text-[14px] block">
                {record.user_id}
              </Text>
            </div>
            <div>
              <Text className="text-bud-text-disabled text-[12px]">
                Full API Key
              </Text>
              <Text className="mt-[0.25rem] font-mono text-xs text-bud-text-primary block">
                {record.key}
              </Text>
            </div>
          </div>
          <div className="flex gap-6 flex-wrap">
            <div>
              <Text className="text-bud-text-disabled text-[12px]">
                Allowed Models
              </Text>
              <div className="mt-[0.25rem] flex gap-2 flex-wrap">
                {record.allowed_models.map((model) => (
                  <Tag
                    key={model}
                    className="border-0 px-[0.5rem] py-[0.125rem] text-[0.75rem] bg-bud-purple bg-opacity-20 text-bud-purple"
                  >
                    {model}
                  </Tag>
                ))}
              </div>
            </div>
            <div>
              <Text className="text-bud-text-disabled text-[12px]">
                Allowed Endpoints
              </Text>
              <div className="mt-[0.25rem] flex gap-2 flex-wrap">
                {record.allowed_endpoints.map((endpoint) => (
                  <Tag
                    key={endpoint}
                    className="border-0 px-[0.5rem] py-[0.125rem] text-[0.75rem] bg-blue-500 bg-opacity-20 text-blue-500"
                  >
                    {endpoint}
                  </Tag>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <DashboardLayout>
      <div className="p-8">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <Title level={2} className="!text-bud-text-primary !mb-0">
              API Keys
            </Title>
          </div>
          <div className="flex items-center gap-4">
            <Input.Search
              placeholder="Search by name, key, or description"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ width: 300 }}
              className={`${styles.searchInput} !bg-bud-bg-secondary !border-bud-border`}
            />

            <Popover
              placement="bottomRight"
              arrow={false}
              open={filterOpen}
              onOpenChange={handleOpenChange}
              content={
                <div className="bg-[var(--bg-card)] shadow-none border border-[var(--border-color)] rounded-[6px] width-348">
                  <div className="p-[1.5rem] flex items-start justify-start flex-col">
                    <Text className="text-[var(--text-primary)] text-[14px] font-normal">
                      Filter
                    </Text>
                    <Text className="text-[12px] font-normal text-bud-text-disabled">
                      Apply filters to find specific logs
                    </Text>
                  </div>
                  <div className="height-1 bg-bud-border mb-[1.5rem] w-full"></div>
                  <div className="w-full flex flex-col gap-size-20 px-[1.5rem] pb-[1.5rem]">
                    <div
                      className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[1rem]`}
                    >
                      <div className="w-full">
                        <Text className="absolute bg-[var(--bg-primary)] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap text-[var(--text-primary)] text-[12px] font-light">
                          Status
                        </Text>
                      </div>
                      <div className="custom-select-two w-full rounded-[6px] relative">
                        <ConfigProvider
                          theme={{
                            token: {
                              colorTextPlaceholder: "var(--text-disabled)",
                              boxShadowSecondary: "none",
                            },
                          }}
                        >
                          <Select
                            variant="borderless"
                            placeholder="Select Status"
                            style={{
                              backgroundColor: "transparent",
                              color: "var(--text-primary)",
                              border: "0.5px solid var(--border-color)",
                              width: "100%",
                            }}
                            size="large"
                            value={tempFilter.status || undefined}
                            className="drawerInp !bg-transparent text-bud-text-primary py-[.6rem] font-light text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-bud-text-primary focus:border-bud-text-primary active:border-bud-text-primary h-[2.5rem] outline-none"
                            options={[
                              { label: "All Status", value: "" },
                              { label: "Active", value: "active" },
                              { label: "Revoked", value: "revoked" },
                              { label: "Expired", value: "expired" },
                            ]}
                            onChange={(value) => {
                              setTempFilter({ ...tempFilter, status: value });
                            }}
                          />
                        </ConfigProvider>
                      </div>
                    </div>

                    <div
                      className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[1rem]`}
                    >
                      <div className="w-full">
                        <Text className="absolute bg-[var(--bg-primary)] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap text-[var(--text-primary)] text-[12px] font-light">
                          Date Range
                        </Text>
                      </div>
                      <div className="custom-select-two w-full rounded-[6px] relative">
                        <RangePicker
                          value={tempFilter.dateRange}
                          onChange={(dates) =>
                            setTempFilter({
                              ...tempFilter,
                              dateRange: dates as [dayjs.Dayjs, dayjs.Dayjs],
                            })
                          }
                          className={`${styles.rangePicker} !bg-transparent text-bud-text-primary border-[0.5px] border-bud-text-disabled w-full hover:border-bud-text-primary focus:border-bud-text-primary`}
                          style={{ width: "100%" }}
                          format="YYYY-MM-DD"
                        />
                      </div>
                    </div>

                    <div className="flex items-center justify-between">
                      <SecondaryButton
                        type="button"
                        onClick={resetFilter}
                        classNames="!px-[.8rem] tracking-[.02rem] mr-[.5rem]"
                      >
                        Reset
                      </SecondaryButton>
                      <PrimaryButton
                        type="submit"
                        onClick={applyFilter}
                        classNames="!px-[.8rem] tracking-[.02rem]"
                      >
                        Apply
                      </PrimaryButton>
                    </div>
                  </div>
                </div>
              }
              trigger={["click"]}
            >
              <div
                className="group h-9 px-3 flex items-center cursor-pointer rounded-md hover:bg-bud-bg-hover transition-colors"
                onClick={() => {}}
              >
                <MixerHorizontalIcon
                  style={{ width: "0.875rem", height: "0.875rem" }}
                  className="text-bud-text-muted group-hover:text-bud-text-primary"
                />
              </div>
            </Popover>

            <button
              onClick={() => console.log("Create new API key")}
              className="px-6 py-2 bg-bud-purple text-white rounded-md hover:bg-bud-purple-hover transition-colors flex items-center gap-2"
            >
              <span className="text-lg">+</span>
              Create API Key
            </button>
          </div>
        </div>

        {/* Table */}
        <div className="bg-bud-bg-secondary border border-bud-border rounded-lg overflow-hidden">
          <Table<APIKey>
            columns={columns}
            pagination={{
              className: "small-pagination",
              current: currentPage,
              pageSize: pageSize,
              total: filteredKeys.length,
              onChange: handlePageChange,
              showSizeChanger: true,
              pageSizeOptions: ["5", "10", "20", "50"],
            }}
            dataSource={filteredKeys}
            bordered={false}
            virtual
            onRow={(record) => {
              return {
                onClick: async (event) => {
                  event.stopPropagation();
                  if (expandedRows.includes(record.id)) {
                    setExpandedRows(
                      expandedRows.filter((id) => id !== record.id),
                    );
                  } else {
                    setExpandedRows([...expandedRows, record.id]);
                  }
                },
              };
            }}
            expandable={{
              expandedRowRender,
              expandedRowKeys: expandedRows,
              expandRowByClick: false,
            }}
            showSorterTooltip={false}
            locale={{
              emptyText: (
                <NoDataFount
                  classNames="h-[20vh]"
                  textMessage={`No API Keys Found`}
                />
              ),
            }}
            className={styles.logsTable}
          />
        </div>
      </div>
    </DashboardLayout>
  );
}

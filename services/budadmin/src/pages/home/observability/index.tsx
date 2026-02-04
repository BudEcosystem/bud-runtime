import React, { useEffect, useState } from "react";
import {
  Tabs,
  Button,
  Table,
  Tag,
  Typography,
  Card,
  Row,
  Col,
  Statistic,
  Select,
  DatePicker,
  Space,
  Segmented,
  Image,
  ConfigProvider,
} from "antd";
import {
  DownloadOutlined,
  ReloadOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  BarChartOutlined,
  LineChartOutlined,
  PieChartOutlined,
  GlobalOutlined,
  FilterOutlined,
  UserOutlined,
  AppstoreOutlined,
  RocketOutlined,
  CodeOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { format } from "date-fns";
import { formatTimestamp } from "@/utils/formatDate";
import { useRouter } from "next/router";
import { useInferences, InferenceListItem } from "@/stores/useInferences";
import InferenceFilters from "@/components/inferences/InferenceFilters";
import {
  Text_12_300_EEEEEE,
  Text_12_400_EEEEEE,
  Text_16_600_FFFFFF,
  Text_14_600_EEEEEE,
  Text_14_600_B3B3B3,
  Text_12_400_808080,
} from "@/components/ui/text";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import NoDataFount from "@/components/ui/noDataFount";
import {
  PrimaryButton,
  SecondaryButton,
} from "@/components/ui/bud/form/Buttons";
import ProjectTags from "src/flows/components/ProjectTags";
import { SortIcon } from "@/components/ui/bud/table/SortIcon";
import { formatDate } from "src/utils/formatDate";
import { useLoaderOnLoding } from "src/hooks/useLoaderOnLoading";
import { copyToClipboard as copyText } from "@/utils/clipboard";
import DashBoardLayout from "../layout";
import PageHeader from "@/components/ui/pageHeader";
import { ClientTimestamp } from "@/components/ui/ClientTimestamp";
import MetricsTab from "./MetricsTab";
import RulesTab from "./RulesTab";
import type { RangePickerProps } from "antd/es/date-picker";
import dayjs from "dayjs";
import { errorToast, successToast } from "@/components/toast";
import CustomPopover from "src/flows/components/customPopover";

const { Text } = Typography;
const { RangePicker } = DatePicker;

const ObservabilityPage: React.FC = () => {
  const router = useRouter();
  const [searchValue, setSearchValue] = useState("");
  const [activeTab, setActiveTab] = useState("metrics");
  // Initialize with consistent rounded times
  const [timeRange, setTimeRange] = useState<[dayjs.Dayjs, dayjs.Dayjs]>([
    dayjs().startOf("day").subtract(7, "days"),
    dayjs().startOf("hour"),
  ]);
  const [viewBy, setViewBy] = useState<
    "model" | "deployment" | "project" | "user"
  >("model");
  const [selectedPreset, setSelectedPreset] = useState<string>("Last 7 days");

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
  useLoaderOnLoding(isLoading);

  // Sync filters with timeRange on mount and fetch inferences
  useEffect(() => {
    // Create initial filters based on timeRange
    const initialFilters = {
      from_date: timeRange[0].toISOString(),
      to_date: timeRange[1].toISOString(),
      sort_by: "timestamp" as const,
      sort_order: "desc" as const,
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
  const copyToClipboard = async (text: string) => {
    await copyText(text, {
      onSuccess: () => successToast("Copied to clipboard"),
      onError: () => errorToast("Failed to copy to clipboard"),
    });
  };

  // Handle time range change
  const handleTimeRangeChange: RangePickerProps["onChange"] = (dates) => {
    if (dates && dates[0] && dates[1]) {
      setTimeRange([dates[0], dates[1]]);
      setSelectedPreset(""); // Clear preset selection when using date picker
      // Create the new filters
      const newFilters = {
        from_date: dates[0].toISOString(),
        to_date: dates[1].toISOString(),
        sort_by: "timestamp" as const,
        sort_order: "desc" as const,
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
      label: "Last 1 hour",
      value: () => {
        const now = dayjs(); // Use exact current time
        return [now.subtract(1, "hours"), now] as [dayjs.Dayjs, dayjs.Dayjs];
      },
    },
    {
      label: "Last 6 hours",
      value: () => {
        const now = dayjs(); // Use exact current time
        return [now.subtract(6, "hours"), now] as [dayjs.Dayjs, dayjs.Dayjs];
      },
    },
    {
      label: "Last 24 hours",
      value: () => {
        const now = dayjs(); // Use exact current time
        return [now.subtract(24, "hours"), now] as [dayjs.Dayjs, dayjs.Dayjs];
      },
    },
    {
      label: "Last 7 days",
      value: () => {
        const now = dayjs().startOf("day"); // Round to start of current day
        return [now.subtract(7, "days"), now] as [dayjs.Dayjs, dayjs.Dayjs];
      },
    },
    {
      label: "Last 30 days",
      value: () => {
        const now = dayjs().startOf("day"); // Round to start of current day
        return [now.subtract(30, "days"), now] as [dayjs.Dayjs, dayjs.Dayjs];
      },
    },
    {
      label: "Last 3 months",
      value: () => {
        const now = dayjs().startOf("day"); // Round to start of current day
        return [now.subtract(3, "months"), now] as [dayjs.Dayjs, dayjs.Dayjs];
      },
    },
  ];

  // View by options with appropriate icons
  const viewByOptions = [
    {
      label: "Model",
      value: "model",
      icon: (active: boolean) => (
        <Image
          preview={false}
          src={
            active
              ? "/images/icons/modelRepoWhite.png"
              : "/images/icons/modelRepo.png"
          }
          style={{ width: "14px", height: "14px" }}
          alt="Model"
        />
      ),
    },
    {
      label: "Deployment",
      value: "deployment",
      icon: (active: boolean) => (
        <Image
          preview={false}
          src={
            active
              ? "/images/icons/clustersWhite.png"
              : "/images/icons/cluster.png"
          }
          style={{ width: "14px", height: "14px" }}
          alt="Deployment"
        />
      ),
    },
    {
      label: "Project",
      value: "project",
      icon: (active: boolean) => (
        <Image
          preview={false}
          src={
            active
              ? "/images/icons/projectIconWhite.png"
              : "/images/icons/projectIcon.png"
          }
          style={{ width: "14px", height: "14px" }}
          alt="Project"
        />
      ),
    },
    {
      label: "User",
      value: "user",
      icon: (active: boolean) => (
        <Image
          preview={false}
          src={
            active ? "/images/icons/userWhite.png" : "/images/icons/user.png"
          }
          style={{ width: "14px", height: "14px" }}
          alt="User"
        />
      ),
    },
  ];

  // Table columns definition
  const columns: ColumnsType<InferenceListItem> = [
    {
      title: "Timestamp",
      dataIndex: "timestamp",
      key: "timestamp",
      width: 180,
      render: (timestamp: string) => (
        <Text_12_400_EEEEEE>
          <ClientTimestamp timestamp={timestamp} />
        </Text_12_400_EEEEEE>
      ),
      sorter: true,
      sortIcon: SortIcon,
    },
    {
      title: "Project",
      dataIndex: "project_name",
      key: "project_name",
      width: 150,
      render: (project_name: string) => (
        <CustomPopover title={project_name || "N/A"}>
          <Text_12_400_EEEEEE className="truncate max-w-[130px]">
            {project_name || "-"}
          </Text_12_400_EEEEEE>
        </CustomPopover>
      ),
    },
    {
      title: "Deployment",
      dataIndex: "endpoint_name",
      key: "endpoint_name",
      width: 200,
      render: (endpoint_name: string) => (
        <CustomPopover title={endpoint_name || "N/A"}>
          <Text_12_400_EEEEEE className="truncate max-w-[180px]">
            {endpoint_name || "-"}
          </Text_12_400_EEEEEE>
        </CustomPopover>
      ),
    },
    {
      title: "Prompt Preview",
      dataIndex: "prompt_preview",
      key: "prompt_preview",
      width: 350,
      render: (prompt: string) => (
        <CustomPopover title={prompt}>
          <Text_12_300_EEEEEE className="truncate max-w-[330px]">
            {prompt}
          </Text_12_300_EEEEEE>
        </CustomPopover>
      ),
    },
    {
      title: "Response Time",
      dataIndex: "response_time_ms",
      key: "response_time_ms",
      width: 120,
      render: (response_time_ms: number) => (
        <Text_12_400_EEEEEE>
          {response_time_ms ? `${response_time_ms.toLocaleString()} ms` : "-"}
        </Text_12_400_EEEEEE>
      ),
      sorter: true,
      sortIcon: SortIcon,
    },
    {
      title: "Tokens",
      key: "tokens",
      width: 120,
      render: (_, record) => (
        <Text_12_400_EEEEEE>
          {record.input_tokens + record.output_tokens || "-"}
        </Text_12_400_EEEEEE>
      ),
    },
    {
      title: "Status",
      key: "status",
      width: 100,
      render: (_, record) => (
        <ProjectTags
          name={record.is_success ? "Success" : "Failed"}
          color={record.is_success ? "#22c55e" : "#ef4444"}
          textClass="text-[.75rem]"
        />
      ),
    },
  ];

  // Handle table change (pagination, sorting)
  const handleTableChange = (
    newPagination: any,
    _filters: any,
    sorter: any,
  ) => {
    // Handle sorting
    if (sorter.field) {
      const sortMap: Record<string, string> = {
        timestamp: "timestamp",
        response_time_ms: "latency",
      };

      const sortBy = sortMap[sorter.field] || "timestamp";
      const sortOrder = sorter.order === "ascend" ? "asc" : "desc";

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
      key: "csv",
      label: "Export as CSV",
      onClick: () => exportInferences("csv"),
    },
    {
      key: "json",
      label: "Export as JSON",
      onClick: () => exportInferences("json"),
    },
  ];

  return (
    <DashBoardLayout>
      <div className="boardPageView">
        <div className="boardPageTop">
          <PageHeader headding="Observability" />
        </div>

        <div className="projectDetailsDiv antTabWrap mt-4">
          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            items={[
              {
                label: (
                  <div className="flex items-center gap-[0.375rem] px-2">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width=".875rem"
                      height=".875rem"
                      viewBox="0 0 14 14"
                      fill="none"
                    >
                      <path
                        d="M12.6875 12.3672C12.6842 12.6073 12.4901 12.8014 12.25 12.8047H2.33352C1.77079 12.8014 1.31579 12.3464 1.3125 11.7837V1.86719C1.3125 1.62546 1.50828 1.42969 1.75 1.42969C1.99172 1.42969 2.1875 1.62546 2.1875 1.86719V7.40867L3.08602 6.73765V6.73819C3.07672 6.67038 3.07672 6.60148 3.08602 6.53367C3.08602 5.96985 3.54266 5.5132 4.10649 5.5132C4.67032 5.5132 5.12751 5.96983 5.12751 6.53367C5.12751 6.61843 5.11603 6.7032 5.09251 6.78469L7.18103 8.53469C7.31447 8.47344 7.45994 8.44172 7.60651 8.44117C7.69565 8.44281 7.78424 8.45649 7.86901 8.48219L10.15 5.78117C10.0942 5.65047 10.0647 5.50937 10.0625 5.36719C10.0625 4.9543 10.3114 4.58187 10.6925 4.42383C11.0743 4.26633 11.5134 4.35328 11.8054 4.64531C12.0969 4.93733 12.1844 5.37648 12.0264 5.75765C11.8683 6.13937 11.4964 6.3882 11.0835 6.3882C10.9944 6.38655 10.9058 6.37288 10.821 6.34718L8.48751 9.03616C8.5433 9.16741 8.57283 9.30796 8.57501 9.45069C8.57501 10.0145 8.11783 10.4712 7.55399 10.4712C6.99017 10.4712 6.53352 10.0145 6.53352 9.45069C6.53297 9.36592 6.545 9.28116 6.56852 9.19967L4.48 7.44967C4.34656 7.51092 4.20109 7.54263 4.05398 7.54318C3.88882 7.54099 3.72695 7.49943 3.58148 7.42068L2.1875 8.50568V11.7836C2.1875 11.8225 2.20281 11.8597 2.23016 11.887C2.2575 11.9143 2.29469 11.9297 2.33352 11.9297H12.25C12.4901 11.9329 12.6842 12.1271 12.6875 12.3672Z"
                        fill={activeTab === "metrics" ? "#EEEEEE" : "#B3B3B3"}
                      />
                    </svg>
                    {activeTab === "metrics" ? (
                      <Text_14_600_EEEEEE>Metrics</Text_14_600_EEEEEE>
                    ) : (
                      <Text_14_600_B3B3B3>Metrics</Text_14_600_B3B3B3>
                    )}
                  </div>
                ),
                key: "metrics",
                children: (
                  <>
                    {/* Enhanced Filters Section - Single Row */}
                    <div className="mb-8 mt-2 flex justify-between items-end gap-6">
                      {/* View By Section */}
                      <div className="flex flex-col gap-2">
                        <Text_12_400_808080>View by</Text_12_400_808080>
                        <Segmented
                          options={viewByOptions.map((opt) => ({
                            label: (
                              <span className="flex items-center gap-2">
                                {opt.icon(viewBy === opt.value)}
                                {opt.label}
                              </span>
                            ),
                            value: opt.value,
                          }))}
                          value={viewBy}
                          onChange={(value) => setViewBy(value as any)}
                          className="antSegmented"
                        />
                      </div>

                      {/* Time Range Section */}
                      <div className="flex flex-col gap-2 flex-1">
                        <Text_12_400_808080>Time Range</Text_12_400_808080>
                        <div className="flex items-center gap-3">
                          <ConfigProvider
                            theme={{
                              token: {
                                colorPrimary: "#965CDE",
                                colorPrimaryHover: "#a873e5",
                                colorPrimaryActive: "#8348c7",
                              },
                              components: {
                                DatePicker: {
                                  colorBgContainer: "#1A1A1A",
                                  colorBorder: "#1F1F1F",
                                  colorText: "#EEEEEE",
                                  colorTextPlaceholder: "#666666",
                                  colorBgElevated: "#1A1A1A",
                                  colorPrimary: "#965CDE",
                                  colorPrimaryBg: "#2A1F3D",
                                  colorPrimaryBgHover: "#3A2F4D",
                                  colorTextLightSolid: "#FFFFFF",
                                  controlItemBgActive: "#965CDE",
                                  colorLink: "#965CDE",
                                  colorLinkHover: "#a873e5",
                                  colorLinkActive: "#8348c7",
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
                              className="bg-[#1A1A1A] border-[#1F1F1F] hover:border-[#3F3F3F] flex-1 h-7"
                              placeholder={["Start Date", "End Date"]}
                            />
                          </ConfigProvider>
                          <div className="flex gap-2">
                            {timeRangePresets.slice(0, 3).map((preset) => {
                              const isSelected =
                                selectedPreset === preset.label;
                              return (
                                <Button
                                  key={preset.label}
                                  size="small"
                                  style={{
                                    height: "34px",
                                    backgroundColor: isSelected
                                      ? "#1E0C34"
                                      : "transparent",
                                    borderColor: isSelected
                                      ? "#965CDE"
                                      : "#374151",
                                    color: isSelected ? "#FFFFFF" : "#9CA3AF",
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
                                      sort_by: "timestamp" as const,
                                      sort_order: "desc" as const,
                                    };
                                    // Update filters in store
                                    setFilters(newFilters);
                                    // Fetch with the same filters to ensure consistency
                                    fetchInferences(undefined, newFilters);
                                  }}
                                  className="text-xs hover:text-white hover:border-gray-500"
                                >
                                  {preset.label}
                                </Button>
                              );
                            })}
                          </div>
                        </div>
                      </div>

                      {/* Refresh Button */}
                      <PrimaryButton onClick={() => fetchInferences()}>
                        <ReloadOutlined />
                        <span className="ml-2">Refresh</span>
                      </PrimaryButton>
                    </div>

                    <MetricsTab
                      timeRange={timeRange}
                      inferences={inferences}
                      isLoading={isLoading}
                      viewBy={viewBy}
                      isActive={activeTab === "metrics"}
                      filters={filters}
                    />
                  </>
                ),
              },
              {
                label: (
                  <div className="flex items-center gap-[0.375rem] px-2">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width=".875rem"
                      height=".875rem"
                      viewBox="0 0 14 14"
                      fill="none"
                    >
                      <path
                        fillRule="evenodd"
                        clipRule="evenodd"
                        d="M1.75 2.11719C1.50828 2.11719 1.3125 2.31296 1.3125 2.55469V12.4922C1.3125 12.7339 1.50828 12.9297 1.75 12.9297H12.25C12.4917 12.9297 12.6875 12.7339 12.6875 12.4922V4.74219C12.6875 4.50046 12.4917 4.30469 12.25 4.30469H7.875C7.71148 4.30469 7.56147 4.21718 7.48353 4.07718L6.39147 2.11719H1.75ZM0.4375 2.55469C0.4375 1.82951 1.02483 1.24219 1.75 1.24219H6.625C6.78852 1.24219 6.93853 1.3297 7.01647 1.4697L8.10853 3.42969H12.25C12.9752 3.42969 13.5625 4.01701 13.5625 4.74219V12.4922C13.5625 13.2174 12.9752 13.8047 12.25 13.8047H1.75C1.02483 13.8047 0.4375 13.2174 0.4375 12.4922V2.55469Z"
                        fill={activeTab === "requests" ? "#EEEEEE" : "#B3B3B3"}
                      />
                    </svg>
                    {activeTab === "requests" ? (
                      <Text_14_600_EEEEEE>Requests</Text_14_600_EEEEEE>
                    ) : (
                      <Text_14_600_B3B3B3>Requests</Text_14_600_B3B3B3>
                    )}
                  </div>
                ),
                key: "requests",
                children: (
                  <div className="listingContainer observability">
                    <div className="mb-4">
                      <InferenceFilters
                        projectId={"all"} // Pass a dummy ID for global view
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
                      footer={null}
                      onChange={handleTableChange}
                      scroll={{ x: 1200 }}
                      showSorterTooltip={true}
                      onRow={(record) => ({
                        onClick: (e) => {
                          e.preventDefault();
                          router.push(`/observability/${record.inference_id}`);
                        },
                        className: "cursor-pointer hover:bg-gray-900",
                      })}
                      title={() => (
                        <div className="flex justify-between items-center px-[0.75rem] py-[1rem]">
                          <Text_16_600_FFFFFF className="text-[#EEEEEE]">
                            Inference Requests
                          </Text_16_600_FFFFFF>
                          <div className="flex items-center justify-between gap-x-[.8rem]">
                            <SearchHeaderInput
                              placeholder="Search by prompt or response"
                              searchValue={searchValue}
                              setSearchValue={setSearchValue}
                            />
                            <PrimaryButton onClick={() => fetchInferences()}>
                              <ReloadOutlined />
                              <span className="ml-2">Refresh</span>
                            </PrimaryButton>
                            <SecondaryButton
                              onClick={() => exportInferences("csv")}
                            >
                              <DownloadOutlined />
                              <span className="ml-2">Export</span>
                            </SecondaryButton>
                          </div>
                        </div>
                      )}
                      locale={{
                        emptyText: (
                          <NoDataFount
                            classNames="h-[20vh]"
                            textMessage="No observability data found"
                          />
                        ),
                      }}
                    />
                  </div>
                ),
              },
              {
                label: (
                  <div className="flex items-center gap-[0.375rem] px-2">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width=".875rem"
                      height=".875rem"
                      viewBox="0 0 14 14"
                      fill="none"
                    >
                      <path
                        d="M7 1.75C7 1.33579 6.66421 1 6.25 1C5.83579 1 5.5 1.33579 5.5 1.75V2.5H3.75C3.33579 2.5 3 2.83579 3 3.25V4H11V3.25C11 2.83579 10.6642 2.5 10.25 2.5H8.5V1.75C8.5 1.33579 8.16421 1 7.75 1C7.33579 1 7 1.33579 7 1.75ZM3 5.5V11.75C3 12.1642 3.33579 12.5 3.75 12.5H10.25C10.6642 12.5 11 12.1642 11 11.75V5.5H3ZM5.5 7C5.5 6.72386 5.72386 6.5 6 6.5C6.27614 6.5 6.5 6.72386 6.5 7V10C6.5 10.2761 6.27614 10.5 6 10.5C5.72386 10.5 5.5 10.2761 5.5 10V7ZM7.5 7C7.5 6.72386 7.72386 6.5 8 6.5C8.27614 6.5 8.5 6.72386 8.5 7V10C8.5 10.2761 8.27614 10.5 8 10.5C7.72386 10.5 7.5 10.2761 7.5 10V7Z"
                        fill={activeTab === "rules" ? "#EEEEEE" : "#B3B3B3"}
                      />
                    </svg>
                    {activeTab === "rules" ? (
                      <Text_14_600_EEEEEE>Rules</Text_14_600_EEEEEE>
                    ) : (
                      <Text_14_600_B3B3B3>Rules</Text_14_600_B3B3B3>
                    )}
                  </div>
                ),
                key: "rules",
                children: (
                  <RulesTab
                    timeRange={timeRange}
                    isActive={activeTab === "rules"}
                  />
                ),
              },
            ]}
          />
        </div>
      </div>
    </DashBoardLayout>
  );
};

export default ObservabilityPage;

"use client";
import { useState, useEffect, useMemo, useCallback } from "react";
import React from "react";
import { Table, Tag, Popover, ConfigProvider, Select, DatePicker } from "antd";
import { ColumnsType } from "antd/es/table";
import { useRouter } from "next/router";
import { MixerHorizontalIcon } from "@radix-ui/react-icons";
import { useEvaluations, ExperimentData, GetExperimentsPayload } from "src/hooks/useEvaluations";
import {
  Text_12_400_EEEEEE,
  Text_16_600_FFFFFF,
  Text_12_300_EEEEEE,
  Text_12_400_B3B3B3,
  Text_12_400_FFFFFF,
} from "@/components/ui/text";
import { PrimaryButton, SecondaryButton } from "@/components/ui/bud/form/Buttons";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import NoDataFount from "@/components/ui/noDataFount";
import { SortIcon } from "@/components/ui/bud/table/SortIcon";
import { formatDate } from "@/utils/formatDate";
import Tags from "src/flows/components/DrawerTags";
import ProjectTags from "src/flows/components/ProjectTags";
import { capitalize } from "@/lib/utils";
import { endpointStatusMapping } from "@/lib/colorMapping";
import { Model, useModels } from "@/hooks/useModels";
import dayjs from "dayjs";


// Remove the local interface since we're importing it from the hook

interface ExperimentFilters {
  status?: string;
  tags?: string[];
  model_id?: string
  created_after?: string
  created_before?: string
}

const defaultFilter: ExperimentFilters = {
  status: '',
  tags: [],
  model_id: '',
  created_after: '',
  created_before: ''
};

const ExperimentsTable = () => {
  const router = useRouter();
  const [searchValue, setSearchValue] = useState("");
  const [order, setOrder] = useState("");
  const [orderBy, setOrderBy] = useState("");
  const [filterOpen, setFilterOpen] = useState(false);
  const [tempFilter, setTempFilter] = useState<ExperimentFilters>(defaultFilter);
  const [filter, setFilter] = useState<ExperimentFilters>(defaultFilter);

  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const { RangePicker } = DatePicker;
  // Sample data for testing when API returns no data
  const sampleExperiments: ExperimentData[] = [
    // {
    //   id: "exp-1",
    //   experimentName: "GPT-4 vs Claude-3 Performance Test",
    //   models: "GPT-4, Claude-3",
    //   traits: "Accuracy, Speed, Cost",
    //   tags: ["production", "benchmark"],
    //   status: "Completed",
    //   createdDate: "2024-01-15T10:30:00Z"
    // },
  ];

  // Use Zustand store
  const {
    experimentsList,
    experimentsListTotal,
    loading,
    getExperiments
  } = useEvaluations();

  const {
    models,
    getGlobalModels
  } = useModels();

  // Fetch experiments data from API
  const fetchExperiments = useCallback(async () => {
    try {
      const payload: GetExperimentsPayload = {
        page: currentPage,
        limit: pageSize,
        search: searchValue || undefined,
        experiment_status: filter.status?.length > 0 ? filter.status : undefined,
        tags: filter.tags?.length > 0 ? filter.tags : undefined,
        order: order || undefined,
        orderBy: orderBy || undefined,
        model_id: filter.model_id || undefined,
        created_after: filter.created_after || undefined,
        created_before: filter.created_before || undefined,
      };

      await getExperiments(payload);
    } catch (error) {
      console.error("Failed to fetch experiments:", error);
      // You could show a toast notification here or handle the error as needed
    }
  }, [currentPage, pageSize, searchValue, filter, order, orderBy, getExperiments]);

  // Initial data fetch
  useEffect(() => {
    fetchExperiments();
  }, [fetchExperiments]);

  // Debounced search effect
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      setCurrentPage(1); // Reset to first page when search changes
    }, 300); // 300ms debounce

    return () => clearTimeout(timeoutId);
  }, [searchValue]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case "Running":
        return "#D1B854";
      case "Completed":
        return "#52C41A";
      case "Failed":
        return "#FF4D4F";
      default:
        return "#757575";
    }
  };

  const columns: ColumnsType<ExperimentData> = [
    {
      title: "Experiment name",
      dataIndex: "name",
      key: "name",
      render: (text) => <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>,
      sorter: true,
      sortOrder:
        orderBy === "name"
          ? order === "-"
            ? "descend"
            : "ascend"
          : undefined,
      sortIcon: SortIcon,
    },
    {
      title: "Models",
      dataIndex: "models",
      key: "models",
      ellipsis: true,
      render: (models) => {
        // Handle both string and object/array formats
        let displayText = '-';

        if (typeof models === 'string') {
          displayText = models;
        } else if (Array.isArray(models)) {
          // If it's an array of objects with name property
          displayText = models.map(m => m.name || m).join(', ');
        } else if (models && typeof models === 'object') {
          // If it's a single object with name property
          displayText = models.name || models.deployment_name || JSON.stringify(models);
        }

        if (displayText === '-') {
          return <Text_12_400_EEEEEE>-</Text_12_400_EEEEEE>;
        }

        // Check if text needs truncation (approximately 30 chars for ellipsis)
        const needsTruncation = displayText.length > 30;
        const truncatedText = needsTruncation ? displayText.substring(0, 30) + '...' : displayText;

        if (needsTruncation) {
          return (
            <Popover
              content={
                <div className="max-w-[400px] break-words p-[.8rem]">
                  <Text_12_400_EEEEEE>{displayText}</Text_12_400_EEEEEE>
                </div>
              }
              placement="top"
              rootClassName="models-popover"
            >
              <div className="cursor-pointer" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                <Text_12_400_EEEEEE>{truncatedText}</Text_12_400_EEEEEE>
              </div>
            </Popover>
          );
        }

        return (
          <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            <Text_12_400_EEEEEE>{displayText}</Text_12_400_EEEEEE>
          </div>
        );
      },
    },
    {
      title: "Traits",
      dataIndex: "traits",
      key: "traits",
      ellipsis: true,
      render: (traits) => {
        // Handle both string and object/array formats
        let displayText = '-';

        if (typeof traits === 'string') {
          displayText = traits;
        } else if (Array.isArray(traits)) {
          // If it's an array of objects with name property
          displayText = traits.map(t => t.name || t).join(', ');
        } else if (traits && typeof traits === 'object') {
          // If it's a single object with name property
          displayText = traits.name || JSON.stringify(traits);
        }

        if (displayText === '-') {
          return <Text_12_400_EEEEEE>-</Text_12_400_EEEEEE>;
        }

        // Check if text needs truncation (approximately 30 chars for ellipsis)
        const needsTruncation = displayText.length > 30;
        const truncatedText = needsTruncation ? displayText.substring(0, 30) + '...' : displayText;

        if (needsTruncation) {
          return (
            <Popover
              content={
                <div className="max-w-[400px] break-words p-[.8rem]">
                  <Text_12_400_EEEEEE>{displayText}</Text_12_400_EEEEEE>
                </div>
              }
              placement="top"
              rootClassName="traits-popover"
            >
              <div className="cursor-pointer" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                <Text_12_400_EEEEEE>{truncatedText}</Text_12_400_EEEEEE>
              </div>
            </Popover>
          );
        }

        return (
          <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            <Text_12_400_EEEEEE>{displayText}</Text_12_400_EEEEEE>
          </div>
        );
      },
    },
    {
      title: "Tags",
      dataIndex: "tags",
      key: "tags",
      render: (tags) => {
        // Ensure tags is an array
        const tagsArray = Array.isArray(tags) ? tags : [];
        if (tagsArray.length === 0) {
          return <Text_12_400_EEEEEE>-</Text_12_400_EEEEEE>;
        }
        return (
          <div className="flex gap-1 flex-wrap p-2">
            {tagsArray.map((tag, index) => (
              <Tags
                key={index}
                name={typeof tag === 'string' ? tag : tag.name || JSON.stringify(tag)}
                color="#D1B854"
                classNames="text-center justify-center items-center"
              />
            ))}
          </div>
        );
      },
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      render: (status: string) => (
        <ProjectTags
          name={capitalize(status)}
          color={endpointStatusMapping[capitalize(status) === 'Running' ? capitalize(status) + '-yellow' : capitalize(status)]}
          textClass="text-[.75rem] py-[.22rem]"
          tagClass="py-[0rem]"
        />
      ),
      sorter: true,
      sortOrder:
        orderBy === "status" ? (order === "-" ? "descend" : "ascend") : undefined,
      sortIcon: SortIcon,
    },
    {
      title: (
        <div className="flex items-center">
          Created date
          <svg
            className="ml-1"
            width="12"
            height="12"
            viewBox="0 0 12 12"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M3 7.5L6 10.5L9 7.5M3 4.5L6 1.5L9 4.5"
              stroke="#757575"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
      ),
      dataIndex: "created_at",
      key: "created_at",
      render: (date) => (
        <Text_12_400_EEEEEE>
          {formatDate(date)}
        </Text_12_400_EEEEEE>
      ),
      sorter: true,
      sortOrder:
        orderBy === "created_at"
          ? order === "-"
            ? "descend"
            : "ascend"
          : undefined,
      sortIcon: SortIcon,
    },
    {
      title: "",
      key: "action",
      // width: 140,
      align: 'left' as const,
      className: "px-0",
      render: (_, record) => (
        <div className="">
          <PrimaryButton
            onClick={(e: React.MouseEvent) => {
              e.stopPropagation();
              router.push(`/home/evaluations/experiments/${record.id}`);
            }}
            classNames="!px-4 !py-1 !text-xs opacity-0 group-hover:opacity-100 whitespace-nowrap"
          >
            View Experiment
          </PrimaryButton>
        </div>
      ),
    },
  ];

  // Since filtering is now handled by the API, we can directly use the experiments list
  const filteredData = useMemo(() => {
    console.log("experimentsList:", experimentsList);
    console.log("Is array:", Array.isArray(experimentsList));

    // Ensure experimentsList is an array
    if (!experimentsList || !Array.isArray(experimentsList)) {
      console.log("Using sample experiments because experimentsList is not an array");
      return sampleExperiments;
    }
    // Use sample data if experimentsList is empty
    if (experimentsList.length === 0) {
      console.log("Using sample experiments because experimentsList is empty");
      return sampleExperiments;
    }
    return experimentsList;
  }, [experimentsList]);

  const handleTableChange = (_pagination: any, _filters: any, sorter: any) => {
    if (sorter.field) {
      setOrder(sorter.order === "ascend" ? "" : "-");
      setOrderBy(sorter.field);
    }
  };

  const handleOpenChange = (open: boolean) => {
    setFilterOpen(open);
    setTempFilter(filter);
  };

  const applyFilter = () => {
    setFilterOpen(false);
    setFilter(tempFilter);
    setCurrentPage(1); // Reset to first page when applying filters
  };

  const resetFilter = () => {
    setTempFilter(defaultFilter);
    setFilter(defaultFilter);
    setFilterOpen(false);
    setCurrentPage(1); // Reset to first page when resetting filters
  };

  // Commented out for future use when filter tags display is re-enabled
  // const removeSelectedTag = (key: string, value: string) => {
  //   if (key === "status") {
  //     setFilter({
  //       ...filter,
  //       status: filter.status?.filter((s) => s !== value) || [],
  //     });
  //   } else if (key === "tags") {
  //     setFilter({
  //       ...filter,
  //       tags: filter.tags?.filter((t) => t !== value) || [],
  //     });
  //   }
  // };

  // Get unique tags from all experiments for filter options
  const availableTags = useMemo(() => {
    const tags = new Set<string>();
    if (Array.isArray(experimentsList)) {
      experimentsList.forEach((exp) => {
        if (Array.isArray(exp.tags)) {
          exp.tags.forEach((tag: any) => {
            if (typeof tag === 'string') {
              tags.add(tag);
            } else if (tag && typeof tag === 'object' && 'name' in tag) {
              tags.add(tag.name);
            }
          });
        }
      });
    }
    return Array.from(tags);
  }, [experimentsList]);

  useEffect(() => {
    getGlobalModels({
        page: 1,
        limit: 1000,
    });
  }, [])

  return (
    <div className="h-full w-full relative pt-[2.5rem]">
      {/* Selected Filters */}
      {/* {(filter.status?.length > 0 || filter.tags?.length > 0) && (
        <div className="flex justify-start gap-[.4rem] items-center absolute top-[4.5rem] left-[0.75rem] z-10">
          {filter.status?.map((status, index) => (
            <Tags
              key={`status-${index}`}
              name={`Status: ${status}`}
              color="#d1b854"
              closable
              onClose={() => removeSelectedTag("status", status)}
            />
          ))}
          {filter.tags?.map((tag, index) => (
            <Tags
              key={`tag-${index}`}
              name={`Tag: ${tag}`}
              color="#d1b854"
              closable
              onClose={() => removeSelectedTag("tags", tag)}
            />
          ))}
        </div>
      )} */}
      <div className="userTable evalTable relative CommonCustomPagination">
        <Table<ExperimentData>
          columns={columns}
          dataSource={Array.isArray(filteredData) ? filteredData : []}
          tableLayout="fixed"
          pagination={{
            className: 'small-pagination',
            current: currentPage,
            pageSize: pageSize,
            total: experimentsListTotal || 0,
            onChange: (page, size) => {
              setCurrentPage(page);
              setPageSize(size);
            },
            showSizeChanger: true,
            pageSizeOptions: ['5', '10', '20', '50'],
          }}
          loading={loading}
          onChange={handleTableChange}
          onRow={(record) => ({
            onClick: () => router.push(`/home/evaluations/experiments/${record.id}`),
            style: { cursor: "pointer" },
            className: 'group'
          })}
          showSorterTooltip={false}
          rowKey="id"
          className="experiments-table"
          title={() => (
            <div className="flex justify-between items-center px-[0.75rem] py-[1rem]">
              <Text_16_600_FFFFFF>Experiments</Text_16_600_FFFFFF>
              <div className="flex items-center gap-3">
                <SearchHeaderInput
                  searchValue={searchValue}
                  setSearchValue={setSearchValue}
                  placeholder="Search experiments..."
                />
                <ConfigProvider
                  theme={{
                    token: {
                      colorBgElevated: "#101010",
                      colorBorder: "#1F1F1F",
                    },
                  }}
                >
                  <Popover
                    open={filterOpen}
                    onOpenChange={handleOpenChange}
                    placement="bottomRight"
                    content={
                      <div className="w-[22rem] bg-[#101010] rounded-lg">
                        <div className="flex items-center justify-between px-4 py-3 border-b border-[#1F1F1F]">
                          <Text_16_600_FFFFFF>Filter</Text_16_600_FFFFFF>
                          <button
                            onClick={() => setFilterOpen(false)}
                            className="text-[#B3B3B3] hover:text-[#FFFFFF]"
                          >
                            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
                              <path d="M13 1L1 13M1 1L13 13" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                          </button>
                        </div>
                        <div className="p-4 space-y-4">
                          <Text_12_400_B3B3B3 className="mb-4">
                            Filter experiments by status and tags
                          </Text_12_400_B3B3B3>

                          {/* Status Filter */}
                          <div className="rounded-[6px] relative !bg-[transparent] !w-[100%]">
                            <div className="w-full">
                              <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] px-1 tracking-[.035rem] z-10">
                                Status
                              </Text_12_300_EEEEEE>
                            </div>
                            <div className="custom-select-two w-full rounded-[6px] relative">
                              <ConfigProvider
                                theme={{
                                  token: {
                                    colorTextPlaceholder: "#808080",
                                  },
                                }}
                              >
                                <Select
                                  placeholder="Select Status"
                                  style={{
                                    backgroundColor: "transparent",
                                    color: "#EEEEEE",
                                    border: "0.5px solid #757575",
                                    width: "100%",
                                  }}
                                  value={tempFilter.status}
                                  size="large"
                                  className="drawerInp !bg-[transparent] text-[#EEEEEE] py-[.6rem] font-[300] text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] h-[2.59338rem] outline-none"
                                  options={[
                                    { label: "Running", value: "running" },
                                    { label: "Completed", value: "completed" },
                                    { label: "No Runs", value: "no_runs" },
                                  ]}
                                  onChange={(value) => {
                                    setTempFilter({
                                      ...tempFilter,
                                      status: value,
                                    });
                                  }}
                                  tagRender={(props) => {
                                    const { label } = props;
                                    return (
                                      <Tags
                                        name={label}
                                        color="#D1B854"
                                        classNames="text-center justify-center items-center"
                                      />
                                    );
                                  }}
                                />
                              </ConfigProvider>
                            </div>
                          </div>

                          {/* Models Filter */}
                          <div className="rounded-[6px] relative !bg-[transparent] !w-[100%]">
                            <div className="w-full">
                              <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] px-1 tracking-[.035rem] z-10">
                                Models
                              </Text_12_300_EEEEEE>
                            </div>
                            <div className="custom-select-two w-full rounded-[6px] relative">
                              <ConfigProvider
                                theme={{
                                  token: {
                                    colorTextPlaceholder: "#808080",
                                  },
                                }}
                              >
                                <Select
                                  placeholder="Select Models"
                                  style={{
                                    backgroundColor: "transparent",
                                    color: "#EEEEEE",
                                    border: "0.5px solid #757575",
                                    width: "100%",
                                  }}
                                  value={tempFilter.model_id}
                                  size="large"
                                  className="drawerInp !bg-[transparent] text-[#EEEEEE] py-[.6rem] font-[300] text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] h-[2.59338rem] outline-none"
                                  options={models.map((model: Model) => ({
                                    label: model?.name,
                                    value: model?.id,
                                  }))}
                                  onChange={(value) => {
                                    setTempFilter({
                                      ...tempFilter,
                                      model_id: value,
                                    });
                                  }}
                                  tagRender={(props) => {
                                    const { label } = props;
                                    return (
                                      <Tags
                                        name={label}
                                        color="#D1B854"
                                        classNames="text-center justify-center items-center"
                                      />
                                    );
                                  }}
                                />
                              </ConfigProvider>
                            </div>
                            <div className="mt-4">
                              <Text_12_400_FFFFFF className="mb-1">Created Date</Text_12_400_FFFFFF>
                              <RangePicker
                                showTime={false}
                                style={{ width: "100%" }}
                                format="YYYY-MM-DD"
                                placeholder={["Start Date", "End Date"]}
                                className="bg-[#1A1A1A] border-[#1F1F1F] hover:border-[#3F3F3F]"
                                value={[
                                  tempFilter.created_after ? dayjs(tempFilter.created_after) : null,
                                  tempFilter.created_before ? dayjs(tempFilter.created_before) : null
                                ]}
                                onChange={(dates) => {
                                  if (!dates) {
                                    setTempFilter({
                                      ...tempFilter,
                                      created_after: undefined,
                                      created_before: undefined
                                    });
                                    return;
                                  }

                                  const [from, to] = dates;

                                  setTempFilter({
                                    ...tempFilter,
                                    created_after: from
                                      ? from.startOf('day').toISOString()
                                      : undefined,
                                    created_before: to
                                      ? to.endOf('day').toISOString()
                                      : undefined,
                                  });
                                }}
                              />
                            </div>
                          </div>

                          {/* Action Buttons */}
                          <div className="flex items-center justify-between pt-2">
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
                    <label
                      className="group h-[1.7rem] text-[#EEEEEE] mx-2 flex items-center cursor-pointer text-xs font-normal leading-3 rounded-[6px] shadow-none bg-transparent"
                      onClick={(e: React.MouseEvent) => { e.stopPropagation(); }}
                    >
                      <MixerHorizontalIcon
                        style={{ width: "0.875rem", height: "0.875rem" }}
                        className="text-[#B3B3B3] group-hover:text-[#FFFFFF]"
                      />
                    </label>
                  </Popover>
                </ConfigProvider>
              </div>
            </div>
          )}
          locale={{
            emptyText: <NoDataFount textMessage="No experiments found" />,
          }}
        />
      </div>
    </div>
  );
};

export default ExperimentsTable;

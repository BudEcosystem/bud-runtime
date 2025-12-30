"use client";
import { useRouter } from "next/router";
import React, { useCallback, useEffect, useState } from "react";
import {
  Text_12_300_EEEEEE,
  Text_12_400_EEEEEE,
  Text_16_600_FFFFFF,
} from "@/components/ui/text";
import { useDrawer } from "src/hooks/useDrawer";
import {
  Tabs,
  Image,
  Popover,
  ConfigProvider,
  Select,
  Table,
  Slider,
} from "antd";
import { formatDate } from "src/utils/formatDate";
import { notification } from "antd";
import useHandleRouteChange from "@/lib/useHandleRouteChange";
import NoDataFount from "@/components/ui/noDataFount";
import { SortIcon } from "@/components/ui/bud/table/SortIcon";
import ProjectTags from "src/flows/components/ProjectTags";
import { capitalize } from "@/lib/utils";
import { endpointStatusMapping } from "@/lib/colorMapping";
import { useLoader } from "src/context/appContext";
import { useBenchmarks } from "src/hooks/useBenchmark";
import { IconOnlyRender } from "src/flows/components/BudIconRender";
import { usePerfomanceBenchmark } from "src/stores/usePerfomanceBenchmark";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import CustomPopover from "src/flows/components/customPopover";
import {
  PrimaryButton,
  SecondaryButton,
} from "@/components/ui/bud/form/Buttons";
import Tags from "src/flows/components/DrawerTags";
import { MixerHorizontalIcon } from "@radix-ui/react-icons";

const defaultFilter = {
  benchmarkName: "",
  status: "",
};

interface DataType {
  key?: string;
  created_at?: string;
  model: [];
  cluster: [];
  name?: string;
  modelName?: string;
  modelImage?: string;
  clusterName?: string;
  clusterImage?: string;
  node_type?: any;
  vendor_type?: string;
  status?: string;
  concurrency?: any;
  tpot?: string;
  ttft?: string;
  id?: string;
}

const BenchmarksTable = ({ showTableTitle }: { showTableTitle?: boolean }) => {
  const { reset } = usePerfomanceBenchmark();
  const {
    benchmarks,
    totalUsers,
    getBenchmarks,
    setSelectedBenchmark,
    selectedBenchmark,
    getBenchmarkModelClusterDetails,
    getfilterList,
    modelFilterList,
    clusterFilterList,
  } = useBenchmarks();
  const { isLoading, showLoader, hideLoader } = useLoader();
  const [selectedRow, setSelectedRow] = useState<DataType | null>(null);
  const router = useRouter();
  const { openDrawer } = useDrawer();
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [filter, setFilter] = useState<{
    benchmarkName?: string;
    status?: string;
  }>(defaultFilter);
  const [filterOpen, setFilterOpen] = React.useState(false);
  const [tempFilter, setTempFilter] = useState<any>({});
  const [filterReset, setFilterReset] = useState(false);
  const [order, setOrder] = useState<"-" | "">("");
  const [orderBy, setOrderBy] = useState<string>("created_at");

  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    getfilterList({
      page: 1,
      limit: 10000,
      search: false,
      resource: "model",
    });
    getfilterList({
      page: 1,
      limit: 10000,
      search: false,
      resource: "cluster",
    });
  }, []);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  useEffect(() => {
    if (selectedBenchmark) {
      getBenchmarkModelClusterDetails(selectedBenchmark.id);
    }
  }, [selectedBenchmark]);

  const handleOpenChange = (open) => {
    setFilterOpen(open);
    setTempFilter(filter);
  };

  const resetFilter = () => {
    // setFilter(defaultFilter);
    setTempFilter({ defaultFilter });
    setCurrentPage(1);
    // setFilterOpen(false);
    // load(defaultFilter);
    setFilterReset(true);
  };

  const applyFilter = () => {
    setFilterOpen(false);
    setFilter(tempFilter);
    setCurrentPage(1);
    // load(tempFilter);
    setFilterReset(false);
  };

  useHandleRouteChange(() => {
    notification.destroy();
  });

  const goBack = () => {
    router.back();
  };

  const load = useCallback(
    async (filter) => {
      showLoader();
      await getBenchmarks({
        ...filter,
        page: currentPage,
        limit: pageSize,
        name: filter.benchmarkName || undefined,
        search: !!filter.benchmarkName,
        order_by: "-created_at",
      });
      hideLoader();
    },
    [currentPage, pageSize, getBenchmarks],
  );

  useEffect(() => {
    console.log("filter", filter);
    load(filter);
  }, [currentPage, pageSize, getBenchmarks, filter]);

  useEffect(() => {
    if (filterReset) {
      applyFilter();
    }
  }, [filterReset]);

  const handlePageChange = (currentPage, pageSize) => {
    setCurrentPage(currentPage);
    setPageSize(pageSize);
  };

  return (
    <div className="CommonCustomPagination">
      <Table<DataType>
        columns={[
          {
            title: "Benchmark Name",
            dataIndex: "name",
            key: "name",
            render: (text) => <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>,
            sortOrder:
              orderBy === "name"
                ? order === "-"
                  ? "descend"
                  : "ascend"
                : undefined,
            sorter: true,
            sortIcon: SortIcon,
          },
          {
            title: "Date",
            dataIndex: "created_at",
            key: "created_at",
            minWidth: 150,
            render: (text) => (
              <Text_12_400_EEEEEE className="text-nowrap">
                {formatDate(text)}
              </Text_12_400_EEEEEE>
            ),
            sortIcon: SortIcon,
          },
          {
            title: "Model Name",
            dataIndex: "model",
            key: "model",
            width: "auto",
            className: "min-w-[280px] 1680px:min-w-[300px] 1920:min-w-[500px]",
            render: (text, record) => (
              <div className="flex justify-start items-center gap-[.5rem]">
                {/* {record.modelImage && (
                      <div className='w-[0.875rem] h-[0.875rem] mr-[.4rem]'>
                        <Image src={`${record.modelImage}`} preview={false}
                          style={{ width: '0.875rem' }}
                        />
                      </div>
                    )} */}
                <div className="w-[0.875rem] h-[0.875rem]">
                  <IconOnlyRender
                    icon={text?.["icon"] || text?.provider?.["icon"]}
                    type={text?.["provider_type"]}
                    imageSize={14}
                  />
                </div>
                <Text_12_400_EEEEEE className="truncate">
                  {text.name}
                </Text_12_400_EEEEEE>
              </div>
            ),
            sortIcon: SortIcon,
          },
          {
            title: "Cluster Name",
            key: "cluster",
            dataIndex: "cluster",
            sortOrder:
              orderBy === "status"
                ? order === "-"
                  ? "descend"
                  : "ascend"
                : undefined,
            sorter: true,
            render: (name, record) => (
              <div className="flex justify-start items-center gap-[.5rem]">
                {/* <div className='w-[0.875rem] h-[0.875rem] mr-[.4rem]'>
                    <Image src={`${name?.['icon']}`} preview={false}
                      style={{ width: '0.875rem' }}
                    />
                  </div> */}
                <div className="w-[0.875rem] h-[0.875rem]">
                  <IconOnlyRender
                    icon={name?.["icon"]}
                    type={record?.["provider_type"]}
                    imageSize={14}
                  />
                </div>
                <Text_12_400_EEEEEE className="text-nowrap">
                  {name.name}
                </Text_12_400_EEEEEE>
              </div>
            ),
            sortIcon: SortIcon,
          },
          {
            title: "Node Type",
            dataIndex: "node_type",
            key: "node_type",
            render: (text) => {
              // Map node_type values to display labels
              const getNodeTypeLabel = (nodeType: string) => {
                if (!nodeType) return "-";
                if (nodeType.toLowerCase().startsWith("cpu")) return "CPU";
                if (nodeType.toLowerCase().startsWith("gpu")) return "GPU";
                if (nodeType.toLowerCase().startsWith("hpu")) return "HPU";
                return nodeType.toUpperCase();
              };
              return (
                <div className="flex gap-[.4rem]">
                  <Text_12_400_EEEEEE>{getNodeTypeLabel(text)}</Text_12_400_EEEEEE>
                </div>
              );
            },
            sortIcon: SortIcon,
          },
          {
            title: "Vendor Type",
            dataIndex: "vendor_type",
            sorter: true,
            key: "vendor_type",
            minWidth: 150,
            className: "text-nowrap",
            sortOrder:
              orderBy === "created_at"
                ? order === "-"
                  ? "descend"
                  : "ascend"
                : undefined,
            render: (text) => {
              const lowerText = text?.toLowerCase() || "";
              const hasKnownVendor =
                lowerText.includes("intel") ||
                lowerText.includes("amd") ||
                lowerText.includes("nvidia");

              return (
                <div className="w-[auto] text-nowrap h-[1.25rem]">
                  <div className="w-auto h-[1.25rem] flex items-center justify-start gap-[.7rem]">
                    {lowerText.includes("intel") && (
                      <Image
                        preview={false}
                        src="/images/icons/intel.png"
                        alt="Intel"
                        style={{ width: "auto", height: "1.25rem" }}
                      />
                    )}
                    {lowerText.includes("amd") && (
                      <Image
                        preview={false}
                        src="/images/icons/amd.png"
                        alt="AMD"
                        style={{ width: "auto", height: "0.59725rem" }}
                      />
                    )}
                    {lowerText.includes("nvidia") && (
                      <Image
                        preview={false}
                        src="/images/icons/nvdia.png"
                        alt="NVIDIA"
                        style={{ width: "auto", height: "1.25rem" }}
                      />
                    )}
                    {!hasKnownVendor && text && (
                      <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>
                    )}
                  </div>
                </div>
              );
            },
            sortIcon: SortIcon,
          },
          {
            title: "Status",
            key: "status",
            dataIndex: "status",
            sortOrder:
              orderBy === "status"
                ? order === "-"
                  ? "descend"
                  : "ascend"
                : undefined,
            sorter: true,
            render: (status) => (
              <span>
                <ProjectTags
                  name={capitalize(status)}
                  color={endpointStatusMapping[capitalize(status)]}
                />
              </span>
            ),
            sortIcon: SortIcon,
          },
          {
            title: "Concurrent Requests",
            dataIndex: "concurrency",
            key: "concurrency",
            render: (text, record) => (
              <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>
            ),
            sortIcon: SortIcon,
          },
          {
            title: "TPOT",
            dataIndex: "tpot",
            key: "tpot",
            render: (text, record) => (
              <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>
            ),
            sortIcon: SortIcon,
          },
          {
            title: "TTFT",
            dataIndex: "ttft",
            key: "ttft",
            render: (text, record) => (
              <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>
            ),
            sortIcon: SortIcon,
          },
        ]}
        // loading={loading}
        pagination={{
          current: currentPage,
          pageSize: pageSize,
          total: totalUsers,
          onChange: handlePageChange,
          showSizeChanger: true,
          pageSizeOptions: ["5", "10", "20", "50"],
        }}
        dataSource={benchmarks}
        bordered={false}
        footer={null}
        virtual
        onRow={(record, rowIndex) => {
          return {
            onClick: async (event) => {
              if (record.status != "processing") {
                router.push(`/modelRepo/benchmarks-history/${record.id}`);
                setSelectedBenchmark(record);
              }
            },
          };
        }}
        onChange={(
          pagination,
          filters,
          sorter: {
            order: "ascend" | "descend";
            field: string;
          },
          extra,
        ) => {
          setOrder(sorter.order === "ascend" ? "" : "-");
          setOrderBy(sorter.field);
        }}
        showSorterTooltip={true}
        title={() => (
          <div>
            {showTableTitle && (
              <div className="flex justify-between items-center px-[0.75rem] py-[1rem]">
                <div></div>
                <div className="flex items-center justify-between gap-x-[0rem]">
                  <SearchHeaderInput
                    classNames="mr-[1rem]"
                    placeholder="Search by name or tags"
                    searchValue={filter.benchmarkName || ""}
                    setSearchValue={(value) => {
                      setFilter({ ...filter, benchmarkName: value });
                    }}
                  />
                  <Popover
                    open={filterOpen}
                    onOpenChange={handleOpenChange}
                    placement="left"
                    content={
                      <div className="bg-[#111113] shadow-none  border border-[#1F1F1F] rounded-[6px] width-348">
                        <div className="p-[1.5rem] flex items-start justify-start flex-col">
                          <div className="text-[#FFFFFF] text-14 font-400">
                            Filter
                          </div>
                          <div className="text-12 font-400 text-[#757575]">
                            Apply the following filters to find benchmark of
                            your choice.
                          </div>
                        </div>
                        <div className="height-1 bg-[#1F1F1F] mb-[1.5rem] w-full"></div>
                        <div className="w-full flex flex-col gap-size-20 px-[1.5rem] pb-[1.5rem]">
                          <div className="w-full flex flex-col gap-size-20 pt-[.5rem] max-h-[40vh] overflow-y-auto scroll-smooth">
                            <div
                              className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]`}
                            >
                              <div className="w-full">
                                <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap">
                                  Status
                                  <CustomPopover title="Select benchmark status">
                                    <Image
                                      src="/images/info.png"
                                      preview={false}
                                      alt="info"
                                      style={{
                                        width: ".75rem",
                                        height: ".75rem",
                                      }}
                                    />
                                  </CustomPopover>
                                </Text_12_300_EEEEEE>
                              </div>
                              <div className="custom-select-two w-full rounded-[6px] relative">
                                <ConfigProvider
                                  theme={{
                                    token: {
                                      colorTextPlaceholder: "#808080",
                                      boxShadowSecondary: "none",
                                    },
                                  }}
                                >
                                  <Select
                                    variant="borderless"
                                    placeholder="Select status"
                                    style={{
                                      backgroundColor: "transparent",
                                      color: "#EEEEEE",
                                      border: "0.5px solid #757575",
                                      width: "100%",
                                    }}
                                    value={tempFilter.status || undefined}
                                    size="large"
                                    className="drawerInp !bg-[transparent] text-[#EEEEEE] py-[.6rem] font-[300]  text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] h-[2.5rem] outline-none"
                                    options={[
                                      { label: "Success", value: "success" },
                                      { label: "Failed", value: "failed" },
                                      {
                                        label: "Processing",
                                        value: "processing",
                                      },
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
                                        ></Tags>
                                      );
                                    }}
                                  />
                                </ConfigProvider>
                              </div>
                            </div>
                            <div
                              className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]`}
                            >
                              <div className="w-full">
                                <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap">
                                  Model Name
                                  <CustomPopover title="Select model name">
                                    <Image
                                      src="/images/info.png"
                                      preview={false}
                                      alt="info"
                                      style={{
                                        width: ".75rem",
                                        height: ".75rem",
                                      }}
                                    />
                                  </CustomPopover>
                                </Text_12_300_EEEEEE>
                              </div>
                              <div className="custom-select-two w-full rounded-[6px] relative">
                                <ConfigProvider
                                  theme={{
                                    token: {
                                      colorTextPlaceholder: "#808080",
                                      boxShadowSecondary: "none",
                                    },
                                  }}
                                >
                                  <Select
                                    variant="borderless"
                                    placeholder="Select model name"
                                    style={{
                                      backgroundColor: "transparent",
                                      color: "#EEEEEE",
                                      border: "0.5px solid #757575",
                                      width: "100%",
                                    }}
                                    value={tempFilter.model_name || undefined}
                                    size="large"
                                    className="drawerInp !bg-[transparent] text-[#EEEEEE] py-[.6rem] font-[300]  text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] h-[2.5rem] outline-none"
                                    options={modelFilterList?.map((item) => ({
                                      label: item,
                                      value: item,
                                    }))}
                                    onChange={(value) => {
                                      setTempFilter({
                                        ...tempFilter,
                                        model_name: value,
                                      });
                                    }}
                                    tagRender={(props) => {
                                      const { label } = props;
                                      return (
                                        <Tags
                                          name={label}
                                          color="#D1B854"
                                        ></Tags>
                                      );
                                    }}
                                  />
                                </ConfigProvider>
                              </div>
                            </div>
                            <div
                              className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]`}
                            >
                              <div className="w-full">
                                <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap">
                                  Cluster Name
                                  <CustomPopover title="Select cluster name">
                                    <Image
                                      src="/images/info.png"
                                      preview={false}
                                      alt="info"
                                      style={{
                                        width: ".75rem",
                                        height: ".75rem",
                                      }}
                                    />
                                  </CustomPopover>
                                </Text_12_300_EEEEEE>
                              </div>
                              <div className="custom-select-two w-full rounded-[6px] relative">
                                <ConfigProvider
                                  theme={{
                                    token: {
                                      colorTextPlaceholder: "#808080",
                                      boxShadowSecondary: "none",
                                    },
                                  }}
                                >
                                  <Select
                                    variant="borderless"
                                    placeholder="Select cluster name"
                                    style={{
                                      backgroundColor: "transparent",
                                      color: "#EEEEEE",
                                      border: "0.5px solid #757575",
                                      width: "100%",
                                    }}
                                    value={tempFilter.cluster_name || undefined}
                                    size="large"
                                    className="drawerInp !bg-[transparent] text-[#EEEEEE] py-[.6rem] font-[300]  text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] h-[2.5rem] outline-none"
                                    options={clusterFilterList?.map((item) => ({
                                      label: item,
                                      value: item,
                                    }))}
                                    onChange={(value) => {
                                      setTempFilter({
                                        ...tempFilter,
                                        cluster_name: value,
                                      });
                                    }}
                                    tagRender={(props) => {
                                      const { label } = props;
                                      return (
                                        <Tags
                                          name={label}
                                          color="#D1B854"
                                        ></Tags>
                                      );
                                    }}
                                  />
                                </ConfigProvider>
                              </div>
                            </div>
                            <div
                              className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]`}
                            >
                              <div className="w-full">
                                <Text_12_300_EEEEEE className="absolute px-1.4 tracking-[.035rem] flex items-center gap-1 text-nowrap">
                                  TPOT
                                  <CustomPopover title="The minimum and maximum of tpot.">
                                    <Image
                                      preview={false}
                                      src="/images/info.png"
                                      alt="info"
                                      style={{
                                        width: ".75rem",
                                        height: ".75rem",
                                      }}
                                    />
                                  </CustomPopover>
                                </Text_12_300_EEEEEE>
                                <div className="flex items-center justify-center">
                                  <div className="text-[#757575] text-[.75rem] h-[4px] mr-1  leading-8">
                                    1
                                  </div>
                                  <Slider
                                    className="budSlider mt-[3.2rem] w-full"
                                    min={0}
                                    max={500}
                                    step={1}
                                    range
                                    defaultValue={[
                                      tempFilter.min_tpot || undefined,
                                      tempFilter.max_tpot || undefined,
                                    ]}
                                    onChange={(value) => {
                                      setTempFilter({
                                        ...tempFilter,
                                        min_tpot: value[0],
                                        max_tpot: value[1],
                                      });
                                    }}
                                    tooltip={{
                                      open: true,
                                      getPopupContainer: (trigger) =>
                                        (trigger.parentNode as HTMLElement) ||
                                        document.body, // Cast parentNode to HTMLElement
                                    }}
                                    styles={{
                                      track: {
                                        backgroundColor: "#965CDE",
                                      },
                                      rail: {
                                        backgroundColor: "#212225",
                                        height: 4,
                                      },
                                    }}
                                  />
                                  <div className="text-[#757575] text-[.75rem] h-[4px] ml-1 leading-8">
                                    500
                                  </div>
                                </div>
                              </div>
                            </div>
                            <div
                              className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]`}
                            >
                              <div className="w-full">
                                <Text_12_300_EEEEEE className="absolute px-1.4 tracking-[.035rem] flex items-center gap-1 text-nowrap">
                                  TTFT
                                  <CustomPopover title="The minimum and maximum of ttft.">
                                    <Image
                                      preview={false}
                                      src="/images/info.png"
                                      alt="info"
                                      style={{
                                        width: ".75rem",
                                        height: ".75rem",
                                      }}
                                    />
                                  </CustomPopover>
                                </Text_12_300_EEEEEE>
                                <div className="flex items-center justify-center">
                                  <div className="text-[#757575] text-[.75rem] h-[4px] mr-1  leading-8">
                                    1
                                  </div>
                                  <Slider
                                    className="budSlider mt-[3.2rem] w-full"
                                    min={0}
                                    max={500}
                                    step={1}
                                    range
                                    defaultValue={[
                                      tempFilter.min_ttft || undefined,
                                      tempFilter.max_ttft || undefined,
                                    ]}
                                    onChange={(value) => {
                                      setTempFilter({
                                        ...tempFilter,
                                        min_ttft: value[0],
                                        max_ttft: value[1],
                                      });
                                    }}
                                    tooltip={{
                                      open: true,
                                      getPopupContainer: (trigger) =>
                                        (trigger.parentNode as HTMLElement) ||
                                        document.body, // Cast parentNode to HTMLElement
                                    }}
                                    styles={{
                                      track: {
                                        backgroundColor: "#965CDE",
                                      },
                                      rail: {
                                        backgroundColor: "#212225",
                                        height: 4,
                                      },
                                    }}
                                  />
                                  <div className="text-[#757575] text-[.75rem] h-[4px] ml-1 leading-8">
                                    500
                                  </div>
                                </div>
                              </div>
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
                    <label
                      className="h-[1.7rem] text-[#FFFFFF] ml-0 mr-1 flex items-center cursor-pointer text-xs font-normal leading-3 rounded-[6px] shadow-none bg-transparent"
                      onClick={() => {}}
                    >
                      <MixerHorizontalIcon
                        style={{ width: "0.875rem", height: "0.875rem" }}
                        className="mr-2"
                      />
                      {/* <Text_12_400_C7C7C7>Filter</Text_12_400_C7C7C7> */}
                    </label>
                  </Popover>
                  <PrimaryButton
                    type="submit"
                    onClick={() => {
                      reset();
                      openDrawer("model_benchmark");
                    }}
                    classNames="!pr-[.8rem] tracking-[.02rem]"
                  >
                    <div className="flex items-center justify-center gap-[.2rem]">
                      Run Another Benchmark
                    </div>
                  </PrimaryButton>
                </div>
              </div>
            )}
          </div>
        )}
        locale={{
          emptyText: (
            <NoDataFount
              classNames="h-[20vh] max-w-[70vw]"
              textMessage={`No Benchmarks`}
            />
          ),
        }}
      />
    </div>
  );
};

export default BenchmarksTable;

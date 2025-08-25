"use client";
import { useRouter } from "next/router";
import React, { useCallback, useEffect, useState } from "react";
import { Text_12_300_EEEEEE, Text_12_400_EEEEEE } from "@/components/ui/text";
import { Project, useProjects } from "src/hooks/useProjects";
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
import Tags from "src/flows/components/DrawerTags";
import { CustomBreadcrumb } from "@/components/ui/bud/card/DrawerBreadCrumbNavigation";
import BackButton from "@/components/ui/bud/drawer/BackButton";
import { formatDate } from "src/utils/formatDate";
import { notification } from "antd";
import { useOverlay } from "src/context/overlayContext";
import { openWarning } from "@/components/warningMessage";
import { useEndPoints } from "src/hooks/useEndPoint";
import useHandleRouteChange from "@/lib/useHandleRouteChange";
import { PermissionEnum, useUser } from "src/stores/useUser";
import { useCluster } from "src/hooks/useCluster";
import PageHeader from "@/components/ui/pageHeader";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import CustomPopover from "src/flows/components/customPopover";
import {
  PrimaryButton,
  SecondaryButton,
} from "@/components/ui/bud/form/Buttons";
import { MixerHorizontalIcon } from "@radix-ui/react-icons";
import NoDataFount from "@/components/ui/noDataFount";
import { SortIcon } from "@/components/ui/bud/table/SortIcon";
import ProjectTags from "src/flows/components/ProjectTags";
import { capitalize } from "@/lib/utils";
import { endpointStatusMapping } from "@/lib/colorMapping";
import DashBoardLayout from "../layout";
import { useLoader } from "src/context/appContext";
import { useBenchmarks } from "src/hooks/useBenchmark";
import { IconOnlyRender } from "src/flows/components/BudIconRender";
import { usePerfomanceBenchmark } from "src/stores/usePerfomanceBenchmark";
import BenchmarksTable from "./components/BenchmarksTable";

const defaultFilter = {
  name: "",
  status: "",
  model_name: "",
  cluster_name: "",
  min_tpot: undefined,
  max_tpot: undefined,
  min_ttft: undefined,
  max_ttft: undefined,
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

const PerfomanceBenchmarks = () => {
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
  const { hasProjectPermission, hasPermission } = useUser();
  const { setOverlayVisible } = useOverlay();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState("1");
  const [isHovered, setIsHovered] = useState(false);
  const { clustersId } = router.query; // Access the dynamic part of the route
  const { openDrawer } = useDrawer();
  const {
    setSelectedProjectId,
    selectedProject: selectedProjectResult,
    deleteProject,
    setProjectValues,
    projectMembers,
    selectedProjectId,
  } = useProjects();
  const {
    clusters,
    getClusters,
    setCluster,
    loading,
    deleteCluster,
    setClusterValues,
    getClusterById,
  } = useCluster();

  const { endPointsCount } = useEndPoints();
  const [selectedProject, setProject] = useState<Project | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [filter, setFilter] = useState<{
    name?: string;
    status?: string;
    model_name?: string;
    cluster_name?: string;
    min_tpot?: number;
    max_tpot?: number;
    min_ttft?: number;
    max_ttft?: number;
  }>(defaultFilter);
  const [filterOpen, setFilterOpen] = React.useState(false);
  const [tempFilter, setTempFilter] = useState<any>({});
  const [filterReset, setFilterReset] = useState(false);
  const [order, setOrder] = useState<"-" | "">("");
  const [orderBy, setOrderBy] = useState<string>("created_at");

  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  useEffect(() => {
    console.log("modelFilterList", modelFilterList);
  }, [modelFilterList]);

  useEffect(() => {
    console.log("clusterFilterList", clusterFilterList);
  }, [clusterFilterList]);

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

  useEffect(() => {
    if (selectedProjectResult) {
      setProject(selectedProjectResult);
    }
  }, [selectedProjectResult]);

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
    load(filter);
  }, [currentPage, pageSize, getBenchmarks, filter]);

  useEffect(() => {
    if (filterReset) {
      applyFilter();
    }
  }, [filterReset]);

  const HeaderContent = () => {
    return (
      <div className="flex justify-between items-center">
        {isMounted && (
          <div className="flex justify-start items-center">
            <BackButton onClick={goBack} />
            <CustomBreadcrumb
              urls={["/modelRepo", ``, ``]}
              data={["Models", `Performance Benchmarks`]}
            />
          </div>
        )}
      </div>
    );
  };
  const triggerDeleteNotification = () => {
    let description =
      endPointsCount > 0
        ? "The deployments are running and you will not be allowed to delete the project. In order to delete the project, you will have to pause or delete all deployments in order to delete the project."
        : "There are no running deployments, you can delete the project.";
    let title =
      endPointsCount > 0
        ? "You’re not allowed to delete the Project"
        : "You’re about to delete the Project";
    const updateNotificationMessage = openWarning({
      title: title, // Replace 'entityName' with the actual value
      description: description,
      deleteDisabled: endPointsCount > 0,
      onDelete: () => {
        deleteProject(selectedProjectId, router).then((result) => {
          // deleteProject('9290dfd0-2225-4f38-bee8-9d5e89c3b7', router).then((result) => {
          if (result.success) {
            setOverlayVisible(false);
            notification.destroy(`${title}-delete-notification`);
          } else {
            updateNotificationMessage("An unknown error occurred.");
          }
        });
      },
      onCancel: () => {
        setOverlayVisible(false);
      },
    });
  };

  const handlePageChange = (currentPage, pageSize) => {
    setCurrentPage(currentPage);
    setPageSize(pageSize);
  };

  return (
    <DashBoardLayout>
      <div className="boardPageView ">
        <div className="boardPageTop pt-0 px-0 pb-[0]">
          <div className="px-[1.2rem] pt-[1.05rem] pb-[1.15rem] mb-[2.15rem] border-b-[1px] border-b-[#1F1F1F]">
            <HeaderContent />
          </div>
          <div className="px-[3.5rem] boardPageTop pt-[0]">
            <PageHeader
              headding="Performance Benchmarks"
              text="Bud Performance benchmarking tools allows model evaluation on different clusters & Nodes to check its performance on the hardware"
              buttonLabel={"Run Another Benchmark"}
              hClass=""
              buttonPermission={hasPermission(PermissionEnum.ModelManage)}
              buttonAction={() => {
                reset();
                openDrawer("model_benchmark");
                // reset();
              }}
              rightComponent={
                <>
                  <SearchHeaderInput
                    classNames="mr-[1rem]"
                    placeholder="Search by name or tags"
                    searchValue={filter.name || ""}
                    setSearchValue={(value) => {
                      setFilter({ ...filter, name: value });
                    }}
                  />

                  <Popover
                    open={filterOpen}
                    onOpenChange={handleOpenChange}
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
                      className="h-[1.7rem] text-[#FFFFFF] mx-2 flex items-center cursor-pointer text-xs font-normal leading-3 rounded-[6px] shadow-none bg-transparent"
                      onClick={() => {}}
                    >
                      <MixerHorizontalIcon
                        style={{ width: "0.875rem", height: "0.875rem" }}
                        className="mr-2"
                      />
                    </label>
                  </Popover>
                </>
              }
            />
          </div>
        </div>
        <div className="projectDetailsDiv pt-[2.6rem] ">
          <BenchmarksTable />
        </div>
      </div>
    </DashBoardLayout>
  );
};

export default PerfomanceBenchmarks;

/* eslint-disable react/no-unescaped-entities */
"use client";
import { MixerHorizontalIcon } from "@radix-ui/react-icons";
import { ConfigProvider, Image, Popover, Select, Slider, Tag } from "antd";
import { useCallback, useEffect, useState, useRef } from "react";
import React from "react";
import DashBoardLayout from "../layout";

// ui components
import {
  Text_11_400_808080,
  Text_17_600_FFFFFF,
  Text_13_400_B3B3B3,
  Text_12_400_B3B3B3,
  Text_12_600_EEEEEE,
  Text_12_300_EEEEEE,
  Text_12_400_EEEEEE,
} from "./../../../components/ui/text";
import { useLoader } from "src/context/appContext";
import PageHeader from "@/components/ui/pageHeader";
import NoAccess from "@/components/ui/noAccess";
import { useDrawer } from "src/hooks/useDrawer";
import { useDeployModel } from "src/stores/useDeployModel";
import { getChromeColor } from "@/components/ui/bud/dataEntry/TagsInputData";
import { formatDate } from "src/utils/formatDate";
import { cloudProviders, Model, useModels } from "src/hooks/useModels";
import Tags from "src/flows/components/DrawerTags";
import {
  PrimaryButton,
  SecondaryButton,
} from "@/components/ui/bud/form/Buttons";
import CustomPopover from "src/flows/components/customPopover";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import ImageIcon from "src/flows/components/ImageIcon";
import NoDataFount from "@/components/ui/noDataFount";
import ModelTags from "src/flows/components/ModelTags";
import { PermissionEnum, useUser } from "src/stores/useUser";
import IconRender from "src/flows/components/BudIconRender";
import router from "next/router";
import { PlusOutlined } from "@ant-design/icons";

function ModelCard(item: Model, index) {
  const { getModel } = useModels();
  const { openDrawer } = useDrawer();
  return (
    <div
      className="flex flex-col justify-between bg-[#101010] border border-[#1F1F1F] rounded-lg pt-[1.54em] 1680px:pt-[1.85em] min-h-[325px] 1680px:min-h-[400px] 2048px:min-h-[475px] group cursor-pointer hover:shadow-[1px_1px_6px_-1px_#2e3036] overflow-hidden"
      key={index}
      onClick={async () => {
        const result = await getModel(item.id);
        if (result) {
          openDrawer("view-model");
        }
      }}
    >
      <div className="px-[1.6rem] min-h-[230px]">
        <div className="w-[2.40125rem] h-[2.40125rem] bg-[#1F1F1F] rounded-[5px] flex items-center justify-center">
          <IconRender
            icon={item?.icon || item?.icon}
            size={26}
            imageSize={24}
            type={item.provider_type}
            model={item}
          />
        </div>
        {item?.modified_at && (
          <div className="mt-[1.2rem]">
            <Text_11_400_808080>
              {formatDate(item?.created_at)}
            </Text_11_400_808080>
          </div>
        )}
        <Text_17_600_FFFFFF
          className="max-w-[100] truncate w-[calc(100%-20px)] mt-[.4rem]"
          onClick={(e) => {
            // e.stopPropagation();
            // copy to clipboard
            // navigator.clipboard.writeText(item.name);
            // successToast("Copied to clipboard");
          }}
        >
          {item.name}
        </Text_17_600_FFFFFF>
        <Text_13_400_B3B3B3 className="mt-[.6rem] leading-[1.125rem] h-[1.25rem] tracking-[.01em] line-clamp-1 overflow-hidden display-webkit-box">
          {item?.description || ""}
        </Text_13_400_B3B3B3>

        <div className="flex items-center flex-wrap py-[1.1em]  gap-[.3rem]">
          <ModelTags model={item} maxTags={3} limit={true} />
        </div>
      </div>
      <div className="px-[1.6rem] pt-[.9rem] pb-[1rem] bg-[#161616] border-t-[.5px] border-t-[#1F1F1F] min-h-[32%]">
        <Text_12_400_B3B3B3 className="mb-[.65rem]">
          Recommended Cluster
        </Text_12_400_B3B3B3>
        {item?.model_cluster_recommended ? (
          <>
            <Text_12_600_EEEEEE className="mb-[.6rem]">
              {item?.model_cluster_recommended?.cluster?.name}
            </Text_12_600_EEEEEE>
            <div className="flex items-center justify-start">
              <Tag
                className={`text-[#B3B3B3] border-[0] rounded-[6px] cursor-pointer hover:text-[#EEEEEE] flex justify-center items-center py-[.3rem] px-[.4rem]`}
                style={{
                  backgroundColor: getChromeColor("#1F1F1F"),
                  background: "#1F1F1F",
                }}
              >
                <div
                  className={`text-[0.625rem] font-[400] leading-[100%]`}
                  style={{
                    color: "#EEEEEE",
                  }}
                >
                  {
                    item?.model_cluster_recommended?.cluster
                      ?.availability_percentage
                  }
                  % Available
                </div>
              </Tag>
              {item?.model_cluster_recommended?.hardware_type?.map(
                (resource, index) => (
                  <Tag
                    key={index}
                    className={`text-[#B3B3B3] border-[0] rounded-[6px] cursor-pointer hover:text-[#EEEEEE] flex justify-center items-center py-[.3rem] px-[.4rem]`}
                    style={{
                      backgroundColor: getChromeColor("#1F1F1F"),
                      background: "#1F1F1F",
                    }}
                  >
                    <div
                      className={`text-[0.625rem] font-[400] leading-[100%]`}
                      style={{
                        color: "#EEEEEE",
                      }}
                    >
                      {resource.toUpperCase()}
                    </div>
                  </Tag>
                ),
              )}
              <Tag
                className={`text-[#B3B3B3] border-[0] rounded-[6px] cursor-pointer hover:text-[#EEEEEE] flex justify-center items-center py-[.3rem] px-[.4rem]`}
                style={{
                  backgroundColor: getChromeColor("#1F1F1F"),
                  background: "#1F1F1F",
                }}
              >
                <div
                  className={`text-[0.625rem] font-[400] leading-[100%]`}
                  style={{
                    color: "#EEEEEE",
                  }}
                >
                  $
                  {Number(
                    item?.model_cluster_recommended?.cost_per_million_tokens,
                  ).toFixed(2)}{" "}
                  / 1M Tokens
                </div>
              </Tag>
            </div>
          </>
        ) : (
          <>
            <Tag
              className={`text-[#B3B3B3] border-[0] rounded-[6px] cursor-pointer hover:text-[#EEEEEE] justify-center items-center py-[.5rem] px-[.8rem]`}
              style={{
                backgroundColor: getChromeColor("#1F1F1F"),
                background: "#1F1F1F",
              }}
            >
              <div
                className={`text-[0.625rem] font-[400] leading-[100%]`}
                style={{
                  color: "#EEEEEE",
                }}
              >
                No data available
              </div>
            </Tag>
          </>
        )}
      </div>
    </div>
  );
}

const sourceTypes = [
  { label: "Local", value: "model" },
  { label: "Cloud", value: "cloud_model" },
];

const defaultFilter = {
  name: "",
  modality: [],
  model_size_min: undefined,
  model_size_max: undefined,
  table_source: ["model"],
};

interface Filters {
  author?: string;
  tasks?: string[];
  model_size_min?: string;
  model_size_max?: string;
  // modality?: string[];
  // Add other filter properties as needed
}

const SelectedFilters = ({
  filters,
  removeTag,
}: {
  filters: Filters;
  removeTag?: (key, item) => void;
}) => {
  return (
    <div className="flex justify-start gap-[.4rem] items-center absolute top-[.4rem] left-[3.5rem]">
      {filters?.author && (
        <Tags
          name={`Author: ${filters.author}`}
          color="#d1b854"
          closable
          onClose={() => removeTag("author", filters?.author)}
        />
      )}
      {filters?.tasks?.length > 0 &&
        filters.tasks.map((item, index) => (
          <Tags
            name={item}
            color="#d1b854"
            key={index}
            closable
            onClose={() => removeTag("tasks", item)}
          />
        ))}
      {filters?.model_size_min && (
        <Tags
          name={`Min size: ${filters.model_size_min}`}
          color="#d1b854"
          closable
          onClose={() => removeTag("model_size_min", filters.model_size_min)}
        />
      )}
      {filters?.model_size_max && (
        <Tags
          name={`Max size: ${filters.model_size_max}`}
          color="#d1b854"
          closable
          onClose={() => removeTag("model_size_max", filters.model_size_max)}
        />
      )}
      {/* {filters?.modality?.length > 0 &&
        filters.modality.map((item, index) => (
          <Tags
            name={item}
            color="#d1b854"
            key={index}
            closable
            onClose={() => removeTag("modality", item)}
          />
        ))} */}
      {/* Uncomment and update if needed
      {filters?.table_source?.length > 0 &&
        filters.table_source.map((item, index) => (
          <Tags name={item} color="#d1b854" key={index} />
        ))} */}
    </div>
  );
};

export default function ModelRepo() {
  const [isMounted, setIsMounted] = useState(false);
  const { hasPermission, loadingUser } = useUser();
  const {
    models,
    getGlobalModels,
    getTasks,
    getAuthors,
    authors,
    tasks,
    totalModels,
    totalPages,
  } = useModels();
  const { showLoader, hideLoader } = useLoader();
  const { openDrawer, openDrawerWithStep } = useDrawer();
  const { reset } = useDeployModel();

  // for pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [tempFilter, setTempFilter] = useState<any>({});
  const [filter, setFilter] = useState<{
    name?: string;
    modality?: string[];
    model_size_min?: number;
    model_size_max?: number;
    table_source?: string[];
  }>(defaultFilter);
  const [filterOpen, setFilterOpen] = React.useState(false);

  const [modalityFilters, setModalityFilters] = useState(cloudProviders);
  const [filterReset, setFilterReset] = useState(false);

  // Add refs to prevent multiple API calls
  const isLoadingMore = useRef(false);
  const lastScrollTop = useRef(0);

  const load = useCallback(
    async (filter, page?: number, isInfiniteScroll: boolean = false) => {
      if (hasPermission(PermissionEnum.ModelView)) {
        // Prevent multiple simultaneous calls for infinite scroll
        if (isInfiniteScroll && isLoadingMore.current) {
          return;
        }

        if (isInfiniteScroll) {
          isLoadingMore.current = true;
        }

        const targetPage = page !== undefined ? page : currentPage;

        if (!isInfiniteScroll) {
          showLoader();
        }

        await getGlobalModels({
          page: targetPage,
          limit: pageSize,
          name: filter.name,
          tag: filter.name,
          // description: filter.name,
          modality: filter.modality?.length > 0 ? filter.modality : undefined,
          tasks: filter.tasks?.length > 0 ? filter.tasks : undefined,
          author: filter.author?.length > 0 ? filter.author : undefined,
          model_size_min: isFinite(filter.model_size_min)
            ? filter.model_size_min
            : undefined,
          model_size_max: isFinite(filter.model_size_max)
            ? filter.model_size_max
            : undefined,
          // table_source: filter.table_source,
          table_source: "model",
        });

        if (!isInfiniteScroll) {
          hideLoader();
        }

        if (isInfiniteScroll) {
          isLoadingMore.current = false;
        }
      }
    },
    [currentPage, pageSize, getGlobalModels, hasPermission, showLoader, hideLoader],
  );

  const handleOpenChange = (open) => {
    setFilterOpen(open);
    setTempFilter(filter);
  };

  const applyFilter = () => {
    setFilterOpen(false);
    setFilter(tempFilter);
    setCurrentPage(1);
    // Reset loading state when applying filter
    isLoadingMore.current = false;
    lastScrollTop.current = 0;
    load(tempFilter, 1, false);
    setFilterReset(false);
  };

  const resetFilter = () => {
    // setFilter(defaultFilter);
    setTempFilter({ defaultFilter });
    setCurrentPage(1);
    // setFilterOpen(false);
    // load(defaultFilter);
    setFilterReset(true);
  };

  const removeSelectedTag = (key, item) => {
    if (key === "author") {
      setTempFilter({ ...tempFilter, author: "" });
    } else if (key === "model_size_max" || key === "model_size_min") {
      setTempFilter({ ...tempFilter, model_size_max: "", model_size_min: "" });
    } else {
      const filteredItems = tempFilter[key].filter(
        (element) => element != item,
      );
      setTempFilter({ ...tempFilter, [key]: filteredItems });
    }
    setFilterReset(true);
  };

  useEffect(() => {
    if (filterReset) {
      applyFilter();
    }
  }, [filterReset]);

  // Initial load
  useEffect(() => {
    if (isMounted && hasPermission(PermissionEnum.ModelView)) {
      getTasks();
      getAuthors();
      load(filter, 1, false);
    }
  }, [isMounted]);

  // Search with debounce
  useEffect(() => {
    if (!isMounted) return;

    // Reset loading state when search changes
    isLoadingMore.current = false;
    lastScrollTop.current = 0;

    const timer = setTimeout(() => {
      setCurrentPage(1);
      load(filter, 1, false);
    }, 500);
    return () => clearTimeout(timer);
  }, [filter.name]);

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const target = e.currentTarget;
    const scrollTop = target.scrollTop;
    const scrollHeight = target.scrollHeight;
    const clientHeight = target.clientHeight;

    // Only trigger when scrolling down
    if (scrollTop <= lastScrollTop.current) {
      lastScrollTop.current = scrollTop;
      return;
    }

    lastScrollTop.current = scrollTop;

    // Calculate if we're near the bottom (within 100px)
    const isNearBottom = scrollTop + clientHeight >= scrollHeight - 100;

    // Check if we should load more
    if (
      isNearBottom &&
      !isLoadingMore.current &&
      models.length < totalModels &&
      currentPage < totalPages
    ) {
      const nextPage = currentPage + 1;
      setCurrentPage(nextPage);
      load(filter, nextPage, true);
    }
  };

  useEffect(() => {
    setIsMounted(true);
  }, []);
  return (
    <DashBoardLayout>
      <div className="boardPageView" id="model-container">
        <div className="boardPageTop">
          <PageHeader
            headding="Models"
            buttonLabel="Model"
            buttonPermission={hasPermission(PermissionEnum.ModelManage)}
            buttonAction={() => {
              openDrawer("add-model");
              reset();
            }}
            ButtonIcon={PlusOutlined}
            rightComponent={
              hasPermission(PermissionEnum.ModelView) && (
                <div className="flex gap-x-[.2rem]">
                  <SearchHeaderInput
                    classNames="mr-[.2rem]"
                    placeholder="Search by name or tags"
                    searchValue={filter.name || ""}
                    setSearchValue={(value) => {
                      setFilter({ ...filter, name: value });
                    }}
                  />
                  <ConfigProvider
                    theme={{
                      token: {
                        sizePopupArrow: 0,
                      },
                    }}
                    getPopupContainer={(trigger) =>
                      (trigger.parentNode as HTMLElement) || document.body
                    }
                  >
                    <Popover
                      open={filterOpen}
                      onOpenChange={handleOpenChange}
                      placement="bottomRight"
                      content={
                        <div className="bg-[#111113] shadow-none  border border-[#1F1F1F] rounded-[6px] width-348">
                          <div className="p-[1.5rem] flex items-start justify-start flex-col">
                            <div className="text-[#FFFFFF] text-[0.875rem] font-400">
                              Filter
                            </div>
                            <div className="text-[0.75rem] font-400 text-[#757575]">
                              Apply the following filters to find model of your
                              choice.
                            </div>
                          </div>
                          <div className="height-1 bg-[#1F1F1F] mb-[1.5rem] w-full"></div>
                          <div className="w-full flex flex-col gap-size-20 px-[1.5rem] pb-[1.5rem]">
                            <div
                              className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]`}
                            >
                              <div className="w-full">
                                <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap">
                                  Author
                                  <CustomPopover title="This is the author">
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
                                    placeholder="Select Author"
                                    style={{
                                      backgroundColor: "transparent",
                                      color: "#EEEEEE",
                                      border: "0.5px solid #757575",
                                      width: "100%",
                                    }}
                                    value={tempFilter.author}
                                    size="large"
                                    className="drawerInp !bg-[transparent] text-[#EEEEEE] py-[.6rem] font-[300]  text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] h-[2.59338rem] outline-none"
                                    options={authors?.map((author) => ({
                                      label: author,
                                      value: author,
                                    }))}
                                    onChange={(value) => {
                                      setTempFilter({
                                        ...tempFilter,
                                        author: value,
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
                                  Task
                                  <CustomPopover title="This is the task">
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
                                    placeholder="Select Task"
                                    style={{
                                      backgroundColor: "transparent",
                                      color: "#EEEEEE",
                                      border: "0.5px solid #757575",
                                      width: "100%",
                                    }}
                                    value={tempFilter.tasks}
                                    size="large"
                                    className="drawerInp !bg-[transparent] text-[#EEEEEE] py-[.6rem] font-[300]  text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] h-[2.59338rem] outline-none"
                                    options={tasks?.map((task) => ({
                                      label: task.name,
                                      value: task.name,
                                    }))}
                                    mode="multiple"
                                    onChange={(value) => {
                                      setTempFilter({
                                        ...tempFilter,
                                        tasks: value,
                                      });
                                    }}
                                    tagRender={(props) => {
                                      const { label } = props;
                                      return (
                                        <Tags
                                          name={label}
                                          color="#D1B854"
                                          classNames="text-center	justify-center items-center"
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
                                  Model Size
                                  <CustomPopover title="The maximum input length you want the model can process.">
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
                                    min={1}
                                    max={500}
                                    step={1}
                                    range
                                    value={[
                                      tempFilter.model_size_min || 1,
                                      tempFilter.model_size_max || 500,
                                    ]}
                                    onChange={(value) => {
                                      setTempFilter({
                                        ...tempFilter,
                                        model_size_min: value[0],
                                        model_size_max: value[1],
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
                                <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1">
                                  Modality
                                  <CustomPopover title="This is the modality">
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
                                    },
                                  }}
                                >
                                  <Select
                                    placeholder="Select Modality"
                                    style={{
                                      backgroundColor: "transparent",
                                      color: "#EEEEEE",
                                      border: "0.5px solid #757575",
                                      width: "100%",
                                    }}
                                    value={tempFilter.modality}
                                    maxTagCount={2}
                                    size="large"
                                    className="drawerInp !bg-[transparent] text-[#EEEEEE] py-[.15rem] font-[300]  text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] h-[2.59338rem] outline-none"
                                    options={modalityFilters.map(
                                      (modality) => ({
                                        label: modality.label,
                                        value: modality.modality,
                                      }),
                                    )}
                                    tagRender={(props) => {
                                      const { label } = props;
                                      return (
                                        <Tags
                                          name={label}
                                          color="#D1B854"
                                        ></Tags>
                                      );
                                    }}
                                    mode="multiple"
                                    onChange={(value) => {
                                      setTempFilter({
                                        ...tempFilter,
                                        modality: value,
                                      });
                                    }}
                                  />
                                </ConfigProvider>
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
                        className="group h-[1.7rem] text-[#EEEEEE] mx-2 flex items-center cursor-pointer text-xs font-normal leading-3 rounded-[6px] shadow-none bg-transparent"
                        onClick={() => {}}
                      >
                        <MixerHorizontalIcon
                          style={{ width: "0.875rem", height: "0.875rem" }}
                          className="text-[#B3B3B3] group-hover:text-[#FFFFFF]"
                        />
                        {/* <Text_12_400_C7C7C7>Filter</Text_12_400_C7C7C7> */}
                      </label>
                    </Popover>
                  </ConfigProvider>
                  <div
                    className="group flex justtify-center items-center gap-[.1rem] mr-[.5rem] cursor-pointer"
                    onClick={() => router.push("/modelRepo/benchmarks-history")}
                  >
                    <div className="relative">
                      <Text_12_400_EEEEEE className="group-hover:text-[#FFFFFF]">
                        Benchmark history
                      </Text_12_400_EEEEEE>
                      <div className="absolute bottom-[2px] h-[1px] w-[100%] bg-[#EEEEEE] brightness-50 group-hover:brightness-100"></div>
                    </div>
                    <div>
                      <Image
                        preview={false}
                        src="/images/icons/ArrowTopRight.png"
                        style={{ width: "0.75rem" }}
                        className="transition-transform duration-200 group-hover:scale-110"
                      />
                    </div>
                  </div>
                </div>
              )
            }
          />
        </div>
        {hasPermission(PermissionEnum.ModelView) ? (
          <>
            <div
              className="boardMainContainer  listingContainer scroll-smooth pt-[2.95rem] relative"
              id="model-repo"
              onScroll={handleScroll}
            >
              <SelectedFilters
                filters={tempFilter}
                removeTag={(key, item) => {
                  removeSelectedTag(key, item);
                }}
              />
              {models?.length > 0 ? (
                <div className="grid gap-[1.1rem] grid-cols-3  1680px:mt-[1.75rem] pb-[1.1rem]">
                  <>
                    {models.map((item, index) => (
                      <ModelCard key={index} {...item} />
                    ))}
                  </>
                </div>
              ) : (
                <div>
                  <>
                    {Object.keys(filter).filter(
                      (key) =>
                        filter[key] !== undefined &&
                        filter[key] !== "" &&
                        key !== "table_source",
                    ).length > 0 ? (
                      <NoDataFount
                        classNames="h-[60vh]"
                        textMessage={`No models found for the ${
                          filter.name
                            ? `search term "${filter.name}"`
                            : "selected filters"
                        }`}
                      />
                    ) : (
                      <NoDataFount
                        classNames="h-[60vh]"
                        textMessage="Let’s start adding models to Bud Inference engine.
                        Currently there are no models in the model repository."
                      />
                    )}
                  </>
                </div>
              )}
            </div>
          </>
        ) : (
          !loadingUser && (
            <>
              <NoAccess textMessage="You do not have access to view models, please ask admin to give you access to either view or edit for models." />
            </>
          )
        )}
      </div>
    </DashBoardLayout>
  );
}

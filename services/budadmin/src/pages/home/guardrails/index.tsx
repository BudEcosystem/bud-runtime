/* eslint-disable react/no-unescaped-entities */
"use client";
import { MixerHorizontalIcon } from "@radix-ui/react-icons";
import { ConfigProvider, Image, Popover, Select, Slider, Tag } from "antd";
import { useCallback, useEffect, useState } from "react";
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
} from "../../../components/ui/text";
import { useLoader } from "src/context/appContext";
import PageHeader from "@/components/ui/pageHeader";
import NoAccess from "@/components/ui/noAccess";
import { useDrawer } from "src/hooks/useDrawer";
import { useDeployModel } from "src/stores/useDeployModel";
import { getChromeColor } from "@/components/ui/bud/dataEntry/TagsInputData";
import { formatDate } from "src/utils/formatDate";
import useGuardrails, { Probe } from "src/hooks/useGuardrails";
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
import { Spin } from "antd";

function GuardRailCard({ item, index }: { item: Probe; index: number }) {
  const { openDrawer, openDrawerWithStep } = useDrawer();
  const { setSelectedProbe } = useGuardrails();

  const getTypeIcon = (providerType: string) => {
    switch (providerType?.toLowerCase()) {
      case "bud_sentinel":
      case "bud-sentinel":
        return "🛡️";
      case "azure":
      case "azure_ai":
        return "☁️";
      case "aws":
      case "aws_bedrock":
        return "🔶";
      case "custom":
        return "⚙️";
      default:
        return "🛡️";
    }
  };

  return (
    <div
      className="flex flex-col bg-[#101010] border border-[#1F1F1F] rounded-lg p-[1.5rem] min-h-[280px] group cursor-pointer hover:shadow-[1px_1px_6px_-1px_#2e3036] hover:border-[#757575] transition-all"
      key={index}
      onClick={() => {
        setSelectedProbe(item);
        openDrawerWithStep("probe-details");
      }}
    >
      <div className="flex items-start justify-between mb-[1.25rem]">
        <div className="flex items-center gap-[1rem]">
          <div className="w-[3rem] h-[3rem] bg-[#1F1F1F] rounded-[8px] flex items-center justify-center text-[1.75rem]">
            {getTypeIcon(item.provider_type)}
          </div>
          <div className="flex-1">
            <Text_17_600_FFFFFF className="mb-[0.25rem] line-clamp-1">
              {item.name}
            </Text_17_600_FFFFFF>
            {item.provider_name && (
              <Text_12_400_B3B3B3>by {item.provider_name}</Text_12_400_B3B3B3>
            )}
          </div>
        </div>
      </div>

      {item.is_custom !== undefined && (
        <div className="flex items-center gap-[0.5rem] mb-[1.25rem]">
          {item.is_custom && (
            <span className="text-[10px] px-[0.5rem] py-[0.125rem] bg-[#965CDE20] text-[#965CDE] rounded-[4px]">
              Custom
            </span>
          )}
          {item.rule_count !== undefined && (
            <span className="text-[10px] px-[0.5rem] py-[0.125rem] bg-[#1F1F1F] text-[#B3B3B3] rounded-[4px]">
              {item.rule_count} rules
            </span>
          )}
        </div>
      )}
      {item.description && (
        <Text_13_400_B3B3B3 className="mb-[1.25rem] line-clamp-3 leading-[1.4]">
          {item.description}
        </Text_13_400_B3B3B3>
      )}

      <div className="flex items-center justify-between mt-auto pt-[1rem] border-t border-[#1F1F1F]">
        <div className="flex items-center gap-[0.5rem] flex-wrap">
          {item.tags &&
            item.tags.slice(0, 3).map((tag, idx) => (
              <Tag
                key={idx}
                className="text-[#B3B3B3] border-[0] rounded-[6px] flex items-center px-[0.75rem] py-[0.375rem]"
                style={{
                  backgroundColor: tag.color + "20" || "#1F1F1F",
                  color: tag.color || "#B3B3B3",
                }}
              >
                <span className="text-[0.75rem] font-[400]">{tag.name}</span>
              </Tag>
            ))}
          {item.tags && item.tags.length > 3 && (
            <Tag
              className="text-[#757575] border-[0] rounded-[6px] flex items-center px-[0.75rem] py-[0.375rem]"
              style={{
                backgroundColor: "#1F1F1F",
              }}
            >
              <span className="text-[0.75rem] font-[400]">
                +{item.tags.length - 3}
              </span>
            </Tag>
          )}
        </div>
      </div>
    </div>
  );
}

const providerTypes = [
  { label: "Bud Sentinel", value: "bud-sentinel" },
  { label: "Azure AI", value: "azure-ai" },
  { label: "AWS Bedrock", value: "aws-bedrock" },
  { label: "Custom", value: "custom" },
];

const guardRailTypes = [
  { label: "PII Detection", value: "pii" },
  { label: "Jailbreak Protection", value: "jailbreak" },
  { label: "Toxicity Filter", value: "toxicity" },
  { label: "Bias Detection", value: "bias" },
  { label: "Profanity Filter", value: "profanity" },
  { label: "Custom Regex", value: "regex" },
];

const modalityTypes = [
  { label: "Text", value: "text" },
  { label: "Image", value: "image" },
  { label: "Audio", value: "audio" },
  { label: "Code", value: "code" },
  { label: "Video", value: "video" },
];

const defaultFilter = {
  name: "",
  provider: [],
  guardRailType: [],
  modality: [],
  status: [],
};

interface GuardRailFilters {
  name?: string;
  provider?: string[];
  guardRailType?: string[];
  modality?: string[];
  status?: string[];
}

const SelectedFilters = ({
  filters,
  removeTag,
}: {
  filters: GuardRailFilters;
  removeTag?: (key, item) => void;
}) => {
  return (
    <div className="flex justify-start gap-[.4rem] items-center absolute top-[.4rem] left-[3.5rem]">
      {filters?.provider?.length > 0 &&
        filters.provider.map((item, index) => (
          <Tags
            name={`Provider: ${item}`}
            color="#965CDE"
            key={index}
            closable
            onClose={() => removeTag("provider", item)}
          />
        ))}
      {filters?.guardRailType?.length > 0 &&
        filters.guardRailType.map((item, index) => (
          <Tags
            name={`Type: ${item}`}
            color="#965CDE"
            key={index}
            closable
            onClose={() => removeTag("guardRailType", item)}
          />
        ))}
      {filters?.modality?.length > 0 &&
        filters.modality.map((item, index) => (
          <Tags
            name={`Modality: ${item}`}
            color="#965CDE"
            key={index}
            closable
            onClose={() => removeTag("modality", item)}
          />
        ))}
      {filters?.status?.length > 0 &&
        filters.status.map((item, index) => (
          <Tags
            name={`Status: ${item}`}
            color="#965CDE"
            key={index}
            closable
            onClose={() => removeTag("status", item)}
          />
        ))}
    </div>
  );
};

export default function GuardRails() {
  const [isMounted, setIsMounted] = useState(false);
  const { hasPermission, loadingUser } = useUser();
  const { showLoader, hideLoader } = useLoader();
  const { openDrawer, openDrawerWithStep } = useDrawer();
  const { reset } = useDeployModel();

  // Use guardrails hook for API integration
  const { clearWorkflow } = useGuardrails();
  const {
    probes,
    probesLoading,
    probesError,
    totalProbes,
    currentPage,
    pageSize,
    totalPages,
    fetchProbes,
    setCurrentPage,
    setPageSize,
    setSearchTerm,
    searchTerm,
    selectedTags,
    setSelectedTags,
  } = useGuardrails();

  // State for guardrails
  const [selectedCategory, setSelectedCategory] = useState<string>("all");

  // for filters
  const [tempFilter, setTempFilter] = useState<GuardRailFilters>({});
  const [filter, setFilter] = useState<GuardRailFilters>(defaultFilter);
  const [filterOpen, setFilterOpen] = React.useState(false);
  const [filterReset, setFilterReset] = useState(false);

  const load = useCallback(
    async (filter: GuardRailFilters) => {
      if (hasPermission(PermissionEnum.ModelView)) {
        // Build API params from filter
        const params: any = {
          page: currentPage,
          page_size: pageSize,
        };

        if (filter.name) {
          params.search = filter.name;
        }

        if (filter.provider && filter.provider.length > 0) {
          // Map frontend provider values to API provider_type values
          const providerMapping: Record<string, string> = {
            "bud-sentinel": "bud_sentinel",
            "azure-ai": "azure",
            "aws-bedrock": "aws",
            custom: "custom",
          };
          const mappedProviders = filter.provider.map(
            (p) => providerMapping[p] || p,
          );
          params.provider_type = mappedProviders.join(",");
        }

        // Fetch probes from API
        await fetchProbes(params);
      }
    },
    [hasPermission, currentPage, pageSize, fetchProbes],
  );

  const handleOpenChange = (open) => {
    setFilterOpen(open);
    setTempFilter(filter);
  };

  const applyFilter = () => {
    setFilterOpen(false);
    setFilter(tempFilter);
    setCurrentPage(1);
    load(tempFilter);
    setFilterReset(false);
  };

  const resetFilter = () => {
    // setFilter(defaultFilter);
    setTempFilter(defaultFilter);
    setCurrentPage(1);
    // setFilterOpen(false);
    // load(defaultFilter);
    setFilterReset(true);
  };

  const removeSelectedTag = (key: string, item: string) => {
    if (
      key === "provider" ||
      key === "guardRailType" ||
      key === "modality" ||
      key === "status"
    ) {
      const filteredItems =
        tempFilter[key]?.filter((element) => element !== item) || [];
      setTempFilter({ ...tempFilter, [key]: filteredItems });
    }
    setFilterReset(true);
  };

  useEffect(() => {
    if (filterReset) {
      applyFilter();
    }
  }, [filterReset]);

  useEffect(() => {
    // debounce search
    const timer = setTimeout(() => {
      load(filter);
    }, 500);
    return () => clearTimeout(timer);
  }, [filter.name]);

  useEffect(() => {
    // Load initial data
    if (isMounted) {
      load(filter);
    }
  }, [currentPage, pageSize, filter, isMounted, load]);

  useEffect(() => {
    setIsMounted(true);
  }, []);
  return (
    <DashBoardLayout>
      <div className="boardPageView" id="model-container">
        <div className="boardPageTop">
          <PageHeader
            headding="Guard Rails"
            buttonLabel="Add Guardrail"
            buttonPermission={hasPermission(PermissionEnum.ModelManage)}
            buttonAction={() => {
              clearWorkflow(); // Clear any existing workflow state
              openDrawer("add-guardrail");
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
                        <div className="bg-[#111113] shadow-none border border-[#1F1F1F] rounded-[6px] width-348">
                          <div className="p-[1.5rem] flex items-start justify-start flex-col">
                            <div className="text-[#FFFFFF] text-[0.875rem] font-400">
                              Filter
                            </div>
                            <div className="text-[0.75rem] font-400 text-[#757575]">
                              Apply the following filters to find guardrails of
                              your choice.
                            </div>
                          </div>
                          <div className="height-1 bg-[#1F1F1F] mb-[1.5rem] w-full"></div>
                          <div className="w-full flex flex-col gap-size-20 px-[1.5rem] pb-[1.5rem]">
                            {/* Provider Filter */}
                            <div
                              className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]`}
                            >
                              <div className="w-full">
                                <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap">
                                  Provider
                                  <CustomPopover title="Filter by guardrail provider">
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
                                    placeholder="Select Provider"
                                    style={{
                                      backgroundColor: "transparent",
                                      color: "#EEEEEE",
                                      border: "0.5px solid #757575",
                                      width: "100%",
                                    }}
                                    value={tempFilter.provider}
                                    size="large"
                                    mode="multiple"
                                    className="drawerInp !bg-[transparent] text-[#EEEEEE] py-[.6rem] font-[300] text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] h-[2.59338rem] outline-none"
                                    options={providerTypes}
                                    onChange={(value) => {
                                      setTempFilter({
                                        ...tempFilter,
                                        provider: value,
                                      });
                                    }}
                                    tagRender={(props) => {
                                      const { label } = props;
                                      return (
                                        <Tags
                                          name={label}
                                          color="#965CDE"
                                        ></Tags>
                                      );
                                    }}
                                  />
                                </ConfigProvider>
                              </div>
                            </div>

                            {/* GuardRail Type Filter */}
                            <div
                              className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]`}
                            >
                              <div className="w-full">
                                <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap">
                                  GuardRail Type
                                  <CustomPopover title="Filter by guardrail functionality">
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
                                    placeholder="Select GuardRail Type"
                                    style={{
                                      backgroundColor: "transparent",
                                      color: "#EEEEEE",
                                      border: "0.5px solid #757575",
                                      width: "100%",
                                    }}
                                    value={tempFilter.guardRailType}
                                    size="large"
                                    mode="multiple"
                                    className="drawerInp !bg-[transparent] text-[#EEEEEE] py-[.6rem] font-[300] text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] h-[2.59338rem] outline-none"
                                    options={guardRailTypes}
                                    onChange={(value) => {
                                      setTempFilter({
                                        ...tempFilter,
                                        guardRailType: value,
                                      });
                                    }}
                                    tagRender={(props) => {
                                      const { label } = props;
                                      return (
                                        <Tags
                                          name={label}
                                          color="#965CDE"
                                        ></Tags>
                                      );
                                    }}
                                  />
                                </ConfigProvider>
                              </div>
                            </div>

                            {/* Modality Filter */}
                            <div
                              className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]`}
                            >
                              <div className="w-full">
                                <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1">
                                  Modality
                                  <CustomPopover title="Filter by supported data types">
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
                                    mode="multiple"
                                    className="drawerInp !bg-[transparent] text-[#EEEEEE] py-[.15rem] font-[300] text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] h-[2.59338rem] outline-none"
                                    options={modalityTypes}
                                    onChange={(value) => {
                                      setTempFilter({
                                        ...tempFilter,
                                        modality: value,
                                      });
                                    }}
                                    tagRender={(props) => {
                                      const { label } = props;
                                      return (
                                        <Tags
                                          name={label}
                                          color="#965CDE"
                                        ></Tags>
                                      );
                                    }}
                                  />
                                </ConfigProvider>
                              </div>
                            </div>

                            {/* Status Filter */}
                            <div
                              className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]`}
                            >
                              <div className="w-full">
                                <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1">
                                  Status
                                  <CustomPopover title="Filter by guardrail status">
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
                                    placeholder="Select Status"
                                    style={{
                                      backgroundColor: "transparent",
                                      color: "#EEEEEE",
                                      border: "0.5px solid #757575",
                                      width: "100%",
                                    }}
                                    value={tempFilter.status}
                                    size="large"
                                    mode="multiple"
                                    className="drawerInp !bg-[transparent] text-[#EEEEEE] py-[.15rem] font-[300] text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] h-[2.59338rem] outline-none"
                                    options={[
                                      { label: "Active", value: "active" },
                                      { label: "Inactive", value: "inactive" },
                                      { label: "Pending", value: "pending" },
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
                                          color="#965CDE"
                                        ></Tags>
                                      );
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
                </div>
              )
            }
          />
        </div>
        {hasPermission(PermissionEnum.ModelView) ? (
          <>
            <div
              className="boardMainContainer listingContainer scroll-smooth pt-[1rem] relative"
              id="guardrails-container"
            >
              {/* Category Filter Tags */}
              <div className="flex items-center gap-[0.75rem] mb-[2rem] px-[1.5rem]">
                <Tags
                  name="All"
                  color={selectedCategory === "all" ? "#FFFFFF" : "#B3B3B3"}
                  textClass={selectedCategory === "all" ? "!text-white" : ""}
                  classNames={`cursor-pointer px-[1rem] py-[0.5rem] rounded-[6px] transition-all ${
                    selectedCategory === "all"
                      ? "!bg-[#965CDE]"
                      : "!bg-transparent border-[0.5px] border-[#757575] hover:border-[#965CDE]"
                  }`}
                  onTagClick={() => setSelectedCategory("all")}
                />
                <Tags
                  name="Harm"
                  color={selectedCategory === "harm" ? "#FFFFFF" : "#B3B3B3"}
                  textClass={selectedCategory === "harm" ? "!text-white" : ""}
                  classNames={`cursor-pointer px-[1rem] py-[0.5rem] rounded-[6px] transition-all ${
                    selectedCategory === "harm"
                      ? "!bg-[#965CDE]"
                      : "!bg-transparent border-[0.5px] border-[#757575] hover:border-[#965CDE]"
                  }`}
                  onTagClick={() => setSelectedCategory("harm")}
                />
                <Tags
                  name="Jailbreak"
                  color={
                    selectedCategory === "jailbreak" ? "#FFFFFF" : "#B3B3B3"
                  }
                  textClass={
                    selectedCategory === "jailbreak" ? "!text-white" : ""
                  }
                  classNames={`cursor-pointer px-[1rem] py-[0.5rem] rounded-[6px] transition-all ${
                    selectedCategory === "jailbreak"
                      ? "!bg-[#965CDE]"
                      : "!bg-transparent border-[0.5px] border-[#757575] hover:border-[#965CDE]"
                  }`}
                  onTagClick={() => setSelectedCategory("jailbreak")}
                />
                <Tags
                  name="Toxic"
                  color={selectedCategory === "toxic" ? "#FFFFFF" : "#B3B3B3"}
                  textClass={selectedCategory === "toxic" ? "!text-white" : ""}
                  classNames={`cursor-pointer px-[1rem] py-[0.5rem] rounded-[6px] transition-all ${
                    selectedCategory === "toxic"
                      ? "!bg-[#965CDE]"
                      : "!bg-transparent border-[0.5px] border-[#757575] hover:border-[#965CDE]"
                  }`}
                  onTagClick={() => setSelectedCategory("toxic")}
                />
                <Tags
                  name="Bias"
                  color={selectedCategory === "bias" ? "#FFFFFF" : "#B3B3B3"}
                  textClass={selectedCategory === "bias" ? "!text-white" : ""}
                  classNames={`cursor-pointer px-[1rem] py-[0.5rem] rounded-[6px] transition-all ${
                    selectedCategory === "bias"
                      ? "!bg-[#965CDE]"
                      : "!bg-transparent border-[0.5px] border-[#757575] hover:border-[#965CDE]"
                  }`}
                  onTagClick={() => setSelectedCategory("bias")}
                />
                <Tags
                  name="Compliance"
                  color={
                    selectedCategory === "compliance" ? "#FFFFFF" : "#B3B3B3"
                  }
                  textClass={
                    selectedCategory === "compliance" ? "!text-white" : ""
                  }
                  classNames={`cursor-pointer px-[1rem] py-[0.5rem] rounded-[6px] transition-all ${
                    selectedCategory === "compliance"
                      ? "!bg-[#965CDE]"
                      : "!bg-transparent border-[0.5px] border-[#757575] hover:border-[#965CDE]"
                  }`}
                  onTagClick={() => setSelectedCategory("compliance")}
                />
                <Tags
                  name="Custom"
                  color={selectedCategory === "custom" ? "#FFFFFF" : "#B3B3B3"}
                  textClass={selectedCategory === "custom" ? "!text-white" : ""}
                  classNames={`cursor-pointer px-[1rem] py-[0.5rem] rounded-[6px] transition-all ${
                    selectedCategory === "custom"
                      ? "!bg-[#965CDE]"
                      : "!bg-transparent border-[0.5px] border-[#757575] hover:border-[#965CDE]"
                  }`}
                  onTagClick={() => setSelectedCategory("custom")}
                />
              </div>

              {/* GuardRails Grid */}
              {probesLoading ? (
                <div className="flex justify-center items-center h-[50vh]">
                  <Spin size="large" />
                </div>
              ) : (
                (() => {
                  // Filter probes by selected category
                  const filteredProbes =
                    selectedCategory === "all"
                      ? probes
                      : probes.filter((probe) =>
                          probe.tags?.some(
                            (tag) =>
                              tag.name.toLowerCase() ===
                              selectedCategory.toLowerCase(),
                          ),
                        );

                  return filteredProbes && filteredProbes.length > 0 ? (
                    <>
                      <div className="grid gap-[1.5rem] grid-cols-3 pb-[1.5rem] px-[1.5rem]">
                        {filteredProbes.map((item, index) => (
                          <GuardRailCard
                            key={item.id}
                            item={item}
                            index={index}
                          />
                        ))}
                      </div>

                      {/* Pagination */}
                      {totalPages > 1 && (
                        <div className="flex justify-center items-center gap-[1rem] py-[2rem] border-t border-[#1F1F1F]">
                          <button
                            onClick={() =>
                              setCurrentPage(Math.max(1, currentPage - 1))
                            }
                            disabled={currentPage === 1}
                            className="px-[1rem] py-[0.5rem] bg-[#1F1F1F] text-[#EEEEEE] rounded-[6px] hover:bg-[#2A2A2A] disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            Previous
                          </button>
                          <span className="text-[#B3B3B3]">
                            Page {currentPage} of {totalPages}
                          </span>
                          <button
                            onClick={() =>
                              setCurrentPage(
                                Math.min(totalPages, currentPage + 1),
                              )
                            }
                            disabled={currentPage === totalPages}
                            className="px-[1rem] py-[0.5rem] bg-[#1F1F1F] text-[#EEEEEE] rounded-[6px] hover:bg-[#2A2A2A] disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            Next
                          </button>
                        </div>
                      )}
                    </>
                  ) : (
                    <NoDataFount
                      classNames="h-[50vh]"
                      textMessage={
                        selectedCategory === "all"
                          ? "No guardrails found"
                          : `No guardrails found for the "${selectedCategory}" category`
                      }
                    />
                  );
                })()
              )}
            </div>
          </>
        ) : (
          !loadingUser && (
            <>
              <NoAccess textMessage="You do not have access to view guardrails, please ask admin to give you access to either view or edit for guardrails." />
            </>
          )
        )}
      </div>
    </DashBoardLayout>
  );
}

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

interface GuardRail {
  id: string;
  name: string;
  type: string;
  category: string[];
  description?: string;
  provider?: string;
  deployments?: number;
  status?: "active" | "inactive" | "pending";
  createdAt?: string;
  icon?: string;
}

function GuardRailCard({ item, index }: { item: GuardRail; index: number }) {
  const { openDrawer, openDrawerWithStep } = useDrawer();
  const [descriptionPopoverOpen, setDescriptionPopoverOpen] = useState(false);

  // Check if description is long enough to need "See more" (approximately 3 lines worth)
  const needsSeeMore = item.description && item.description.length > 150;

  const getTypeIcon = (type: string) => {
    switch(type) {
      case 'pii':
        return '🔒';
      case 'regex':
        return '📝';
      case 'toxicity':
        return '⚠️';
      case 'bias':
        return '⚖️';
      case 'jailbreak':
        return '🚫';
      case 'custom':
        return '⚙️';
      case 'profanity':
        return '🤬';
      case 'semantic':
        return '🧠';
      default:
        return '🛡️';
    }
  };

  const getStatusColor = (status?: string) => {
    switch(status) {
      case 'active':
        return '#52C41A';
      case 'inactive':
        return '#757575';
      case 'pending':
        return '#FAAD14';
      default:
        return '#757575';
    }
  };

  return (
    <div
      className="flex flex-col bg-[#101010] border border-[#1F1F1F] rounded-lg p-[1.5rem] min-h-[280px] group cursor-pointer hover:shadow-[1px_1px_6px_-1px_#2e3036] hover:border-[#757575] transition-all"
      key={index}
      onClick={() => {
        openDrawer("view-guardrail-details", { guardrail: item });
      }}
    >
      <div className="flex items-start justify-between mb-[1.25rem]">
        <div className="flex items-center gap-[1rem]">
          <div className="w-[3rem] h-[3rem] bg-[#1F1F1F] rounded-[8px] flex items-center justify-center text-[1.75rem]">
            {getTypeIcon(item.type)}
          </div>
          <div className="flex-1">
            <Text_17_600_FFFFFF className="mb-[0.25rem] line-clamp-1">
              {item.name}
            </Text_17_600_FFFFFF>
            {item.provider && (
              <Text_12_400_B3B3B3>
                by {item.provider}
              </Text_12_400_B3B3B3>
            )}
          </div>
        </div>
        {item.status && (
          <div
            className="w-[10px] h-[10px] rounded-full shrink-0"
            style={{ backgroundColor: getStatusColor(item.status) }}
            title={item.status}
          />
        )}
      </div>

      {item.description && (
        <div className="mb-[1.25rem] relative">
          <div
            className="line-clamp-3 overflow-hidden"
            style={{
              display: "-webkit-box",
              WebkitBoxOrient: "vertical",
              WebkitLineClamp: 3
            }}
          >
            <Text_13_400_B3B3B3 className="leading-[1.4]">
              {item.description}
            </Text_13_400_B3B3B3>
          </div>
          {needsSeeMore && (
            <ConfigProvider
              theme={{
                token: {
                  sizePopupArrow: 0,
                },
              }}
            >
              <Popover
                content={
                  <div className="max-w-[400px] p-[1rem] bg-[#111113] border border-[#1F1F1F] rounded-[6px]">
                    <Text_13_400_B3B3B3 className="leading-[1.4] whitespace-pre-wrap">
                      {item.description}
                    </Text_13_400_B3B3B3>
                  </div>
                }
                trigger="click"
                open={descriptionPopoverOpen}
                onOpenChange={setDescriptionPopoverOpen}
                placement="top"
                rootClassName="guardrail-description-popover"
                getPopupContainer={(trigger) =>
                  (trigger.parentNode as HTMLElement) || document.body
                }
              >
                <Text_12_600_EEEEEE
                  className="cursor-pointer mt-[0.5rem] inline-block hover:text-[#965CDE] transition-colors"
                  onClick={(e: React.MouseEvent) => {
                    e.stopPropagation();
                  }}
                >
                  See more
                </Text_12_600_EEEEEE>
              </Popover>
            </ConfigProvider>
          )}
        </div>
      )}

      <div className="flex items-center justify-between mt-auto pt-[1rem] border-t border-[#1F1F1F]">
        <div className="flex items-center gap-[0.5rem] flex-wrap">
          {item.category.slice(0, 3).map((cat, idx) => (
            <Tags
              name={cat}
              color="#1F1F1F"
              key={idx}
            />
          ))}
          {item.category.length > 3 && (
            <Tags
              name={`+${item.category.length - 3}`}
              color="#1F1F1F"
            />
          )}
        </div>
        {item.deployments !== undefined && (
          <Text_12_400_B3B3B3 className="shrink-0">
            {item.deployments} {item.deployments === 1 ? 'deploy' : 'deploys'}
          </Text_12_400_B3B3B3>
        )}
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

// Dummy guardrail data
const dummyGuardRails: GuardRail[] = [
  {
    id: "1",
    name: "PII Detection",
    type: "pii",
    category: ["harm", "compliance", "privacy"],
    description: "Detects and masks personal identifiable information including SSN, credit cards, emails, phone numbers",
    provider: "Bud Sentinel",
    deployments: 12,
    status: "active"
  },
  {
    id: "2",
    name: "Jailbreak Protection",
    type: "jailbreak",
    category: ["jailbreak", "security"],
    description: "Prevents prompt injection and jailbreak attempts to bypass model safety guidelines",
    provider: "Bud Sentinel",
    deployments: 8,
    status: "active"
  },
  {
    id: "3",
    name: "Toxicity Filter",
    type: "toxicity",
    category: ["toxic", "harm", "content"],
    description: "Filters out toxic, harmful, and inappropriate content from model responses",
    provider: "Bud Sentinel",
    deployments: 15,
    status: "active"
  },
  {
    id: "4",
    name: "Bias Detection",
    type: "bias",
    category: ["bias", "fairness"],
    description: "Identifies and mitigates bias in AI model outputs including gender, racial, and age bias",
    provider: "Bud Sentinel",
    deployments: 5,
    status: "pending"
  },
  {
    id: "5",
    name: "Profanity Blocker",
    type: "profanity",
    category: ["content", "harm"],
    description: "Blocks profane language and offensive terms in both input and output",
    provider: "Azure AI",
    deployments: 20,
    status: "active"
  },
  {
    id: "6",
    name: "RegEx Pattern Matcher",
    type: "regex",
    category: ["custom", "pattern"],
    description: "Custom regex patterns for detecting specific text patterns or formats",
    provider: "Custom",
    deployments: 3,
    status: "active"
  },
  {
    id: "7",
    name: "Semantic Similarity",
    type: "semantic",
    category: ["custom", "similarity"],
    description: "Checks semantic similarity between prompts and predefined patterns",
    provider: "Custom",
    deployments: 0,
    status: "inactive"
  },
  {
    id: "8",
    name: "Medical Info Filter",
    type: "pii",
    category: ["harm", "compliance", "healthcare"],
    description: "Specialized filter for medical and health-related personal information",
    provider: "Bud Sentinel",
    deployments: 7,
    status: "active"
  },
  {
    id: "9",
    name: "Financial Data Protection",
    type: "pii",
    category: ["compliance", "finance"],
    description: "Protects financial data including account numbers, routing numbers, and transaction details",
    provider: "AWS Bedrock",
    deployments: 10,
    status: "active"
  }
];

export default function GuardRails() {
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

  // State for guardrails
  const [guardRails, setGuardRails] = useState<GuardRail[]>(dummyGuardRails);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");

  // for pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [tempFilter, setTempFilter] = useState<GuardRailFilters>({});
  const [filter, setFilter] = useState<GuardRailFilters>(defaultFilter);
  const [filterOpen, setFilterOpen] = React.useState(false);
  const [filterReset, setFilterReset] = useState(false);

  const load = useCallback(
    async (filter: GuardRailFilters) => {
      if (hasPermission(PermissionEnum.ModelView)) {
        // For now, just filter the local dummy data
        // In real implementation, this would call an API
        let filteredGuardRails = [...dummyGuardRails];

        if (filter.name) {
          filteredGuardRails = filteredGuardRails.filter(gr =>
            gr.name.toLowerCase().includes(filter.name!.toLowerCase())
          );
        }

        if (filter.provider?.length > 0) {
          filteredGuardRails = filteredGuardRails.filter(gr =>
            filter.provider!.includes(gr.provider?.toLowerCase().replace(/\s+/g, '-') || '')
          );
        }

        if (filter.guardRailType?.length > 0) {
          filteredGuardRails = filteredGuardRails.filter(gr =>
            filter.guardRailType!.includes(gr.type)
          );
        }

        if (filter.status?.length > 0) {
          filteredGuardRails = filteredGuardRails.filter(gr =>
            filter.status!.includes(gr.status || '')
          );
        }

        setGuardRails(filteredGuardRails);
      }
    },
    [hasPermission]
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
    if (key === "provider" || key === "guardRailType" || key === "modality" || key === "status") {
      const filteredItems = tempFilter[key]?.filter(
        (element) => element !== item
      ) || [];
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
    // debounce
    const timer = setTimeout(() => {
      load(filter);
      setCurrentPage(1);
    }, 500);
    return () => clearTimeout(timer);
  }, [filter.name]);

  useEffect(() => {
    getTasks();
    getAuthors();
  }, []);

  useEffect(() => {
    // openDrawer('cluster-event');
  }, []);

  const handleScroll = (e) => {
    // is at the bottom
    const bottom =
      document.getElementById("model-repo")?.scrollTop > models.length * 30;
    if (bottom && models.length < totalModels && currentPage < totalPages) {
      setCurrentPage(currentPage + 1);
    }
  };
  useEffect(() => {
    if (isMounted) {
      setTimeout(() => {
        load(filter);
      }, 1000);
    }
  }, [currentPage, pageSize, getGlobalModels, filter, isMounted]);
   useEffect(() => {
      setIsMounted(true)
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
                    getPopupContainer={(trigger) => (trigger.parentNode as HTMLElement) || document.body}
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
                              Apply the following filters to find guardrails of your choice.
                            </div>
                          </div>
                          <div className="height-1 bg-[#1F1F1F] mb-[1.5rem] w-full"></div>
                          <div className="w-full flex flex-col gap-size-20 px-[1.5rem] pb-[1.5rem]">

                            {/* Provider Filter */}
                            <div className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]`}>
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
                                        <Tags name={label} color="#965CDE"></Tags>
                                      );
                                    }}
                                  />
                                </ConfigProvider>
                              </div>
                            </div>

                            {/* GuardRail Type Filter */}
                            <div className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]`}>
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
                                        <Tags name={label} color="#965CDE"></Tags>
                                      );
                                    }}
                                  />
                                </ConfigProvider>
                              </div>
                            </div>

                            {/* Modality Filter */}
                            <div className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]`}>
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
                                        <Tags name={label} color="#965CDE"></Tags>
                                      );
                                    }}
                                  />
                                </ConfigProvider>
                              </div>
                            </div>

                            {/* Status Filter */}
                            <div className={`rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]`}>
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
                                        <Tags name={label} color="#965CDE"></Tags>
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
                        onClick={() => { }}
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
                {["all", "harm", "jailbreak", "toxic", "bias", "compliance", "custom"].map((category) => (
                  <Tags
                    key={category}
                    name={category.charAt(0).toUpperCase() + category.slice(1)}
                    color={selectedCategory === category ? "#965CDE" : "#757575"}
                    classNames="px-[1rem] py-[0.5rem]"
                    onTagClick={() => setSelectedCategory(category)}
                  />
                ))}
              </div>

              {/* GuardRails Grid */}
              {(() => {
                const filteredGuardRails = selectedCategory === "all"
                  ? guardRails
                  : guardRails.filter(gr => gr.category.includes(selectedCategory));

                return filteredGuardRails.length > 0 ? (
                  <div className="grid gap-[1.5rem] grid-cols-3 pb-[1.5rem] px-[1.5rem]">
                    {filteredGuardRails.map((item, index) => (
                      <GuardRailCard key={item.id} item={item} index={index} />
                    ))}
                  </div>
                ) : (
                  <NoDataFount
                    classNames="h-[50vh]"
                    textMessage={`No guardrails found for the "${selectedCategory}" category`}
                  />
                );
              })()}
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

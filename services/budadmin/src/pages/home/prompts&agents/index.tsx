/* eslint-disable react/no-unescaped-entities */
"use client";
import { MixerHorizontalIcon } from "@radix-ui/react-icons";
import { ConfigProvider, Popover, Select, Slider, Tag } from "antd";
import { useCallback, useEffect, useState } from "react";
import React from "react";
import DashBoardLayout from "../layout";

// ui components
import {
  Text_11_400_808080,
  Text_17_600_FFFFFF,
  Text_13_400_B3B3B3,
  Text_12_400_B3B3B3,
  Text_12_300_EEEEEE,
} from "./../../../components/ui/text";
import { useLoader } from "src/context/appContext";
import PageHeader from "@/components/ui/pageHeader";
import NoAccess from "@/components/ui/noAccess";
import { useDrawer } from "src/hooks/useDrawer";
import { getChromeColor } from "@/components/ui/bud/dataEntry/TagsInputData";
import { formatDate } from "src/utils/formatDate";
import Tags from "src/flows/components/DrawerTags";
import {
  PrimaryButton,
  SecondaryButton,
} from "@/components/ui/bud/form/Buttons";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import NoDataFount from "@/components/ui/noDataFount";
import { PermissionEnum, useUser } from "src/stores/useUser";
import { PlusOutlined } from "@ant-design/icons";

// Types
interface PromptAgent {
  id: string;
  name: string;
  description: string;
  type: 'prompt' | 'agent';
  category: string;
  tags: string[];
  created_at: string;
  modified_at: string;
  author: string;
  usage_count: number;
  rating: number;
  is_public: boolean;
  icon?: string;
  parameters?: any;
  version: string;
}

// Mock data for demonstration
const mockPromptsAgents: PromptAgent[] = [
  {
    id: "1",
    name: "Code Review Assistant",
    description: "An intelligent agent that performs comprehensive code reviews with security, performance, and best practice checks",
    type: "agent",
    category: "Development",
    tags: ["code-review", "security", "performance", "best-practices"],
    created_at: "2024-01-15T10:00:00Z",
    modified_at: "2024-01-20T14:30:00Z",
    author: "BudAI Team",
    usage_count: 1250,
    rating: 4.8,
    is_public: true,
    version: "1.2.0"
  },
  {
    id: "2",
    name: "SQL Query Optimizer",
    description: "Analyzes and optimizes SQL queries for better performance and efficiency",
    type: "prompt",
    category: "Database",
    tags: ["sql", "optimization", "database", "performance"],
    created_at: "2024-01-10T09:00:00Z",
    modified_at: "2024-01-18T11:00:00Z",
    author: "Data Team",
    usage_count: 890,
    rating: 4.6,
    is_public: true,
    version: "2.0.0"
  },
  {
    id: "3",
    name: "Documentation Generator",
    description: "Automatically generates comprehensive documentation from code comments and structure",
    type: "agent",
    category: "Documentation",
    tags: ["documentation", "automation", "markdown", "api-docs"],
    created_at: "2024-01-08T08:00:00Z",
    modified_at: "2024-01-16T10:00:00Z",
    author: "DevOps Team",
    usage_count: 2100,
    rating: 4.9,
    is_public: true,
    version: "3.1.0"
  },
  {
    id: "4",
    name: "Test Case Generator",
    description: "Creates comprehensive test cases based on code analysis and requirements",
    type: "prompt",
    category: "Testing",
    tags: ["testing", "qa", "automation", "unit-tests"],
    created_at: "2024-01-05T07:00:00Z",
    modified_at: "2024-01-14T09:00:00Z",
    author: "QA Team",
    usage_count: 1500,
    rating: 4.7,
    is_public: true,
    version: "1.5.0"
  },
  {
    id: "5",
    name: "Security Vulnerability Scanner",
    description: "Scans code for security vulnerabilities and provides remediation suggestions",
    type: "agent",
    category: "Security",
    tags: ["security", "vulnerability", "scanning", "compliance"],
    created_at: "2024-01-03T06:00:00Z",
    modified_at: "2024-01-12T08:00:00Z",
    author: "Security Team",
    usage_count: 3200,
    rating: 4.95,
    is_public: true,
    version: "4.0.0"
  },
  {
    id: "6",
    name: "API Response Formatter",
    description: "Formats and structures API responses according to best practices",
    type: "prompt",
    category: "API",
    tags: ["api", "formatting", "rest", "json"],
    created_at: "2024-01-01T05:00:00Z",
    modified_at: "2024-01-10T07:00:00Z",
    author: "API Team",
    usage_count: 750,
    rating: 4.5,
    is_public: true,
    version: "1.0.0"
  }
];

function PromptAgentCard({ item, index }: { item: PromptAgent; index: number }) {
  const { openDrawer } = useDrawer();

  const getTypeColor = (type: string) => {
    return type === 'agent' ? '#965CDE' : '#5CADFF';
  };

  const getTypeIcon = (type: string) => {
    return type === 'agent' ? '>' : '=�';
  };

  return (
    <div
      className="flex flex-col justify-between bg-[#101010] border border-[#1F1F1F] rounded-lg pt-[1.54em] 1680px:pt-[1.85em] min-h-[325px] 1680px:min-h-[400px] 2048px:min-h-[475px] group cursor-pointer hover:shadow-[1px_1px_6px_-1px_#2e3036] overflow-hidden"
      key={index}
      onClick={async () => {
        // Handle click - will need to implement drawer flow or navigation
        // For now, just log the action
        console.log("View prompt/agent:", item.name);
      }}
    >
      <div className="px-[1.6rem] min-h-[230px]">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-[2.40125rem] h-[2.40125rem] bg-[#1F1F1F] rounded-[5px] flex items-center justify-center text-[1.2rem]">
            {getTypeIcon(item.type)}
          </div>
          <Tag
            className="border-0 rounded-[4px] px-2 py-1"
            style={{
              backgroundColor: getTypeColor(item.type) + '20',
              color: getTypeColor(item.type),
            }}
          >
            {item.type === 'agent' ? 'Agent' : 'Prompt'}
          </Tag>
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
        >
          {item.name}
        </Text_17_600_FFFFFF>

        <Text_13_400_B3B3B3 className="mt-[.6rem] leading-[1.125rem] h-[2.5rem] tracking-[.01em] line-clamp-2 overflow-hidden display-webkit-box">
          {item?.description || ""}
        </Text_13_400_B3B3B3>

        <div className="flex items-center flex-wrap py-[1.1em] gap-[.3rem]">
          {item.tags.slice(0, 3).map((tag, idx) => (
            <Tag
              key={idx}
              className="text-[#B3B3B3] border-[0] rounded-[6px] py-[.3rem] px-[.4rem]"
              style={{
                backgroundColor: getChromeColor("#1F1F1F"),
                background: "#1F1F1F",
              }}
            >
              <div className="text-[0.625rem] font-[400] leading-[100%]" style={{ color: "#EEEEEE" }}>
                {tag}
              </div>
            </Tag>
          ))}
          {item.tags.length > 3 && (
            <Tag
              className="text-[#B3B3B3] border-[0] rounded-[6px] py-[.3rem] px-[.4rem]"
              style={{
                backgroundColor: getChromeColor("#1F1F1F"),
                background: "#1F1F1F",
              }}
            >
              <div className="text-[0.625rem] font-[400] leading-[100%]" style={{ color: "#808080" }}>
                +{item.tags.length - 3}
              </div>
            </Tag>
          )}
        </div>
      </div>

      <div className="px-[1.6rem] pt-[.9rem] pb-[1rem] bg-[#161616] border-t-[.5px] border-t-[#1F1F1F] min-h-[32%]">
        <div className="flex items-center justify-between mb-2">
          <Text_12_400_B3B3B3>Usage & Rating</Text_12_400_B3B3B3>
          <Text_12_400_B3B3B3>v{item.version}</Text_12_400_B3B3B3>
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Tag
              className="text-[#B3B3B3] border-[0] rounded-[6px] py-[.3rem] px-[.4rem]"
              style={{
                backgroundColor: getChromeColor("#1F1F1F"),
                background: "#1F1F1F",
              }}
            >
              <div className="text-[0.625rem] font-[400] leading-[100%]" style={{ color: "#EEEEEE" }}>
                {item.usage_count.toLocaleString()} uses
              </div>
            </Tag>

            <Tag
              className="text-[#B3B3B3] border-[0] rounded-[6px] py-[.3rem] px-[.4rem]"
              style={{
                backgroundColor: getChromeColor("#1F1F1F"),
                background: "#1F1F1F",
              }}
            >
              <div className="text-[0.625rem] font-[400] leading-[100%]" style={{ color: "#EEEEEE" }}>
                P {item.rating}
              </div>
            </Tag>
          </div>

          <Tag
            className="text-[#B3B3B3] border-[0] rounded-[6px] py-[.3rem] px-[.4rem]"
            style={{
              backgroundColor: getChromeColor("#1F1F1F"),
              background: "#1F1F1F",
            }}
          >
            <div className="text-[0.625rem] font-[400] leading-[100%]" style={{ color: "#EEEEEE" }}>
              {item.category}
            </div>
          </Tag>
        </div>
      </div>
    </div>
  );
}

const SelectedFilters = ({
  filters,
  removeTag,
}: {
  filters: any;
  removeTag?: (key: string, item: any) => void;
}) => {
  return (
    <div className="flex justify-start gap-[.4rem] items-center absolute top-[.4rem] left-[3.5rem]">
      {filters?.type && (
        <Tags
          name={`Type: ${filters.type}`}
          color="#d1b854"
          closable
          onClose={() => removeTag?.("type", filters?.type)}
        />
      )}
      {filters?.category && (
        <Tags
          name={`Category: ${filters.category}`}
          color="#d1b854"
          closable
          onClose={() => removeTag?.("category", filters?.category)}
        />
      )}
      {filters?.author && (
        <Tags
          name={`Author: ${filters.author}`}
          color="#d1b854"
          closable
          onClose={() => removeTag?.("author", filters?.author)}
        />
      )}
      {filters?.tags?.length > 0 &&
        filters.tags.map((item: string, index: number) => (
          <Tags
            name={item}
            color="#d1b854"
            key={index}
            closable
            onClose={() => removeTag?.("tags", item)}
          />
        ))}
    </div>
  );
};

const defaultFilter = {
  name: "",
  type: undefined as 'prompt' | 'agent' | undefined,
  category: undefined,
  author: undefined,
  tags: [] as string[],
  rating_min: undefined,
  rating_max: undefined,
};

export default function PromptsAgents() {
  const { hasPermission, loadingUser } = useUser();
  const { showLoader, hideLoader } = useLoader();
  const { openDrawer } = useDrawer();

  // State
  const [filteredData, setFilteredData] = useState<PromptAgent[]>(mockPromptsAgents);
  const [currentPage, setCurrentPage] = useState(1);
  const [tempFilter, setTempFilter] = useState<any>(defaultFilter);
  const [filter, setFilter] = useState<any>(defaultFilter);
  const [filterOpen, setFilterOpen] = React.useState(false);
  const [filterReset, setFilterReset] = useState(false);

  // Mock data for filters
  const categories = ["Development", "Database", "Documentation", "Testing", "Security", "API"];
  const authors = ["BudAI Team", "Data Team", "DevOps Team", "QA Team", "Security Team", "API Team"];
  const allTags = Array.from(new Set(mockPromptsAgents.flatMap(item => item.tags)));

  const load = useCallback(
    async (filter: any) => {
      showLoader();

      // Simulate API call with filtering
      let filtered = [...mockPromptsAgents];

      if (filter.name) {
        filtered = filtered.filter(item =>
          item.name.toLowerCase().includes(filter.name.toLowerCase()) ||
          item.description.toLowerCase().includes(filter.name.toLowerCase())
        );
      }

      if (filter.type) {
        filtered = filtered.filter(item => item.type === filter.type);
      }

      if (filter.category) {
        filtered = filtered.filter(item => item.category === filter.category);
      }

      if (filter.author) {
        filtered = filtered.filter(item => item.author === filter.author);
      }

      if (filter.tags?.length > 0) {
        filtered = filtered.filter(item =>
          filter.tags.some((tag: string) => item.tags.includes(tag))
        );
      }

      if (filter.rating_min) {
        filtered = filtered.filter(item => item.rating >= filter.rating_min);
      }

      if (filter.rating_max) {
        filtered = filtered.filter(item => item.rating <= filter.rating_max);
      }

      setFilteredData(filtered);
      hideLoader();
    },
    []
  );

  const handleOpenChange = (open: boolean) => {
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
    setTempFilter(defaultFilter);
    setCurrentPage(1);
    setFilterReset(true);
  };

  const removeSelectedTag = (key: string, item: any) => {
    if (key === "tags") {
      const filteredTags = tempFilter.tags.filter((tag: string) => tag !== item);
      setTempFilter({ ...tempFilter, tags: filteredTags });
    } else {
      setTempFilter({ ...tempFilter, [key]: undefined });
    }
    setFilterReset(true);
  };

  useEffect(() => {
    if (filterReset) {
      applyFilter();
    }
  }, [filterReset]);

  useEffect(() => {
    const timer = setTimeout(() => {
      load(filter);
      setCurrentPage(1);
    }, 500);
    return () => clearTimeout(timer);
  }, [filter.name]);

  useEffect(() => {
    load(defaultFilter);
  }, []);

  return (
    <DashBoardLayout>
      <div className="boardPageView" id="prompts-agents-container">
        <div className="boardPageTop">
          <PageHeader
            headding="Prompts & Agents"
            buttonLabel="Agent"
            buttonPermission={hasPermission(PermissionEnum.ModelManage)}
            buttonAction={() => {
              // Will need to implement add prompt/agent flow
              console.log("Add new prompt/agent");
            }}
            ButtonIcon={PlusOutlined}
            rightComponent={
              <div className="flex gap-x-[.2rem]">
                <SearchHeaderInput
                  classNames="mr-[.2rem]"
                  placeholder="Search prompts and agents..."
                  searchValue={filter.name || ""}
                  setSearchValue={(value: string) => {
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
                            Apply filters to find prompts and agents
                          </div>
                        </div>
                        <div className="height-1 bg-[#1F1F1F] mb-[1.5rem] w-full"></div>
                        <div className="w-full flex flex-col gap-size-20 px-[1.5rem] pb-[1.5rem]">
                          {/* Type Filter */}
                          <div className="rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]">
                            <div className="w-full">
                              <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap">
                                Type
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
                                  placeholder="Select Type"
                                  style={{
                                    backgroundColor: "transparent",
                                    color: "#EEEEEE",
                                    border: "0.5px solid #757575",
                                    width: "100%",
                                  }}
                                  value={tempFilter.type}
                                  size="large"
                                  className="drawerInp !bg-[transparent] text-[#EEEEEE] py-[.6rem] font-[300] text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] h-[2.59338rem] outline-none"
                                  options={[
                                    { label: "Prompt", value: "prompt" },
                                    { label: "Agent", value: "agent" },
                                  ]}
                                  onChange={(value) => {
                                    setTempFilter({
                                      ...tempFilter,
                                      type: value,
                                    });
                                  }}
                                />
                              </ConfigProvider>
                            </div>
                          </div>

                          {/* Category Filter */}
                          <div className="rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]">
                            <div className="w-full">
                              <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap">
                                Category
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
                                  placeholder="Select Category"
                                  style={{
                                    backgroundColor: "transparent",
                                    color: "#EEEEEE",
                                    border: "0.5px solid #757575",
                                    width: "100%",
                                  }}
                                  value={tempFilter.category}
                                  size="large"
                                  className="drawerInp !bg-[transparent] text-[#EEEEEE] py-[.6rem] font-[300] text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] h-[2.59338rem] outline-none"
                                  options={categories.map(cat => ({
                                    label: cat,
                                    value: cat,
                                  }))}
                                  onChange={(value) => {
                                    setTempFilter({
                                      ...tempFilter,
                                      category: value,
                                    });
                                  }}
                                />
                              </ConfigProvider>
                            </div>
                          </div>

                          {/* Author Filter */}
                          <div className="rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]">
                            <div className="w-full">
                              <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap">
                                Author
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
                                  className="drawerInp !bg-[transparent] text-[#EEEEEE] py-[.6rem] font-[300] text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] h-[2.59338rem] outline-none"
                                  options={authors.map(author => ({
                                    label: author,
                                    value: author,
                                  }))}
                                  onChange={(value) => {
                                    setTempFilter({
                                      ...tempFilter,
                                      author: value,
                                    });
                                  }}
                                />
                              </ConfigProvider>
                            </div>
                          </div>

                          {/* Tags Filter */}
                          <div className="rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]">
                            <div className="w-full">
                              <Text_12_300_EEEEEE className="absolute bg-[#101010] -top-1.5 left-[1.1rem] tracking-[.035rem] z-10 flex items-center gap-1 text-nowrap">
                                Tags
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
                                  placeholder="Select Tags"
                                  style={{
                                    backgroundColor: "transparent",
                                    color: "#EEEEEE",
                                    border: "0.5px solid #757575",
                                    width: "100%",
                                  }}
                                  value={tempFilter.tags}
                                  size="large"
                                  mode="multiple"
                                  className="drawerInp !bg-[transparent] text-[#EEEEEE] py-[.6rem] font-[300] text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] h-[2.59338rem] outline-none"
                                  options={allTags.map(tag => ({
                                    label: tag,
                                    value: tag,
                                  }))}
                                  onChange={(value) => {
                                    setTempFilter({
                                      ...tempFilter,
                                      tags: value,
                                    });
                                  }}
                                  tagRender={(props) => {
                                    const { label } = props;
                                    return (
                                      <Tags name={label as string} color="#D1B854" />
                                    );
                                  }}
                                />
                              </ConfigProvider>
                            </div>
                          </div>

                          {/* Rating Range */}
                          <div className="rounded-[6px] relative !bg-[transparent] !w-[100%] mb-[0]">
                            <div className="w-full">
                              <Text_12_300_EEEEEE className="absolute px-1.4 tracking-[.035rem] flex items-center gap-1 text-nowrap">
                                Rating
                              </Text_12_300_EEEEEE>
                              <div className="flex items-center justify-center">
                                <div className="text-[#757575] text-[.75rem] h-[4px] mr-1 leading-8">
                                  0
                                </div>
                                <Slider
                                  className="budSlider mt-[3.2rem] w-full"
                                  min={0}
                                  max={5}
                                  step={0.1}
                                  range
                                  value={[
                                    tempFilter.rating_min || 0,
                                    tempFilter.rating_max || 5,
                                  ]}
                                  onChange={(value) => {
                                    setTempFilter({
                                      ...tempFilter,
                                      rating_min: value[0],
                                      rating_max: value[1],
                                    });
                                  }}
                                  tooltip={{
                                    open: true,
                                    getPopupContainer: (trigger) =>
                                      (trigger.parentNode as HTMLElement) ||
                                      document.body,
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
                                  5
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
                      className="group h-[1.7rem] text-[#EEEEEE] mx-2 flex items-center cursor-pointer text-xs font-normal leading-3 rounded-[6px] shadow-none bg-transparent"
                    >
                      <MixerHorizontalIcon
                        style={{ width: "0.875rem", height: "0.875rem" }}
                        className="text-[#B3B3B3] group-hover:text-[#FFFFFF]"
                      />
                    </label>
                  </Popover>
                </ConfigProvider>
              </div>
            }
          />
        </div>

        {hasPermission(PermissionEnum.ModelView) ? (
          <>
            <div
              className="boardMainContainer listingContainer scroll-smooth pt-[2.95rem] relative"
              id="prompts-agents-list"
            >
              <SelectedFilters
                filters={tempFilter}
                removeTag={(key, item) => {
                  removeSelectedTag(key, item);
                }}
              />
              {filteredData?.length > 0 ? (
                <div className="grid gap-[1.1rem] grid-cols-3 1680px:mt-[1.75rem] pb-[1.1rem]">
                  {filteredData.map((item, index) => (
                    <PromptAgentCard key={item.id} item={item} index={index} />
                  ))}
                </div>
              ) : (
                <div>
                  {Object.keys(filter).filter(
                    (key) =>
                      filter[key] !== undefined &&
                      filter[key] !== "" &&
                      (key !== "tags" || filter[key].length > 0)
                  ).length > 0 ? (
                    <NoDataFount
                      classNames="h-[60vh]"
                      textMessage={`No prompts or agents found for the ${
                        filter.name
                          ? `search term "${filter.name}"`
                          : "selected filters"
                      }`}
                    />
                  ) : (
                    <NoDataFount
                      classNames="h-[60vh]"
                      textMessage="No prompts or agents available. Start by adding your first prompt or agent."
                    />
                  )}
                </div>
              )}
            </div>
          </>
        ) : (
          !loadingUser && (
            <>
              <NoAccess textMessage="You do not have access to view prompts and agents. Please ask admin to give you access." />
            </>
          )
        )}
      </div>
    </DashBoardLayout>
  );
}

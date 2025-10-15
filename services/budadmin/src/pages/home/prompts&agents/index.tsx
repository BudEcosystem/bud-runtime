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
  Text_12_600_EEEEEE,
} from "./../../../components/ui/text";
import { useLoader } from "src/context/appContext";
import PageHeader from "@/components/ui/pageHeader";
import NoAccess from "@/components/ui/noAccess";
import { useDrawer } from "src/hooks/useDrawer";
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
import { useAgentStore } from "@/stores/useAgentStore";
import AgentDrawer from "@/components/agents/AgentDrawer";
import { usePromptsAgents, type PromptAgent } from "@/stores/usePromptsAgents";
import { IconOnlyRender } from "src/flows/components/BudIconRender";
import PromptAgentTags from "src/flows/components/PromptAgentTags";


function PromptAgentCard({ item, index }: { item: PromptAgent; index: number }) {
  const getTypeColor = (type?: string) => {
    return type === 'agent' ? '#965CDE' : '#5CADFF';
  };

  // Check if description is long enough to need "See more" (approximately 2 lines worth)
  const needsSeeMore = item.description && item.description.length > 100;


  return (
    <div
      className="flex flex-col justify-start bg-[#101010] border border-[#1F1F1F] rounded-lg min-h-[250px] 1680px:min-h-[325px] 2048px:min-h-[400px] group cursor-pointer hover:shadow-[1px_1px_6px_-1px_#2e3036] overflow-hidden"
      key={index}
      onClick={async () => {
        // Handle click - will need to implement drawer flow or navigation
        // For now, just log the action
        console.log("View prompt/agent:", item.name);
      }}
    >
      <div className="pr-[1.5em] pl-[1.5em] pt-[1.6em] pb-[.6rem] h-full flex flex-col">
        <div className="min-h-[160px]">
          <div className="flex justify-between w-full">
            <div className="flex items-center justify-center bg-[#1F1F1F] w-[2.40125rem] h-[2.40125rem] rounded">
              {item.model_icon ? (
                <div className="w-[2.40125rem] h-[2.40125rem] bg-[#1F1F1F] rounded-[5px] flex items-center justify-center">
                  <IconOnlyRender
                    icon={item?.model_icon}
                    size={26}
                    imageSize={24}
                    model={item}
                  />
                </div>
              ) : (
                <div className="text-[1.5625rem]">
                  {item.prompt_type === 'agent' ? '🤖' : '📝'}
                </div>
              )}
            </div>
          </div>

          <div className="pl-[.1rem] pt-[1.25rem]">
            <Text_11_400_808080>
              {formatDate(item?.modified_at || item?.created_at)}
            </Text_11_400_808080>
            <Text_17_600_FFFFFF className="pt-[.35em] text-wrap pr-1 truncate-text max-w-[90%]">
              {item.name}
            </Text_17_600_FFFFFF>
            <div className="pt-[.85em] pr-[.45em] min-h-[5rem]">
              <div
                className="line-clamp-2 overflow-hidden"
                style={{
                  display: "-webkit-box",
                  WebkitBoxOrient: "vertical",
                  WebkitLineClamp: 2
                }}
              >
                <Text_13_400_B3B3B3 className="text-[0.75em] tracking-[.01em] leading-[150%]">
                  {item?.description || ""}
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
                    trigger="hover"
                    placement="top"
                    rootClassName="prompt-agent-description-popover"
                    getPopupContainer={(trigger) =>
                      (trigger.parentNode as HTMLElement) || document.body
                    }
                  >
                    <Text_12_600_EEEEEE
                      className="cursor-pointer mt-[0.3rem] inline-block hover:text-[#965CDE] transition-colors"
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
          </div>
        </div>

        <div
          className="mt-[1.1rem] flex gap-[.45rem] justify-start items-center flex-wrap overflow-hidden mb-[1.1rem]"
          style={{
            maxHeight: "4rem",
            lineHeight: "1.5rem",
          }}
        >
          <PromptAgentTags promptAgent={item} maxTags={3} limit={false} />
        </div>
      </div>

      {/* <div className="pt-[1.1rem] pr-[1.5em] pl-[1.5em] pb-[1.45em] bg-[#161616] flex justify-between items-center">
        <div>
          <Text_17_600_FFFFFF className="block px-[.2em] group-hover:text-[#FFFFFF] text[0.75rem] leading-[100%]">
            {(item.usage_count || 0).toLocaleString()}
          </Text_17_600_FFFFFF>
          <Text_13_400_B3B3B3 className="pt-[.3rem]">
            Uses
          </Text_13_400_B3B3B3>
        </div>
        <div>
          <Text_17_600_FFFFFF className="block px-[.2em] group-hover:text-[#FFFFFF] text[0.75rem] leading-[100%]">
            {item.rating || 0}
          </Text_17_600_FFFFFF>
          <Text_13_400_B3B3B3 className="pt-[.3rem]">
            Rating
          </Text_13_400_B3B3B3>
        </div>
        <div>
          <Text_17_600_FFFFFF className="block px-[.2em] group-hover:text-[#FFFFFF] text[0.75rem] leading-[100%]">
            v{item.default_version || item.version || '1.0'}
          </Text_17_600_FFFFFF>
          <Text_13_400_B3B3B3 className="pt-[.3rem]">
            Version
          </Text_13_400_B3B3B3>
        </div>
      </div> */}
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
  const { openAgentDrawer } = useAgentStore();
  // openAgentDrawer();
  // Use the store
  const {
    filteredPrompts,
    isLoading,
    searchQuery,
    selectedType,
    selectedCategory,
    selectedAuthor,
    selectedTags,
    ratingMin,
    ratingMax,
    categories,
    authors,
    allTags,
    fetchPrompts,
    setSearchQuery,
    setSelectedType,
    setSelectedCategory,
    setSelectedAuthor,
    setSelectedTags,
    setRatingRange,
    applyFilters,
    resetFilters: storeResetFilters,
  } = usePromptsAgents();

  // State
  const [currentPage, setCurrentPage] = useState(1);
  const [tempFilter, setTempFilter] = useState<any>(defaultFilter);
  const [filter, setFilter] = useState<any>(defaultFilter);
  const [filterOpen, setFilterOpen] = React.useState(false);
  const [filterReset, setFilterReset] = useState(false);

  const load = useCallback(
    async (filter: any) => {
      // Update store filters
      if (filter.name !== undefined) setSearchQuery(filter.name);
      if (filter.type !== undefined) setSelectedType(filter.type);
      if (filter.category !== undefined) setSelectedCategory(filter.category);
      if (filter.author !== undefined) setSelectedAuthor(filter.author);
      if (filter.tags !== undefined) setSelectedTags(filter.tags);
      if (filter.rating_min !== undefined || filter.rating_max !== undefined) {
        setRatingRange(filter.rating_min, filter.rating_max);
      }

      // Apply filters will trigger the API call
      await applyFilters();
    },
    [setSearchQuery, setSelectedType, setSelectedCategory, setSelectedAuthor, setSelectedTags, setRatingRange, applyFilters]
  );

  const handleOpenChange = (open: boolean) => {
    setFilterOpen(open);
    setTempFilter(filter);
  };

  const applyFilter = async () => {
    setFilterOpen(false);
    setFilter(tempFilter);
    setCurrentPage(1);
    await load(tempFilter);
    setFilterReset(false);
  };

  const resetFilter = async () => {
    setTempFilter(defaultFilter);
    setCurrentPage(1);
    setFilterReset(true);
    await storeResetFilters();
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
      if (filter.name !== undefined) {
        setSearchQuery(filter.name);
        fetchPrompts();
      }
      setCurrentPage(1);
    }, 500);
    return () => clearTimeout(timer);
  }, [filter.name]);

  useEffect(() => {
    fetchPrompts();
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
              openDrawer("add-agent");
            }}
            ButtonIcon={PlusOutlined}
            rightComponent={
              <div className="flex gap-x-[.2rem] hidden">
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
                                    { label: "Prompt", value: "simple_prompt" },
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
              {isLoading ? (
                <div className="flex items-center justify-center h-[60vh]">
                  <div className="text-[#B3B3B3]">Loading prompts and agents...</div>
                </div>
              ) : filteredPrompts?.length > 0 ? (
                <div className="grid gap-[1.1rem] grid-cols-3 1680px:mt-[1.75rem] pb-[1.1rem]">
                  {filteredPrompts.map((item, index) => (
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
                      textMessage={`No prompts or agents found for the ${filter.name
                          ? `search term "${filter.name}"`
                          : "selected filters"
                        }`}
                    />
                  ) : (
                    <NoDataFount
                      classNames="h-[60vh]"
                      textMessage="No prompts or agents available"
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

      {/* Agent Drawer - Independent from existing drawer */}
      <AgentDrawer />
    </DashBoardLayout>
  );
}

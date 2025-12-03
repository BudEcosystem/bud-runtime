/* eslint-disable react/no-unescaped-entities */
"use client";
import { MixerHorizontalIcon } from "@radix-ui/react-icons";
import { ConfigProvider, Image, Popover, Select, Spin } from "antd";
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
import useGuardrails from "src/hooks/useGuardrails";
import { AppRequest } from "src/pages/api/requests";
import { errorToast } from "@/components/toast";
import { useModels } from "src/hooks/useModels";
import Tags from "src/flows/components/DrawerTags";
import {
  PrimaryButton,
  SecondaryButton,
} from "@/components/ui/bud/form/Buttons";
import CustomPopover from "src/flows/components/customPopover";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import NoDataFount from "@/components/ui/noDataFount";
import { PermissionEnum, useUser } from "src/stores/useUser";
import { PlusOutlined } from "@ant-design/icons";

// Interface for GuardRail/Probe data structure
interface GuardRail {
  id: string;
  name: string;
  uri?: string;
  type?: string;
  category: string[];
  description?: string;
  provider?: any;
  provider_type?: string;
  deployments?: number;
  status?: string;
  createdAt?: string;
  created_at?: string;
  icon?: string;
  tags?: Array<{ name: string; color: string }>;
  scanner_types?: string[];
  modality_types?: string[];
  guard_types?: string[];
  examples?: string[];
}

function GuardRailCard({ item, index }: { item: any; index: number }) {
  const { openDrawer, openDrawerWithStep } = useDrawer();
  const [descriptionPopoverOpen, setDescriptionPopoverOpen] = useState(false);

  // Check if description is long enough to need "See more" (approximately 3 lines worth)
  const needsSeeMore = item.description && item.description.length > 150;

  const getTypeIcon = (item: any) => {
    // Use uri or type to determine icon
    const typeIdentifier = item.uri || item.type || '';
    switch (typeIdentifier.toLowerCase()) {
      case 'pii':
      case 'personal_identifier_information':
        return '🔒';
      case 'secrets':
      case 'credentials':
        return '🔐';
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
    switch (status) {
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
            {getTypeIcon(item)}
          </div>
          <div className="flex-1">
            <Text_17_600_FFFFFF className="mb-[0.25rem] line-clamp-1">
              {item.name}
            </Text_17_600_FFFFFF>
            {item.provider && (
              <Text_12_400_B3B3B3>
                by {typeof item.provider === 'object' ? item.provider.name : item.provider}
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
          {item.tags ? (
            // Use tags from API if available
            <>
              {item.tags.slice(0, 3).map((tag: any, idx: number) => (
                <Tags
                  name={tag.name}
                  color={tag.color || "#1F1F1F"}
                  key={idx}
                />
              ))}
              {item.tags.length > 3 && (
                <Tags
                  name={`+${item.tags.length - 3}`}
                  color="#1F1F1F"
                />
              )}
            </>
          ) : item.category ? (
            // Fallback to category if tags not available
            <>
              {item.category.slice(0, 3).map((cat: string, idx: number) => (
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
            </>
          ) : null}
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
  status: "",
};

interface GuardRailFilters {
  name?: string;
  provider?: string[];
  guardRailType?: string[];
  modality?: string[];
  status?: string;
}

// Component for displaying selected filters
const SelectedFilters = ({
  filters,
  removeTag,
}: {
  filters: GuardRailFilters;
  removeTag?: (key: string, item: string) => void;
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
      {filters?.status && (
        <Tags
          name={`Status: ${filters.status}`}
          color="#965CDE"
          closable
          onClose={() => removeTag("status", filters.status)}
        />
      )}
    </div>
  );
};

export default function GuardRails() {
  const [isMounted, setIsMounted] = useState(false);
  const { hasPermission, loadingUser } = useUser();
  const {
    models,
    getTasks,
    getAuthors,
    totalModels,
    totalPages,
  } = useModels();
  const { showLoader, hideLoader } = useLoader();
  const { openDrawer } = useDrawer();
  const { reset } = useDeployModel();

  // Use the guardrails hook (but we won't use its fetchProbes for the main listing)
  // This is to avoid conflicts with the add guardrail workflow
  const guardrailsHook = useGuardrails();

  // Local state for main listing page probes
  const [probes, setProbes] = useState<any[]>([]);
  const [probesLoading, setProbesLoading] = useState(false);
  const [totalProbes, setTotalProbes] = useState(0);
  const [totalProbePages, setTotalProbePages] = useState(0);

  // State for guardrails (fallback for when API is not available)
  const [guardRails] = useState<any[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");

  // for pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize] = useState(10);
  const [tempFilter, setTempFilter] = useState<GuardRailFilters>({});
  const [filter, setFilter] = useState<GuardRailFilters>(defaultFilter);
  const [filterOpen, setFilterOpen] = React.useState(false);
  const [filterReset, setFilterReset] = useState(false);

  // Local fetch function for main listing page
  const fetchMainPageProbes = useCallback(
    async (params?: any) => {
      setProbesLoading(true);
      try {
        const queryParams: any = {
          page: params?.page || 1,
          page_size: params?.page_size || 20,
          search: params?.isSearching === true ? true : false, // Add search parameter
        };

        // Add optional filters
        if (params?.searchTerm) {
          queryParams.query = params.searchTerm; // Use 'query' for the actual search term
        }
        if (params?.provider_type) {
          queryParams.provider_type = params.provider_type;
        }
        if (params?.tags) {
          queryParams.tags = params.tags;
        }
        if (params?.status) {
          queryParams.status = params.status; // Add status parameter
        }

        const response = await AppRequest.Get("/guardrails/probes", {
          params: queryParams,
        });

        if (response.data) {
          setProbes(response.data.probes || []);
          setTotalProbes(response.data.total_record || 0);
          setTotalProbePages(response.data.total_pages || 0);
        }
      } catch (error: any) {
        // Silently handle error - don't show toast for listing API
        console.error("Failed to fetch probes:", error?.message);
        setProbes([]);
      } finally {
        setProbesLoading(false);
      }
    },
    []
  );

  const load = useCallback(
    async (filter: GuardRailFilters, isSearching: boolean = false) => {
      if (hasPermission(PermissionEnum.ModelView)) {
        // Determine if we should set search to true
        // Set search: true if we have name search or status filter
        const shouldSearch = isSearching || !!filter.name || !!filter.status;

        // Use local fetch function instead of the hook's fetchProbes
        const params: any = {
          page: currentPage,
          page_size: pageSize,
          isSearching: shouldSearch, // Pass the search flag
        };

        if (filter.name) {
          params.searchTerm = filter.name; // Use searchTerm for the actual search string
        }

        if (filter.provider?.length > 0) {
          // For provider filtering, we might need to pass provider_id or provider_type
          // This depends on your API implementation
          params.provider_type = filter.provider.join(',');
        }

        if (filter.guardRailType?.length > 0) {
          // Map guardRailType to tags or other API parameters
          params.tags = filter.guardRailType.join(',');
        }

        if (filter.status) {
          // Pass status filter to API
          params.status = filter.status;
        }

        await fetchMainPageProbes(params);
      }
    },
    [hasPermission, currentPage, pageSize, fetchMainPageProbes]
  );

  const handleOpenChange = (open: boolean) => {
    setFilterOpen(open);
    setTempFilter(filter);
  };

  const applyFilter = () => {
    setFilterOpen(false);
    setFilter(tempFilter);
    setCurrentPage(1);
    // Check if status filter is applied to determine if it's a search operation
    const hasStatusFilter = !!tempFilter.status;
    load(tempFilter, hasStatusFilter);
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
    if (key === "status") {
      // Status is a single value, clear it
      setTempFilter({ ...tempFilter, status: "" });
    } else if (key === "provider" || key === "guardRailType" || key === "modality") {
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

  // Handle search with debounce
  useEffect(() => {
    if (!isMounted || loadingUser) return;

    const timer = setTimeout(() => {
      if (hasPermission(PermissionEnum.ModelView)) {
        // Pass true for isSearching when searching by name
        load(filter, !!filter.name);
      }
    }, 500);
    return () => clearTimeout(timer);
  }, [filter.name, isMounted, loadingUser]);

  // Handle other filter changes (non-search)
  useEffect(() => {
    if (!isMounted || loadingUser) return;

    if (hasPermission(PermissionEnum.ModelView)) {
      // Pass true for isSearching when status filter is applied, false for others
      const hasStatusFilter = !!filter.status;
      load(filter, hasStatusFilter);
    }
  }, [filter.provider, filter.guardRailType, filter.modality, filter.status, currentPage, pageSize, isMounted, loadingUser]);

  // Initial data fetch - depend on loadingUser to re-run when user permissions load
  useEffect(() => {
    getTasks();
    getAuthors();
    setIsMounted(true);

    // Only fetch when user is loaded and has permission
    if (!loadingUser && hasPermission(PermissionEnum.ModelView)) {
      fetchMainPageProbes({ page: 1, page_size: 20, isSearching: false });
    }
  }, [loadingUser]);
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
                                    value={tempFilter.status || undefined}
                                    size="large"
                                    allowClear
                                    className="drawerInp !bg-[transparent] text-[#EEEEEE] py-[.15rem] font-[300] text-[.75rem] shadow-none w-full indent-[.4rem] border-0 outline-0 hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] h-[2.59338rem] outline-none"
                                    options={[
                                      { label: "Active", value: "active" },
                                      { label: "Inactive", value: "inactive" },
                                      { label: "Pending", value: "pending" },
                                    ]}
                                    onChange={(value) => {
                                      setTempFilter({
                                        ...tempFilter,
                                        status: value || "",
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
              {/* Selected Filters */}
              {/* {(filter.provider?.length > 0 || filter.guardRailType?.length > 0 || filter.modality?.length > 0 || filter.status?.length > 0) && (
                <SelectedFilters filters={filter} removeTag={removeSelectedTag} />
              )} */}
              {/* Category Filter Tags */}
              <div className="flex items-center gap-[0.75rem] mb-[2rem] px-[1.5rem] flex-wrap">
                {(() => {
                  // Extract unique tag names from probes
                  const uniqueTags = new Set<string>();
                  uniqueTags.add("all"); // Always include "all"

                  const dataToProcess = probes.length > 0 ? probes : guardRails;
                  dataToProcess.forEach((probe: any) => {
                    if (probe.tags) {
                      probe.tags.forEach((tag: any) => {
                        // Extract main category from tag name (e.g., "Content Safety" -> "Content Safety")
                        const tagName = tag.name.toLowerCase();
                        if (tagName.includes("content safety")) uniqueTags.add("content safety");
                        else if (tagName.includes("data loss")) uniqueTags.add("dlp");
                        else if (tagName.includes("compliance")) uniqueTags.add("compliance");
                        else if (tagName.includes("harm")) uniqueTags.add("harm");
                        else if (tagName.includes("jailbreak")) uniqueTags.add("jailbreak");
                        else if (tagName.includes("toxic")) uniqueTags.add("toxic");
                        else if (tagName.includes("bias")) uniqueTags.add("bias");
                      });
                    } else if (probe.category) {
                      probe.category.forEach((cat: string) => uniqueTags.add(cat));
                    }
                  });

                  return Array.from(uniqueTags).slice(0, 7).map((category) => (
                    <Tags
                      key={category}
                      name={category.charAt(0).toUpperCase() + category.slice(1)}
                      color={selectedCategory === category ? "#965CDE" : "#757575"}
                      classNames="px-[1rem] py-[0.5rem] cursor-pointer"
                      onTagClick={() => setSelectedCategory(category)}
                    />
                  ));
                })()}
              </div>

              {/* GuardRails Grid */}
              {probesLoading ? (
                <div className="flex justify-center items-center h-[50vh]">
                  <Spin size="large" />
                </div>
              ) : (() => {
                // Use probes from API or fallback to guardRails state
                const dataToDisplay = probes.length > 0 ? probes : guardRails;

                // Filter by category if needed
                const filteredGuardRails = selectedCategory === "all"
                  ? dataToDisplay
                  : dataToDisplay.filter((gr: any) => {
                    // Check tags first, then fallback to category
                    if (gr.tags) {
                      return gr.tags.some((tag: any) => {
                        const tagName = tag.name.toLowerCase();
                        const category = selectedCategory.toLowerCase();

                        // Match different variations
                        if (category === "dlp") {
                          return tagName.includes("data loss");
                        } else if (category === "content safety") {
                          return tagName.includes("content safety");
                        }
                        return tagName.includes(category);
                      });
                    }
                    return gr.category?.includes(selectedCategory);
                  });

                return filteredGuardRails.length > 0 ? (
                  <div className="grid gap-[1.5rem] grid-cols-3 pb-[1.5rem] px-[1.5rem]">
                    {filteredGuardRails.map((item: any, index: number) => (
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

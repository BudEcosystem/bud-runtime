"use client";
import { useEffect, useState, useMemo, useRef, useCallback } from "react";
import React from "react";
import DashBoardLayout from "../layout";
import {
  Text_11_400_808080,
  Text_13_400_B3B3B3,
  Text_14_400_C7C7C7,
  Text_17_600_FFFFFF,
  Text_12_400_6A6E76,
} from "@/components/ui/text";
import PageHeader from "@/components/ui/pageHeader";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import NoDataFount from "@/components/ui/noDataFount";
import { PlusOutlined } from "@ant-design/icons";
import { SecondaryButton } from "@/components/ui/bud/form/Buttons";
import TagsList from "src/flows/components/TagsList";
import { formatDate } from "src/utils/formatDate";
import ProjectTags from "src/flows/components/ProjectTags";
import { useDrawer } from "src/hooks/useDrawer";
import { useTools, Tool } from "src/stores/useTools";
import { useVirtualServers, VirtualServer } from "src/stores/useVirtualServers";
import { Spin } from "antd";

type TabType = "tools" | "virtual-servers";

const Tools = () => {
  const [isMounted, setIsMounted] = useState(false);
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [debouncedSearch, setDebouncedSearch] = useState<string>("");
  const [activeFilters, setActiveFilters] = useState<Set<string>>(new Set());
  const [activeTab, setActiveTab] = useState<TabType>("tools");
  const loadMoreRef = useRef<HTMLDivElement>(null);
  const loadMoreVsRef = useRef<HTMLDivElement>(null);
  const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const { openDrawer } = useDrawer();
  const { tools, getTools, setSelectedTool, isLoading, isLoadingMore, hasMore, loadMore, resetPagination } = useTools();
  const {
    virtualServers,
    getVirtualServers,
    setSelectedVirtualServer,
    isLoading: isLoadingVs,
    isLoadingMore: isLoadingMoreVs,
    hasMore: hasMoreVs,
    loadMore: loadMoreVs,
  } = useVirtualServers();

  // Extract unique tags from tools for filtering
  const filterTags = useMemo(() => {
    const tagMap = new Map<string, { name: string; color: string }>();
    tools.forEach((tool) => {
      tool.tags.forEach((tag) => {
        if (!tagMap.has(tag.name)) {
          tagMap.set(tag.name, tag);
        }
      });
    });
    return Array.from(tagMap.values());
  }, [tools]);

  // Debounced search - updates debouncedSearch after 300ms of no typing
  useEffect(() => {
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }
    searchTimeoutRef.current = setTimeout(() => {
      setDebouncedSearch(searchTerm);
    }, 300);

    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current);
      }
    };
  }, [searchTerm]);

  // Fetch tools when search changes (server-side search)
  useEffect(() => {
    if (!isMounted) return;

    resetPagination();
    getTools({
      search: debouncedSearch || undefined,
      tags: activeFilters.size > 0 ? Array.from(activeFilters).join(",") : undefined,
    });
  }, [debouncedSearch, activeFilters, isMounted]);

  useEffect(() => {
    setIsMounted(true);
    getVirtualServers();
  }, []);

  // Infinite scroll with Intersection Observer for Tools
  useEffect(() => {
    if (!loadMoreRef.current || activeTab !== "tools") return;

    const observer = new IntersectionObserver(
      (entries) => {
        const [entry] = entries;
        // Load more if intersecting, has more items, and not already loading
        if (entry.isIntersecting && hasMore && !isLoadingMore && !isLoading) {
          loadMore();
        }
      },
      {
        root: null, // Use viewport
        rootMargin: "100px", // Load 100px before reaching the bottom
        threshold: 0.1,
      }
    );

    observer.observe(loadMoreRef.current);

    return () => {
      observer.disconnect();
    };
  }, [hasMore, isLoadingMore, isLoading, loadMore, activeTab]);

  // Infinite scroll with Intersection Observer for Virtual Servers
  useEffect(() => {
    if (!loadMoreVsRef.current || activeTab !== "virtual-servers") return;

    const observer = new IntersectionObserver(
      (entries) => {
        const [entry] = entries;
        if (entry.isIntersecting && hasMoreVs && !isLoadingMoreVs && !isLoadingVs && !searchTerm) {
          loadMoreVs();
        }
      },
      {
        root: null,
        rootMargin: "100px",
        threshold: 0.1,
      }
    );

    observer.observe(loadMoreVsRef.current);

    return () => {
      observer.disconnect();
    };
  }, [hasMoreVs, isLoadingMoreVs, isLoadingVs, searchTerm, loadMoreVs, activeTab]);

  // Tools are now filtered server-side via search and tags params
  // No need for client-side filtering

  // Filter virtual servers based on search
  const filteredVirtualServers = virtualServers.filter((server) => {
    return (
      !searchTerm ||
      server.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      server.description.toLowerCase().includes(searchTerm.toLowerCase())
    );
  });

  const handleTagFilter = (tag: string) => {
    setActiveFilters((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(tag)) {
        newSet.delete(tag);
      } else {
        newSet.add(tag);
      }
      return newSet;
    });
  };

  const handleAddTool = () => {
    openDrawer("add-tool");
  };

  const handleAddVirtualServer = () => {
    openDrawer("add-tool");
  };

  const goToVirtualServerDetails = async (server: VirtualServer) => {
    setSelectedVirtualServer(server);
    openDrawer("view-virtual-server");
  };

  if (!isMounted) return null;

  return (
    <DashBoardLayout>
      <div className="boardPageView">
        <div className="boardPageTop">
          <PageHeader
            headding="Tools"
            ButtonIcon={PlusOutlined}
            buttonLabel="Tool"
            buttonPermission={true}
            buttonAction={handleAddTool}
            rightComponent={
              <div className="flex items-center gap-3 mr-[.5rem]">
                <SecondaryButton onClick={handleAddVirtualServer}>
                  <div className="flex items-center justify-center gap-[.3rem]">
                    <PlusOutlined className="text-[#B3B3B3] text-[12px]" />
                    Add virtual server
                  </div>
                </SecondaryButton>
              </div>
            }
          />
        </div>

        <div className="boardMainContainer listingContainer" id="tools-list">
          {/* Tabs */}
          <div className="flex items-center gap-6 mt-[1.5rem] border-b border-[#1F1F1F]">
            <button
              onClick={() => setActiveTab("tools")}
              className={`pb-3 text-sm font-medium transition-colors relative ${
                activeTab === "tools"
                  ? "text-[#EEEEEE]"
                  : "text-[#6A6E76] hover:text-[#B3B3B3]"
              }`}
            >
              Tools
              {activeTab === "tools" && (
                <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-[#965CDE]" />
              )}
            </button>
            <button
              onClick={() => setActiveTab("virtual-servers")}
              className={`pb-3 text-sm font-medium transition-colors relative ${
                activeTab === "virtual-servers"
                  ? "text-[#EEEEEE]"
                  : "text-[#6A6E76] hover:text-[#B3B3B3]"
              }`}
            >
              Virtual Servers
              {activeTab === "virtual-servers" && (
                <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-[#965CDE]" />
              )}
            </button>
          </div>

          {/* Tools Tab Content */}
          {activeTab === "tools" && (
            <>
              {/* Filter Tags Row */}
              <div className="flex items-center justify-between mt-[1.25rem] mb-[1.25rem]">
                <div className="flex items-center gap-2 flex-wrap">
                  {filterTags.length > 0 ? (
                    filterTags.map((tag) => (
                      <div
                        key={tag.name}
                        onClick={() => handleTagFilter(tag.name)}
                        className={`cursor-pointer transition-all rounded-[6px] ${
                          activeFilters.has(tag.name)
                            ? "ring-2 ring-[#965CDE] ring-offset-1 ring-offset-[#101010]"
                            : "opacity-70 hover:opacity-100"
                        }`}
                      >
                        <ProjectTags name={tag.name} color={tag.color} />
                      </div>
                    ))
                  ) : (
                    <Text_12_400_6A6E76>No tags available</Text_12_400_6A6E76>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <SearchHeaderInput
                    placeholder="Search tools..."
                    searchValue={searchTerm}
                    setSearchValue={setSearchTerm}
                    classNames=""
                  />
                  <label
                    className="group h-[1.7rem] text-[#EEEEEE] mx-2 flex items-center cursor-pointer text-xs font-normal leading-3 rounded-[6px] shadow-none bg-transparent"
                  >
                    <svg
                      width="15"
                      height="15"
                      viewBox="0 0 15 15"
                      fill="none"
                      xmlns="http://www.w3.org/2000/svg"
                      style={{ width: "0.875rem", height: "0.875rem" }}
                      className="text-[#B3B3B3] group-hover:text-[#FFFFFF]"
                    >
                      <path
                        fillRule="evenodd"
                        clipRule="evenodd"
                        d="M5.5 3C4.67157 3 4 3.67157 4 4.5C4 5.32843 4.67157 6 5.5 6C6.32843 6 7 5.32843 7 4.5C7 3.67157 6.32843 3 5.5 3ZM3 5C3.01671 5 3.03323 4.99918 3.04952 4.99758C3.28022 6.1399 4.28967 7 5.5 7C6.71033 7 7.71978 6.1399 7.95048 4.99758C7.96677 4.99918 7.98329 5 8 5H13.5C13.7761 5 14 4.77614 14 4.5C14 4.22386 13.7761 4 13.5 4H8C7.98329 4 7.96677 4.00082 7.95048 4.00242C7.71978 2.86009 6.71033 2 5.5 2C4.28967 2 3.28022 2.86009 3.04952 4.00242C3.03323 4.00082 3.01671 4 3 4H1.5C1.22386 4 1 4.22386 1 4.5C1 4.77614 1.22386 5 1.5 5H3ZM11.9505 10.9976C11.7198 12.1399 10.7103 13 9.5 13C8.28967 13 7.28022 12.1399 7.04952 10.9976C7.03323 10.9992 7.01671 11 7 11H1.5C1.22386 11 1 10.7761 1 10.5C1 10.2239 1.22386 10 1.5 10H7C7.01671 10 7.03323 10.0008 7.04952 10.0024C7.28022 8.8601 8.28967 8 9.5 8C10.7103 8 11.7198 8.8601 11.9505 10.0024C11.9668 10.0008 11.9833 10 12 10H13.5C13.7761 10 14 10.2239 14 10.5C14 10.7761 13.7761 11 13.5 11H12C11.9833 11 11.9668 10.9992 11.9505 10.9976ZM8 10.5C8 9.67157 8.67157 9 9.5 9C10.3284 9 11 9.67157 11 10.5C11 11.3284 10.3284 12 9.5 12C8.67157 12 8 11.3284 8 10.5Z"
                        fill="currentColor"
                      />
                    </svg>
                  </label>
                </div>
              </div>

              {/* Loading State */}
              {isLoading && (
                <Text_12_400_6A6E76 className="mt-5">
                  Loading tools...
                </Text_12_400_6A6E76>
              )}

              {/* Empty State */}
              {!isLoading && !tools.length && !debouncedSearch && activeFilters.size === 0 && (
                <Text_12_400_6A6E76 className="mt-5">
                  No tools have been added yet. Click the "Add Tool" button to get
                  started.
                </Text_12_400_6A6E76>
              )}

              {!isLoading && (debouncedSearch || activeFilters.size > 0) && !tools.length && (
                <NoDataFount
                  classNames="h-[60vh]"
                  textMessage={`No tools found matching your criteria`}
                />
              )}

              {/* Tools Grid */}
              <div className="grid gap-[1.1rem] grid-cols-3 mt-[1rem] pb-[1.1rem]">
                {tools.length > 0 ? (
                  <>
                    {tools.map((tool, index) => (
                      <div
                        className="flex flex-col justify-start toolCards min-h-[280px] 1680px:min-h-[320px] border border-[#1F1F1F] rounded-lg text-[1rem] 1680px:text-[1.1rem] bg-[#101010] overflow-hidden"
                        key={index}
                      >
                        <div className="flex flex-col justify-start pr-[1.5em] pl-[1.5em] pt-[1.6em] h-full">
                          <div className="min-h-[140px]">
                            <div className="flex justify-between w-full">
                              <div className="flex items-center justify-center bg-[#1F1F1F] w-[2.40125rem] h-[2.40125rem] rounded">
                                <div className="text-[1.5625rem]">{tool.icon}</div>
                              </div>
                            </div>
                            <div className="pl-[.1rem] pt-[1.25rem]">
                              <Text_11_400_808080>
                                {formatDate(tool.created_at)}
                              </Text_11_400_808080>
                              <Text_17_600_FFFFFF className="pt-[.35em] text-wrap pr-1 truncate-text max-w-[90%]">
                                {tool.name}
                              </Text_17_600_FFFFFF>
                              <Text_13_400_B3B3B3 className="pt-[.85em] pr-[.45em] text-[0.75em] tracking-[.01em] line-clamp-2 overflow-hidden display-webkit-box leading-[150%]">
                                {tool.description}
                              </Text_13_400_B3B3B3>
                            </div>
                          </div>
                          <div
                            className="flex gap-[.45rem] justify-start items-center mt-[1.1rem] flex-wrap overflow-hidden mb-[1.1rem]"
                            style={{
                              maxHeight: "4rem",
                              lineHeight: "1.5rem",
                            }}
                          >
                            <TagsList data={tool.tags} />
                          </div>
                        </div>
                        <div className="flex justify-between items-center pt-[1.1rem] pr-[1.5em] pl-[1.5em] pb-[1.45em] bg-[#161616]">
                          <div>
                            <Text_17_600_FFFFFF className="block px-[.2em] group-hover:text-[#FFFFFF] text[0.75rem] leading-[100%]">
                              {tool.executionCount || 0}
                            </Text_17_600_FFFFFF>
                            <Text_13_400_B3B3B3 className="pt-[.3rem]">
                              Usages
                            </Text_13_400_B3B3B3>
                          </div>
                        </div>
                      </div>
                    ))}
                  </>
                ) : (
                  !isLoading && !debouncedSearch &&
                  activeFilters.size === 0 && (
                    <div
                      className="flex justify-center items-center w-[100%] min-h-[182px] border border-[#2F3035] rounded-lg bg-[#18191B] cursor-pointer"
                      onClick={handleAddTool}
                    >
                      <Text_14_400_C7C7C7>+ Add Tool</Text_14_400_C7C7C7>
                    </div>
                  )
                )}
              </div>

              {/* Load More Sentinel & Indicator */}
              <div ref={loadMoreRef} className="flex justify-center items-center py-6">
                {isLoadingMore && (
                  <div className="flex items-center gap-2">
                    <Spin size="small" />
                    <Text_12_400_6A6E76>Loading more tools...</Text_12_400_6A6E76>
                  </div>
                )}
                {!hasMore && tools.length > 0 && (
                  <Text_12_400_6A6E76>No more tools to load</Text_12_400_6A6E76>
                )}
              </div>
            </>
          )}

          {/* Virtual Servers Tab Content */}
          {activeTab === "virtual-servers" && (
            <>
              {/* Search Row for Virtual Servers */}
              <div className="flex items-center justify-end mt-[1.25rem] mb-[1.25rem]">
                <SearchHeaderInput
                  placeholder="Search virtual servers..."
                  searchValue={searchTerm}
                  setSearchValue={setSearchTerm}
                  classNames=""
                />
              </div>

              {/* Loading State */}
              {isLoadingVs && (
                <Text_12_400_6A6E76 className="mt-5">
                  Loading virtual servers...
                </Text_12_400_6A6E76>
              )}

              {/* Empty State */}
              {!isLoadingVs && !filteredVirtualServers.length && !searchTerm && (
                <Text_12_400_6A6E76 className="mt-5">
                  No virtual servers have been created yet. Create one by adding tools and selecting "Create Virtual Server".
                </Text_12_400_6A6E76>
              )}

              {searchTerm && !filteredVirtualServers.length && (
                <NoDataFount
                  classNames="h-[60vh]"
                  textMessage={`No virtual servers found matching your search`}
                />
              )}

              {/* Virtual Servers Grid */}
              <div className="grid gap-[1.1rem] grid-cols-3 mt-[1rem] pb-[1.1rem]">
                {filteredVirtualServers.length > 0 ? (
                  <>
                    {filteredVirtualServers.map((server, index) => (
                      <div
                        className="flex flex-col justify-start toolCards min-h-[200px] border border-[#1F1F1F] rounded-lg cursor-pointer text-[1rem] hover:shadow-[1px_1px_6px_-1px_#2e3036] bg-[#101010] overflow-hidden"
                        key={index}
                        onClick={() => goToVirtualServerDetails(server)}
                      >
                        <div className="flex flex-col justify-start pr-[1.5em] pl-[1.5em] pt-[1.6em] h-full">
                          <div className="min-h-[100px]">
                            <div className="flex justify-between w-full">
                              <div className="flex items-center justify-center bg-[#1F1F1F] w-[2.40125rem] h-[2.40125rem] rounded">
                                <div className="text-[1.5625rem]">🖥️</div>
                              </div>
                              <span className={`px-2 py-1 text-[0.625rem] rounded ${
                                server.visibility === "public"
                                  ? "bg-[#22C55E]/20 text-[#22C55E]"
                                  : "bg-[#F59E0B]/20 text-[#F59E0B]"
                              }`}>
                                {server.visibility}
                              </span>
                            </div>
                            <div className="pl-[.1rem] pt-[1.25rem]">
                              <Text_11_400_808080>
                                {server.created_at ? formatDate(server.created_at) : "—"}
                              </Text_11_400_808080>
                              <Text_17_600_FFFFFF className="pt-[.35em] text-wrap pr-1 truncate-text max-w-[90%]">
                                {server.name}
                              </Text_17_600_FFFFFF>
                              {server.description && (
                                <Text_13_400_B3B3B3 className="pt-[.85em] pr-[.45em] text-[0.75em] tracking-[.01em] line-clamp-2 overflow-hidden display-webkit-box leading-[150%]">
                                  {server.description}
                                </Text_13_400_B3B3B3>
                              )}
                            </div>
                          </div>
                        </div>
                        <div className="flex justify-between items-center pt-[1.1rem] pr-[1.5em] pl-[1.5em] pb-[1.45em] bg-[#161616]">
                          <div>
                            <Text_17_600_FFFFFF className="block px-[.2em] group-hover:text-[#FFFFFF] text[0.75rem] leading-[100%]">
                              {server.toolsCount}
                            </Text_17_600_FFFFFF>
                            <Text_13_400_B3B3B3 className="pt-[.3rem]">
                              Tools
                            </Text_13_400_B3B3B3>
                          </div>
                        </div>
                      </div>
                    ))}
                  </>
                ) : (
                  !searchTerm && (
                    <div
                      className="flex justify-center items-center w-[100%] min-h-[182px] border border-[#2F3035] rounded-lg bg-[#18191B] cursor-pointer"
                      onClick={handleAddVirtualServer}
                    >
                      <Text_14_400_C7C7C7>+ Add Virtual Server</Text_14_400_C7C7C7>
                    </div>
                  )
                )}
              </div>

              {/* Load More Sentinel & Indicator for Virtual Servers */}
              {!searchTerm && (
                <div ref={loadMoreVsRef} className="flex justify-center items-center py-6">
                  {isLoadingMoreVs && (
                    <div className="flex items-center gap-2">
                      <Spin size="small" />
                      <Text_12_400_6A6E76>Loading more virtual servers...</Text_12_400_6A6E76>
                    </div>
                  )}
                  {!hasMoreVs && virtualServers.length > 0 && (
                    <Text_12_400_6A6E76>No more virtual servers to load</Text_12_400_6A6E76>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </DashBoardLayout>
  );
};

export default Tools;

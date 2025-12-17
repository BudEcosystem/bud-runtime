"use client";
import { useEffect, useState } from "react";
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

// Available filter tags with colors
const filterTags = [
  { name: "Tag 1", color: "#965CDE" },
  { name: "Tag 2", color: "#22C55E" },
  { name: "tag 3", color: "#F59E0B" },
  { name: "tool", color: "#3B82F6" },
  { name: "virtual", color: "#EF4444" },
];

const Tools = () => {
  const [isMounted, setIsMounted] = useState(false);
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [activeFilters, setActiveFilters] = useState<Set<string>>(new Set());

  const { openDrawer } = useDrawer();
  const { tools, getTools, setSelectedTool } = useTools();

  useEffect(() => {
    setIsMounted(true);
    getTools();
  }, []);

  // Filter tools based on search and active filters
  const filteredTools = tools.filter((tool) => {
    const matchesSearch =
      !searchTerm ||
      tool.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      tool.description.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesFilter =
      activeFilters.size === 0 ||
      tool.tags.some((tag) => activeFilters.has(tag.name));

    return matchesSearch && matchesFilter;
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
    // TODO: Implement add virtual server functionality
    console.log("Add Virtual Server clicked");
  };

  const goToDetails = async (tool: Tool) => {
    setSelectedTool(tool);
    openDrawer("view-tool");
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
          {/* Filter Tags Row */}
          <div className="flex items-center justify-between mt-[1.5rem] mb-[1.25rem]">
            <div className="flex items-center gap-2 flex-wrap">
              {filterTags.map((tag) => (
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
              ))}
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

          {/* Empty State */}
          {!filteredTools.length && !searchTerm && activeFilters.size === 0 && (
            <Text_12_400_6A6E76 className="mt-5">
              No tools have been added yet. Click the "Add Tool" button to get
              started.
            </Text_12_400_6A6E76>
          )}

          {(searchTerm || activeFilters.size > 0) && !filteredTools.length && (
            <NoDataFount
              classNames="h-[60vh]"
              textMessage={`No tools found matching your criteria`}
            />
          )}

          {/* Tools Grid */}
          <div className="grid gap-[1.1rem] grid-cols-3 mt-[1rem] pb-[1.1rem]">
            {filteredTools.length > 0 ? (
              <>
                {filteredTools.map((tool, index) => (
                  <div
                    className="flex flex-col justify-start toolCards min-h-[280px] 1680px:min-h-[320px] border border-[#1F1F1F] rounded-lg cursor-pointer text-[1rem] 1680px:text-[1.1rem] hover:shadow-[1px_1px_6px_-1px_#2e3036] bg-[#101010] overflow-hidden"
                    key={index}
                    onClick={() => goToDetails(tool)}
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
                          {tool.usage_count}
                        </Text_17_600_FFFFFF>
                        <Text_13_400_B3B3B3 className="pt-[.3rem]">
                          Usages
                        </Text_13_400_B3B3B3>
                      </div>
                      <span className="bg-[#965CDE33] text-[#CFABFC] px-3 py-[5px] rounded-[6px] border border-[#CFABFC] text-[0.625rem] leading-[100%]">
                        {tool.category}
                      </span>
                    </div>
                  </div>
                ))}
              </>
            ) : (
              !searchTerm &&
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
        </div>
      </div>
    </DashBoardLayout>
  );
};

export default Tools;

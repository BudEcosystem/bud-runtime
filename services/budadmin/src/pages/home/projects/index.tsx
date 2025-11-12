/* eslint-disable react/no-unescaped-entities */
"use client";
import { Box, Flex } from "@radix-ui/themes";
import { PlusIcon, Share1Icon } from "@radix-ui/react-icons";
import { useEffect, useState, useRef } from "react";
import React from "react";
import DashBoardLayout from "../layout";
import {
  Text_11_400_808080,
  Text_12_400_6A6E76,
  Text_13_400_B3B3B3,
  Text_14_400_C7C7C7,
  Text_17_600_FFFFFF,
} from "@/components/ui/text";
import router from "next/router";
import PageHeader from "@/components/ui/pageHeader";
import NoAccess from "@/components/ui/noAccess";
import { formatDate } from "src/utils/formatDate";
import { useProjects } from "src/hooks/useProjects";
import { useDrawer } from "src/hooks/useDrawer";
import SharedWithUsers from "@/components/ui/bud/drawer/SharedWithUsers";
import { useLoader } from "src/context/appContext";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import NoDataFount from "@/components/ui/noDataFount";
import TagsList from "src/flows/components/TagsList";
import { PermissionEnum, useUser } from "src/stores/useUser";
import { PlusOutlined } from "@ant-design/icons";

const Projects = () => {
  const [isMounted, setIsMounted] = useState(false);
  const { hasPermission, loadingUser, hasProjectPermission } = useUser();
  const {
    globalProjects,
    getGlobalProjects,
    getProject,
    totalProjects,
    totalPages,
  } = useProjects();
  const { openDrawer } = useDrawer();

  const [searchTerm, setSearchTerm] = React.useState<string>("");
  // for pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const { showLoader, hideLoader } = useLoader();

  // Add refs to prevent multiple API calls
  const isLoadingMore = useRef(false);
  const lastScrollTop = useRef(0);

  const goToDetails = (item) => {
    router.push(`/projects/${item.project.id}`);
  };

  const load = async (page: number, size: number, searchTerm?: string, isInfiniteScroll: boolean = false) => {
    if (hasPermission(PermissionEnum.ProjectView)) {
      // Prevent multiple simultaneous calls for infinite scroll
      if (isInfiniteScroll && isLoadingMore.current) {
        return;
      }

      if (isInfiniteScroll) {
        isLoadingMore.current = true;
      }

      setCurrentPage(page);
      setPageSize(size);

      if (!isInfiniteScroll) {
        showLoader();
      }

      await getGlobalProjects(page, size, searchTerm);

      if (!isInfiniteScroll) {
        hideLoader();
      }

      if (isInfiniteScroll) {
        isLoadingMore.current = false;
      }
    }
  };

  // Initial load
  useEffect(() => {
    if (isMounted && hasPermission(PermissionEnum.ProjectView)) {
      load(1, pageSize);
    }
  }, [isMounted]);

  // Search with debounce
  useEffect(() => {
    if (!isMounted) return;

    // Reset loading state when search changes
    isLoadingMore.current = false;
    lastScrollTop.current = 0;

    const timer = setTimeout(() => {
      load(1, pageSize, searchTerm);
    }, 500);
    return () => clearTimeout(timer);
  }, [searchTerm]);

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
      globalProjects?.length < totalProjects &&
      currentPage < totalPages
    ) {
      const nextPage = currentPage + 1;
      load(nextPage, pageSize, searchTerm, true);
    }
  };

  useEffect(() => {
    setIsMounted(true);
  }, []);

  return (
    <DashBoardLayout>
      <Box className="boardPageView">
        <Box className="boardPageTop">
          <PageHeader
            headding="Projects"
            ButtonIcon={PlusOutlined}
            buttonLabel="Project"
            buttonPermission={hasPermission(PermissionEnum.ProjectManage)}
            // buttonAction={() => openFlow("project-success")}
            buttonAction={() => {
              openDrawer("new-project");
            }}
            rightComponent={
              hasPermission(PermissionEnum.ProjectManage) && (
                <>
                  <SearchHeaderInput
                    placeholder="Search by name or tags"
                    searchValue={searchTerm}
                    setSearchValue={setSearchTerm}
                    classNames="mr-[.6rem]"
                  />
                </>
              )
            }
          />
        </Box>
        {/* <button onClick={() => openFlow("new-project")}>open</button> */}
        {hasPermission(PermissionEnum.ProjectView) ? (
          <Box
            className="boardMainContainer listingContainer"
            id="project-repo"
            onScroll={handleScroll}
          >
            {!globalProjects?.length && !searchTerm && (
              <Text_12_400_6A6E76 className="mt-5">
                Let’s start creating project on the Bud Inference engine.
                Currently no projects have been created
              </Text_12_400_6A6E76>
            )}
            {searchTerm && !globalProjects?.length && (
              <NoDataFount
                classNames="h-[60vh]"
                textMessage={`No projects found for the search term ${searchTerm}`}
              />
            )}
            <div className="grid gap-[1.1rem] grid-cols-3 mt-[2.95rem] 1680px:mt-[1.75rem] pb-[1.1rem]">
              {globalProjects?.length > 0 ? (
                <>
                  {globalProjects?.map((item: any, index) => (
                    <Flex
                      direction="column"
                      justify="start"
                      className="projectCards min-h-[325px] 1680px:min-h-[400px] 2048px:min-h-[475px] border border-[#1F1F1F] rounded-lg cursor-pointer text-[1rem] 1680px:text-[1.1rem]  hover:shadow-[1px_1px_6px_-1px_#2e3036] bg-[#101010] overflow-hidden"
                      key={index}
                      onClick={() => goToDetails(item)}
                    >
                      <Flex
                        direction={"column"}
                        justify={"start"}
                        className="pr-[1.5em] pl-[1.5em] pt-[1.6em] h-full"
                      >
                        <Box className="min-h-[160px]">
                          <Flex justify="between" className="w-full">
                            <Flex
                              align={"center"}
                              justify={"center"}
                              className="bg-[#1F1F1F] w-[2.40125rem] h-[2.40125rem] rounded"
                            >
                              <div className="text-[1.5625rem]">
                                {item.project.icon}
                              </div>
                            </Flex>
                            <Flex>
                              {hasPermission(PermissionEnum.ProjectManage) ||
                              hasProjectPermission(
                                item.project.id,
                                PermissionEnum.ProjectManage,
                              ) ? (
                                <Flex
                                  align={"center"}
                                  justify={"end"}
                                  className="w-[2.40125rem] h-[2.40125rem] rounded"
                                  onClick={async (e) => {
                                    e.stopPropagation();
                                    await getProject(item.project.id);
                                    openDrawer("add-members");
                                  }}
                                >
                                  <Share1Icon className="text-[#B3B3B3]"></Share1Icon>
                                </Flex>
                              ) : (
                                <></>
                              )}
                            </Flex>
                          </Flex>
                          <Box className="pl-[.1rem] pt-[1.25rem]">
                            <Text_11_400_808080>
                              {formatDate(item.project.created_at)}
                            </Text_11_400_808080>
                            <Text_17_600_FFFFFF className="pt-[.35em] text-wrap	pr-1 truncate-text max-w-[90%]">
                              {item.project.name}
                            </Text_17_600_FFFFFF>
                            <Text_13_400_B3B3B3 className="pt-[.85em] pr-[.45em] text-[0.75em] tracking-[.01em] line-clamp-2 overflow-hidden display-webkit-box leading-[150%]">
                              {item.project.description}
                            </Text_13_400_B3B3B3>
                          </Box>
                        </Box>
                        <Flex
                          gap=".45rem"
                          justify={"start"}
                          align={"center"}
                          className="mt-[1.1rem] flex-wrap overflow-hidden mb-[1.1rem]"
                          style={{
                            maxHeight: "4rem", // Limit the height to approximately two rows (adjust based on tag size)
                            lineHeight: "1.5rem", // Adjust this value according to your tag's vertical spacing
                          }}
                        >
                          <TagsList data={item.project.tags} />
                        </Flex>
                      </Flex>
                      <Flex
                        justify={"between"}
                        align={"center"}
                        className="pt-[1.1rem] pr-[1.5em] pl-[1.5em] pb-[1.45em] bg-[#161616]"
                      >
                        <Box>
                          <Text_17_600_FFFFFF className="block px-[.2em] group-hover:text-[#FFFFFF] text[0.75rem] leading-[100%]">
                            {item.endpoints_count}
                            {/* 20 */}
                          </Text_17_600_FFFFFF>
                          <Text_13_400_B3B3B3 className="pt-[.3rem]">
                            Deployments
                          </Text_13_400_B3B3B3>
                        </Box>
                        <SharedWithUsers
                          users_count={item.users_count}
                          users_colours={item.profile_colors}
                        />
                      </Flex>
                    </Flex>
                  ))}
                </>
              ) : (
                !searchTerm && (
                  <>
                    {hasPermission(PermissionEnum.ProjectManage) ? (
                      <Flex
                        justify="center"
                        align="center"
                        className="w-[100%] min-h-[182px] border border-[#2F3035] rounded-lg bg-[#18191B] cursor-pointer"
                        onClick={() => openDrawer("new-project")}
                      >
                        <Text_14_400_C7C7C7>+ Project</Text_14_400_C7C7C7>
                      </Flex>
                    ) : (
                      <Flex
                        justify="center"
                        align="center"
                        className="w-[100%] min-h-[182px] border border-[#2F3035] rounded-lg bg-[#18191B] cursor-pointer"
                      >
                        <Text_14_400_C7C7C7>
                          No Projects available
                        </Text_14_400_C7C7C7>
                      </Flex>
                    )}
                  </>
                )
              )}
            </div>
          </Box>
        ) : (
          !loadingUser && (
            <>
              <NoAccess textMessage="You do not have access to view projects, please ask admin to give you access to either view or edit for projects." />
            </>
          )
        )}
      </Box>
    </DashBoardLayout>
  );
};
export default Projects;

/* eslint-disable react/no-unescaped-entities */
"use client";
import { Box, Button, Flex } from "@radix-ui/themes";
import { ReloadIcon, Pencil1Icon, TrashIcon } from "@radix-ui/react-icons";
import { useEffect, useState, useRef } from "react";
import React from "react";
import DashBoardLayout from "../layout";
// import { Marker } from "../../components/marker";
import {
  Text_11_400_808080,
  Text_12_400_B3B3B3,
  Text_17_600_FFFFFF,
} from "@/components/ui/text";
import PageHeader from "@/components/ui/pageHeader";
import NoAccess from "@/components/ui/noAccess";
import { formatDate } from "src/utils/formatDate";
import { Tag, Image, notification } from "antd";
import { getChromeColor } from "@/components/ui/bud/dataEntry/TagsInputData";
import { useDrawer } from "src/hooks/useDrawer";
import { Cluster, useCluster } from "src/hooks/useCluster";
import ImageIcon from "src/flows/components/ImageIcon";
import { openWarning } from "@/components/warningMessage";
import { useOverlay } from "src/context/overlayContext";
import NoDataFount from "@/components/ui/noDataFount";
import useHandleRouteChange from "@/lib/useHandleRouteChange";
import { PermissionEnum, useUser } from "src/stores/useUser";
import router from "next/router";
import IconRender from "src/flows/components/BudIconRender";
import { useConfirmAction } from "src/hooks/useConfirmAction";
import { PlusOutlined } from "@ant-design/icons";

export default function Clusters() {
  const [isMounted, setIsMounted] = useState(false);
  const { setOverlayVisible } = useOverlay();
  const { openDrawer } = useDrawer();
  const { hasPermission, loadingUser } = useUser();
  const {
    clusters,
    getClusters,
    setCluster,
    selectedCluster,
    loading,
    deleteCluster,
    setClusterValues,
    getClusterById,
    totalClusters,
    totalPages,
  } = useCluster();
  const { contextHolder, openConfirm } = useConfirmAction();

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize] = useState(10);

  // Add refs to prevent multiple API calls
  const isLoadingMore = useRef(false);
  const lastScrollTop = useRef(0);

  const loadClusters = async (page: number, isInfiniteScroll: boolean = false) => {
    if (!hasPermission(PermissionEnum.ClusterView)) return;

    // Prevent multiple simultaneous calls for infinite scroll
    if (isInfiniteScroll && isLoadingMore.current) {
      return;
    }

    if (isInfiniteScroll) {
      isLoadingMore.current = true;
    }

    await getClusters({ page, limit: pageSize });

    if (isInfiniteScroll) {
      isLoadingMore.current = false;
    }
  };

  // Initial load
  useEffect(() => {
    if (isMounted && hasPermission(PermissionEnum.ClusterView)) {
      loadClusters(1, false);
    }
  }, [isMounted]);

  useHandleRouteChange(() => {
    notification.destroy();
  });

  const handleOpenDialogEdit = (cluster: Cluster) => {
    setCluster(cluster);
    openDrawer("edit-cluster");
  };

  const handleOpenDialogDelete = (cluster: Cluster) => {
    setCluster(cluster);
    openDrawer("delete-cluster");
  };
  const triggerDeleteNotification = (item) => {
    openConfirm({
      message: `You're about to delete the Cluster ${item.name}`,
      description:
        item.endpoint_count > 0
          ? "The cluster is running and you will not be allowed to delete the cluster. In order to delete the cluster, you will have to pause or delete all deployments in order to delete the cluster."
          : "You are about to delete the cluster. Once deleted, you won’t be able to recover. Please confirm, if you would like to proceed.",
      okAction: () => {
        deleteCluster(item.id).then((result) => {
          if (result.status == "200") {
            openWarning({
              title: "You're about to delete the Cluster",
              description: result?.data?.message,
              deleteDisabled: true,
            });
            setTimeout(() => {
              notification.destroy(
                "You're about to delete the Cluster-delete-notification",
              );
              setOverlayVisible(false);
            }, 4000);
          } else {
            openWarning({
              title: "You're about to delete the Cluster",
              description: "Cannot delete cluster with active deployments",
              deleteDisabled: true,
              onCancel: () => {
                setOverlayVisible(false);
              },
            });
          }
        });
      },
      cancelAction: () => {
        setOverlayVisible(false);
      },
      loading: false,
      cancelText: "Cancel",
      okText: "Delete",
      key: "delete-cluster",
      type: "warining",
    });
  };

  const goToDetails = (item) => {
    router.push(`/clusters/${item.id}`);
  };

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
      totalClusters &&
      totalPages &&
      clusters.length < totalClusters &&
      currentPage < totalPages
    ) {
      const nextPage = currentPage + 1;
      setCurrentPage(nextPage);
      loadClusters(nextPage, true);
    }
  };

  useEffect(() => {
    setIsMounted(true);
  }, []);

  return (
    <DashBoardLayout>
      {contextHolder}
      <div className="boardPageView">
        <div className="boardPageTop">
          <PageHeader
            headding="Clusters"
            buttonLabel="Cluster"
            ButtonIcon={PlusOutlined}
            buttonPermission={hasPermission(PermissionEnum.ClusterManage)}
            buttonAction={() => {
              setClusterValues({});
              openDrawer("add-cluster-select-source");
              //openDrawer("add-cluster");
              //openDrawer("add-cluster-select-source");
            }}
          />
        </div>
        {hasPermission(PermissionEnum.ClusterView) ? (
          <div
            className="boardMainContainer listingContainer scroll-smooth"
            onScroll={handleScroll}
          >
            {clusters.length > 0 ? (
              <div className="grid gap-[1.1rem] grid-cols-3 mt-[2.95rem] 1680px:mt-[1.75rem] pb-[1.1rem]">
                <>
                  {clusters.map((item: Cluster, index) => (
                    <div
                      className="flex flex-col justify-between w-full bg-[#101010] border border-[#1F1F1F] rounded-lg pt-[1.54em] 1680px:pt-[1.85em] min-h-[325px] 1680px:min-h-[400px] 2048px:min-h-[475px] cursor-pointer hover:shadow-[1px_1px_6px_-1px_#2e3036] overflow-hidden"
                      key={index}
                      onClick={async () => {
                        await getClusterById(item.id);
                        goToDetails(item);
                      }}
                    >
                      <div className="px-[1.6rem] pb-[1.54em]">
                        <div className="pr-0 flex justify-between items-start gap-3">
                          <div className="w-[calc(100%-80px)]">
                            <div className="w-[2.40125rem] h-[2.40125rem] bg-[#1F1F1F] rounded-[5px] flex items-center justify-center">
                              <IconRender
                                icon={item.icon}
                                size={26}
                                imageSize={24}
                              />
                            </div>
                          </div>
                        </div>
                        <div className="mt-[1.3rem]">
                          <Text_11_400_808080>
                            {formatDate(item.created_at)}
                          </Text_11_400_808080>
                        </div>
                        <div className="mt-[.75rem]">
                          <Text_17_600_FFFFFF className="max-w-[100] truncate w-[calc(100%-20px)] leading-[0.964375rem]">
                            {item.name}
                          </Text_17_600_FFFFFF>
                        </div>

                        <div className="flex items-center pt-[1.1em]">
                          {item.endpoint_count > 0 && (
                            <Tag
                              className={`text-[#B3B3B3] border-[0] rounded-[6px] cursor-pointer hover:text-[#EEEEEE] flex justify-center items-center py-[.3rem] px-[.4rem]`}
                              style={{
                                backgroundColor: getChromeColor("#8F55D62B"),
                              }}
                            >
                              <div className="w-[0.625rem] h-[0.625rem] flex justify-center items-center mr-[.3rem]">
                                <Image
                                  preview={false}
                                  src="/images/drawer/rocket.png"
                                  alt="info"
                                  style={{
                                    width: "0.625rem",
                                    height: "0.625rem",
                                  }}
                                />
                              </div>
                              <div
                                className={`text-[0.625rem] font-[400] leading-[100%]`}
                                style={{
                                  color: "#965CDE",
                                }}
                              >
                                {item.endpoint_count}
                              </div>
                            </Tag>
                          )}

                          {item.cpu_count > 0 && (
                            <Tag
                              className={`text-[#B3B3B3] border-[0] rounded-[6px] cursor-pointer hover:text-[#EEEEEE] flex justify-center items-center py-[.3rem] px-[.4rem]`}
                              style={{
                                backgroundColor: getChromeColor("#423A1A40"),
                              }}
                            >
                              <div
                                className={`text-[0.625rem] font-[400] leading-[100%]`}
                                style={{
                                  color: "#D1B854",
                                }}
                              >
                                {item.cpu_count}&nbsp;CPU
                              </div>
                            </Tag>
                          )}

                          {item.gpu_count > 0 && (
                            <Tag
                              className={`text-[#B3B3B3] border-[0] rounded-[6px] cursor-pointer hover:text-[#EEEEEE] flex justify-center items-center py-[.3rem] px-[.4rem]`}
                              style={{
                                backgroundColor: getChromeColor("#423A1A40"),
                              }}
                            >
                              <div
                                className={`text-[0.625rem] font-[400] leading-[100%]`}
                                style={{
                                  color: "#D1B854",
                                }}
                              >
                                {item.gpu_count}&nbsp;GPU
                              </div>
                            </Tag>
                          )}

                          {item.hpu_count > 0 && (
                            <Tag
                              className={`text-[#B3B3B3] border-[0] rounded-[6px] cursor-pointer hover:text-[#EEEEEE] flex justify-center items-center py-[.3rem] px-[.4rem]`}
                              style={{
                                backgroundColor: getChromeColor("#423A1A40"),
                              }}
                            >
                              <div
                                className={`text-[0.625rem] font-[400] leading-[100%]`}
                                style={{
                                  color: "#D1B854",
                                }}
                              >
                                {item.hpu_count}&nbsp;HPU
                              </div>
                            </Tag>
                          )}
                        </div>
                        {item.status && (
                          <Box
                            className={`inline-block rounded-[6px] px-[.3em] mt-[.5rem] py-[.15em] capitalize 1680px:px-[.55em] 1680px:py-[.4em] bg-${item.status}`}
                          >
                            <div className="Color text-[0.625rem] font-[400] leading-[0.965625rem]">
                              {item.status === "not_available"
                                ? "not available"
                                : item.status === "error"
                                  ? "Error"
                                  : item.status === "deleting"
                                    ? "Deleting"
                                    : "available"}
                            </div>
                          </Box>
                        )}
                      </div>
                      <div className="px-[1.6rem] bg-[#161616] pt-[1.4rem] pb-[1.5rem]  border-t-[.5px] border-t-[#1F1F1F]">
                        <Text_12_400_B3B3B3 className="mb-[.7rem]">
                          Resource Availability
                        </Text_12_400_B3B3B3>
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
                              {item.available_nodes}&nbsp;Available Nodes
                            </div>
                          </Tag>
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
                              {item.total_nodes}&nbsp;Total Nodes
                            </div>
                          </Tag>
                        </div>
                      </div>
                    </div>
                  ))}
                </>
              </div>
            ) : (
              <Box>
                <>
                  {!loading && (
                    <NoDataFount
                      classNames="h-[60vh]"
                      textMessage="No clusters available"
                    />
                  )}
                </>
                {/* {hasPermission(PermissionEnum.ClusterManage) && (
                  <Flex
                    className="bg-[#18191B] w-full rounded-xl p-4 h-[96px] max-w-[30%] rounded-lg border border-[#1A1A1A] bg-[#18191B] mt-8"
                    justify="center"
                    align="center"
                  >
                    <Button
                      className="bg-[transparent] text-sm border-0 shadow-none hover:border-0"
                      onClick={() => {
                        setClusterValues({});
                        openDrawer("add-cluster");
                      }}
                    >
                      + Add Cluster
                    </Button>
                  </Flex>
                )} */}
              </Box>
            )}
          </div>
        ) : (
          <>
            {!loading && !loadingUser && (
              <NoAccess textMessage="You do not have access to view the cluster repository, please ask admin to give you access to either view or edit for clusters." />
            )}
          </>
        )}
      </div>
    </DashBoardLayout>
  );
}

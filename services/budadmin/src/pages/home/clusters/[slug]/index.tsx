"use client";
import { useRouter } from "next/router";
import React, { useEffect, useState } from "react";
import DashBoardLayout from "../../layout";
import {
  Text_12_400_B3B3B3,
  Text_14_600_B3B3B3,
  Text_14_600_EEEEEE,
} from "@/components/ui/text";
import { Project, useProjects } from "src/hooks/useProjects";
import { useDrawer } from "src/hooks/useDrawer";
import { NameIconDisplay } from "@/components/ui/bud/dataEntry/ProjectNameInput";
import { Tabs, Image, Flex, Button } from "antd";
import Tags from "src/flows/components/DrawerTags";
import { CustomBreadcrumb } from "@/components/ui/bud/card/DrawerBreadCrumbNavigation";
import BackButton from "@/components/ui/bud/drawer/BackButton";
import { formatDate } from "src/utils/formatDate";
import { SharedWithProjectUsers } from "@/components/ui/bud/drawer/SharedWithUsers";
import { notification } from "antd";
import { useOverlay } from "src/context/overlayContext";
import { openWarning } from "@/components/warningMessage";
import { useEndPoints } from "src/hooks/useEndPoint";
import useHandleRouteChange from "@/lib/useHandleRouteChange";
import { PermissionEnum, useUser } from "src/stores/useUser";
import ComingSoon from "@/components/ui/comingSoon";
import RoutesComponent from "../../projects/[slug]/Routes/Routes";
import AnalyticsComponent from "../../projects/[slug]/components/analytics";
import { Cluster, useCluster } from "src/hooks/useCluster";
import ClusterGeneral from "./General";
import DeploymentListTable from "./Deploymnets";
import CostAnalysis from "./CostAnalysis";
import ClusterNodes from "./Nodes";
import HealthStatus from "./HealthStatus";
import Analytics from "./Analytics";
import ClusterTags from "src/flows/components/ClusterTags";
import { Pencil1Icon, ReloadIcon } from "@radix-ui/react-icons";
import { TrashIcon } from "lucide-react";
import { useConfirmAction } from "src/hooks/useConfirmAction";
import { successToast } from "@/components/toast";

const ClusterDetailsPage = () => {
  const { hasProjectPermission, hasPermission } = useUser();
  const { setOverlayVisible } = useOverlay();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState("1");
  const [isHovered, setIsHovered] = useState(false);
  const { clustersId } = router.query; // Access the dynamic part of the route
  const { openDrawer } = useDrawer();
  const { setSelectedProjectId, selectedProject: selectedProjectResult, deleteProject, setProjectValues, projectMembers, selectedProjectId } = useProjects();
  const { clusters, getClusters, setCluster, selectedCluster, loading, deleteCluster, setClusterValues, getClusterById } = useCluster();
  const { contextHolder, openConfirm } = useConfirmAction()

  const { endPointsCount } = useEndPoints();
  const [selectedProject, setProject] = useState<Project | null>(null);
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true)
  }, []);

  useEffect(() => {
    if (selectedProjectResult) {
      setProject(selectedProjectResult);
    }
  }, [selectedProjectResult]);



  useEffect(() => {
    if (clustersId) {
      getClusterById(clustersId as string);
    }
  }, [clustersId]);

  useEffect(() => {
    console.log("selectedCluster", selectedCluster);
  }, [selectedCluster]);

  useHandleRouteChange(() => {
    notification.destroy();
  });

  const goBack = () => {
    router.back();
  };


  const HeaderContent = () => {
    return (
      <div className="flex justify-between items-center">
        {isMounted && (
          <div className="flex justify-start items-center">
            <BackButton onClick={goBack} />
            <CustomBreadcrumb
              urls={["/clusters", `/clusters/${selectedCluster.id}`, "/clusters/[slug]"]}
              data={["Clusters", `${selectedCluster?.icon} ${selectedCluster?.name}`]} />
          </div>
        )}
      </div>
    );
  };

  const triggerDeleteNotification = (item) => {
    openConfirm({
      message: `You're about to delete the Cluster ${item.name}`,
      description: item.endpoint_count > 0 ? "The cluster is running and you will not be allowed to delete the cluster. In order to delete the cluster, you will have to pause or delete all deployments in order to delete the cluster." :
        "You are about to delete the cluster. Once deleted, you won’t be able to recover. Please confirm, if you would like to proceed.",
      okAction: () => {
        deleteCluster(item.id).then((result) => {
          if (result.status == '200') {
            successToast("Cluster deleted request has been sent successfully")
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
      type: 'warining'
    })
  };

  const handleOpenDialogEdit = (cluster: Cluster) => {
    setCluster(cluster);
    openDrawer("edit-cluster");
  }

  return (
    <DashBoardLayout >
      <div className="boardPageView">
        <div className="boardPageTop pt-0 px-0 pb-[0]">
          <div className="px-[1.2rem] pt-[1.05rem] pb-[1.15rem] mb-[2.1rem] border-b-[1px] border-b-[#1F1F1F]">
            <HeaderContent />
          </div>
          <div className="px-[3.5rem]">
            <div className="flex items-center gap-4 justify-between">
              <NameIconDisplay
                icon={selectedCluster?.icon}
                name={selectedCluster?.name}
              />
              <div className="flex items-center gap-2">
                {selectedCluster?.created_at && <Text_12_400_B3B3B3>{formatDate(selectedCluster?.created_at)}</Text_12_400_B3B3B3>}
                {hasPermission(PermissionEnum.ClusterManage) && (
                  <div className="w-[80px]">
                    <div className="flex justify-end items-center">
                      {selectedCluster.status == 'available' && (
                        <Button className="group bg-transparent px-[0.25em] py-0 h-[1.5em] border-none hover:border-transparent"
                        // onClick={() => refreshCluster(item)}
                        >
                          <ReloadIcon className="text-[#B3B3B3] group-hover:text-[#FFFFFF] text-[0.875em] w-[0.875rem] h-[0.875rem]" />
                        </Button>
                      )}
                      {contextHolder}
                      <button className="group bg-transparent px-[0.25em] py-0 h-[1.5rem] border-none hover:border-transparent"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenDialogEdit(selectedCluster)
                        }}
                      >
                        <Pencil1Icon className="text-[#B3B3B3] group-hover:text-[#FFFFFF] text-[0.875em] w-[0.875rem] h-[0.875rem]" />
                      </button>
                      {selectedCluster?.status !== 'deleting' && (<button className="group bg-transparent px-[0.25em] py-0 h-[1.5rem] hover:border-transparent"
                        onClick={(e) => {
                          e.stopPropagation();
                          triggerDeleteNotification(selectedCluster)
                        }}
                      >
                        <TrashIcon className="text-[#B3B3B3] group-hover:text-[#FFFFFF] text-[0.875em] w-[0.875rem] h-[0.875rem]" />
                      </button>)}
                    </div>
                  </div>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2 mt-[1.7rem] flex-wrap mb-[1.75rem]">
              <ClusterTags cluster={selectedCluster} />
            </div>
          </div>
        </div>
        <div className="projectDetailsDiv ">
          <Tabs
            defaultActiveKey="3"
            activeKey={activeTab}
            onChange={(key) => setActiveTab(key)}
            items={[
              {
                label: <div className="flex items-center gap-[0.375rem]">
                  <div className="w-[.975rem] pt-[.15rem]">
                    <Image
                      preview={false}
                      src="/images/icons/home.png"
                      alt="home"
                      style={{
                        width: '.875rem',
                        height: '.875rem'
                      }}
                    />
                  </div>
                  {activeTab === "1" ?
                    <Text_14_600_EEEEEE >
                      General</Text_14_600_EEEEEE>
                    :
                    <Text_14_600_B3B3B3 >General</Text_14_600_B3B3B3>
                  }
                </div>,
                key: '1',
                children: <ClusterGeneral data={selectedCluster} />
              },
              {
                label: <div className="flex items-center gap-[0.375rem]">
                  <div className="w-[.975rem] pt-[.15rem]">
                    <Image
                      preview={false}
                      src="/images/icons/rocket-white.png"
                      alt="home"
                      style={{
                        width: '.875rem',
                        height: '.875rem'
                      }}
                    />
                  </div>
                  {activeTab === "2" ?
                    <Text_14_600_EEEEEE >
                      Deployments</Text_14_600_EEEEEE>
                    :
                    <Text_14_600_B3B3B3
                      className="hover:text-white!"
                    >Deployments</Text_14_600_B3B3B3>
                  }
                </div>,
                key: '2',
                children: <DeploymentListTable />,
              },
              {
                label: <div className="flex items-center gap-[0.375rem]">
                  <div className="w-[.975rem] pt-[.15rem]">
                    <Image
                      preview={false}
                      src="/images/icons/nodes.png"
                      alt="home"
                      style={{
                        width: '.875rem',
                        height: '.875rem'
                      }}
                    />
                  </div>
                  {activeTab === "3" ?
                    <Text_14_600_EEEEEE >
                      Nodes</Text_14_600_EEEEEE>
                    :
                    <Text_14_600_B3B3B3 >Nodes</Text_14_600_B3B3B3>
                  }
                </div>,
                key: '3',
                children: <ClusterNodes data={selectedCluster} />
              },
              // {
              //   label: <div className="flex items-center gap-[0.375rem]">
              //     <div className="w-[.975rem] pt-[.15rem]">
              //       <Image
              //         preview={false}
              //         src="/images/icons/health.png"
              //         alt="home"
              //         style={{
              //           width: '.875rem',
              //           height: '.875rem'
              //         }}
              //       />
              //     </div>
              //     {activeTab === "4" ?
              //       <Text_14_600_EEEEEE >
              //         Health Status</Text_14_600_EEEEEE>
              //       :
              //       <Text_14_600_B3B3B3 >Health Status</Text_14_600_B3B3B3>
              //     }
              //   </div>,
              //   key: '4',
              //   children: <HealthStatus data={selectedCluster} />
              // },
              // {
              //   label: <div className="flex items-center gap-[0.375rem]">
              //     <div className="w-[.975rem] pt-[.15rem]">
              //       <Image
              //         preview={false}
              //         src="/images/icons/dollar.png"
              //         alt="home"
              //         style={{
              //           width: '.875rem',
              //           height: '.875rem'
              //         }}
              //       />
              //     </div>
              //     {activeTab === "4" ?
              //       <Text_14_600_EEEEEE >
              //         Cost Analysis/ TCO</Text_14_600_EEEEEE>
              //       :
              //       <Text_14_600_B3B3B3 >Cost Analysis/ TCO</Text_14_600_B3B3B3>
              //     }
              //   </div>,
              //   key: '5',
              //   children: <CostAnalysis data={selectedCluster} />
              // },
              {
                label: <div className="flex items-center gap-[0.375rem]">
                  <div className="w-[.975rem] pt-[.15rem]">
                    <Image
                      preview={false}
                      src="/images/icons/runBenchmarkIcnWhite.png"
                      alt="home"
                      style={{
                        width: '.875rem',
                        height: '.875rem'
                      }}
                    />
                  </div>
                  {activeTab === "6" ?
                    <Text_14_600_EEEEEE >
                      Analytics</Text_14_600_EEEEEE>
                    :
                    <Text_14_600_B3B3B3 >Analytics</Text_14_600_B3B3B3>
                  }
                </div>,
                key: '6',
                children: <Analytics cluster_id={selectedCluster.id} />
              }
            ]}
          />
        </div>
      </div>
    </DashBoardLayout>
  );
};

export default ClusterDetailsPage;

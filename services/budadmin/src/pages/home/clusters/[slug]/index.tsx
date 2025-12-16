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
import { successToast, errorToast } from "@/components/toast";
import { SelectInput } from "@/components/ui/input";
import { enableDevMode } from "@/components/environment";

const ACCESS_MODE_OPTIONS = [
  {
    label: "ReadWriteOnce",
    value: "ReadWriteOnce",
    description: "Single node read/write access (default for block storage).",
  },
  {
    label: "ReadWriteMany",
    value: "ReadWriteMany",
    description: "Multiple nodes read/write simultaneously (shared/NFS storage).",
  },
  {
    label: "ReadOnlyMany",
    value: "ReadOnlyMany",
    description: "Multiple nodes read-only access.",
  },
  {
    label: "ReadWriteOncePod",
    value: "ReadWriteOncePod",
    description: "Single pod read/write access (Kubernetes v1.22+).",
  },
];

const ClusterDetailsPage = () => {
  const { hasProjectPermission, hasPermission } = useUser();
  const { setOverlayVisible } = useOverlay();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState("1");
  const [isHovered, setIsHovered] = useState(false);
  const [storageClass, setStorageClass] = useState("");
  const [accessMode, setAccessMode] = useState("");
  const [accessModeManuallySet, setAccessModeManuallySet] = useState(false);
  const [storageClassMetadata, setStorageClassMetadata] = useState<Record<string, { recommendedAccessMode?: string; isDefault?: boolean }>>({});
  const [availableStorageClasses, setAvailableStorageClasses] = useState([]);
  const [storageClassesLoading, setStorageClassesLoading] = useState(false);
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [settingsError, setSettingsError] = useState("");
  const [hasExistingSettings, setHasExistingSettings] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const { clustersId } = router.query; // Access the dynamic part of the route
  const { openDrawer } = useDrawer();
  const {
    setSelectedProjectId,
    selectedProject: selectedProjectResult,
    deleteProject,
    setProjectValues,
    projectMembers,
    selectedProjectId,
  } = useProjects();
  const {
    clusters,
    getClusters,
    setCluster,
    selectedCluster,
    loading,
    deleteCluster,
    setClusterValues,
    getClusterById,
    getClusterSettings,
    createClusterSettings,
    updateClusterSettings,
    getClusterStorageClasses,
  } = useCluster();
  const { contextHolder, openConfirm } = useConfirmAction();

  const { endPointsCount } = useEndPoints();
  const [selectedProject, setProject] = useState<Project | null>(null);
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
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
    if (selectedCluster?.id && activeTab === "7") {
      const bootstrapSettings = async () => {
        await loadClusterSettings();
        await loadStorageClasses();
      };
      bootstrapSettings();
    }
  }, [selectedCluster, activeTab]);

  const loadClusterSettings = async () => {
    if (!selectedCluster?.id) return;

    setSettingsLoading(true);
    setSettingsError("");

    try {
      const settings = await getClusterSettings(selectedCluster.id);
      if (settings) {
        setStorageClass(settings.default_storage_class || "");
        setAccessMode(settings.default_access_mode || "");
        setAccessModeManuallySet(Boolean(settings.default_access_mode));
        setHasExistingSettings(true);
      } else {
        // Settings don't exist yet (404) - this is normal for new clusters
        setStorageClass("");
        setAccessMode("");
        setAccessModeManuallySet(false);
        setHasExistingSettings(false);
      }
    } catch (error) {
      // Only show error for non-404 errors (network issues, server errors, etc.)
      console.error('Error loading cluster settings:', error);
      setStorageClass("");
      setHasExistingSettings(false);
      setSettingsError("Failed to load cluster settings");
    } finally {
      setSettingsLoading(false);
    }
  };

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
              urls={[
                "/clusters",
                `/clusters/${selectedCluster.id}`,
                "/clusters/[slug]",
              ]}
              data={[
                "Clusters",
                `${selectedCluster?.icon} ${selectedCluster?.name}`,
              ]}
            />
          </div>
        )}
      </div>
    );
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
            successToast("Cluster deleted request has been sent successfully");
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
      type: "warning",
    });
  };

  const handleOpenDialogEdit = (cluster: Cluster) => {
    setCluster(cluster);
    openDrawer("edit-cluster");
  };

  const loadStorageClasses = async () => {
    if (!selectedCluster?.id) return;

    setStorageClassesLoading(true);

    try {
      // Fetch storage classes from the cluster via API
      const storageClasses = await getClusterStorageClasses(selectedCluster.id);

      // Transform the API response into the format expected by SelectInput
      const formattedStorageClasses = storageClasses.map((sc: any) => ({
        label: sc.default ? `${sc.name} (Default)` : sc.name,
        value: sc.name,
        description: `${sc.provisioner} · Reclaim: ${sc.reclaim_policy} · Recommended: ${sc.recommended_access_mode}`,
      }));

      const metadata = storageClasses.reduce(
        (
          acc: Record<string, { recommendedAccessMode?: string; isDefault?: boolean }>,
          sc: any,
        ) => {
          acc[sc.name] = {
            recommendedAccessMode: sc.recommended_access_mode,
            isDefault: sc.default,
          };
          return acc;
        },
        {},
      );

      setAvailableStorageClasses(formattedStorageClasses);
      setStorageClassMetadata(metadata);

      if (!accessModeManuallySet) {
        const targetClass =
          (storageClass && metadata[storageClass] ? storageClass : undefined) ??
          Object.keys(metadata).find((name) => metadata[name]?.isDefault);

        const recommended = targetClass ? metadata[targetClass]?.recommendedAccessMode : undefined;
        if (recommended) {
          setAccessMode(recommended);
        }
      }
    } catch (error) {
      console.error('Error loading storage classes:', error);
      setAvailableStorageClasses([]);
      setSettingsError("Failed to load storage classes from cluster");
    } finally {
      setStorageClassesLoading(false);
    }
  };

  const handleStorageClassChange = (selectedItem: any) => {
    // Extract the value from the selected item object
    const value = typeof selectedItem === 'string' ? selectedItem : selectedItem?.value || '';
    setStorageClass(value);
    setSettingsError(""); // Clear any previous errors since dropdown values are always valid

    const metadata = storageClassMetadata[value];
    if (metadata?.recommendedAccessMode) {
      setAccessMode(metadata.recommendedAccessMode);
      setAccessModeManuallySet(false);
    }
  };

  const handleAccessModeChange = (selectedItem: any) => {
    const value = typeof selectedItem === 'string' ? selectedItem : selectedItem?.value || '';
    setAccessMode(value);
    setAccessModeManuallySet(Boolean(value));
  };

  const handleSaveSettings = async () => {
    if (!selectedCluster?.id) return;

    setIsSaving(true);
    setSettingsError("");

    try {
      const data = {
        default_storage_class: storageClass || null,
        default_access_mode: accessMode || null,
      };

      if (hasExistingSettings) {
        await updateClusterSettings(selectedCluster.id, data);
        successToast("Cluster settings updated successfully");
      } else {
        await createClusterSettings(selectedCluster.id, data);
        successToast("Cluster settings created successfully");
        setHasExistingSettings(true);
      }
    } catch (error) {
      console.error('Error saving cluster settings:', error);
      errorToast('Failed to save cluster settings');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <DashBoardLayout>
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
                {selectedCluster?.created_at && (
                  <Text_12_400_B3B3B3>
                    {formatDate(selectedCluster?.created_at)}
                  </Text_12_400_B3B3B3>
                )}
                {hasPermission(PermissionEnum.ClusterManage) && (
                  <div className="w-[80px]">
                    <div className="flex justify-end items-center">
                      {/* {selectedCluster.status == "available" && (
                        <Button
                          className="group bg-transparent px-[0.25em] py-0 h-[1.5em] border-none hover:border-transparent"
                          // onClick={() => refreshCluster(item)}
                        >
                          <ReloadIcon className="text-[#B3B3B3] group-hover:text-[#FFFFFF] text-[0.875em] w-[0.875rem] h-[0.875rem]" />
                        </Button>
                      )} */}
                      {contextHolder}
                      <button
                        className="group bg-transparent px-[0.25em] py-0 h-[1.5rem] border-none hover:border-transparent"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenDialogEdit(selectedCluster);
                        }}
                      >
                        <Pencil1Icon className="text-[#B3B3B3] group-hover:text-[#FFFFFF] text-[0.875em] w-[0.875rem] h-[0.875rem]" />
                      </button>
                      {selectedCluster?.status !== "deleting" && (
                        <button
                          className="group bg-transparent px-[0.25em] py-0 h-[1.5rem] hover:border-transparent"
                          onClick={(e) => {
                            e.stopPropagation();
                            triggerDeleteNotification(selectedCluster);
                          }}
                        >
                          <TrashIcon className="text-[#B3B3B3] group-hover:text-[#FFFFFF] text-[0.875em] w-[0.875rem] h-[0.875rem]" />
                        </button>
                      )}
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
                label: (
                  <div className="flex items-center gap-[0.375rem]">
                    <div className="w-[.975rem] pt-[.15rem]">
                      <Image
                        preview={false}
                        src="/images/icons/home.png"
                        alt="home"
                        style={{
                          width: ".875rem",
                          height: ".875rem",
                        }}
                      />
                    </div>
                    {activeTab === "1" ? (
                      <Text_14_600_EEEEEE>General</Text_14_600_EEEEEE>
                    ) : (
                      <Text_14_600_B3B3B3>General</Text_14_600_B3B3B3>
                    )}
                  </div>
                ),
                key: "1",
                children: <ClusterGeneral data={selectedCluster} isActive={activeTab === "1"} />,
              },
              {
                label: (
                  <div className="flex items-center gap-[0.375rem]">
                    <div className="w-[.975rem] pt-[.15rem]">
                      <Image
                        preview={false}
                        src="/images/icons/rocket-white.png"
                        alt="home"
                        style={{
                          width: ".875rem",
                          height: ".875rem",
                        }}
                      />
                    </div>
                    {activeTab === "2" ? (
                      <Text_14_600_EEEEEE>Deployments</Text_14_600_EEEEEE>
                    ) : (
                      <Text_14_600_B3B3B3 className="hover:text-white!">
                        Deployments
                      </Text_14_600_B3B3B3>
                    )}
                  </div>
                ),
                key: "2",
                children: <DeploymentListTable />,
              },
              {
                label: (
                  <div className="flex items-center gap-[0.375rem]">
                    <div className="w-[.975rem] pt-[.15rem]">
                      <Image
                        preview={false}
                        src="/images/icons/nodes.png"
                        alt="home"
                        style={{
                          width: ".875rem",
                          height: ".875rem",
                        }}
                      />
                    </div>
                    {activeTab === "3" ? (
                      <Text_14_600_EEEEEE>Nodes</Text_14_600_EEEEEE>
                    ) : (
                      <Text_14_600_B3B3B3>Nodes</Text_14_600_B3B3B3>
                    )}
                  </div>
                ),
                key: "3",
                children: <ClusterNodes data={selectedCluster} />,
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
              ...(enableDevMode ? [{
                label: (
                  <div className="flex items-center gap-[0.375rem]">
                    <div className="w-[.975rem] pt-[.15rem]">
                      <Image
                        preview={false}
                        src="/images/icons/runBenchmarkIcnWhite.png"
                        alt="home"
                        style={{
                          width: ".875rem",
                          height: ".875rem",
                        }}
                      />
                    </div>
                    {activeTab === "6" ? (
                      <Text_14_600_EEEEEE>Analytics</Text_14_600_EEEEEE>
                    ) : (
                      <Text_14_600_B3B3B3>Analytics</Text_14_600_B3B3B3>
                    )}
                  </div>
                ),
                key: "6",
                children: <Analytics cluster_id={selectedCluster.id} />,
              }] : []),
              ...(hasPermission(PermissionEnum.ClusterManage) ? [{
                label: <div className="flex items-center gap-[0.375rem]">
                  <div className="w-[.975rem] pt-[.15rem]">
                    <Image
                      preview={false}
                      src="/images/icons/settings.png"
                      alt="settings"
                      style={{
                        width: '.875rem',
                        height: '.875rem'
                      }}
                    />
                  </div>
                  {activeTab === "7" ?
                    <Text_14_600_EEEEEE>
                      Settings</Text_14_600_EEEEEE>
                    :
                    <Text_14_600_B3B3B3>Settings</Text_14_600_B3B3B3>
                  }
                </div>,
                key: '7',
                children: <div className="p-6">
                  <div className="bg-[#111113] rounded-lg p-6 border border-[#1F1F1F]">

                    {settingsLoading || storageClassesLoading ? (
                      <div className="flex justify-center align-center py-4">
                        <Text_12_400_B3B3B3>
                          {settingsLoading && storageClassesLoading
                            ? "Loading cluster settings and storage classes..."
                            : settingsLoading
                              ? "Loading cluster settings..."
                              : "Loading storage classes..."}
                        </Text_12_400_B3B3B3>
                      </div>
                    ) : (
                      <div className="space-y-4">
                        <div className="mb-4">
                          <label className="block mb-2">
                            <Text_14_600_EEEEEE>Default Storage Class</Text_14_600_EEEEEE>
                            <Text_12_400_B3B3B3 className="mt-1 mb-3">
                              Select the default storage class for deployments on this cluster. Choose the one marked "(Default)" to use the cluster's system default.
                            </Text_12_400_B3B3B3>
                          </label>
                          <SelectInput
                            value={storageClass}
                            placeholder="Select storage class"
                            selectItems={availableStorageClasses}
                            disabled={isSaving || storageClassesLoading}
                            onValueChange={(value) => handleStorageClassChange(value)}
                            size="2"
                            className="w-full"
                          />
                        </div>

                        <div className="mb-4">
                          <label className="block mb-2">
                            <Text_14_600_EEEEEE>Preferred Access Mode</Text_14_600_EEEEEE>
                            <Text_12_400_B3B3B3 className="mt-1 mb-3">
                              Choose how persistent volumes should be mounted. We pre-fill the value recommended by your storage class.
                            </Text_12_400_B3B3B3>
                          </label>
                          <SelectInput
                            value={accessMode}
                            placeholder="Select access mode"
                            selectItems={ACCESS_MODE_OPTIONS}
                            disabled={isSaving}
                            onValueChange={(value) => handleAccessModeChange(value)}
                            size="2"
                            className="w-full"
                          />
                          {settingsError && (
                            <Text_12_400_B3B3B3 className="text-red-500 mt-1">{settingsError}</Text_12_400_B3B3B3>
                          )}
                        </div>

                        <div className="flex gap-3 justify-end">
                          <Button
                            type="primary"
                            onClick={handleSaveSettings}
                            disabled={isSaving || storageClassesLoading}
                            className="bg-[#007AFF] hover:bg-[#0056CC] border-none"
                            loading={isSaving}
                          >
                            {isSaving
                              ? 'Saving...'
                              : hasExistingSettings ? 'Update Settings' : 'Save Settings'}
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              }] : [])
            ]}
          />
        </div>
      </div>
    </DashBoardLayout>
  );
};

export default ClusterDetailsPage;

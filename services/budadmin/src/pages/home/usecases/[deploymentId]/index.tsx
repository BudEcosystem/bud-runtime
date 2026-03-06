"use client";
import { useRouter } from "next/router";
import React, { useEffect, useRef, useState } from "react";
import { Flex, Tabs, Tag } from "antd";
import { ExternalLink, Monitor, Square, Trash2 } from "lucide-react";
import DashBoardLayout from "../../layout";
import {
  Text_14_600_FFFFFF,
  Text_26_600_FFFFFF,
} from "@/components/ui/text";
import { CustomBreadcrumb } from "@/components/ui/bud/card/DrawerBreadCrumbNavigation";
import BackButton from "@/components/ui/bud/drawer/BackButton";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import { useConfirmAction } from "src/hooks/useConfirmAction";
import { useLoader } from "src/context/appContext";
import {
  BudUseCasesAPI,
  Deployment,
} from "@/lib/budusecases";
import { errorToast, successToast } from "@/components/toast";
import { deploymentStatusColors } from "@/components/usecases/DeploymentCard";
import { useUseCases } from "src/stores/useUseCases";
import GeneralTab from "./Overview";
import Components from "./Components";
import Access from "./Access";

const ACTIVE_STATUSES = ["pending", "provisioning", "deploying"];

const capitalize = (str: string) =>
  str ? str.charAt(0).toUpperCase() + str.slice(1).toLowerCase() : "";

const UseCaseDetailPage = () => {
  const router = useRouter();
  const { deploymentId } = router.query;
  const projectId = (router.query.projectId as string) || undefined;

  const [deployment, setDeployment] = useState<Deployment | null>(null);
  const [activeTab, setActiveTab] = useState("1");
  const [isMounted, setIsMounted] = useState(false);

  const { showLoader, hideLoader } = useLoader();
  const { contextHolder, openConfirm } = useConfirmAction();
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    setIsMounted(true);
    return () => stopPolling();
  }, []);

  const stopPolling = () => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  };

  const fetchDeployment = async (showGlobalLoader = false) => {
    if (!deploymentId) return;
    if (showGlobalLoader) showLoader();
    try {
      const data = await BudUseCasesAPI.deployments.get(deploymentId as string);
      setDeployment(data);

      // Auto-stop polling on terminal states
      const status = data.status?.toLowerCase();
      if (status && !ACTIVE_STATUSES.includes(status)) {
        stopPolling();
      }
    } catch (error: any) {
      const message =
        error.response?.data?.detail || "Failed to fetch deployment";
      errorToast(message);
    } finally {
      if (showGlobalLoader) hideLoader();
    }
  };

  // Initial load
  useEffect(() => {
    if (deploymentId) {
      fetchDeployment(true);
    }
  }, [deploymentId]);

  // Start polling for active statuses
  useEffect(() => {
    if (!deployment) return;
    const status = deployment.status?.toLowerCase();
    if (status && ACTIVE_STATUSES.includes(status) && !pollingRef.current) {
      pollingRef.current = setInterval(() => fetchDeployment(false), 5000);
    }
  }, [deployment?.status]);

  const goBack = () => {
    router.back();
  };

  const { openAppOverlay } = useUseCases();

  const handleOpenUI = () => {
    if (!deployment) return;
    openAppOverlay(deployment);
  };

  const handleStop = async () => {
    if (!deployment) return;
    try {
      await BudUseCasesAPI.deployments.stop(deployment.id);
      successToast("Deployment stopped");
      await fetchDeployment(false);
    } catch (error: any) {
      const message =
        error.response?.data?.detail || "Failed to stop deployment";
      errorToast(message);
    }
  };

  const handleDelete = () => {
    if (!deployment) return;
    openConfirm({
      message: `You're about to delete the ${deployment.name} deployment`,
      description:
        "Once you delete the deployment, it will not be recovered. Are you sure?",
      cancelAction: () => {},
      cancelText: "Cancel",
      loading: false,
      key: "delete-usecase-deployment",
      okAction: async () => {
        try {
          await BudUseCasesAPI.deployments.delete(deployment.id);
          successToast("Deployment deleted successfully");
          if (projectId) {
            router.push(`/projects/${projectId}`);
          } else {
            router.push("/projects");
          }
        } catch (error: any) {
          const message =
            error.response?.data?.detail || "Failed to delete deployment";
          errorToast(message);
        }
      },
      okText: "Delete",
      type: "warning",
    });
  };

  const status = deployment?.status?.toLowerCase() || "";
  const statusColor = deploymentStatusColors[status] || "#8c8c8c";
  const isRunning = status === "running" || status === "completed";
  const uiEnabled = deployment?.access_config?.ui?.enabled === true;

  const tabItems = [
    {
      label: (
        <div className="flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" width=".875rem" height=".875rem" viewBox="0 0 24 24" fill="none">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" fill={activeTab === "1" ? "#EEEEEE" : "#B3B3B3"} />
          </svg>
          <Text_14_600_FFFFFF style={{ color: activeTab === "1" ? "#EEEEEE" : "#B3B3B3" }}>
            General
          </Text_14_600_FFFFFF>
        </div>
      ),
      key: "1",
      children: deployment ? <GeneralTab deployment={deployment} /> : null,
    },
    {
      label: (
        <div className="flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" width=".875rem" height=".875rem" viewBox="0 0 24 24" fill="none">
            <path d="M4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6zm16-4H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-1 9h-4v4h-2v-4H9V9h4V5h2v4h4v2z" fill={activeTab === "2" ? "#EEEEEE" : "#B3B3B3"} />
          </svg>
          <Text_14_600_FFFFFF style={{ color: activeTab === "2" ? "#EEEEEE" : "#B3B3B3" }}>
            Components
          </Text_14_600_FFFFFF>
        </div>
      ),
      key: "2",
      children: deployment ? <Components deployment={deployment} /> : null,
    },
    {
      label: (
        <div className="flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" width=".875rem" height=".875rem" viewBox="0 0 24 24" fill="none">
            <path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z" fill={activeTab === "3" ? "#EEEEEE" : "#B3B3B3"} />
          </svg>
          <Text_14_600_FFFFFF style={{ color: activeTab === "3" ? "#EEEEEE" : "#B3B3B3" }}>
            Access & Settings
          </Text_14_600_FFFFFF>
        </div>
      ),
      key: "3",
      children: deployment ? <Access deployment={deployment} /> : null,
    },
  ];

  return (
    <DashBoardLayout>
      <div className="boardPageView">
        {contextHolder}
        <div className="boardPageTop pt-0 !mb-[.4rem] px-[0]">
          <div className="px-[1.2rem] pt-[1.05rem] pb-[1.15rem] mb-[2.1rem] border-b-[1px] border-b-[#1F1F1F]">
            {isMounted && (
              <Flex align="center" justify="start">
                <BackButton onClick={goBack} />
                <CustomBreadcrumb
                  data={["Use Cases", deployment?.name || "..."]}
                  urls={[
                    projectId ? `/projects/${projectId}` : "/projects",
                    "",
                  ]}
                />
              </Flex>
            )}
          </div>
          <div className="flex items-center gap-4 justify-between flex-row px-[3.5rem]">
            <div className="w-full">
              <div className="flex items-center gap-3">
                <Text_26_600_FFFFFF className="text-[#EEE]">
                  {deployment?.name || "Loading..."}
                </Text_26_600_FFFFFF>
              </div>
              <div className="flex items-center gap-2 mt-[1rem]">
                {deployment?.status && (
                  <Tag
                    className="border-[0] rounded-[6px] flex justify-center items-center py-[.3rem] px-[.4rem] capitalize"
                    style={{
                      backgroundColor: `${statusColor}20`,
                      color: statusColor,
                    }}
                  >
                    <div className="text-[0.625rem] font-[400] leading-[100%]">
                      {capitalize(deployment.status)}
                    </div>
                  </Tag>
                )}
                {deployment?.template_name && (
                  <Tag
                    className="text-[#B3B3B3] border-[0] rounded-[6px] flex justify-center items-center py-[.3rem] px-[.4rem]"
                    style={{ backgroundColor: "#1F1F1F" }}
                  >
                    <div className="text-[0.625rem] font-[400] leading-[100%]">
                      {deployment.template_name}
                    </div>
                  </Tag>
                )}
                {deployment?.components && deployment.components.length > 0 && (
                  <Tag
                    className="text-[#B3B3B3] border-[0] rounded-[6px] flex justify-center items-center py-[.3rem] px-[.4rem]"
                    style={{ backgroundColor: "#1F1F1F" }}
                  >
                    <div className="text-[0.625rem] font-[400] leading-[100%]">
                      {deployment.components.length} Component
                      {deployment.components.length !== 1 ? "s" : ""}
                    </div>
                  </Tag>
                )}
              </div>
            </div>
            <div className="flex-row flex gap-2">
              {isRunning && uiEnabled && (
                <PrimaryButton
                  onClick={handleOpenUI}
                  className="min-w-[7rem]"
                  style={{ background: "#8B5CF6", borderColor: "#8B5CF6" }}
                >
                  <div className="flex items-center gap-[.3rem]">
                    <Monitor className="w-[.875rem] h-[.875rem]" />
                    Open UI
                    <ExternalLink className="w-[.75rem] h-[.75rem]" />
                  </div>
                </PrimaryButton>
              )}
              {isRunning && (
                <PrimaryButton
                  onClick={handleStop}
                  className="min-w-[5.5rem]"
                  style={{ background: "#6B7280", borderColor: "#6B7280" }}
                >
                  <div className="flex items-center gap-[.3rem]">
                    <Square className="w-[.75rem] h-[.75rem]" />
                    Stop
                  </div>
                </PrimaryButton>
              )}
              <PrimaryButton
                onClick={handleDelete}
                className="min-w-[5.5rem]"
                style={{ background: "#EF444420", borderColor: "#EF4444", color: "#EF4444" }}
              >
                <div className="flex items-center gap-[.3rem]">
                  <Trash2 className="w-[.75rem] h-[.75rem]" />
                  Delete
                </div>
              </PrimaryButton>
            </div>
          </div>
        </div>
        <div className="projectDetailsDiv pb-3">
          <Tabs
            className="deploymentDetailsTable"
            defaultActiveKey="1"
            activeKey={activeTab}
            onChange={(key) => setActiveTab(key)}
            items={tabItems}
          />
        </div>
      </div>
    </DashBoardLayout>
  );
};

export default UseCaseDetailPage;

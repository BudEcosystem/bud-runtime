"use client";
import { Box, Flex } from "@radix-ui/themes";
import { useEffect, useState } from "react";
import React from "react";
import DashBoardLayout from "../layout";
import {
  Text_11_400_808080,
  Text_12_400_6A6E76,
  Text_13_400_B3B3B3,
  Text_17_600_FFFFFF,
} from "@/components/ui/text";
import router from "next/router";
import PageHeader from "@/components/ui/pageHeader";
import { useLoader } from "src/context/appContext";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import NoDataFount from "@/components/ui/noDataFount";
import { PlusOutlined, ClockCircleOutlined, MoreOutlined } from "@ant-design/icons";
import { useBudPipeline, BudPipelineItem } from "src/stores/useBudPipeline";
import { Tag, Tooltip, Dropdown, ConfigProvider } from "antd";
import { formatDistanceToNow } from "date-fns";
import { useDrawer } from "src/hooks/useDrawer";
import { useConfirmAction } from "src/hooks/useConfirmAction";
import { successToast, errorToast } from "@/components/toast";

// Status badge colors
const statusColors: Record<string, string> = {
  active: "#52c41a",
  inactive: "#8c8c8c",
  draft: "#faad14",
};

const WorkflowCard = ({
  workflow,
  onClick,
  onEdit,
  onDelete,
}: {
  workflow: BudPipelineItem;
  onClick: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) => {

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onClick();
    }
  };

  return (
    <div
      className="flex flex-col justify-between w-full bg-[#101010] border border-[#1F1F1F] rounded-lg pt-[1.54em] min-h-[325px] cursor-pointer hover:shadow-[1px_1px_6px_-1px_#2e3036] hover:border-[#965CDE] transition-all duration-200 overflow-hidden focus:outline-none focus:ring-2 focus:ring-[#965CDE] focus:ring-offset-2 focus:ring-offset-[#000000]"
      onClick={onClick}
      onKeyDown={handleKeyDown}
      role="button"
      tabIndex={0}
      aria-label={`Open pipeline: ${workflow.name}. ${workflow.step_count} steps. Status: ${workflow.status}`}
    >
      <div className="px-[1.6rem] pb-[1.54em]">
        {/* Header with icon */}
        <div className="pr-0 flex justify-between items-start gap-3">
          <div className="w-[2.40125rem] h-[2.40125rem] bg-[#1F1F1F] rounded-[5px] flex items-center justify-center text-xl">
            🔄
          </div>
          <ConfigProvider
            theme={{
              token: {
                colorBgElevated: "#111113",
                colorText: "#EEEEEE",
                controlItemBgHover: "#1F1F1F",
                boxShadowSecondary: "0 0 0 1px #1F1F1F",
              },
            }}
          >
            <Dropdown
              menu={{
                items: [
                  {
                    key: "edit",
                    label: "Edit",
                    onClick: (e) => {
                      e.domEvent.stopPropagation();
                      onEdit();
                    },
                  },
                  {
                    key: "delete",
                    label: "Delete",
                    danger: true,
                    onClick: (e) => {
                      e.domEvent.stopPropagation();
                      onDelete();
                    },
                  },
                ],
              }}
              trigger={["hover"]}
              placement="bottomRight"
            >
              <div
                className="w-[1.5rem] h-[1.5rem] flex items-center justify-center rounded hover:bg-[#1F1F1F] transition-colors cursor-pointer"
                onClick={(e) => e.stopPropagation()}
              >
                <MoreOutlined className="text-[#B3B3B3] text-[1.2rem]" rotate={180} />
              </div>
            </Dropdown>
          </ConfigProvider>
        </div>

        {/* Date */}
        <div className="mt-[1.3rem]">
          <Text_11_400_808080>
            {workflow.created_at ? formatDistanceToNow(new Date(workflow.created_at), { addSuffix: true }) : "Recently created"}
          </Text_11_400_808080>
        </div>

        {/* Name */}
        <div className="mt-[.75rem]">
          <Text_17_600_FFFFFF className="max-w-[100] truncate w-[calc(100%-20px)] leading-[0.964375rem]">
            {workflow.name}
          </Text_17_600_FFFFFF>
        </div>

        {/* Description */}
        <Text_13_400_B3B3B3 className="mt-2 line-clamp-2 text-[12px]">
          {workflow.dag?.description || "No description provided"}
        </Text_13_400_B3B3B3>

        {/* Step count and status */}
        <Flex gap="2" wrap="wrap" className="mt-4" align="center">
          {workflow.step_count > 0 && (
            <Tag
              className="text-[#B3B3B3] border-[0] rounded-[6px] flex justify-center items-center py-[.3rem] px-[.4rem]"
              style={{ backgroundColor: "#8F55D62B" }}
            >
              <div className="text-[0.625rem] font-[400] leading-[100%]" style={{ color: "#965CDE" }}>
                {workflow.step_count} Steps
              </div>
            </Tag>
          )}
          <Tag
            className="border-[0] rounded-[6px] flex justify-center items-center py-[.3rem] px-[.4rem] capitalize"
            style={{
              backgroundColor: workflow.status === "active" ? "#52c41a20" : workflow.status === "draft" ? "#faad1420" : "#8c8c8c20",
              color: statusColors[workflow.status],
            }}
          >
            <div className="text-[0.625rem] font-[400] leading-[100%]">
              {workflow.status}
            </div>
          </Tag>
        </Flex>
      </div>

      {/* Footer */}
      <div className="px-[1.6rem] bg-[#161616] pt-[1.4rem] pb-[1.5rem] border-t-[.5px] border-t-[#1F1F1F]">
        <Text_12_400_6A6E76 className="mb-[.7rem]">Execution Stats</Text_12_400_6A6E76>
        <Flex gap="2" align="center">
          <Tag
            className="text-[#B3B3B3] border-[0] rounded-[6px] flex justify-center items-center py-[.3rem] px-[.4rem]"
            style={{ backgroundColor: "#1F1F1F" }}
          >
            <div className="text-[0.625rem] font-[400] leading-[100%]">
              {workflow.execution_count || 0} Runs
            </div>
          </Tag>
          {workflow.last_execution_at && (
            <Tooltip title={`Last run: ${new Date(workflow.last_execution_at).toLocaleString()}`}>
              <Tag
                className="text-[#6A6E76] border-[0] rounded-[6px] flex justify-center items-center py-[.3rem] px-[.4rem]"
                style={{ backgroundColor: "#1F1F1F" }}
              >
                <ClockCircleOutlined className="text-[10px] mr-1" />
                <div className="text-[0.625rem] font-[400] leading-[100%]">
                  {formatDistanceToNow(new Date(workflow.last_execution_at), { addSuffix: true })}
                </div>
              </Tag>
            </Tooltip>
          )}
        </Flex>
      </div>
    </div>
  );
};

const BudPipelines = () => {
  const [isMounted, setIsMounted] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [confirmLoading, setConfirmLoading] = useState(false);
  const { showLoader, hideLoader } = useLoader();
  const { workflows, getWorkflows, deleteWorkflow, isLoading } = useBudPipeline();
  const { openDrawerWithStep, openDrawer } = useDrawer();
  const { contextHolder, openConfirm } = useConfirmAction();

  const filteredWorkflows = React.useMemo(() => {
    // Filter out any undefined/null items first
    const validWorkflows = workflows?.filter((w): w is BudPipelineItem => w != null && w.id != null) || [];
    if (!searchTerm) return validWorkflows;
    const term = searchTerm.toLowerCase();
    return validWorkflows.filter(
      (w) =>
        w.name?.toLowerCase().includes(term) ||
        w.dag?.description?.toLowerCase().includes(term) ||
        w.dag?.steps?.some((s) => s.action?.toLowerCase().includes(term))
    );
  }, [workflows, searchTerm]);

  const goToDetails = (workflow: BudPipelineItem) => {
    router.push(`/pipelines/${workflow.id}`);
  };

  const handleEditClick = (workflow: BudPipelineItem) => {
    // Open the edit drawer with the pipeline data
    openDrawer("edit-pipeline", { pipeline: workflow });
  };

  const handleDeleteClick = (workflow: BudPipelineItem) => {
    openConfirm({
      message: `You're about to delete the ${workflow.name} pipeline`,
      description: "Once you delete the pipeline, it cannot be recovered. All associated schedules, webhooks, and event triggers will also be deleted. Are you sure?",
      cancelAction: () => {},
      cancelText: "Cancel",
      loading: confirmLoading,
      key: "delete-pipeline",
      okAction: async () => {
        setConfirmLoading(true);
        const success = await deleteWorkflow(workflow.id);
        if (success) {
          successToast("Pipeline deleted successfully");
          getWorkflows();
        } else {
          errorToast("Failed to delete pipeline");
        }
        setConfirmLoading(false);
      },
      okText: "Delete",
      type: "warning",
    });
  };

  useEffect(() => {
    if (isMounted) {
      showLoader();
      getWorkflows().finally(() => hideLoader());
    }
  }, [isMounted]);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  return (
    <DashBoardLayout>
      <Box className="boardPageView">
        <Box className="boardPageTop">
          <PageHeader
            headding="Pipelines"
            ButtonIcon={PlusOutlined}
            buttonLabel="Pipeline"
            buttonPermission={true}
            buttonAction={() => {
              openDrawerWithStep("new-pipeline");
            }}
            rightComponent={
              <SearchHeaderInput
                placeholder="Search pipelines..."
                searchValue={searchTerm}
                setSearchValue={setSearchTerm}
                classNames="mr-[.6rem]"
              />
            }
          />
        </Box>

        <Box className="boardMainContainer listingContainer" id="pipeline-list">
          {/* Empty state */}
          {!filteredWorkflows?.length && !searchTerm && !isLoading && (
            <NoDataFount
              classNames="h-[50vh]"
              textMessage="No pipelines created yet. Create your first DAG pipeline to automate tasks."
            />
          )}

          {/* Search empty state */}
          {searchTerm && !filteredWorkflows?.length && (
            <NoDataFount
              classNames="h-[50vh]"
              textMessage={`No pipelines found for "${searchTerm}"`}
            />
          )}

          {/* Workflow grid */}
          <div className="grid gap-[1.1rem] grid-cols-1 md:grid-cols-2 lg:grid-cols-3 mt-[2.95rem] pb-6">
            {filteredWorkflows?.map((workflow) => (
              <WorkflowCard
                key={workflow.id}
                workflow={workflow}
                onClick={() => goToDetails(workflow)}
                onEdit={() => handleEditClick(workflow)}
                onDelete={() => handleDeleteClick(workflow)}
              />
            ))}
          </div>
        </Box>
      </Box>

      {/* Confirmation dialog context */}
      {contextHolder}
    </DashBoardLayout>
  );
};

export default BudPipelines;

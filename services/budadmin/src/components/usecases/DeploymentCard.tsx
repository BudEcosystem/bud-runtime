import React from "react";
import { Flex } from "@radix-ui/themes";
import {
  Text_11_400_808080,
  Text_12_400_6A6E76,
  Text_17_600_FFFFFF,
  Text_13_400_B3B3B3,
} from "@/components/ui/text";
import { MoreOutlined } from "@ant-design/icons";
import { Tag, Tooltip, Dropdown, ConfigProvider } from "antd";
import { formatDistanceToNow } from "date-fns";
import { Deployment, ComponentType } from "@/lib/budusecases";

// Component type badge colors
export const componentTypeColors: Record<ComponentType, string> = {
  model: "#8B5CF6",
  llm: "#8B5CF6",
  embedder: "#F59E0B",
  reranker: "#EF4444",
  vector_db: "#10B981",
  memory_store: "#3B82F6",
  helm: "#06B6D4",
};

// Deployment status badge colors
export const deploymentStatusColors: Record<string, string> = {
  pending: "#faad14",
  deploying: "#1890ff",
  running: "#52c41a",
  completed: "#52c41a",
  failed: "#ff4d4f",
  stopped: "#8c8c8c",
};

export const DeploymentCard = ({
  deployment,
  onClick,
  onDelete,
  onOpenApp,
}: {
  deployment: Deployment;
  onClick: () => void;
  onDelete: () => void;
  onOpenApp?: () => void;
}) => {
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onClick();
    }
  };

  const statusColor = deploymentStatusColors[deployment.status?.toLowerCase()] || "#8c8c8c";

  return (
    <div
      className="flex flex-col justify-between w-full bg-[#101010] border border-[#1F1F1F] rounded-lg pt-[1.54em] min-h-[325px] cursor-pointer hover:shadow-[1px_1px_6px_-1px_#2e3036] hover:border-[#965CDE] transition-all duration-200 overflow-hidden focus:outline-none focus:ring-2 focus:ring-[#965CDE] focus:ring-offset-2 focus:ring-offset-[#000000]"
      onClick={onClick}
      onKeyDown={handleKeyDown}
      role="button"
      tabIndex={0}
      aria-label={`View deployment: ${deployment.name}. Status: ${deployment.status}`}
    >
      <div className="px-[1.6rem] pb-[1.54em]">
        {/* Header with icon and actions */}
        <div className="pr-0 flex justify-between items-start gap-3">
          <div className="w-[2.40125rem] h-[2.40125rem] bg-[#1F1F1F] rounded-[5px] flex items-center justify-center text-xl">
            📦
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
                  ...(deployment.status?.toLowerCase() === "running" &&
                  deployment.access_config?.ui?.enabled &&
                  onOpenApp
                    ? [
                        {
                          key: "open-app",
                          label: "Open App",
                          onClick: (e: any) => {
                            e.domEvent.stopPropagation();
                            onOpenApp();
                          },
                        },
                      ]
                    : []),
                  {
                    key: "delete",
                    label: "Delete",
                    danger: true,
                    onClick: (e: any) => {
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
            {deployment.created_at
              ? formatDistanceToNow(new Date(deployment.created_at), { addSuffix: true })
              : "Recently created"}
          </Text_11_400_808080>
        </div>

        {/* Name */}
        <div className="mt-[.75rem]">
          <Text_17_600_FFFFFF className="max-w-[100] truncate w-[calc(100%-20px)] leading-[0.964375rem]">
            {deployment.name}
          </Text_17_600_FFFFFF>
        </div>

        {/* Template name */}
        <Text_13_400_B3B3B3 className="mt-2 line-clamp-1 text-[12px]">
          Template: {deployment.template_name || "Unknown"}
        </Text_13_400_B3B3B3>

        {/* Status and component count */}
        <Flex gap="2" wrap="wrap" className="mt-4" align="center">
          <Tag
            className="border-[0] rounded-[6px] flex justify-center items-center py-[.3rem] px-[.4rem] capitalize"
            style={{ backgroundColor: `${statusColor}20`, color: statusColor }}
          >
            <div className="text-[0.625rem] font-[400] leading-[100%]">
              {deployment.status}
            </div>
          </Tag>
          {deployment.components?.length > 0 && (
            <Tag
              className="text-[#B3B3B3] border-[0] rounded-[6px] flex justify-center items-center py-[.3rem] px-[.4rem]"
              style={{ backgroundColor: "#1F1F1F" }}
            >
              <div className="text-[0.625rem] font-[400] leading-[100%]">
                {deployment.components.length} Component{deployment.components.length !== 1 ? "s" : ""}
              </div>
            </Tag>
          )}
        </Flex>

        {/* Access mode badges - shown when deployment is running */}
        {deployment.status?.toLowerCase() === "running" && deployment.access_config && (
          <Flex gap="2" wrap="wrap" className="mt-2" align="center">
            {deployment.access_config.ui?.enabled && (
              <Tooltip title="Web UI access available">
                <Tag
                  className="border-[0] rounded-[6px] flex justify-center items-center py-[.3rem] px-[.4rem]"
                  style={{ backgroundColor: "#3B82F620", color: "#3B82F6" }}
                >
                  <div className="text-[0.625rem] font-[400] leading-[100%]">
                    UI
                  </div>
                </Tag>
              </Tooltip>
            )}
            {deployment.access_config.api?.enabled && (
              <Tooltip title="API access available">
                <Tag
                  className="border-[0] rounded-[6px] flex justify-center items-center py-[.3rem] px-[.4rem]"
                  style={{ backgroundColor: "#10B98120", color: "#10B981" }}
                >
                  <div className="text-[0.625rem] font-[400] leading-[100%]">
                    API
                  </div>
                </Tag>
              </Tooltip>
            )}
          </Flex>
        )}
      </div>

      {/* Footer - timestamps */}
      <div className="px-[1.6rem] bg-[#161616] pt-[1.4rem] pb-[1.5rem] border-t-[.5px] border-t-[#1F1F1F]">
        <Text_12_400_6A6E76 className="mb-[.7rem]">Timestamps</Text_12_400_6A6E76>
        <Flex gap="2" wrap="wrap" align="center">
          {deployment.started_at && (
            <Tooltip title={`Started: ${new Date(deployment.started_at).toLocaleString()}`}>
              <Tag
                className="text-[#6A6E76] border-[0] rounded-[6px] flex justify-center items-center py-[.3rem] px-[.4rem]"
                style={{ backgroundColor: "#1F1F1F" }}
              >
                <div className="text-[0.625rem] font-[400] leading-[100%]">
                  Started {formatDistanceToNow(new Date(deployment.started_at), { addSuffix: true })}
                </div>
              </Tag>
            </Tooltip>
          )}
          {deployment.completed_at && (
            <Tooltip title={`Completed: ${new Date(deployment.completed_at).toLocaleString()}`}>
              <Tag
                className="text-[#6A6E76] border-[0] rounded-[6px] flex justify-center items-center py-[.3rem] px-[.4rem]"
                style={{ backgroundColor: "#1F1F1F" }}
              >
                <div className="text-[0.625rem] font-[400] leading-[100%]">
                  Completed {formatDistanceToNow(new Date(deployment.completed_at), { addSuffix: true })}
                </div>
              </Tag>
            </Tooltip>
          )}
          {!deployment.started_at && !deployment.completed_at && (
            <Tag
              className="text-[#6A6E76] border-[0] rounded-[6px] flex justify-center items-center py-[.3rem] px-[.4rem]"
              style={{ backgroundColor: "#1F1F1F" }}
            >
              <div className="text-[0.625rem] font-[400] leading-[100%]">
                Not started
              </div>
            </Tag>
          )}
        </Flex>
      </div>
    </div>
  );
};

export default DeploymentCard;

import React from "react";
import { Table, Tag, Tooltip } from "antd";
import { Copy } from "lucide-react";
import { Deployment, ComponentDeployment, ComponentType } from "@/lib/budusecases";
import { Text_12_400_EEEEEE } from "@/components/ui/text";
import { formatDate } from "src/utils/formatDate";
import { SortIcon } from "@/components/ui/bud/table/SortIcon";
import { copyToClipboard } from "@/utils/clipboard";
import { successToast } from "@/components/toast";
import type { ColumnsType } from "antd/es/table";

const componentTypeColors: Record<ComponentType, string> = {
  model: "#8B5CF6",
  llm: "#8B5CF6",
  embedder: "#F59E0B",
  reranker: "#EF4444",
  vector_db: "#10B981",
  memory_store: "#3B82F6",
  helm: "#06B6D4",
};

const componentStatusColors: Record<string, string> = {
  pending: "#faad14",
  deploying: "#1890ff",
  running: "#52c41a",
  completed: "#52c41a",
  failed: "#ff4d4f",
  stopped: "#8c8c8c",
};

const capitalize = (str: string): string =>
  str ? str.charAt(0).toUpperCase() + str.slice(1).toLowerCase() : "";

const humanizeType = (type: string): string =>
  capitalize(type.replace(/_/g, " "));

interface ComponentsProps {
  deployment?: Deployment;
}

const Components: React.FC<ComponentsProps> = ({ deployment }) => {
  if (!deployment) return null;
  const columns: ColumnsType<ComponentDeployment> = [
    {
      title: "Component Name",
      dataIndex: "component_name",
      key: "component_name",
      sortIcon: SortIcon,
      render: (text: string) => <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>,
    },
    {
      title: "Type",
      dataIndex: "component_type",
      key: "component_type",
      sortIcon: SortIcon,
      render: (type: ComponentType) => {
        const color = componentTypeColors[type] || "#8c8c8c";
        return (
          <Tag
            className="border-0 rounded-[6px]"
            style={{ backgroundColor: `${color}20`, color }}
          >
            {humanizeType(type)}
          </Tag>
        );
      },
    },
    {
      title: "Selected Component",
      dataIndex: "selected_component",
      key: "selected_component",
      sortIcon: SortIcon,
      render: (text: string | null) => (
        <Text_12_400_EEEEEE>{text ?? "—"}</Text_12_400_EEEEEE>
      ),
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      sortIcon: SortIcon,
      render: (status: string) => {
        const key = status?.toLowerCase() ?? "";
        const color = componentStatusColors[key] || "#8c8c8c";
        return (
          <Tag
            className="border-0 rounded-[6px]"
            style={{ backgroundColor: `${color}20`, color }}
          >
            {capitalize(key)}
          </Tag>
        );
      },
    },
    {
      title: "Endpoint URL",
      dataIndex: "endpoint_url",
      key: "endpoint_url",
      render: (url: string | null) => {
        if (!url) return <Text_12_400_EEEEEE>—</Text_12_400_EEEEEE>;
        return (
          <div className="flex items-center gap-2 min-w-0">
            <Tooltip title={url}>
              <span
                className="font-mono text-[0.75rem] text-[#EEEEEE] truncate max-w-[220px] block"
              >
                {url}
              </span>
            </Tooltip>
            <button
              className="flex-shrink-0 text-[#808080] hover:text-[#EEEEEE] transition-colors"
              onClick={(e) => {
                e.stopPropagation();
                copyToClipboard(url, {
                  onSuccess: () => successToast("Copied to clipboard"),
                });
              }}
              title="Copy URL"
            >
              <Copy size={12} />
            </button>
          </div>
        );
      },
    },
    {
      title: "Error",
      dataIndex: "error_message",
      key: "error_message",
      render: (msg: string | null) =>
        msg ? (
          <Tooltip title={msg}>
            <span className="text-[0.75rem] text-[#ff4d4f] truncate max-w-[200px] block">
              {msg}
            </span>
          </Tooltip>
        ) : (
          <Text_12_400_EEEEEE>—</Text_12_400_EEEEEE>
        ),
    },
    {
      title: "Updated",
      dataIndex: "updated_at",
      key: "updated_at",
      sortIcon: SortIcon,
      render: (text: string) => (
        <Text_12_400_EEEEEE>{formatDate(text)}</Text_12_400_EEEEEE>
      ),
    },
  ];

  return (
    <div className="pb-[60px] pt-[.4rem]">
      <Table<ComponentDeployment>
        columns={columns}
        dataSource={deployment.components}
        rowKey="id"
        pagination={false}
        bordered={false}
        footer={null}
      />
    </div>
  );
};

export default Components;

import React, { useEffect, useState, useCallback } from "react";
import { Button, Table } from "antd";
import { RocketOutlined } from "@ant-design/icons";
import ProjectTags from "src/flows/components/ProjectTags";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import NoDataFount from "@/components/ui/noDataFount";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import { Text_12_400_EEEEEE, Text_16_600_FFFFFF } from "@/components/ui/text";
import { BudUseCasesAPI, Deployment } from "@/lib/budusecases";
import { useDrawer } from "src/hooks/useDrawer";
import { useUseCases } from "src/stores/useUseCases";
import { errorToast, successToast } from "@/components/toast";
import { formatDate } from "src/utils/formatDate";
import { ExternalLink } from "lucide-react";
import { SortIcon } from "@/components/ui/bud/table/SortIcon";
import { useConfirmAction } from "src/hooks/useConfirmAction";
import { useLoaderOnLoding } from "src/hooks/useLoaderOnLoading";

const capitalize = (str: string) =>
  str ? str.charAt(0).toUpperCase() + str.slice(1).toLowerCase() : "";

// Status color mapping for use case deployments
const usecaseStatusMapping: Record<string, string> = {
  Pending: "#D1B854",
  Deploying: "#965CDE",
  Running: "#479D5F",
  Completed: "#479D5F",
  Failed: "#EC7575",
  Stopped: "#DE5CD1",
  Cancelled: "#ECAE75",
};

interface UseCaseDeploymentsProps {
  projectId?: string;
}

const UseCaseDeployments: React.FC<UseCaseDeploymentsProps> = ({ projectId }) => {
  const [isMounted, setIsMounted] = useState(false);
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [order, setOrder] = useState<"-" | "">("");
  const [orderBy, setOrderBy] = useState<string>("created_at");
  const { openDrawer } = useDrawer();
  const { selectDeployment, resetWizard, openAppOverlay } = useUseCases();
  const { contextHolder, openConfirm } = useConfirmAction();
  useLoaderOnLoding(loading);

  const fetchDeployments = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const response = await BudUseCasesAPI.deployments.list({
        project_id: projectId,
        page_size: 100,
      });
      setDeployments(response.items || []);
    } catch (error: any) {
      const message = error.response?.data?.detail || "Failed to fetch use case deployments";
      errorToast(message);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchDeployments();
  }, [fetchDeployments]);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  // Client-side search filtering
  const filteredDeployments = React.useMemo(() => {
    const valid = deployments.filter((d): d is Deployment => d != null && d.id != null);
    if (!searchTerm) return valid;
    const term = searchTerm.toLowerCase();
    return valid.filter(
      (d) =>
        d.name?.toLowerCase().includes(term) ||
        d.template_name?.toLowerCase().includes(term) ||
        d.status?.toLowerCase().includes(term)
    );
  }, [deployments, searchTerm]);

  const confirmDelete = (record: Deployment) => {
    openConfirm({
      message: `You're about to delete the ${record?.name} deployment`,
      description:
        "Once you delete the deployment, it will not be recovered. Are you sure?",
      cancelAction: () => {},
      cancelText: "Cancel",
      loading: false,
      key: "delete-usecase-deployment",
      okAction: async () => {
        try {
          await BudUseCasesAPI.deployments.delete(record.id);
          successToast("Deployment deleted successfully");
          await fetchDeployments();
        } catch (error: any) {
          const message = error.response?.data?.detail || "Failed to delete deployment";
          errorToast(message);
        }
      },
      okText: "Delete",
      type: "warning",
    });
  };

  return (
    <div className="pb-[60px] pt-[.4rem]">
      {contextHolder}
      {isMounted && (
        <Table<Deployment>
          columns={[
            {
              title: "Name",
              dataIndex: "name",
              key: "name",
              render: (text) => <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>,
              sortOrder: orderBy === "name" ? (order === "-" ? "descend" : "ascend") : undefined,
              sorter: true,
              sortIcon: SortIcon,
            },
            {
              title: "Template",
              dataIndex: "template_name",
              key: "template_name",
              render: (text) => (
                <Text_12_400_EEEEEE>{text || "Unknown"}</Text_12_400_EEEEEE>
              ),
              sortIcon: SortIcon,
            },
            {
              title: "Status",
              key: "status",
              dataIndex: "status",
              sortOrder: orderBy === "status" ? (order === "-" ? "descend" : "ascend") : undefined,
              sorter: true,
              render: (status) => (
                <span>
                  <ProjectTags
                    name={capitalize(status)}
                    color={usecaseStatusMapping[capitalize(status)] || "#B3B3B3"}
                    textClass="text-[.75rem]"
                  />
                </span>
              ),
              sortIcon: SortIcon,
            },
            {
              title: "Components",
              dataIndex: "components",
              key: "components",
              render: (components) => (
                <Text_12_400_EEEEEE>
                  {components?.length || 0}
                </Text_12_400_EEEEEE>
              ),
            },
            {
              title: "Created On",
              dataIndex: "created_at",
              sorter: true,
              key: "created_at",
              sortOrder: orderBy === "created_at" ? (order === "-" ? "descend" : "ascend") : undefined,
              render: (text) => <Text_12_400_EEEEEE>{formatDate(text)}</Text_12_400_EEEEEE>,
              sortIcon: SortIcon,
            },
            {
              title: "",
              dataIndex: "actions",
              key: "actions",
              render: (_text, record) => (
                <div className="min-w-[40px]">
                  <div className="flex flex-row items-center justify-end gap-1">
                    {record.status?.toLowerCase() === "running" &&
                      record.access_config?.ui?.enabled && (
                        <Button
                          className="bg-transparent border-none p-0 opacity-0 group-hover:opacity-100"
                          onClick={(event) => {
                            event.stopPropagation();
                            openAppOverlay(record);
                          }}
                        >
                          <ExternalLink className="w-[.875rem] h-[.875rem] text-[#3B82F6]" />
                        </Button>
                      )}
                    <div className="w-[1rem] h-auto block">
                      <Button
                        className="bg-transparent border-none p-0 opacity-0 group-hover:opacity-100"
                        onClick={(event) => {
                          event.stopPropagation();
                          confirmDelete(record);
                        }}
                      >
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          width=".875rem"
                          height=".875rem"
                          viewBox="0 0 14 15"
                          fill="none"
                        >
                          <path
                            fillRule="evenodd"
                            clipRule="evenodd"
                            d="M5.13327 1.28906C4.85713 1.28906 4.63327 1.51292 4.63327 1.78906C4.63327 2.0652 4.85713 2.28906 5.13327 2.28906H8.8666C9.14274 2.28906 9.3666 2.0652 9.3666 1.78906C9.3666 1.51292 9.14274 1.28906 8.8666 1.28906H5.13327ZM2.7666 3.65573C2.7666 3.37959 2.99046 3.15573 3.2666 3.15573H10.7333C11.0094 3.15573 11.2333 3.37959 11.2333 3.65573C11.2333 3.93187 11.0094 4.15573 10.7333 4.15573H10.2661C10.2664 4.1668 10.2666 4.17791 10.2666 4.18906V11.5224C10.2666 12.0747 9.81889 12.5224 9.2666 12.5224H4.73327C4.18098 12.5224 3.73327 12.0747 3.73327 11.5224V4.18906C3.73327 4.17791 3.73345 4.1668 3.73381 4.15573H3.2666C2.99046 4.15573 2.7666 3.93187 2.7666 3.65573ZM9.2666 4.18906L4.73327 4.18906V11.5224L9.2666 11.5224V4.18906Z"
                            fill="#B3B3B3"
                          />
                        </svg>
                      </Button>
                    </div>
                  </div>
                </div>
              ),
            },
          ]}
          pagination={false}
          dataSource={filteredDeployments}
          rowKey="id"
          bordered={false}
          footer={null}
          virtual
          onRow={(record) => ({
            className: "group",
            onClick: () => {
              selectDeployment(record);
              openDrawer("deployment-progress", { deployment: record });
            },
          })}
          onChange={(_pagination, _filters, sorter: any) => {
            setOrder(sorter.order === "ascend" ? "" : "-");
            setOrderBy(sorter.field);
          }}
          showSorterTooltip={true}
          title={() => (
            <div className="flex justify-between items-center px-[0.75rem] py-[1rem]">
              <Text_16_600_FFFFFF className="text-[#EEEEEE]">
                Use Case Deployments
              </Text_16_600_FFFFFF>
              <div className="flex items-center justify-between gap-x-[.8rem]">
                <SearchHeaderInput
                  placeholder="Search by name"
                  searchValue={searchTerm}
                  setSearchValue={setSearchTerm}
                />
                <PrimaryButton
                  onClick={() => {
                    resetWizard();
                    openDrawer("deploy-usecase", { projectId });
                  }}
                >
                  <div className="flex items-center justify-center gap-[.2rem]">
                    <RocketOutlined className="text-[#FFFFFF]" />
                    <div className="ml-1" />
                    Deploy
                  </div>
                </PrimaryButton>
              </div>
            </div>
          )}
          locale={{
            emptyText: (
              <NoDataFount
                classNames="h-[20vh]"
                textMessage="No use case deployments"
              />
            ),
          }}
        />
      )}
    </div>
  );
};

export default UseCaseDeployments;

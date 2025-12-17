import { errorToast, successToast } from "@/components/toast";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import { SortIcon } from "@/components/ui/bud/table/SortIcon";
import NoDataFount from "@/components/ui/noDataFount";
import { Text_12_400_EEEEEE, Text_12_600_EEEEEE } from "@/components/ui/text";
import { endpointStatusMapping } from "@/lib/colorMapping";
import { MixerHorizontalIcon } from "@radix-ui/react-icons";
import { Button, ConfigProvider, Popover, Table, TableProps } from "antd";
import { useRouter } from "next/router";
import { useCallback, useEffect, useState } from "react";
import ProjectTags from "src/flows/components/ProjectTags";
import { useConfirmAction } from "src/hooks/useConfirmAction";
import { useDrawer } from "src/hooks/useDrawer";
import { IAdapter, useEndPoints } from "src/hooks/useEndPoint";
import { useProjects } from "src/hooks/useProjects";
import { IWorker } from "src/hooks/useWorkers";
import { useDeployModel } from "src/stores/useDeployModel";
import { PermissionEnum, useUser } from "src/stores/useUser";
import { formatDate } from "src/utils/formatDate";

type ColumnsType<T extends object> = TableProps<T>["columns"];

const capitalize = (str) =>
  str?.charAt(0).toUpperCase() + str?.slice(1).toLowerCase();

export default function AdaptersTable() {
  const router = useRouter();
  const { deploymentId } = router.query; // Access the dynamic part of the route
  const { hasPermission, hasProjectPermission } = useUser();
  const { openDrawer } = useDrawer();
  const { selectedProjectId } = useProjects();
  const { adapters, getAdapters, deleteAdapter } = useEndPoints();
  const { contextHolder, openConfirm } = useConfirmAction();
  const { reset } = useDeployModel();

  const [selectedRow, setSelectedRow] = useState(null);
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [confirmVisible, setConfirmVisible] = useState(false);
  const projectId = router.query.projectId as string;

  const load = useCallback(async () => {
    const payload = {
      endpointId: deploymentId as string,
      page: 1,
      limit: 20,
    };
    await getAdapters(payload, projectId);
  }, [deploymentId, projectId, getAdapters]);

  useEffect(() => {
    load();
  }, [deploymentId, projectId]);
  const columns: ColumnsType<IAdapter> = [
    {
      title: "Adapter Name",
      dataIndex: "name",
      key: "name",
      render: (text) => (
        <Text_12_600_EEEEEE className="whitespace-nowrap">
          {text}
        </Text_12_600_EEEEEE>
      ),
      sorter: (a, b) => a.name.localeCompare(b.name),
      sortIcon: SortIcon,
    },
    {
      title: "Model",
      dataIndex: "model",
      key: "model",
      render: (text) => (
        <Text_12_600_EEEEEE className="whitespace-nowrap">
          {text.name}
        </Text_12_600_EEEEEE>
      ),
      sorter: (a, b) => a.name.localeCompare(b.name),
      sortIcon: SortIcon,
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      render: (status) => (
        <span>
          <ProjectTags
            name={capitalize(status)}
            color={endpointStatusMapping[capitalize(status)]}
            textClass="text-[.75rem]"
          />
        </span>
      ),
      sorter: (a, b) => a.name.localeCompare(b.name),
      sortIcon: SortIcon,
    },
    {
      title: "Created At",
      dataIndex: "created_at",
      key: "created_at",
      render: (text) => (
        <Text_12_400_EEEEEE>{formatDate(text)}</Text_12_400_EEEEEE>
      ),
      sorter: (a, b) => a.name.localeCompare(b.name),
      sortIcon: SortIcon,
    },
    {
      title: "",
      dataIndex: "action",
      key: "action",
      render: (text, record) => (
        <div className="min-w-[130px]">
          {hasPermission(PermissionEnum.ModelManage) && (
            <div
              className="flex flex-row items-center visible-on-hover"
              style={{
                display: confirmVisible && "flex",
              }}
            >
              <PrimaryButton
                onClick={async (event) => {
                  event.stopPropagation();
                  // Pass adapter data in a format similar to endpoint
                  openDrawer("use-model", {
                    endpoint: {
                      name: record.name,
                      model: record.model,
                      // Adapters might not have supported_endpoints, so we'll rely on model.supported_endpoints
                    },
                  });
                }}
              >
                Use this model
              </PrimaryButton>
              <Button
                className="ml-[.3rem] bg-transparent border-none p-0"
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
          )}
        </div>
      ),
      sortIcon: SortIcon,
    },
  ];

  const confirmDelete = (record) => {
    if (record?.status === "deleting" || record?.status === "deleted") {
      errorToast(
        "Adapter is in deleting state, please wait for it to complete",
      );
      return;
    }
    console.log("record", record);
    setSelectedRow(record);
    setConfirmVisible(true);
    openConfirm({
      message: `You're about to delete the ${record?.name} adapter`,
      description:
        "Once you delete the adapter, it will not be recovered. If the adapter code is being used anywhere it wont function. Are you sure?",
      cancelAction: () => {},
      cancelText: "Cancel",
      loading: confirmLoading,
      key: "delete-endpoint",
      okAction: async () => {
        if (!record) {
          errorToast("No record selected");
          return;
        }
        setConfirmLoading(true);
        await deleteAdapter(record?.id, projectId);
        // deleteAdapter already shows appropriate toast message
        await load();
        setConfirmLoading(false);
        setConfirmVisible(false);
      },
      okText: "Delete",
      type: "warning",
    });
  };

  return (
    <div className="relative">
      {contextHolder}
      <Table<IAdapter>
        columns={columns}
        pagination={false}
        dataSource={adapters}
        footer={null}
        virtual
        showSorterTooltip={false}
        title={() => (
          <div className="flex justify-between items-center px-[0.75rem] py-[1rem]">
            <div className="flex justify-start items-center gap-[.4rem]">
              {/* <Tags
                    name="Model Name"
                    color="#D1B854"
                  />
                  <Tags
                    name="Cluster Name"
                    color="#D1B854"
                  /> */}
            </div>
            <div className="flex items-center">
              {(hasPermission(PermissionEnum.ProjectManage) ||
                hasProjectPermission(
                  selectedProjectId,
                  PermissionEnum.EndpointManage,
                )) && (
                <PrimaryButton
                  onClick={() => {
                    reset();
                    openDrawer("add-adapter");
                  }}
                >
                  <Text_12_600_EEEEEE className="flex items-center justify-center">
                    Add Adapter
                  </Text_12_600_EEEEEE>
                </PrimaryButton>
              )}
            </div>
          </div>
        )}
        locale={{
          emptyText: (
            <NoDataFount classNames="h-[20vh]" textMessage={`No adapters`} />
          ),
        }}
      />
    </div>
  );
}

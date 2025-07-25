import React, { useEffect, useState } from "react";
import { Table } from "antd";
import { useCloudProviders } from "src/hooks/useCloudProviders";
import {
  Text_14_400_EEEEEE,
  Text_14_600_EEEEEE,
  Text_16_600_FFFFFF,
} from "../../text";
import Image from "next/image";
import { PrimaryButton } from "../form/Buttons";
import { useDrawer } from "src/hooks/useDrawer";
import { Plus } from "lucide-react";
import { useCloudInfraProviders } from "src/hooks/useCloudInfraProviders";
import { assetBaseUrl } from "@/components/environment";
import { formatDate } from "src/utils/formatDate";

const CloudProvidersListTable = () => {
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(10);
  const { openDrawer } = useDrawer();
  const { getCloudCredentials, credentials, isLoading } =
    useCloudInfraProviders();

  useEffect(() => {
    getCloudCredentials();
  }, []);

  const columns = [
    {
      title: <Text_14_600_EEEEEE>Provider</Text_14_600_EEEEEE>,
      dataIndex: "provider_name",
      key: "provider_name",
      render: (text: string, record: any) => (
        <div className="flex items-center gap-2">
          {record.icon && (
            <div className="bg-[#1F1F1F] w-[1.75rem] h-[1.75rem] rounded-[5px] flex items-center justify-center ">
              <img
                src={`${assetBaseUrl}${record.icon || record.logo_url}`}
                alt={text}
                width={24}
                height={24}
                className="rounded-full"
              />
            </div>
          )}
          <Text_14_400_EEEEEE>{text}</Text_14_400_EEEEEE>
        </div>
      ),
    },
    {
      title: <Text_14_600_EEEEEE>Credential Name</Text_14_600_EEEEEE>,
      dataIndex: "credential_name",
      key: "credential_name",
      render: (text: string) => <Text_14_400_EEEEEE>{text}</Text_14_400_EEEEEE>,
    },
    {
      title: <Text_14_600_EEEEEE>Description</Text_14_600_EEEEEE>,
      dataIndex: "provider_description",
      key: "provider_description",
      render: (text: string) => <Text_14_400_EEEEEE>{text}</Text_14_400_EEEEEE>,
    },
    {
      title: <Text_14_600_EEEEEE>Created On</Text_14_600_EEEEEE>,
      dataIndex: "created_at",
      key: "created_at",
      render: (text: string) => (
        <Text_14_400_EEEEEE>{formatDate(text)}</Text_14_400_EEEEEE>
      ),
    },
  ];

  return (
    <div className="pb-[60px] pt-[.4rem]">
      <Table
        dataSource={credentials}
        columns={columns}
        loading={isLoading}
        title={() => (
          <div className="flex justify-between items-center px-[0.75rem] py-[1rem]">
            <Text_16_600_FFFFFF>Cloud Providers</Text_16_600_FFFFFF>
            <div className="flex items-center justify-between">
              <PrimaryButton
                onClick={() => {
                  openDrawer("add-new-cloud-provider");
                }}
              >
                <div className="flex items-center justify-center ext-[0.8125rem]">
                  <Plus className="w-[.85rem] mr-[0.375rem]" />
                  Connect To Cloud
                </div>
              </PrimaryButton>
            </div>
          </div>
        )}
        pagination={false}
        rowKey="id"
        bordered={false}
        virtual
        footer={null}
      />
    </div>
  );
};

export default CloudProvidersListTable;

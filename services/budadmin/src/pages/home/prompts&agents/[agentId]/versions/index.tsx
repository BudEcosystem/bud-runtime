import React from "react";
import { Table, Button, Tag } from "antd";
import {
  Text_14_600_EEEEEE,
  Text_12_400_B3B3B3,
} from "@/components/ui/text";
import { formatDate } from "src/utils/formatDate";

interface VersionsTabProps {
  agentData: any;
}

const VersionsTab: React.FC<VersionsTabProps> = ({ agentData }) => {
  // Mock data for versions
  const versionsData = [
    {
      key: "1",
      version: "v1.0.0",
      status: "Active",
      created_at: new Date().toISOString(),
      description: "Initial version",
    },
    {
      key: "2",
      version: "v0.9.0",
      status: "Deprecated",
      created_at: new Date(Date.now() - 86400000).toISOString(),
      description: "Previous version",
    },
  ];

  const columns = [
    {
      title: "Version",
      dataIndex: "version",
      key: "version",
      render: (text: string) => <Text_14_600_EEEEEE>{text}</Text_14_600_EEEEEE>,
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      render: (status: string) => (
        <Tag color={status === "Active" ? "green" : "default"}>{status}</Tag>
      ),
    },
    {
      title: "Description",
      dataIndex: "description",
      key: "description",
      render: (text: string) => <Text_12_400_B3B3B3>{text}</Text_12_400_B3B3B3>,
    },
    {
      title: "Created Date",
      dataIndex: "created_at",
      key: "created_at",
      render: (date: string) => <Text_12_400_B3B3B3>{formatDate(date)}</Text_12_400_B3B3B3>,
    },
    {
      title: "Actions",
      key: "actions",
      render: () => (
        <div className="flex gap-2">
          <Button size="small" type="link">
            View
          </Button>
          <Button size="small" type="link">
            Set as Default
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="px-[3.5rem] pb-8">
      <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6">
        <div className="flex justify-between items-center mb-4">
          <Text_14_600_EEEEEE>Version History</Text_14_600_EEEEEE>
          <Button type="primary">Create New Version</Button>
        </div>
        <Table
          columns={columns}
          dataSource={versionsData}
          pagination={{ pageSize: 10 }}
          className="custom-table"
        />
      </div>
    </div>
  );
};

export default VersionsTab;

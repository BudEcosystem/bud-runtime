import React from "react";
import { Table, Input, Select, DatePicker, Tag } from "antd";
import {
  Text_14_600_EEEEEE,
  Text_12_400_B3B3B3,
  Text_12_600_EEEEEE,
} from "@/components/ui/text";
import { formatTimestampWithTZ } from "@/utils/formatDate";

const { RangePicker } = DatePicker;

interface LogsTracesTabProps {
  agentData: any;
}

const LogsTracesTab: React.FC<LogsTracesTabProps> = ({ agentData }) => {
  // Mock data for logs
  const logsData = [
    {
      key: "1",
      timestamp: new Date().toISOString(),
      level: "INFO",
      message: "Agent request processed successfully",
      duration: "245ms",
      status: "Success",
    },
    {
      key: "2",
      timestamp: new Date(Date.now() - 60000).toISOString(),
      level: "ERROR",
      message: "Rate limit exceeded",
      duration: "12ms",
      status: "Failed",
    },
    {
      key: "3",
      timestamp: new Date(Date.now() - 120000).toISOString(),
      level: "INFO",
      message: "Agent request processed successfully",
      duration: "189ms",
      status: "Success",
    },
  ];

  const columns = [
    {
      title: "Timestamp",
      dataIndex: "timestamp",
      key: "timestamp",
      render: (date: string) => <Text_12_400_B3B3B3>{formatTimestampWithTZ(date)}</Text_12_400_B3B3B3>,
    },
    {
      title: "Level",
      dataIndex: "level",
      key: "level",
      render: (level: string) => (
        <Tag color={level === "ERROR" ? "red" : level === "WARN" ? "orange" : "blue"}>
          {level}
        </Tag>
      ),
    },
    {
      title: "Message",
      dataIndex: "message",
      key: "message",
      render: (text: string) => <Text_12_600_EEEEEE>{text}</Text_12_600_EEEEEE>,
    },
    {
      title: "Duration",
      dataIndex: "duration",
      key: "duration",
      render: (text: string) => <Text_12_400_B3B3B3>{text}</Text_12_400_B3B3B3>,
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      render: (status: string) => (
        <Tag color={status === "Success" ? "green" : "red"}>{status}</Tag>
      ),
    },
  ];

  return (
    <div className="px-[3.5rem] pb-8">
      <div className="bg-[#101010] border border-[#1F1F1F] rounded-lg p-6">
        <Text_14_600_EEEEEE className="mb-4 block">Logs & Traces</Text_14_600_EEEEEE>

        {/* Filters */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          <Input.Search placeholder="Search logs..." />
          <Select
            placeholder="Log Level"
            options={[
              { label: "All Levels", value: "all" },
              { label: "INFO", value: "info" },
              { label: "WARN", value: "warn" },
              { label: "ERROR", value: "error" },
            ]}
          />
          <Select
            placeholder="Status"
            options={[
              { label: "All Status", value: "all" },
              { label: "Success", value: "success" },
              { label: "Failed", value: "failed" },
            ]}
          />
          <RangePicker className="w-full" />
        </div>

        {/* Logs Table */}
        <Table
          columns={columns}
          dataSource={logsData}
          pagination={{ pageSize: 20 }}
          scroll={{ y: 400 }}
          className="custom-table"
        />
      </div>
    </div>
  );
};

export default LogsTracesTab;

import React from "react";
import { Table } from "antd";
import { ColumnsType } from "antd/es/table";
import { Text_12_400_EEEEEE, Text_12_400_B3B3B3 } from "@/components/ui/text";
import ProjectTags from "src/flows/components/ProjectTags";
import { capitalize } from "@/lib/utils";
import { endpointStatusMapping } from "@/lib/colorMapping";

interface RunHistoryItem {
  runId: string;
  model: string;
  status: 'Completed' | 'Failed' | 'Running';
  startedDate: string;
  duration: string;
  benchmarkScore: string;
}

interface RunsHistoryTableProps {
  data: RunHistoryItem[];
}

const RunsHistoryTable: React.FC<RunsHistoryTableProps> = ({ data }) => {
  const columns: ColumnsType<RunHistoryItem> = [
    {
      title: "Run ID",
      dataIndex: "runId",
      key: "runId",
      render: (text: string) => (
        <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>
      ),
    },
    {
      title: "Model",
      dataIndex: "model",
      key: "model",
      render: (text: string) => (
        <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>
      ),
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      render: (status: string) => (
        <ProjectTags
          name={capitalize(status)}
          color={endpointStatusMapping[capitalize(status) === 'Running' ? capitalize(status) + '-yellow' : capitalize(status)]}
          textClass="text-[.75rem] py-[.22rem]"
          tagClass="py-[0rem]"
        />
      ),
    },
    {
      title: "Started Date",
      dataIndex: "startedDate",
      key: "startedDate",
      render: (text: string) => (
        <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>
      ),
    },
    {
      title: "Duration",
      dataIndex: "duration",
      key: "duration",
      render: (text: string) => (
        <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>
      ),
    },
    {
      title: "Evaluated Benchmark and Score",
      dataIndex: "benchmarkScore",
      key: "benchmarkScore",
      render: (text: string) => (
        <div className="flex space-x-2">
          <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>
          <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>
          <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>
        </div>
      ),
    },
  ];

  return (
    <div className="runs-history-table eval-explorer-wrapper">
      <style jsx global>{`
        .runs-history-table .ant-table {
          background: transparent;
        }
        .runs-history-table .ant-table-thead > tr > th {
          background: transparent;
          border-bottom: 1px solid #1F1F1F;
          color: #B3B3B3;
          font-size: 12px;
          font-weight: 400;
          padding: 12px 16px;
        }
        .runs-history-table .ant-table-tbody > tr > td {
          background: transparent;
          border-bottom: 1px solid #1F1F1F;
          padding: 12px 16px;
        }
        .runs-history-table .ant-table-tbody > tr:hover > td {
          background: rgba(255, 255, 255, 0.02);
        }
        .runs-history-table .ant-table-tbody > tr:last-child > td {
          border-bottom: none;
        }
      `}</style>
      <Table
        columns={columns}
        dataSource={Array.isArray(data) ? data : []}
        pagination={false}
        // pagination={{
        //   pageSize: 10,
        //   showSizeChanger: true,
        //   showQuickJumper: true,
        //   showTotal: (total, range) => `${range[0]}-${range[1]} of ${total} items`,
        // }}
        rowKey="runId"
        size="small"
        className="eval-explorer-table"
      />
    </div>
  );
};

export default RunsHistoryTable;

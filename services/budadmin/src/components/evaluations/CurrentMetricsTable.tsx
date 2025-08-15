import React from "react";
import { Table } from "antd";
import { ColumnsType } from "antd/es/table";
import { Text_12_400_EEEEEE, Text_12_400_B3B3B3 } from "@/components/ui/text";

interface CurrentMetric {
  evaluation: string;
  gpt4Score: number;
  claude3Score: number;
}

interface CurrentMetricsTableProps {
  data: CurrentMetric[];
}

const CurrentMetricsTable: React.FC<CurrentMetricsTableProps> = ({ data }) => {
  const columns: ColumnsType<CurrentMetric> = [
    {
      title: "Evaluation",
      dataIndex: "evaluation",
      key: "evaluation",
      render: (text: string) => (
        <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>
      ),
    },
    {
      title: "GPT-4 Score",
      dataIndex: "gpt4Score",
      key: "gpt4Score",
      render: (score: number) => (
        <Text_12_400_EEEEEE>{score}%</Text_12_400_EEEEEE>
      ),
    },
    {
      title: "Claude 3 Suit",
      dataIndex: "claude3Score",
      key: "claude3Score",
      render: (score: number) => (
        <Text_12_400_EEEEEE>{score}%</Text_12_400_EEEEEE>
      ),
    },
  ];

  return (
    <div className="current-metrics-table eval-explorer-wrapper">
      <style jsx global>{`
        .current-metrics-table .ant-table {
          background: transparent;
        }
        .current-metrics-table .ant-table-thead > tr > th {
          background: transparent;
          border-bottom: 1px solid #1F1F1F;
          color: #B3B3B3;
          font-size: 12px;
          font-weight: 400;
          padding: 12px 16px;
        }
        .current-metrics-table .ant-table-tbody > tr > td {
          background: transparent;
          border-bottom: 1px solid #1F1F1F;
          padding: 12px 16px;
        }
        .current-metrics-table .ant-table-tbody > tr:hover > td {
          background: rgba(255, 255, 255, 0.02);
        }
        .current-metrics-table .ant-table-tbody > tr:last-child > td {
          border-bottom: none;
        }
      `}</style>
      <Table
        columns={columns}
        dataSource={Array.isArray(data) ? data : []}
        pagination={false}
        rowKey="evaluation"
        size="small"
      />
    </div>
  );
};

export default CurrentMetricsTable;

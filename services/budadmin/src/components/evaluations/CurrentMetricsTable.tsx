import React, { useMemo } from "react";
import { Table } from "antd";
import { ColumnsType } from "antd/es/table";
import { Text_12_400_EEEEEE, Text_12_400_B3B3B3 } from "@/components/ui/text";

interface ModelScore {
  value: number;
  higher_is_better: boolean;
  status: string;
}

interface CurrentMetric {
  trait_name: string;
  model_scores: {
    [modelName: string]: ModelScore;
  };
}

interface CurrentMetricsTableProps {
  data: CurrentMetric[];
}

const CurrentMetricsTable: React.FC<CurrentMetricsTableProps> = ({ data }) => {
  // Extract unique model names from the data to create dynamic columns
  const modelNames = useMemo(() => {
    if (!Array.isArray(data) || data.length === 0) return [];
    const models = new Set<string>();
    data.forEach(metric => {
      if (metric?.model_scores) {
        Object.keys(metric.model_scores).forEach(model => models.add(model));
      }
    });
    return Array.from(models);
  }, [data]);

  // Transform data for the table
  const tableData = useMemo(() => {
    if (!Array.isArray(data)) return [];
    return data.map(metric => ({
      trait_name: metric.trait_name,
      ...metric.model_scores
    }));
  }, [data]);

  const columns: ColumnsType<any> = useMemo(() => {
    const cols: ColumnsType<any> = [
      {
        title: "Evaluation",
        dataIndex: "trait_name",
        key: "trait_name",
        render: (text: string) => <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>,
      },
    ];

    // Add a column for each model
    modelNames.forEach(modelName => {
      cols.push({
        title: modelName,
        dataIndex: modelName,
        key: modelName,
        render: (scoreData: ModelScore) => {
          if (!scoreData || scoreData.value === 0) {
            return <Text_12_400_EEEEEE>-</Text_12_400_EEEEEE>;
          }
          // Convert to percentage (multiply by 100 if value is between 0 and 1)
          const displayValue = scoreData.value <= 1 ? (scoreData.value * 100).toFixed(1) : scoreData.value.toFixed(1);
          return <Text_12_400_EEEEEE>{displayValue}%</Text_12_400_EEEEEE>;
        },
      });
    });

    return cols;
  }, [modelNames]);

  return (
    <div className="current-metrics-table eval-explorer-wrapper">
      <style jsx global>{`
        .current-metrics-table .ant-table {
          background: transparent;
        }
        .current-metrics-table .ant-table-thead > tr > th {
          background: transparent;
          border-bottom: 1px solid #1f1f1f;
          color: #b3b3b3;
          font-size: 12px;
          font-weight: 400;
          padding: 12px 16px;
        }
        .current-metrics-table .ant-table-tbody > tr > td {
          background: transparent;
          border-bottom: 1px solid #1f1f1f;
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
        dataSource={tableData}
        pagination={false}
        rowKey="trait_name"
        size="small"
      />
    </div>
  );
};

export default CurrentMetricsTable;

import React from "react";
import { Table, Skeleton } from "antd";
import { Typography } from "antd";
import dayjs from "dayjs";
import styles from "./UsageTable.module.scss";

const { Text } = Typography;

interface UsageTableProps {
  data: any[];
  loading?: boolean;
}

const UsageTable: React.FC<UsageTableProps> = ({ data, loading = false }) => {
  const columns = [
    {
      title: <Text className={styles.columnHeader}>DATE</Text>,
      dataIndex: "date",
      key: "date",
      render: (date: string) => (
        <Text className={styles.cellText}>
          {dayjs(date).format("MMM DD, YYYY")}
        </Text>
      ),
    },
    {
      title: <Text className={styles.columnHeader}>MODEL</Text>,
      dataIndex: "model",
      key: "model",
      render: (model: string) => (
        <Text className={styles.cellText}>{model || "—"}</Text>
      ),
    },
    {
      title: <Text className={styles.columnHeader}>ENDPOINT</Text>,
      dataIndex: "endpoint",
      key: "endpoint",
      render: (endpoint: string) => (
        <Text className={styles.cellText}>{endpoint || "—"}</Text>
      ),
    },
    {
      title: <Text className={styles.columnHeader}>TOKENS</Text>,
      dataIndex: "tokens",
      key: "tokens",
      align: "right" as const,
      render: (tokens: number) => (
        <Text className={styles.cellText}>
          {tokens ? tokens.toLocaleString() : "0"}
        </Text>
      ),
    },
    {
      title: <Text className={styles.columnHeader}>REQUESTS</Text>,
      dataIndex: "requests",
      key: "requests",
      align: "right" as const,
      render: (requests: number) => (
        <Text className={styles.cellText}>{requests || "0"}</Text>
      ),
    },
    {
      title: <Text className={styles.columnHeader}>COST</Text>,
      dataIndex: "cost",
      key: "cost",
      align: "right" as const,
      render: (cost: number) => (
        <Text className={styles.costText}>
          ${cost ? cost.toFixed(4) : "0.0000"}
        </Text>
      ),
    },
  ];

  if (loading) {
    return (
      <div className={styles.tableContainer}>
        <div className={styles.tableHeader}>
          <Text className={styles.tableTitle}>Usage Details</Text>
        </div>
        <Skeleton active paragraph={{ rows: 8 }} />
      </div>
    );
  }

  return (
    <div className={styles.tableContainer}>
      <div className={styles.tableHeader}>
        <Text className={styles.tableTitle}>Usage Details</Text>
        <Text className={styles.tableSubtitle}>
          {data.length} records found
        </Text>
      </div>
      <Table
        dataSource={data}
        columns={columns}
        rowKey={(record) => `${record.date}-${record.model}-${record.endpoint}`}
        pagination={{
          pageSize: 10,
          showSizeChanger: false,
          showTotal: (total, range) => `${range[0]}-${range[1]} of ${total}`,
          className: styles.pagination,
        }}
        className={styles.usageTable}
        scroll={{ x: 800 }}
      />
    </div>
  );
};

export default UsageTable;

import React, { useMemo, useState } from "react";
import { Table, Tooltip } from "antd";
import ProjectTags from "src/flows/components/ProjectTags";
import { LeaderBoardItem } from "src/hooks/useModels";
import { Text_12_300_EEEEEE } from "../../text";
import NoDataFount from "../../noDataFount";

function SortIcon({ sortOrder }: { sortOrder: string }) {
  return sortOrder ? (
    sortOrder === "descend" ? (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="12"
        height="13"
        viewBox="0 0 12 13"
        fill="none"
      >
        <path
          fillRule="evenodd"
          clipRule="evenodd"
          d="M6.00078 2.10938C6.27692 2.10938 6.50078 2.33324 6.50078 2.60938L6.50078 9.40223L8.84723 7.05578C9.04249 6.86052 9.35907 6.86052 9.55433 7.05578C9.7496 7.25104 9.7496 7.56763 9.55433 7.76289L6.35433 10.9629C6.15907 11.1582 5.84249 11.1582 5.64723 10.9629L2.44723 7.76289C2.25197 7.56763 2.25197 7.25104 2.44723 7.05578C2.64249 6.86052 2.95907 6.86052 3.15433 7.05578L5.50078 9.40223L5.50078 2.60938C5.50078 2.33324 5.72464 2.10938 6.00078 2.10938Z"
          fill="#B3B3B3"
        />
      </svg>
    ) : (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="12"
        height="13"
        viewBox="0 0 12 13"
        fill="none"
      >
        <path
          fillRule="evenodd"
          clipRule="evenodd"
          d="M6.00078 10.8906C6.27692 10.8906 6.50078 10.6668 6.50078 10.3906L6.50078 3.59773L8.84723 5.94418C9.04249 6.13944 9.35907 6.13944 9.55433 5.94418C9.7496 5.74892 9.7496 5.43233 9.55433 5.23707L6.35433 2.03707C6.15907 1.84181 5.84249 1.84181 5.64723 2.03707L2.44723 5.23707C2.25197 5.43233 2.25197 5.74892 2.44723 5.94418C2.64249 6.13944 2.95907 6.13944 3.15433 5.94418L5.50078 3.59773L5.50078 10.3906C5.50078 10.6668 5.72464 10.8906 6.00078 10.8906Z"
          fill="#B3B3B3"
        />
      </svg>
    )
  ) : null;
}

// Helper function to format decimal values to max 6 decimal places
const formatDecimalValue = (value: unknown): string => {
  if (value === null || value === undefined) return "-";

  const numValue = Number(value);
  if (isNaN(numValue)) {
    // Return the original string value if it's not a valid number
    return String(value);
  }

  // Use toFixed(6) and convert back to number to remove trailing zeros
  return Number(numValue.toFixed(6)).toString();
};

function LeaderboardsTable({
  data,
  leaderboardClasses,
}: {
  data: LeaderBoardItem[];
  leaderboardClasses?: string;
}) {
  const [, setOrderBy] = useState<string>("");
  const [, setOrder] = useState<string>("");

  const rows = useMemo(() => {
    let horizontalRows = [];

    data?.forEach((item) => {
      Object.keys(item.benchmarks).forEach((key) => {
        if (!horizontalRows.includes(key)) {
          horizontalRows.push({
            label: item.benchmarks[key].label,
            dataset: item.benchmarks[key].type,
            [item.model.uri]: item.benchmarks[key].value,
          });
        } else {
          horizontalRows = horizontalRows.map((row) => {
            if (row.label === item.benchmarks[key].label) {
              return {
                ...row,
                dataset: item.benchmarks[key].type,
                [item.model.uri]: item.benchmarks[key].value,
              };
            }
            return row;
          });
        }
      });
    });
    // merge the rows
    const mergedRows = [];

    horizontalRows.forEach((row) => {
      const existingRow = mergedRows.find(
        (mergedRow) => mergedRow.label === row.label,
      );
      if (existingRow) {
        mergedRows[mergedRows.indexOf(existingRow)] = {
          ...existingRow,
          ...row,
        };
      } else {
        mergedRows.push(row);
      }
    });

    return mergedRows;
  }, [data]);

  return (
    <div
      className={`${leaderboardClasses} leaderboards-table`}
      style={{
        paddingBottom: "30px",
        paddingTop: ".4rem",
      }}
    >
      <style jsx global>{`
        .leaderboards-table .ant-table-body {
          overflow-x: auto !important;
          scrollbar-width: thin;
          scrollbar-color: #757575 #1f1f1f;
        }
        .leaderboards-table .ant-table-body::-webkit-scrollbar {
          height: 8px;
        }
        .leaderboards-table .ant-table-body::-webkit-scrollbar-track {
          background: #1f1f1f;
          border-radius: 4px;
        }
        .leaderboards-table .ant-table-body::-webkit-scrollbar-thumb {
          background: #757575;
          border-radius: 4px;
        }
        .leaderboards-table .ant-table-body::-webkit-scrollbar-thumb:hover {
          background: #999999;
        }
        .leaderboards-table .ant-table-content {
          position: relative;
        }
        .leaderboards-table .ant-table-content::after {
          content: '';
          position: absolute;
          top: 0;
          right: 0;
          bottom: 8px;
          width: 30px;
          background: linear-gradient(to right, transparent, rgba(16, 16, 16, 0.9));
          pointer-events: none;
          z-index: 1;
        }
        .leaderboards-table:hover .ant-table-content::after {
          opacity: 0.5;
        }
      `}</style>
      <Table<LeaderBoardItem>
        columns={[
          {
            width: 120,
            ellipsis: true,
            title: "Benchmark",
            dataIndex: "label",
            key: "label",
            render: (text) => <Text_12_300_EEEEEE>{text}</Text_12_300_EEEEEE>,
            sortIcon: SortIcon,
          },
          {
            width: 120,
            ellipsis: true,
            title: "Type",
            dataIndex: "dataset",
            key: "dataset",
            render: (text) => (
              <ProjectTags color="#D1B854" name={text || "N/A"} />
            ),
            sortIcon: SortIcon,
          },
          data
            ?.filter((item) => item.model.is_selected)
            .map((item) => {
              return {
                width: 120,
                ellipsis: true,
                title: "Selected Model",
                dataIndex: item.model?.uri,
                key: item.model?.uri,
                render: (text: number | string) => (
                  <Text_12_300_EEEEEE>{formatDecimalValue(text)}</Text_12_300_EEEEEE>
                ),
                sortIcon: SortIcon,
              };
            })?.[0] || {
            title: "Selected Model",
            dataIndex: "selected",
            key: "selected",
            render: (text: number | string) => <Text_12_300_EEEEEE>{formatDecimalValue(text)}</Text_12_300_EEEEEE>,
            sortIcon: SortIcon,
          },
          ...data
            ?.filter((item) => !item.model.is_selected)
            .map((item) => {
              return {
                width: 120,
                ellipsis: true,
                title: (
                  <Tooltip placement="topLeft" title={item.model?.uri}>
                    {item.model?.uri}
                  </Tooltip>
                ),
                dataIndex: item.model?.uri,
                key: item.model?.uri,
                render: (text: number | string) => (
                  <Text_12_300_EEEEEE className="">{formatDecimalValue(text)}</Text_12_300_EEEEEE>
                ),
                sortIcon: SortIcon,
              };
            }),
        ]}
        pagination={false}
        dataSource={rows}
        bordered={false}
        footer={null}
        scroll={{ x: 600 }}
        onChange={(
          pagination,
          filters,
          sorter: {
            order: "ascend" | "descend";
            field: string;
          },
          extra,
        ) => {
          setOrder(sorter.order === "ascend" ? "" : "-");
          setOrderBy(sorter.field);
        }}
        showSorterTooltip={true}
        locale={{
          emptyText: (
            <NoDataFount
              classNames="h-[20vh]"
              textMessage={`Data not available`}
            />
          ),
        }}
      />
    </div>
  );
}

export default LeaderboardsTable;

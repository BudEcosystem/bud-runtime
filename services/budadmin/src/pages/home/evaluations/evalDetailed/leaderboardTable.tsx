import React, { useEffect, useState } from "react";
import { Image, Modal, notification, Popconfirm, Table } from "antd";
import { assetBaseUrl } from "@/components/environment";

import { useRouter as useRouter } from "next/router";

import {
  Text_12_300_EEEEEE,
  Text_12_400_EEEEEE,
  Text_16_600_FFFFFF,
} from "@/components/ui/text";
import NoDataFount from "@/components/ui/noDataFount";

import { SortIcon } from "@/components/ui/bud/table/SortIcon";
import { color } from "echarts";
import Tags from "src/flows/components/DrawerTags";
import { formatDate } from "@/utils/formatDate";
const capitalize = (str) =>
  str?.charAt(0).toUpperCase() + str?.slice(1).toLowerCase();

interface DataType {
  rank?: {
    name: string;
    color: string;
  };
  model: {
    icon: string;
    name: string;
  };
  score?: string;
  lastUpdated?: string;
}

const sampleResponse = [
  {
    rank: { name: "#1", color: "#965CDE" },
    model: { icon: "/images/drawer/zephyr.png", name: "GPT 3.5" },
    score: "65.1",
    lastUpdated: "2 days ago",
  },
  {
    rank: { name: "#2", color: "#42CACF" },
    model: { icon: "/images/drawer/zephyr.png", name: "GPT 3.5" },
    score: "65.1",
    lastUpdated: "2 days ago",
  },
  {
    rank: { name: "#3", color: "#EC7575" },
    model: { icon: "/images/drawer/zephyr.png", name: "GPT 3.5" },
    score: "65.1",
    lastUpdated: "2 days ago",
  },
  {
    rank: { name: "#4", color: "#EC7575" },
    model: { icon: "/images/drawer/zephyr.png", name: "GPT 3.5" },
    score: "65.1",
    lastUpdated: "2 days ago",
  },
  {
    rank: { name: "#5", color: "#EC7575" },
    model: { icon: "/images/drawer/zephyr.png", name: "GPT 3.5" },
    score: "65.1",
    lastUpdated: "2 days ago",
  },
];

type LeaderboardDetailsProps = {
  leaderBoards: any[] | null;
};
function LeaderboardTable({ leaderBoards }: LeaderboardDetailsProps) {
  const router = useRouter();
  const [order, setOrder] = useState<"-" | "">("");
  const [orderBy, setOrderBy] = useState<string>("created_at");

  return (
    <div className="pb-[60px] pt-[1.45rem] eval-explorer-wrapper">
      <Table<DataType>
        className="eval-explorer-table"
        columns={[
          {
            title: "Rank",
            dataIndex: "rank",
            key: "rank",
            width: "10%",
            render: (text) => (
              <div className="flex justify-start">
                <Tags
                  name={text}
                  color={'#D1B854'}
                  textClass="text-[#EEEEEE] text-[0.75rem]"
                  classNames="w-[2rem] h-[1.5rem]"
                />
              </div>
            ),
            sortOrder:
              orderBy === "name"
                ? order === "-"
                  ? "descend"
                  : "ascend"
                : undefined,
            sorter: true,
            sortIcon: SortIcon,
          },
          {
            title: "Model",
            dataIndex: "model",
            key: "model",
            width: "40%",
            render: (_, record: any) => (
              <div className="flex justify-start items-center gap-[.2rem]">
                {record.model_icon && (
                  <div className="w-[1.2rem] h-[1.2rem] p-[.2rem] bg-[#1F1F1F] rounded-[5px] flex items-center justify-center" >
                    <Image
                      preview={false}
                      src={`${assetBaseUrl}${record.model_icon}`}
                      style={{ width: "100%", height: "100%", objectFit: 'contain' }}
                      alt="Model Icon"
                    />
                  </div>
                )}
                <Text_12_300_EEEEEE>{record.model_name}</Text_12_300_EEEEEE>
              </div>
            ),
            sorter: true,
            sortIcon: SortIcon,
          },
          {
            title: "Score",
            dataIndex: "accuracy",
            key: "accuracy",
            width: "10%",
            sorter: true,
            sortOrder:
              orderBy === "text"
                ? order === "-"
                  ? "descend"
                  : "ascend"
                : undefined,
            render: (text) => <Text_12_300_EEEEEE>{Number(text || 0).toFixed(2)}</Text_12_300_EEEEEE>,
            sortIcon: SortIcon,
          },
          {
            title: "Last Updated",
            dataIndex: "created_at",
            key: "created_at",
            width: "15%",
            sorter: true,
            sortOrder:
              orderBy === "text"
                ? order === "-"
                  ? "descend"
                  : "ascend"
                : undefined,
            render: (text) => <Text_12_300_EEEEEE>{formatDate(text)}</Text_12_300_EEEEEE>,
            sortIcon: SortIcon,
          },
        ]}
        pagination={false}
        dataSource={leaderBoards}
        bordered={false}
        footer={null}
        virtual
        onRow={(record, rowIndex) => {
          return {
            onClick: async (event) => {
              null;
            },
          };
        }}
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
            <NoDataFount classNames="h-[20vh]" textMessage={`No deployments`} />
          ),
        }}
      />
    </div>
  );
}

export default LeaderboardTable;

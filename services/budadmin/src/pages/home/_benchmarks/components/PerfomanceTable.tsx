import React, { useEffect, useState } from "react";
import { Image, Input, notification, Table } from "antd";
import type { TableProps } from "antd";
import ProjectTags from "src/flows/components/ProjectTags";
import { assetBaseUrl } from "@/components/environment";
import { useRouter as useRouter } from "next/router";
import { useDrawer } from "src/hooks/useDrawer";
import { useDeployModel } from "src/stores/useDeployModel";
import { useProjects } from "src/hooks/useProjects";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import { formatDate } from "src/utils/formatDate";
import { useOverlay } from "src/context/overlayContext";
import useHandleRouteChange from "@/lib/useHandleRouteChange";
import Tags from "src/flows/components/DrawerTags";
import { useLoaderOnLoding } from "src/hooks/useLoaderOnLoading";
import { Text_12_400_EEEEEE, Text_16_600_FFFFFF } from "@/components/ui/text";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import NoDataFount from "@/components/ui/noDataFount";
import { RequestMetricsData, useBenchmarks } from "src/hooks/useBenchmark";
import { SortIcon } from "@/components/ui/bud/table/SortIcon";

const capitalize = (str) =>
  str?.charAt(0).toUpperCase() + str?.slice(1).toLowerCase();

function PerfomanceTable() {
  const [loading, setLoading] = useState(false);
  const [searchValue, setSearchValue] = useState("");
  const router = useRouter();
  const { benchmarkId } = router.query; // Access the dynamic part of the route
  const [order, setOrder] = useState<"-" | "">("");
  const [orderBy, setOrderBy] = useState<string>("created_at");
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const {
    getBenchmarkResultRequestMetrics,
    benchmarkRequestMetrics,
    benchmarkRequestMetricsTotalCount,
  } = useBenchmarks();

  useLoaderOnLoding(loading);

  useHandleRouteChange(() => {
    notification.destroy();
  });

  const getData = () => {
    if (!benchmarkId) return;
    getBenchmarkResultRequestMetrics({
      benchmark_id: benchmarkId as string,
      page: currentPage,
      limit: pageSize,
    });
  };

  useEffect(() => {
    getData();
  }, [benchmarkId]);

  useEffect(() => {
    // debounce
    if (!benchmarkId) return;
    const timer = setTimeout(() => {
      getData();
    }, 500);
    return () => clearTimeout(timer);
  }, [searchValue, currentPage, pageSize]);

  const handlePageChange = (currentPage, pageSize) => {
    setCurrentPage(currentPage);
    setPageSize(pageSize);
  };

  return (
    <div className="CommonCustomPagination">
      <Table<RequestMetricsData>
        columns={[
          {
            title: "Input Tokens",
            dataIndex: "prompt_len",
            sorter: true,
            key: "prompt_len",
            sortOrder:
              orderBy === "prompt_len"
                ? order === "-"
                  ? "descend"
                  : "ascend"
                : undefined,
            render: (text) => <Text_12_400_EEEEEE>{text ?? "-"}</Text_12_400_EEEEEE>,
            sortIcon: SortIcon,
          },
          {
            title: "Output Tokens",
            dataIndex: "output_len",
            sorter: true,
            key: "output_len",
            sortOrder:
              orderBy === "output_len"
                ? order === "-"
                  ? "descend"
                  : "ascend"
                : undefined,
            render: (text) => <Text_12_400_EEEEEE>{text ?? "-"}</Text_12_400_EEEEEE>,
            sortIcon: SortIcon,
          },
          {
            title: "Output Throughput (tok/s)",
            dataIndex: "req_output_throughput",
            key: "req_output_throughput",
            render: (text) => (
              <Text_12_400_EEEEEE className="text-nowrap">
                {text?.toFixed(2) || "-"}
              </Text_12_400_EEEEEE>
            ),
            sortOrder:
              orderBy === "req_output_throughput"
                ? order === "-"
                  ? "descend"
                  : "ascend"
                : undefined,
            sorter: true,
            sortIcon: SortIcon,
          },
          {
            title: "TTFT (s)",
            dataIndex: "ttft",
            key: "ttft",
            sorter: true,
            sortOrder:
              orderBy === "ttft"
                ? order === "-"
                  ? "descend"
                  : "ascend"
                : undefined,
            render: (text) => (
              <Text_12_400_EEEEEE>{text?.toFixed(4) || "-"}</Text_12_400_EEEEEE>
            ),
            sortIcon: SortIcon,
          },
          {
            title: "ITL Mean (s)",
            dataIndex: "itl",
            key: "itl",
            sorter: false,
            render: (itl: number[]) => {
              const mean = itl?.length > 0 ? itl.reduce((a, b) => a + b, 0) / itl.length : null;
              return (
                <Text_12_400_EEEEEE>{mean?.toFixed(4) || "-"}</Text_12_400_EEEEEE>
              );
            },
            sortIcon: SortIcon,
          },
          {
            title: "E2E Latency (s)",
            dataIndex: "latency",
            key: "latency",
            sorter: true,
            sortOrder:
              orderBy === "latency"
                ? order === "-"
                  ? "descend"
                  : "ascend"
                : undefined,
            render: (text) => (
              <Text_12_400_EEEEEE>{text?.toFixed(4) || "-"}</Text_12_400_EEEEEE>
            ),
            sortIcon: SortIcon,
          },
          {
            title: "Error",
            dataIndex: "error",
            key: "error",
            sortOrder:
              orderBy === "error"
                ? order === "-"
                  ? "descend"
                  : "ascend"
                : undefined,
            sorter: true,
            render: (text) => (
              <Text_12_400_EEEEEE>{text || "-"}</Text_12_400_EEEEEE>
            ),
            sortIcon: SortIcon,
          },
        ]}
        pagination={{
          current: currentPage,
          pageSize: pageSize,
          total: benchmarkRequestMetricsTotalCount,
          onChange: handlePageChange,
        }}
        dataSource={benchmarkRequestMetrics}
        bordered={false}
        footer={null}
        virtual
        onRow={(record, rowIndex) => {
          return {
            onClick: async (event) => {
              // router.push(`/projects/${projectId}/deployments/${record.id}`)
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
        title={() => (
          <div className="flex justify-between items-center px-[0.75rem] py-[.9rem]">
            <Text_16_600_FFFFFF className="text-[#EEEEEE]">
              Perfomance
            </Text_16_600_FFFFFF>
            <div className="flex items-center justify-between gap-x-[.4rem]">
              <SearchHeaderInput
                placeholder={"Search by name"}
                searchValue={searchValue}
                setSearchValue={setSearchValue}
              />
            </div>
          </div>
        )}
        locale={{
          emptyText: (
            <NoDataFount
              classNames="h-[20vh]"
              textMessage={`No clusters found`}
            />
          ),
        }}
      />
    </div>
  );
}

export default PerfomanceTable;

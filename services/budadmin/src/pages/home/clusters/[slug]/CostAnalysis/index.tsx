"use client";
import { useCallback, useEffect, useState } from "react";
import { AppRequest } from "./../../../../api/requests";
import { Image, Segmented, Table } from "antd";

import {
  Text_12_300_EEEEEE,
  Text_12_400_EEEEEE,
  Text_13_400_757575,
  Text_16_600_FFFFFF,
  Text_19_600_EEEEEE,
  Text_20_400_EEEEEE,
  Text_26_400_EEEEEE,
} from "@/components/ui/text";

import { useRouter } from "next/router";
import { assetBaseUrl, tempApiBaseUrl } from "@/components/environment";
import { Cluster } from "src/hooks/useCluster";
import BarChart from "@/components/charts/barChart";
import { Model } from "src/hooks/useModels";
import ProjectTags from "src/flows/components/ProjectTags";
import { capitalize } from "@/lib/utils";
import { endpointStatusMapping } from "@/lib/colorMapping";
import { formatDate } from "src/utils/formatDate";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import { useUser } from "src/stores/useUser";
import NoDataFount from "@/components/ui/noDataFount";
import { useEndPoints } from "src/hooks/useEndPoint";
import { useLoaderOnLoding } from "src/hooks/useLoaderOnLoading";

const modelDataSample = {
  data: [46.06, 34.065],
  categories: ["zephyr", "budecosystem/code-millenials-8b"],
  label1: "Usage",
  label2: "Models",
};

interface GeneralProps {
  data: Cluster;
}

interface DataType {
  key?: string;
  name?: string;
  status?: string;
  type?: string;
  created_at?: string;
  model?: Model;
  cluster?: Cluster;
  id?: string;
}

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

const CostAnalysis: React.FC<GeneralProps> = ({ data }) => {
  const router = useRouter();
  const { projectId } = router.query;
  const [modelChartData, setModelChartData] = useState<any>(modelDataSample);
  const [modelRequestData, setModleRequestData] = useState<any>();
  const [modelRequestInterval, setModelRequestInterval] =
    useState<any>("daily");

  const [tokenUsageChartData, setTokenUsageChartData] =
    useState<any>(modelDataSample);
  const [tokenUsageRequestData, setTokenUsageRequestData] = useState<any>();
  const [tokenUsageRequestInterval, setTokenUsageRequestInterval] =
    useState<any>("daily");
  const [order, setOrder] = useState<"-" | "">("");
  const [orderBy, setOrderBy] = useState<string>("created_at");
  const [searchValue, setSearchValue] = useState("");
  const { endPoints } = useEndPoints();
  // useLoaderOnLoding(loading);

  const requestOptions = [
    { label: "Last 24 hrs", value: "daily" },
    { label: "Last 7 days", value: "weekly" },
    { label: "Last 30 days", value: "monthly" },
  ];
  const numberOfDays = {
    daily: 1, // Last 24 hours
    weekly: 7, // Last 7 days
    monthly: 30, // Last 30 days
  };

  const segmentOptions = ["LAST 24 HRS", "LAST 7 DAYS", "LAST 30 DAYS"];

  const getDateSubtracted = (days) => {
    const date = new Date();
    date.setDate(date.getDate() - days);
    return date.toISOString().split("T")[0];
  };

  const calculateFromDate = (daysToReduce: number) => {
    const now = new Date(); // Get current date and time
    const pastDate = new Date(now); // Create a copy
    pastDate.setUTCDate(now.getUTCDate() - daysToReduce); // Subtract days
    return pastDate.toISOString(); // Return full ISO string with time
  };
  // model usage code block ----------------------------------
  const getModelUsageData = async (freq?: any, endDate?: any) => {
    try {
      const url = `${tempApiBaseUrl}/metrics/analytics/request-counts`;
      const response: any = await AppRequest.Post(url, {
        frequency: freq || modelRequestInterval,
        filter_by: "model",
        filter_conditions: [],
        from_date: calculateFromDate(numberOfDays[modelRequestInterval]),
        top_k: 5,
        metrics: "overall",
        project_id: projectId,
      });
      setModleRequestData(response.data);
      // successToast(response.message);
    } catch (error) {
      console.error("Error creating model:", error);
    }
  };

  const getTokenUsageData = async (freq?: any, endDate?: any) => {
    try {
      const url = `${tempApiBaseUrl}/metrics/analytics/request-counts`;
      const response: any = await AppRequest.Post(url, {
        frequency: freq || tokenUsageRequestInterval,
        filter_by: "endpoint",
        filter_conditions: [],
        from_date: calculateFromDate(numberOfDays[tokenUsageRequestInterval]),
        top_k: 5,
        metrics: "concurrency",
        project_id: projectId,
      });
      setTokenUsageRequestData(response.data);
      // successToast(response.message);
    } catch (error) {
      console.error("Error creating model:", error);
    }
  };

  const createModelChartData = (data) => {
    if (data) {
      setModelChartData((prevState) => ({
        ...prevState,
        categories:
          data?.overall_metrics?.summary_metrics?.items.map(
            (item) => item.name,
          ) || [],
        data:
          data?.overall_metrics?.summary_metrics?.items.map(
            (item) => item.total_value,
          ) || [],
      }));
    }
  };

  const handleModelRequestChange = (data) => {
    setModelRequestInterval(data.value);
  };

  useEffect(() => {
    getModelUsageData(modelRequestInterval);
  }, [modelRequestInterval, projectId]);

  useEffect(() => {
    createModelChartData(modelRequestData);
  }, [modelRequestData]);
  // model usage code block ----------------------------------

  const createTokenUsageChartData = (data) => {
    if (data) {
      setTokenUsageChartData((prevState) => ({
        ...prevState,
        categories:
          data?.concurrency_metrics?.summary_metrics?.items.map(
            (item) => item.name,
          ) || [],
        data:
          data?.concurrency_metrics?.summary_metrics?.items.map(
            (item) => item.total_value,
          ) || [],
      }));
    }
  };

  const handleTokenUsageRequestChange = (data) => {
    setTokenUsageRequestInterval(data.value);
  };

  useEffect(() => {
    getTokenUsageData(tokenUsageRequestInterval);
  }, [tokenUsageRequestInterval, projectId]);

  useEffect(() => {
    createTokenUsageChartData(tokenUsageRequestData);
  }, [tokenUsageRequestData]);

  let computeUsage = {
    categories: ["time", "time", "time", "time", "time", "time"],
    data: [0, 20, 40, 60, 80],
    label1: "",
    label2: "",
    color: "#FFC442",
    smooth: true,
  };
  const chartCardData = [
    {
      title: "Total Cost",
      description: "Total Cost per Node",
      value: "Avg. +21.01%",
      percentage: "",
      chartData: <BarChart data={modelDataSample} />, // Pass your chart data here
      segmentOptions: segmentOptions,
      onSegmentChange: null,
      classNames: "",
    },
    {
      title: "Power Consumption",
      description: "Power consumption per Node",
      value: "127K",
      percentage: "Avg. +21.01%",
      chartData: <BarChart data={modelDataSample} />, // Pass your chart data here
      segmentOptions: segmentOptions,
      onSegmentChange: null,
      classNames: "",
    },
    {
      title: "Operations Cost",
      description: "Operations Cost per Node",
      value: "13%",
      percentage: "Avg. +21.01%",
      chartData: <BarChart data={modelDataSample} />, // Pass your chart data here
      segmentOptions: segmentOptions,
      onSegmentChange: null,
      classNames: "",
    },
  ];

  const ChartUsageCard = ({ data, showSegmented = false }: any) => {
    return (
      <div
        className={`cardBG w-[49.1%] h-[380px] py-[2rem] pb-[.5rem] px-[1.5rem] border border-[#1F1F1F] rounded-md ${data.classNames}`}
      >
        <div className="flex justify-between align-center">
          <div>
            <Text_19_600_EEEEEE>{data.title}</Text_19_600_EEEEEE>
          </div>
          {showSegmented && data.segmentOptions && (
            <Segmented
              options={data.segmentOptions}
              onChange={(value) => {
                data.onSegmentChange(value); // This function comes from the data prop
              }}
              className="antSegmented general rounded-md text-[#EEEEEE] font-[400] bg-[transparent] border border-[#4D4D4D] border-[.53px] p-[0] mt-[.05rem]"
            />
          )}
        </div>
        {data.description && (
          <div className="mt-[.7rem]">
            <Text_13_400_757575>{data.description}</Text_13_400_757575>
          </div>
        )}
        <div className="flex flex-col items-start mt-[1.7rem]">
          <Text_26_400_EEEEEE className="">{data.value}</Text_26_400_EEEEEE>
          <div className="flex bg-[#122F1140] rounded-md items-center px-[.45rem] mb-[.1rem] h-[1.35rem] mt-[0.35rem]">
            <span className="text-[#479D5F] font-[400] text-[0.8125rem] leading-[100%]">{`Avg. ${data.percentage}`}</span>
            <Image
              preview={false}
              width={12}
              src="/images/dashboard/greenArrow.png"
              className="ml-[.2rem]"
              alt=""
            />
          </div>
        </div>
        <div className="h-[180px]">{data.chartData}</div>
      </div>
    );
  };

  return (
    <div className="relative pb-[3rem]">
      <div>
        <Text_20_400_EEEEEE>Cost Analytics</Text_20_400_EEEEEE>
      </div>
      <div className="mt-[1.55rem]">
        <div className="flex justify-between flex-wrap gap-x-[.8rem] gap-y-[1.4rem] mt-[1.4rem]">
          {chartCardData.map((item, index) => (
            <ChartUsageCard
              key={index}
              data={item}
              showSegmented={!!item.segmentOptions}
            />
          ))}
        </div>
      </div>
      <div className="hR my-[1.2rem]"></div>
      <div>
        <Table<DataType>
          columns={[
            {
              title: "Model Name",
              dataIndex: "name",
              key: "name",
              render: (text) => <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>,
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
              title: "Name Space",
              dataIndex: "model",
              key: "model",
              width: 150,
              render: (text) => (
                <div className="select-none flex items-center">
                  <div className="w-[0.875rem] h-[0.875rem]">
                    <Image
                      src={`${assetBaseUrl}${text.icon}`}
                      preview={false}
                      style={{ width: "0.875rem" }}
                    />
                  </div>
                  <Text_12_300_EEEEEE
                    className="flex-auto truncate max-w-[90%]"
                    style={{ marginLeft: 10 }}
                  >
                    {text.name}
                  </Text_12_300_EEEEEE>
                </div>
              ),
              sortIcon: SortIcon,
            },
            {
              title: "IP Address",
              dataIndex: "cluster",
              key: "cluster_name",
              render: (text) => (
                <Text_12_400_EEEEEE>{text?.name}</Text_12_400_EEEEEE>
              ),
              sortIcon: SortIcon,
            },
            {
              title: "Node IP",
              key: "status",
              dataIndex: "status",
              sortOrder:
                orderBy === "status"
                  ? order === "-"
                    ? "descend"
                    : "ascend"
                  : undefined,
              sorter: true,
              render: (status) => (
                <span>
                  <ProjectTags
                    name={capitalize(status)}
                    color={endpointStatusMapping[capitalize(status)]}
                  />
                </span>
              ),
              sortIcon: SortIcon,
            },
            {
              title: "Node Cost",
              dataIndex: "model",
              key: "type",
              render: (text) => (
                <Text_12_400_EEEEEE>{text.modality}</Text_12_400_EEEEEE>
              ),
              sortIcon: SortIcon,
            },
            {
              title: "Running Cost",
              dataIndex: "created_at",
              sorter: true,
              key: "created_at",
              sortOrder:
                orderBy === "created_at"
                  ? order === "-"
                    ? "descend"
                    : "ascend"
                  : undefined,
              render: (text) => (
                <Text_12_400_EEEEEE>{formatDate(text)}</Text_12_400_EEEEEE>
              ),
              sortIcon: SortIcon,
            },
            {
              title: "Power Consumption",
              dataIndex: "created_on",
              key: "created_on",
              render: (text, record) => (
                <div className="min-w-[130px]">
                  <div className="flex flex-row items-center visible-on-hover">
                    <PrimaryButton
                      onClick={async (event) => {
                        event.stopPropagation();
                      }}
                    >
                      Use this model
                    </PrimaryButton>
                    <button
                      type="button"
                      className="ml-[.3rem]"
                      style={{
                        display:
                          record?.status === "deleting" ||
                          record?.status === "deleted"
                            ? "none"
                            : "block",
                      }}
                      onClick={(event) => {}}
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        width="14"
                        height="15"
                        viewBox="0 0 14 15"
                        fill="none"
                      >
                        <path
                          fillRule="evenodd"
                          clipRule="evenodd"
                          d="M5.13327 1.28906C4.85713 1.28906 4.63327 1.51292 4.63327 1.78906C4.63327 2.0652 4.85713 2.28906 5.13327 2.28906H8.8666C9.14274 2.28906 9.3666 2.0652 9.3666 1.78906C9.3666 1.51292 9.14274 1.28906 8.8666 1.28906H5.13327ZM2.7666 3.65573C2.7666 3.37959 2.99046 3.15573 3.2666 3.15573H10.7333C11.0094 3.15573 11.2333 3.37959 11.2333 3.65573C11.2333 3.93187 11.0094 4.15573 10.7333 4.15573H10.2661C10.2664 4.1668 10.2666 4.17791 10.2666 4.18906V11.5224C10.2666 12.0747 9.81889 12.5224 9.2666 12.5224H4.73327C4.18098 12.5224 3.73327 12.0747 3.73327 11.5224V4.18906C3.73327 4.17791 3.73345 4.1668 3.73381 4.15573H3.2666C2.99046 4.15573 2.7666 3.93187 2.7666 3.65573ZM9.2666 4.18906L4.73327 4.18906V11.5224L9.2666 11.5224V4.18906Z"
                          fill="#B3B3B3"
                        />
                      </svg>
                    </button>
                  </div>
                </div>
              ),
              sortIcon: SortIcon,
            },
          ]}
          pagination={false}
          dataSource={endPoints}
          bordered={false}
          footer={null}
          virtual
          onRow={(record, rowIndex) => {
            return {
              onClick: async (event) => {
                router.push(`/projects/${projectId}/deployments/${record.id}`);
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
            <div className="flex justify-between items-center px-[0.75rem] py-[1rem]">
              <Text_16_600_FFFFFF className="text-[#EEEEEE]">
                Cost
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
                textMessage={`No deployments`}
              />
            ),
          }}
        />
      </div>
    </div>
  );
};

export default CostAnalysis;

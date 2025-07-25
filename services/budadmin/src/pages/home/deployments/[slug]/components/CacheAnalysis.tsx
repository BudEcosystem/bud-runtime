import {
  Text_12_300_EEEEEE,
  Text_12_400_EEEEEE,
  Text_14_400_EEEEEE,
  Text_16_400_757575,
  Text_19_600_EEEEEE,
  Text_20_400_EEEEEE,
} from "@/components/ui/text";
import { ConfigProvider, Progress, Table, Typography } from "antd";
import React, { useEffect, useState } from "react";
import { CircleProgress } from "./DeploymentAnalysis";
import ComingSoon from "@/components/ui/comingSoon";
import { useRouter } from "next/router";
import { tempApiBaseUrl } from "@/components/environment";
import { AppRequest } from "src/pages/api/requests";
import NoDataFount from "@/components/ui/noDataFount";
import { secondsToMilliseconds } from "@/lib/utils";
import { useEndPoints } from "src/hooks/useEndPoint";

function PlaceholderCard() {
  return (
    <div className="p-[1.067rem] w-full flex items-center justify-center flex-col"></div>
  );
}

export default function CacheAnalysis() {
  const router = useRouter();
  const { projectId, deploymentId } = router.query;
  const { getReusedPrompts, reusedPromptList } = useEndPoints();

  function LatencyCard(latency) {
    return (
      <div className="bg-[#101010] p-[1.067rem] pl-[2.1rem] rounded-[6.403px] border-[1.067px] border-[#1F1F1F]  flex flex-row gap-x-[1.1875rem] align-start justify-start w-[65%]">
        <div className="flex items-center justify-center rounded-full  border-[#479D5F33] border border-[3px] w-[4.451875rem] h-[4.451875rem]">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="1.5rem"
            height="1.5rem"
            viewBox="0 0 24 25"
            fill="none"
          >
            <path
              d="M9.03182 12.5774C9.26714 12.5774 9.5015 12.4874 9.68057 12.3084C10.0396 11.9503 10.0396 11.369 9.68057 11.0099L7.04537 8.37474H18.2738C18.781 8.37474 19.1916 7.96318 19.1916 7.45693C19.1916 6.94974 18.78 6.53912 18.2738 6.53912L7.04537 6.53818L9.68057 3.90298C10.0396 3.54485 10.0396 2.96266 9.68057 2.60453C9.32151 2.24641 8.74025 2.24641 8.38212 2.60453L4.17924 6.80741C3.82111 7.16554 3.82111 7.7468 4.17924 8.10586L8.38212 12.3087C8.56118 12.4878 8.7965 12.5778 9.0318 12.5778L9.03182 12.5774Z"
              fill="#479D5F"
            />
            <path
              d="M19.8204 16.9637L15.6176 12.7608C15.2594 12.4027 14.6782 12.4027 14.3191 12.7608C13.96 13.1189 13.96 13.7002 14.3191 14.0592L16.9543 16.6944H5.72591C5.21872 16.6944 4.80811 17.106 4.80811 17.6132C4.80811 18.1204 5.21966 18.531 5.72591 18.531H16.9543L14.3191 21.1671C13.96 21.5253 13.96 22.1075 14.3191 22.4656C14.4982 22.6447 14.7335 22.7347 14.9679 22.7347C15.2032 22.7347 15.4385 22.6447 15.6166 22.4656L19.8195 18.2618C20.1785 17.9036 20.1785 17.3224 19.8204 16.9633L19.8204 16.9637Z"
              fill="#479D5F"
            />
          </svg>
        </div>
        <div className="flex flex-col gap-[0.5875rem] align-start justify-start">
          <Text_14_400_EEEEEE className="text-[2.875rem]  w-full font-[700] leading-[2.5rem]">
            {secondsToMilliseconds(latency.latency)}
            <span className="font-[400]">
              {latency.latency >= 1 ? "s" : "ms"}
            </span>
          </Text_14_400_EEEEEE>
          <Text_20_400_EEEEEE className="ml-[0.23rem] mt-[0.1rem] leading-[100%] text-nowrap">
            Cache Latency
          </Text_20_400_EEEEEE>
        </div>
      </div>
    );
  }

  function PromptsDetailCard(promptList) {
    const dataSource = promptList?.promptList?.map((item, index) => ({
      key: (index + 1).toString(),
      prompts: item[0],
      reused: item[1],
    }));
    return (
      <div className="bg-[#101010] rounded-[6.403px] border-[1.067px] border-[#1F1F1F]  w-[100%] flex items-center justify-center flex-col">
        <div className="flex items-start justify-between w-full flex-row border-b-[1px] border-[#1F1F1F] px-[1.4rem] pt-[1.25rem] pb-[1.35rem] group">
          <div className="flex items-start justify-start w-full flex-col">
            <Typography.Title
              className="mb-[0.5rem] text-[#EEEEEE] font-[400] self-start text-[0.875rem] text-nowrap"
              level={4}
            >
              Most Reused Prompts
            </Typography.Title>
            <Typography.Text className="text-[#757575] self-start font-[400] text-[.75rem] text-nowrap">
              Below are the most reused prompts in the deployment
            </Typography.Text>
          </div>
          <div className="flex items-center justify-end mt-[.2rem]">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width=".75rem"
              height=".75rem"
              viewBox="0 0 13 13"
              fill="none"
              className="opacity-0 group-hover:opacity-100 transition-opacity duration-200"
            >
              <path
                fillRule="evenodd"
                clipRule="evenodd"
                d="M4.60039 1.21875C4.32425 1.21875 4.10039 1.44261 4.10039 1.71875C4.10039 1.99489 4.32425 2.21875 4.60039 2.21875H10.5004V10.8188H4.60039C4.32425 10.8188 4.10039 11.0426 4.10039 11.3188C4.10039 11.5949 4.32425 11.8188 4.60039 11.8188H10.6004C11.0974 11.8188 11.5004 11.4158 11.5004 10.9187V2.11875C11.5004 1.62169 11.0974 1.21875 10.6004 1.21875H4.60039ZM6.35394 4.3652C6.15868 4.16993 5.8421 4.16993 5.64684 4.3652C5.45158 4.56046 5.45158 4.87704 5.64684 5.0723L6.59328 6.01875H1.40039C1.12425 6.01875 0.900391 6.24261 0.900391 6.51875C0.900391 6.79489 1.12425 7.01875 1.40039 7.01875H6.59328L5.64684 7.9652C5.45158 8.16046 5.45158 8.47704 5.64684 8.6723C5.8421 8.86757 6.15868 8.86757 6.35394 8.6723L8.15394 6.8723C8.34921 6.67704 8.34921 6.36046 8.15394 6.1652L6.35394 4.3652Z"
                fill="#B3B3B3"
              />
            </svg>
          </div>
        </div>
        <div className="CacheAnalyticsTable CommonCustomPagination flex flex-col gap-2 w-full px-[1.4rem] py-[.85rem]">
          <ConfigProvider
            theme={{
              token: {
                borderRadius: 0,
              },
              components: {
                Table: {
                  headerBg: "#161616",
                },
              },
            }}
          >
            <Table
              columns={[
                {
                  title: "Prompts",
                  dataIndex: "prompts",
                  key: "prompts",
                  width: "80%",
                  render: (text) => (
                    <Text_12_300_EEEEEE className="py-[1rem]">
                      {text}
                    </Text_12_300_EEEEEE>
                  ),
                },
                {
                  title: "Reused",
                  dataIndex: "reused",
                  key: "reused",
                  align: "center",
                  render: (text) => (
                    <Text_12_300_EEEEEE className="text-center">
                      {text}
                    </Text_12_300_EEEEEE>
                  ),
                },
              ]}
              onHeaderRow={(column) => {
                return {
                  style: {
                    color: "#EEE",
                    fontSize: ".75rem",
                    fontWeight: 400,
                  },
                };
              }}
              showSorterTooltip={false}
              dataSource={dataSource}
              scroll={{ x: "max-content", y: 55 * 5 }}
              pagination={{ pageSize: 5 }}
              locale={{
                emptyText: (
                  <NoDataFount
                    classNames="h-[20vh]"
                    textMessage={`No Prompts`}
                  />
                ),
              }}
            />
          </ConfigProvider>
        </div>
      </div>
    );
  }

  const load = async () => {
    getReusedPrompts(deploymentId as string);
  };

  useEffect(() => {
    if (deploymentId) {
      load();
    }
  }, [deploymentId]);

  const [data, setData] = React.useState([
    {
      title: "HIT Ratio",
      percent: 0,
      size: 49,
      strokeWidth: 4,
      trailColor: "#1F1F1F",
      strokeColor: "#FFA800",
    },
  ]);
  useEffect(() => {
    setData([
      {
        title: "HIT Ratio",
        percent: reusedPromptList
          ? Number((Number(reusedPromptList.hit_ratio) * 100).toFixed(2))
          : 0,
        size: 49,
        strokeWidth: 4,
        trailColor: "#1F1F1F",
        strokeColor: "#FFA800",
      },
    ]);
  }, [reusedPromptList]);
  return (
    <div className="flex flex-col gap-[.75rem] p-[.25rem] px-[0rem] pb-[0] relative">
      <div>
        <Text_20_400_EEEEEE className="mb-[0.1em] mt-[.75rem] w-full tracking-[.025rem]">
          Cache Analytics
        </Text_20_400_EEEEEE>
        <Text_16_400_757575>
          Start adding the cluster by entering the details{" "}
        </Text_16_400_757575>
      </div>
      <div className="flex w-full mt-[.5rem]">
        <div className="flex gap-[.75rem] w-[51%]">
          {reusedPromptList && (
            <LatencyCard latency={reusedPromptList?.latency} />
          )}
          {data.map((item, index) => (
            <CircleProgress key={index} {...item} />
          ))}
        </div>
      </div>
      <div className="flex gap-4 pt-[.1rem]">
        <PromptsDetailCard promptList={reusedPromptList?.most_reused_prompts} />
      </div>
    </div>
  );
}

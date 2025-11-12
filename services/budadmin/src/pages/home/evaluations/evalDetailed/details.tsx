import React, { useEffect, useState } from "react";
import { Image, Modal, notification, Popconfirm, Table } from "antd";

import { useRouter as useRouter } from "next/router";

import {
  Text_12_300_EEEEEE,
  Text_12_400_757575,
  Text_12_400_EEEEEE,
  Text_14_400_EEEEEE,
  Text_16_400_EEEEEE,
  Text_16_600_FFFFFF,
  Text_24_400_EEEEEE,
} from "@/components/ui/text";
import NoDataFount from "@/components/ui/noDataFount";

import { SortIcon } from "@/components/ui/bud/table/SortIcon";
import { color } from "echarts";
import Tags from "src/flows/components/DrawerTags";
import EvalBarChart from "@/components/charts/barChart/evalBarChart";
const capitalize = (str) =>
  str?.charAt(0).toUpperCase() + str?.slice(1).toLowerCase();

const ChartData = {
  data: [80, 20, 10, 30, 23],
  categories: ["10", "20", "30", "40", "50", "60"],
  label1: "Usage",
  label2: "Models",
  barColor: "#9462D5",
};

const lsitData = [
  {
    title: "Why Run this Eval?",
    content: [
      "InternLM 2.5 offers strong reasoning across the board as well as tool",
      "InternLM 2.5 offers strong reasoning across the board as well as tool use for developers, while sitting at the sweet spot of size for those with 24GB GPUs.",
    ],
  },
  {
    title: "What to Expect?",
    content: [
      "InternLM 2.5 offers strong reasoning across the board as well as tool",
      "InternLM 2.5 offers strong reasoning across the board as well as tool use for developers, while sitting at the sweet spot of size for those with 24GB GPUs.",
    ],
  },
  {
    title: "Advantages",
    content: [
      "InternLM 2.5 offers strong reasoning across the board as well as tool",
      "InternLM 2.5 offers strong reasoning across the board as well as tool use for developers, while sitting at the sweet spot of size for those with 24GB GPUs.",
    ],
  },
  {
    title: "Constraints",
    content: [
      "InternLM 2.5 offers strong reasoning across the board as well as tool",
      "InternLM 2.5 offers strong reasoning across the board as well as tool use for developers, while sitting at the sweet spot of size for those with 24GB GPUs.",
    ],
  },
];
interface ListItem {
  title: string;
  content: string[];
}
type LeaderboardDetailsProps = {
  datasets: any
};
function LeaderboardDetails({datasets}: LeaderboardDetailsProps) {
  const router = useRouter();
  const [listData, setListData] = useState<ListItem[]>([
    { title: "Why Run this Eval?", content: [] },
    { title: "What to Expect?", content: [] },
    { title: "Advantages", content: [] },
    { title: "Constraints", content: [] },
  ]);
  useEffect(()=> {
    const updatedList = [
      { title: "Why Run this Eval?", content: datasets?.advantages_disadvantages?.why_run_eval || [] },
      { title: "What to Expect?", content: datasets?.advantages_disadvantages?.what_to_expect || [] },
      { title: "Advantages", content: datasets?.advantages_disadvantages?.advantages || [] },
      { title: "Constraints", content: datasets?.advantages_disadvantages?.disadvantages || [] },
    ];

    setListData(updatedList);
  }, [datasets])
  return (
    <div className="pb-[60px] flex justify-between items-start ">
      <div className="w-[63.5%]">
        <div className="pb-[1.5rem]">
          <Text_24_400_EEEEEE>Introduction</Text_24_400_EEEEEE>
          <Text_12_400_757575 className="leading-[140%] pt-[.25rem]">
            {datasets?.description}
          </Text_12_400_757575>
        </div>
        <div className="hR"></div>
        <div>
          {listData.map((data, index) => (
            <div className="pt-[1.2rem]" key={index}>
              <Text_16_400_EEEEEE>{data.title}</Text_16_400_EEEEEE>
              {data.content.length > 0 ? <ul className="custom-bullet-list mt-[.5rem] !pl-[0]">
                {data.content.map((data, index) => (
                  <li className="mb-[.6rem]" key={index}>
                    <Text_12_400_EEEEEE className="leading-[140%] indent-0 pl-[.5rem]">
                      {data}
                    </Text_12_400_EEEEEE>
                  </li>
                ))}
              </ul>: <div className="pt-[.5rem]"><Text_12_400_757575 className="leading-[140%] pt-[.25rem]">No Data Found</Text_12_400_757575></div>}
              <div className="hR mt-[1.2rem]"></div>
            </div>
          ))}
        </div>
      </div>
      <div className="w-[36.5%] relative flex justify-end items-start">
        <div className="w-[88%] border rounded-[.875rem] border-[#1F1F1F] py-[1.7rem] px-[1.4rem] backdrop-blur-sm bg-white/5">
          <div>
            <Text_14_400_EEEEEE>Evaluation Values</Text_14_400_EEEEEE>
            <Text_12_400_757575 className="leading-[140%] pt-[.3rem]">
              Following are some of the concepts this evaluator
            </Text_12_400_757575>
          </div>
          <div className="w-[100%]">
            <div className="flex justify-start mt-[1rem]">
              <div
                className={`flex ${Number(5) >= 0 ? "text-[#479D5F] bg-[#122F1140]" : "bg-[#861A1A33] text-[#EC7575]"} rounded-md items-center px-[.45rem] mb-[.1rem] h-[1.35rem] mt-[0.82rem]`}
              >
                <span className="font-[400] text-[0.8125rem] leading-[100%]">
                  Avg. +{Number(5).toFixed(0)}yrs{" "}
                </span>
                {Number(5) >= 0 ? (
                  <Image
                    preview={false}
                    width={12}
                    src="/images/dashboard/greenArrow.png"
                    className="ml-[.2rem]"
                    alt=""
                  />
                ) : (
                  <Image
                    preview={false}
                    width={12}
                    src="/images/dashboard/redArrow.png"
                    className="ml-[.2rem]"
                    alt=""
                  />
                )}
              </div>
            </div>
            <div className="w-[100%] h-[160px] min-[1680]:h-[200px]">
              <EvalBarChart data={ChartData} />
            </div>
            <div className="hR mt-[0.7rem]"></div>
          </div>
          <div className="py-[1.35rem]">
            <div className="mb-[1rem]">
              <div className={`flex justify-start items-center  "min-w-[32%]"`}>
                <div className="h-[.75rem] flex justify-start items-start">
                  <div className="!mr-[.4rem] w-[0.75rem] flex justify-start items-start">
                    <Image
                      preview={false}
                      src="/images/drawer/tag.png"
                      alt="info"
                      style={{ height: ".75rem" }}
                    />
                  </div>
                </div>
                <Text_12_400_EEEEEE className="ml-[.1rem] mr-[.4rem] text-nowrap">
                  Total Input tokens
                </Text_12_400_EEEEEE>
                <Text_12_400_EEEEEE className="ml-[.5rem] mr-[.4rem] text-nowrap">
                  {datasets?.estimated_input_tokens || 0}
                </Text_12_400_EEEEEE>
              </div>
            </div>
            <div className="">
              <div className={`flex justify-start items-center  "min-w-[32%]"`}>
                <div className="h-[.75rem] flex justify-start items-start">
                  <div className="!mr-[.4rem] w-[0.75rem] flex justify-start items-start">
                    <Image
                      preview={false}
                      src="/images/drawer/tag.png"
                      alt="info"
                      style={{ height: ".75rem" }}
                    />
                  </div>
                </div>
                <Text_12_400_EEEEEE className="ml-[.1rem] mr-[.4rem] text-nowrap">
                  Expected Output
                </Text_12_400_EEEEEE>
                <Text_12_400_EEEEEE className="ml-[.5rem] mr-[.4rem] text-nowrap">
                  {datasets?.estimated_output_tokens || 0}
                </Text_12_400_EEEEEE>
              </div>
            </div>
            <div className="hR mt-[1.3rem]"></div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default LeaderboardDetails;

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
import CompositeChart from "@/components/charts/compositeChart";
const capitalize = (str) =>
  str?.charAt(0).toUpperCase() + str?.slice(1).toLowerCase();


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
  datasets: {
    estimated_input_tokens?: number;
    estimated_output_tokens?: number;
    description: string;
    advantages_disadvantages: any;
    additional_info: any;
    modalities: string[];
    what_to_expect: string[];
    why_run_this_eval: string[];
    meta_links: any
  } | null;
  leaderBoards: any[]
};

function LeaderboardDetails({ datasets, leaderBoards }: LeaderboardDetailsProps) {

  const [chartData, setChartData] = useState<any>({
    data: [80, 20, 10, 30, 23],
    categories: ["10", "20", "30", "40", "50", "60"],
    label1: "Usage",
    label2: "Models",
    barColor: "#9462D5",
  });

  const router = useRouter();
  const [listData, setListData] = useState<ListItem[]>([
    { title: "Why Run this Eval?", content: [] },
    { title: "What to Expect?", content: [] },
    { title: "Advantages", content: [] },
    { title: "Constraints", content: [] },
  ]);
  useEffect(() => {
    const updatedList = [
      { title: "Why Run this Eval?", content: datasets?.why_run_this_eval || [] },
      { title: "What to Expect?", content: datasets?.what_to_expect || [] },
      { title: "Advantages", content: datasets?.advantages_disadvantages?.advantages || [] },
      { title: "Constraints", content: datasets?.advantages_disadvantages?.disadvantages || [] },
    ];

    setListData(updatedList);
  }, [datasets])

  useEffect(()=> {
    const displayValues = leaderBoards?.map((item: any) => ({
      accuracy: item.accuracy,
      model_name: item.model_name ?? null
    }));
    console.log(displayValues)
    setChartData({...chartData, data:displayValues?.map(el => el.accuracy) ?? [], categories:displayValues?.map(el => el.model_name) ?? []})
  }, [leaderBoards])
  const data: any = {};

  const displaySections = [
    {
      header: 'Domains',
      description: 'Following are some of the domains of this evaluation',
      keyName: 'top_5_domains',
    },
    {
      header: 'Concepts',
      description: 'Following are some of the domains of this evaluation',
      keyName: 'top_5_concepts',
    },
    {
      header: 'Humans vs LLM Qualifications',
      description: 'Following are some of the domains of this evaluation',
      keyName: 'top_5_qualifications',
    },
    {
      header: 'Language',
      description: 'Following are some of the domains of this evaluation',
      keyName: 'top_5_languages',
    }, {
      header: 'Skills Identified',
      description: 'Following are some of the domains of this evaluation',
      keyName: 'top_5_skills',
    },
    {
      header: 'Task Type',
      description: 'Following are some of the domains of this evaluation',
      keyName: 'top_5_task_types',
    },
  ]
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
            data?.content.length ? <div className="pt-[1.2rem]" key={index}>
              <Text_16_400_EEEEEE>{data?.title}</Text_16_400_EEEEEE>
              {data?.content.length > 0 ? <ul className="custom-bullet-list mt-[.5rem] !pl-[0]">
                {data?.content.map((data, index) => (
                  <li className="mb-[.6rem]" key={index}>
                    <Text_12_400_EEEEEE className="leading-[140%] indent-0 pl-[.5rem]">
                      {data}
                    </Text_12_400_EEEEEE>
                  </li>
                ))}
              </ul> : <div className="pt-[.5rem]"><Text_12_400_757575 className="leading-[140%] pt-[.25rem]">No Data Found</Text_12_400_757575></div>}
              <div className="hR mt-[1.2rem]"></div>
            </div>: null
          ))}
        </div>
      </div>
      <div className="w-[36.5%] relative flex justify-end items-start">
        <div className="w-[88%] border rounded-[.875rem] border-[#1F1F1F] py-[1.7rem] px-[1.4rem] backdrop-blur-sm bg-white/5">
          <div>
            <Text_14_400_EEEEEE>Evaluation Values</Text_14_400_EEEEEE>
            <Text_12_400_757575 className="leading-[140%] pt-[.3rem]">
              Following are some of the evaluator scores
            </Text_12_400_757575>
          </div>
          <div className="w-[100%]">
            <div className="flex hidden justify-start mt-[1rem]">
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
              <EvalBarChart data={chartData} />
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

          <div className="py-[.3rem]">
            <div className="flex items-center justify-between mb-[.2rem]">
              <div className="flex items-center justify-start gap-[.6rem]">
                {datasets?.meta_links?.github && (
                  <div className="bg-[#8F55D62B] flex items-center rounded-md items-center px-[.45rem] mb-[.1rem] h-[1.35rem]">
                  <a
                    href={datasets?.meta_links?.github}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="flex  items-center gap-1 justify-center hover:opacity-80 transition-opacity"
                  >
                    <Image
                      preview={false}
                      className=""
                      style={{ width: "auto", height: "0.75rem" }}
                      src="/images/evaluations/icons/cat.svg"
                      alt="GitHub"
                    />
                    <span className="text-[#965CDE] font-[400] text-[0.6rem] leading-[100%]">Paper 1</span>
                  </a>
                  </div>
                )}
                {datasets?.meta_links?.paper && (
                  <div className="bg-[#8F55D62B] flex items-center rounded-md items-center px-[.45rem] mb-[.1rem] h-[1.35rem]">
                  <a
                    href={datasets?.meta_links.paper}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="flex items-center gap-1 justify-center h-[0.75rem] hover:opacity-80 transition-opacity"
                  >
                    <Image
                      preview={false}
                      className=""
                      style={{ width: "auto", height: "0.75rem" }}
                      src="/images/evaluations/icons/lense.svg"
                      alt="Paper"
                    />
                    <span className="text-[#965CDE] font-[400] text-[0.6rem] leading-[100%]">Github Link</span>
                  </a>
                  </div>
                )}
                {datasets?.meta_links?.website && (
                <div className="bg-[#8F55D62B] flex items-center rounded-md items-center px-[.45rem] mb-[.1rem] h-[1.35rem]">
                  <a
                    href={datasets?.meta_links.website}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="flex items-center gap-1 justify-center h-[.9rem] hover:opacity-80 transition-opacity"
                  >
                    <Image
                      preview={false}
                      className=""
                      style={{ width: "auto", height: ".9rem" }}
                      src="/images/icons/Globe.png"
                      alt="Website"
                    />
                    <span className="text-[#965CDE] font-[400] text-[0.6rem] leading-[100%]">Website</span>
                  </a>
                  </div>
                )}
              </div>
              </div>
            <div className="hR mt-[1.3rem]"></div>
          </div>

          <div className="pt-[1.3rem]">
            <Text_14_400_EEEEEE>Modalities</Text_14_400_EEEEEE>
            <Text_12_400_757575 className="pt-[.33rem]">
              Following is the list of things model is really good at doing
            </Text_12_400_757575>
            <div className="modality flex items-center justify-start gap-[.5rem] mt-[1rem]">
              <div className="flex flex-col items-center gap-[.5rem] gap-y-[1rem] bg-[#ffffff08] w-[50%] p-[1rem] rounded-[6px]">
                <Text_14_400_EEEEEE className="leading-[100%]">
                  Input
                </Text_14_400_EEEEEE>
                <div className="flex justify-center items-center gap-x-[.5rem]">
                  <div className="h-[1.25rem]">
                    <Image
                      preview={false}
                      src={
                        datasets?.modalities.includes('text')
                          ? "/images/drawer/endpoints/text.png"
                          : "/images/drawer/endpoints/text-not.png"
                      }
                      alt={'Text'}
                      style={{ width: "1.25rem", height: "1.25rem" }}
                    />
                  </div>
                  <div className="h-[1.25rem]">
                    <Image
                      preview={false}
                      src={
                        datasets?.modalities.includes('image')
                          ? "/images/drawer/endpoints/image.png"
                          : "/images/drawer/endpoints/image-not.png"
                      }
                      alt={'Image'}
                      style={{ height: "1.25rem" }}
                    />
                  </div>
                  <div className="h-[1.25rem]">
                    <Image
                      preview={false}
                      src={
                        datasets?.modalities.includes('audio')
                          ? "/images/drawer/endpoints/audio_speech.png"
                          : "/images/drawer/endpoints/audio_speech-not.png"
                      }
                      alt={'Audio'}
                      style={{ height: "1.25rem" }}
                    />
                  </div>
                </div>
                <Text_12_400_EEEEEE className="leading-[100%] capitalize">
                  {datasets?.modalities?.join(", ")}
                </Text_12_400_EEEEEE>
              </div>
              <div className="flex flex-col items-center gap-[.5rem] gap-y-[1rem] bg-[#ffffff08] w-[50%] p-[1rem] rounded-[6px]">
                <Text_14_400_EEEEEE className="leading-[100%]">
                  Output
                </Text_14_400_EEEEEE>
                <div className="flex justify-center items-center gap-x-[.5rem]">
                  <div className="h-[1.25rem]">
                    <Image
                      preview={false}
                      src={
                        datasets?.modalities.includes('text')
                          ? "/images/drawer/endpoints/text.png"
                          : "/images/drawer/endpoints/text-not.png"
                      }
                      alt={'Text'}
                      style={{ height: "1.25rem" }}
                    />
                  </div>
                  <div className="h-[1.25rem]">
                    <Image
                      preview={false}
                      src={
                        datasets?.modalities.includes('image')
                          ? "/images/drawer/endpoints/image.png"
                          : "/images/drawer/endpoints/image-not.png"
                      }
                      alt={'Image'}
                      style={{ height: "1.25rem" }}
                    />
                  </div>
                  <div className="h-[1.25rem]">
                    <Image
                      preview={false}
                      src={
                        datasets?.modalities.includes('audio')
                          ? "/images/drawer/endpoints/audio_speech.png"
                          : "/images/drawer/endpoints/audio_speech-not.png"
                      }
                      alt={'Audio'}
                      style={{ height: "1.25rem" }}
                    />
                  </div>
                </div>
                <Text_12_400_EEEEEE className="leading-[100%] capitalize">
                  {datasets?.modalities?.join(", ")}
                </Text_12_400_EEEEEE>
              </div>
            </div>
          </div>
          {datasets ? displaySections.map((item, sectionIndex) => datasets.additional_info?.[item?.keyName] && <div key={item.keyName || sectionIndex}>
            <div className="hR mt-[1.5rem]"></div>
            <div className="pt-[1.3rem]">
              <Text_14_400_EEEEEE>{item.header}</Text_14_400_EEEEEE>
              <Text_12_400_757575 className="pt-[.33rem]">
                {item.description}
              </Text_12_400_757575>
            </div>
            <div className="flex flex-wrap gap-2 mt-3">
              {datasets.additional_info?.[item?.keyName] ?
                (datasets.additional_info?.[item?.keyName] || []).map((tag, tagIndex) => <Tags
                  key={`${item.keyName}-${tag}-${tagIndex}`}
                  name={tag
                    .split("_")
                    .join(" ")
                  }
                  color="#D1B854"
                  classNames="text-center justify-center items-center capitalize"
                />) :
                <Text_12_400_757575> No Data Available </Text_12_400_757575>
              }
            </div>
          </div>) : null}

          {datasets && datasets.additional_info.age_distribution &&
          <>
            <div className="hR mt-[1.5rem]"></div>
            <div className="pt-[1.3rem]">
            <Text_14_400_EEEEEE>Age Distribution</Text_14_400_EEEEEE>
            <Text_12_400_757575 className="pt-[.33rem]">
              Following represents the age distribution for this evaluator
            </Text_12_400_757575>

            <div className="h-[232px]">
              <CompositeChart data={datasets.additional_info.age_distribution}/>
            </div>
          </div>
          </>}
        </div>
      </div>
    </div>
  );
}

export default LeaderboardDetails;

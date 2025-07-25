import React, { useEffect, useRef } from "react";
import {
  Checkbox,
  ConfigProvider,
  Dropdown,
  Image,
  MenuProps,
  Progress,
  Slider,
} from "antd";
import { Cluster } from "src/hooks/useCluster";
import CustomPopover from "src/flows/components/customPopover";
import {
  Text_12_400_B3B3B3,
  Text_14_400_EEEEEE,
  Text_14_600_EEEEEE,
  Text_12_400_EEEEEE,
  Text_12_400_757575,
  Text_10_400_EEEEEE,
  Text_10_400_B3B3B3,
  Text_18_400_EEEEEE,
  Text_8_400_EEEEEE,
} from "@/components/ui/text";
import Tags from "./DrawerTags";
import * as echarts from "echarts";
import DirectionArrowChart from "@/components/charts/directionArrowChart";
import { getCategories, getChartData } from "@/lib/utils";

type SingleGuageChartData = {
  data: number;
  label1: string;
  barColor: string;
};

const SingleGuageChart = ({ data }: { data: SingleGuageChartData }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (chartRef.current) {
      const containerWidth = chartRef.current.clientWidth;
      const containerHeight = chartRef.current.clientHeight;

      if (containerWidth === 0 || containerHeight === 0) {
        console.warn("bar Chart container has no width or height yet.");
        return;
      }
      const myChart = echarts.init(chartRef.current, null, {
        renderer: "canvas",
        useDirtyRect: false,
      });

      const option = {
        grid: {
          top: "0%",
          left: "0%",
          bottom: "0%",
          right: "0%",
        },
        series: [
          {
            type: "gauge",
            center: ["50%", "90%"],
            radius: "162%",
            startAngle: 180,
            endAngle: 0,
            min: 0,
            max: 100,
            splitNumber: 12,
            itemStyle: {
              color: data.barColor ? data.barColor : "#479D5F",
              shadowBlur: 10,
              shadowOffsetX: 2,
              shadowOffsetY: 2,
            },
            progress: {
              show: true,
              roundCap: true,
              width: 4,
            },
            pointer: {
              show: false,
            },
            axisLine: {
              roundCap: true,
              lineStyle: {
                width: 4,
                color: [
                  [1, "#1F1F1F"], // Set the gauge background color to #1F1F1F
                ],
              },
            },
            axisTick: {
              show: false,
              splitNumber: 2,
              lineStyle: {
                width: 2,
                color: "#999",
              },
            },
            splitLine: {
              show: false,
            },
            axisLabel: {
              show: false,
            },
            title: {
              show: false,
            },
            detail: {
              show: false,
            },
            data: [
              {
                value: data.data,
              },
            ],
          },
        ],
      };

      myChart.setOption(option);

      const handleResize = () => {
        myChart.resize();
      };

      window.addEventListener("resize", handleResize);

      return () => {
        window.removeEventListener("resize", handleResize);
        myChart.dispose();
      };
    }
  }, []);

  return (
    <div className="relative h-full">
      {/* <Text_12_500_FFFFFF className='block absolute top-[1.8em] left-[5em]'>{barChartData?.title}</Text_12_500_FFFFFF> */}
      {/* <Text className='block absolute -rotate-90 origin-top-left	 top-[50%] left-[.8rem] mt-[1.8rem] p-0 text-xs text-[#6A6E76] font-light h-[1rem] leading-[100%]'>{barChartData?.label1}</Text> */}
      <div
        ref={chartRef}
        style={{ width: "100%", height: "100%" }}
        className=""
      />
      {/* <Text className='block absolute m-auto bottom-3 left-[50%] top-auto p-0 text-xs text-[#6A6E76] font-light h-[1rem] leading-[100%]'>{barChartData?.label2}</Text> */}
      <div className="absolute flex flex-col justify-center items-center w-full px-[14%] mt-[-0.8rem]">
        {/* <Text_10_400_EEEEEE>{data.data?.toFixed(0)} %</Text_10_400_EEEEEE> */}
      </div>
    </div>
  );
};

function CompareGraph({ data }: { data: SingleGuageChartData }) {
  return (
    <div className="flex flex-col justify-start items-center w-[21%] mr-[.55rem]">
      <div className="max-w-[5.5rem]">
        <Text_10_400_B3B3B3 className="text-center">
          {data.label1}
        </Text_10_400_B3B3B3>
        <Text_10_400_EEEEEE className="text-center">
          {data.data.toFixed(2)} %
        </Text_10_400_EEEEEE>
      </div>
      <div className="w-[60%] h-[25px] mt-[.3rem]">
        <SingleGuageChart data={data} />
      </div>
    </div>
  );
}

export function ClusterCard({
  data,
  selected,
  handleClick,
  hideSelection,
  hideRank,
  ip,
}: {
  data: any;
  selected?: boolean;
  handleClick?: () => void;
  hideSelection?: boolean;
  hideRank?: boolean;
  ip: string;
}) {
  const [hover, setHover] = React.useState(false);

  const resource_details = {
    total: data.resource_details?.reduce(
      (sum, resource) => sum + resource.total,
      0
    ),
    available: data.resource_details?.reduce(
      (sum, resource) => sum + resource.available,
      0
    ),
  };

  useEffect(() => {
    console.log("data", data);
  }, [data]);

  const tagData = [
    { name: "CPU", color: "#D1B854", hide: !data?.cpu },
    { name: "HPU", color: "#D1B854", hide: !data?.gpu },
    { name: "GPU", color: "#D1B854", hide: !data?.gpu },
    { name: ip, color: "#965CDE" },
    {
      name: data?.events_count > 1 ? "High" : "Low",
      color: data?.events_count > 1 ? "#EC7575" : "#479D5F",
    },
  ]?.filter((item) => !item.hide);
  const chartData: SingleGuageChartData[] = [
    {
      barColor: "#D1B854",
      data: (data.cpu.current / data.cpu.capacity) * 100,
      label1: "CPU Requests",
    },
    {
      barColor: "#479D5F",
      data: (data.memory.current / data.memory.capacity) * 100,
      label1: "Memory Requests",
    },
  ];
  return (
    <div
      onMouseEnter={() => setHover(true)}
      onClick={handleClick}
      onMouseLeave={() => setHover(false)}
      className="clusterDropup border-b-[1px] border-[#757575] clusterCardRow w-full px-[1.4rem]  pt-[.95rem] pb-[.2rem]"
    >
      <div className="flex justify-between items-center w-full">
        <div
          className=""
          style={{
            width: hideSelection ? "100%" : "83%",
          }}
        >
          <div className="flex items-center justify-start">
            <Text_14_400_EEEEEE className="max-w-[100px]  1920px:max-w-[150px] 2560px:max-w-[250px] truncate overflow-hidden whitespace-nowrap leading-[100%]">
              {data.hostname}
            </Text_14_400_EEEEEE>
          </div>
        </div>

        {(hover || selected) && !hideSelection && (
          <div className="flex justify-end items-center cursor-pointer hover:text-[#EEEEEE]">
            <Checkbox
              checked={selected}
              className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]"
            />
          </div>
        )}
      </div>
      <div className="flex flex-col justify-start items-start w-full">
        <div className="flex justify-start items-start w-full pt-[.95rem]">
          <div className="flex flex-wrap justify-start items-start gap-x-[.5rem] gap-y-[.45rem] w-[30%] pl-[.5rem]">
            {tagData.map((item, index) => (
              <Tags
                key={index}
                name={item.name}
                color={item.color}
                classNames="py-[.26rem] px-[.4rem]"
              />
            ))}
          </div>
          {chartData.map((item, index) => (
            <CompareGraph key={index} data={item} />
          ))}
          <div className="flex flex-col justify-start items-center w-[20%]">
            <div>
              <Text_10_400_B3B3B3 className="text-center">
                Network I/O
              </Text_10_400_B3B3B3>
            </div>
            <div className="flex justify-center items-baseline mt-[0.05rem]">
              <Text_10_400_EEEEEE>{data?.network?.bandwidth[data?.network?.bandwidth.length - 1].mbps}</Text_10_400_EEEEEE>
              <Text_8_400_EEEEEE>Mbps</Text_8_400_EEEEEE>
            </div>
            <div className="w-full flex justify-center items-start px-[30%]">
              <DirectionArrowChart
                categories={getCategories(
                  "today",
                  data?.network.bandwidth?.map((item) => ({
                    timestamp: item.timestamp,
                    value: item.mbps,
                  }))
                )}
                data={getChartData(
                  "today",
                  data?.network.bandwidth?.map((item) => ({
                    timestamp: item.timestamp,
                    value: item.mbps,
                  }))
                )}
                chartAdjust={{ top: "0" }}
                classNames="h-[35px] pt-[5px]"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function NodesList({
  nodes,
  handleNodeSelection,
  selectedNodes,
  hideSelection,
  hideRank,
}: {
  nodes: any;
  handleNodeSelection?: (node: any) => void;
  selectedNodes?: any;
  hideSelection?: boolean;
  hideRank?: boolean;
}) {
  return Object.keys(nodes).map((key, index) => (
    <ClusterCard
      key={index}
      data={nodes[key]}
      ip={key}
      hideRank={hideRank}
      hideSelection={hideSelection}
      // selected={nodes[key].hostname === selectedNodes?.hostname} // Check if the cluster is selected
      selected={selectedNodes?.some(
        (selected) => selected.hostname === nodes[key].hostname
      )}
      handleClick={() => handleNodeSelection(nodes[key])} // Set the selected cluster
    />
  ));
}

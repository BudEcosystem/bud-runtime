import { Text_14_400_EEEEEE, Text_26_400_EEEEEE } from "@/components/ui/text";
import * as echarts from "echarts";
import React, { useEffect, useRef, useState } from "react";
import Tags from "src/flows/components/DrawerTags";
import { AppRequest } from "src/pages/api/requests";

interface BarChartProps {
  data?: {
    percentage: number;
    average?: number;
    tag?: string;
    reverse?: boolean;
  };
}
const GuageChart: React.FC<BarChartProps> = ({ data }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (chartRef.current) {
      const containerWidth = chartRef.current.clientWidth;
      const containerHeight = chartRef.current.clientHeight;
      const colors = ["#479D5F", "#D1B854", "#E36E4F"];
      if (data?.reverse) {
        colors.reverse();
      }

      if (containerWidth === 0 || containerHeight === 0) {
        console.warn("bar Chart container has no width or height yet.");
        return;
      }
      const myChart = echarts.init(chartRef.current, null, {
        renderer: "canvas",
        useDirtyRect: false,
      });

      const option = {
        series: [
          {
            center: ["50%", "90%"],
            radius: "160%",
            startAngle: 180,
            endAngle: 0,
            splitNumber: 0,
            type: "gauge",
            splitLine: {
              show: false,
            },
            anchor: {
              show: false,
            },
            pointer: {
              show: false,
            },

            progress: {
              show: true,
              overlap: true,
              roundCap: false,
            },

            axisTick: {
              show: false,
              length: 0,
            },
            axisLabel: {
              show: false,
            },
            axisLine: {
              roundCap: false,
              lineStyle: {
                width: 6, // Set desired stroke width
                color: [
                  [0.33, colors[0]], // Segmented colors
                  [0.66, colors[1]],
                  [1, colors[2]],
                ],
              },
            },
            data: [],
            title: {
              show: false,
            },
            detail: {
              show: false,
            },
          },
          {
            center: ["50%", "90%"],
            radius: "147%",
            startAngle: 180,
            endAngle: 0,
            splitNumber: 0,
            type: "gauge",
            splitLine: {
              show: false,
            },
            anchor: {
              show: false,
            },
            pointer: {
              show: false,
            },

            progress: {
              show: true,
              overlap: true,
              roundCap: false,
            },

            axisTick: {
              show: false,
              length: 0,
            },
            axisLabel: {
              show: false,
            },
            axisLine: {
              roundCap: false,
              lineStyle: {
                width: 37, // Set desired stroke width
                color:
                  data?.percentage > 0.01
                    ? data?.percentage < 33
                      ? [
                          [data?.percentage / 100, colors[0]], // Segmented colors
                          [1, "transparent"],
                        ]
                      : data?.percentage < 66
                        ? [
                            [0.33, colors[0]], // Segmented colors
                            [data?.percentage / 100, colors[1]],
                            [1, "transparent"],
                          ]
                        : [
                            [0.33, colors[0]], // Segmented colors
                            [0.66, colors[1]],
                            [data?.percentage / 100, colors[2]],
                            [1, "transparent"],
                          ]
                    : [
                        [0.01, colors[0]], // Segmented colors
                        [1, "transparent"],
                      ],
              },
            },
            data: [],
            title: {
              show: false,
            },
            detail: {
              show: false,
            },
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
  }, [data]);

  return (
    <div className="relative h-full mt-[.9rem]">
      {/* <Text_12_500_FFFFFF className='block absolute top-[1.8em] left-[5em]'>{barChartData?.title}</Text_12_500_FFFFFF> */}
      {/* <Text className='block absolute -rotate-90 origin-top-left	 top-[50%] left-[.8rem] mt-[1.8rem] p-0 text-xs text-[#6A6E76] font-light h-[1rem] leading-[100%]'>{barChartData?.label1}</Text> */}
      <div
        ref={chartRef}
        style={{ width: "100%", height: "100%" }}
        className=""
      />
      {/* <Text className='block absolute m-auto bottom-3 left-[50%] top-auto p-0 text-xs text-[#6A6E76] font-light h-[1rem] leading-[100%]'>{barChartData?.label2}</Text> */}
      <div className="absolute flex justify-between items-center w-full px-[14%] mt-[-1.05rem]">
        <Text_14_400_EEEEEE>0</Text_14_400_EEEEEE>
        <Text_14_400_EEEEEE>100</Text_14_400_EEEEEE>
      </div>
      <div className="absolute flex flex-col justify-center items-center w-full px-[14%] mt-[-5.8rem]">
        <Text_26_400_EEEEEE>
          {isNaN(data.percentage) ? 0 : (data.reverse ? 100 - data.percentage : data.percentage)}%
        </Text_26_400_EEEEEE>
        <div className="flex items-center justify-center mt-[.5rem]">
          <Tags
            name={
              <div className="flex items-center justify-between gap-1">
                {data.average && (
                  <>
                    <div className="text-[0.8125rem] text-[#479D5F] font-[400]">
                      Avg.{" "}
                      {data.average > 0 ? "+" : data.average < 0 ? "-" : ""}{" "}
                      {data.average}%
                    </div>
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width=".75rem"
                      height=".75rem"
                      viewBox="0 0 14 14"
                      fill="none"
                    >
                      <path
                        d="M11.8919 3.07815H9.49077C8.96251 3.07815 8.96251 3.87854 9.49077 3.87854H10.8554L7.5017 6.92797L6.16908 5.59535C6.02501 5.45128 5.7929 5.43926 5.63282 5.56733L1.23464 9.17306C0.822431 9.51322 1.33469 10.1255 1.74289 9.79337L5.86087 6.41969L7.20553 7.76435C7.3576 7.91642 7.59772 7.92043 7.7578 7.77635L11.4916 4.3827V5.87949C11.4916 6.40775 12.292 6.40775 12.292 5.87949V3.47832C12.292 3.27421 12.1159 3.07812 11.8918 3.07812L11.8919 3.07815Z"
                        fill="#479D5F"
                      />
                    </svg>
                  </>
                )}
                {data.tag && (
                  <div className="text-[0.8125rem] text-[#479D5F] font-[400]">
                    {data.tag}
                  </div>
                )}
              </div>
            }
            classNames="w-fit !py-[.25rem]"
            color="#479D5F"
          />
        </div>
      </div>
    </div>
  );
};

export default GuageChart;
